# Curation

Corundum's curation layer separates the act of making content judgments from the act of hosting content. Curators are independent entities — organizations, research groups, or specialized services — that publish signed feeds of content judgments (spec Chapters 27–32). Operators subscribe to curator feeds and apply those judgments according to their own policy. This API exposes the curation layer to clients and to operator administrators.

This section has no Mastodon analogue.

## Concepts

**Curator:** An independent entity that publishes signed `CurationEntry` objects about content, identified by content hash (spec Chapter 28). A curator is identified by the URL of its Authority Declaration, called its **authority** (the declaration's `id`, and the `authority` field of every entry it issues). Curators are not Corundum user identities and have no DID or IPNS name.

**Authority Declaration:** An attached JWS (spec Chapter 34, `corundumType` `"AuthorityDeclaration"`) served at the authority URL. It names the curator's keys and delegate keys, organization, jurisdiction claims, governance model, appeal process, hash capabilities, and feed access (spec Chapter 30).

**CurationEntry:** One signed judgment: one or more content-hash subjects, a `reason` from the spec's taxonomy (`category/subcode`, e.g. `spam/spam-commercial`), and an `ordinal` from `0.0` to `1.0` giving its strength. Entries carry a feed `sequence` number, and may `expire` or `supersede` an earlier entry. An entry at ordinal `0.0` retracts the entry it supersedes (spec Chapter 29).

**CurationLabel:** This API's projection of a CurationEntry that matches a particular status, together with the action this operator takes on it (`02-entities.md`). It carries the entry's JWS line verbatim, so a client can verify the curator's signature itself.

**Operator policy:** Each operator chooses which curators it subscribes to and, for each reason category, the ordinal thresholds at which it labels, warns, or blocks. The actions are `label` (show the content with a label), `warn` (interstitial warning before showing), and `block` (do not serve the content). Thresholds are always greater than `0.0`, so a retraction never matches a rule.

**Restricted feeds.** Some feeds, such as `legal/*` child-safety hash lists, are readable only by operators the curator has admitted, and are fetched with RFC 9421-authenticated requests (spec Chapter 32). This API never exposes the contents of a restricted feed to clients; a client sees only the labels that apply to statuses it can see, subject to the operator's policy.

Path parameters named `:authority` are the authority URL, percent-encoded as one path segment (`00-design.md`, Identifiers). For example, `https://curator.example/.well-known/corundum-curator` becomes `https%3A%2F%2Fcurator.example%2F.well-known%2Fcorundum-curator`.

---

## Client Endpoints

### GET /api/corundum/v1/curation/curators

List the curators this operator subscribes to.

**Authentication:** Optional. The subscription list is public; any client may retrieve it.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cursor` | string | — | Opaque pagination cursor (`00-design.md`, Pagination) |
| `limit` | integer | 40 | Maximum number of results (max 80) |

**Returns:** PaginatedResponse of curator objects.

```json
{
  "@type": "corundum:PaginatedResponse",
  "items": [
    {
      "authority": "https://curator.example/.well-known/corundum-curator",
      "display_name": "Example Spam Curator",
      "reasons": ["spam/spam-commercial", "spam/spam-phishing"],
      "feed_access": "public",
      "subscribed_since": "2025-01-01T00:00:00Z",
      "last_polled": "2025-03-10T12:00:00Z",
      "latest_sequence": 48293,
      "governance_url": "https://curator.example/governance",
      "appeal_url": "https://curator.example/appeals"
    }
  ],
  "pagination": { "limit": 40 }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `authority` | string | The curator's Authority Declaration URL. Stable identifier. |
| `display_name` | string | The organization name from the declaration. |
| `reasons` | array of strings | The reasons this operator ingests from this curator, as `category/subcode` strings. |
| `feed_access` | string | `public` or `restricted`, as declared. |
| `subscribed_since` | string (ISO 8601) | When this operator began subscribing to this curator's feed. |
| `last_polled` | string (ISO 8601) | When this operator last fetched the curator's feed. |
| `latest_sequence` | integer | Highest feed `sequence` this operator has processed. |
| `governance_url` | string | The declaration's governance model link. |
| `appeal_url` | string | The declaration's appeal process link. |

---

### GET /api/corundum/v1/curation/curators/:authority

Get a single subscribed curator.

**Authentication:** Optional.

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:authority` | The curator's authority URL, percent-encoded |

**Returns:** Curator object (same shape as the list items).

**Errors:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 404 | `NOT_FOUND` | This operator does not subscribe to a curator with this authority |

---

### GET /api/corundum/v1/curation/curators/:authority/declaration

Get the curator's Authority Declaration as this operator last fetched and verified it.

**Authentication:** Optional.

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:authority` | The curator's authority URL, percent-encoded |

**Returns:** The stored attached-JWS bytes, exactly as served at the authority URL, with `Content-Type: application/jose+json`. The operator never re-serializes them, so a client can verify the signatures itself (spec Chapter 34) or compare them with a copy fetched from the authority URL directly.

**Errors:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 404 | `NOT_FOUND` | This operator does not subscribe to a curator with this authority |

---

### GET /api/corundum/v1/statuses/:id/curation

Get the curation labels that apply to a status. This is the only definition of this endpoint; `03-statuses.md` refers here.

**Authentication:** Optional. Unauthenticated requests return labels from the operator's own subscriptions. Authenticated requests may additionally include labels from curators the user has subscribed to, where the operator offers personal subscriptions.

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:id` | The activity id of the status |

**Returns:** Array of CurationLabel entities (`02-entities.md`). An empty array means no subscribed curator has an unexpired, non-retracted entry matching this content. Superseded entries are not returned; only the entry that supersedes them is.

```json
[
  {
    "authority": "https://curator.example/.well-known/corundum-curator",
    "curator_display_name": "Example Spam Curator",
    "sequence": 48293,
    "reason": "spam/spam-commercial",
    "ordinal": 0.85,
    "issued": "2025-01-15T12:34:56Z",
    "expires": null,
    "matched_subject": { "hash_type": "sha256", "hash_scope": "text-exact" },
    "entry": "<the CurationEntry JWS line, verbatim>",
    "operator_action": "label",
    "appeal_url": "https://curator.example/appeals"
  }
]
```

A label is the curator's judgment; `operator_action` is this operator's decision about it under its policy. Neither binds any other operator. A label with `operator_action` `block` is returned only to the status's author and to administrators, since the content itself is not served to anyone else.

To verify a label, decode `entry` (an attached JWS, `corundumType` `"CurationEntry"`), check its signatures against the keys in the curator's Authority Declaration (spec Chapter 34 and the CurationEntry wire format in spec Chapter 32), and check that the subject hash matches the content.

**Errors:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 404 | `NOT_FOUND` | No status with this id is known to this operator |
| 410 | `GONE` | The status has been deleted |

---

### POST /api/corundum/v1/curation/appeals

Submit an appeal against a label. The operator forwards the appeal to the appeal process declared in the curator's Authority Declaration on the user's behalf.

**Authentication:** Required (`write:curation` scope).

**Content-Type:** `application/json`

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `status_id` | string | yes | Activity id of the labeled status |
| `authority` | string | yes | Authority URL of the curator that issued the entry |
| `sequence` | integer | yes | Feed sequence number of the entry being appealed |
| `appeal_text` | string | yes | The user's appeal statement |

**Behavior:** The operator delivers the appeal to the curator's declared appeal process. It does not change its own curation state as a result; the label stays until the curator publishes an entry that supersedes or retracts it.

**Returns:**

```json
{
  "appeal_id": "<curator-assigned appeal id>",
  "appeal_url": "https://curator.example/appeals/<curator-assigned appeal id>",
  "submitted_at": "2025-03-10T15:00:00Z"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `appeal_id` | string | The id the curator's appeal system assigned. |
| `appeal_url` | string | URL where the user can track the appeal. |
| `submitted_at` | string (ISO 8601) | When the appeal was submitted. |

**Errors:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 401 | `UNAUTHORIZED` | No valid token provided |
| 403 | `INSUFFICIENT_SCOPE` | Token lacks `write:curation` scope |
| 404 | `NOT_FOUND` | No subscribed curator with this authority, or no active entry with this sequence applies to this status |
| 502 | `UPSTREAM_UNAVAILABLE` | The curator's appeal endpoint could not be reached |

---

## Admin Endpoints

These endpoints are restricted to operator administrators. Reads require `admin:read`; changes require `admin:write`.

### POST /api/corundum/v1/admin/curation/curators

Subscribe to a curator.

**Authentication:** Required (`admin:write` scope)

**Content-Type:** `application/json`

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `authority` | string | yes | The curator's Authority Declaration URL |
| `reasons` | array of strings | no | Restrict ingestion to these reasons; `category/*` matches a whole category. If omitted, every reason the curator issues is ingested. |

For a restricted feed, the curator must already have admitted this operator; the operator fetches the feed with RFC 9421-authenticated requests (spec Chapter 32).

**Returns:** Curator object for the new subscription.

**Errors:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 400 | `CURATION_AUTHORITY_INVALID` | The Authority Declaration is invalid, its signatures do not verify, or it does not match its fetch URL |
| 403 | `FORBIDDEN` | The feed is restricted and the curator has not admitted this operator |
| 409 | `ALREADY_SUBSCRIBED` | This operator already subscribes to this curator |
| 502 | `UPSTREAM_UNAVAILABLE` | The authority URL or feed could not be reached |

---

### DELETE /api/corundum/v1/admin/curation/curators/:authority

Unsubscribe from a curator. The operator stops applying the curator's entries; labels derived from them are no longer returned or enforced.

**Authentication:** Required (`admin:write` scope)

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:authority` | The curator's authority URL, percent-encoded |

**Returns:** `204 No Content` on success.

**Errors:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 404 | `NOT_FOUND` | This operator does not subscribe to a curator with this authority |

---

### GET /api/corundum/v1/admin/curation/policy

Get the operator's current curation policy.

**Authentication:** Required (`admin:read` scope)

**Returns:**

```json
{
  "rules": [
    { "reason": "legal/*", "action": "block", "min_ordinal": 0.5 },
    { "reason": "spam/*", "action": "block", "min_ordinal": 0.9 },
    { "reason": "spam/*", "action": "label", "min_ordinal": 0.7 },
    { "reason": "nsfw/*", "action": "warn", "min_ordinal": 0.6 }
  ],
  "default_action": "label"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `rules` | array | Policy rules. Each has a `reason` (a `category/subcode`, or `category/*` for a whole category), an `action` (`label`, `warn`, or `block`), and a `min_ordinal` greater than `0.0` and at most `1.0`. A matching entry triggers the rule when its `ordinal` is at least `min_ordinal`. When several rules trigger, the strongest action applies (`block` over `warn` over `label`). |
| `default_action` | string | Action for an entry from a subscribed curator that no rule covers: `label`, `warn`, or `block`. Entries at ordinal `0.0` never trigger it. |

How an operator handles legally mandated categories, such as reporting and preserving apparent CSAM, depends on its jurisdiction and is outside this API (spec Chapters 29 and 39).

---

### PUT /api/corundum/v1/admin/curation/policy

Replace the operator's curation policy.

**Authentication:** Required (`admin:write` scope)

**Content-Type:** `application/json`

**Request Body:** A complete policy object, same shape as the GET response.

**Returns:** The updated policy object.

**Errors:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 422 | `VALIDATION_FAILED` | A rule names an unknown reason or action, or a `min_ordinal` is not greater than `0.0` or exceeds `1.0` |
