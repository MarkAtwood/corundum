## Part IV: Content Storage

### Chapter 9: The Archive Structure

A user's content is stored in IPFS as a content-addressed tree. This structure is the core data structure that makes Corundum's performance, portability, and integrity guarantees possible. Understanding it requires understanding why content-addressing provides integrity: the CID (Content IDentifier) of an IPFS object IS the cryptographic hash of that object's content. You cannot change an object and keep its CID. If someone hands you an IPFS CID, and you fetch an object with that CID, you know with certainty that you have exactly the content that was addressed — any modification would have changed the hash and thus the CID.

This property makes the entire archive self-verifying. The signed RootManifest contains the CID of the ArchiveIndex. The ArchiveIndex contains the CIDs of IndexPages. Each IndexPage contains the CIDs of epochs. Each epoch contains its entries, and each entry names an activity and its signing record by CID. Change any piece of content anywhere in the tree, and the CID chain breaks. The only way to produce a valid archive is to have the original content. This is why Corundum removed the original hash chain and intra-epoch Merkle tree that appeared in early drafts: they were redundant. IPFS content-addressing provides all the tamper detection you need, without any additional data structure.

**Nothing in the archive tree ever changes once written.** The rest of the design depends on this rule. Edits, deletions, re-signatures, and replies are recorded outside the tree (Chapter 10, Chapter 13), so an old epoch keeps its CID forever, can be cached forever, and lets any verifier detect an attempt to rewrite history (Chapter 34).

Corundum objects are stored as raw IPFS blocks (Chapter 33). IPFS itself therefore sees no links between them: the links are CID strings inside JSON, which Corundum software follows. An operator pins each object it keeps individually, and exporting an archive (for example, as a CAR file) is a traversal that Corundum software performs, not a recursive IPFS pin.

**What the archive provides:**

- Append a new entry in O(1) time — add to the current chunk
- Retrieve the most recent content in O(1) time — read the current chunk
- Look up any entry by sequence number in O(1) time — the ArchiveIndex lookup procedure below
- Detect omitted or reordered entries via monotonically increasing sequence numbers
- Synchronize between operators efficiently by comparing epoch CIDs — only epochs a peer does not yet have need to be exchanged

**Structure:**

At the top is the **RootManifest**, the mutable entry point for a user's entire Corundum presence. It is pointed to by the user's IPNS name and contains:

- Identity block (the user's DID, display name, avatar)
- Operator endpoint
- Timeline pointer (latest entry sequence number, current chunk CID, ArchiveIndex CID)
- StateMap CID: edits, deletions, and re-signatures (Chapter 10)
- ReplyMap: the IPNS name under which the user's operator publishes reply trees (Chapter 10)
- Social graph pointer (CIDs of the encrypted following list, block list, and mute list; Chapter 25)

The RootManifest is stored as an attached JWS (Chapter 34) with `corundumType` `"RootManifest"`, signed by every content-signing key the user's DID document currently lists. The history of the user's operators and keys is recorded by the DID log (Chapter 7), not by the RootManifest.

Below the RootManifest is the **timeline**, organized in two tiers:

**The current chunk** is a mutable array of recent timeline entries (up to 256 entries). New posts are appended here. This is the "hot" data — it changes whenever the user posts. The current chunk is referenced by CID from the RootManifest's timeline pointer. When a new post is added, a new current chunk object (with the new entry added) is created, producing a new CID, and the RootManifest is updated to reference the new CID.

**The archive** consists of immutable **epochs**. When the current chunk fills up (reaches 256 entries), it is finalized into an epoch: the chunk becomes immutable and is referenced by a permanent CID. A new empty current chunk is started. Each epoch covers a fixed sequence range (entries 0–255, 256–511, etc.).

**The ArchiveIndex** provides O(1) lookup by sequence number regardless of how large the archive has grown.

- **Top-level ArchiveIndex**: an array of IndexPageRefs, stored as an IPFS object and referenced from the RootManifest. Each IndexPageRef records: startEpochIndex, endEpochIndex, and the CID of an IndexPage.
- **IndexPage**: an array of up to 256 EpochRefs. Each EpochRef records: startSeq, endSeq, and the CID of the epoch.

To find the entry with sequence number N:

1. If N is at or above the first sequence number in the current chunk, the entry is in the current chunk, at position N minus that first sequence number. Stop.
2. Compute `epoch_index = floor(N / 256)` and `page_index = floor(epoch_index / 256)`.
3. Fetch the ArchiveIndex. The IndexPageRef at position `page_index` names the IndexPage.
4. Fetch that IndexPage. The EpochRef at position `epoch_index mod 256` names the epoch.
5. Fetch the epoch. The entry is at position `N mod 256`.

Verifiers check that each ref's recorded ranges contain the index they used, so a malformed index is detected rather than followed.

As a worked example: entry #65,792. `floor(65792 / 256) = 257`, so this is epoch 257, and `floor(257 / 256) = 1`, so it is in IndexPage 1 (epochs 256–511). Fetch the ArchiveIndex → IndexPageRef 1 → fetch IndexPage 1 → EpochRef at position `257 mod 256 = 1` → fetch the epoch → entry at position `65792 mod 256 = 0`. Three IPFS fetches after the RootManifest, regardless of how large the archive is. Resolving the RootManifest itself (Chapter 5) comes first and usually costs more than the lookup.

This keeps every fetched object small regardless of archive size. A user with 100 million posts requires a top-level ArchiveIndex of approximately 1,526 entries (~229 KB) — the largest realistic case. The signed RootManifest commits to the ArchiveIndex CID, which commits to all IndexPage CIDs, which commit to all epoch CIDs, which commit to all their entries — the entire archive is verifiable from the single RootManifest signature.

### Chapter 10: Timeline Entries and Changing State

Each timeline entry (`corundum:Entry`) is a small JSON object that represents one item in a user's timeline. An example:

```json
{
  "@type": "corundum:Entry",
  "seq": 1042,
  "content": "<activity id>",
  "signingRecord": "<SigningRecord CID>"
}
```

`seq` is the monotonically increasing sequence number. It is the primary integrity mechanism: if entries are omitted or reordered, the gaps or inversions in sequence numbers are immediately detectable. This is why hash chains (where each entry contains the hash of the previous entry) were not added — sequence numbers achieve the same detection with less complexity and without requiring linear traversal to verify any given entry. The entry's `seq` MUST equal the `seq` field of the activity it names (Chapter 11); a verifier rejects an entry where they differ.

`content` is the identifier of the activity (Chapter 11). `signingRecord` is the CID of the SigningRecord made when the activity was published (Chapter 12).

**An entry never changes.** Everything about a post that can change after it is published lives in one of two side structures, which have the same shape as the archive so that they can be looked up the same way.

**Sequence maps.** A sequence map associates values with sequence numbers. It has the same three levels as the archive: a top-level index of page refs, index pages of up to 256 refs, and leaf pages of 256 slots, one per sequence number in an epoch. Slot `N mod 256` of the leaf page for epoch `floor(N / 256)` holds the value for sequence number N, or `null`. A leaf page exists only for epochs that have at least one value; the ref to a missing page is `null`. Unlike the archive, a sequence map is mutable: changing a value rewrites one leaf page, one index page, and the top-level index, and does not touch the archive.

**The StateMap** is the author's sequence map. It records what the author has done to a post since publishing it. Each slot holds an `EntryState` object with any of these members:

| Member | Meaning |
|---|---|
| `replacedBy` | Identifier of the activity that replaces this one (an edit; Chapter 13). |
| `deletedBy` | Identifier of the `Delete` activity that deletes this one (Chapter 13). |
| `signingRecord` | CID of the current SigningRecord, when the activity has been re-signed (Chapter 12). |

The RootManifest names the StateMap's top-level index, so the StateMap is signed by the author's content keys like everything else the manifest commits to. Every value in it points at something independently verifiable. A reader that acts on `replacedBy` or `deletedBy` MUST fetch the named activity and check that it is authentic (Chapter 34), by the same author, and names this post in its `replaces` or `object` field. The StateMap is an index over signed facts, not a source of authority.

**The ReplyMap** is the operator's sequence map. Each slot holds the CID of the reply tree for that post (Chapter 21). Accepting replies is the decision of the post author's operator, so the ReplyMap is published by that operator, not by the author. Its top-level index is stored as an attached JWS (Chapter 34) with `corundumType` `"ReplyMap"`, signed with the operator's key, and published under an IPNS name that the operator controls. The RootManifest names that IPNS name. When a user moves to a new operator, the new operator publishes a new ReplyMap (starting from a copy of the old one, which it can fetch from IPFS), and the user's next RootManifest names it.

Keeping the two apart matters for users who hold their own content key. The operator accepts replies continuously and can update its ReplyMap without the user's key. The author changes their own StateMap only when they edit, delete, or re-sign, and they republish their RootManifest then anyway.

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
  "seq": 1042,
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
  "inReplyTo": "<identifier of Alice's post>",
  "content": "This reminds me of the incident in 2003 where...",
  "summary": "Discussion of historical system failure",
  "sensitive": true,
  "seq": 1043,
  "published": "2025-03-15T14:25:03Z",
  "language": "en",
  "to": ["https://www.w3.org/ns/activitystreams#Public"]
}
```

**Key fields in the activity object:**

`attributedTo` is the author's DID. This is the primary authorship claim: the signing record must carry signatures from the content keys that this DID's document lists (Chapter 34).

`seq` is the activity's position in its author's timeline, and MUST equal the `seq` of the entry that names it (Chapter 10). Carrying it in the activity lets anyone who holds only the activity's identifier find its slot in the author's StateMap and ReplyMap directly. Whoever publishes the author's RootManifest assigns it.

`published` is the author-declared timestamp. It is signed as part of the activity, so it represents what the author claimed the publication time to be. Operators may add their own receipt timestamps, but the `published` field is the author's timestamp.

`language` is a BCP 47 language tag (`"en"`, `"zh-Hant"`, `"fr-CA"`). This is used by operators for language-specific filtering and feed construction, and by client apps for localization decisions. It is optional: if omitted, the language is unspecified. Operators should not attempt to infer language from content; if the author didn't declare it, treat it as unknown.

`sensitive` is a boolean content warning flag. `true` means the author has flagged this content as potentially sensitive. Client apps use this to decide whether to show the content behind a click-through warning. The `summary` field (if present) provides the content warning text: a brief description of what the sensitive content is, shown to the user before they click through. If `sensitive` is `false` or absent, `summary` is used as a subtitle or excerpt (standard ActivityStreams semantics).

`inReplyTo` is the identifier of the activity being replied to. Its presence is what triggers the reply protocol: when an operator processes a new activity with `inReplyTo` set, it must route the activity through the inter-operator reply submission process to the parent post's author's operator.

`replaces` is present only on an edit: it is the identifier of the version this activity replaces (Chapter 13).

`expiresAt` is an optional RFC 3339 time after which operators stop displaying the activity, for content designed to disappear, like stories. It is the only place expiry is recorded (Chapter 39).

`atd` is an optional CID naming the Activity Type Definition the activity follows (Chapter 14). When it is absent, `@type` names one of the standard types.

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
  "object": "<identifier of Alice's post>",
  "seq": 1044,
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
  "object": "<identifier of Alice's post>",
  "seq": 1045,
  "published": "2025-03-15T14:30:00Z"
}
```

Custom emoji reactions use the `EmojiReact` type from the Corundum namespace extension, with a `content` field containing the emoji or its identifier:

```json
{
  "@context": ["https://www.w3.org/ns/activitystreams", "https://corundum.example/ns/v1"],
  "@type": "corundum:EmojiReact",
  "attributedTo": "did:webvh:<SCID>:birdsite.example:users:alice",
  "object": "<identifier of Alice's post>",
  "content": "🎉",
  "seq": 1046,
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

**Resignatures.** Re-signing an activity, for example to add a post-quantum signature, produces a new SigningRecord containing all of the activity's signatures. The activity and its identifier are unchanged. The Entry in the archive keeps the CID of the original SigningRecord, because the archive tree never changes once written. The new SigningRecord's CID goes in the activity's StateMap slot (Chapter 10), outside the archive tree. Re-signing is never required to keep old content verifiable, because archived content is authenticated by inclusion in the current RootManifest (Chapter 34).

**Reply submissions** include the signing record inline (not by CID), so the receiving operator does not need a separate IPFS fetch for it during reply validation.

**Out-of-band verification**: fetch the activity from IPFS by its identifier, fetch the signing record by the CID in the entry's `signingRecord` field, and verify the signature. Both objects can be fetched directly from IPFS; no operator API is required.

### Chapter 13: Deletion and Editing

Content deletion in Corundum involves a tension that the protocol handles explicitly: IPFS content-addressing is designed for permanence (the whole point is that content addressed by CID is immutable and indefinitely retrievable), but GDPR and user expectations both require that users be able to delete their content.

Corundum never removes or changes anything in the archive tree (Chapter 9). A deletion or an edit is a new activity, appended to the author's timeline like any other post and signed like any other post. What changes is what operators store and display.

**Deletion.** To delete a post, the author publishes a `Delete` activity naming it. The `Delete` activity is the post's *tombstone*:

```json
{
  "@context": ["https://www.w3.org/ns/activitystreams", "https://corundum.example/ns/v1"],
  "@type": "Delete",
  "attributedTo": "did:webvh:<SCID>:birdsite.example:users:alice",
  "object": "<identifier of the deleted activity>",
  "seq": 1107,
  "published": "2025-03-20T09:14:00Z"
}
```

Then:

1. The `Delete` activity is appended to the timeline with its own entry and SigningRecord.
2. The deleted activity's StateMap slot gets `deletedBy`, naming the `Delete` activity (Chapter 10).
3. The operator unpins the deleted activity and its SigningRecords from its IPFS node and stops serving them.
4. The operator notifies operators known to have fetched the content, which SHOULD unpin it (Chapter 39).

A receiver MUST NOT act on a `Delete` activity until it has verified that the activity is authentic (Chapter 34) and that its author is the author of the activity it names. Only the author can delete their post this way.

An operator that holds a user's content key MUST NOT use it to publish a `Delete` the user did not ask for. An operator that removes content for its own reasons — a curation judgment, its own policy, a legal order — does not speak for the author: it stops serving the content and unpins it, and that decision binds only that operator.

The deleted activity's identifier stays in the original entry, because the tree never changes. Chapter 39 explains how that identifier is treated under data-protection law, and how legal holds interact with deletion.

**Edits.** You cannot change an IPFS object; changing the content changes the CID. An edit is therefore a new activity that replaces the old one. The revised activity:

- has the same `@type`, `attributedTo`, and `inReplyTo` (if any) as the version it replaces;
- carries `replaces`, the identifier of the version it replaces;
- is appended to the timeline like any other activity.

The old version's StateMap slot gets `replacedBy`, naming the new version. A reader that has the old identifier, for example from a Boost, follows `replacedBy` to show the newest version, after checking each step as Chapter 10 requires. The history stays intact: every version is still in the timeline.

**Edited replies.** A reply tree shows exactly the version of each reply that the parent post's operator accepted, never a newer one it has not seen. An edit to a reply is submitted to the parent's operator as a new reply submission (Chapter 21) and validated from scratch, like any other reply. If it is accepted, that operator puts the new version in its reply tree in place of the old one; if it is rejected, the tree keeps the version it accepted. Readers MUST NOT follow `replacedBy` for a reply shown inside someone else's reply tree. Otherwise anyone could get a harmless reply accepted and then edit it into abuse.

Editing is subject to the ATD of the post type. The `Note` ATD allows edits; some ATDs (e.g., `Poll`) may prohibit editing after the first response has been recorded, since editing a poll question after votes have been cast would be dishonest. Operators reject an edit that its ATD prohibits.

Content **expiration** is also supported. An activity's `expiresAt` (Chapter 11) lets an author specify that content should stop being displayed after a certain time — like social media "Stories" that disappear after 24 hours. Expired content remains in the archive for integrity, but operators should not display it. Expiration is distinct from deletion: expired content was not deleted by user request; it was designed to expire from the start.

---

