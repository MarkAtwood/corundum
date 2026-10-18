# Relationships

Relationship endpoints manage the social graph: follows, blocks, and mutes. Account `:id` path parameters are DIDs, percent-encoded as one path segment (`00-design.md`, Identifiers).

The user's following list, block list, and mute list are stored encrypted in their RootManifest (spec Chapter 25), so they move with the user to a new operator. Follow lists are private by default; a user may choose to publish theirs.

For a self-custody account (`10-identity-migration.md`, Key custody), every endpoint below that changes one of these lists returns `202 Accepted` with a `pending_root_manifest` for the client to sign and commit, instead of the Relationship entity. The change takes effect when the signed RootManifest is committed.

## Relationship Query

### GET /api/corundum/v1/accounts/relationships

Returns the authenticated user's relationship to one or more accounts. Use this endpoint to determine follow state, block state, mute state, and pending follow requests before rendering account views.

**Authentication:** Required (`read:follows` scope).

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id[]` | array of strings (DIDs) | Yes | The accounts to query. Multiple values are accepted. |

**Returns:** Array of Relationship entities, in the same order as the requested `id[]` values.

**Relationship Entity Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | string (DID) | The account this relationship describes |
| `following` | boolean | You are following this account |
| `followed_by` | boolean | This account follows you |
| `requested` | boolean | You have a pending follow request to this account |
| `requested_by` | boolean | This account has a pending follow request to you |
| `blocking` | boolean | You have blocked this account |
| `blocked_by` | boolean | This account has blocked you (where detectable, for example after a `blocked-user` reply rejection) |
| `muting` | boolean | You have muted this account |
| `muting_notifications` | boolean | You have muted notifications from this account |
| `endorsed` | boolean | You have endorsed (featured) this account on your profile |
| `note` | string | Your personal note about this account |

**Errors:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 401 | `UNAUTHORIZED` | No valid token provided |
| 403 | `INSUFFICIENT_SCOPE` | Token lacks `read:follows` scope |

---

## Follow Management

### POST /api/corundum/v1/accounts/:id/follow

Follows the specified account. If the account has `locked: true`, this creates a follow request rather than an immediate follow.

Your operator adds the account to your encrypted following list and always sends a FollowNotification to the followed account's operator (spec Chapter 26), which keeps that operator's followers cache current and lets it apply followers-only reply policies.

**Authentication:** Required (`write:follows` scope).

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:id` | The DID of the account to follow |

**Request Body (optional, application/json or form):**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `reblogs` | boolean | `true` | Show this account's boosts in your home timeline |
| `notify` | boolean | `false` | Receive a `status` notification when this account posts |

**Returns:** Relationship entity (`202` with `pending_root_manifest` for self-custody accounts).

**Errors:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 401 | `UNAUTHORIZED` | No valid token provided |
| 403 | `INSUFFICIENT_SCOPE` | Token lacks `write:follows` scope |
| 404 | `NOT_FOUND` | No account with that DID could be resolved |
| 502 | `DID_RESOLUTION_FAILED` | The account's DID document could not be fetched |

---

### POST /api/corundum/v1/accounts/:id/unfollow

Unfollows the specified account, or cancels a pending follow request.

**Authentication:** Required (`write:follows` scope).

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:id` | The DID of the account to unfollow |

**Returns:** Relationship entity (`202` with `pending_root_manifest` for self-custody accounts).

**Errors:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 401 | `UNAUTHORIZED` | No valid token provided |
| 403 | `INSUFFICIENT_SCOPE` | Token lacks `write:follows` scope |
| 404 | `NOT_FOUND` | No account with that DID is known to this operator |

---

## Block Management

### POST /api/corundum/v1/accounts/:id/block

Blocks the specified account.

**Authentication:** Required (`write:blocks` scope).

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:id` | The DID of the account to block |

**Returns:** Relationship entity with `blocking: true` (`202` with `pending_root_manifest` for self-custody accounts).

**What a block does:**

A block keeps the blocked account out of your conversations. It is enforced by your own operator, which is the gatekeeper for the reply trees of your posts:

1. Your operator adds the account's DID to your block list, which is stored encrypted in your RootManifest.
2. When the blocked user's operator submits a reply to any of your posts, your operator rejects it with `REPLY_REJECTED` and reason `blocked-user` (spec Chapter 21). The reply never enters your reply tree, so it is absent for every reader, on every operator.
3. Your operator removes the blocked account's earlier replies from the reply trees of your posts.
4. The blocked user's operator learns of the block from the rejection; Corundum does not pretend a block can be hidden from the person blocked. The blocked user receives a `corundum.reply_rejected` notification the next time they try to reply to you (`06-notifications.md`).

Blocking also removes any follow in either direction.

**Errors:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 401 | `UNAUTHORIZED` | No valid token provided |
| 403 | `INSUFFICIENT_SCOPE` | Token lacks `write:blocks` scope |
| 404 | `NOT_FOUND` | No account with that DID could be resolved |

---

### POST /api/corundum/v1/accounts/:id/unblock

Removes a block on the specified account.

**Authentication:** Required (`write:blocks` scope).

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:id` | The DID of the account to unblock |

**Returns:** Relationship entity with `blocking: false` (`202` with `pending_root_manifest` for self-custody accounts).

**Note:** Unblocking does not restore replies that were removed during the block period.

**Errors:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 401 | `UNAUTHORIZED` | No valid token provided |
| 403 | `INSUFFICIENT_SCOPE` | Token lacks `write:blocks` scope |
| 404 | `NOT_FOUND` | No account with that DID is known to this operator |

---

## Mute Management

### POST /api/corundum/v1/accounts/:id/mute

Mutes the specified account. A mute is a display filter: your operator and your clients hide the muted account's content from you. The mute list is stored encrypted in your RootManifest, so it follows you across clients and operators. It has no inter-operator effect.

**Authentication:** Required (`write:mutes` scope).

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:id` | The DID of the account to mute |

**Request Body (optional):**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `notifications` | boolean | `true` | Also mute notifications from this account |
| `duration` | integer | 0 | Mute duration in seconds. `0` means indefinite. |

**Returns:** Relationship entity with `muting: true` (`202` with `pending_root_manifest` for self-custody accounts).

**Errors:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 401 | `UNAUTHORIZED` | No valid token provided |
| 403 | `INSUFFICIENT_SCOPE` | Token lacks `write:mutes` scope |
| 404 | `NOT_FOUND` | No account with that DID could be resolved |

---

### POST /api/corundum/v1/accounts/:id/unmute

Removes a mute on the specified account.

**Authentication:** Required (`write:mutes` scope).

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:id` | The DID of the account to unmute |

**Returns:** Relationship entity with `muting: false` (`202` with `pending_root_manifest` for self-custody accounts).

**Errors:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 401 | `UNAUTHORIZED` | No valid token provided |
| 403 | `INSUFFICIENT_SCOPE` | Token lacks `write:mutes` scope |
| 404 | `NOT_FOUND` | No account with that DID is known to this operator |

---

## Block vs. Mute

These two mechanisms are intentionally different:

**Block** keeps someone out of your conversations:
- Your operator rejects their reply submissions to your posts with `REPLY_REJECTED` / `blocked-user`, so their replies are absent for every reader.
- Their earlier replies are removed from your reply trees.
- Their operator learns of the block from the rejection, and they receive a `corundum.reply_rejected` notification. Rejected content is not silently dropped.
- The block lasts until you remove it.

**Mute** stops you seeing someone:
- The muted user can still reply to your posts; you do not see their content.
- Their replies remain in your reply trees and are visible to other users.
- No inter-operator signal is sent. Their operator learns nothing.
- Mutes can be temporary (via `duration`) or indefinite.

Use block when you want the person to have no access to your reply threads. Use mute when you want to stop seeing someone's content without affecting their ability to participate in conversations.

---

## Block and Mute Lists

### GET /api/corundum/v1/blocks

Returns all accounts the authenticated user has blocked.

**Authentication:** Required (`read:blocks` scope).

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cursor` | string | — | Opaque pagination cursor (`00-design.md`, Pagination) |
| `limit` | integer | 40 | Maximum number of results (max 80) |

**Returns:** PaginatedResponse of Account entities.

---

### GET /api/corundum/v1/mutes

Returns all accounts the authenticated user has muted.

**Authentication:** Required (`read:mutes` scope).

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cursor` | string | — | Opaque pagination cursor (`00-design.md`, Pagination) |
| `limit` | integer | 40 | Maximum number of results (max 80) |

**Returns:** PaginatedResponse of Account entities.

---

## Follow Requests (Locked Accounts)

When an account has `locked: true`, incoming follows create pending follow requests rather than immediate follows. The account owner must approve or reject each request. Locking controls who appears as a follower; it does not restrict who can read the account's posts, which are always public.

### GET /api/corundum/v1/follow_requests

Returns pending incoming follow requests for the authenticated user.

**Authentication:** Required (`read:follows` scope).

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cursor` | string | — | Opaque pagination cursor (`00-design.md`, Pagination) |
| `limit` | integer | 40 | Maximum number of results (max 80) |

**Returns:** PaginatedResponse of Account entities (the accounts requesting to follow you).

---

### POST /api/corundum/v1/follow_requests/:id/authorize

Approves a pending follow request.

**Authentication:** Required (`write:follows` scope).

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:id` | The DID of the account whose follow request to approve |

**Returns:** Relationship entity.

**Errors:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 401 | `UNAUTHORIZED` | No valid token provided |
| 403 | `INSUFFICIENT_SCOPE` | Token lacks `write:follows` scope |
| 404 | `NOT_FOUND` | No pending follow request from that account |

---

### POST /api/corundum/v1/follow_requests/:id/reject

Rejects and removes a pending follow request.

**Authentication:** Required (`write:follows` scope).

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:id` | The DID of the account whose follow request to reject |

**Returns:** Relationship entity.

**Errors:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 401 | `UNAUTHORIZED` | No valid token provided |
| 403 | `INSUFFICIENT_SCOPE` | Token lacks `write:follows` scope |
| 404 | `NOT_FOUND` | No pending follow request from that account |
