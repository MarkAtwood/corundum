# Search

Search endpoints allow clients to find accounts, statuses, and hashtags. Standard search uses the Mastodon-compatible v2 endpoint. Corundum extensions provide direct lookup by CID or IPNS name, leveraging the globally addressable nature of Corundum content.

## Standard Search

### GET /api/v2/search

Search for accounts, statuses, and hashtags.

**Authentication:** Optional. Authenticated requests expand results to include private statuses the authenticated user is authorized to see (e.g., statuses from accounts the user follows, where the account visibility is set to followers-only).

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `q` | string | yes | The search query |
| `type` | string | no | Restrict results to one type: `accounts`, `statuses`, or `hashtags`. If omitted, all three types are returned. |
| `resolve` | boolean | no | If `true`, attempt to resolve remote accounts and statuses via federation when the local operator does not have them. Requires authentication. Default: `false`. |
| `following` | boolean | no | If `true`, restrict account results to accounts the authenticated user follows. Requires authentication. Default: `false`. |
| `account_id` | string (IPNS name) | no | Restrict status results to statuses authored by this account. Value is an IPNS name (base36lower). |
| `exclude_unreviewed` | boolean | no | If `true`, exclude statuses that carry unreviewed curation labels from any subscribed curator. Default: `false`. |
| `max_id` | string | no | Return results with an ID strictly less than this value. Used for pagination. |
| `min_id` | string | no | Return results with an ID strictly greater than this value. Used for pagination. |
| `limit` | integer | no | Maximum number of results per type. Default: 20. Maximum: 40. |
| `offset` | integer | no | Integer offset for result pagination. Supported as an alternative to cursor-based pagination for search, since full-text ranking makes cursor positioning ambiguous. Default: 0. |

`offset` and `max_id`/`min_id` should not be combined in the same request. If both are provided, the operator returns a `400 Bad Request`.

**Returns:**

```json
{
  "accounts": [...],
  "statuses": [...],
  "hashtags": [...]
}
```

Each array contains entities of its respective type (Account, Status, or Tag). If `type` is specified, the other two arrays are present but empty. Results within each array are ordered by relevance, descending.

**Errors:**

| Code | Error | Description |
|------|-------|-------------|
| 400 | `invalid_request` | `q` is missing, or `offset` and cursor parameters are both present |
| 401 | `unauthorized` | `resolve` or `following` was `true` but no valid token was provided |

---

## Corundum-Specific Search

These endpoints leverage the globally addressable nature of Corundum identifiers. Because CIDs are content hashes and IPNS names are public key hashes, either identifier can be resolved from any participating operator without central coordination.

### GET /api/v1/corundum/search/by_cid/:cid

Look up a status by its CID.

**Authentication:** Optional.

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:cid` | The CID of the activity (base32lower) |

**Behavior:** The operator first checks its local store. If the content is not cached locally and the operator has IPFS resolution enabled, it attempts to fetch the content from the IPFS network. Because the CID is a cryptographic hash of the content, the operator can verify any retrieved copy is authentic by recomputing the hash; a mismatch is detectable and the operator returns `not_found` rather than serving unverified content.

**Returns:** Status entity if the content is found and the requesting user is authorized to see it.

```json
{
  "id": "bafyreib4gy7...",
  "content": "<p>hello world</p>",
  "corundum": {
    "media_cid": "bafyreib4gy7..."
  },
  ...
}
```

**Errors:**

| Code | Error | Description |
|------|-------|-------------|
| 403 | `forbidden` | The status exists but the authenticated user is not authorized to view it (e.g., followers-only post from an account the user does not follow) |
| 404 | `not_found` | No status with this CID is known to this operator and resolution from IPFS failed or is disabled |
| 410 | `gone` | The status existed but has been deleted (tombstoned) |

---

### GET /api/v1/corundum/search/by_ipns/:ipns_name

Look up an account by its IPNS name.

**Authentication:** Optional.

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:ipns_name` | The account's IPNS name (base36lower), e.g. `k51qzi5uqu5dh9ihj4p2v5sl3hxvv27ryx2w0xrsv6jmmui2qbv7bhg4c1jbdx` |

**Behavior:** The operator checks its local account store. If the account is not known locally, the operator resolves the IPNS name to find the account's current RootManifest and operator endpoint, then returns an Account entity populated from that data. The operator may cache the result.

**Returns:** Account entity.

```json
{
  "id": "k51qzi5uqu5dh9ihj4p2v5sl3hxvv27ryx2w0xrsv6jmmui2qbv7bhg4c1jbdx",
  "username": "alice",
  "acct": "alice@social.example",
  "ipns_name": "k51qzi5uqu5dh9ihj4p2v5sl3hxvv27ryx2w0xrsv6jmmui2qbv7bhg4c1jbdx",
  "did": "did:web:alice.example",
  "operator_endpoint": "https://social.example",
  ...
}
```

**Errors:**

| Code | Error | Description |
|------|-------|-------------|
| 404 | `not_found` | No account with this IPNS name is known to this operator and IPNS resolution failed or is disabled |
