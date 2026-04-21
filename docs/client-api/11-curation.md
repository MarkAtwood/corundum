# Curation

Corundum's curation layer separates the act of making content judgments from the act of hosting content. Curators are independent entities — organizations, research groups, or specialized services — that publish signed feeds of content judgments. Operators subscribe to curator feeds and apply those judgments according to their own policy. This API exposes the curation layer to clients and to operator administrators.

This section has no Mastodon analogue.

## Concepts

**Curator:** An independent entity that publishes signed feeds of content judgments. Each curator has a stable IPNS name and an authority declaration: a signed document that describes the curator's scope, the categories of content it judges, and the governance and appeals processes it provides.

**Authority declaration:** A signed document published by the curator in IPFS that defines the curator's mandate. Operators and users can verify any curator judgment by checking it against the published authority declaration. The CID of the authority declaration is the stable reference for the curator's claimed authority.

**CurationLabel:** A signed judgment applied to a specific content CID. Labels carry a category (e.g., `csam`, `spam`, `misinformation`), a confidence level, and a reference to the authority declaration that backs the judgment. Labels are independently verifiable: any party can re-check the signature.

**Operator policy:** Each operator configures which curators it subscribes to and what action to take for each label category. The policy options are `label` (show the content with a label attached), `warn` (interstitial warning before showing), or `block` (do not serve the content at all). Some categories (e.g., `csam`) are expected to always be blocked; operator policy cannot override legal obligations.

---

## Client Endpoints

### GET /api/v1/corundum/curators

List the curator feeds this operator subscribes to.

**Authentication:** Optional. The subscription list is public; any client may retrieve it.

**Returns:** Array of curator objects.

```json
[
  {
    "curator_id": "k51qzi5uqu5dh9ihj4p2v5sl3hxvv27ryx2w0xrsv6jmmui2qbv7bhg4c1jbdx",
    "display_name": "CSAM Hash Database",
    "authority_declaration_cid": "bafyreiabcdefghijklmnopqrstuvwxyz234567abcdefghijklmnopq",
    "authority_declaration_url": "https://curator.example/authority",
    "judgment_categories": ["csam"],
    "subscribed_since": "2024-01-01T00:00:00Z",
    "last_polled": "2024-03-10T12:00:00Z",
    "entry_count": 150000,
    "governance_url": "https://curator.example/governance",
    "appeal_url": "https://curator.example/appeals"
  }
]
```

| Field | Type | Description |
|-------|------|-------------|
| `curator_id` | string | The curator's IPNS name (base36lower). Stable identifier. |
| `display_name` | string | Human-readable name for the curator feed. |
| `authority_declaration_cid` | string | CID of the curator's authority declaration document in IPFS. |
| `authority_declaration_url` | string | HTTP URL where the authority declaration can be retrieved. |
| `judgment_categories` | array of strings | The label categories this curator issues, e.g. `["csam", "spam"]`. |
| `subscribed_since` | string (ISO 8601) | When this operator began subscribing to this curator's feed. |
| `last_polled` | string (ISO 8601) | When this operator last fetched an updated feed from this curator. |
| `entry_count` | integer | Number of active judgment entries currently in this curator's feed as known to this operator. |
| `governance_url` | string | URL of the curator's governance documentation. |
| `appeal_url` | string | URL of the curator's appeals process. |

---

### GET /api/v1/corundum/curators/:curator_id

Get the full details for a single curator feed.

**Authentication:** Optional.

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:curator_id` | The curator's IPNS name (base36lower) |

**Returns:** Curator object (same shape as array entries from the list endpoint), with no additional fields. The authority declaration summary is accessible via the `authority_declaration_cid` and `authority_declaration_url` fields; the full document is returned by `GET /api/v1/corundum/curators/:curator_id/authority`.

**Errors:**

| Code | Error | Description |
|------|-------|-------------|
| 404 | `not_found` | This operator does not subscribe to a curator with this ID |

---

### GET /api/v1/corundum/curators/:curator_id/authority

Get the full authority declaration published by a curator.

**Authentication:** Optional.

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:curator_id` | The curator's IPNS name (base36lower) |

**Returns:** The authority declaration object as published by the curator in IPFS. The exact structure is defined in the Corundum curation specification. The response includes the raw declaration and its CID so the client can independently verify the content matches the declared CID.

```json
{
  "cid": "bafyreiabcdefghijklmnopqrstuvwxyz234567abcdefghijklmnopq",
  "declaration": {
    "curator_ipns_name": "k51qzi5...",
    "display_name": "CSAM Hash Database",
    "version": 1,
    "categories": ["csam"],
    "scope": "...",
    "governance_url": "https://curator.example/governance",
    "appeal_url": "https://curator.example/appeals",
    "signed_at": "2024-01-01T00:00:00Z",
    "signature": "..."
  }
}
```

**Errors:**

| Code | Error | Description |
|------|-------|-------------|
| 404 | `not_found` | This operator does not subscribe to a curator with this ID |

---

### GET /api/v1/statuses/:id/curation

Get the curation labels applied to a status by any subscribed curator.

**Authentication:** Optional.

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:id` | The CID of the status (base32lower) |

**Returns:** Array of CurationLabel entities. An empty array means no subscribed curator has issued a judgment against this content.

```json
[
  {
    "label_id": "bafyreicuration...",
    "curator_id": "k51qzi5...",
    "curator_display_name": "Spam Detection Service",
    "status_cid": "bafyreib4gy7...",
    "category": "spam",
    "confidence": 0.97,
    "authority_declaration_cid": "bafyreiabcdef...",
    "issued_at": "2024-03-09T08:00:00Z",
    "operator_action": "label"
  }
]
```

| Field | Type | Description |
|-------|------|-------------|
| `label_id` | string | CID of the CurationLabel object in IPFS. Uniquely identifies this specific judgment. |
| `curator_id` | string | IPNS name of the curator that issued this label. |
| `curator_display_name` | string | Human-readable name of the curator. |
| `status_cid` | string | CID of the content this label applies to. |
| `category` | string | Label category, e.g. `csam`, `spam`, `misinformation`. |
| `confidence` | number | Curator's confidence score, in the range `0.0` to `1.0`. Meaning is curator-defined; consult the authority declaration. |
| `authority_declaration_cid` | string | CID of the authority declaration that backs this judgment. Clients can verify the label is within the curator's declared scope. |
| `issued_at` | string (ISO 8601) | When the curator issued this label. |
| `operator_action` | string | The action this operator is taking based on its policy: `label`, `warn`, or `block`. A `block` response means the client received this information via an admin or transparency endpoint; the content itself would normally not be served. |

**Errors:**

| Code | Error | Description |
|------|-------|-------------|
| 404 | `not_found` | No status with this CID is known to this operator |

---

### POST /api/v1/corundum/curation/appeal

Submit an appeal against a curation label. The operator forwards the appeal to the curator's appeals endpoint on the user's behalf.

**Authentication:** Required.

**Content-Type:** `application/json`

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `status_id` | string | yes | CID of the status the label was applied to |
| `curator_id` | string | yes | IPNS name of the curator that issued the label |
| `appeal_text` | string | yes | The user's appeal statement |

**Behavior:** The operator constructs an appeal submission and delivers it to the `appeal_url` declared in the curator's authority declaration. The appeal is associated with the authenticated user's account. The operator does not modify its local curation state as a result of this call; the label remains in place until the curator issues an updated judgment.

**Returns:**

```json
{
  "appeal_id": "8f3a92c1",
  "appeal_url": "https://curator.example/appeals/8f3a92c1",
  "submitted_at": "2024-03-10T15:00:00Z"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `appeal_id` | string | The ID assigned to this appeal by the curator's appeals system. |
| `appeal_url` | string | URL where the user can track the appeal status. |
| `submitted_at` | string (ISO 8601) | When the appeal was submitted. |

**Errors:**

| Code | Error | Description |
|------|-------|-------------|
| 400 | `no_label_found` | No active label from the specified curator applies to the specified status |
| 404 | `curator_not_found` | This operator does not subscribe to a curator with the given ID |
| 502 | `appeal_endpoint_unavailable` | The curator's appeals endpoint could not be reached |

---

## Admin Endpoints

These endpoints require `admin:write` scope and are restricted to operator administrators. They are not available to ordinary user tokens.

### POST /api/v1/admin/corundum/curators

Subscribe to a new curator feed.

**Authentication:** Required (`admin:write` scope)

**Content-Type:** `application/json`

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `curator_endpoint` | string | yes | HTTPS URL of the curator's feed endpoint |
| `auto_enforce` | boolean | yes | If `true`, the operator will automatically apply this curator's judgments according to the operator's curation policy. If `false`, labels are recorded but no enforcement action is taken. |
| `categories` | array of strings | no | Restrict subscription to these label categories. If omitted, all categories published by this curator are ingested. |

**Returns:** Curator object for the newly subscribed feed.

**Errors:**

| Code | Error | Description |
|------|-------|-------------|
| 409 | `already_subscribed` | This operator already subscribes to this curator |
| 422 | `invalid_authority_declaration` | The curator's authority declaration could not be fetched or its signature is invalid |
| 502 | `curator_endpoint_unavailable` | The curator feed endpoint could not be reached |

---

### DELETE /api/v1/admin/corundum/curators/:curator_id

Unsubscribe from a curator feed. Existing labels already applied to content are not retroactively removed; they remain in the local store but are no longer used for enforcement.

**Authentication:** Required (`admin:write` scope)

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:curator_id` | The curator's IPNS name (base36lower) |

**Returns:** `204 No Content` on success.

**Errors:**

| Code | Error | Description |
|------|-------|-------------|
| 404 | `not_found` | This operator does not subscribe to a curator with this ID |

---

### GET /api/v1/admin/corundum/curation/policy

Get the operator's current curation enforcement policy.

**Authentication:** Required (`admin:write` scope)

**Returns:**

```json
{
  "enforce_csam": true,
  "enforce_spam": false,
  "default_action": "label",
  "hard_block_categories": ["csam"]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `enforce_csam` | boolean | Whether CSAM labels from subscribed curators result in enforcement action. |
| `enforce_spam` | boolean | Whether spam labels from subscribed curators result in enforcement action. |
| `default_action` | string | The default action taken for labeled content not covered by a specific rule: `label`, `warn`, or `block`. |
| `hard_block_categories` | array of strings | Categories for which content is always blocked, regardless of other policy settings. Operators must include `csam` in this list. |

---

### PUT /api/v1/admin/corundum/curation/policy

Update the operator's curation enforcement policy.

**Authentication:** Required (`admin:write` scope)

**Content-Type:** `application/json`

**Request Body:** Same fields as the GET response. All fields are optional; only provided fields are updated.

**Returns:** The full updated policy object (same shape as GET response).

**Errors:**

| Code | Error | Description |
|------|-------|-------------|
| 422 | `invalid_policy` | The policy is internally inconsistent (e.g., `hard_block_categories` does not include `csam`, which is required). |
