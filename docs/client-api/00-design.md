# Design Principles

## Scope

The Corundum inter-operator protocol does not specify a client/server API. That is an explicit design decision: what a social media app shows users, how it authenticates them, and what endpoints it exposes are policy decisions for each operator, not interoperability requirements for the protocol (spec Chapter 40). Two operators with completely different client APIs can still federate with each other.

This document set describes the **reference implementation's** client/server API. It is non-normative. An app built against this API works against any operator that implements it, and not against an operator that chose a different API. Where this API touches protocol objects (identifiers, signatures, the archive, reply rejection), it follows the specification and does not redefine them.

## Why Not Just the Mastodon API

The Mastodon API is a reasonable starting point: it is widely implemented, well understood by client developers, and covers the core social media operations. Where Corundum's model aligns with Mastodon's, this API keeps Mastodon's endpoint names and response shapes to reduce the cost of building a native Corundum client. Where the models diverge, Corundum departs from Mastodon rather than papering over the differences. Existing Mastodon apps are served by a separate shim (`13-mastodon-shim.md`), so this API does not have to pretend its identifiers are Mastodon's.

The two most important divergences are identity and content addressing.

**Status IDs are content identifiers, not database keys.** A Mastodon status ID like `103704874086360371` has no meaning outside the server that generated it. You cannot verify the content matches the ID or fetch it from any other server, and if the server goes away the ID is worthless. A Corundum status ID is the activity's identifier: a CIDv1 with the `raw` codec and a SHA-256 multihash over the activity's exact stored bytes, written in base32 (it always begins `bafkrei`; spec Chapter 33). Anyone who has the bytes can check them against the ID by hashing them, and anyone can fetch them from any IPFS node that has them.

**Account IDs are DIDs, not database rows.** A Mastodon account ID like `1234567` is a row on one server; when the user migrates they get a new ID and the old one becomes a tombstone. A Corundum account ID is the user's DID (for example `did:webvh:<SCID>:birdsite.example:users:alice`), which the specification makes the canonical persistent identifier (spec Chapter 5). The DID does not change when the user changes operator, rotates keys, or changes handle. The DID document names the user's current IPNS name and operator; both of those change on migration, so neither is used as an account ID. Followers do not need to refollow.

### Mastodon vs. Corundum Comparison

| Concern | Mastodon | Corundum |
|---------|----------|----------|
| Status ID type | 64-bit integer, server-local | Activity identifier: CIDv1 (raw codec, SHA-256) over the exact bytes, globally unique |
| Account ID type | 64-bit integer, server-local | DID, globally unique and stable across operators and keys |
| Status content verification | Not possible; trust the server | Hash the stored bytes and compare with the ID; verify the detached JWS signing record (`02-entities.md`) |
| Identity portability | Account move transfers followers but not post history; needs the old server's cooperation | The user signs a DID update naming a new operator; post history is in IPFS; no cooperation from the old operator required |
| Block semantics | Client-side filter; blocked user's replies may still propagate | The post author's operator rejects the blocked user's reply submissions (`REPLY_REJECTED`, reason `blocked-user`); the replies are never added to the reply tree |
| Moderation transparency | Platform-internal | Curators publish signed, auditable judgment feeds traceable to a declared authority |

## Mastodon-Shaped Surface

All native endpoints live under `/api/corundum/v1/`. The Mastodon shim owns `/api/v1/` and `/api/v2/`, so the two surfaces never collide on one host, whatever the deployment. Nothing client-facing lives under `/corundum/`, which belongs to the server-to-server protocol. OAuth (`/oauth/`) is one authorization server shared by both surfaces (`01-auth.md`).

Under that prefix, endpoint names follow Mastodon's (`/api/corundum/v1/statuses/:id`, `/api/corundum/v1/timelines/home`, `/api/corundum/v1/accounts/:id/follow`, and so on), and entity shapes keep Mastodon's field names. The differences a Mastodon-experienced developer needs to know:

- IDs are strings that are activity identifiers (statuses) or DIDs (accounts), never integers.
- Every Corundum-specific field is nested under a `corundum` key in the entity (`02-entities.md`). There are no Corundum fields at the top level.
- Pagination uses opaque cursors, not `max_id`/`min_id` (below).
- Errors use the `corundum:Error` envelope (below).
- Visibility is always `public`. Corundum covers the public conversation only (spec Chapter 40); there are no followers-only or direct statuses.
- An edit is a new status with a new ID that replaces the old one (`03-statuses.md`).

### Corundum-Only Endpoint Groups

| Endpoint Group | Path Prefix | Purpose |
|----------------|-------------|---------|
| Self-custody publishing | `/api/corundum/v1/activities` | Submit activities the client signed itself (`03-statuses.md`) |
| Identity | `/api/corundum/v1/identity/` | DID, key custody, content-key rotation, DID updates, RootManifest |
| Migration | `/api/corundum/v1/migration/` | Move to this operator, archive export, migration status |
| Curation | `/api/corundum/v1/curation/` | Subscribed curators, per-status labels, appeals |
| Event stream | `/api/corundum/v1/streaming` | Real-time updates (`14-event-stream.md`) |

### Key Custody

Every account has a key custody mode, shown as `corundum.key_custody` on the Account entity. With `operator` custody (the default), the operator holds the user's content key and signs on their behalf, so the status endpoints work as they do on Mastodon. With `self` custody, the client holds the content key and submits activities it has already signed. Either way, the update keys that change the user's DID document stay with the user and never reach the operator (spec Chapter 7). `10-identity-migration.md` defines both modes.

## Identifiers

| Identifier | Used for | Form |
|------------|----------|------|
| DID | Account `id`, `in_reply_to_account_id`, every reference to a user | `did:webvh:…`, `did:plc:…`, or `did:key:…` (spec Chapter 5) |
| Activity identifier | Status `id`, `in_reply_to_id`, `corundum.replaces` | CIDv1, raw codec, SHA-256, base32 (`bafkrei…`) |
| CID | SigningRecord, RootManifest, media content | CIDv1, base32 |
| Authority URL | Curator identity (`11-curation.md`) | HTTPS URL of the curator's Authority Declaration |
| Operator-local ID | Media uploads, notifications, lists, upload sessions | Opaque string, meaningful only on this operator |

**Path encoding.** DIDs contain `:` and may contain `%` (for example, a `did:webvh` with a port), and authority URLs contain `/`. When a DID or URL is used as a path parameter (`:id` for accounts, `:authority` for curators), the client sends it as a single path segment and percent-encodes every byte outside the RFC 3986 `unreserved` set: `:` becomes `%3A`, `%` becomes `%25`, and `/` becomes `%2F`. The operator percent-decodes the segment exactly once and compares the result with the stored DID byte for byte. For example:

```
GET /api/corundum/v1/accounts/did%3Awebvh%3A<SCID>%3Abirdsite.example%3Ausers%3Aalice
```

Activity identifiers and CIDs contain only lowercase letters and digits and need no encoding. In query strings and request bodies, DIDs and URLs use ordinary form or percent encoding.

## Pagination

Collection endpoints follow the specification's cursor rules (spec Chapter 38). Offset pagination is not supported.

### Request Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cursor` | string | — | An opaque cursor from a previous response's `nextCursor` or `prevCursor`. Absent: the first page from the newest end. The cursor carries its own direction. |
| `limit` | integer | 20 | Page size. The operator may clamp it and reports the size it applied. |

Time-ordered collections (timelines, an account's statuses, notifications) also accept two position filters:

| Parameter | Type | Description |
|-----------|------|-------------|
| `before` | string (RFC 3339) | Only items whose sort time is strictly earlier than this time. |
| `after` | string (RFC 3339) | Only items whose sort time is strictly later than this time. |

An item's sort time is the `created_at` of its first version (`03-statuses.md`), at millisecond precision. `before` and `after` are filters, not cursors: they are bound into the cursors issued for the request, and a cursor presented with different filters is rejected with `INVALID_CURSOR`. They let a client jump to a point in time, which the Mastodon shim needs to translate Mastodon's `max_id` and `min_id` (`13-mastodon-shim.md`).

### Response

A paginated response is a `corundum:PaginatedResponse`:

```json
{
  "@type": "corundum:PaginatedResponse",
  "items": [ "...entities..." ],
  "pagination": {
    "nextCursor": "<opaque cursor toward older items>",
    "prevCursor": "<opaque cursor toward newer items>",
    "limit": 20
  }
}
```

Search (`09-search.md`) is the one exception to this shape: it returns several typed lists in one object, with a single `pagination` member covering them.

`nextCursor` is absent at the end of the collection. `prevCursor` is present whenever `items` is non-empty, so a client can poll for newer items. `total` may be included when the operator can compute it cheaply; clients must not depend on it.

Clients MUST treat cursors as opaque and MUST NOT construct or parse them. Each cursor carries a MAC and is bound to its collection, filters, and direction. Cursors do not expire. An operator stops accepting one only when it retires that cursor encoding or rotates its MAC key, and then rejects it with `INVALID_CURSOR`; the client discards it and starts again without a cursor.

## Error Responses

Every error response is a `corundum:Error` (spec Chapter 37), with `Content-Type: application/json`:

```json
{
  "@type": "corundum:Error",
  "code": "NOT_FOUND",
  "message": "No status with this activity id is known to this operator",
  "httpStatus": 404,
  "retryable": false,
  "details": {}
}
```

`code` is a stable machine-readable string; clients branch on it. `message` is for developers and logs, not for display to end users. `httpStatus` equals the HTTP status. `retryable` says whether repeating the same request might succeed; a retryable error with `details.retryAfter` (integer seconds) also carries a `Retry-After` header with the same value. `details.reason` gives a finer-grained, lower-kebab-case sub-code where one is defined. Clients that receive an unknown `code` treat the error as the generic meaning of its HTTP status.

When the operator relays an error from the protocol, such as a reply rejection from a remote operator, it passes the protocol's `code` and `details.reason` through unchanged.

### Error Code Registry

Every code used anywhere in this API is listed here. Codes marked *spec* are the specification's (spec Chapter 37) and keep its meaning.

| Code | HTTP Status | Retryable | Meaning |
|------|-------------|-----------|---------|
| `INVALID_REQUEST` (spec) | 400 | false | Malformed request or missing required field (`details.missingField`). |
| `VALIDATION_FAILED` | 422 | false | Well-formed but semantically invalid: content too long, conflicting parameters, unsupported visibility (`details.reason` `visibility-unsupported`), and similar. `details.reason` or `details.missingField` names the problem. |
| `UNAUTHORIZED` | 401 | false | Missing, invalid, or revoked access token. |
| `INSUFFICIENT_SCOPE` | 403 | false | The token lacks the scope this endpoint requires (`01-auth.md`). |
| `FORBIDDEN` | 403 | false | Authenticated and scoped, but not permitted (for example, not the author). |
| `NOT_FOUND` | 404 | false | The resource does not exist or is not known to this operator. |
| `GONE` | 410 | false | The resource existed but was deleted. |
| `PAYLOAD_TOO_LARGE` | 413 | false | The upload or chunk exceeds the allowed size. |
| `CURATION_REJECTED` | 403 | false | This operator's curation policy refuses the content. |
| `CUSTODY_MODE_MISMATCH` | 409 | false | The endpoint requires the other key custody mode (`10-identity-migration.md`). |
| `SEQ_CONFLICT` | 409 | false | The submitted activity or pending RootManifest is based on a sequence number that is no longer current. Fetch `next_seq` and retry. |
| `ACTIVITY_INVALID` | 400 | false | A client-signed activity failed verification. `details.reason`: `cid-mismatch`, `signature-invalid`, `seq-mismatch`, or `author-mismatch`. |
| `DID_UPDATE_INVALID` | 400 | false | A submitted DID log entry or PLC operation does not verify or does not chain to the current DID state. |
| `ALREADY_HOSTED` | 409 | false | This operator already hosts the identity. |
| `EXPORT_IN_PROGRESS` | 409 | false | An archive export is already running for this account. |
| `ALREADY_SUBSCRIBED` | 409 | false | The operator already subscribes to this curator. |
| `RATE_LIMITED` (spec) | 429 | true | Rate limit exceeded. `details.retryAfter` present. |
| `INVALID_CURSOR` (spec) | 400 | false | The cursor fails verification or does not match the request. Discard it and start again. |
| `REPLY_REJECTED` (spec) | per reason | per reason | A remote operator rejected a reply submission; `details.reason` is the spec Chapter 21 reason code (for example `blocked-user`). |
| `DID_RESOLUTION_FAILED` (spec) | 502 | true | A DID document could not be resolved. |
| `HANDLE_VERIFICATION_FAILED` (spec) | 400 | false | A handle does not verify bidirectionally against its DID (spec Chapter 8). |
| `ALGORITHM_REJECTED` (spec) | 400 | false | The key or signature algorithm is not in the spec Chapter 36 registry. |
| `CURATION_AUTHORITY_INVALID` (spec) | 400 | false | A curator's Authority Declaration is invalid or does not match its URL. |
| `CHUNK_MISSING` (spec) | 400 | false | A chunked upload was completed with chunks missing (`details` lists them). |
| `UPLOAD_SESSION_EXPIRED` (spec) | 410 | false | The upload session no longer exists. |
| `RESUME_BUFFER_EXHAUSTED` (spec) | 410 | false | An event stream resume point is older than the retained buffer (`14-event-stream.md`). |
| `UPSTREAM_UNAVAILABLE` | 502 | true | A service the operator depends on (a curator, a remote operator) could not be reached. |
| `IPFS_UNAVAILABLE` | 503 | true | The operator's IPFS node is temporarily unreachable. |
| `INTERNAL_ERROR` | 500 | true | Operator fault. Retry with backoff. |
