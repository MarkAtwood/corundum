# Media

Media endpoints handle uploading and managing media attachments. Uploaded files are stored in IPFS and referenced from activities in `ipfs` mode (spec Chapter 15).

## Media IDs and Content CIDs

A media attachment has two identifiers, and they do different jobs:

- **`id`** is an opaque, operator-local identifier for one upload by one user. It is what the client passes in `media_ids[]` when posting, and what `GET` and `PUT /api/corundum/v1/media/:id` take. Only the uploading user can see or change it.
- **`corundum.media_cid`** is the CID of the file's bytes. It is what the published activity references, and anyone can fetch the file by it from any IPFS node.

They are separate because a CID names bytes, not an upload. Two users who upload the same file get the same CID, so the CID cannot carry ownership, alt text, focal point, or "already attached" state: each of those belongs to one user's upload. The operator pins each CID once and counts references across media ids, unpinning only when no upload or published activity still uses it.

The CID is computed with the fixed UnixFS parameters of spec Chapter 15, so anyone who has the file computes the same CID: CIDv1, SHA-256, raw leaves, a fixed-size chunker of 1,048,576 bytes, and the balanced layout with at most 174 links per node (in Kubo, `ipfs add --cid-version=1 --raw-leaves --chunker=size-1048576`). A file of at most 1 MiB is a single raw block, so its CID begins `bafkrei`; a larger file has a dag-pb root and its CID begins `bafybei`. The operator MUST compute and verify the CID with these parameters before accepting an upload; the chunk size an upload was transported in has no effect on it.

## Upload Endpoints

### POST /api/corundum/v1/media

Upload a media attachment. The operator stores the file, computes its CID, and either finishes processing (thumbnails, metadata) within the request or continues in the background.

**Authentication:** Required (`write:media` scope)

**Content-Type:** `multipart/form-data`

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | binary | yes | The media file to upload |
| `thumbnail` | binary | no | Custom thumbnail for video or audio attachments |
| `description` | string | no | Alt text for the attachment. Strongly recommended for accessibility. |
| `focus` | string | no | Focal point for cropping, as `x,y` where each value is in the range `-1.0` to `1.0`. Example: `0.5,-0.3` |

**Returns:** MediaAttachment entity, with `200 OK` when processing is complete, or `202 Accepted` with `url: null` and `preview_url: null` while processing continues. After a `202`, poll `GET /api/corundum/v1/media/:id`; when `url` is non-null, the attachment is ready to use in a status.

```json
{
  "id": "<operator-assigned media id>",
  "type": "image",
  "url": "https://birdsite.example/ipfs/<CID of the file>",
  "preview_url": "https://birdsite.example/ipfs/<CID of the preview>",
  "description": "A photograph of a mountain at sunset",
  "meta": {
    "original": {
      "width": 3840,
      "height": 2160,
      "size": "3840x2160",
      "aspect": 1.777
    },
    "small": {
      "width": 640,
      "height": 360,
      "size": "640x360",
      "aspect": 1.777
    }
  },
  "corundum": {
    "media_cid": "<CID of the file>"
  }
}
```

**MediaAttachment fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Operator-local media id for this upload. Used in `media_ids[]` when creating a status. |
| `type` | string | `image`, `video`, `audio`, or `unknown` |
| `url` | string or null | IPFS gateway URL served by this operator. Clients that speak IPFS natively may fetch `ipfs://<media_cid>` instead. `null` while processing. |
| `preview_url` | string or null | URL of a smaller preview or thumbnail |
| `description` | string or null | Alt text |
| `meta` | object | Dimension and duration metadata. Shape varies by media type. |
| `corundum.media_cid` | string | CID of the file's bytes, computed with the Chapter 15 parameters above. |

**Errors:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 401 | `UNAUTHORIZED` | No valid token provided |
| 403 | `INSUFFICIENT_SCOPE` | Token lacks `write:media` scope |
| 413 | `PAYLOAD_TOO_LARGE` | File exceeds the single-request size limit. Use chunked upload. |
| 422 | `VALIDATION_FAILED` | File type not supported or file is malformed |
| 503 | `IPFS_UNAVAILABLE` | The operator's IPFS backend is temporarily unreachable |

---

### GET /api/corundum/v1/media/:id

Get the current state of a media attachment. Primarily used to poll for completion after a `202` upload.

**Authentication:** Required (`write:media` scope). The attachment must belong to the authenticated user.

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:id` | The media id returned by the upload endpoint |

**Returns:** MediaAttachment entity. If `url` is non-null, processing is complete.

**Errors:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 401 | `UNAUTHORIZED` | No valid token provided |
| 404 | `NOT_FOUND` | No attachment with this id belongs to the authenticated user |

---

### PUT /api/corundum/v1/media/:id

Update metadata on a media attachment that has not yet been attached to a published status. Once an activity referencing the media is published, its description is part of that activity's signed bytes and cannot change; edit the status instead (`03-statuses.md`).

**Authentication:** Required (`write:media` scope)

**Content-Type:** `application/json`

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `description` | string | no | Updated alt text |
| `focus` | string | no | Updated focal point as `x,y` |

**Returns:** Updated MediaAttachment entity.

**Errors:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 401 | `UNAUTHORIZED` | No valid token provided |
| 403 | `FORBIDDEN` | The attachment has already been used in a published status |
| 403 | `INSUFFICIENT_SCOPE` | Token lacks `write:media` scope |
| 404 | `NOT_FOUND` | No attachment with this id belongs to the authenticated user |
| 422 | `VALIDATION_FAILED` | `focus` value is out of the `-1.0` to `1.0` range |

---

## Chunked Upload

For files too large for one request, chunked upload is a resumable transport for **one** file: the client sends the file in pieces, and the operator reassembles it. The transport chunk size is unrelated to IPFS chunking and has no effect on the file's CID. When the upload completes, the operator builds the UnixFS DAG with the Chapter 15 parameters and verifies the resulting CID.

Segmented playback media (a `corundum:MediaManifest` or `corundum:MediaVariants`, spec Chapter 16) is a set of separate files: the client uploads each segment as its own file with these endpoints, and the manifest that lists their CIDs is part of the activity it publishes. This API does not build manifests.

### POST /api/corundum/v1/media/chunked/init

Initialize a chunked upload session.

**Authentication:** Required (`write:media` scope)

**Content-Type:** `application/json`

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `total_size` | integer | yes | Total file size in bytes |
| `mime_type` | string | yes | MIME type of the file, e.g. `video/mp4` |
| `chunk_size` | integer | no | Requested transport chunk size in bytes. The operator may adjust this; the actual chunk size is returned in the response. |

**Returns:**

```json
{
  "upload_id": "<operator-assigned upload id>",
  "chunk_size": 8388608,
  "total_chunks": 4,
  "expires_at": "2025-03-16T14:00:00Z"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `upload_id` | string | Opaque identifier for this upload session. Used in subsequent chunk and complete requests. |
| `chunk_size` | integer | The chunk size the client must use for all chunks except the final one, which may be smaller. |
| `total_chunks` | integer | Expected number of chunks given `total_size` and `chunk_size`. |
| `expires_at` | string (ISO 8601) | When the session expires if not completed. |

**Errors:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 401 | `UNAUTHORIZED` | No valid token provided |
| 403 | `INSUFFICIENT_SCOPE` | Token lacks `write:media` scope |
| 413 | `PAYLOAD_TOO_LARGE` | `total_size` exceeds the operator's maximum file size |
| 422 | `VALIDATION_FAILED` | `mime_type` is not supported |

---

### POST /api/corundum/v1/media/chunked/:upload_id/chunk/:n

Upload a single chunk.

**Authentication:** Required (`write:media` scope)

**Content-Type:** `application/octet-stream`

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:upload_id` | Upload session ID returned by the init endpoint |
| `:n` | Zero-based chunk index |

**Request Body:** Raw chunk bytes.

**Returns:** `204 No Content` on success.

Chunks may be uploaded in any order. Uploading the same chunk index twice replaces the previous upload for that index. The operator does not assemble the file until `/complete` is called.

**Errors:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 404 | `NOT_FOUND` | No upload session with this ID belongs to the authenticated user |
| 410 | `UPLOAD_SESSION_EXPIRED` | The session has expired. Start a new session. |
| 413 | `PAYLOAD_TOO_LARGE` | Chunk exceeds the negotiated `chunk_size` |

---

### POST /api/corundum/v1/media/chunked/:upload_id/complete

Finalize the chunked upload. The operator reassembles the file, builds and verifies its UnixFS DAG with the Chapter 15 parameters, pins it, and returns the MediaAttachment.

**Authentication:** Required (`write:media` scope)

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:upload_id` | Upload session ID |

**Request Body:** None required. Optionally, a JSON body with `description` and `focus` fields (as for `POST /api/corundum/v1/media`) sets metadata at completion time.

**Returns:** MediaAttachment entity with `corundum.media_cid` populated, as `200 OK` if post-processing (thumbnails, transcoding) finished, or `202 Accepted` otherwise; after a `202`, poll `GET /api/corundum/v1/media/:id`.

**Errors:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 400 | `CHUNK_MISSING` | One or more chunks were not uploaded; `details` lists the missing indexes |
| 404 | `NOT_FOUND` | No upload session with this ID belongs to the authenticated user |
| 410 | `UPLOAD_SESSION_EXPIRED` | The session has expired. Start a new session. |
| 422 | `VALIDATION_FAILED` | The assembled file's size differs from `total_size`, or the file is malformed |
| 503 | `IPFS_UNAVAILABLE` | The operator's IPFS backend is temporarily unreachable |
