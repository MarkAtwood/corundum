## Part V: Activity Types and the Extension System

### Chapter 14: The Activity Type Definition (ATD) System

Rather than hardcoding a fixed set of content types, Corundum defines an extensible type system. The insight behind it is that social media content types are not stable: stories, reels, spaces, events, polls, fleets — platforms invent new content types regularly. A protocol that enumerates allowed types becomes stale; a protocol that defines how to define types stays relevant.

An ATD (Activity Type Definition) is a content-addressed schema document. Because it's content-addressed, its CID is its stable identifier: if you change an ATD, you get a new CID, and the old CID continues to identify the old version. There is no versioning system separate from the content-addressing. This provides automatic version pinning: an activity that references an ATD by CID always refers to exactly that version of the schema, not "the current version" of the type.

An ATD specifies:

- Required and optional metadata fields with types and constraints
- Content resolution modes (how to get the actual content — inline, IPFS CID, URL, stream, chunked)
- Reply type definitions (what kinds of replies are accepted on activities of this type)
- Reaction vocabulary (which reactions are defined — likes, bookmarks, custom emoji reactions)
- Language constraints
- Quote and embedding behaviors
- ActivityStreams 2.0 translation mappings (how to represent this type in plain ActivityStreams for interoperability with non-Corundum systems)

The core specification defines standard ATDs for common types: Note (short text), Article (long-form), Image (single or gallery), Video, Audio, Event (with RSVP support), Poll, and Boost (reshare). These standard ATDs are published by the Corundum specification project and their CIDs are stable references that all implementations know.

Here is an abbreviated example of what the standard `Note` ATD looks like:

```json
{
  "@type": "corundum:ActivityTypeDefinition",
  "name": "Note",
  "version": "1.0",
  "fields": {
    "required": [
      { "name": "content", "type": "ContentRef", "modes": ["inline", "ipfs"] }
    ],
    "optional": [
      { "name": "summary", "type": "string", "maxLength": 500 },
      { "name": "sensitive", "type": "boolean" },
      { "name": "inReplyTo", "type": "cid" },
      { "name": "quoting", "type": "cid" },
      { "name": "language", "type": "bcp47" }
    ]
  },
  "contentConstraints": {
    "maxInlineLength": 5000
  },
  "replyTypes": ["Note"],
  "reactions": ["like", "bookmark"],
  "activityStreamsMapping": {
    "type": "Note",
    "contentField": "content"
  }
}
```

This ATD says: a Note requires a `content` field (inline or IPFS mode), allows optional `summary`, `sensitive`, `inReplyTo`, `quoting`, and `language` fields, accepts Note replies (not Article replies), supports like and bookmark reactions, and maps to an ActivityStreams 2.0 `Note` object for non-Corundum interoperability.

Anyone can publish a new ATD. If Meetup wants to define an ATD for structured event RSVPs that carries venue capacity, accessibility information, and calendar invite data, they publish an ATD document to IPFS and share its CID. Operators can discover it, fetch it, and decide whether to support it. Birdsite might decide to render Meetup's ATD natively (showing a rich event card); a minimal operator might fall back to the ActivityStreams translation mapping. Activities reference their ATD by CID, so validators can always resolve the exact schema version used.

This extensibility mechanism is what allows the Corundum ecosystem to innovate in content types without requiring protocol changes. New types are additive; they don't break existing implementations that don't support them.

### Chapter 15: Content Reference Modes

Every activity references its content through a `ContentRef` object that specifies a delivery mode. The most important thing to understand about this design is why content is not simply embedded in the activity JSON by default.

Activities are CID-addressed: the CID of an activity is the hash of its bytes. If the content were inline, the activity's CID would change every time the content changed — but in Corundum, activities are immutable once published. More practically, embedding a 4 MB image as a base64 blob in a JSON activity makes the activity's CID useless as a cache key, blows up JSON parsing in relay pipelines, and means that two different activities referencing the same image (say, two people boosting the same photo) each carry a separate copy instead of sharing one. Separating content reference from content data lets the activity remain small, stable, and CID-stable, while the content itself is stored and deduplicated by whatever storage system is most appropriate for its type and size.

The `ContentRef` system defines five modes:

**Inline**: Content embedded directly in the activity object. This mode is appropriate for short text where the overhead of a separate fetch would exceed the content itself. A short note, a brief caption, a poll question: things where the whole point is immediate availability and the content is never going to be deduplicated across activities anyway.

```json
{
  "mode": "inline",
  "mediaType": "text/plain",
  "value": "Hello, world!"
}
```

**IPFS**: Content referenced by CID. The CID is the address of the content on the IPFS network; any IPFS node that has pinned the content can serve it to any other. This is the preferred mode for images, documents, and anything that should be available permanently and independently of the original server. Critically, for IPFS content, the CID IS the integrity check — there is no separate hash field because the CID is a hash of the content by definition. If the bytes you fetch don't hash to the CID, your IPFS library will tell you before you ever see them.

```json
{
  "mode": "ipfs",
  "cid": "bafyreib2vekw73m2esv7m3n7ldvikfojqxj3u5ufwtfpwjw6uktrnxlcbq",
  "mediaType": "image/jpeg",
  "size": 2481920
}
```

**URL**: External content with an integrity hash. Some content cannot or will not be moved to IPFS — a paywalled article, a file hosted on an existing CDN, a document controlled by a third party. The URL mode allows referencing such content, but it requires an `integrity` field containing a hash of the content at the time of authorship. This is not optional: URL content is mutable (the URL can serve different bytes on different requests), so without the hash, there is no way to detect tampering or content substitution. A verifier that fetches the URL and finds the hash does not match should treat the content as invalid, not just stale.

```json
{
  "mode": "url",
  "url": "https://cdn.example/photo.jpg",
  "integrity": "sha256-abc123...",
  "mediaType": "image/jpeg"
}
```

**Stream**: Live content via WebSocket or SSE. This mode is for content that does not exist as a stored file — a live video broadcast, a real-time data feed, a live audio stream. The activity carries an endpoint URL and protocol identifier. No content hash is possible by definition: the content is being generated in real time and its final form does not exist at the time the activity is created. Stream-mode activities are the exception that proves the rule: for everything except genuinely live content, some form of hash-verified reference is possible and required.

```json
{
  "mode": "stream",
  "endpoint": "wss://birdsite.example/live/event-42",
  "protocol": "websocket",
  "mediaType": "video/mp4"
}
```

**Chunked**: Large files split into segments described by a MediaManifest. The `manifest` field holds the CID of a `corundum:MediaManifest` object (described in Chapter 16) that lists every chunk of the file. This is the mode for video files, long audio recordings, and any content that is too large to store as a single IPFS object or that requires range-access for streaming playback.

```json
{
  "mode": "chunked",
  "manifest": "bafyreic3d2vekw73m2esv7m3n7ldvikfojqxj3u5ufwtfpwjw6uktrnxlcbq",
  "mediaType": "video/mp4",
  "size": 847362048
}
```

The mode system is extensible via URI-based identifiers. A new storage backend — say, a Filecoin-addressed retrieval system or an operator-proprietary CDN with its own authentication — can be registered as a new content mode using a URI identifier in the `mode` field. Operators and clients that don't recognize a mode fall back to `url` mode if a fallback URL is provided, or treat the content as unavailable. This means new storage backends can be introduced without changing the protocol: activities referencing novel modes remain valid Corundum objects, and the ecosystem adopts them as implementations add support.

### Chapter 16: Chunked Media

IPFS works best with objects under a few hundred megabytes — objects that fit comfortably in memory and can be retrieved as a unit. A 45-minute 1080p video is 3–4 GB. A feature film at broadcast quality is larger still. These do not fit in a single IPFS object in any practical sense, and even if they did, streaming playback would still require fetching the entire file before the viewer could start watching. Range access — seeking to minute 32 without downloading the first 31 minutes — is essential for any real media experience. CDN architectures and adaptive bitrate protocols like HLS and DASH are built around the same idea: they serve small segments (2–6 seconds each), not monolithic files, because segments can be independently cached, independently delivered from the nearest edge node, and dynamically substituted when bandwidth drops. Corundum's chunked media system mirrors this architecture at the protocol level.

**The MediaManifest structure.** A `corundum:MediaManifest` is a content-addressed document that describes a complete media file in terms of its constituent chunks. Each chunk is individually stored as an IPFS object and described by a `ChunkRef` with four fields: `seq` (sequence number), `cid` (IPFS CID of the chunk's bytes), `byteRange` (inclusive start and exclusive end byte offset within the full file), and `timeRange` (start and end timestamps in seconds, for audio/video; omitted for non-temporal content). The manifest's top-level metadata includes `mimeType`, `codec` (a string in the format used by HTML5's `codecs=` attribute), `totalSize` in bytes, and `duration` in seconds for temporal media.

**Quality variants.** A single `MediaManifest` can declare multiple quality variants via a top-level `variants` array. Each variant entry carries a human-readable `label` (e.g., `"1080p"`), a `bitrate` in bits per second, and a `manifest` CID pointing to another `MediaManifest` for that quality level. The client chooses a variant based on current bandwidth, screen resolution, or user preference, then fetches chunks from that variant's manifest. Where possible — for keyframe-aligned segmentation — lower-quality variants share chunk CIDs with higher-quality ones for segments that encode identically; this reduces storage and simplifies curation (flagging the manifest flags all variants simultaneously).

**Streaming access pattern.** The client fetches the `MediaManifest` (one small JSON document), selects a variant, and then requests chunks by CID in sequence number order. Because chunks are individually CID-addressed, they can be served from any source that has them: the operator's IPFS node, a CDN with IPFS pinning, a dedicated media delivery server at `https://cdn.operator.example/ipfs/{cid}`, or any IPFS gateway. The client does not need to know where the chunks are stored — the CID is sufficient. It fetches chunk 0, starts playback immediately while fetching chunk 1, and so on. Seeking to a timestamp means finding the `ChunkRef` whose `timeRange` contains the target time, then fetching from that chunk forward. No special server-side range-request support is needed; it's just fetching a different set of chunks.

**Upload protocol.** The upload flow is designed so that connection interruptions don't require starting over. The client begins by POSTing to `/upload` to create a session, receiving a session ID in response. It then PUTs chunks identified by sequence number (`/upload/{sessionId}/chunks/{seq}`), in any order — there is no requirement to upload sequentially, so parallel connections are encouraged. The operator verifies each chunk's hash before acknowledging it; a chunk whose bytes don't match the expected CID is rejected immediately, so errors are caught at upload time rather than playback time. Once all chunks are uploaded, the client POSTs to `/upload/{sessionId}/finalize` with the complete chunk list (sequence numbers, CIDs, byte ranges, time ranges) and top-level metadata. The operator creates the `MediaManifest` document, pins it to IPFS, and returns the `MediaManifest` CID. That CID goes into the activity's `ContentRef` with `mode: "chunked"`.

Here is a concrete `MediaManifest` example:

```json
{
  "@type": "corundum:MediaManifest",
  "id": "bafyreic3d2vekw73m2esv7m3n7ldvikfojqxj3u5ufwtfpwjw6uktrnxlcbq",
  "mimeType": "video/mp4",
  "codec": "avc1.64001F,mp4a.40.2",
  "totalSize": 847362048,
  "duration": 3612.4,
  "chunks": [
    {
      "seq": 0,
      "cid": "bafyreiexamplechunk0ccccccccccccccccccccccccccccccccccccccccc",
      "byteRange": [0, 4194303],
      "timeRange": [0.0, 4.0]
    },
    {
      "seq": 1,
      "cid": "bafyreiexamplechunk1ccccccccccccccccccccccccccccccccccccccccc",
      "byteRange": [4194304, 8388607],
      "timeRange": [4.0, 8.0]
    }
  ],
  "variants": [
    {
      "label": "1080p",
      "bitrate": 8000000,
      "manifest": "bafyreic3d2vekw73m2esv7m3n7ldvikfojqxj3u5ufwtfpwjw6uktrnxlcbq"
    },
    {
      "label": "720p",
      "bitrate": 4000000,
      "manifest": "bafyreiabc720pmanifestccccccccccccccccccccccccccccccccccccccc"
    },
    {
      "label": "480p",
      "bitrate": 2000000,
      "manifest": "bafyreidef480pmanifestccccccccccccccccccccccccccccccccccccccc"
    }
  ]
}
```

The upload protocol also supports operator-side transcoding: the client uploads the source file in a single quality (or even raw uncompressed), and the operator's transcoding pipeline generates the lower-quality variants, creating a `MediaManifest` with a populated `variants` array. This is optional — clients that pre-encode their own variants can supply the complete chunk lists at finalization — but it simplifies the client's job for the common case of a single upload.

---

