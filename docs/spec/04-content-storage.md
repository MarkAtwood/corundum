## Part IV: Content Storage

### Chapter 9: The Archive Structure

A user's content is stored in IPFS as a content-addressed tree. This structure is the core data structure that makes Corundum's performance, portability, and integrity guarantees possible. Understanding it requires understanding why content-addressing provides integrity: the CID (Content IDentifier) of an IPFS object IS the cryptographic hash of that object's content. You cannot change an object and keep its CID. If someone hands you an IPFS CID, and you fetch an object with that CID, you know with certainty that you have exactly the content that was addressed — any modification would have changed the hash and thus the CID.

This property makes the entire archive self-verifying. The signed RootManifest contains the CID of the ArchiveIndex. The ArchiveIndex contains the CIDs of IndexPages. Each IndexPage contains the CIDs of epochs. Each epoch contains the CIDs of entries. Each entry contains the CID of an activity. Change any piece of content anywhere in the tree, and the CID chain breaks. The only way to produce a valid archive is to have the original content. This is why Corundum removed the original hash chain and intra-epoch Merkle tree that appeared in early drafts: they were redundant. IPFS content-addressing provides all the tamper detection you need, without any additional data structure.

**What the archive provides:**

- Append a new entry in O(1) time — add to the current chunk
- Retrieve the most recent content in O(1) time — read the current chunk
- Look up any entry by sequence number in O(1) time — the ArchiveIndex lookup procedure below
- Detect omitted or reordered entries via monotonically increasing sequence numbers
- Synchronize between operators efficiently by comparing epoch CIDs — only differing epochs need to be exchanged

**Structure:**

At the top is the **RootManifest**, the mutable entry point for a user's entire Corundum presence. It is pointed to by the user's IPNS name and contains:

- Identity block (the user's DID, display name, avatar)
- Operator declaration (current operator endpoint, when declared)
- Timeline pointer (latest entry sequence number, total count, current chunk CID, archive root CID)
- Social graph pointer (CID of following list, block list, mute list)
- Migration audit trail (CID of append-only migration history)

The RootManifest is stored as an attached JWS (Chapter 34) with `corundumType` `"RootManifest"`, signed by every content-signing key the user's DID document currently lists.

Below the RootManifest is the **timeline**, organized in two tiers:

**The current chunk** is a mutable array of recent timeline entries (up to 256 entries by default). New posts are appended here. This is the "hot" data — it changes whenever the user posts. The current chunk is referenced by CID from the RootManifest's timeline pointer. When a new post is added, a new current chunk object (with the new entry added) is created, producing a new CID, and the RootManifest is updated to reference the new CID.

**The archive** consists of immutable **epochs**. When the current chunk fills up (reaches 256 entries), it is finalized into an epoch: the chunk becomes immutable and is referenced by a permanent CID. A new empty current chunk is started. Epochs are never modified after finalization. Each epoch covers a fixed sequence range (entries 0–255, 256–511, etc.).

**The ArchiveIndex** provides O(1) lookup by sequence number regardless of how large the archive has grown.

- **Top-level ArchiveIndex**: a small array of IndexPageRefs, stored as an IPFS object and referenced from the RootManifest. Each IndexPageRef records: startEpochIndex, endEpochIndex, and the CID of an IndexPage.
- **IndexPage**: an array of up to 256 EpochRefs. Each EpochRef records: startSeq, endSeq, and the CID of the epoch.

To find entry with sequence number N:

1. Compute `epoch_index = floor(N / 256)`. This tells you which epoch contains entry N.
2. Fetch the top-level ArchiveIndex from the RootManifest. Scan the IndexPageRefs to find which IndexPage covers `epoch_index`.
3. Fetch that IndexPage. Index into it at position `epoch_index mod 256` to get the EpochRef.
4. Fetch the epoch object at the EpochRef's CID. Index into it at position `N mod 256` to get the entry.

As a worked example: entry #65,792. `floor(65792 / 256) = 257`, so this is epoch 257. It lives in the second IndexPage (which covers epochs 256–511). Fetch the ArchiveIndex → find IndexPage 1 → fetch IndexPage 1 → find the EpochRef at position `257 mod 256 = 1` → fetch the epoch → find entry at position `65792 mod 256 = 0`. Four IPFS fetches, regardless of how large the archive is.

This keeps every fetched object small regardless of archive size. A user with 100 million posts requires a top-level ArchiveIndex of approximately 1,526 entries (~229 KB) — the largest realistic case. The signed RootManifest commits to the ArchiveIndex CID, which commits to all IndexPage CIDs, which commit to all epoch CIDs, which commit to all their entries — the entire archive is verifiable from the single RootManifest signature.

### Chapter 10: Timeline Entries

Each timeline entry (`corundum:Entry`) is a small JSON object that represents one item in a user's timeline. An example:

```json
{
  "@type": "corundum:Entry",
  "seq": 1042,
  "ts": "2025-03-15T14:22:11Z",
  "content": "bafyreib2vekw73m2esv7m3n7ldvikfojqxj3u5ufwtfpwjw6uktrnxlcbq",
  "contentHash": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "signingRecord": "bafyreidqw3bxjpkbkwrmtxjt4pjyatnmhfhz3eqcl3jkn6p2olbqgfptay",
  "replies": "bafyreifmjdshxl2e6vmizllwxbmzfkpptzdqkgzwh7h5fefkptwnllycqi",
  "retention": {
    "status": "active"
  }
}
```

Each field has a specific role. `seq` is the monotonically increasing sequence number. It is the primary integrity mechanism: if entries are omitted or reordered, the gaps or inversions in sequence numbers are immediately detectable. This is why hash chains (where each entry contains the hash of the previous entry) were not added — sequence numbers achieve the same detection with less complexity and without requiring linear traversal to verify any given entry.

`content` is the CID of the unsigned activity object. `contentHash` is the SHA-256 hash of the original content, preserved even after deletion — if the content is later tombstoned and the IPFS object is unpinned, the contentHash remains as a record of what existed. `signingRecord` is the CID of the detached signing record that establishes authorship (discussed in the next chapter). `replies` is the CID of the operator-managed reply tree. `retention` carries expiration metadata.

### Chapter 11: Activity Objects

Activity objects are the actual content: the posts, images, articles, events, and other things users create. They follow the ActivityStreams 2.0 data model but Corundum uses only the data objects, not the ActivityPub protocol.

Here is an example Note (a short text post) in its unsigned form, with the common optional fields shown:

```json
{
  "@context": [
    "https://www.w3.org/ns/activitystreams",
    "https://corundum.example/ns/v1"
  ],
  "@type": "Note",
  "attributedTo": "did:webvh:<SCID>:birdsite.example:users:alice",
  "content": "Just finished the most fascinating book on distributed systems.",
  "published": "2025-03-15T14:22:11Z",
  "language": "en",
  "sensitive": false,
  "tag": [
    {"type": "Hashtag", "name": "#distributedsystems"},
    {"type": "Hashtag", "name": "#books"}
  ],
  "to": ["https://www.w3.org/ns/activitystreams#Public"]
}
```

An example reply with a content warning:

```json
{
  "@context": [
    "https://www.w3.org/ns/activitystreams",
    "https://corundum.example/ns/v1"
  ],
  "@type": "Note",
  "attributedTo": "did:webvh:<SCID>:birdsite.example:users:alice",
  "inReplyTo": "bafyreib2vekw73m2esv7m3n7ldvikfojqxj3u5ufwtfpwjw6uktrnxlcbq",
  "content": "This reminds me of the incident in 2003 where...",
  "summary": "Discussion of historical system failure",
  "sensitive": true,
  "published": "2025-03-15T14:25:03Z",
  "language": "en",
  "to": ["https://www.w3.org/ns/activitystreams#Public"]
}
```

**Key fields in the activity object:**

`attributedTo` is the author's DID. This is the primary authorship claim: the signing record must carry signatures from the content keys that this DID's document lists (Chapter 34).

`published` is the author-declared timestamp. It is signed as part of the activity, so it represents what the author claimed the publication time to be. Operators may add their own receipt timestamps, but the `published` field is the author's timestamp.

`language` is a BCP 47 language tag (`"en"`, `"zh-Hant"`, `"fr-CA"`). This is used by operators for language-specific filtering and feed construction, and by client apps for localization decisions. It is optional: if omitted, the language is unspecified. Operators should not attempt to infer language from content; if the author didn't declare it, treat it as unknown.

`sensitive` is a boolean content warning flag. `true` means the author has flagged this content as potentially sensitive. Client apps use this to decide whether to show the content behind a click-through warning. The `summary` field (if present) provides the content warning text: a brief description of what the sensitive content is, shown to the user before they click through. If `sensitive` is `false` or absent, `summary` is used as a subtitle or excerpt (standard ActivityStreams semantics).

`inReplyTo` is the identifier of the activity being replied to. Its presence is what triggers the reply protocol: when an operator processes a new activity with `inReplyTo` set, it must route the activity through the inter-operator reply submission process to the parent post's author's operator.

`tag` contains hashtags (type `Hashtag`), mentions (type `Mention`), and emoji reactions. Hashtags are used for feed discovery; mentions notify the mentioned user's operator. Mentions carry the DID of the mentioned user alongside the display handle, so the operator can route the mention notification without a separate identity lookup:

```json
"tag": [
  {"type": "Hashtag", "name": "#distributedsystems"},
  {
    "type": "Mention",
    "name": "@alice@birdsite.example",
    "href": "did:webvh:<SCID>:birdsite.example:users:alice"
  }
]
```

**Boost (reshare).** A Boost is an activity of type `Announce` in ActivityStreams 2.0. It represents a user resharing another user's post to their own followers:

```json
{
  "@context": ["https://www.w3.org/ns/activitystreams", "https://corundum.example/ns/v1"],
  "@type": "Announce",
  "attributedTo": "did:webvh:<SCID>:meetup.example:users:bob",
  "object": "bafyreib2vekw73m2esv7m3n7ldvikfojqxj3u5ufwtfpwjw6uktrnxlcbq",
  "published": "2025-03-15T16:00:00Z",
  "to": ["https://www.w3.org/ns/activitystreams#Public"]
}
```

The `object` field is the identifier of the boosted activity. The Boost is its own signed activity in Bob's timeline; Alice's original post is referenced by CID, not embedded. This means boosting the same post twice creates two Boost activities with the same `object` — the operator can detect and deduplicate these.

When Bob's operator processes a Boost, it notifies Alice's operator (via a lightweight notification, not through the reply protocol — Boosts are not replies). Alice's operator records that Bob boosted her post; Alice's app might show a "Bob boosted this" indicator.

**Reactions (likes and custom reactions).** Reactions are lightweight activity objects stored in the reacting user's timeline but not submitted to the target via the reply protocol:

```json
{
  "@context": ["https://www.w3.org/ns/activitystreams", "https://corundum.example/ns/v1"],
  "@type": "Like",
  "attributedTo": "did:webvh:<SCID>:birdsite.example:users:alice",
  "object": "bafyreib2vekw73m2esv7m3n7ldvikfojqxj3u5ufwtfpwjw6uktrnxlcbq",
  "published": "2025-03-15T14:30:00Z"
}
```

Custom emoji reactions use the `EmojiReact` type from the Corundum namespace extension, with a `content` field containing the emoji or its identifier:

```json
{
  "@context": ["https://www.w3.org/ns/activitystreams", "https://corundum.example/ns/v1"],
  "@type": "corundum:EmojiReact",
  "attributedTo": "did:webvh:<SCID>:birdsite.example:users:alice",
  "object": "bafyreib2vekw73m2esv7m3n7ldvikfojqxj3u5ufwtfpwjw6uktrnxlcbq",
  "content": "🎉",
  "published": "2025-03-15T14:30:01Z"
}
```

Reactions (Like, EmojiReact, Bookmark) are stored in the reacting user's own timeline. The ATD for the target post declares which reaction types are supported; operators that support the same reaction vocabulary display aggregate reaction counts by fetching from their users' timelines and the timelines of followed users. The operator notifies the target activity's author's operator when a reaction is published, so the author can see it in their notifications.

Activities have no `id` field. An activity's identifier is the CID of its stored bytes (Chapter 33): a CIDv1 with the `raw` codec and a SHA-256 multihash. It is the same value as the activity's IPFS storage CID. All cross-references, such as `inReplyTo` and `object`, use it. The activity is stored exactly as its author wrote it and is never re-serialized, so the identifier never changes.

**Unsigned storage** is perhaps the most counterintuitive design decision in Corundum. Why store posts without signatures? Two reasons:

First, raw IPFS fetchability. Anyone can fetch an activity directly from IPFS by its identifier, without going through any operator API, and verify it by hashing the bytes received.

Second, re-signing without changing identity. A signature inside the activity would be part of its bytes, so adding a signature (for example, a post-quantum one) would change the identifier and break every reference to the post. Keeping signatures outside lets them be added without changing the activity.

An identifier names one post, not a piece of text: the same words posted by two users are two activities with different identifiers. Curation that needs to match the same text or media wherever it appears uses the content hash types of Chapter 28.

Authorship is established separately, by the signing record described in the next chapter.

### Chapter 12: Signing Records

Since activities are stored unsigned, how does a reader know who created a post? The answer is a separate **SigningRecord** object, stored in IPFS alongside the activity and referenced from the Entry.

A SigningRecord is a detached JWS (Chapter 34) over the activity's stored bytes, in the General JSON Serialization:

```json
{
  "signatures": [
    {
      "protected": "<base64url of the protected header>",
      "signature": "<base64url of the Ed25519 signature>"
    }
  ]
}
```

The protected header, before base64url encoding, looks like this:

```json
{"alg":"Ed25519","b64":false,"crit":["b64","corundumType"],"corundumType":"Activity","kid":"<IPNS name of the signing key>"}
```

There is no `payload` member: the payload is the activity itself, which the verifier fetches by identifier or already holds. A SigningRecord does not name the activity it signs; it verifies against the activity's bytes or it does not verify at all. Chapter 34 defines the header parameters, the verification procedure, and which keys are authorized to sign.

The signature is detached because the activity's identifier is the hash of its bytes. A signature inside the activity would be part of those bytes, so adding a signature would change the identifier. With detached signatures, the activity never changes.

**Resignatures.** Re-signing an activity, for example to add a post-quantum signature, produces a new SigningRecord containing all of the activity's signatures. The activity and its identifier are unchanged. The Entry in the archive keeps the CID of the original SigningRecord, because the archive tree never changes once written. The new SigningRecord is published outside the archive tree, alongside the activity's other changing state (Chapter 10). Re-signing is never required to keep old content verifiable, because archived content is authenticated by inclusion in the current RootManifest (Chapter 34).

**Reply submissions** include the signing record inline (not by CID), so the receiving operator does not need a separate IPFS fetch for it during reply validation.

**Out-of-band verification**: fetch the activity from IPFS by its identifier, fetch the signing record by the CID in the entry's `signingRecord` field, and verify the signature. Both objects can be fetched directly from IPFS; no operator API is required.

### Chapter 13: Deletion and Editing

Content deletion in Corundum involves a tension that the protocol handles explicitly: IPFS content-addressing is designed for permanence (the whole point is that content addressed by CID is immutable and indefinitely retrievable), but GDPR and user expectations both require that users be able to delete their content.

Corundum resolves this tension by distinguishing between *archive integrity* and *content availability*. The archive structure — the ArchiveIndex, IndexPages, epochs, entries — must remain structurally complete for verification to work. You cannot remove an entry from an epoch without changing the epoch's CID, which would break the ArchiveIndex, which would break the signed RootManifest. The structural skeleton must remain intact.

What can be removed is the *content* the entry points to. When a user deletes a post:

1. A **tombstone** object is published to IPFS, recording who deleted the content, when, and why.
2. The entry's `content` field is set to null (the activity CID is removed).
3. The entry's `contentHash` is preserved (a record of what existed, without the content itself).
4. The entry's `tombstone` field is set to the CID of the tombstone object.
5. The operator unpins the original activity from its IPFS node. If no other operator has pinned it, the content becomes unavailable on the network.

A tombstone object:

```json
{
  "@type": "corundum:Tombstone",
  "deletedContent": "bafyreib2vekw73m2esv7m3n7ldvikfojqxj3u5ufwtfpwjw6uktrnxlcbq",
  "deletedBy": "did:webvh:<SCID>:birdsite.example:users:alice",
  "deletedAt": "2025-03-20T09:14:00Z",
  "reason": "user-request",
  "retainUntil": null
}
```

`deletedContent` is the CID of the activity that was deleted. `deletedBy` is the DID of the user who deleted it (always the author in a standard deletion; may be an operator in a curation-mandated removal). `reason` is one of: `user-request` (user's own deletion), `curation-removal` (operator removed content per curation policy), `operator-policy` (operator policy override), or `legal-hold-release` (content retained under legal hold and now released). `retainUntil` is set when a legal hold requires the content to be retained despite the deletion request; it is the date when the hold expires and the content may be physically deleted.

The tombstone is published to IPFS (it gets its own CID), making it independently verifiable: anyone can check that a legitimate deletion occurred and when.

The GDPR compliance argument is: the deleted content is removed from all operator-controlled storage (unpinned). The content hash that remains in the entry is not the content itself; it is a fixed-length digest. Retaining a hash of deleted content is analogous to retaining a record that a message existed — something systems routinely do for audit purposes without retaining the message content.

The content remains in the archive *structurally* (the entry still exists, the sequence numbers are still contiguous), but the content itself is no longer available. This is the correct tradeoff: archive integrity is preserved, GDPR deletion is respected, and the deletion is recorded in the tombstone for transparency.

**Legal holds** complicate this. If a curator has issued a legal hold on a piece of content (e.g., it's evidence in a CSAM investigation), the operator may be legally prohibited from unpinning it even if the user requests deletion. The `retainUntil` field in the tombstone records this hold. The content is hidden from display but retained in storage until `retainUntil` passes. The operator must document why the deletion request was not honored.

**Edits** in a content-addressed system are necessarily non-destructive. You cannot change an IPFS object; changing the content changes the CID. An "edit" in Corundum means publishing a new version of the activity and updating the entry to point to it, while preserving the history.

The edit procedure:
1. Create the revised activity object (without `id`) and compute its new CID.
2. Publish an `EditRecord` to IPFS that links the original activity CID to the new activity CID.
3. Update the timeline entry: set `content` to the new activity CID, set `editRecord` to the CID of the EditRecord, retain `contentHash` of the original version.

The `EditRecord`:

```json
{
  "@type": "corundum:EditRecord",
  "originalContent": "bafyreib2vekw73m2esv7m3n7ldvikfojqxj3u5ufwtfpwjw6uktrnxlcbq",
  "revisedContent": "bafyreid7new4contentcid...",
  "editedBy": "did:webvh:<SCID>:birdsite.example:users:alice",
  "editedAt": "2025-03-16T08:30:00Z",
  "editNote": "Fixed typo in title"
}
```

Editing is subject to the same operator policies as the ATD of the post type. The `Note` ATD allows edits; some ATDs (e.g., `Poll`) may prohibit editing after the first response has been recorded, since editing a poll question after votes have been cast would be dishonest.

Content **expiration** is also supported. The `expires` field in the retention metadata lets an author specify that content should stop being displayed after a certain time — like social media "Stories" that disappear after 24 hours. Expired content remains in the archive for integrity, but operators should not display it. Expiration is distinct from deletion: expired content was not deleted by user request; it was designed to expire from the start.

---

