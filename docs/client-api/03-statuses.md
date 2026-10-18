# Status Endpoints

Status endpoints are the core of the Corundum posting API. They let clients create, read, edit, delete, and interact with statuses. Because Corundum statuses are content-addressed, the `:id` parameter throughout this document is an activity identifier: the CIDv1 (raw codec, sha2-256, base32 `bafkrei...`) of the activity's exact stored bytes (spec Chapter 33), not a database integer.

All endpoints that modify state require a Bearer token in the `Authorization` header. Read-only endpoints accept unauthenticated requests, because all Corundum content is public (spec Chapter 40). Scope requirements are noted per endpoint.

The endpoints that publish an activity (`POST`, `PUT`, `DELETE /statuses`, reblog, unreblog, favourite, unfavourite) are for accounts whose content key the operator holds (`corundum.key_custody` `"operator"`, the default). For a self-custody account they return `409 CUSTODY_MODE_MISMATCH`; the client builds and signs the activity itself and submits it with `POST /api/corundum/v1/activities` (below). Key custody is described in `10-identity-migration.md`.

---

## POST /api/corundum/v1/statuses

Create a new status.

**Required scope:** `write:statuses`

**Request body** (JSON or `application/x-www-form-urlencoded`):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `status` | string | Conditionally | The text content of the status. Required unless `media_ids[]` is present. Maximum length is determined by the operator's instance configuration (default 500 characters). |
| `media_ids[]` | array of strings | Conditionally | Array of media attachment IDs (operator-local ids returned by the media upload endpoint, `08-media.md`) to attach to this status. Required if `status` is absent. Maximum 4 attachments per status. |
| `poll` | object | No | Poll configuration. See poll sub-fields below. Mutually exclusive with `media_ids[]`. |
| `poll.options[]` | array of strings | If poll present | The poll answer choices. Minimum 2, maximum 4. |
| `poll.expires_in` | integer | If poll present | Duration in seconds until the poll closes. |
| `poll.multiple` | boolean | No | If true, voters may select multiple options. Default false. |
| `poll.hide_totals` | boolean | No | If true, vote totals are hidden until the poll closes. Default false. |
| `in_reply_to_id` | string | No | Activity id of the status this is a reply to. The reply is submitted to the parent author's operator through the reply protocol (spec Chapter 21). |
| `sensitive` | boolean | No | Mark the status as containing sensitive content. Default false. |
| `spoiler_text` | string | No | Content warning text shown before the content. Setting this implicitly sets `sensitive` to true. |
| `visibility` | string | No | Only `public` is accepted (spec Chapter 40). Any other value is rejected with `VALIDATION_FAILED`, `details.reason` `visibility-unsupported`. |
| `language` | string | No | BCP 47 language tag for the status content. If absent, the language is unspecified. |
| `scheduled_at` | string (ISO 8601) | No | If provided, the status is scheduled for future publication rather than posted immediately. Returns a ScheduledStatus entity instead of a Status entity. |

**Server-side processing:**

1. The operator builds the activity's bytes once: an ActivityStreams object with `attributedTo` set to the user's DID, `to` set to the public collection, `published`, and the next `seq` in the user's timeline (spec Chapter 11). These bytes are never re-serialized afterwards.
2. It computes the activity id: the raw-codec CID of those bytes (spec Chapter 33).
3. It stores the bytes in IPFS and pins them.
4. It signs the bytes with the user's content key, producing a detached JWS SigningRecord (spec Chapter 12), and stores and pins that too.
5. It appends an Entry (`seq`, activity id, SigningRecord CID) to the user's current chunk (spec Chapter 9).
6. It publishes a new RootManifest and a new IPNS record pointing to it.
7. For a reply, it submits the reply to the parent author's operator. A rejection arrives later as a `corundum.reply_rejected` notification (`06-notifications.md`).

The returned `id` is the CID from step 2. Any client that holds the activity bytes can check it by hashing them.

**Returns:** Status entity (`02-entities.md`).

**Example response:**

```json
{
  "id": "<activity id>",
  "created_at": "2025-03-15T14:22:11.000Z",
  "in_reply_to_id": null,
  "in_reply_to_account_id": null,
  "sensitive": false,
  "spoiler_text": "",
  "visibility": "public",
  "language": "en",
  "uri": "https://birdsite.example/statuses/<activity id>",
  "url": "https://birdsite.example/@alice/<activity id>",
  "replies_count": 0,
  "reblogs_count": 0,
  "favourites_count": 0,
  "content": "<p>Hello, federated world.</p>",
  "reblog": null,
  "account": { "id": "did:webvh:<SCID>:birdsite.example:users:alice", "...": "..." },
  "media_attachments": [],
  "tags": [],
  "emojis": [],
  "corundum": {
    "seq": 1042,
    "epoch": 4,
    "signing_record_cid": "<CID of the SigningRecord>",
    "replaces": null,
    "replaced_by": null,
    "curation_labels": []
  }
}
```

**Error responses:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 401 | `UNAUTHORIZED` | No valid token provided. |
| 403 | `INSUFFICIENT_SCOPE` | Token does not have `write:statuses` scope. |
| 403 | `CURATION_REJECTED` | The content matched a curation rule this operator enforces. |
| 409 | `CUSTODY_MODE_MISMATCH` | The account is self-custodied; use `POST /api/corundum/v1/activities`. |
| 422 | `VALIDATION_FAILED` | Missing required fields, content too long, unsupported `visibility`, or unknown `in_reply_to_id`. |
| 503 | `IPFS_UNAVAILABLE` | The operator's IPFS backend is temporarily unreachable. |

---

## POST /api/corundum/v1/activities

Publish an activity that the client built and signed itself. This is the write path for self-custody accounts; it covers every activity type (posts, edits, `Delete`, `Announce`, `Like`).

**Required scope:** `write:statuses`

**Request body** (JSON):

```json
{
  "activity": "<base64url of the exact activity bytes>",
  "signing_record": "<base64url of the SigningRecord bytes>"
}
```

Both values are base64url so that the JSON transport never re-serializes the signed bytes.

**Behavior:** The operator computes the activity's CID, verifies the SigningRecord against the bytes (spec Chapter 34), and checks that `attributedTo` is the authenticated user's DID and that `seq` equals the `next_seq` reported by `GET /api/corundum/v1/identity`. It then stores and pins both objects and prepares the new current chunk and RootManifest. Because only the user can sign the RootManifest and IPNS record, it responds `202 Accepted` with a pending RootManifest, which the client signs and commits with `PUT /api/corundum/v1/identity/root_manifest` (`10-identity-migration.md`). The activity is published when that commit succeeds.

**Returns:** `202 Accepted`:

```json
{
  "id": "<activity id>",
  "pending_root_manifest": {
    "payload": "<base64url of the RootManifest payload bytes>",
    "ipns_record": "<base64url of the unsigned IPNS record>"
  }
}
```

**Error responses:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 400 | `ACTIVITY_INVALID` | `details.reason` is `cid-mismatch`, `signature-invalid`, `seq-mismatch`, or `author-mismatch`. |
| 401 | `UNAUTHORIZED` | No valid token provided. |
| 403 | `INSUFFICIENT_SCOPE` | Token does not have `write:statuses` scope. |
| 409 | `CUSTODY_MODE_MISMATCH` | The account is operator-custodied; use the status endpoints. |
| 409 | `SEQ_CONFLICT` | Another activity already took this `seq`; fetch `next_seq` and rebuild. |

---

## GET /api/corundum/v1/statuses/:id

Fetch a single status by its activity id.

**Required scope:** None.

**Path parameter:** `:id` — the activity id.

**Returns:** Status entity. If the status has been edited, this is the requested version, with `corundum.replaced_by` naming the newer one.

**Notes:** The operator looks the status up in its local store. If it is not cached locally, the operator may fetch it from IPFS or from the author's operator, verifying the CID and SigningRecord before serving it.

**Error responses:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 404 | `NOT_FOUND` | No status with this id is known to this operator. |
| 410 | `GONE` | The author deleted this status. |

---

## DELETE /api/corundum/v1/statuses/:id

Delete a status. The authenticated user must be the author.

**Required scope:** `write:statuses`

**Path parameter:** `:id` — the activity id of the status to delete.

**Behavior:** An identifier cannot be destroyed, and the archive tree never changes (spec Chapter 9). Deleting means (spec Chapter 13):

1. The operator publishes an AS2 `Delete` activity whose `object` is `:id`, signed and appended to the user's timeline like any other activity.
2. The status's StateMap slot gets `deletedBy`, naming the `Delete` activity.
3. The operator unpins the status and its SigningRecords and stops serving them; later requests return `410 GONE`.
4. The operator notifies operators known to have fetched the content.

Copies pinned elsewhere may persist. Receivers verify the `Delete` before acting on it.

**Returns:** Status entity of the deleted status (with content still present, so the client can offer "delete and redraft").

**Error responses:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 401 | `UNAUTHORIZED` | No valid token provided. |
| 403 | `FORBIDDEN` | You are not the author of this status. |
| 404 | `NOT_FOUND` | No status with this id is known to this operator. |
| 409 | `CUSTODY_MODE_MISMATCH` | The account is self-custodied; publish a `Delete` with `POST /api/corundum/v1/activities`. |

---

## PUT /api/corundum/v1/statuses/:id

Edit a status. The authenticated user must be the author.

**Required scope:** `write:statuses`

**Path parameter:** `:id` — the activity id of the version being edited.

**Request body:** Same fields as `POST /api/corundum/v1/statuses`.

**Behavior:** An edit is a new activity (spec Chapter 13):

1. The operator builds a new activity with the same `@type`, `attributedTo`, and `inReplyTo` as the edited version, plus `replaces: <:id>`.
2. It is published like any other activity, with a new `seq` and a new id.
3. The edited version's StateMap slot gets `replacedBy`, naming the new version. The old version stays in the archive.

Timelines list each post once: its newest version, at the position of its first version. An edit to a reply is submitted to the parent's operator as a new reply submission; reply trees show the version that operator accepted.

**Returns:** Status entity of the new version. Its `id` is the new activity id and its `corundum.replaces` is `:id`.

**Error responses:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 401 | `UNAUTHORIZED` | No valid token provided. |
| 403 | `FORBIDDEN` | You are not the author of this status, or its activity type prohibits edits. |
| 404 | `NOT_FOUND` | No status with this id is known to this operator. |
| 409 | `CUSTODY_MODE_MISMATCH` | The account is self-custodied; publish the edit with `POST /api/corundum/v1/activities`. |
| 422 | `VALIDATION_FAILED` | Invalid field values in the request body. |

---

## GET /api/corundum/v1/statuses/:id/context

Fetch the reply thread surrounding a status: the ancestors (walking up the reply chain) and the descendants (replies accepted into the reply trees below it).

**Required scope:** None.

**Path parameter:** `:id` — the activity id of the status.

**Returns:**

```json
{
  "ancestors": [ "...Status entity...", "...Status entity..." ],
  "descendants": [ "...Status entity...", "...Status entity..." ]
}
```

`ancestors` is ordered from the root of the thread down to the immediate parent of the requested status. `descendants` is a depth-first ordered list of replies.

**Notes:** Descendants come from the reply trees published by each parent author's operator (spec Chapter 21). For an edited reply, the thread shows the version the parent's operator accepted, not a newer one; clients must not follow `replaced_by` inside a thread. Statuses that could not be fetched are omitted, so the thread may have gaps.

---

## POST /api/corundum/v1/statuses/:id/reblog

Reblog (boost) a status. Publishes an `Announce` activity whose `object` is `:id`.

**Required scope:** `write:statuses`

**Path parameter:** `:id` — the activity id of the status to reblog.

**Returns:** Status entity of the `Announce` activity. Its `reblog` field contains the original Status entity. Reblogging a status you have already reblogged returns your existing reblog and publishes nothing.

**Error responses:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 401 | `UNAUTHORIZED` | No valid token provided. |
| 404 | `NOT_FOUND` | No status with this id is known to this operator. |
| 409 | `CUSTODY_MODE_MISMATCH` | The account is self-custodied. |

---

## POST /api/corundum/v1/statuses/:id/unreblog

Remove a reblog. Publishes a `Delete` activity naming your `Announce` activity.

**Required scope:** `write:statuses`

**Path parameter:** `:id` — the activity id of the original status (not of the `Announce`).

**Returns:** Status entity of the original status, with updated `reblogs_count`. If you have not reblogged it, nothing is published.

**Error responses:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 401 | `UNAUTHORIZED` | No valid token provided. |
| 404 | `NOT_FOUND` | No status with this id is known to this operator. |
| 409 | `CUSTODY_MODE_MISMATCH` | The account is self-custodied. |

---

## POST /api/corundum/v1/statuses/:id/favourite

Favourite a status. Publishes a `Like` activity whose `object` is `:id`. Favouriting a status you have already favourited publishes nothing.

**Required scope:** `write:favourites`

**Path parameter:** `:id` — the activity id of the status to favourite.

**Returns:** Status entity with updated `favourites_count`.

**Error responses:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 401 | `UNAUTHORIZED` | No valid token provided. |
| 404 | `NOT_FOUND` | No status with this id is known to this operator. |
| 409 | `CUSTODY_MODE_MISMATCH` | The account is self-custodied. |

---

## POST /api/corundum/v1/statuses/:id/unfavourite

Remove a favourite. Publishes a `Delete` activity naming your `Like` activity. If you have not favourited the status, nothing is published.

**Required scope:** `write:favourites`

**Path parameter:** `:id` — the activity id of the status.

**Returns:** Status entity with updated `favourites_count`.

**Error responses:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 401 | `UNAUTHORIZED` | No valid token provided. |
| 404 | `NOT_FOUND` | No status with this id is known to this operator. |
| 409 | `CUSTODY_MODE_MISMATCH` | The account is self-custodied. |

---

## GET /api/corundum/v1/statuses/:id/signing_record

Fetch the SigningRecord for a status: the detached JWS over the activity's bytes (spec Chapter 12).

**Required scope:** None. Anyone can verify authorship without an account.

**Path parameter:** `:id` — the activity id of the status.

**Returns:** The current SigningRecord's stored bytes, exactly as stored (never re-serialized), with `Content-Type: application/json`. If the activity has been re-signed, this is the SigningRecord named in its StateMap slot; otherwise it is the one named in its archive Entry. The same bytes can be fetched by CID (`corundum.signing_record_cid`) from any IPFS gateway.

To verify authorship, follow the SigningRecord verification procedure in `02-entities.md`.

**Error responses:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 404 | `NOT_FOUND` | No status with this id is known, or its SigningRecord has not been fetched. |
| 410 | `GONE` | The author deleted this status. |

---

## Curation labels

`GET /api/corundum/v1/statuses/:id/curation` is defined in `11-curation.md`.
