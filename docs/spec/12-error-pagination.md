## Part XII: Error Handling and Pagination

### Chapter 37: The Error Envelope

A consistent error format allows any client — whether an operator, a user client, or a monitoring system — to handle errors programmatically without parsing free-form error messages. The design follows RFC 9457 (Problem Details for HTTP APIs) in spirit: errors carry structured machine-readable data alongside a human-readable explanation.

All Corundum API endpoints return errors in this envelope:

```json
{
  "@type": "corundum:Error",
  "code": "REPLY_REJECTED",
  "message": "Reply rejected: author is on the target user's block list",
  "httpStatus": 403,
  "retryable": false,
  "details": {
    "reason": "blocked-user",
    "blockedIdentity": "ipns://k51qzi5uqu5dj4nl2xvwya5k4y6a4xy9jh0jrh5e5c5w0n9i7r3i4j8fmq4gh"
  }
}
```

**`code`** is a stable machine-readable string. Operators and clients branch on this field. It never changes for a given error condition; the human-readable `message` may be updated for clarity without breaking clients.

**`message`** is a short English description for developers and logs. It is not suitable for display to end users (user-facing messages require localization and tone appropriate to the application). The message explains what happened in enough detail to understand the error without consulting documentation.

**`httpStatus`** duplicates the HTTP response status code in the body. This is redundant but useful: some proxy and logging infrastructure strips or loses HTTP status codes. Having the status in the body means the error is recoverable from a response body alone.

**`retryable`** is a boolean that tells the client whether repeating the request (with the same parameters) might succeed. `true` means the error is transient — the target was temporarily unreachable, rate limits will expire, a resource is temporarily locked. `false` means the error is permanent given the current request — the identity doesn't exist, the cursor is expired, the algorithm is rejected. A `retryable: false` error should not be retried without changing the request; a `retryable: true` error should be retried with backoff.

**`details`** is an object with structured error-specific fields. Its schema is specified per error code. Common `details` fields:
- `reason`: A sub-code providing finer-grained information within the error code. For `REPLY_REJECTED`, the reason might be `blocked-user`, `blocked-operator`, `policy-violation`, `curation-match`, or `rate-limited`.
- `retryAfter`: An ISO 8601 timestamp (for rate-limit errors) indicating when the request can be retried.
- `missingField`: The specific field that failed validation (for `INVALID_REQUEST` errors).
- `requiredAlgorithm`: The algorithm the receiver requires (for `ALGORITHM_REJECTED` errors).

**HTTP status code conventions.** Corundum follows standard HTTP semantics:
- `400 Bad Request` — The request is syntactically or semantically invalid; `retryable: false`.
- `401 Unauthorized` — The request lacks valid authentication; `retryable: false` until credentials are fixed.
- `403 Forbidden` — The request is authenticated but not authorized for this action (blocked user, policy violation); `retryable: false`.
- `404 Not Found` — The resource doesn't exist; `retryable: false`.
- `410 Gone` — The resource existed but has been deleted (tombstoned content); `retryable: false`.
- `429 Too Many Requests` — Rate limit exceeded; `retryable: true` with `retryAfter` in `details`.
- `500 Internal Server Error` — Server fault; `retryable: true` with backoff.
- `503 Service Unavailable` — The server is temporarily down; `retryable: true` with backoff.

**Error codes by namespace:**

- Identity: `IDENTITY_NOT_FOUND`, `DID_RESOLUTION_FAILED`, `HANDLE_VERIFICATION_FAILED`
- Curation: `CURATION_AUTHORITY_INVALID`, `HASH_TYPE_UNSUPPORTED`, `CURATION_EXPIRED`
- Reply: `REPLY_REJECTED`, `BLOCKED_USER`, `BLOCKED_OPERATOR`, `CONTENT_HASH_MISMATCH`
- Pagination: `INVALID_CURSOR`, `EXPIRED_CURSOR`, `CURSOR_VERSION_MISMATCH`
- Auth: `SIGNATURE_INVALID`, `KEY_NOT_FOUND`, `ALGORITHM_REJECTED`
- Media: `CHUNK_MISSING`, `MANIFEST_INVALID`, `UPLOAD_SESSION_EXPIRED`

### Chapter 38: Pagination

**Why cursor-based, not offset-based.** The familiar offset pagination pattern — `?page=3&size=20` — works for static datasets but fails for live timelines. A timeline grows continuously: new posts appear at the top, and older posts shift down in the offset ordering. By the time a client requests "page 3," the 40 items that were previously on pages 1 and 2 may have grown to 43 items as three new posts arrived. The items that the client thinks are at offsets 40–59 are now at offsets 43–62. The client either sees three duplicate items (items it already fetched are now on page 3 as well) or silently skips three items (it fetched what was pages 1 and 2, but the first three items of what is now page 2 were not on the page 1 it fetched). Both outcomes are wrong, and neither is detectable by the client.

Cursors encode a stable position in the collection: "give me the 20 items after this specific position in the ordering." The position doesn't change as new items are added before or after it. If the client is at position P and requests the next page, it gets the items following P regardless of how many new items arrived after the client's previous request. This is the fundamental guarantee that makes cursor pagination correct for live timelines.

**How cursors work internally.** Clients treat cursors as opaque strings and must not attempt to parse or construct them. Internally, a cursor encodes the sort key position in the collection (for a timeline ordered by epoch index and sequence number, that is an epoch index and sequence number), a version field identifying the cursor encoding format, and an expiry time after which the operator considers the cursor stale. The operator base64url-encodes this structure, and may optionally encrypt it to prevent clients from reverse-engineering the internals. The opacity is a deliberate contract: the operator can change the internal cursor encoding (say, when the underlying timeline index structure changes) as long as it continues to honor cursors it has already issued within their TTL. Clients that pass cursors verbatim are insulated from these changes.

**Bidirectional pagination.** Every paginated response includes both a `nextCursor` (for forward pagination, toward older items on a reverse-chronological timeline) and a `prevCursor` (for backward pagination, toward newer items). The `direction` query parameter defaults to forward. When a client has been holding a position in a timeline and wants to catch up on new posts without re-fetching from the beginning, it uses the `prevCursor` from its most recent response — that cursor's position is just after the newest item the client has seen, so paginating backward from there returns only posts that arrived after the client's last fetch.

**Cursor expiry.** Cursors are not indefinitely valid because maintaining position state has a cost: at minimum, the operator needs to be able to interpret the cursor's encoded position against the current collection structure. A typical TTL is 24 to 48 hours. An expired cursor results in error code `EXPIRED_CURSOR`. The client's recovery path is to start a new pagination session without a cursor, which returns the most-recent end of the collection. There is no way to resume from an expired position without potentially missing some items; this is a known and accepted tradeoff. Cursors are for browsing sessions, not long-term bookmarks.

The full `corundum:PaginatedResponse` envelope:

```json
{
  "@type": "corundum:PaginatedResponse",
  "items": [],
  "pagination": {
    "cursor": "eyJlcG9jaCI6MTIzLCJzZXEiOjQ1NiwidmVyIjoxfQ",
    "nextCursor": "eyJlcG9jaCI6MTIzLCJzZXEiOjQzNiwidmVyIjoxfQ",
    "prevCursor": "eyJlcG9jaCI6MTIzLCJzZXEiOjQ3NiwidmVyIjoxfQ",
    "hasMore": true,
    "total": null
  },
  "limit": 20
}
```

**Why `total` is optional.** Computing an exact count of items in a large live collection is expensive. Some collection types can provide it cheaply: a user's timeline has a counter maintained in the operator's database, and returning the count adds negligible cost to the query. Others cannot: a federated timeline aggregating posts from thousands of followed users across dozens of operators does not have a precomputed total, and computing one would require counting all matching items in the index before returning the first page. Clients must not depend on `total` for navigation logic. Use `hasMore` to know whether more items follow the current page, and use cursors to navigate to them. When `total` is present, treat it as informational — a rough count that may not reflect very recent changes.

**Pagination error codes.** Three error codes distinguish cursor failures, each with `retryable: false`:

- `INVALID_CURSOR`: The cursor is malformed — not valid base64url, not parseable after decoding, or structurally corrupt. The client sent something that was never a valid cursor from this operator.
- `EXPIRED_CURSOR`: The cursor was well-formed and valid when issued but has exceeded its TTL. The encoded expiry time is in the past. Start a new pagination session.
- `CURSOR_VERSION_MISMATCH`: The cursor was well-formed and not expired, but uses an internal encoding version the operator no longer supports. This occurs after a major operator upgrade that changes the cursor format and allows old cursors to expire naturally. Start a new pagination session.

All three are non-retryable: sending the same cursor again will produce the same error. The client must discard the cursor and begin again from the collection's current position.

---

