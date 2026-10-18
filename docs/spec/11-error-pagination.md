## Part XI: Error Handling and Pagination

### Chapter 37: The Error Envelope

A consistent error format allows any client — whether an operator, a user client, or a monitoring system — to handle errors programmatically without parsing free-form error messages. The design follows RFC 9457 (Problem Details for HTTP APIs) in spirit: errors carry structured machine-readable data alongside a human-readable explanation.

Every Corundum inter-operator endpoint MUST return a non-2xx response that has a body as a `corundum:Error` with `Content-Type: application/json`. There is no other error format. Endpoint-specific errors are specializations: a `ReplyRejection` (Chapter 21) is a `corundum:Error` with `code` `REPLY_REJECTED`, and its reply reason code is in `details.reason`.

```json
{
  "@type": "corundum:Error",
  "code": "REPLY_REJECTED",
  "message": "Reply rejected: author is on the target user's block list",
  "httpStatus": 403,
  "retryable": false,
  "details": {
    "reason": "blocked-user",
    "parentId": "<identifier of the parent post>",
    "replyId": "<identifier of the rejected reply>"
  }
}
```

**`code`** is a stable machine-readable string from the registry below. Operators and clients branch on this field. It never changes for a given error condition; the human-readable `message` may be updated for clarity without breaking clients.

**`message`** is a short English description for developers and logs. It is not suitable for display to end users (user-facing messages require localization and tone appropriate to the application). The message explains what happened in enough detail to understand the error without consulting documentation.

**`httpStatus`** duplicates the HTTP response status code in the body. This is redundant but useful: some proxy and logging infrastructure strips or loses HTTP status codes. Having the status in the body means the error is recoverable from a response body alone. It MUST equal the HTTP status of the response.

**`retryable`** is a boolean that tells the client whether repeating the request (with the same parameters) might succeed. `true` means the error is transient — the target was temporarily unreachable, rate limits will expire, a resource is temporarily locked. `false` means the error is permanent given the current request — the identity doesn't exist, the cursor is invalid, the algorithm is rejected. A `retryable: false` error MUST NOT be retried without changing the request; a `retryable: true` error SHOULD be retried with exponential backoff, waiting at least `retryAfter` seconds when it is present.

**`details`** is an object with structured error-specific fields. Its schema is specified per error code. Common `details` fields:
- `reason`: A sub-code providing finer-grained information within the error code. The values for `REPLY_REJECTED` are the normative reason codes of Chapter 21. Where the same condition can occur on several endpoints, the same `reason` string is used for it everywhere.
- `retryAfter`: A non-negative integer number of seconds after which the request MAY be retried. This is the delta-seconds form of the HTTP `Retry-After` header (RFC 9110 §10.2.3); the HTTP-date form is not used. When `retryAfter` is present, the response SHOULD also carry a `Retry-After` header with the same value.
- `missingField`: The specific field that failed validation (for `INVALID_REQUEST` errors).
- `requiredAlgorithm`: The algorithm the receiver requires (for `ALGORITHM_REJECTED` errors).
- `earliestSequence`: The oldest sequence number still retained (for `RESUME_BUFFER_EXHAUSTED` errors).

Receivers MUST ignore unknown `details` fields. A receiver that gets an unknown `code` or `reason` MUST treat the error as the generic meaning of its HTTP status code, with the `retryable` value given in the body.

**HTTP status code conventions.** Corundum follows standard HTTP semantics:
- `400 Bad Request` — The request is syntactically or semantically invalid; `retryable: false`.
- `401 Unauthorized` — The request lacks valid authentication; `retryable: false` until credentials are fixed.
- `403 Forbidden` — The request is authenticated but not authorized for this action (blocked user, policy violation); `retryable: false`.
- `404 Not Found` — The resource doesn't exist; `retryable: false`.
- `410 Gone` — The resource existed but has been deleted (tombstoned content) or is no longer retained; `retryable: false`.
- `429 Too Many Requests` — Rate limit exceeded; `retryable: true`. `details.retryAfter` MUST be present.
- `500 Internal Server Error` — Server fault; `retryable: true` with backoff.
- `502 Bad Gateway` — A service the operator depends on (DID resolver, IPFS, a remote operator) failed; `retryable: true` with backoff.
- `503 Service Unavailable` — The server is temporarily down; `retryable: true` with backoff. The body MAY be absent.

**Error code registry.** Codes are `UPPER_SNAKE_CASE`; `details.reason` values are `lower-kebab-case`. This registry is exhaustive for inter-operator endpoints: an operator MUST NOT return a `code` that is not listed here. Client APIs are outside the protocol; the non-normative reference API (`docs/client-api/00-design.md`) reuses this envelope with its own additional codes.

| Code | Status | Retryable | Condition |
|------|--------|-----------|-----------|
| `INVALID_REQUEST` | 400 | false | Request is malformed or missing a required field (`details.missingField`). |
| `RATE_LIMITED` | 429 | true | Rate limit exceeded on an endpoint that has no endpoint-specific code. `details.retryAfter` REQUIRED. |
| `SIGNATURE_INVALID` | 401 | false | Inter-operator request authentication failed (Chapter 19). `details.reason` is `invalid-operator-signature` or `insufficient-signature-coverage`. On the reply endpoints these conditions are reported as `REPLY_REJECTED` with the same reasons. |
| `KEY_NOT_FOUND` | 401 | false | The signing key is not in the signer's manifest or DID document, after the re-fetch required by Chapter 19. |
| `ALGORITHM_REJECTED` | 400 | false | Signature algorithm is not accepted by the Chapter 36 registry (`details.requiredAlgorithm`). |
| `TIMESTAMP_SKEW` | 400 | false | Activity `published` time is beyond the future-time tolerance (Chapter 34). |
| `IDENTITY_NOT_FOUND` | 404 | false | The identity does not exist on this operator. |
| `DID_RESOLUTION_FAILED` | 502 | true | The DID document could not be fetched. |
| `HANDLE_VERIFICATION_FAILED` | 400 | false | The handle does not verify against the identity. |
| `REPLY_REJECTED` | per reason | `rate-limited` and `follow-not-yet-known` only | Reply submission rejected. Status and `details.reason` per the Chapter 21 table. |
| `CURATION_AUTHORITY_INVALID` | 400 | false | The curation authority declaration is invalid or does not match its fetch URL. |
| `HASH_TYPE_UNSUPPORTED` | 400 | false | The curation hash type is not supported. |
| `CURATION_EXPIRED` | 400 | false | The curation entry or declaration is past its validity. |
| `CHUNK_MISSING` | 400 | false | Finalize referenced a chunk that was not uploaded (Chapter 16). |
| `MANIFEST_INVALID` | 400 | false | The media manifest is malformed or inconsistent with its chunks. |
| `UPLOAD_SESSION_EXPIRED` | 410 | false | The upload session no longer exists. Start a new session. |
| `INVALID_CURSOR` | 400 | false | The cursor fails verification or does not match the request (Chapter 38). |
| `RESUME_BUFFER_EXHAUSTED` | 410 | false | The requested resume sequence is older than the retained window (Part XV, Chapters 48 and 50). `details.earliestSequence` REQUIRED. |

New codes are added by revising this registry.

### Chapter 38: Pagination

**Why cursor-based, not offset-based.** The familiar offset pagination pattern — `?page=3&size=20` — works for static datasets but fails for live timelines. A timeline grows continuously: new posts appear at the top, and older posts shift down in the offset ordering. By the time a client requests "page 3," the 40 items that were previously on pages 1 and 2 may have grown to 43 items as three new posts arrived. The items that the client thinks are at offsets 40–59 are now at offsets 43–62. The client either sees three duplicate items (items it already fetched are now on page 3 as well) or silently skips three items (it fetched what was pages 1 and 2, but the first three items of what is now page 2 were not on the page 1 it fetched). Both outcomes are wrong, and neither is detectable by the client.

Cursors encode a stable position in the collection: "give me the 20 items after this specific position in the ordering." The position doesn't change as new items are added before or after it. If the client is at position P and requests the next page, it gets the items following P regardless of how many new items arrived after the client's previous request. This is the fundamental guarantee that makes cursor pagination correct for live timelines.

**Scope.** This chapter governs any inter-operator collection endpoint. The non-normative reference client API (`docs/client-api/`) reuses it for its own collections. No inter-operator endpoint defined by this specification currently returns a collection: reply submission, batch submission, and migration notification are single-object POSTs, and manifests are single documents. Two inter-operator mechanisms page through sequences of their own and are NOT governed by this chapter: the event stream resumes by sequence number (`since`, Chapters 48–52), and static curation feeds are read by log page and sequence number (Chapter 32).

**Cursor contents.** A cursor is a keyset cursor: it encodes the sort-key position of the last item returned (for a timeline ordered by epoch index and sequence number, that is an epoch index and sequence number). The operator keeps no per-cursor state. A cursor MUST also encode, and be bound to:
- the collection it was issued for,
- the filter parameters of the request that produced it, and
- the direction of traversal.

The cursor MUST carry a MAC over all of its contents, computed with a secret key known only to the issuing operator (HMAC-SHA-256 is sufficient). The operator MUST verify the MAC, and MUST verify that the collection and filter of the request match those bound in the cursor, before using the position. A cursor that fails either check MUST be rejected with `INVALID_CURSOR`. Without the MAC, a forged or altered cursor is indistinguishable from a valid one, and the operator would silently serve the wrong page.

A cursor grants no access. The operator MUST authorize each request on its own, exactly as if no cursor were present.

**Opacity.** Clients and remote operators MUST treat cursors as opaque strings and MUST NOT parse, construct, or modify them. The cursor encoding is private to the issuing operator, which MAY also encrypt it. The operator can change the encoding at any time; including a version field lets it keep accepting cursors in older encodings for as long as it chooses.

**No expiry.** Cursors do not expire. A keyset position stays meaningful as long as the sort key exists, and since there is no server state there is nothing to reclaim. A cursor stops being accepted only when the operator drops its encoding version or rotates the MAC key, and it is then rejected with `INVALID_CURSOR`. A cursor whose position falls on an item that has since been deleted still works: the next page begins at the first item after that position.

**Request.** A request without a cursor returns the first page from the newest end of the collection. A request with a cursor continues in the direction bound into that cursor; there is no separate `direction` parameter. The `limit` query parameter sets the page size. The operator MAY clamp it to an operator-defined maximum and MUST report the size it applied.

**Response.** A paginated response is a `corundum:PaginatedResponse`:

```json
{
  "@type": "corundum:PaginatedResponse",
  "items": [],
  "pagination": {
    "nextCursor": "Zk3pQ0v8bH1xR2s9cLmT4aWnYeJ6uDqV",
    "prevCursor": "Q7tGm2KcX9rB0wNfP5hZsLd8yUaE3vjH",
    "limit": 20,
    "total": 1843
  }
}
```

- `nextCursor` (string, OPTIONAL): Continues toward older items on a reverse-chronological collection. Absent when no further items exist in that direction; its absence is the end-of-collection signal.
- `prevCursor` (string, OPTIONAL): Continues toward newer items. Present whenever `items` is non-empty, because new items may arrive at any time. A client holding a position uses the `prevCursor` from its most recent response to fetch only items that arrived since. A page that returns no newer items yields a `prevCursor` at the same position, so the client can poll with it.
- `limit` (integer, REQUIRED): The page size the operator applied.
- `total` (integer, OPTIONAL): Number of items in the collection.

**Why `total` is optional.** Computing an exact count of items in a large live collection is expensive. Some collection types can provide it cheaply: a user's timeline has a counter maintained in the operator's database, and returning the count adds negligible cost to the query. Others cannot: a federated timeline aggregating posts from thousands of followed users across dozens of operators does not have a precomputed total, and computing one would require counting all matching items in the index before returning the first page. An operator SHOULD include `total` only when it can compute it cheaply, and otherwise omits the field. Clients MUST NOT depend on `total` for navigation. When `total` is present, treat it as informational — a rough count that may not reflect very recent changes.

**Cursor errors.** The only cursor error is `INVALID_CURSOR` (`400`, `retryable: false`): the cursor does not decode, its MAC does not verify, its encoding version is no longer accepted, or it was issued for a different collection or filter. Sending the same cursor again produces the same error. The client MUST discard the cursor and begin again without one.

---

