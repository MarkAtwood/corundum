## Part XV: Inter-Operator Event Streams

### Chapter 47: Design and Motivation

The reply submission endpoint (`POST /corundum/v1/replies/submit`) handles one reply per HTTP request. At low federation volume this is adequate. At scale — a large operator where thousands of cross-operator interactions occur per second — the per-request overhead accumulates: TLS connection setup (even with session resumption), HTTP framing overhead, manifest cache lookups, and synchronous validation round-trips. The batch submission endpoint (`batchSubmission`) reduces this somewhat, but it is still request/response.

Beyond reply submission, there are events that operators currently have no efficient mechanism to exchange at all: new posts published by users that other operators' users follow, `Delete` activities that should propagate quickly, and changes to users' DID documents or the operator's own keys that should invalidate caches promptly. Today these are either not federated in real time, or require polling and repeated IPFS resolution.

The inter-operator event stream addresses both problems: high-throughput event delivery over a persistent connection, and a general-purpose channel for all inter-operator events beyond reply submission.

**Design choices:**

**Pull, not push.** The receiving operator initiates the stream by connecting to the sending operator's stream endpoint. This is the same model as the curation transport (Chapter 32): the receiver pulls from the sender. Pull composes better with operator autonomy — Operator B connects to Operator A when it wants events from Operator A; Operator A does not need to know in advance which operators will connect, does not need to maintain a push target list, and does not need to handle reconnect logic for failed pushes. The sender's job is to maintain an event log and serve it on demand. The receiver's job is to connect, consume, and reconnect if interrupted.

**Sequence-numbered log, not ephemeral stream.** The sender maintains a durable, monotonically increasing sequence number across all events. Events are not discarded after delivery — they are retained in the log for at least 7 days (Chapter 50). A receiver that disconnects reconnects with `?since={last_processed_sequence}` and receives every event it missed, possibly with some it has already seen (Chapter 48). There is no coordination state between sender and receiver: the sequence number in the request is sufficient to resume.

**NDJSON over HTTP.** One long-lived HTTP GET, chunked transfer encoding, newline-delimited JSON events. This is the simplest possible framing that supports streaming. It works over HTTP/1.1 and HTTP/2. No WebSocket upgrade negotiation, no custom framing layer, no protocol switch. A receiver that does not want to hold a connection open can connect periodically with `since`, read until it has caught up, and close.

**General-purpose event bus.** One stream carries all event types. A `type` field discriminates them. Receivers that only care about certain event types use the `types` filter parameter to avoid processing irrelevant events. This is simpler than maintaining separate endpoints per event type, and it ensures the stream is a complete, ordered record of inter-operator events — useful for auditing and debugging.

**Events are notices, not authorities.** The GET request that establishes the stream carries RFC 9421 authentication (Chapter 19), and the response arrives over HTTPS from the sender's origin. Events are not signed. None needs to be: every event either names signed objects that the receiver fetches and verifies before acting (activities, SigningRecords, `Delete` activities), or tells the receiver to re-fetch a self-authenticating document (a DID document, the Operator Manifest). A forged or replayed event can at most make a receiver fetch something and find it does not verify. Receivers MUST NOT change any state on the strength of an event alone.

**Bounded stream lifetime.** The sender authorizes a stream when it is established. So that a revoked requester key cannot keep a stream open indefinitely, the sender MUST close each stream no later than one hour after it was established. The receiver reconnects with `since` and a fresh signature, which the sender verifies against its current copy of the requester's Operator Manifest (Chapter 19).

---

### Chapter 48: The Event Stream Endpoint

Operators that declare `capabilities.eventStream: true` in their Operator Manifest MUST expose:

```
GET /corundum/v1/events
```

The request MUST be authenticated per Chapter 19. Because the request has no body, `content-digest` is omitted from the required components (per the normative table in Chapter 19). Required components: `"@method"`, `"@target-uri"`, `"@authority"`, with the `created` and `expires` signature parameters.

**Query parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `since` | integer or `earliest` | OPTIONAL | Where the stream begins. An integer `N` is the last sequence number the receiver has processed; the stream begins with the first event whose `sequence` is greater than `N`. `earliest` begins with the oldest event the sender still retains. If absent, the stream begins at the current head: the receiver gets only events that become visible after the stream is established. |
| `types` | string | OPTIONAL | Comma-separated list of event type names. If present, only events whose `type` matches one of the listed values are sent. If absent, all event types are sent. |
| `filter` | string | OPTIONAL | Comma-separated list of DIDs. If present, only events whose `author` or `user` field is one of the listed DIDs are sent. If absent, all events are sent regardless of identity. The `operator.key-rotated` event type is always included regardless of the `filter` parameter, because it affects all interactions with the operator. |

Sequence numbers start at 1, so `since=0` asks for the whole log and fails with `410` once any event has been pruned. If `N` is greater than the current head, the sender MUST reject the request with `400`.

**Response:**

HTTP status `200 OK`. `Content-Type: application/x-ndjson`. `Transfer-Encoding: chunked` (HTTP/1.1) or HTTP/2 DATA frames. The response body is a sequence of newline-terminated JSON lines, in increasing `sequence` order. The connection remains open until the receiver closes it, the stream reaches its lifetime limit (Chapter 47), or the sender encounters an unrecoverable error.

**Visibility after commit.** Sequence numbers need not be contiguous: a sender that assigns numbers to concurrent transactions may leave a number unused when a transaction aborts. But a receiver resumes from the highest sequence it has seen, so it would skip any event that commits after a higher-numbered one has been sent. The sender MUST NOT send an event, or report a head that includes it, until no event with a lower sequence number can still commit.

**At-least-once delivery.** A receiver can see an event more than once: after reconnecting with an older `since`, or where a snapshot and the live stream overlap (Chapter 50). Receivers MUST process events idempotently, identifying an event by its `operator` and `sequence`. A receiver SHOULD record a sequence number as processed only after it has finished acting on that event.

**Filtered streams.** With `types` or `filter`, the receiver sees only some sequence numbers. A gap between consecutive sequence numbers never indicates a lost event; ordering and visibility guarantee that every matching event is sent.

**Keepalives:** The sender MUST send a keepalive line at least every 30 seconds when no events are pending. This prevents intervening proxies and firewalls from closing idle connections:

```json
{"type":"keepalive","head":48298,"timestamp":"2025-03-15T12:00:30Z"}
```

A keepalive is not an event: it has no `sequence`, is not in the log, and is never replayed. `head` is the highest visible sequence number (`0` if the log is empty). It states that every event up to `head` that matches the request has been sent. A receiver MAY therefore treat `head` as processed and resume from it, which keeps a filtered stream's `since` within the retention window when no matching events occur. Receivers MAY use the absence of keepalives for more than 60 seconds as a signal that the connection has stalled and should be restarted.

**Error responses** (before the stream is established). Bodies are `corundum:Error` objects (Chapter 37).

| HTTP Status | `code` | Meaning |
|-------------|--------|---------|
| `400 Bad Request` | `INVALID_REQUEST` | Malformed parameter, or `since` is greater than the current head. |
| `401 Unauthorized` | `SIGNATURE_INVALID` or `KEY_NOT_FOUND` | Authentication failed. |
| `403 Forbidden` | (no body) | Authenticated, but this operator's federation policy does not permit event streams from this requester. |
| `404 Not Found` | (no body) | Event streams not supported (`capabilities.eventStream` not true). |
| `410 Gone` | `RESUME_BUFFER_EXHAUSTED` | Events after `since` have been pruned. `details.earliestSequence` gives the oldest retained sequence. The receiver either loads a snapshot (Chapter 50) or reconnects with `since=earliest`, accepting that it has missed events. |
| `429 Too Many Requests` | `RATE_LIMITED` | Too many concurrent stream connections from this operator. `details.retryAfter` gives the wait in seconds. |

---

### Chapter 49: Event Object Schemas

Every event object shares a common base, plus type-specific fields. Users are named by DID and activities by their identifier (Chapter 33).

The stream carries no social-graph events. A follow or block concerns one other operator and is sent only to it (the FollowNotification and BlockNotification of Chapter 26, or a reply rejection with reason `blocked-user`). Senders MUST NOT broadcast follows or blocks on the stream.

**Base fields (all events):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | REQUIRED | Discriminated event type (normative list below). |
| `sequence` | integer | REQUIRED | uint64, operator-wide, starting at 1. Strictly greater than the sequence of the preceding event (Chapter 48). |
| `timestamp` | string | REQUIRED | ISO 8601 datetime (UTC, `Z` suffix) when the event was generated by the sending operator. |
| `operator` | string | REQUIRED | Origin of the sending operator (its manifest `id`). With `sequence`, identifies the event for deduplication. |

---

#### Event Type: `post.published`

A user on this operator published a new activity.

```json
{
  "type": "post.published",
  "sequence": 48293,
  "timestamp": "2025-03-15T12:34:56Z",
  "operator": "https://wobble.example",
  "author": "did:webvh:<SCID>:wobble.example:users:bob",
  "activity": "<identifier of the activity>",
  "activity_type": "Note",
  "signing_record_cid": "<CID of the activity's SigningRecord>"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `author` | string | REQUIRED | DID of the author. |
| `activity` | string | REQUIRED | Identifier of the published activity. |
| `activity_type` | string | REQUIRED | ActivityStreams type of the activity (e.g., `"Note"`, `"Announce"`, `"Like"`). |
| `signing_record_cid` | string | REQUIRED | CID of the activity's SigningRecord. |

Edits and deletions have their own events below. The event is a notice that new content is available; the content itself is in IPFS. A receiver MAY fetch the activity and SigningRecord, and MUST verify them (Chapter 34) and check that the activity's author is `author` before using the activity.

---

#### Event Type: `post.edited`

A user edited an existing post. The original CID is immutable; an edit produces a new activity whose `replaces` field names the prior version.

```json
{
  "type": "post.edited",
  "sequence": 48294,
  "timestamp": "2025-03-15T12:35:10Z",
  "operator": "https://wobble.example",
  "author": "did:webvh:<SCID>:wobble.example:users:bob",
  "activity": "<identifier of the new version>",
  "replaces": "<identifier of the version it replaces>",
  "signing_record_cid": "<CID of the new version's SigningRecord>"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `author` | string | REQUIRED | DID of the author. |
| `activity` | string | REQUIRED | Identifier of the new version. |
| `replaces` | string | REQUIRED | Identifier of the version it replaces. |
| `signing_record_cid` | string | REQUIRED | CID of the SigningRecord for the new version. |

The event is a notice, not an authority. A receiver MUST fetch the new version and verify it (Chapter 34), and MUST check that its `replaces` field names the version given and that it has the same author, before using it. Every version remains valid content in IPFS; nothing is deleted.

A receiver that serves a reply tree containing the replaced version MUST NOT substitute the new version in that tree. An edited reply is a new reply submission, validated from scratch by the parent post's operator (Chapter 13, Chapter 21). Outside reply trees, a receiver that displays the old version MAY show the new one instead.

---

#### Event Type: `post.deleted`

A user deleted a post by publishing a `Delete` activity (Chapter 13). This operator has unpinned the deleted content; receivers SHOULD unpin it too (Chapter 39).

```json
{
  "type": "post.deleted",
  "sequence": 48295,
  "timestamp": "2025-03-15T12:36:00Z",
  "operator": "https://wobble.example",
  "author": "did:webvh:<SCID>:wobble.example:users:bob",
  "activity": "<identifier of the deleted activity>",
  "delete_activity": "<identifier of the Delete activity>",
  "signing_record_cid": "<CID of the Delete activity's SigningRecord>"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `author` | string | REQUIRED | DID of the author. |
| `activity` | string | REQUIRED | Identifier of the deleted activity. |
| `delete_activity` | string | REQUIRED | Identifier of the `Delete` activity. |
| `signing_record_cid` | string | REQUIRED | CID of the `Delete` activity's SigningRecord. |

A receiver MUST NOT act on this event until it has fetched the `Delete` activity, verified it (Chapter 34), and checked that its `object` is `activity` and its author is the author of `activity`. Once it has, it MUST stop serving the deleted activity, MUST remove it from any reply trees or feeds it serves, and SHOULD unpin it and its SigningRecords (Chapter 39).

Only authors delete posts through this event. An operator that stops serving content for its own reasons (a curation judgment, its own policy, a legal order) does not send `post.deleted`, and its decision does not bind other operators.

---

#### Event Type: `identity.updated`

The DID document of a user on this operator has changed: a content key rotation, a move to another operator, or any other DID update (Chapter 7).

```json
{
  "type": "identity.updated",
  "sequence": 48296,
  "timestamp": "2025-03-15T12:37:00Z",
  "operator": "https://wobble.example",
  "user": "did:webvh:<SCID>:wobble.example:users:bob"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user` | string | REQUIRED | DID of the user. |

Like the MigrationNotification, this event is a hint. A receiver that holds a cached DID document for `user` SHOULD discard it and re-resolve the DID, and MUST take the content keys, IPNS name and operator endpoint from the resolved document, never from the event. A receiver that misses the event finds the change when its cached DID document expires (at most 24 hours, Chapter 7). After a move, the old operator may not send this event; the new operator's MigrationNotification and the cache limit cover that case.

---

#### Event Type: `operator.key-rotated`

This operator has rotated its own signing key. The operator's manifest has been updated. Receiving operators MUST invalidate their cached copy of this operator's manifest and re-fetch it.

```json
{
  "type": "operator.key-rotated",
  "sequence": 48298,
  "timestamp": "2025-03-15T12:39:00Z",
  "operator": "https://wobble.example",
  "new_key_id": "https://wobble.example#key-2025-06",
  "deprecated_key_id": "https://wobble.example#key-2025-01"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `new_key_id` | string | REQUIRED | Key ID of the newly active key. |
| `deprecated_key_id` | string | OPTIONAL | Key ID of the key that was deprecated by this rotation. |

This event is always delivered regardless of the `filter` parameter, because it affects all communication with this operator.

---

### Chapter 50: Retention and Snapshots

The event log is a durable sequence. Senders MUST retain events for at least 7 days. After the retention window, events MAY be pruned; the `410 Gone` response with code `RESUME_BUFFER_EXHAUSTED` signals to receivers that their `since` cursor is too old.

For receivers that need to onboard a history older than the retention window — for example, a new operator federating with an established operator — the sender SHOULD provide snapshots following the same structure as curation feed snapshots (Chapter 32):

```
GET /corundum/v1/events/snapshots/index.json
GET /corundum/v1/events/snapshots/snapshot-2025-03-01.ndjson.gz
```

The snapshot `index.json` follows the same schema as the curation `index.json` (Chapter 32, index.json schema), with the `authority` field replaced by `operator`. Snapshots contain all non-pruned events up to a stated sequence number. After loading a snapshot, the receiver connects to the live stream with `since` set to that sequence number.

Snapshots are OPTIONAL. Operators that do not provide snapshots return `404 Not Found` for the snapshots index. Receivers MUST handle the absence of snapshots gracefully.

---

### Chapter 51: Adding the Event Stream to the Manifest

The event stream endpoints are listed in the normative inter-operator endpoint table (Chapter 20), gated by the `eventStream` capability. In the Operator Manifest (Chapter 18):

```json
"capabilities": {
  "replies": true,
  "eventStream": true,
  "eventStreamRetentionDays": 30
}
```

`eventStream` (boolean, OPTIONAL): The operator exposes `GET /corundum/v1/events` (Chapter 48) and MAY expose the snapshot endpoints (Chapter 50).

`eventStreamRetentionDays` (integer, OPTIONAL): How many days of event history the operator retains. Receivers use this to plan reconnection windows. If absent, receivers SHOULD assume the minimum (7 days).

---

### Chapter 52: Relationship to Client-Facing Event Streams

Chapters 47–51 define the only event stream in the Corundum protocol. How an operator pushes updates to its own users' apps is the operator's own business, like the rest of its client/server API (Chapter 17). The reference implementation's client stream is described, non-normatively, in `docs/client-api/14-event-stream.md`.

A receiving operator typically turns verified inter-operator events into updates for its own clients: after fetching and verifying the activity named by a `post.published` event from a followed user on Operator A, Operator B pushes the new status to its clients who follow that user.

---

