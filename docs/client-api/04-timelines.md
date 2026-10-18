# Timelines

Timeline endpoints return paginated collections of Status entities, newest first. Pagination follows `00-design.md` (Pagination): opaque `cursor` and `limit`, plus the time filters `before` and `after`. Responses are `corundum:PaginatedResponse` objects.

A post that has been edited appears once in a timeline: as its newest version, at the position (sort time) of its first version.

## Common Query Parameters

These apply to every timeline endpoint below unless noted.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cursor` | string | — | Opaque cursor from a previous response's `pagination` |
| `limit` | integer | 20 | Maximum number of results (max 40) |
| `before` | string (RFC 3339) | — | Only items whose sort time is strictly earlier than this |
| `after` | string (RFC 3339) | — | Only items whose sort time is strictly later than this |

## Standard Timelines

### GET /api/corundum/v1/timelines/home

Returns statuses from accounts the authenticated user follows, newest first.

**Authentication:** Required (`read:statuses` scope)

**Query Parameters:** Common parameters, plus:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `local` | boolean | `false` | Return only statuses from this operator's local accounts |

**Returns:** PaginatedResponse of Status entities.

**Errors:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 400 | `INVALID_CURSOR` | The cursor fails verification or was issued for a different request |
| 401 | `UNAUTHORIZED` | No valid token provided |
| 403 | `INSUFFICIENT_SCOPE` | Token lacks `read:statuses` scope |

---

### GET /api/corundum/v1/timelines/public

Returns public statuses from the federated network, or only from the local operator when `local=true`.

**Authentication:** Optional. Unauthenticated requests may receive a reduced result set at operator discretion.

**Query Parameters:** Common parameters, plus:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `local` | boolean | `false` | Return only statuses from this operator's local accounts |
| `remote` | boolean | `false` | Return only statuses from remote (federated) accounts |
| `only_media` | boolean | `false` | Return only statuses that include media attachments |

`local` and `remote` are mutually exclusive. If both are `true`, the operator returns `422 VALIDATION_FAILED`.

**Returns:** PaginatedResponse of Status entities.

---

### GET /api/corundum/v1/timelines/tag/:hashtag

Returns statuses for the given hashtag.

**Authentication:** Optional.

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:hashtag` | The hashtag to search for, without the leading `#` character |

**Query Parameters:** Common parameters, plus:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `local` | boolean | `false` | Return only statuses from local accounts |
| `remote` | boolean | `false` | Return only statuses from remote accounts |
| `only_media` | boolean | `false` | Return only statuses that include media attachments |
| `any[]` | array of strings | — | Return statuses that contain any of these additional hashtags |
| `all[]` | array of strings | — | Return statuses that contain all of these additional hashtags |
| `none[]` | array of strings | — | Exclude statuses that contain any of these hashtags |

**Returns:** PaginatedResponse of Status entities.

---

### GET /api/corundum/v1/timelines/list/:list_id

Returns statuses from accounts in the specified list.

**Authentication:** Required. The list must belong to the authenticated user.

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:list_id` | The ID of the list |

**Query Parameters:** Common parameters.

**Returns:** PaginatedResponse of Status entities.

**Errors:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 401 | `UNAUTHORIZED` | No valid token provided |
| 404 | `NOT_FOUND` | List does not exist or does not belong to the authenticated user |

---

## Corundum-Specific Timelines

### GET /api/corundum/v1/timelines/archive/:account_id

Returns the entries of an account's IPFS-backed archive in sequence order, newest first. Unlike the other timelines, this one lists every entry, including edits (`corundum.replaces` set) and the activities edits replaced, because the archive never changes (spec Chapter 9).

The archive is reachable from the account's RootManifest, so it can be read and verified even if the account's operator is unavailable. The archive is divided into epochs: fixed chunks of 256 entries, where epoch *k* holds `seq` 256*k* to 256*k*+255. Each status carries `corundum.seq` and `corundum.epoch` (= `floor(seq / 256)`).

**Authentication:** Optional.

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:account_id` | The account's DID, percent-encoded as one path segment (`00-design.md`, Identifiers) |

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cursor` | string | — | Opaque cursor from a previous response |
| `limit` | integer | 20 | Maximum number of results (max 40) |
| `max_seq` | integer | — | Start at entries with `seq` at or below this value |
| `epoch` | integer | — | Restrict results to this epoch (`seq` 256×`epoch` to 256×`epoch`+255) |

`max_seq` and `epoch` are filters, bound into the cursors the response returns; the cursors themselves are opaque.

**Returns:** PaginatedResponse of Status entities, in descending `seq` order.

**Example:**

```
GET /api/corundum/v1/timelines/archive/did%3Awebvh%3A<SCID>%3Abirdsite.example%3Ausers%3Aalice?max_seq=301&limit=2
```

```json
{
  "@type": "corundum:PaginatedResponse",
  "items": [
    { "id": "<activity id>", "corundum": { "seq": 301, "epoch": 1, "...": "..." }, "...": "..." },
    { "id": "<activity id>", "corundum": { "seq": 300, "epoch": 1, "...": "..." }, "...": "..." }
  ],
  "pagination": { "nextCursor": "<opaque cursor>", "prevCursor": "<opaque cursor>", "limit": 2 }
}
```

**Errors:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 400 | `INVALID_CURSOR` | The cursor fails verification or was issued for a different request |
| 404 | `NOT_FOUND` | No account with that DID is known to this operator, and the DID could not be resolved |
| 502 | `DID_RESOLUTION_FAILED` | The account's DID document could not be fetched |

---

## Pagination

See `00-design.md` (Pagination). To load older content, pass the `nextCursor` of the current page; to load newer content, pass its `prevCursor`.
