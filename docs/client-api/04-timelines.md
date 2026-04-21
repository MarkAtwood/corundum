# Timelines

Timeline endpoints return ordered arrays of Status entities. All timelines use cursor-based pagination via `max_id` and `min_id` query parameters. Unless noted otherwise, cursors are Status CIDs (base32lower). Timelines return results newest-first.

## Standard Timelines

### GET /api/v1/timelines/home

Returns statuses from accounts the authenticated user follows, in reverse chronological order.

**Authentication:** Required (`read:statuses` scope)

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_id` | string (CID) | — | Return results older than this CID |
| `min_id` | string (CID) | — | Return results newer than this CID |
| `limit` | integer | 20 | Maximum number of results (max 40) |
| `local` | boolean | `false` | Return only statuses from this operator's local accounts |

**Returns:** Array of Status entities, newest first.

**Errors:**

| Code | Error | Description |
|------|-------|-------------|
| 401 | `unauthorized` | No valid token provided |
| 403 | `insufficient_scope` | Token lacks `read:statuses` scope |

---

### GET /api/v1/timelines/public

Returns public statuses from the federated network, or only from the local operator when `local=true`.

**Authentication:** Optional. Unauthenticated requests may receive a reduced result set at operator discretion.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_id` | string (CID) | — | Return results older than this CID |
| `min_id` | string (CID) | — | Return results newer than this CID |
| `limit` | integer | 20 | Maximum number of results (max 40) |
| `local` | boolean | `false` | Return only statuses from this operator's local accounts |
| `remote` | boolean | `false` | Return only statuses from remote (federated) accounts |
| `only_media` | boolean | `false` | Return only statuses that include media attachments |

`local` and `remote` are mutually exclusive. If both are `true`, the operator returns a 422 error.

**Returns:** Array of Status entities, newest first.

---

### GET /api/v1/timelines/tag/:hashtag

Returns public statuses for the given hashtag.

**Authentication:** Optional.

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:hashtag` | The hashtag to search for, without the leading `#` character |

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_id` | string (CID) | — | Return results older than this CID |
| `min_id` | string (CID) | — | Return results newer than this CID |
| `limit` | integer | 20 | Maximum number of results (max 40) |
| `local` | boolean | `false` | Return only statuses from local accounts |
| `remote` | boolean | `false` | Return only statuses from remote accounts |
| `only_media` | boolean | `false` | Return only statuses that include media attachments |
| `any[]` | array of strings | — | Return statuses that contain any of these additional hashtags |
| `all[]` | array of strings | — | Return statuses that contain all of these additional hashtags |
| `none[]` | array of strings | — | Exclude statuses that contain any of these hashtags |

**Returns:** Array of Status entities, newest first.

---

### GET /api/v1/timelines/list/:list_id

Returns statuses from accounts in the specified list.

**Authentication:** Required. The list must belong to the authenticated user.

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:list_id` | The ID of the list |

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_id` | string (CID) | — | Return results older than this CID |
| `min_id` | string (CID) | — | Return results newer than this CID |
| `limit` | integer | 20 | Maximum number of results (max 40) |

**Returns:** Array of Status entities, newest first.

**Errors:**

| Code | Error | Description |
|------|-------|-------------|
| 401 | `unauthorized` | No valid token provided |
| 404 | `not_found` | List does not exist or does not belong to the authenticated user |

---

## Corundum-Specific Timelines

### GET /api/v1/timelines/archive/:account_id

Returns statuses from the account's IPFS-backed archive, in sequence order (oldest first within a page, with pagination moving forward or backward through the sequence).

This is the canonical durable timeline for a Corundum account. Because it is backed by IPFS and addressed by the account's IPNS name, it can be resolved and verified even if the account's current operator is unavailable. Each status in the response includes `corundum.sequence_number` and `corundum.epoch` fields.

**Authentication:** Optional. Public accounts are accessible without authentication. Private accounts require a token with an approved follow relationship.

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:account_id` | The account's IPNS name (base36lower) |

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_id` | string (integer as string) | — | Return results with sequence number less than this value |
| `min_id` | string (integer as string) | — | Return results with sequence number greater than this value |
| `limit` | integer | 20 | Maximum number of results (max 40) |
| `epoch` | integer | — | If provided, restrict results to this epoch only |

**Cursor semantics differ here:** `max_id` and `min_id` are sequence numbers represented as decimal integer strings (e.g. `"500"`), not CIDs. This is because the archive is indexed by append-sequence rather than by content address.

**Returns:** Array of Status entities, in ascending sequence order. Each status includes the following additional fields in the `corundum` namespace:

```json
{
  "corundum": {
    "sequence_number": 312,
    "epoch": 0
  }
}
```

**Example:**

```
GET /api/v1/timelines/archive/k51qzi5uqu5dh9ihj4p2v5sl3hxvv27ryx2w0xrsv6jmmui2qbv7bhg4c1jbdx?min_id=300&limit=5
```

```json
[
  {
    "id": "bafyreib4gy7...",
    "content": "<p>hello from sequence 301</p>",
    "corundum": { "sequence_number": 301, "epoch": 0 },
    ...
  },
  ...
]
```

**Errors:**

| Code | Error | Description |
|------|-------|-------------|
| 404 | `not_found` | No account with that IPNS name is known to this operator |
| 403 | `forbidden` | Account is private and the requesting user does not have an approved follow |

---

## Pagination

All timeline endpoints use cursor-based pagination. The cursors are opaque from the client's perspective except for the archive timeline (where they are sequence numbers).

To page backward through a timeline (load older content), use `max_id` set to the ID of the oldest status in the current page.

To page forward (load newer content), use `min_id` set to the ID of the newest status in the current page.

Link headers are provided on all paginated responses per RFC 5988:

```
Link: <https://social.example/api/v1/timelines/home?max_id=bafyrei...>; rel="next",
      <https://social.example/api/v1/timelines/home?min_id=bafyrei...>; rel="prev"
```
