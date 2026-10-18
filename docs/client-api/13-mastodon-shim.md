# Mastodon Compatibility Shim

Any Mastodon client — Ivory, Tusky, Elk, Pinafore, and any other app built against the Mastodon API — can connect to a Corundum operator through a shim layer that translates between the two APIs. The shim presents a standard Mastodon API surface to clients and speaks the native reference API (or Corundum operator internals) on the backend.

This document designs that shim: what state it holds, how ID mapping works, how posting is signed, and where the translation is lossless versus approximate. Like the rest of this directory it is non-normative.

---

## What the Shim Does and Does Not Do

The shim makes Mastodon clients work. It does not make Mastodon clients aware of Corundum. From the client's perspective, it is connecting to a Mastodon server. Corundum-specific features — signing transparency, CID-addressed content, DID identity, curation authority declarations, migration — are invisible to Mastodon clients. They continue to exist and operate on the Corundum side; they simply have no surface in the Mastodon API.

A user who connects via a Mastodon client still benefits from Corundum's architecture: their content is stored in IPFS, their identity is portable, blocks keep blocked users out of their reply trees, and curation operates. They just cannot see or use those features through a Mastodon client. A user who later switches to a native Corundum client finds their full account intact.

**Posting requires operator custody.** Mastodon apps submit post text and expect the server to publish it; they cannot sign anything. The shim can therefore publish only for users whose operator holds their content key (`key_custody` `operator`, `10-identity-migration.md`). For self-custody users, the shim serves every read endpoint, but every write that would publish an activity or change the RootManifest — posting, editing, deleting, boosting, favouriting, following, blocking, muting, profile updates — returns `422` with a Mastodon error body:

```json
{ "error": "This account signs its own posts. Use a Corundum client to post." }
```

---

## Paths

One rule keeps the two surfaces apart on one host, in either deployment:

| Prefix | Owner |
|--------|-------|
| `/api/v1/`, `/api/v2/` (including `/api/v1/streaming`) | Mastodon shim |
| `/api/corundum/v1/` | Native reference API (`00-design.md`) |
| `/oauth/` | One authorization server shared by both. A token is valid on both surfaces, within its scopes. |
| `/corundum/v1/`, `/.well-known/corundum-operator` | Server-to-server protocol (spec). Nothing client-facing lives here. |

Mastodon `id` values are integers and native ids are CIDs and DIDs, so the two surfaces never share a path.

---

## Deployment Architecture

The shim can be deployed in two configurations.

### Sidecar (Recommended)

The shim runs alongside the Corundum operator on the same host and calls the operator's internals directly, with no network hop between shim and operator.

```
Internet
  │
  ├─ HTTPS :443 /api/v1/, /api/v2/   ──→  [ Mastodon Shim ]
  │                                           │
  │                                           ├─ shared database (shim tables)
  │                                           │
  ├─ HTTPS :443 /api/corundum/v1/    ──→  [ Corundum Operator ] ── Kubo (IPFS)
  ├─ HTTPS :443 /oauth/              ──→        (shared OAuth server)
  └─ HTTPS :443 /corundum/v1/        ──→        (server-to-server)
```

The sidecar adds its own tables (ID mapping, edit chains) to the operator's database.

### Reverse Proxy

The shim sits in front of a separately deployed Corundum operator and speaks the native reference API to it, with its own database for ID mapping. A clean separation of concerns; the operator is unmodified.

```
Internet
  │
  └─ HTTPS :443  ──→  [ Mastodon Shim ]  ──→  [ Corundum Operator ]  ──→  Kubo
                            │
                            └─ local database (ID maps, edit chains)
```

The reverse proxy model is easier to operate independently (the shim can be updated without touching the operator) but adds a network hop on every request.

### Signing

The shim holds no keys in either configuration. When a Mastodon client posts, the shim asks the operator to publish through its normal operator-custody path: the sidecar calls the operator's internal publish function, and the reverse proxy calls `POST /api/corundum/v1/statuses` with the user's token. The operator builds the activity, signs the SigningRecord with the content key it holds, and publishes. The shim never sees a private key, so compromising the shim does not expose one.

---

## State the Shim Holds

The shim's state is small, and every row of it can be rebuilt: integer IDs are derived deterministically from Corundum identifiers.

### Status IDs

Mastodon clients use 64-bit integer IDs, pass them in URLs, request bodies, and pagination parameters, and assume that a higher ID is a newer status. The shim derives each status's integer from the activity itself, the way Mastodon derives its own snowflake IDs:

```
mastodon_id = (published_ms << 16) | (first 16 bits of SHA-256(activity id))
```

`published_ms` is the activity's `published` time in milliseconds since the Unix epoch. For an edited post it is the `published` time of the first version (see Edits below).

A first design assigned integers in arrival order, as rows were inserted. That broke ordering: content the shim first saw late — an old post fetched while loading a thread, a remote account's backfilled history, a boosted post from last year — got the newest integer and sorted to the top of timelines, and `max_id` paging skipped or repeated items around it. Deriving the ID from `published` sorts by creation time, whenever the shim happens to see the post.

`published` is author-controlled, so an author can backdate a post, and an activity may be up to five minutes in the future (spec Chapter 34). Mastodon has the same property for remote statuses, whose IDs it derives from their claimed creation time.

Because the ID is a function of the activity, the mapping table is a cache:

```sql
CREATE TABLE mastodon_status_ids (
    mastodon_id   INTEGER PRIMARY KEY,
    activity_id   TEXT    UNIQUE NOT NULL,   -- CID; for an edited post, the first version
    collided      INTEGER NOT NULL DEFAULT 0 -- 1 if the low bits were bumped
);
```

The shim needs the table only to go from an integer back to an activity id. It can prune rows freely: when it meets the activity again it derives the same integer. The one exception is a collision — two activities with the same millisecond and the same 16 hash bits. The shim then increments the low bits until it finds a free value, records the row with `collided = 1`, and never prunes it, since that value could not be re-derived. If the shim database is lost entirely, every non-collided ID comes back unchanged.

### Account IDs

Account IDs do not need to sort by time. The shim derives them from the DID:

```
mastodon_account_id = first 63 bits of SHA-256(DID), as a decimal integer
```

The DID does not change when a user migrates, rotates keys, or changes handle, so neither does their Mastodon account ID. The shim keeps a `mastodon_account_ids(mastodon_id, did)` table to map back, and treats a collision (negligible at 63 bits) as an error to report rather than resolve.

### Other IDs

Notification IDs are derived like status IDs, from the notification's `created_at` and a hash of the native notification id. Media attachment IDs map the operator-local native media id (`08-media.md`) to an integer, from the upload time and a hash of the media id.

### Edit Chains

A Mastodon edit keeps the status ID; a Corundum edit is a new activity with a new id and a `replaces` link (spec Chapter 13). The shim maps each edit chain to the Mastodon ID of its first version:

```sql
CREATE TABLE edit_chain (
    first_activity_id   TEXT PRIMARY KEY,
    latest_activity_id  TEXT NOT NULL
);
```

When the shim sees a status whose `corundum.replaces` is set, it walks `replaces` back to the first version (native timelines already place an edited post at its first version's position, `02-entities.md`), uses that version's Mastodon ID, and updates `latest_activity_id`.

### OAuth State

The shim uses the shared authorization server (`01-auth.md`), so it adds no token tables of its own. Tokens are bound to the user's DID:

```sql
CREATE TABLE oauth_tokens (
    token         TEXT PRIMARY KEY,
    user_did      TEXT NOT NULL,
    client_id     TEXT NOT NULL,
    scopes        TEXT NOT NULL,
    created_at    INTEGER NOT NULL
);
```

Mastodon scope names map to native scopes: `read` and `write` (and their `read:*` and `write:*` subscopes) map to the native scopes of the same name; `follow` maps to `read:follows`, `write:follows`, `read:blocks`, `write:blocks`, `read:mutes`, and `write:mutes`; `push` is not supported, because the shim does not implement Web Push.

---

## Endpoint Translation Map

### OAuth and Authentication

| Mastodon endpoint | Translation |
|-------------------|-------------|
| `POST /api/v1/apps` | Registers the app with the shared authorization server; returns a Mastodon-shaped response |
| `GET /oauth/authorize`, `POST /oauth/token`, `POST /oauth/revoke` | Shared authorization server; Mastodon scope names translated as above |
| `GET /api/v1/instance`, `GET /api/v2/instance` | Mastodon-shaped instance info; `version` set to `"4.x.x (Corundum)"` to indicate compatibility; Corundum extension fields omitted |

### Statuses

| Mastodon endpoint | Translation |
|-------------------|-------------|
| `POST /api/v1/statuses` | Map `in_reply_to_id` and `media_ids[]` to native ids → native `POST /api/corundum/v1/statuses` → derive the Mastodon ID → return a Mastodon Status entity |
| `GET /api/v1/statuses/:id` | Integer → activity id (latest version of the chain) → native `GET` → translate |
| `PUT /api/v1/statuses/:id` | Integer → latest version → native `PUT` on it → new activity id recorded in `edit_chain` → return the Status with the same Mastodon ID and `edited_at` set to the new version's `created_at` |
| `GET /api/v1/statuses/:id/history` | Walk `replaces` from the latest version back to the first → return Mastodon StatusEdit entities, oldest first |
| `GET /api/v1/statuses/:id/source` | Fetch the latest version's activity bytes → return its plain `content` and `summary` |
| `DELETE /api/v1/statuses/:id` | Integer → latest version → native `DELETE` (publishes a `Delete` activity) → return the deleted Status, as Mastodon does for delete-and-redraft |
| `GET /api/v1/statuses/:id/context` | Native context → translate every status and account reference to integers |
| `POST /api/v1/statuses/:id/reblog`, `.../unreblog` | Native reblog (an `Announce`) or unreblog (a `Delete` of the `Announce`) |
| `POST /api/v1/statuses/:id/favourite`, `.../unfavourite` | Native favourite (a `Like`) or unfavourite (a `Delete` of the `Like`) |

**Visibility.** Corundum carries only the public conversation (spec Chapter 40). A post with `visibility` `public` (or none) is published normally. `unlisted`, `private`, and `direct` are rejected with `422` and a Mastodon error body, rather than published more widely than the user chose.

**In-reply-to translation.** A Mastodon reply sends `in_reply_to_id` as an integer. The shim maps it to the activity id the user saw (the latest version) and the operator submits the reply through the inter-operator reply protocol. If the parent's operator rejects it (for example, `REPLY_REJECTED` with reason `blocked-user`), the native API reports that with a `corundum.reply_rejected` notification, which the shim cannot surface (see Notifications).

**Status entity translation:**

```
Native Status                           Mastodon Status
────────────────────────────────────    ──────────────────────────────────
id (activity id)                    →   id (snowflake of the first version)
account.id (DID)                    →   account.id (hash of DID)
content, created_at                 →   content (unchanged); created_at of the first version
created_at of the latest version    →   edited_at (null if never edited)
in_reply_to_id (activity id)        →   in_reply_to_id (integer)
in_reply_to_account_id (DID)        →   in_reply_to_account_id (integer)
visibility ("public")               →   visibility ("public")
corundum.curation_labels            →   (omitted, or surfaced as `filtered` if policy requires)
corundum.signing_record_cid, seq,   →   (omitted)
  epoch, replaces, replaced_by
```

### Timelines

| Mastodon endpoint | Translation |
|-------------------|-------------|
| `GET /api/v1/timelines/home` | Native home timeline → translate → return |
| `GET /api/v1/timelines/public` | Native public timeline → translate → return |
| `GET /api/v1/timelines/tag/:hashtag` | Native hashtag timeline → translate → return |
| `GET /api/v1/timelines/list/:list_id` | Native list timeline → translate → return |

**Pagination translation.** Mastodon clients page with `max_id`, `since_id`, and `min_id`, and they construct these from status IDs they already hold. The native API takes only opaque cursors plus `before` and `after` time filters (`00-design.md`). Because a Mastodon status ID encodes its sort time, the shim translates without any lookup: `max_id` becomes `before` set to the ID's millisecond plus one, and `since_id`/`min_id` become `after` set to the ID's millisecond minus one. The shim then drops items whose Mastodon ID is not strictly beyond the requested one, which makes the boundary exact even when several items share a millisecond. `min_id` returns the oldest items after the boundary and `since_id` the newest, as in Mastodon. The shim builds the Mastodon `Link` header from the first and last IDs it returns.

### Accounts

| Mastodon endpoint | Translation |
|-------------------|-------------|
| `GET /api/v1/accounts/verify_credentials` | Native verify_credentials → translate |
| `PATCH /api/v1/accounts/update_credentials` | Native update_credentials → translate |
| `GET /api/v1/accounts/:id` | Integer → DID → native account → translate |
| `GET /api/v1/accounts/:id/statuses` | Integer → DID → native account statuses → translate |
| `GET /api/v1/accounts/lookup` | Native lookup by `acct` → translate |

**Account entity translation:**

```
Native Account                          Mastodon Account
────────────────────────────────────    ──────────────────────────────────
id (DID)                            →   id (hash of DID)
username, acct, display_name, ...   →   (unchanged)
corundum.ipns_name                  →   (omitted)
corundum.operator_endpoint          →   (omitted)
corundum.root_manifest_cid          →   (omitted)
corundum.key_custody                →   (omitted)
```

**Migration.** When an account moves to a new operator, its DID — and so its Mastodon account ID — does not change, and the shim's next fetch returns the new `acct` and profile. Nothing else needs translating. The shim does not set Mastodon's `moved` field, which tells clients the account is abandoned and points them at a different account; here the account is the same one and keeps working.

### Notifications

| Mastodon endpoint | Translation |
|-------------------|-------------|
| `GET /api/v1/notifications` | Native notifications → translate references → translate types → return |
| `GET /api/v1/notifications/:id` | Integer → native id → translate |
| `POST /api/v1/notifications/clear` | Forward → return |
| `POST /api/v1/notifications/:id/dismiss` | Forward → return |

**Notification type translation:**

| Native type | Mastodon type | Notes |
|-------------|---------------|-------|
| `mention`, `reblog`, `favourite`, `follow`, `follow_request`, `poll`, `status` | same | Direct |
| `corundum.reply_rejected` | (dropped) | No Mastodon equivalent |
| `corundum.account_migrated` | (dropped) | The account ID is unchanged; see Migration above. It is not a follow. |
| `corundum.curation_flagged` | (dropped) | Mastodon's `admin.report` and `moderation_warning` mean different things (a report to moderators; a warning from the user's own server) |

### Relationships (Follow, Block, Mute)

These translate directly. The Mastodon follow, block, and mute endpoints map to the native endpoints of the same names, with the integer account ID mapped to the DID. The differences are invisible to the client:

- A Corundum block keeps the blocked account out of the user's reply trees for every reader; the Mastodon client sees `blocking: true`.
- A Corundum follow notifies the followee's operator; the Mastodon client sees new statuses in the home timeline.

The native Relationship entity has only Mastodon fields (`02-entities.md`), so the translation maps `id` and nothing else.

### Media

Media upload translates cleanly. The shim accepts `multipart/form-data` at `POST /api/v1/media` or `POST /api/v2/media`, forwards it to `POST /api/corundum/v1/media`, and returns a Mastodon-shaped MediaAttachment entity (`202` while processing, as Mastodon's v2 endpoint does).

```
Native MediaAttachment                  Mastodon MediaAttachment
────────────────────────────────────    ──────────────────────────────────
id (operator-local media id)        →   id (integer)
url (IPFS gateway)                  →   url
preview_url, description, meta      →   (unchanged)
corundum.media_cid                  →   (omitted)
```

---

## Streaming

Mastodon clients connect to `GET /api/v1/streaming` over WebSocket (or its SSE variants) and subscribe to streams such as `user`, `public`, `public:local`, `hashtag`, `list`, and `direct`. The shim implements these by translating the native event stream (`14-event-stream.md`: SSE at `GET /api/corundum/v1/streaming`), so it depends on that file's topics and event names.

Stream mapping:

| Mastodon stream | Native topics |
|-----------------|---------------|
| `user` | `home` and `notifications` |
| `user:notification` | `notifications` |
| `public`, `public:local`, `hashtag`, `hashtag:local`, `list` | Not supported: the native stream has no public, hashtag, or list topics. The shim rejects these subscriptions with an `error` message, and clients fall back to polling. |
| `direct` | Not supported: Corundum has no direct messages. |

Event mapping:

| Native event | Mastodon event |
|--------------|----------------|
| `timeline.entry.created` | `update`, payload the translated Status |
| `timeline.entry.edited` | `status.update`, payload the translated Status (same Mastodon ID as the first version, `edited_at` set) |
| `timeline.entry.deleted` | `delete`, payload the Mastodon ID of the first version of the deleted status |
| `notification` | `notification`, payload the translated Notification (dropped if its type is dropped above) |
| `heartbeat` | WebSocket ping (or an SSE comment line) |
| `reply.accepted`, `curation.entry.created` | (dropped) No Mastodon equivalent |

The shim keeps one native stream per connected Mastodon client, passes the native `Last-Event-ID` through when it reconnects, and derives integer IDs for every status and account in an event exactly as in the request path, so an ID first seen on the stream is the same ID the client later gets over HTTP.

---

## What Mastodon Clients Cannot Access

These Corundum capabilities have no surface in the Mastodon API and are not exposed by the shim:

| Corundum Feature | Status in Shim |
|-----------------|----------------|
| Signing transparency (`signing_record`) | Exists in Corundum; not exposed to Mastodon clients |
| Curation label detail | Exists; not exposed (optionally surfaced as `filtered`) |
| Authority declarations | Exists; not exposed |
| Archive structure (`seq`, epochs) | Exists; not exposed |
| DID (stable identity) | Exists; exposed only as the integer account ID derived from it |
| DID updates, content key rotation, migration | Exist; native API only. Migration is invisible to the client (account ID unchanged) |
| Self-custody | Not available through the shim: Mastodon apps cannot sign, so self-custody users can read but not write |
| Content verification by CID | Not available through the shim (client never sees CIDs) |

---

## Limitations and Caveats

**Integer IDs are shim-local but reproducible.** Another shim implementation, or a shim with a different collision history, could assign a different integer to a collided status. Non-collided status IDs and all account IDs are pure functions of Corundum data, so resetting or rebuilding the shim database reproduces them, and pruning the mapping table loses nothing.

**Posting trusts the operator.** Users who post through the shim are in operator custody: their operator holds the content key and could in principle publish in their name. This is the same trust model as any Mastodon server. Users who want cryptographic assurance that the operator cannot impersonate them use self-custody with a native Corundum client, and cannot post through the shim.

**No Corundum feature discovery.** Mastodon clients will not know they are connected to a Corundum operator. The instance `version` string (`4.x.x (Corundum)`) reveals it to clients that display version information, but no standardized Mastodon mechanism exists for advertising protocol extensions.

**Rejections are silent.** If the parent's operator rejects a reply (because of a block, a reply policy, or a curation match), the Mastodon client receives no feedback: the reply appears on the user's own timeline but not in the thread, and the `corundum.reply_rejected` notification is dropped. This is worse than the native client experience but consistent with Mastodon's opacity around moderation.

**Edits of replies.** An edited reply is a new reply submission to the parent's operator (spec Chapter 13). If that operator accepts the original but rejects the edit, the thread keeps showing the original while the author's client shows the edit under the same Mastodon ID.

**Unsupported streams.** Public, hashtag, and list streaming are unavailable until the native event stream offers matching topics; clients poll instead.
