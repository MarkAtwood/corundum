# Media

Media endpoints handle uploading and managing media attachments. Uploaded media is stored directly in IPFS; the returned CID is the canonical, globally addressable identifier for that content.

## Standard Mastodon-Compatible Endpoints

### POST /api/v1/media

Upload a media attachment synchronously. Suitable for small files that can be processed within a single request. Large files should use `POST /api/v2/media` or the chunked upload extension.

**Authentication:** Required (`write:media` scope)

**Content-Type:** `multipart/form-data`

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | binary | yes | The media file to upload |
| `thumbnail` | binary | no | Custom thumbnail for video or audio attachments |
| `description` | string | no | Alt text for the attachment. Strongly recommended for accessibility. |
| `focus` | string | no | Focal point for cropping, as `x,y` where each value is in the range `-1.0` to `1.0`. Example: `0.5,-0.3` |

**Returns:** MediaAttachment entity.

```json
{
  "id": "bafyreihoge5xqxmfqhm6b5cqwlzrvhpuqxvkkhhlq2giqzimf7v3sn2zfm",
  "type": "image",
  "url": "https://ipfs.social.example/ipfs/bafyreihoge5xqxmfqhm6b5cqwlzrvhpuqxvkkhhlq2giqzimf7v3sn2zfm",
  "preview_url": "https://ipfs.social.example/ipfs/bafyreia7x2q7...",
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
    "media_cid": "bafyreihoge5xqxmfqhm6b5cqwlzrvhpuqxvkkhhlq2giqzimf7v3sn2zfm"
  }
}
```

**MediaAttachment fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | CID of the media stored in IPFS (base32lower). Used as the attachment reference in status creation. |
| `type` | string | `image`, `video`, `audio`, or `unknown` |
| `url` | string | IPFS gateway URL served by this operator. Clients that speak IPFS natively may also fetch the content via `ipfs://<CID>`. |
| `preview_url` | string | URL of a smaller preview or thumbnail |
| `description` | string or null | Alt text |
| `meta` | object | Dimension and duration metadata. Shape varies by media type. |
| `corundum.media_cid` | string | The raw CID of the media content. Identical to `id` in the native API; provided for clients that need explicit access to the CID separate from the Mastodon-compatible `id` field. |

**Errors:**

| Code | Error | Description |
|------|-------|-------------|
| 401 | `unauthorized` | No valid token provided |
| 403 | `forbidden` | Token lacks `write:media` scope |
| 422 | `unprocessable_entity` | File type not supported or file is malformed |
| 413 | `payload_too_large` | File exceeds the synchronous upload size limit. Use `POST /api/v2/media` or chunked upload. |

---

### POST /api/v2/media

Upload a media attachment asynchronously. Use for large files. The operator accepts the upload immediately and processes it in the background. The response is returned before processing completes.

**Authentication:** Required (`write:media` scope)

**Content-Type:** `multipart/form-data`

**Request Body:** Same parameters as `POST /api/v1/media`.

**Returns:** MediaAttachment entity with `url: null` and `preview_url: null` while processing is in progress.

```json
{
  "id": "bafyreihoge5xqxmfqhm6b5cqwlzrvhpuqxvkkhhlq2giqzimf7v3sn2zfm",
  "type": "image",
  "url": null,
  "preview_url": null,
  "description": "A photograph of a mountain at sunset",
  "meta": {},
  "corundum": {
    "media_cid": "bafyreihoge5xqxmfqhm6b5cqwlzrvhpuqxvkkhhlq2giqzimf7v3sn2zfm"
  }
}
```

Poll `GET /api/v1/media/:id` to check processing status. When `url` is no longer null, the attachment is ready to use in a status.

**HTTP status on response:** `202 Accepted` (not `200 OK`).

---

### GET /api/v1/media/:id

Get the current state of a media attachment. Primarily used to poll for completion after an async upload.

**Authentication:** Required. The attachment must belong to the authenticated user.

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:id` | The CID of the attachment (as returned by the upload endpoint) |

**Returns:** MediaAttachment entity. If `url` is non-null, processing is complete.

**Errors:**

| Code | Error | Description |
|------|-------|-------------|
| 401 | `unauthorized` | No valid token provided |
| 404 | `not_found` | No attachment with this ID belongs to the authenticated user |

---

### PUT /api/v1/media/:id

Update metadata on a media attachment that has not yet been attached to a published status.

**Authentication:** Required (`write:media` scope)

**Content-Type:** `application/json`

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `description` | string | no | Updated alt text |
| `focus` | string | no | Updated focal point as `x,y` |

**Returns:** Updated MediaAttachment entity.

**Errors:**

| Code | Error | Description |
|------|-------|-------------|
| 401 | `unauthorized` | No valid token provided |
| 403 | `forbidden` | Token lacks `write:media` scope, or the attachment has already been used in a published status |
| 404 | `not_found` | No attachment with this ID belongs to the authenticated user |
| 422 | `unprocessable_entity` | `focus` value is out of the `-1.0` to `1.0` range |

---

## Corundum Extension: Chunked Upload

For very large files (multi-gigabyte video, high-resolution archives), Corundum provides a three-step chunked upload protocol. This maps to the IPFS chunked block ingestion mechanism: each chunk is stored as an IPFS block, and the final step assembles the blocks into a single DAG node with a stable root CID.

### POST /api/v1/corundum/media/chunked/init

Initialize a chunked upload session.

**Authentication:** Required (`write:media` scope)

**Content-Type:** `application/json`

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `total_size` | integer | yes | Total file size in bytes |
| `mime_type` | string | yes | MIME type of the file, e.g. `video/mp4` |
| `chunk_size` | integer | no | Requested chunk size in bytes. The operator may adjust this; the actual chunk size is returned in the response. |

**Returns:**

```json
{
  "upload_id": "abc123",
  "chunk_size": 262144,
  "total_chunks": 4
}
```

| Field | Type | Description |
|-------|------|-------------|
| `upload_id` | string | Opaque identifier for this upload session. Used in subsequent chunk and complete requests. |
| `chunk_size` | integer | The chunk size the client must use for all chunks except the final one, which may be smaller. |
| `total_chunks` | integer | Expected number of chunks given `total_size` and `chunk_size`. |

---

### POST /api/v1/corundum/media/chunked/:upload_id/chunk/:n

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

Chunks may be uploaded in any order. Uploading the same chunk index twice overwrites the previous upload for that index. The operator does not attempt assembly until `/complete` is called.

**Errors:**

| Code | Error | Description |
|------|-------|-------------|
| 404 | `not_found` | No upload session with this ID, or it has expired |
| 413 | `payload_too_large` | Chunk exceeds the negotiated `chunk_size` |

---

### POST /api/v1/corundum/media/chunked/:upload_id/complete

Finalize the chunked upload. The operator assembles the chunks into a single IPFS DAG, pins the result, and returns the completed MediaAttachment.

**Authentication:** Required (`write:media` scope)

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `:upload_id` | Upload session ID |

**Request Body:** None required. Optionally, a JSON body with `description` and `focus` fields (same as the standard upload endpoints) may be included to set metadata at completion time.

**Returns:** MediaAttachment entity with the final CID populated. The `url` field will be non-null if post-processing (thumbnail generation, transcoding) completed synchronously. If not, poll `GET /api/v1/media/:id` as with async uploads.

**Errors:**

| Code | Error | Description |
|------|-------|-------------|
| 404 | `not_found` | No upload session with this ID |
| 422 | `unprocessable_entity` | One or more chunks are missing; the response body identifies which chunk indexes are absent |
