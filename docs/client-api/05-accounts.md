# Accounts

Account endpoints provide access to user profiles, their published statuses, and their social graph (followers and following lists). Account IDs in Corundum are IPNS names (base36lower), not opaque integers.

## Profile Endpoints

### GET /api/v1/accounts/:id

Returns the public profile for any account.

**Authentication:** Optional.

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:id` | The account's IPNS name (base36lower) |

**Returns:** Account entity.

**Errors:**

| Code | Error | Description |
|------|-------|-------------|
| 404 | `not_found` | No account with that IPNS name is known to this operator |

---

### GET /api/v1/accounts/verify_credentials

Returns the profile of the currently authenticated user. Used by clients to confirm that a token is valid and to fetch the user's own account details.

**Authentication:** Required (any read scope).

**Returns:** Account entity with the additional `source` field containing account settings (privacy, language, note in plain text, etc.).

**Errors:**

| Code | Error | Description |
|------|-------|-------------|
| 401 | `unauthorized` | No valid token provided |

---

### PATCH /api/v1/accounts/update_credentials

Updates the authenticated user's profile.

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

**Returns:** Updated Account entity.

**Errors:**

| Code | Error | Description |
|------|-------|-------------|
| 401 | `unauthorized` | No valid token provided |
| 403 | `insufficient_scope` | Token lacks `write:accounts` scope |
| 422 | `unprocessable_entity` | Validation failed (e.g. display name too long) |

---

## Statuses and Social Graph

### GET /api/v1/accounts/:id/statuses

Returns statuses published by the specified account, in reverse chronological order.

**Authentication:** Optional. Private accounts require an approved follow.

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:id` | The account's IPNS name (base36lower) |

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_id` | string (CID) | — | Return results older than this CID |
| `min_id` | string (CID) | — | Return results newer than this CID |
| `limit` | integer | 20 | Maximum number of results (max 40) |
| `only_media` | boolean | `false` | Return only statuses that include media attachments |
| `exclude_replies` | boolean | `false` | Exclude statuses that are replies |
| `exclude_reblogs` | boolean | `false` | Exclude boosts/reblogs |
| `tagged` | string | — | Return only statuses tagged with this hashtag (without `#`) |

**Returns:** Array of Status entities, newest first.

---

### GET /api/v1/accounts/:id/followers

Returns a list of accounts that follow the specified account.

**Authentication:** Optional. Some operators may restrict this endpoint for private accounts.

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:id` | The account's IPNS name (base36lower) |

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_id` | string | — | Pagination cursor (opaque) |
| `min_id` | string | — | Pagination cursor (opaque) |
| `limit` | integer | 40 | Maximum number of results (max 80) |

**Returns:** Array of Account entities.

---

### GET /api/v1/accounts/:id/following

Returns a list of accounts that the specified account follows.

**Authentication:** Optional. Some operators may restrict this endpoint for private accounts.

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:id` | The account's IPNS name (base36lower) |

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_id` | string | — | Pagination cursor (opaque) |
| `min_id` | string | — | Pagination cursor (opaque) |
| `limit` | integer | 40 | Maximum number of results (max 80) |

**Returns:** Array of Account entities.

---

## Lookup and Search

### GET /api/v1/accounts/lookup

Resolves an account by its Webfinger handle without performing a search. Returns a single account if found. This is useful when the client already knows the handle and wants the canonical Account entity.

**Authentication:** Optional.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `acct` | string | Yes | Webfinger handle in `user@domain` format, or local `user` without domain |

**Returns:** Account entity.

**Errors:**

| Code | Error | Description |
|------|-------|-------------|
| 404 | `not_found` | No account found for that handle |

---

### GET /api/v1/accounts/search

Searches for accounts by display name, username, or handle. Optionally resolves remote accounts via federation.

**Authentication:** Optional. The `following` filter requires authentication.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `q` | string | — | Search query (required) |
| `limit` | integer | 40 | Maximum number of results (max 80) |
| `resolve` | boolean | `false` | If `true`, attempt to resolve remote accounts via federation when no local match is found |
| `following` | boolean | `false` | If `true`, restrict results to accounts the authenticated user follows |

**Returns:** Array of Account entities.

---

## Corundum-Specific Account Endpoints

### GET /api/v1/accounts/:id/archive_index

Returns the machine-readable ArchiveIndex for the account's IPFS-backed archive. This structure allows clients and third-party tools to directly access and verify the account's content via IPFS without relying on the operator.

**Authentication:** Optional.

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:id` | The account's IPNS name (base36lower) |

**Returns:** ArchiveIndex structure:

```json
{
  "cid": "bafyreib4gy7...",
  "epochs": [
    {
      "epoch": 0,
      "entry_count": 500,
      "epoch_cid": "bafyreiabc1...",
      "sequence_start": 1,
      "sequence_end": 500
    },
    {
      "epoch": 1,
      "entry_count": 391,
      "epoch_cid": "bafyreidef2...",
      "sequence_start": 501,
      "sequence_end": 891
    }
  ],
  "total_entries": 891
}
```

| Field | Type | Description |
|-------|------|-------------|
| `cid` | string (CID) | CID of the current ArchiveIndex object in IPFS |
| `epochs` | array | List of archive epochs, in ascending epoch order |
| `epochs[].epoch` | integer | Epoch number (0-based) |
| `epochs[].entry_count` | integer | Number of status entries in this epoch |
| `epochs[].epoch_cid` | string (CID) | CID of the epoch archive object in IPFS |
| `epochs[].sequence_start` | integer | Sequence number of the first entry in this epoch |
| `epochs[].sequence_end` | integer | Sequence number of the last entry in this epoch |
| `total_entries` | integer | Total number of status entries across all epochs |

The `epoch_cid` values can be used to fetch epoch archive data directly from IPFS, independent of this operator. This enables data portability, third-party verification, and recovery from operator failure.

**Errors:**

| Code | Error | Description |
|------|-------|-------------|
| 404 | `not_found` | No account with that IPNS name is known to this operator |
