# Accounts

Account endpoints provide access to user profiles, their published statuses, and their social graph (followers and following lists). Account ids are DIDs (spec Chapter 5), not opaque integers and not IPNS names. A DID in a path is percent-encoded as one path segment (`00-design.md`, Identifiers).

## Profile Endpoints

### GET /api/corundum/v1/accounts/:id

Returns the public profile for any account.

**Authentication:** Optional.

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:id` | The account's DID, percent-encoded |

**Returns:** Account entity.

**Errors:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 404 | `NOT_FOUND` | No account with that DID is known to this operator, and the DID could not be resolved |
| 502 | `DID_RESOLUTION_FAILED` | The DID document could not be fetched |

---

### GET /api/corundum/v1/accounts/verify_credentials

Returns the profile of the currently authenticated user. Used by clients to confirm that a token is valid and to fetch the user's own account details.

**Authentication:** Required (any read scope).

**Returns:** Account entity with the additional `source` field containing account settings (language, note in plain text, etc.).

**Errors:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 401 | `UNAUTHORIZED` | No valid token provided |

---

### PATCH /api/corundum/v1/accounts/update_credentials

Updates the authenticated user's profile. The profile is part of the RootManifest's identity block (spec Chapter 9), so a change republishes the RootManifest.

**Authentication:** Required (`write:accounts` scope).

**Request Body (multipart/form-data or application/x-www-form-urlencoded):**

| Parameter | Type | Description |
|-----------|------|-------------|
| `display_name` | string | Display name (max 30 characters) |
| `note` | string | Profile bio/note (max 500 characters, plain text; operator renders to HTML) |
| `avatar` | file | New avatar image |
| `header` | file | New header/banner image |
| `locked` | boolean | If `true`, follow requests require approval |
| `fields_attributes[]` | array of objects | Profile metadata fields. Each object has `name` and `value` keys. Maximum 4 fields. |

All parameters are optional; only provided fields are updated.

**Returns:** Updated Account entity. For a self-custody account the operator cannot sign the new RootManifest, so it returns `202 Accepted` with a `pending_root_manifest` for the client to sign and commit (`10-identity-migration.md`, Key custody).

**Errors:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 401 | `UNAUTHORIZED` | No valid token provided |
| 403 | `INSUFFICIENT_SCOPE` | Token lacks `write:accounts` scope |
| 422 | `VALIDATION_FAILED` | Validation failed (e.g. display name too long) |

---

## Statuses and Social Graph

### GET /api/corundum/v1/accounts/:id/statuses

Returns statuses published by the specified account, newest first. Edited posts appear once, as their newest version, at the position of their first version.

**Authentication:** Optional.

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:id` | The account's DID, percent-encoded |

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cursor` | string | — | Opaque cursor from a previous response |
| `limit` | integer | 20 | Maximum number of results (max 40) |
| `before` | string (RFC 3339) | — | Only items whose sort time is strictly earlier than this |
| `after` | string (RFC 3339) | — | Only items whose sort time is strictly later than this |
| `only_media` | boolean | `false` | Return only statuses that include media attachments |
| `exclude_replies` | boolean | `false` | Exclude statuses that are replies |
| `exclude_reblogs` | boolean | `false` | Exclude boosts/reblogs |
| `tagged` | string | — | Return only statuses tagged with this hashtag (without `#`) |

**Returns:** PaginatedResponse of Status entities.

---

### GET /api/corundum/v1/accounts/:id/followers

Returns the accounts that follow the specified account, as known to this operator. For a local account this is the operator's followers cache, built from the FollowNotifications that followers' operators send (spec Chapter 25). For a remote account it is whatever this operator has learned and may be incomplete.

**Authentication:** Optional.

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:id` | The account's DID, percent-encoded |

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cursor` | string | — | Opaque cursor from a previous response |
| `limit` | integer | 40 | Maximum number of results (max 80) |

**Returns:** PaginatedResponse of Account entities.

---

### GET /api/corundum/v1/accounts/:id/following

Returns the accounts that the specified account follows. Following lists are stored encrypted in the RootManifest and are private by default (spec Chapter 25). This endpoint returns the list only if its owner has published it, or if the requester is the owner.

**Authentication:** Optional.

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:id` | The account's DID, percent-encoded |

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cursor` | string | — | Opaque cursor from a previous response |
| `limit` | integer | 40 | Maximum number of results (max 80) |

**Returns:** PaginatedResponse of Account entities.

**Errors:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 403 | `FORBIDDEN` | The account has not published its following list |
| 404 | `NOT_FOUND` | No account with that DID is known to this operator |

---

## Lookup and Search

### GET /api/corundum/v1/accounts/lookup

Resolves an account by handle without performing a search. Useful when the client already knows the handle and wants the canonical Account entity.

The operator resolves the handle to a DID (WebFinger for an account handle, the `_corundum` DNS TXT record for a domain handle) and accepts it only if the DID document lists the handle back in `alsoKnownAs` (spec Chapter 8). A handle that fails this bidirectional check is not returned.

**Authentication:** Optional.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `acct` | string | Yes | Account handle in `user@domain` form, local `user` without domain, or a domain handle (`alice.example`) |

**Returns:** Account entity.

**Errors:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 400 | `HANDLE_VERIFICATION_FAILED` | The handle resolves to a DID whose document does not list it |
| 404 | `NOT_FOUND` | No account found for that handle |
| 502 | `DID_RESOLUTION_FAILED` | The DID document could not be fetched |

---

### GET /api/corundum/v1/accounts/search

Searches for accounts by display name, username, or handle. Optionally resolves remote accounts.

**Authentication:** Optional. The `following` filter requires authentication.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `q` | string | — | Search query (required) |
| `cursor` | string | — | Opaque cursor from a previous response |
| `limit` | integer | 40 | Maximum number of results (max 80) |
| `resolve` | boolean | `false` | If `true`, attempt to resolve `q` as a handle (as `lookup` does) when no local match is found |
| `following` | boolean | `false` | If `true`, restrict results to accounts the authenticated user follows |

**Returns:** PaginatedResponse of Account entities.

---

## Corundum-Specific Account Endpoints

### GET /api/corundum/v1/accounts/:id/archive_index

Returns the entry points into the account's IPFS-backed archive, so that clients and third-party tools can read and verify the account's content from IPFS without relying on the operator.

**Authentication:** Optional.

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:id` | The account's DID, percent-encoded |

**Returns:**

```json
{
  "root_manifest_cid": "<CID of the RootManifest>",
  "archive_index_cid": "<CID of the ArchiveIndex>",
  "current_chunk_cid": "<CID of the current chunk>",
  "latest_seq": 891,
  "epoch_count": 3
}
```

| Field | Type | Description |
|-------|------|-------------|
| `root_manifest_cid` | string (CID) | CID of the current RootManifest (an attached JWS signed by the account's content keys) |
| `archive_index_cid` | string (CID) | CID of the top-level ArchiveIndex named by that RootManifest |
| `current_chunk_cid` | string (CID) | CID of the current chunk, holding the entries not yet finalized into an epoch |
| `latest_seq` | integer | `seq` of the newest entry |
| `epoch_count` | integer | Number of finalized epochs |

Epochs are fixed chunks of 256 entries: epoch *k* holds `seq` 256*k* to 256*k*+255, and the current chunk holds the entries after the last finalized epoch. To find an entry, walk ArchiveIndex → IndexPage → epoch as described in spec Chapter 9. Every object is content-addressed, so a client verifies what it fetches by hashing it, and verifies the RootManifest's signatures against the content keys in the account's DID document (spec Chapter 34). The values above are a convenience: a client that does not trust the operator reads them from the RootManifest itself.

**Errors:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 404 | `NOT_FOUND` | No account with that DID is known to this operator |
