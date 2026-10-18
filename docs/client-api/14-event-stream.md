# Event Stream

The event stream pushes real-time updates from an operator to its own users' client applications: new statuses on the home timeline, accepted replies in a thread the client is showing, notifications, and curation labels. This is part of the reference implementation's client/server API; it is not part of the Corundum protocol. The only event stream the protocol defines is the inter-operator stream (spec Chapters 47–52, `docs/spec/15-interop-streams.md`), which is a different endpoint with different authentication and semantics.

Accounts are identified by DID. Statuses are identified by their activity id (the activity's CID). The operator verifies remote content (spec Chapter 34) before pushing it to a client; the stream carries nothing the client could not also fetch through the HTTP endpoints.

**Why Server-Sent Events.** The stream uses SSE (the WHATWG HTML `text/event-stream` format) over a single long-lived HTTP response. It works through ordinary HTTP/1.1 and HTTP/2 proxies and load balancers with no special configuration, and the browser `EventSource` API handles reconnection and resumption itself. WebSocket was considered and rejected: its advantage is changing subscriptions on an open connection, and subscriptions change rarely enough that reconnecting with new topics is cheaper than supporting a second protocol. The Mastodon shim (`13-mastodon-shim.md`) still offers WebSocket to Mastodon clients by translating this stream.

## Endpoints

### GET /api/corundum/v1/streaming

Opens an event stream for the authenticated user.

**Authentication:** Required (`read` scope). The token is sent in the `Authorization` header, or as the `access_token` query parameter for clients that use `EventSource`, which cannot set headers.

**Request Headers:**

| Header | Description |
|--------|-------------|
| `Last-Event-ID` | The `id` of the last event the client received. `EventSource` sends this automatically when it reconnects. If present, the operator first replays every buffered event with a greater `id` that matches the requested topics, then continues live. If absent, the stream starts with new events only. |

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `topics` | string | `home,notifications` | Comma-separated list of topics (below). To change topics, the client closes the stream and opens a new one, passing `Last-Event-ID` so nothing is missed. |

**Topics:**

| Topic | Events |
|-------|--------|
| `home` | `timeline.entry.created`, `timeline.entry.edited`, `timeline.entry.deleted` for statuses on the user's home timeline. |
| `account:<DID>` | The same three events for statuses by the account with that DID. |
| `thread:<activity id>` | `reply.accepted` for replies accepted into the reply tree of that status. |
| `notifications` | `notification` for the authenticated user's notifications. |
| `curation:<authority URL>` | `curation.entry.created` for new entries from a curation authority the user is subscribed to (`11-curation.md`). |

Follows and blocks reach a client only as `notification` events about the authenticated user. The stream never reports other users' follows or blocks.

**Returns:** `200 OK` with `Content-Type: text/event-stream`. Each event has an `id`, an `event` type, and a JSON `data` payload naming the topic it was delivered for:

```
id: 1043
event: timeline.entry.created
data: {"topic":"home","status":{ ...Status entity... }}

id: 1047
event: timeline.entry.deleted
data: {"topic":"home","id":"<activity id of the deleted status>","delete_activity":"<activity id of the Delete activity>"}
```

| Event | `data` fields |
|-------|---------------|
| `timeline.entry.created` | `status`: Status entity. |
| `timeline.entry.edited` | `status`: Status entity for the new version; `replaces`: activity id of the version it replaces. |
| `timeline.entry.deleted` | `id`: activity id of the deleted status; `delete_activity`: activity id of the `Delete` activity. |
| `reply.accepted` | `status`: Status entity for the reply; `in_reply_to`: activity id of the parent. |
| `notification` | `notification`: Notification entity. |
| `curation.entry.created` | `label`: CurationLabel entity. |
| `heartbeat` | Empty object. |

**Event ids.** An event's `id` is an integer from a sequence scoped to the authenticated user, increasing across all topics. Because a stream carries only the requested topics, ids are not contiguous; a gap does not mean an event was lost. The operator does not send an event until every event with a lower id that could still be delivered has been committed, so resuming from `Last-Event-ID` never skips an event that was committed late.

**Heartbeats.** The operator sends a `heartbeat` event at least every 30 seconds. Its `id` is the user's current highest committed id, which tells the client that every matching event up to that id has been sent. `EventSource` records it as the last event id, so a client on a quiet topic resumes from a recent point instead of from an old one that may have left the buffer. A client that receives no event for 60 seconds should assume the connection has silently died (for example, a NAT gateway evicted its state) and reconnect. `EventSource` does not do this on its own; the client closes and reopens it.

**Delivery.** The operator keeps a resume buffer of at least one hour of events per user. Delivery is at-least-once: a replay after reconnecting may repeat an event the client already processed. Clients should apply events idempotently, keyed by `id`, or by the status or notification id the event carries.

**Errors:**

| Code | Error | Description |
|------|-------|-------------|
| 401 | `UNAUTHORIZED` | No valid token provided |
| 403 | `INSUFFICIENT_SCOPE` | Token lacks `read` scope |
| 410 | `RESUME_BUFFER_EXHAUSTED` | `Last-Event-ID` is older than the resume buffer. The client refetches the affected timelines and notifications through the HTTP endpoints (`04-timelines.md`, `06-notifications.md`), then opens a new stream without `Last-Event-ID`. |
| 422 | `VALIDATION_FAILED` | A topic is malformed, or names an authority the user is not subscribed to |
| 429 | `RATE_LIMITED` | Too many open streams for this user. Check `Retry-After` header. |
