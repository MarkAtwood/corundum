# Relationships

Relationship endpoints manage the social graph: follows, blocks, and mutes. In Corundum, blocks have protocol-level enforcement across operator boundaries. Mutes are a client-side filter only. This distinction matters and is described in detail below.

## Relationship Query

### GET /api/v1/accounts/relationships

Returns the authenticated user's relationship to one or more accounts. Use this endpoint to determine follow state, block state, mute state, and pending follow requests before rendering account views.

**Authentication:** Required.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id[]` | array of strings (IPNS names) | Yes | The accounts to query. Multiple values are accepted. |

**Returns:** Array of Relationship entities, in the same order as the requested `id[]` values.

**Relationship Entity Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | string (IPNS name) | The account this relationship describes |
| `following` | boolean | You are following this account |
| `followed_by` | boolean | This account follows you |
| `requested` | boolean | You have a pending follow request to this account |
| `requested_by` | boolean | This account has a pending follow request to you |
| `blocking` | boolean | You have blocked this account |
| `blocked_by` | boolean | This account has blocked you (where detectable) |
| `muting` | boolean | You have muted this account |
| `muting_notifications` | boolean | You have muted notifications from this account |
| `endorsed` | boolean | You have endorsed (featured) this account on your profile |
| `note` | string | Your personal note about this account |
| `corundum.block_enforced` | boolean | Present and `true` when you have blocked this account and protocol-level block enforcement is active |

**Errors:**

| Code | Error | Description |
|------|-------|-------------|
| 401 | `unauthorized` | No valid token provided |

---

## Follow Management

### POST /api/v1/accounts/:id/follow

Follows the specified account. If the account has `locked: true`, this creates a follow request rather than an immediate follow.

**Authentication:** Required (`write:follows` scope).

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:id` | The IPNS name of the account to follow |

**Request Body (optional, application/json or form):**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `reblogs` | boolean | `true` | Show this account's boosts in your home timeline |
| `notify` | boolean | `false` | Receive a `status` notification when this account posts |

**Returns:** Relationship entity.

**Errors:**

| Code | Error | Description |
|------|-------|-------------|
| 401 | `unauthorized` | No valid token provided |
| 403 | `insufficient_scope` | Token lacks `write:follows` scope |
| 404 | `not_found` | No account with that IPNS name is known to this operator |
| 422 | `unprocessable_entity` | Cannot follow this account (e.g. you are blocked by them) |

---

### POST /api/v1/accounts/:id/unfollow

Unfollows the specified account, or cancels a pending follow request.

**Authentication:** Required (`write:follows` scope).

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:id` | The IPNS name of the account to unfollow |

**Returns:** Relationship entity.

**Errors:**

| Code | Error | Description |
|------|-------|-------------|
| 401 | `unauthorized` | No valid token provided |
| 403 | `insufficient_scope` | Token lacks `write:follows` scope |
| 404 | `not_found` | No account with that IPNS name is known to this operator |

---

## Block Management

### POST /api/v1/accounts/:id/block

Blocks the specified account.

**Authentication:** Required (`write:blocks` scope).

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:id` | The IPNS name of the account to block |

**Returns:** Relationship entity with `blocking: true` and `corundum.block_enforced: true`.

**Corundum block enforcement behavior:**

A block in Corundum is a protocol-level action, not a client-side filter. When you block an account:

1. Your operator records the block and marks it for inter-operator enforcement.
2. When the blocked user's operator subsequently attempts to submit a reply to any of your posts, your operator rejects the submission with a `BLOCKED_USER` error at the inter-operator protocol level. The reply is not delivered.
3. Your operator performs a retroactive scan of your existing reply trees and removes any prior replies from the blocked account. These replies are no longer visible to you or to others viewing reply threads through your operator.
4. The blocked user receives a `corundum.block_enforcement` notification informing them that their submission was rejected due to a block (without identifying you as the blocker).

Unfollowing happens automatically when you block someone. If they were following you, that follow relationship is also removed.

**Errors:**

| Code | Error | Description |
|------|-------|-------------|
| 401 | `unauthorized` | No valid token provided |
| 403 | `insufficient_scope` | Token lacks `write:blocks` scope |
| 404 | `not_found` | No account with that IPNS name is known to this operator |

---

### POST /api/v1/accounts/:id/unblock

Removes a block on the specified account.

**Authentication:** Required (`write:blocks` scope).

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:id` | The IPNS name of the account to unblock |

**Returns:** Relationship entity with `blocking: false`.

**Note:** Unblocking does not retroactively restore replies that were removed during the block period.

**Errors:**

| Code | Error | Description |
|------|-------|-------------|
| 401 | `unauthorized` | No valid token provided |
| 403 | `insufficient_scope` | Token lacks `write:blocks` scope |
| 404 | `not_found` | No account with that IPNS name is known to this operator |

---

## Mute Management

### POST /api/v1/accounts/:id/mute

Mutes the specified account. A mute is a client-side filter: the muted account's content is hidden in this client, but there is no inter-operator protocol effect.

**Authentication:** Required (`write:mutes` scope).

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:id` | The IPNS name of the account to mute |

**Request Body (optional):**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `notifications` | boolean | `true` | Also mute notifications from this account |
| `duration` | integer | 0 | Mute duration in seconds. `0` means indefinite. |

**Returns:** Relationship entity with `muting: true`.

**Errors:**

| Code | Error | Description |
|------|-------|-------------|
| 401 | `unauthorized` | No valid token provided |
| 403 | `insufficient_scope` | Token lacks `write:mutes` scope |
| 404 | `not_found` | No account with that IPNS name is known to this operator |

---

### POST /api/v1/accounts/:id/unmute

Removes a mute on the specified account.

**Authentication:** Required (`write:mutes` scope).

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:id` | The IPNS name of the account to unmute |

**Returns:** Relationship entity with `muting: false`.

**Errors:**

| Code | Error | Description |
|------|-------|-------------|
| 401 | `unauthorized` | No valid token provided |
| 403 | `insufficient_scope` | Token lacks `write:mutes` scope |
| 404 | `not_found` | No account with that IPNS name is known to this operator |

---

## Block vs. Mute

These two mechanisms are intentionally different in Corundum:

**Block** is a protocol-level enforcement action:
- The blocked user's operator is notified via `BLOCKED_USER` rejection when they attempt to deliver replies to your posts.
- Prior replies from the blocked user are retroactively removed from your reply trees.
- The blocked user receives explicit feedback (a `corundum.block_enforcement` notification) that their reply was rejected. This is a transparency guarantee: rejected content is not silently dropped.
- The block is permanent and strong until explicitly removed.

**Mute** is a client-side display filter:
- The muted user can still reply to your posts; you simply do not see their content in this client.
- Their replies remain in your reply trees and are visible to other users.
- No inter-operator enforcement occurs. Their operator receives no signal.
- Mutes can be temporary (via `duration`) or indefinite.

Use block when you want the person to have no protocol-level access to your reply threads. Use mute when you want to stop seeing someone's content without affecting their ability to participate in conversations.

---

## Block and Mute Lists

### GET /api/v1/blocks

Returns all accounts the authenticated user has blocked, paginated.

**Authentication:** Required (`read:blocks` scope).

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_id` | string | — | Pagination cursor |
| `min_id` | string | — | Pagination cursor |
| `limit` | integer | 40 | Maximum number of results (max 80) |

**Returns:** Array of Account entities.

---

### GET /api/v1/mutes

Returns all accounts the authenticated user has muted, paginated.

**Authentication:** Required (`read:mutes` scope).

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_id` | string | — | Pagination cursor |
| `min_id` | string | — | Pagination cursor |
| `limit` | integer | 40 | Maximum number of results (max 80) |

**Returns:** Array of Account entities.

---

## Follow Requests (Locked Accounts)

When an account has `locked: true`, incoming follows create pending follow requests rather than immediate follows. The account owner must approve or reject each request.

### GET /api/v1/follow_requests

Returns pending incoming follow requests for the authenticated user.

**Authentication:** Required (`read:follows` scope).

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_id` | string | — | Pagination cursor |
| `min_id` | string | — | Pagination cursor |
| `limit` | integer | 40 | Maximum number of results (max 80) |

**Returns:** Array of Account entities (the accounts requesting to follow you).

---

### POST /api/v1/follow_requests/:id/authorize

Approves a pending follow request.

**Authentication:** Required (`write:follows` scope).

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:id` | The IPNS name of the account whose follow request to approve |

**Returns:** Relationship entity.

**Errors:**

| Code | Error | Description |
|------|-------|-------------|
| 401 | `unauthorized` | No valid token provided |
| 403 | `insufficient_scope` | Token lacks `write:follows` scope |
| 404 | `not_found` | No pending follow request from that account |

---

### POST /api/v1/follow_requests/:id/reject

Rejects and removes a pending follow request.

**Authentication:** Required (`write:follows` scope).

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:id` | The IPNS name of the account whose follow request to reject |

**Returns:** Relationship entity.

**Errors:**

| Code | Error | Description |
|------|-------|-------------|
| 401 | `unauthorized` | No valid token provided |
| 403 | `insufficient_scope` | Token lacks `write:follows` scope |
| 404 | `not_found` | No pending follow request from that account |
