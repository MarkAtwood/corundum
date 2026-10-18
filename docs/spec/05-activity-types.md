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
      { "name": "content", "type": "string" }
    ],
    "optional": [
      { "name": "attachment", "type": "array", "items": "ContentRef", "modes": ["ipfs", "chunked", "url"] },
      { "name": "summary", "type": "string", "maxLength": 500 },
      { "name": "sensitive", "type": "boolean" },
      { "name": "inReplyTo", "type": "cid" },
      { "name": "quoting", "type": "cid" },
      { "name": "language", "type": "bcp47" },
      { "name": "expiresAt", "type": "datetime" }
    ]
  },
  "contentConstraints": {
    "maxContentBytes": 5000
  },
  "replyTypes": ["Note"],
  "reactions": ["like", "bookmark"],
  "activityStreamsMapping": {
    "type": "Note",
    "contentField": "content"
  }
}
```

This ATD says: a Note requires a `content` string of at most 5,000 bytes of UTF-8, allows optional media `attachment`s (Chapter 15) and optional `summary`, `sensitive`, `inReplyTo`, `quoting`, `language`, and `expiresAt` fields, accepts Note replies (not Article replies), supports like and bookmark reactions, and maps to an ActivityStreams 2.0 `Note` object for non-Corundum interoperability.

Anyone can publish a new ATD. If Meetup wants to define an ATD for structured event RSVPs that carries venue capacity, accessibility information, and calendar invite data, they publish an ATD document to IPFS and share its CID. Operators can discover it, fetch it, and decide whether to support it. Birdsite might decide to render Meetup's ATD natively (showing a rich event card); a minimal operator might fall back to the ActivityStreams translation mapping. An activity that follows a published ATD names it by CID in its `atd` field (Chapter 11), so validators can always resolve the exact schema version used. An activity without `atd` follows the standard ATD for its `@type`. Every activity, whatever its ATD, is limited to 1,048,576 bytes (Chapter 33); larger content goes in attachments.

This extensibility mechanism is what allows the Corundum ecosystem to innovate in content types without requiring protocol changes. New types are additive; they don't break existing implementations that don't support them.

### Chapter 15: Content Reference Modes

Every activity references its content through a `ContentRef` object that specifies a delivery mode. The most important thing to understand about this design is why content is not simply embedded in the activity JSON by default.

Activities are CID-addressed: the identifier of an activity is the hash of its bytes, and an activity is at most 1 MiB (Chapter 33). Embedding a 4 MB image as a base64 blob in a JSON activity makes the activity's CID useless as a cache key, blows up JSON parsing in relay pipelines, and means that two different activities referencing the same image (say, two people boosting the same photo) each carry a separate copy instead of sharing one. Separating content reference from content data lets the activity remain small, stable, and CID-stable, while the content itself is stored and deduplicated by whatever storage system is most appropriate for its type and size.

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

A file referenced in `ipfs` mode is stored as a UnixFS file DAG built with fixed parameters, so that anyone who has the file computes the same CID: CIDv1, SHA-256, raw leaves, a fixed-size chunker of 1,048,576 bytes, and the balanced layout with at most 174 links per node. (In Kubo these are `ipfs add --cid-version=1 --raw-leaves --chunker=size-1048576`.) Operators MUST verify an uploaded file's CID with these parameters before accepting it.

```json
{
  "mode": "ipfs",
  "cid": "<CID of the file>",
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

**Chunked**: Large files split into segments described by a MediaManifest. The `manifest` field holds the CID of a `corundum:MediaManifest` object (described in Chapter 16) that lists every chunk of the file. This is the mode for video files, long audio recordings, and other media that needs seeking or adaptive bitrate playback.

```json
{
  "mode": "chunked",
  "manifest": "<CID of the MediaManifest>",
  "mediaType": "video/mp4",
  "size": 847362048
}
```

The mode system is extensible via URI-based identifiers. A new storage backend — say, a Filecoin-addressed retrieval system or an operator-proprietary CDN with its own authentication — can be registered as a new content mode using a URI identifier in the `mode` field. Operators and clients that don't recognize a mode fall back to `url` mode if a fallback URL is provided, or treat the content as unavailable. This means new storage backends can be introduced without changing the protocol: activities referencing novel modes remain valid Corundum objects, and the ecosystem adopts them as implementations add support.

### Chapter 16: Chunked Media

IPFS already splits every large file into blocks of about 1 MiB, so size alone is not a reason to chunk media. The reasons are playback: seeking to minute 32 without downloading the first 31 minutes, and switching quality when bandwidth changes. Adaptive bitrate protocols like HLS and DASH are built around the same idea: they serve small segments (2–6 seconds each), not monolithic files, because segments can be independently cached, independently delivered from the nearest edge node, and dynamically substituted when bandwidth drops. Corundum's chunked media system mirrors this architecture at the protocol level.

**The MediaManifest structure.** A `corundum:MediaManifest` describes one encoding of a media file as a sequence of segments. Its identifier is its CID (Chapter 33); it has no `id` field. Each segment is stored as its own file, with the same fixed UnixFS parameters as `ipfs` mode (Chapter 15), and is described by a `ChunkRef`:

| Member | Meaning |
|---|---|
| `seq` | Segment number, starting at 0. |
| `cid` | CID of the segment's bytes. |
| `timeRange` | Start and end time in seconds, for audio and video. |
| `byteRange` | Optional. Start offset (inclusive) and end offset (exclusive) of the segment within the original file, when the segments are byte ranges of one file. |

The manifest's top-level metadata includes `mimeType`, `codec` (a string in the format used by HTML5's `codecs=` attribute), `totalSize` in bytes, and `duration` in seconds for temporal media.

**Quality variants.** Different encodings of the same media never share segments, because two encodings are never byte-identical. A **MediaVariants** object (`corundum:MediaVariants`) lists the encodings, each with a human-readable `label` (e.g., `"1080p"`), a `bitrate` in bits per second, and the CID of that encoding's MediaManifest. An activity's `chunked` ContentRef names either a single MediaManifest or a MediaVariants object. The client chooses a variant based on current bandwidth, screen resolution, or user preference, then fetches segments from that variant's manifest. Curation applies to each encoding separately, because each has different bytes.

**Streaming access pattern.** The client fetches the manifest (one small JSON document), and then requests segments by CID in sequence order. Because segments are individually CID-addressed, they can be served from any source that has them: the operator's IPFS node, a CDN with IPFS pinning, a dedicated media delivery server at `https://cdn.operator.example/ipfs/{cid}`, or any IPFS gateway. The client does not need to know where the segments are stored — the CID is sufficient. It fetches segment 0, starts playback immediately while fetching segment 1, and so on. Seeking to a timestamp means finding the `ChunkRef` whose `timeRange` contains the target time, then fetching from that segment forward. No special server-side range-request support is needed; it's just fetching a different set of segments.

**Uploading** is between a client and its own operator, so it is not part of the protocol. `docs/client-api/08-media.md` describes a resumable upload API for the reference implementation. Whatever the upload API, the operator verifies every segment's CID before accepting it.

Here is a `MediaVariants` object and one of the MediaManifests it names:

```json
{
  "@type": "corundum:MediaVariants",
  "variants": [
    { "label": "1080p", "bitrate": 8000000, "manifest": "<CID of the 1080p MediaManifest>" },
    { "label": "720p", "bitrate": 4000000, "manifest": "<CID of the 720p MediaManifest>" }
  ]
}
```

```json
{
  "@type": "corundum:MediaManifest",
  "mimeType": "video/mp4",
  "codec": "avc1.64001F,mp4a.40.2",
  "totalSize": 847362048,
  "duration": 3612.4,
  "chunks": [
    { "seq": 0, "cid": "<CID of segment 0>", "timeRange": [0.0, 4.0] },
    { "seq": 1, "cid": "<CID of segment 1>", "timeRange": [4.0, 8.0] }
  ]
}
```

A MediaManifest is limited to 1 MiB like every other Corundum object, which allows several thousand segments. Media long enough to need more uses longer segments.

---

