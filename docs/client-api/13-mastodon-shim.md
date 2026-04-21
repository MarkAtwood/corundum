# Mastodon Compatibility Shim

Any Mastodon client — Ivory, Tusky, Elk, Pinafore, and any other app built against the Mastodon API — can connect to a Corundum operator through a shim layer that translates between the two protocols. The shim presents a standard Mastodon API surface to clients and speaks the native Corundum client API (or Corundum operator internals) on the backend.

This document designs that shim: what state it holds, how ID mapping works, how it handles signing, and where the translation is lossless versus approximate.

---

## What the Shim Does and Does Not Do

The shim makes Mastodon clients work. It does not make Mastodon clients aware of Corundum. From the client's perspective, it is connecting to a Mastodon server. All the Corundum-specific features — signing transparency, CID-addressed content, IPNS identity, curation authority declarations, hostile migration — are invisible to Mastodon clients. They continue to exist and operate on the Corundum side; they simply have no surface in the Mastodon API.

A user who connects via a Mastodon client still benefits from Corundum's architecture: their content is stored in IPFS, their identity is portable, block enforcement is protocol-level, and curation operates. They just cannot see or use those features through a Mastodon client. A user who later switches to a native Corundum client finds their full account intact.

---

## Deployment Architecture

The shim can be deployed in two configurations:

### Sidecar (Recommended)

The shim runs alongside the Corundum operator on the same host and shares its database and signing keys directly. No network hop between shim and operator. The shim exposes Mastodon API endpoints on a separate port (or path prefix); the operator exposes Corundum native endpoints.

```
Internet
  │
  ├─ HTTPS :443 /api/v1/ (Mastodon)  ──→  [ Mastodon Shim ]
  │                                           │  │
  │                                           │  └─ shared SQLite (ID maps, keys)
  │                                           │
  └─ HTTPS :443 /corundum/ (native)  ──→  [ Corundum Operator ]
                                              │
                                              └─ Kubo (IPFS)
```

The sidecar shares the operator's SQLite database and adds its own tables (ID mapping, session state). It has direct access to the user's signing key material rather than going through an API.

### Reverse Proxy

The shim sits in front of a separately deployed Corundum operator and speaks the native Corundum client API to it. Maintains its own database for ID mapping and key storage. A clean separation of concerns; the operator is unmodified.

```
Internet
  │
  └─ HTTPS :443  ──→  [ Mastodon Shim ]  ──→  [ Corundum Operator ]  ──→  Kubo
                            │
                            └─ local SQLite (ID maps, keys, sessions)
```

The reverse proxy model is easier to operate independently (the shim can be updated without touching the operator) but adds a network hop on every request.

---

## State the Shim Holds

The shim needs durable state that survives restarts. All of it lives in a local SQLite database (or the shared operator database in the sidecar configuration).

### ID Mapping Tables

The central challenge is that Mastodon clients use 64-bit integer IDs and pass them in URLs, request bodies, and pagination cursors. Corundum uses CIDs (base32lower, ~60 characters) for content and IPNS names (base36lower, ~60 characters) for accounts. The shim maintains bidirectional maps.

```sql
-- Status ID mapping
CREATE TABLE mastodon_status_ids (
    mastodon_id   INTEGER PRIMARY KEY,  -- assigned by shim, monotonically increasing
    corundum_cid  TEXT    UNIQUE NOT NULL,
    created_at    INTEGER NOT NULL,     -- unix timestamp; drives ordering
    author_ipns   TEXT    NOT NULL
);
CREATE INDEX idx_status_cid ON mastodon_status_ids(corundum_cid);
CREATE INDEX idx_status_time ON mastodon_status_ids(created_at DESC);

-- Account ID mapping
CREATE TABLE mastodon_account_ids (
    mastodon_id   INTEGER PRIMARY KEY,  -- assigned by shim, monotonically increasing
    corundum_ipns TEXT    UNIQUE NOT NULL,
    first_seen    INTEGER NOT NULL      -- unix timestamp
);
CREATE INDEX idx_account_ipns ON mastodon_account_ids(corundum_ipns);
```

**ID assignment**: When the shim encounters a Corundum CID or IPNS name it has not seen before — from a timeline fetch, incoming notification, or search result — it inserts a row and the database assigns the next integer ID. The integer is meaningless outside this shim's database; it is a local handle for this mapping.

**Ordering property**: Mastodon clients rely on integer IDs being roughly chronological for pagination (higher ID = newer). The shim preserves this by ordering `mastodon_id` assignment by `created_at`. As long as the shim assigns IDs in arrival order (which it does, since it inserts when it first encounters content), the ordering property holds.

**Collision**: There is no collision risk. Each CID is globally unique by construction (it is a content hash). Each IPNS name is globally unique (it is a public key hash). The mapping is injective.

**Portability caveat**: These integer IDs are shim-local. If the shim database is lost or reset, new integers are assigned. Mastodon clients that have bookmarked or cached status IDs will not find them at the new integers. This is an inherent limitation of the translation: Mastodon's integer IDs are not portable, but the underlying Corundum CIDs are. A client that stores the CID (via a native Corundum client) is unaffected; a Mastodon client that stores only the integer loses the reference.

### Signing Keys

Mastodon clients have no concept of signing keys. They submit post text; the server handles storage. For Corundum, someone must hold the Ed25519 private key to produce SigningRecords.

The shim holds the key. This places the shim at the operator-as-notary end of the trust axis (see `12-alternative-shapes.md`). Users are trusting the shim not to misuse their signing key, the same trust they place in any Mastodon server. For users who want key custody, a native Corundum client with E2E signing is the right choice; the Mastodon shim cannot offer that.

```sql
CREATE TABLE user_signing_keys (
    user_ipns          TEXT PRIMARY KEY,
    private_key_bytes  BLOB NOT NULL,  -- encrypted at rest with operator master key
    algorithm          TEXT NOT NULL DEFAULT 'ed25519',
    created_at         INTEGER NOT NULL,
    last_used          INTEGER
);
```

Keys are encrypted at rest. The operator holds a master key (from an environment variable or hardware security module); individual signing keys are encrypted with it. A compromise of the database without the master key does not expose signing keys.

### OAuth and Session State

Mastodon OAuth is close enough to Corundum's OAuth that the same tables serve both. The shim issues its own access tokens (Mastodon-style bearer tokens) that it maps to Corundum user sessions.

```sql
CREATE TABLE oauth_apps (
    client_id     TEXT PRIMARY KEY,
    client_secret TEXT NOT NULL,
    name          TEXT NOT NULL,
    redirect_uris TEXT NOT NULL,
    scopes        TEXT NOT NULL,
    website       TEXT
);

CREATE TABLE oauth_tokens (
    token         TEXT PRIMARY KEY,
    user_ipns     TEXT NOT NULL,
    client_id     TEXT NOT NULL,
    scopes        TEXT NOT NULL,
    created_at    INTEGER NOT NULL,
    FOREIGN KEY (user_ipns) REFERENCES user_signing_keys(user_ipns)
);
```

---

## Endpoint Translation Map

### OAuth and Authentication

| Mastodon endpoint | Translation |
|-------------------|-------------|
| `POST /api/v1/apps` | Direct: shim registers app, returns Mastodon-shaped response |
| `GET /oauth/authorize` | Direct: shim handles auth flow, issues its own token |
| `POST /oauth/token` | Direct: shim validates, issues bearer token mapping to `user_ipns` |
| `POST /oauth/revoke` | Direct: shim deletes token |
| `GET /api/v1/instance` | Translated: shim returns Mastodon-shaped instance info; `version` field set to `"4.x.x (Corundum)"` to indicate compatibility; Corundum-specific extension fields omitted |

### Statuses

| Mastodon endpoint | Translation |
|-------------------|-------------|
| `POST /api/v1/statuses` | Shim receives post text → constructs ActivityStreams object → signs with held key → submits to Corundum → receives CID → assigns/looks up integer ID → returns Mastodon Status entity |
| `GET /api/v1/statuses/:id` | Shim looks up CID from integer ID → fetches from Corundum → returns translated Status entity |
| `DELETE /api/v1/statuses/:id` | Shim looks up CID → submits delete/tombstone to Corundum → returns translated deleted status |
| `PUT /api/v1/statuses/:id` | Shim looks up CID → submits edit to Corundum → new CID → assigns new integer ID → returns translated Status entity |
| `GET /api/v1/statuses/:id/context` | Shim looks up CID → fetches reply tree from Corundum → translates all CIDs in ancestors/descendants to integer IDs → returns |
| `POST /api/v1/statuses/:id/reblog` | Look up CID → submit boost → translate response |
| `POST /api/v1/statuses/:id/favourite` | Look up CID → submit favourite → translate response |

**In-reply-to translation**: When a Mastodon client creates a reply, it sends `in_reply_to_id` as a Mastodon integer. The shim looks up the CID for that integer and submits the reply to the Corundum operator with the correct CID reference. The inter-operator reply protocol proceeds normally, including block enforcement.

**Status entity translation**:

```
Corundum Status                     Mastodon Status
────────────────────────────────    ──────────────────────────────────
cid (e.g. bafyrei...)           →   id (integer from mastodon_status_ids)
author.ipns_name                →   account.id (integer from mastodon_account_ids)
content                         →   content (unchanged)
created_at                      →   created_at (unchanged)
in_reply_to.cid                 →   in_reply_to_id (integer lookup)
in_reply_to.author_ipns         →   in_reply_to_account_id (integer lookup)
corundum.curation_labels        →   (omitted, or surfaced as filtered if policy requires)
corundum.signing_record_cid     →   (omitted)
```

### Timelines

| Mastodon endpoint | Translation |
|-------------------|-------------|
| `GET /api/v1/timelines/home` | Fetch from Corundum home timeline → translate all CIDs to integers → return statuses |
| `GET /api/v1/timelines/public` | Fetch from Corundum public timeline → translate → return |
| `GET /api/v1/timelines/tag/:hashtag` | Fetch → translate → return |

**Pagination translation**: Mastodon clients send `max_id` and `min_id` as integers. The shim looks up the corresponding CID for each cursor value and passes the CID cursor to Corundum. The `Link` header in the response translates back to integer cursors before returning to the client.

### Accounts

| Mastodon endpoint | Translation |
|-------------------|-------------|
| `GET /api/v1/accounts/verify_credentials` | Fetch own profile from Corundum → translate IPNS name to integer ID → return Account entity |
| `PATCH /api/v1/accounts/update_credentials` | Forward profile update to Corundum → translate response |
| `GET /api/v1/accounts/:id` | Look up IPNS from integer ID → fetch profile → translate → return |
| `GET /api/v1/accounts/:id/statuses` | Look up IPNS → fetch statuses → translate all CIDs and IPNS names → return |
| `GET /api/v1/accounts/lookup` | Forward `acct` param → receive Corundum account → assign/look up integer ID → return |

**Account entity translation**:

```
Corundum Account                    Mastodon Account
────────────────────────────────    ──────────────────────────────────
ipns_name                       →   id (integer from mastodon_account_ids)
username                        →   username (unchanged)
acct                            →   acct (unchanged)
display_name                    →   display_name (unchanged)
corundum.did                    →   (omitted)
corundum.operator_endpoint      →   (omitted)
corundum.root_manifest_cid      →   (omitted)
```

The `moved_to` field (Mastodon's shallow migration indicator) can be set when the Corundum account has a migration notification, translating to the Mastodon client's understanding of account moves. This is approximate: Mastodon's `moved_to` is advisory, while Corundum migration is protocol-level. But it surfaces the fact that an account has moved.

### Notifications

| Mastodon endpoint | Translation |
|-------------------|-------------|
| `GET /api/v1/notifications` | Fetch from Corundum → translate status and account references to integers → translate Corundum notification types to Mastodon types → return |
| `POST /api/v1/notifications/clear` | Forward → return |
| `POST /api/v1/notifications/:id/dismiss` | Forward → return |

**Notification type translation**:

| Corundum type | Mastodon type | Notes |
|---------------|---------------|-------|
| `mention` | `mention` | Direct |
| `reblog` | `reblog` | Direct |
| `favourite` | `favourite` | Direct |
| `follow` | `follow` | Direct |
| `follow_request` | `follow_request` | Direct |
| `poll` | `poll` | Direct |
| `corundum.block_enforcement` | (omitted) | No Mastodon equivalent; silently dropped |
| `corundum.migration_incoming` | `follow` (approximate) | Surfaced as a follow from the new account location |
| `corundum.curation_flagged` | `admin.report` (approximate) | Approximate; not accurate but surfaces the event |

`corundum.block_enforcement` — the notification that your submitted reply was protocol-level rejected — is the most significant loss. Mastodon clients will not see it. This is acceptable: the underlying block enforcement still happens; the client just does not receive the feedback notification.

### Relationships (Follow, Block, Mute)

These are the most semantically clean translations. The Mastodon follow, block, and mute endpoints map directly to their Corundum equivalents. The differences are invisible to the client:

- A Corundum block enforces at the protocol level; the Mastodon client just sees `blocked: true` in the Relationship entity.
- A Corundum follow triggers IPFS-backed timeline access; the Mastodon client just sees new statuses in the home timeline.

The Relationship entity translation:

```
Corundum Relationship               Mastodon Relationship
────────────────────────────────    ──────────────────────────────────
following                       →   following
followed_by                     →   followed_by
blocking                        →   blocking
muting                          →   muting
corundum.block_enforced         →   (omitted; always true when blocking=true)
```

### Media

Media upload translates cleanly. The shim accepts `multipart/form-data` from the Mastodon client, forwards to Corundum, receives a CID back, and returns a Mastodon-shaped MediaAttachment entity with the `id` field set to an assigned integer. The `url` field points to an IPFS gateway URL.

```
Corundum MediaAttachment            Mastodon MediaAttachment
────────────────────────────────    ──────────────────────────────────
corundum.media_cid              →   id (integer lookup)
url (IPFS gateway)              →   url
preview_url                     →   preview_url
description                     →   description
```

---

## Streaming

Mastodon clients connect to `GET /api/v1/streaming` over WebSocket and subscribe to streams: `user` (home timeline + notifications), `public`, `public:local`, `hashtag`, `list`, `direct`.

The shim translates Corundum's native event stream into Mastodon-compatible streaming events:

```
Corundum event stream              Mastodon streaming event
───────────────────────────────    ──────────────────────────────────
new_status (with CID)          →   event: update\ndata: {Status entity}
delete_status (with CID)       →   event: delete\ndata: {integer_id}
notification (Corundum type)   →   event: notification\ndata: {Notification entity}
```

The shim must:
1. Accept the WebSocket connection and identify the stream type
2. Subscribe to the corresponding Corundum event stream
3. For each incoming event, look up or assign integer IDs for all CIDs and IPNS names in the event
4. Serialize the translated entity and push it to the client

The ID assignment in the streaming path is the same as in the request path. If a new status arrives over the event stream before the client has fetched it via HTTP, the shim assigns an integer ID at event time and will return the same integer if the client later fetches it by URL.

---

## What Mastodon Clients Cannot Access

These Corundum capabilities have no surface in the Mastodon API and are not exposed by the shim:

| Corundum Feature | Status in Shim |
|-----------------|----------------|
| Signing transparency (`/signing_record`) | Exists in Corundum; not exposed to Mastodon clients |
| Curation label detail | Exists; not exposed (optionally surfaced as `filtered`) |
| Authority declarations | Exists; not exposed |
| ArchiveIndex / epoch structure | Exists; not exposed |
| IPNS name (stable identity) | Exists; exposed only as the integer account ID |
| DID document | Exists; not exposed |
| Identity migration | Exists; surfaced approximately via `moved_to` |
| Key rotation | Exists; transparent to client (shim rotates key, client sees nothing) |
| E2E signing | Not available through shim (shim holds keys by necessity) |
| Content verification by CID | Not available through shim (client never sees CIDs) |

---

## Limitations and Caveats

**Integer IDs are shim-local.** They are assigned by the shim's database and have no meaning outside it. If the shim is reset, migrated without its database, or run as two independent instances, the same underlying Corundum content will receive different integer IDs. Bookmarks and saved references in Mastodon clients become stale. The underlying Corundum content is unaffected; only the translation layer breaks.

**The shim is the trust boundary.** Users connecting via Mastodon clients are trusting the shim with their signing key. This is the same trust model as any Mastodon server and is acceptable for most users. Users who want cryptographic assurance that the operator cannot impersonate them must use a native Corundum client with E2E signing.

**No Corundum feature discovery.** Mastodon clients will not know they are connected to a Corundum operator. The `/api/v1/instance` response can include a version string like `4.3.0 (Corundum)`, which surfaces the fact that the server is Corundum-backed for clients that display version information, but no standardized Mastodon mechanism exists for advertising protocol extensions.

**Curation is silent.** If a curation rule causes an incoming reply submission to be rejected at the inter-operator level, the Mastodon client receives no feedback. The Corundum-native `corundum.block_enforcement` and `corundum.curation_flagged` notifications are dropped. This is worse than the native client experience but consistent with Mastodon's opacity around moderation.

**Post editing semantics differ.** Mastodon's edit model creates edit history attached to the same integer ID. Corundum's edit model creates a new CID (the content changes, so the hash changes) with a `predecessor_cid` link. The shim handles this by assigning a new integer ID for the edited version and updating the previous ID's record to point to the new one, while retaining the edit history in the Mastodon-shaped response. Clients that refresh a status by its old integer ID will receive the latest version.

**Scale**: In a high-volume deployment, the ID mapping table grows without bound — one row per status ever seen. Periodic pruning of rows older than some retention window (e.g., 90 days) keeps the table manageable. Statuses that have been pruned from the map will return `404` if a Mastodon client requests them by old integer ID; the underlying Corundum content is unaffected.
