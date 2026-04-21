## Part XVI: Inter-Operator Event Streams

### Chapter 47: Design and Motivation

The reply submission endpoint (`POST /corundum/v1/replies/submit`) handles one reply per HTTP request. At low federation volume this is adequate. At scale — a large operator where thousands of cross-operator interactions occur per second — the per-request overhead accumulates: TLS connection setup (even with session resumption), HTTP framing overhead, manifest cache lookups, and synchronous validation round-trips. The batch submission endpoint (`batchSubmission`) reduces this somewhat, but it is still request/response.

Beyond reply submission, there are events that operators currently have no efficient mechanism to exchange at all: new posts published by users that other operators' users follow, tombstones that need to propagate quickly for GDPR compliance, key rotation notifications that should invalidate caches promptly, and migration announcements. Today these are either not federated in real time, or require polling and repeated IPFS resolution.

The inter-operator event stream addresses both problems: high-throughput event delivery over a persistent connection, and a general-purpose channel for all inter-operator events beyond reply submission.

**Design choices:**

**Pull, not push.** The receiving operator initiates the stream by connecting to the sending operator's stream endpoint. This is the same model as the curation transport (Chapter 32): the receiver pulls from the sender. Pull composites better with operator autonomy — Operator B connects to Operator A when it wants events from Operator A; Operator A does not need to know in advance which operators will connect, does not need to maintain a push target list, and does not need to handle reconnect logic for failed pushes. The sender's job is to maintain an event log and serve it on demand. The receiver's job is to connect, consume, and reconnect if interrupted.

**Sequence-numbered log, not ephemeral stream.** The sender maintains a durable, monotonically increasing sequence number across all events. Events are not discarded after delivery — they are retained in the log for a configurable window (RECOMMENDED minimum: 7 days). A receiver that disconnects reconnects with `?since={last_seen_sequence}` and receives exactly the events it missed. There is no coordination state between sender and receiver: the sequence number in the request is sufficient to resume deterministically.

**NDJSON over HTTP.** One long-lived HTTP GET, chunked transfer encoding, newline-delimited JSON events. This is the simplest possible framing that supports streaming. It works over HTTP/1.1 and HTTP/2. No WebSocket upgrade negotiation, no custom framing layer, no protocol switch. A receiver that does not want to maintain a persistent connection can also poll by fetching the equivalent log page files (same format as curation log pages, Chapter 32).

**General-purpose event bus.** One stream carries all event types. A `type` field discriminates them. Receivers that only care about certain event types use the `types` filter parameter to avoid processing irrelevant events. This is simpler than maintaining separate endpoints per event type, and it ensures the stream is a complete, ordered record of inter-operator events — useful for auditing and debugging.

**Authentication at stream setup, not per-event.** The GET request that establishes the stream carries RFC 9421 authentication (Chapter 19). Once established, the stream is authenticated for its lifetime. Per-event signatures are OPTIONAL and MAY be included for additional tamper resistance (for example, if the stream passes through a TLS-terminating proxy that the receiver does not fully trust). Receivers SHOULD verify per-event signatures when present.

---

### Chapter 48: The Event Stream Endpoint

Operators that declare `capabilities.eventStream: true` in their Operator Manifest MUST expose:

```
GET /corundum/v1/events
```

The request MUST be authenticated per Chapter 19. Because the request has no body, `content-digest` is omitted from the required components (per the normative table in Chapter 19). Required components: `"@method"`, `"@target-uri"`, `"@authority"`, `"corundum-timestamp"`.

**Query parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `since` | integer | OPTIONAL | Last sequence number the receiver has successfully processed. The stream begins with the first event whose `sequence` is strictly greater than this value. If absent or `0`, the stream begins at the current head (the receiver does not receive historical events). |
| `types` | string | OPTIONAL | Comma-separated list of event type names. If present, only events whose `type` matches one of the listed values are sent. If absent, all event types are sent. |
| `filter` | string | OPTIONAL | Comma-separated list of IPNS names (base36lower). If present, only events involving one of the listed identities are sent. If absent, all events are sent regardless of identity. The `operator.key-rotated` event type is always included regardless of the `filter` parameter, because it affects all interactions with the operator. |

**Response:**

HTTP status `200 OK`. `Content-Type: application/x-ndjson`. `Transfer-Encoding: chunked` (HTTP/1.1) or HTTP/2 DATA frames. The response body is an unbounded sequence of newline-terminated JSON lines. The connection remains open until the receiver closes it or the sender encounters an unrecoverable error.

**Keepalives:** The sender MUST send a keepalive line at least every 30 seconds when no events are pending. This prevents intervening proxies and firewalls from closing idle connections:

```json
{"type":"keepalive","sequence":null,"timestamp":"2025-03-15T12:00:30Z"}
```

Receivers MUST ignore keepalive lines. Receivers MAY use the absence of keepalives (timeout > 60 seconds) as a signal that the connection has stalled and should be restarted.

**Error responses** (before the stream is established):

| HTTP Status | Meaning |
|-------------|---------|
| `401 Unauthorized` | Authentication failed. |
| `403 Forbidden` | Authenticated but this operator's federation policy does not permit event streams from this requester. |
| `404 Not Found` | Event streams not supported (`capabilities.eventStream` not true). |
| `410 Gone` | The requested `since` sequence is older than the retention window. The receiver must start from `0` or from a snapshot. |
| `429 Too Many Requests` | Too many concurrent stream connections from this operator. Retry after the `Retry-After` interval. |

---

### Chapter 49: Event Object Schemas

Every event object shares a common base, plus type-specific fields.

**Base fields (all events):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | REQUIRED | Discriminated event type (normative list below). |
| `sequence` | integer | REQUIRED | Monotonically increasing uint64, operator-wide. Strictly greater than the sequence of the preceding event. |
| `timestamp` | string | REQUIRED | ISO 8601 datetime (UTC, `Z` suffix) when the event was generated by the sending operator. |
| `operator` | string | REQUIRED | Base URL of the sending operator. Allows receivers to verify the stream source if events are forwarded or cached. |
| `signature` | object | OPTIONAL | Per-event signature (schema below). MAY be present on any event type. Receivers MUST verify it when present. |

**Per-event signature object** (when present):

| Field | Type | Description |
|-------|------|-------------|
| `algorithm` | string | Algorithm identifier (e.g., `"ed25519-v1"`). |
| `key_id` | string | Key ID from the sending operator's manifest. |
| `value` | string | Base64url-encoded (no padding) signature over the canonical JSON of the event with the `signature` field omitted. |

---

#### Event Type: `post.published`

A user on this operator published a new activity.

```json
{
  "type": "post.published",
  "sequence": 48293,
  "timestamp": "2025-03-15T12:34:56Z",
  "operator": "https://wobble.example",
  "author_ipns": "k51qzi5uqu5dlvj2baxnqndepeb86cbk3ng6bn9tx0dv7azvq7rjz47q2",
  "activity_cid": "bafyreiemxf5abjwjbikoz4mc3a3dla6ual3jsgpdr4cjr3oz3evfyavhwq",
  "activity_type": "Note",
  "signing_record_cid": "bafyreiabcdef1234567890abcdef1234567890abcdef1234567890abcdef"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `author_ipns` | string | REQUIRED | IPNS name of the author. |
| `activity_cid` | string | REQUIRED | CID of the published activity (base32lower). |
| `activity_type` | string | REQUIRED | ActivityStreams type of the activity (e.g., `"Note"`, `"Announce"`, `"Like"`). |
| `signing_record_cid` | string | REQUIRED | CID of the detached signing record. |

The receiving operator MAY fetch the activity and signing record from IPFS using these CIDs. The event is a notification that new content is available; the content itself is in IPFS.

---

#### Event Type: `post.edited`

A user edited an existing post. The original CID is immutable; an edit produces a new activity CID with a `predecessorCid` link to the prior version.

```json
{
  "type": "post.edited",
  "sequence": 48294,
  "timestamp": "2025-03-15T12:35:10Z",
  "operator": "https://wobble.example",
  "author_ipns": "k51qzi5...",
  "new_activity_cid": "bafyreinewedit...",
  "predecessor_cid": "bafyreiemxf5...",
  "signing_record_cid": "bafyreinewsig..."
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `author_ipns` | string | REQUIRED | IPNS name of the author. |
| `new_activity_cid` | string | REQUIRED | CID of the new (edited) activity. |
| `predecessor_cid` | string | REQUIRED | CID of the activity this edit replaces. |
| `signing_record_cid` | string | REQUIRED | CID of the signing record for the new activity. |

Receiving operators that have cached the predecessor CID SHOULD update their references to point to the new CID. The predecessor CID remains valid content in IPFS; it is not deleted.

---

#### Event Type: `post.tombstoned`

A user deleted a post. The tombstone is stored in IPFS; the underlying content is unpinned by this operator and SHOULD be unpinned by receivers (Chapter 39).

```json
{
  "type": "post.tombstoned",
  "sequence": 48295,
  "timestamp": "2025-03-15T12:36:00Z",
  "operator": "https://wobble.example",
  "author_ipns": "k51qzi5...",
  "activity_cid": "bafyreiemxf5...",
  "tombstone_cid": "bafyreitombstone...",
  "reason": "user-deletion"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `author_ipns` | string | REQUIRED | IPNS name of the author. |
| `activity_cid` | string | REQUIRED | CID of the deleted activity. |
| `tombstone_cid` | string | REQUIRED | CID of the tombstone object. Tombstone is a signed object in IPFS. |
| `reason` | string | REQUIRED | One of `"user-deletion"`, `"gdpr-erasure"`, `"legal-hold-release"`, `"curation-enforcement"`. |

Receiving operators MUST remove references to `activity_cid` from any reply trees or feeds they serve. For `"gdpr-erasure"` reason, operators MUST unpin `activity_cid` from their IPFS nodes (Chapter 39).

---

#### Event Type: `identity.key-rotated`

A user on this operator rotated their signing key. The user's RootManifest has been updated. Receiving operators that have cached this user's public key or RootManifest CID MUST invalidate their cache.

```json
{
  "type": "identity.key-rotated",
  "sequence": 48296,
  "timestamp": "2025-03-15T12:37:00Z",
  "operator": "https://wobble.example",
  "user_ipns": "k51qzi5...",
  "new_root_manifest_cid": "bafyreinewmanifest...",
  "new_public_key_multibase": "z6MknewKey..."
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_ipns` | string | REQUIRED | IPNS name of the user whose key rotated. |
| `new_root_manifest_cid` | string | REQUIRED | CID of the updated RootManifest. |
| `new_public_key_multibase` | string | REQUIRED | The new active public key (multibase, base58btc). |

Receiving operators MUST re-verify any cached public key for `user_ipns` against `new_public_key_multibase` before accepting further signing records attributed to this identity.

---

#### Event Type: `identity.migrated`

A user has migrated away from this operator to a new operator. This operator is no longer authoritative for this identity.

```json
{
  "type": "identity.migrated",
  "sequence": 48297,
  "timestamp": "2025-03-15T12:38:00Z",
  "operator": "https://wobble.example",
  "user_ipns": "k51qzi5...",
  "new_operator": "https://birdsite.example",
  "migration_notification_cid": "bafyreimigratenotification..."
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_ipns` | string | REQUIRED | IPNS name of the migrated user. |
| `new_operator` | string | REQUIRED | Base URL of the operator now hosting this user. |
| `migration_notification_cid` | string | REQUIRED | CID of the signed MigrationNotification in IPFS. Receivers MUST verify this object before updating their operator cache for this identity. |

Receiving operators MUST update their DID→IPNS→operator cache for `user_ipns` to point to `new_operator`. Future reply submissions for this identity should be directed to `new_operator`.

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

The event log is a durable sequence. Senders MUST retain events for at least 7 days. After the retention window, events MAY be pruned; the `410 Gone` response signals to receivers that their `since` cursor is too old.

For receivers that need to onboard a history older than the retention window — for example, a new operator federating with an established operator — the sender SHOULD provide snapshots following the same structure as curation feed snapshots (Chapter 32):

```
GET /corundum/v1/events/snapshots/index.json
GET /corundum/v1/events/snapshots/snapshot-2025-03-01.ndjson.gz
```

The snapshot `index.json` follows the same schema as the curation `index.json` (Chapter 32, index.json schema), with the `authority` field replaced by `operator`. Snapshots contain all non-pruned events up to a stated sequence number. After loading a snapshot, the receiver switches to the live stream from that sequence number forward.

Snapshots are OPTIONAL. Operators that do not provide snapshots return `404 Not Found` for the snapshots index. Receivers MUST handle the absence of snapshots gracefully.

---

### Chapter 51: Adding the Event Stream to the Manifest

The `eventStream` capability and the event stream endpoint are added to the normative inter-operator endpoint table (Chapter 20):

| Method | Path | Capability gate | Auth required | Status |
|--------|------|-----------------|---------------|--------|
| `GET` | `/.well-known/corundum-operator` | none | No | MVP |
| `POST` | `/corundum/v1/replies/submit` | `replies: true` | Yes | MVP |
| `POST` | `/corundum/v1/replies/batch` | `batchSubmission: true` | Yes | Post-MVP |
| `POST` | `/corundum/v1/migration/notify` | `migration: true` | Yes | Post-MVP |
| `GET` | `/corundum/v1/events` | `eventStream: true` | Yes | Post-MVP |
| `GET` | `/corundum/v1/events/snapshots/index.json` | `eventStream: true` | Yes | Post-MVP (optional) |

The `eventStream` capability in the Operator Manifest:

```json
"capabilities": {
  "replies": true,
  "eventStream": true,
  "eventStreamRetentionDays": 30
}
```

`eventStreamRetentionDays` (integer, OPTIONAL): How many days of event history the operator retains. Receivers use this to plan reconnection windows. If absent, receivers SHOULD assume the minimum (7 days).

---

### Chapter 52: Relationship to Client-Facing Event Streams

Chapter 36 (`11-event-streams.md`) specifies real-time event streams between operators and their own clients (WebSocket/SSE). The inter-operator event stream specified here is distinct:

| Dimension | Client event stream (Ch 36) | Inter-operator event stream (Ch 47–51) |
|-----------|-----------------------------|----------------------------------------|
| Participants | Operator ↔ its own users' apps | Operator A ↔ Operator B |
| Direction | Server push to client | Pull by receiver (persistent GET) |
| Protocol | WebSocket or SSE | HTTP chunked NDJSON |
| Auth | OAuth bearer token | RFC 9421 HTTP Message Signature |
| Content | Timeline updates, notifications | Published posts, tombstones, key rotations, migrations |
| Retention | Ephemeral (no replay) | Durable log, sequence-resumable |

A receiving operator typically maps incoming inter-operator events to its own clients' event streams: a `post.published` event from a followed user on Operator A triggers a `status.update` push to Operator B's clients who follow that user.

---

