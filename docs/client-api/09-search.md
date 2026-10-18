# Search

Search endpoints let clients find accounts, statuses, and hashtags. Corundum extensions provide direct lookup by activity id or IPNS name, using the globally addressable nature of Corundum identifiers.

## Standard Search

### GET /api/corundum/v1/search

Search for accounts, statuses, and hashtags.

**Authentication:** Optional.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `q` | string | yes | The search query |
| `type` | string | no | Restrict results to one type: `accounts`, `statuses`, or `hashtags`. If omitted, all three types are returned. |
| `resolve` | boolean | no | If `true`, attempt to resolve a handle, DID, or activity id in `q` from the network when the local operator does not have it. Requires authentication. Default: `false`. |
| `following` | boolean | no | If `true`, restrict account results to accounts the authenticated user follows. Requires authentication. Default: `false`. |
| `account_id` | string (DID) | no | Restrict status results to statuses authored by this account. |
| `exclude_unreviewed` | boolean | no | If `true`, exclude statuses that carry curation labels from any subscribed curator. Default: `false`. |
| `cursor` | string | no | Opaque cursor from a previous response (`00-design.md`, Pagination). |
| `limit` | integer | no | Maximum number of results per type. Default: 20. Maximum: 40. |

**Returns:**

```json
{
  "accounts": [],
  "statuses": [],
  "hashtags": [],
  "pagination": { "nextCursor": "<opaque cursor>", "limit": 20 }
}
```

Each array contains entities of its respective type (Account, Status, or Tag). If `type` is specified, the other two arrays are present but empty. Results within each array are ordered by relevance, descending. The cursor binds the query and its ranking position, so the next page continues the same ranking.

**Errors:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 400 | `INVALID_REQUEST` | `q` is missing |
| 400 | `INVALID_CURSOR` | The cursor fails verification or was issued for a different query |
| 401 | `UNAUTHORIZED` | `resolve` or `following` was `true` but no valid token was provided |

---

## Corundum-Specific Search

These endpoints resolve identifiers that are meaningful on every operator: an activity id is the hash of the activity's bytes, and an IPNS name embeds the content-signing key that publishes a RootManifest.

### GET /api/corundum/v1/search/by_cid/:cid

Look up a status by its activity id.

**Authentication:** Optional.

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:cid` | The activity id (raw-codec CID, base32 `bafkrei...`) |

**Behavior:** The operator first checks its local store. If the activity is not cached locally and the operator has IPFS resolution enabled, it fetches the bytes from the IPFS network, recomputes their CID, and verifies the SigningRecord against the author's DID document (spec Chapter 34). A CID mismatch or a failed signature returns `NOT_FOUND` rather than unverified content.

**Returns:** Status entity.

```json
{
  "id": "<activity id>",
  "content": "<p>hello world</p>",
  "account": { "id": "did:webvh:<SCID>:birdsite.example:users:alice", "...": "..." },
  "corundum": {
    "seq": 1042,
    "epoch": 4,
    "signing_record_cid": "<CID of the SigningRecord>",
    "replaces": null,
    "replaced_by": null,
    "curation_labels": []
  },
  "...": "..."
}
```

**Errors:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 404 | `NOT_FOUND` | No status with this id is known to this operator and resolution from IPFS failed, failed verification, or is disabled |
| 410 | `GONE` | The author deleted this status |

---

### GET /api/corundum/v1/search/by_ipns/:ipns_name

Look up an account by an IPNS name. An IPNS name is not an account id: it changes whenever the account's content key changes (for example, on migration), so this lookup succeeds only for an account's current IPNS name.

**Authentication:** Optional.

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:ipns_name` | An IPNS name (`k51...`) |

**Behavior:** The operator resolves the IPNS name to the current RootManifest, verifies it, and reads the DID from its identity block. It then resolves that DID and returns the account only if the DID document currently names this IPNS name in its `CorundumIdentity` service (spec Chapter 6). Otherwise the IPNS name is stale or unauthorized, and the operator returns `NOT_FOUND`. The operator may cache the result.

**Returns:** Account entity.

```json
{
  "id": "did:webvh:<SCID>:birdsite.example:users:alice",
  "username": "alice",
  "acct": "alice@birdsite.example",
  "corundum": {
    "ipns_name": "<IPNS name>",
    "operator_endpoint": "https://birdsite.example",
    "root_manifest_cid": "<CID of the RootManifest>",
    "key_custody": "operator"
  },
  "...": "..."
}
```

**Errors:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 404 | `NOT_FOUND` | The IPNS name could not be resolved, or the DID it leads to does not currently name it |
| 502 | `DID_RESOLUTION_FAILED` | The DID document could not be fetched |
