# Design Principles

## Why Not Just the Mastodon API

The Mastodon API is a reasonable starting point: it is widely implemented, well-understood by client developers, and covers the core social media operations. Where Corundum's model aligns with Mastodon's, the endpoints match as closely as possible to reduce the cost of building a native Corundum client. Where the models diverge, Corundum departs from Mastodon rather than papering over the differences.

The two most important divergences are identity and content addressing.

**Integer status IDs are opaque and operator-local.** A Mastodon status ID like `103704874086360371` has no meaning outside the server that generated it. It is a database primary key. You cannot look at the number and know anything about the content, verify the content matches the ID, or fetch the content from any server other than the one that issued the ID. If the server goes away, the ID is worthless. Corundum uses CIDs (Content Identifiers from IPFS) as status IDs. A CID like `bafyreiabcdef...` is a cryptographic hash of the content. The ID and the content are the same thing: if you have the CID, you can verify any copy of the content you retrieve is authentic by recomputing the hash. The content can be retrieved from any IPFS node that has it pinned, not just from the originating operator.

**Integer account IDs tie identity to one server.** A Mastodon account ID like `1234567` is a database row on one specific server. When that server shuts down, the identity is gone. When the user migrates, they get a new account ID on the new server; the old ID becomes a tombstone. Corundum uses IPNS names as account IDs. An IPNS name is the hash of the user's Ed25519 public key. It is generated from the user's cryptographic keypair, not from an operator's database. If an operator shuts down, the IPNS name is unaffected. When a user migrates, the IPNS name does not change; only the operator endpoint declaration in their RootManifest is updated. Followers do not need to refollow.

### Mastodon vs. Corundum Comparison

| Concern | Mastodon | Corundum |
|---------|----------|----------|
| Status ID type | 64-bit integer, server-local | CID (base32lower, content hash), globally unique |
| Account ID type | 64-bit integer, server-local | IPNS name (base36lower, public key hash), globally unique |
| Status content verification | Not possible; trust the server | Recompute CID from content body; mismatch is detectable |
| Identity portability | Limited; account move transfers follower list but not post history; requires cooperation of old server | Full; IPNS name is unchanged after migration; post history is in IPFS; no cooperation from old operator required |
| Block semantics | Client-side filter; blocked user's replies may still propagate to the server | Protocol-level rejection; operator rejects blocked user's reply submissions at the API boundary; replies are not stored |
| Moderation transparency | Platform-internal; no public accountability for decisions | Curators publish signed, auditable judgment feeds; every curation entry is traceable to a declared authority |

## Mastodon-Compatible Surface

To ease client development and migration, this API follows Mastodon's endpoint paths and response shapes where the underlying model is the same or close. Corundum adds fields to existing response objects and introduces new endpoint groups for Corundum-native features.

### Identical or Near-Identical Endpoints

These endpoints have the same path, method, parameters, and response shape as Mastodon. A client that uses only these endpoints against a Corundum operator will behave as it would against a Mastodon server.

- `GET /api/v1/timelines/home` — home timeline
- `GET /api/v1/timelines/public` — public timeline
- `GET /api/v1/timelines/tag/:hashtag` — hashtag timeline
- `GET /api/v1/notifications` — notifications list
- `POST /api/v1/notifications/clear` — clear all notifications
- `GET /api/v1/accounts/relationships` — follow/block/mute relationship status
- `POST /api/v1/accounts/:id/follow` — follow an account
- `POST /api/v1/accounts/:id/unfollow` — unfollow an account
- `POST /api/v1/accounts/:id/block` — block an account
- `POST /api/v1/accounts/:id/unblock` — unblock an account
- `POST /api/v1/accounts/:id/mute` — mute an account
- `POST /api/v1/accounts/:id/unmute` — unmute an account
- `POST /api/v1/media` — upload media attachment
- `PUT /api/v1/media/:id` — update media attachment metadata

### Endpoints with Corundum Additions

These endpoints exist in Mastodon and are present here with compatible structure, but the response objects carry additional Corundum-specific fields. A Mastodon client will receive these fields as unknown properties and should ignore them gracefully.

**Status objects** include these additional fields:

| Field | Type | Description |
|-------|------|-------------|
| `cid` | string | The CID of this status (base32lower). This is the canonical Corundum ID; the `id` field contains the same value for native clients. |
| `signing_record_cid` | string | CID of the signing record that covers this status, enabling signing transparency verification. |
| `ipns_author` | string | IPNS name of the author (base36lower). Stable across operator migrations. |

**Account objects** include these additional fields:

| Field | Type | Description |
|-------|------|-------------|
| `ipns_name` | string | The account's IPNS name (base36lower). The stable, globally portable identifier. |
| `did` | string | The account's W3C Decentralized Identifier (e.g. `did:web:birdsite.example:users:alice`). |
| `operator_endpoint` | string | Base URL of the operator currently serving this account. |
| `key_algorithm` | string | Signing algorithm declared in the account's DID document (e.g. `Ed25519`). |

### Corundum-Only Endpoints

These endpoint groups have no Mastodon equivalent. They are documented in their own files.

| Endpoint Group | Path Prefix | Purpose |
|----------------|-------------|---------|
| Identity | `/api/v1/identity/` | DID document, IPNS name resolution, key rotation, signing records |
| Migration | `/api/v1/migration/` | Import an existing Corundum identity, export archive, migration status |
| Curation | `/api/v1/curation/` | Subscribed curator feeds, per-content curation labels, appeal submission |

## Pagination

All collection endpoints use cursor-based pagination. Offset-based pagination (e.g., `?page=3`) is not supported. See the design rationale in the Corundum spec (Chapter 38) for why cursor-based pagination is required for live timelines.

### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_id` | string | — | Return only items with an ID (cursor position) strictly less than this value. Used to page toward older content. |
| `min_id` | string | — | Return only items with an ID (cursor position) strictly greater than this value. Used to page toward newer content. |
| `limit` | integer | 20 | Number of items to return. Maximum 80. |

`max_id` and `min_id` are mutually exclusive in a single request. If both are provided, the server returns a `400 Bad Request`.

### Link Header

Paginated responses include a `Link` header following the Mastodon convention (which is itself derived from RFC 5988):

```
Link: <https://operator.example/api/v1/timelines/home?max_id=bafyreiabcdef>; rel="next",
      <https://operator.example/api/v1/timelines/home?min_id=bafyreighijkl>; rel="prev"
```

- `rel="next"` points toward older content (the next page backward in time).
- `rel="prev"` points toward newer content (the next page forward in time, i.e., items that arrived after the most recent item the client has seen).

Cursors are opaque strings. In practice they are CIDs or ISO 8601 timestamps encoded as strings, but clients MUST treat them as opaque and MUST NOT construct or parse them. The operator may change cursor encoding at any time as long as it continues to honor cursors it has already issued within their validity window.

### Cursor Validity

Cursors are not indefinitely valid. A cursor that is too old returns error code `cursor_expired` (see Error Responses below). The client's recovery is to discard the cursor and start a new pagination session from the head of the collection. There is no way to resume from an expired cursor position without potentially missing items; this is an accepted tradeoff for live timelines.

## Error Responses

All error responses use a consistent JSON envelope regardless of which endpoint produced the error.

### Error Envelope

```json
{
  "error": "not_found",
  "error_description": "No status found with CID bafyreiabcdef"
}
```

`error` is a stable machine-readable string code. Clients branch on this field. It does not change across server versions for a given error condition.

`error_description` is a short human-readable explanation intended for developers and logs. It is not suitable for direct display to end users, which require application-level localization and appropriate tone. The description may be updated for clarity without the `error` code changing.

HTTP status codes follow REST conventions as described below.

### HTTP Status Codes

| HTTP Status | Meaning |
|-------------|---------|
| `400 Bad Request` | The request is syntactically or semantically invalid. |
| `401 Unauthorized` | The request lacks valid authentication credentials. |
| `403 Forbidden` | Authenticated but not authorized for this action. |
| `404 Not Found` | The requested resource does not exist. |
| `410 Gone` | The resource existed but has been deleted (tombstoned content). |
| `422 Unprocessable Entity` | The request is well-formed but contains a semantic error (e.g., posting a status with an invalid CID reference). |
| `429 Too Many Requests` | Rate limit exceeded. Response includes a `Retry-After` header. |
| `500 Internal Server Error` | Server fault. |
| `503 Service Unavailable` | The server is temporarily unavailable. |

### Standard Error Codes

| `error` Code | HTTP Status | Meaning |
|--------------|-------------|---------|
| `unauthorized` | 401 | Missing or invalid access token. |
| `forbidden` | 403 | Authenticated but lacking required scope or permission. |
| `not_found` | 404 | Requested resource does not exist. |
| `gone` | 410 | Resource existed but has been deleted. |
| `unprocessable_entity` | 422 | Request is well-formed but semantically invalid. |
| `rate_limited` | 429 | Rate limit exceeded. Check `Retry-After` header. |
| `blocked_user` | 403 | The action involves a user who has blocked or been blocked by the authenticated user. |
| `curation_rejected` | 403 | The content was rejected by a curation rule applied by this operator. |
| `invalid_cursor` | 400 | The pagination cursor is malformed or was not issued by this server. |
| `cursor_expired` | 400 | The pagination cursor has exceeded its validity window. Start a new pagination session. |
| `operator_error` | 500 | An internal operator error occurred. The request may be retried with backoff. |
