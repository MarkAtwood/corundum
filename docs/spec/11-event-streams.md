## Part XI: Event Streams

### Chapter 36: Real-Time Notifications

Corundum defines a real-time event system for pushing updates between operators and to clients. Two transport mechanisms are supported:

**WebSocket vs. SSE tradeoffs.** WebSocket provides a full-duplex, persistent TCP connection. Both sides can send messages at any time. For inter-operator event streaming, this matters: the subscribing operator needs to send subscription management messages (which events to subscribe to, filter updates, acknowledgments) and the publishing operator needs to send events. With WebSocket, this is a single bidirectional connection. The operational cost is that WebSocket requires careful configuration in HTTP reverse proxies and load balancers — some proxies time out idle WebSocket connections, some require specific headers to be forwarded, and some load balancers break connection persistence in ways that are difficult to debug. Operators deploying WebSocket event streams must configure their infrastructure explicitly for it.

Server-Sent Events (SSE) is unidirectional: the server sends events, the client only receives. SSE is built on a long-lived HTTP response and works through any HTTP/1.1 or HTTP/2 infrastructure without special configuration — load balancers, proxies, and CDNs all understand HTTP responses and pass them through transparently. The limitation is that the client cannot send messages on the same connection. For inter-operator streaming where the subscriber needs to update filters or acknowledge events, SSE requires a separate HTTP connection for the subscriber-to-server channel, which adds round-trip latency compared to WebSocket's single bidirectional stream.

The practical guidance: WebSocket is preferred for inter-operator streaming between servers (where both sides are programmable and infrastructure can be configured) and for rich client applications that need bidirectional subscription management. SSE is preferred for simple read-only cases — a client that only needs to receive timeline updates without sending filter changes — and in environments where WebSocket infrastructure configuration is not practical.

**Subscription management.** A connection begins with a subscription request that identifies what the subscriber wants to receive. Example subscription messages include: subscribe to a specific user's timeline (receive events whenever that user posts, boosts, or deletes); subscribe to a specific reply thread (receive events whenever a new reply is accepted into that thread); subscribe to a curation feed (receive events whenever a new curation entry is published for any watched content hash).

Subscriptions can carry filters that reduce the event volume delivered. A subscriber can specify: only deliver `timeline.entry.created` events (not `follow.created` or `block.created`); only deliver events for content matching curation categories `legal/*` or `safety/*`; only deliver events for users in a specific list. Filters are specified in the subscription message and can be updated on an existing WebSocket connection without disconnecting and reconnecting.

```json
{
  "type": "subscribe",
  "topics": [
    {
      "type": "user.timeline",
      "ipns": "k51qzi5uqu5dj4nl2xvwya5k4y6a4xy9jh0jrh5e5c5w0n9i7r3i4j8fmq4gh",
      "eventTypes": ["timeline.entry.created", "timeline.entry.deleted"]
    },
    {
      "type": "curation.feed",
      "authority": "https://csam-authority.example",
      "categories": ["legal/csam-detected"]
    }
  ]
}
```

**Sequence numbers and gap detection.** Every event in a stream carries a `sequence` number that is monotonically increasing per stream. The sequence number is the primary mechanism for detecting dropped events.

When a client reconnects after a disconnect — whether brief (a transient network blip) or extended (a server restart) — it specifies the last sequence number it successfully received via a `lastSequence` query parameter:

```
GET /corundum/v1/events?lastSequence=1039&topics=...
```

If the first event the client receives has `sequence: 1042` and the client's last was `1039`, the client knows it missed events `1040` and `1041`. It can fetch those missed events from the resume buffer: the operator maintains a buffer of recent events (at least 1 hour by default, configurable) accessible via a catch-up endpoint:

```
GET /corundum/v1/events/catchup?since=1039&until=1042&topics=...
```

The catchup endpoint returns the buffered events in sequence order. The client processes them, then reconnects to the live stream at the current sequence. This ensures no events are silently lost during brief disconnections.

**Resume buffer exhaustion.** If a client was offline for longer than the buffer window — more than an hour by default — the events it missed have rolled out of the buffer. In this case, the catch-up endpoint returns a `RESUME_BUFFER_EXHAUSTED` error with the earliest available sequence number in the current buffer.

The client must then fall back to the HTTP polling API to catch up. It fetches the timeline, reply trees, or curation feed via the paginated HTTP endpoints until it has retrieved everything up to the current state. Once it has caught up to the current sequence number (available from the operator's stream status endpoint), it can reconnect to the event stream and resume real-time delivery. This fallback ensures that extended disconnections degrade gracefully to polling rather than causing permanent data loss.

**The heartbeat mechanism.** Operators send a `system.heartbeat` event every 30 seconds by default (the interval is configurable and declared in the operator manifest's event stream configuration).

```json
{
  "type": "system.heartbeat",
  "sequence": 1045,
  "timestamp": "2025-03-15T14:23:41Z",
  "data": {
    "serverTime": "2025-03-15T14:23:41Z",
    "nextHeartbeat": 30
  }
}
```

If a client does not receive a heartbeat for twice the expected interval (i.e., 60 seconds with the default 30-second interval), it should assume the connection has silently died and reconnect. This is important because TCP connections can fail in ways that neither side detects. A common scenario: the connection passes through a NAT gateway that evicts idle connection state after a timeout. From the server's perspective, the connection is still open; from the client's perspective, the connection appears to be open; but any data sent by the server is silently dropped by the NAT because the gateway has forgotten the mapping. Without heartbeats, both sides can sit in apparent normalcy while events are silently lost indefinitely.

The heartbeat sequence number is a regular sequence number in the stream, which means it also serves gap detection: if a client receives heartbeat at sequence 1045 after previously receiving an event at sequence 1039, it knows it missed events 1040–1044 even if none of those events triggered a non-heartbeat event type it was subscribed to.

Events use a standard envelope:

- **type**: Event type (e.g., `timeline.entry.created`, `reply.submitted`, `reply.accepted`, `follow.created`, `block.created`, `system.heartbeat`)
- **sequence**: Monotonically increasing sequence number for gap detection
- **timestamp**: When the event occurred
- **data**: Event-specific payload

The event stream supports:

- **Subscription management**: Subscribe to specific topics — a user's timeline, a reply thread, a curation feed.
- **Gap detection**: If a client reconnects and the server-side sequence has advanced past the last sequence the client saw, the client knows it missed events.
- **Resumption**: Operators maintain a resume buffer (configurable, typically 1 hour). Clients reconnect with a `lastSequence` parameter to replay missed events.
- **Heartbeats**: Regular `system.heartbeat` events keep connections alive and allow clients to detect silent disconnections.

---

