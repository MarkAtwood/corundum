# Status Endpoints

Status endpoints are the core of the Corundum posting API. They let clients create, read, edit, delete, and interact with statuses. Because Corundum statuses are content-addressed, the `:id` parameter throughout this document is a CID — not a database integer. Every endpoint path that takes `:id` expects a base32lower CID (e.g., `bafyreiemxf5abjwjbikoz4mc3a3dla6ual3jsgpdr4cjr3oz3evfyavhwq`).

All endpoints that modify state require a Bearer token in the `Authorization` header. Read-only endpoints on public content accept unauthenticated requests. Scope requirements are noted per endpoint.

---

## POST /api/v1/statuses

Create a new status.

**Required scope:** `write:statuses`

**Request body** (JSON or `application/x-www-form-urlencoded`):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `status` | string | Conditionally | The text content of the status. Required unless `media_ids[]` is present. Maximum length is determined by the operator's instance configuration (default 500 characters). |
| `media_ids[]` | array of strings | Conditionally | Array of media attachment IDs (returned by the media upload endpoint) to attach to this status. Required if `status` is absent. Maximum 4 attachments per status. |
| `poll` | object | No | Poll configuration. See poll sub-fields below. Mutually exclusive with `media_ids[]`. |
| `poll.options[]` | array of strings | If poll present | The poll answer choices. Minimum 2, maximum 4. |
| `poll.expires_in` | integer | If poll present | Duration in seconds until the poll closes. |
| `poll.multiple` | boolean | No | If true, voters may select multiple options. Default false. |
| `poll.hide_totals` | boolean | No | If true, vote totals are hidden until the poll closes. Default false. |
| `in_reply_to_id` | string (CID) | No | CID of the status this is a reply to. If supplied, the server verifies the referenced CID exists before accepting the post. |
| `sensitive` | boolean | No | Mark the status as containing sensitive content. Default false. |
| `spoiler_text` | string | No | Content warning text shown before the content. Setting this implicitly sets `sensitive` to true. |
| `visibility` | string | No | One of `public`, `unlisted`, `private`, `direct`. Default is the user's configured default visibility. |
| `language` | string | No | BCP 47 language tag for the status content. If absent, the operator may attempt auto-detection. |
| `scheduled_at` | string (ISO 8601) | No | If provided, the status is scheduled for future publication rather than posted immediately. Returns a ScheduledStatus entity instead of a Status entity. |

**Server-side processing:**

When the server receives a valid post request, it does not simply insert a row into a database. It performs the following steps before returning a response:

1. Constructs the canonical JSON representation of the activity from the submitted fields.
2. Computes the CID of that canonical JSON. This CID becomes the status `id`.
3. Stores the activity object in IPFS and pins it.
4. Creates a SigningRecord: signs the activity CID with the user's Ed25519 key and stores the SigningRecord in IPFS.
5. Updates the user's ArchiveIndex to include the new CID.
6. Publishes a new IPNS record pointing to the updated RootManifest.

The returned `id` is the CID produced in step 2. Because the CID is derived from the content, the server cannot fabricate or alter it; any client that receives a status can independently verify the `id` by recomputing the CID from the content.

**Returns:** Status entity.

**Example response:**

```json
{
  "id": "bafyreiemxf5abjwjbikoz4mc3a3dla6ual3jsgpdr4cjr3oz3evfyavhwq",
  "created_at": "2024-03-10T12:34:56.789Z",
  "in_reply_to_id": null,
  "in_reply_to_account_id": null,
  "sensitive": false,
  "spoiler_text": "",
  "visibility": "public",
  "language": "en",
  "uri": "https://social.example/statuses/bafyreiemxf5abjwjbikoz4mc3a3dla6ual3jsgpdr4cjr3oz3evfyavhwq",
  "url": "https://social.example/@alice/bafyreiemxf5abjwjbikoz4mc3a3dla6ual3jsgpdr4cjr3oz3evfyavhwq",
  "replies_count": 0,
  "reblogs_count": 0,
  "favourites_count": 0,
  "content": "<p>Hello, federated world.</p>",
  "reblog": null,
  "account": { "id": "k51qzi5uqu5dlvj2baxnqndepeb86cbk3ng6bn9tx0dv7azvq7rjz47q2", "..." : "..." },
  "media_attachments": [],
  "tags": [],
  "emojis": [],
  "corundum": {
    "cid": "bafyreiemxf5abjwjbikoz4mc3a3dla6ual3jsgpdr4cjr3oz3evfyavhwq",
    "signing_record_cid": "bafyreiabcdef...",
    "sequence_number": 43,
    "epoch": 0,
    "curation_labels": []
  }
}
```

**Error responses:**

| HTTP status | Error code | Meaning |
|-------------|------------|---------|
| 401 | `unauthorized` | No valid token provided. |
| 403 | `insufficient_scope` | Token does not have `write:statuses` scope. |
| 422 | `validation_error` | Missing required fields, content too long, or invalid `in_reply_to_id`. |
| 503 | `ipfs_unavailable` | The operator's IPFS backend is temporarily unreachable. |

---

## GET /api/v1/statuses/:id

Fetch a single status by its CID.

**Required scope:** None for public statuses. `read:statuses` required to fetch non-public statuses you are authorized to see.

**Path parameter:** `:id` — the CID of the status.

**Returns:** Status entity.

**Notes:** The operator looks up the status by CID from its local store. If the status is not locally cached (e.g., it belongs to a remote user whose content has not been fetched), the operator may attempt to fetch it from IPFS or from the authoring user's operator. If the CID is not found after resolution attempts, the response is 404.

**Error responses:**

| HTTP status | Error code | Meaning |
|-------------|------------|---------|
| 401 | `unauthorized` | Status has non-public visibility and no token was provided. |
| 403 | `forbidden` | Status has non-public visibility and your account is not authorized to see it. |
| 404 | `not_found` | No status with this CID is known to this operator. |

---

## DELETE /api/v1/statuses/:id

Delete a status. The authenticated user must be the author.

**Required scope:** `write:statuses`

**Path parameter:** `:id` — the CID of the status to delete.

**Behavior:** Deletion in a content-addressed system requires clarification. The original CID and the content it identifies are immutable — you cannot destroy a hash. What "delete" means in Corundum is:

1. The operator publishes a Tombstone activity that references the original status CID and is signed by the author's key.
2. The operator unpins the original activity from its IPFS node, allowing it to be garbage-collected if no other node is pinning it.
3. The status is removed from the author's ArchiveIndex.
4. The operator broadcasts the Tombstone to federated operators via the inter-operator protocol.

The original CID may persist in the IPFS network if other nodes have pinned it. The Tombstone is the authoritative signal that the author has retracted the content; well-behaved operators and clients that receive the Tombstone will remove the content from display. Content that was fetched and cached before the Tombstone was broadcast may continue to be available to nodes that have not yet processed the Tombstone.

**Returns:** Status entity of the deleted status (with content still present, so the client can display "you deleted this post" confirmation).

**Error responses:**

| HTTP status | Error code | Meaning |
|-------------|------------|---------|
| 401 | `unauthorized` | No valid token provided. |
| 403 | `forbidden` | You are not the author of this status. |
| 404 | `not_found` | No status with this CID is known to this operator. |

---

## PUT /api/v1/statuses/:id

Edit a status. The authenticated user must be the author.

**Required scope:** `write:statuses`

**Path parameter:** `:id` — the CID of the status to edit.

**Request body:** Same fields as `POST /api/v1/statuses`.

**Behavior:** Editing a content-addressed status produces a new activity, not a mutation of the existing one. The edit process is:

1. A new activity is constructed from the submitted fields, with an additional `predecessor_cid` field pointing to the CID of the status being edited.
2. The new activity is stored in IPFS. Its CID becomes the new status `id`.
3. The original CID is not deleted; it remains in the IPFS network and in history. The `predecessor_cid` link in the new activity is what connects the edit chain.
4. The author's ArchiveIndex is updated to point to the new CID.

The result is an immutable edit history: every version of a status exists as its own CID, and each version (except the first) declares its predecessor. Clients that want to show edit history can walk the `predecessor_cid` chain.

**Returns:** Status entity of the newly created (edited) status. The returned `id` is the new CID, not the original.

**Error responses:**

| HTTP status | Error code | Meaning |
|-------------|------------|---------|
| 401 | `unauthorized` | No valid token provided. |
| 403 | `forbidden` | You are not the author of this status. |
| 404 | `not_found` | No status with this CID is known to this operator. |
| 422 | `validation_error` | Invalid field values in the request body. |

---

## GET /api/v1/statuses/:id/context

Fetch the reply thread surrounding a status: the ancestors (statuses this one replies to, walking up the reply chain) and the descendants (replies to this status and their replies).

**Required scope:** None for public statuses. `read:statuses` for non-public statuses.

**Path parameter:** `:id` — the CID of the status.

**Returns:** An object with two keys:

```json
{
  "ancestors": [ "...Status entity...", "...Status entity..." ],
  "descendants": [ "...Status entity...", "...Status entity..." ]
}
```

`ancestors` is ordered from the root of the thread down to the immediate parent of the requested status. `descendants` is a depth-first ordered list of all replies.

**Notes:** Reply threads in Corundum may span multiple operators. The serving operator will attempt to fetch statuses from remote operators for threads that originated elsewhere. Statuses that could not be fetched are omitted from the response rather than causing an error; the thread may therefore have gaps.

---

## POST /api/v1/statuses/:id/reblog

Reblog (boost) a status. Creates a Reblog activity that references the original status CID and publishes it to the author's timeline.

**Required scope:** `write:statuses`

**Path parameter:** `:id` — the CID of the status to reblog.

**Returns:** Status entity of the reblog activity (not the original status). The `reblog` field of the returned entity contains the original Status entity.

**Error responses:**

| HTTP status | Error code | Meaning |
|-------------|------------|---------|
| 401 | `unauthorized` | No valid token provided. |
| 403 | `forbidden` | The status is not visible to you, or the author has disabled reblogs. |
| 404 | `not_found` | No status with this CID is known to this operator. |
| 422 | `already_reblogged` | You have already reblogged this status. |

---

## POST /api/v1/statuses/:id/unreblog

Remove a reblog of a status. Publishes a Retract activity for the Reblog activity.

**Required scope:** `write:statuses`

**Path parameter:** `:id` — the CID of the status that was reblogged (the original, not the reblog activity).

**Returns:** Status entity of the original status, with updated `reblogs_count`.

**Error responses:**

| HTTP status | Error code | Meaning |
|-------------|------------|---------|
| 401 | `unauthorized` | No valid token provided. |
| 404 | `not_found` | No status with this CID is known, or you have not reblogged it. |

---

## POST /api/v1/statuses/:id/favourite

Favourite a status.

**Required scope:** `write:favourites`

**Path parameter:** `:id` — the CID of the status to favourite.

**Returns:** Status entity with updated `favourites_count`.

**Error responses:**

| HTTP status | Error code | Meaning |
|-------------|------------|---------|
| 401 | `unauthorized` | No valid token provided. |
| 403 | `forbidden` | The status is not visible to you. |
| 404 | `not_found` | No status with this CID is known to this operator. |

---

## POST /api/v1/statuses/:id/unfavourite

Remove a favourite from a status.

**Required scope:** `write:favourites`

**Path parameter:** `:id` — the CID of the status to unfavourite.

**Returns:** Status entity with updated `favourites_count`.

**Error responses:**

| HTTP status | Error code | Meaning |
|-------------|------------|---------|
| 401 | `unauthorized` | No valid token provided. |
| 404 | `not_found` | No status with this CID is known, or you have not favourited it. |

---

## GET /api/v1/statuses/:id/signing_record

Fetch the SigningRecord for a status. Returns the cryptographic proof of authorship: the author's public key, the signature over the activity CID, and the CID of the SigningRecord object itself.

**Required scope:** None. This endpoint is intentionally unauthenticated and public. Transparency of authorship proofs is a core Corundum design principle — any client, researcher, or auditor can verify that a status was authored by the claimed identity without needing an account or token.

**Path parameter:** `:id` — the CID of the status.

**Returns:** SigningRecord entity.

```json
{
  "activity_cid": "bafyreiemxf5abjwjbikoz4mc3a3dla6ual3jsgpdr4cjr3oz3evfyavhwq",
  "author_ipns": "k51qzi5uqu5dlvj2baxnqndepeb86cbk3ng6bn9tx0dv7azvq7rjz47q2",
  "signed_at": "2024-03-10T12:34:56.789Z",
  "algorithm": "ed25519",
  "public_key_multibase": "z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
  "signature_multibase": "zABC123...",
  "signing_record_cid": "bafyreiabcdef..."
}
```

**Verification procedure:** A client that wants to independently verify a status was authored by the claimed account performs the following steps:

1. Fetch the status via `GET /api/v1/statuses/:id`. Note `account.corundum.public_key_multibase`.
2. Fetch the signing record via `GET /api/v1/statuses/:id/signing_record`. Note `public_key_multibase` and `signature_multibase`.
3. Confirm that the key in the signing record matches the key declared on the account.
4. Recompute the CID of the activity content. Confirm it matches `activity_cid`.
5. Verify the Ed25519 signature in `signature_multibase` over the canonical encoding of `activity_cid` using the public key.

If all five steps pass, authorship is verified without trusting the operator. Step 3 may optionally be extended to resolve the author's DID document and confirm the key is currently declared in the DID, which provides a stronger guarantee in case of key rotation.

**Error responses:**

| HTTP status | Error code | Meaning |
|-------------|------------|---------|
| 404 | `not_found` | No status with this CID is known, or its signing record has not been fetched. |

---

## GET /api/v1/statuses/:id/curation

Fetch the curation labels applied to a status by curators that this operator or the authenticated user subscribes to.

**Required scope:** None. Unauthenticated requests return labels from the operator's default curator subscriptions. Authenticated requests additionally include labels from curators the authenticated user has personally subscribed to.

**Path parameter:** `:id` — the CID of the status.

**Returns:** Array of CurationLabel entities. Empty array if no labels have been applied.

```json
[
  {
    "curator_id": "k51qzi5...",
    "curator_display_name": "Safety Curator",
    "judgment": "spam",
    "confidence": 0.95,
    "signed_at": "2024-03-10T14:00:00.000Z",
    "authority_declaration_cid": "bafyrei...",
    "appeal_url": "https://curator.example/appeals"
  }
]
```

**Notes:** Labels are produced by independent curators, not by the operator. The operator only serves labels from curators it or its users subscribe to. The presence of a label does not mean the operator endorses the label or has taken any moderation action — it means the curator issued the label and the operator is surfacing it. Clients make their own decisions about how to display or act on labels.

Clients that want to independently verify a label's authenticity should fetch the `authority_declaration_cid` document to obtain the curator's declared public key, then verify the signature on the label using that key.

**Error responses:**

| HTTP status | Error code | Meaning |
|-------------|------------|---------|
| 404 | `not_found` | No status with this CID is known to this operator. |
