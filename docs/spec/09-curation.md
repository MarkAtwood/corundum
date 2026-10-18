## Part IX: Curation

### Chapter 27: How Curation Works

Curation is Corundum's most distinctive design, and it is worth understanding the philosophical motivation before the technical details.

Today, platform moderation works like this: the platform makes decisions internally, applies them through opaque systems, and provides no accountability for those decisions. A post that is removed, an account that is suspended, an algorithm that suppresses content — none of these come with a clear statement of who made the decision, what authority they had, or how it can be appealed. The platform is simultaneously the content publisher, the judgment-maker, and the enforcer. There is no separation of these roles.

Corundum's curation system separates who makes the judgment from who enforces it. A curator announces a judgment — "content with this hash is spam" — but does not have the ability to remove content from any platform. The platform (operator) subscribes to the curator's feed and decides how to apply the judgment. This separation has several important consequences.

First, propagation at network scale. Today a curator must integrate separately with every platform — a different API, a different technical integration for each one. In Corundum, a curator publishes one signed curation feed, and every operator that subscribes to it receives each new judgment the next time it polls. The protocol provides the distribution mechanism. It does not replace the curator's own admission rules: child-safety hash lists (NCMEC, IWF) are distributed only to vetted providers under agreement, and a Corundum feed carrying them is readable only by operators the curator has admitted (Chapter 32).

Second, accountability. Curators must publish an Authority Declaration before publishing any curations. The declaration includes their governance model (how decisions are made), their appeal process (how judgments can be challenged), their jurisdiction claims, and the organizational identity behind the operation. Every curation entry is signed by a declared key and traceable to the declaration. There are no anonymous curators; every judgment is attributable to a declared entity.

Third, operator flexibility. Operators choose which curators to trust and decide how to apply their judgments. A children's platform might subscribe to child-safety hash lists, spam detection, NSFW classification, and a curated whitelist of age-appropriate content, and block anything that doesn't pass all checks. An adults-only platform might subscribe to child-safety hash lists but not to NSFW classification, since NSFW content is what their users want. A general-purpose platform might subscribe to several curators and apply them with different severity thresholds. The protocol provides the infrastructure; the policy is the operator's.

A **curator** is any entity that publishes signed judgments about content, identified by content hash. A judgment (a `CurationEntry`) says: "content with hash X has been judged as reason Y with strength Z by authority W."

Curators operate on content hashes, not on platform-specific post IDs. This means:

- A hash flagged by one curator is flagged at every subscribing operator, regardless of which operator hosts the content.
- A spam template identified by one curator can be blocked across all subscribing operators.
- Content can be flagged before it even appears on the network (pre-emptive curation from known-bad hash databases).
- The same content posted by multiple users matches a single curation entry.

### Chapter 28: Hash Types for Content Matching

The curation system supports two kinds of hash, because different matching needs require fundamentally different hash functions.

**Exact hashes** (SHA-256) match identical input. If Alice and Bob both post the exact same JPEG file, their SHA-256 hashes match. If one of them recompresses the JPEG, resizes it, or strips its EXIF data, the hash differs entirely. Exact hashes are matched by equality, so they can be looked up in a hash table, a Bloom filter, or a sharded index.

**Perceptual image hashes** solve the re-encoding problem. A perceptual hash is computed from the visual content of an image — the pixels, not the bytes. Two images that look the same to a human but differ in encoding, compression, resolution, or format produce hashes that differ in only a few bits. Matching is by distance, not equality: two PDQ hashes match when their Hamming distance is at most a threshold. A distance search cannot be answered by an exact-match structure such as a Bloom filter or a lookup keyed by the hash, so perceptual datasets are always downloaded in full and matched locally (Chapter 32).

PhotoDNA is the industry standard for CSAM detection, but it is proprietary and licensed, so Corundum does not define it. PDQ (from Meta's ThreatExchange project) is openly specified and licensed, and is the perceptual hash Corundum defines. PDQ tolerates re-encoding, format conversion, resizing, and mild color or quality changes. It does not tolerate significant cropping, rotation, mirroring, or substantial edits; a curator that wants to match rotated or mirrored copies lists the hashes of those variants as additional subjects.

This version of the specification defines no perceptual hash for video, audio, or near-duplicate text. A future revision may add one once its format and matching parameters can be pinned down precisely. Until then, curators match those media by exact hash.

**Defined hash pairs.** Every subject names a `hash_type` and a `hash_scope`. Only these pairs are defined; an entry with any other pair MUST be rejected:

| `hash_type` | `hash_scope` | Input | Value | Matching |
|---|---|---|---|---|
| `sha256` | `media-bytes` | The complete bytes of a media file (for chunked media, the reassembled file of one variant, Chapter 16) | 64 lowercase hex characters | Exact |
| `sha256` | `text-exact` | The UTF-8 bytes of an activity's `content` string, after JSON unescaping | 64 lowercase hex characters | Exact |
| `sha256` | `text-normalized` | The UTF-8 bytes of the `content` string after text normalization (below) | 64 lowercase hex characters | Exact |
| `pdq` | `perceptual-image` | The decoded image | 64 lowercase hex characters (256 bits), in the encoding of the ThreatExchange reference implementation | Hamming distance ≤ threshold |

**Text normalization** matches text regardless of formatting, so that a spam template matches its reformatted copies. Apply, in order, using Unicode 15.1.0: (1) Normalization Form NFKC; (2) full case folding (`CaseFolding.txt`, statuses C and F); (3) replace every maximal run of `White_Space` characters with a single U+0020; (4) remove a leading or trailing U+0020. Unlike content identifiers (Chapter 33), this hash deliberately folds distinct text together; it is used only for matching, never for identity.

### Chapter 29: Curation Entries

A `CurationEntry` contains:

- **subjects**: One or more content hash references (same content hashed with different algorithms)
- **authority**: The curator issuing the judgment (URI identifying the Authority Declaration)
- **issued**: When the judgment was made
- **reason**: A structured reason code from the defined taxonomy
- **ordinal**: A number from 0 to 1 giving the strength of the judgment
- **evidence**: Optional supporting evidence (itself a content-addressed reference)
- **expires**: Optional expiration (for temporary curations — e.g., electoral misinformation expires after the election)
- **supersedes**: Optional reference to an earlier curation this one replaces

**The `subjects` array.** A single curation entry can list multiple subject hashes because the same content may be representable in multiple ways. Consider a JPEG image: it has a SHA-256 hash (a precise fingerprint of this exact file) and a PDQ hash (a perceptual fingerprint of the visual content). Someone who recompresses the image produces a different SHA-256 but a PDQ hash within the matching distance of the original. By including both hashes as subjects of the same entry, the curator issues a single judgment that can be matched by exact-match systems (using SHA-256) and by perceptual-match systems (using PDQ). Operators that support only one type still benefit from whichever subject hash they can compute. The single entry also means there is one judgment for the content — the authority, the reason, the ordinal, and any evidence are stated once, not duplicated.

**The `ordinal` field.** The ordinal is a number from `0.0` to `1.0` inclusive. Higher always means stronger: more confidence that the reason applies, or a stronger recommendation. `0.0` means the reason does not apply; it is used to retract an earlier entry (see `supersedes` below).

- For `legal/csam-detected`, curators use `1.0`: the content matches known, confirmed material.
- For `spam/spam-commercial`, `0.85` means "85% confidence this is commercial spam." An operator might block at `0.9` and label at `0.7`.
- For `editorial/editor-pick`, `0.9` is a strong recommendation and `0.3` a weak one. The ordinal is a strength, not a rank; an editor who wants an ordered list publishes it by other means.

A single field with a single meaning keeps matching uniform: an operator configures a threshold for each (category, action) pair and checks `ordinal ≥ threshold`. Thresholds MUST be greater than `0.0`, so a retraction never matches a rule.

**The reason taxonomy** is organized into categories, each with specific subcodes:

- **legal**: `csam-detected`, `csam-suspected`, `copyright-infringement`, `court-order`, `sanctions-violation`
- **safety**: `harassment`, `threats-violence`, `self-harm`, `doxxing`
- **spam**: `spam-commercial`, `spam-phishing`, `spam-bot-network`
- **nsfw**: `nsfw-sexual`, `nsfw-gore`, `nsfw-drugs`
- **misinformation**: `misinfo-medical`, `misinfo-electoral`, `manipulated-media`
- **editorial**: `editor-pick`, `featured`, `trending`
- **quality**: `low-quality`, `duplicate`, `off-topic`
- **identity**: `verified-person`, `verified-organization`, `impersonation`

What kinds of organizations publish in each category, and what operators typically do with the entries:

- `legal/csam-detected` at ordinal `1.0`: Published by child safety organizations and law enforcement-designated bodies, to admitted operators only (Chapter 32). Operators typically block the content at once. Blocking is not deletion: operators commonly have legal duties to report apparent CSAM and to preserve what they report (in the US, 18 U.S.C. §2258A requires providers to report apparent CSAM they become aware of and to preserve it; it does not require them to scan). These duties vary by jurisdiction and are outside this specification; Chapter 39 covers how to retain content under a legal hold.

- `quality/low-quality` at ordinal `0.6`: Published by community moderation organizations, editorial boards, or algorithmic quality detectors. An operator might downrank the content (show it lower in feeds) rather than block it. A children's platform might block it; a general-purpose platform might only suppress it from recommendations. There is operator discretion here, which is appropriate for a judgment about quality rather than law.

- `editorial/editor-pick` at ordinal `0.9`: Published by editorial organizations, curated content boards, or trusted communities. An operator might surface entries above a threshold in a "curated" or "featured" feed, or use them as signals for recommendation algorithms. These entries represent positive curation rather than suppression.

**The `expires` and `supersedes` fields.** These fields handle two common operational realities.

`expires` is used for curations that are inherently time-bounded. Electoral misinformation (`misinfo-electoral`) entered during an election campaign should expire after the election, since the same content may not be misleading in a historical context. A temporary account suspension (flagged with a safety reason) might be set to expire in 30 days. After expiration, operators should treat the entry as if it never existed; they should not apply an expired curation to incoming content.

`supersedes` is used when a curator updates a prior judgment. An investigation might proceed in stages: an initial entry at `legal/csam-suspected` is published when content is flagged for review; after the investigation concludes, a second entry at `legal/csam-detected`, or a retraction at ordinal `0.0`, supersedes the original. The superseding entry carries the sequence number of the entry it replaces. Operators that receive both entries apply only the superseding one. This lets curators correct mistakes (a false positive that is subsequently cleared) through the feed itself rather than out-of-band.

### Chapter 30: Curation Authority Declarations

Before publishing curations, a curator must publish an Authority Declaration. This is not merely a formality — it is the accountability mechanism that distinguishes a legitimate curator from an anonymous content-removal service with no oversight.

Without a declaration, curations are anonymous assertions: a signed statement that some content has some property, with no way to determine who made the judgment, on what basis, or how to challenge it. Accountability requires knowing who is speaking. The declaration creates that accountability: it names the organization, describes how it makes decisions, establishes how errors can be corrected, and commits the organization to a published set of procedures. Every curation entry is traceable to this declaration. An operator that subscribes to a curator's feed is not subscribing to an opaque list of hashes; it is subscribing to the judgments of a named entity with a declared governance structure and an appeal mechanism.

The Authority Declaration contains:

- **Keys**: For verifying the curator's signatures.
- **Organization details**: Name, type (government agency, nonprofit, commercial entity), registration information.
- **Jurisdiction claims**: Which regions' laws the curator operates under. A `"global"` claim covers all jurisdictions; specific claims like `"US"` or `"DE"` indicate jurisdiction-specific curations.
- **Governance model**: A link to documentation of how the organization makes its curation decisions. What's the process? Who makes decisions? What oversight exists?
- **Appeal process**: A link to documentation of how content creators and operators can challenge a curation judgment.
- **Hash capabilities**: Which hash types the curator produces, so operators know which of their content-hashing infrastructure to use for matching.
- **Feed access**: Whether the feed is public or restricted to admitted operators.
- **Delegate keys**: Automated systems (ML classifiers, batch processing pipelines) authorized to sign curation entries on behalf of the authority.

**`governanceModel`.** This field links to documentation explaining how the curator makes its decisions. The field is a transparency requirement, not a quality bar: the protocol requires that something be published, not that it meet any particular standard of governance rigor. Different curators will have very different governance structures, and all of them are legitimate.

NCMEC's role is defined in US federal statute (including 18 U.S.C. §2258A and 34 U.S.C. §11293), and its governance document would reference those instruments. A community-operated spam detection service might be governed by a committee of volunteer operators, with decisions made by majority vote and documented in a GitHub repo with an RFC-style proposal process. A commercial classifier might be governed by the company's internal policies with an external audit. The point is that the governance document exists and is linked — operators that subscribe to a curator's feed can read how that curator operates. An operator choosing to subscribe to a spam detection feed can evaluate whether the governance model is appropriate for the trust they're placing in that feed.

**`appealProcess`.** This field links to documentation explaining how judgments can be challenged and corrected. It is specifically required because automated classifiers make mistakes, and false positives have real consequences for legitimate creators.

A photographer whose artistic nude work is flagged as `nsfw-sexual` needs a mechanism to have that judgment reconsidered or overturned. A journalist whose legitimate reporting on extremism is flagged for containing extremist content needs a way to explain the context. A security researcher whose post about malware is flagged as spam needs recourse. The appeal process is how these errors get corrected. An authority declaration without an appeal mechanism would mean curations are effectively irreversible — a curator could flag content with no accountability for errors. The protocol requires the mechanism to exist; it does not specify how long appeals take or what criteria the curator uses, because those are governance decisions for the curator.

**`jurisdictionClaims`.** Curators may have legal authority only within certain jurisdictions, and operators in different jurisdictions appropriately give different weight to different curator authority claims.

A government agency's copyright enforcement body claims authority within its jurisdiction. A US Digital Millennium Copyright Act takedown notice carries legal weight for operators subject to US law, but an operator in Germany running under German law may give it different weight than a `court-order` entry from a German court. A global hash database operated by an international coalition (with mandates from multiple governments) claims global authority and is treated as high-authority by operators in all those jurisdictions.

This field allows operators to implement jurisdiction-appropriate trust hierarchies. An operator serving primarily European users might give higher weight to entries from EU-authorized bodies; a global operator might treat entries from global authorities as universally applicable and jurisdiction-specific entries as applicable only to users in the named jurisdiction.

**`delegateKeys`.** Automated systems sign curation entries on behalf of the authority rather than requiring a human to sign each entry manually. This is a practical necessity for high-volume curation.

A classifier that reviews millions of images a day cannot have a human sign each entry it produces. Delegate keys allow automatic signing: the authority declaration lists one or more delegate keys with the reasons each is authorized to sign. A curation entry signed by a delegate key is treated as if it were signed by the authority, because the authority declaration itself (signed by the authority's root key) names the delegate key and authorizes it.

Delegate keys have narrower authority than the authority's root key. The declaration specifies which reasons each delegate key may sign. A delegate key used by a classifier might be authorized only for `legal/csam-suspected` — a classifier's output is a suspicion, not a confirmed match — and not for editorial or quality judgments. If a delegate key's private key is compromised (e.g., a server breach), the authority can revoke it by publishing an updated declaration that removes the key, without affecting the authority's root key or other delegate keys.

### Chapter 31: How Operators Use Curations

Operators subscribe to whichever curators they choose. A typical operator might subscribe to:

- A child-safety hash list (available only under agreement with the curator)
- A general spam detection curator
- An NSFW classification curator
- An editorial/quality curator (for recommending high-quality content)

**The policy table.** An operator's curation policy is a table of `(curator, reason-pattern, ordinal-threshold, action)` rules. Each row says: when this curator signals this reason at this strength or above, take this action. A concrete example:

```
Curator: Child Safety Hash List
  legal/csam-detected  ≥ 1.0  → BLOCK_IMMEDIATELY + PRESERVE + REPORT
  legal/csam-suspected ≥ 0.8  → QUARANTINE + HUMAN_REVIEW

Curator: SpamShield Pro
  spam/spam-commercial  ≥ 0.9  → BLOCK
  spam/spam-commercial  ≥ 0.6  → LABEL("spam")
  spam/spam-phishing    ≥ 0.7  → BLOCK + WARN_USERS

Curator: NSFW Classifier
  nsfw/nsfw-sexual     ≥ 0.8  → HIDE_FROM_MINORS
  nsfw/nsfw-gore       ≥ 0.9  → BLOCK

Curator: Editorial Board
  editorial/editor-pick ≥ 0.5  → BOOST_IN_RECOMMENDATIONS
```

This is not a wire format — it is illustrative of the data structure an operator maintains internally to drive policy evaluation. The protocol specifies what curators publish and what operators must check; how the operator stores and evaluates its policy rules is an implementation choice.

**The content check pipeline.** When content arrives — either a new local post or an incoming reply submission — the operator runs it through its curation policy before publishing. The pipeline:

1. Compute every hash pair (Chapter 28) that any subscribed curator lists in its `hash_capabilities`. SHA-256 of media bytes is always computed.
2. Match exact hashes against each curator's entries: either the operator's local copy of the full dataset, or the curator's Bloom filter followed, on a positive, by a bucket fetch (Chapter 32).
3. Match PDQ hashes against the operator's local copy of each curator's full dataset, by Hamming distance.
4. Apply the policy table. Evaluate rules in order of severity. If the highest-severity match action is `BLOCK_IMMEDIATELY`: block and stop — do not evaluate further. If the action is `QUARANTINE`: hold for human review, do not publish. If the action is `LABEL`: publish with the label attached. If no rules match: publish.

**Conflicting curator signals.** Curators will sometimes disagree about the same content. A perceptual hash match from an NSFW classifier might assign `nsfw/nsfw-sexual` at ordinal 0.85. The same post might be in an editorial curator's list with `editorial/editor-pick` at ordinal 0.9. These are signals from different categories with different stakes.

The recommended resolution policy: reason categories have an operator-configured severity ranking, and higher-severity categories override lower-severity ones. Legal and safety categories always outrank editorial categories. Within the same category, the more conservative action prevails — block beats label, label beats allow. An `nsfw` signal that requires hiding content from minors does not prevent the content from being boosted in adult recommendations on an adult-oriented platform; the actions apply to different dimensions of content handling. An operator is free to configure its own priority logic; this recommendation is not a protocol requirement.

**Retroactive matching in practice.** When a new curation entry arrives in a subscribed curator's feed, the operator must check whether any content it has already stored matches the new entry.

The implementation challenge is doing this at scale without disrupting service. An operator with billions of stored content items cannot scan them linearly every time a new curation entry arrives. The recommended implementation: maintain a content hash index mapping each exact hash of stored content to the CIDs that contain it, and, if the operator matches PDQ, an index that supports Hamming-distance search over the PDQ hashes of stored images (for example, multi-index hashing). When new curation entries arrive, query these indexes for each new subject. Matches trigger immediate policy application. For operators with large content stores, these indexes are not optional; they are the only way retroactive matching completes in bounded time.

The protocol requires that retroactive matching happen. It does not specify how to implement the index. That is an operator concern.

**No global enforcement.** The operator enforces curations within its own infrastructure boundary. It checks content it hosts and content flowing through its reply protocol. It cannot reach into another operator's IPFS node and remove content from there.

If Operator B hosts content that Operator A has curated as harmful, Operator A's options are: refuse to display it to its own users, refuse to forward it in reply chains that pass through Operator A, and optionally defederate from Operator B entirely. What Operator A cannot do is force Operator B to remove the content. The enforcement boundary is the operator's own infrastructure. This is the correct model: enforcement authority should be limited to what you actually control. Accountability without control is a recipe for liability without remediation.

### Chapter 32: Static Curation Hosting

Not every curator needs to run a live API server. A curator may publish its feed as static files on S3 or a CDN — simpler to operate, cheaper to scale, and compatible with any HTTP client. The static hosting specification enables this: curation feeds can be served from static infrastructure with no custom server software, except that a restricted feed needs a front end that authenticates requests (see Access control below).

**The design constraint** is that curation databases can be large (tens of millions of hashes), and the CDN that serves them is not trusted. Every feed provides the full dataset as a snapshot plus an append-only log, and a signed **feed head** that commits to all of it. Operators that want to match perceptual hashes download the full dataset and match locally, because a distance search cannot be done remotely by key. For exact hashes, a feed may also provide a Bloom filter and prefix buckets, so that an operator can screen content without holding the full dataset.

**The feed head.** The head is the root of trust for everything the CDN serves. It is a small file at:

```
/feeds/example-authority/head.jws
```

The curator re-signs and republishes it every time any feed file changes, and at least once before the current head expires. Every other feed file is checked against a SHA-256 digest that the head commits to, directly or through `index.json`. A CDN therefore cannot alter, withhold, or roll back any part of the feed without the change being detected: it cannot forge a head, an operator rejects any head older than one it has already accepted, and an operator notices that a head has expired. What a CDN can still do is stop serving the feed; the head's expiry bounds how long that can go unnoticed. The head is defined under Feed Head Wire Format below.

Feed files are served over HTTPS, not IPFS, and several of them exceed the single-block limit of Chapter 33, so the feed refers to them by hex SHA-256 digest rather than by CID.

**Incremental synchronization.** The feed publishes an append-only log of new entries at:

```
/feeds/example-authority/log/page-0001.ndjson.gz
/feeds/example-authority/log/page-0002.ndjson.gz
/feeds/example-authority/log/index.json
```

The `index.json` file lists the available log pages and the latest page's last sequence number. An operator that last synced to sequence 4820 fetches the head and `index.json`, finds which pages contain sequences after 4820, downloads those pages, and applies the new entries. Pages are immutable once closed (a new page is opened when the current page exceeds a size threshold, typically 10 MB compressed). Immutability makes pages CDN-cacheable indefinitely.

A new operator that has never synced the feed downloads the **full snapshot**: a single large NDJSON.gz file containing all current entries as of a known sequence number. The feed provides snapshots at:

```
/feeds/example-authority/snapshots/snapshot-2025-01-01.ndjson.gz
```

After loading the snapshot, the operator switches to incremental sync from the snapshot's sequence number forward. The snapshot + incremental approach means a new operator can onboard a large dataset (tens of millions of entries) efficiently without paginating through millions of incremental log entries.

**The exact-match index (optional).** A feed MAY publish a Bloom filter and prefix buckets covering the exact (`sha256`) subjects of its entries up to some sequence number. They never cover `pdq` subjects. An operator that uses them instead of the snapshot MUST still follow the log from the filter's `covers_sequence_through` onward, both to see newer entries and to perform retroactive matching.

The Bloom filter is at:

```
/feeds/example-authority/bloom.bin
```

An operator downloads it once per head that changes it, and checks exact hashes locally. A negative means the hash is definitely not covered. A positive means it may be, and the operator fetches the bucket for that hash to confirm or discard the match. At about 10 bits per element (1% false-positive rate, 7 hash functions), a filter is 12.5 MB for 10 million subjects and 62.5 MB for 50 million.

**Prefix buckets.** Each bucket holds every entry with an exact subject whose `hash_value` begins with a given 4 hex characters:

```
/feeds/example-authority/entries/a3f9.ndjson
```

There are 65,536 buckets, `0000` through `ffff`. A bucket file contains, one per line in ascending sequence order, every entry with sequence ≤ `covers_sequence_through` that has at least one `sha256` subject whose `hash_value` starts with the bucket's prefix. The operator compares the full `hash_type`, `hash_scope`, and `hash_value` of each subject locally. A superseding entry MUST list every subject of the entry it supersedes, so that both always land in the same buckets.

A CDN could serve an empty bucket to hide an entry, so buckets are committed to by `buckets.bin`: 65,536 SHA-256 digests of 32 bytes each (2 MiB), one per bucket in prefix order. A bucket with no entries has the digest of the empty byte string (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`); the curator MAY omit its file, and a `404` response is then valid only if the table holds that digest. Operators MUST verify every bucket against `buckets.bin`, and `buckets.bin` against the head.

**What a bucket fetch reveals.** The Bloom check is local and reveals nothing. A bucket fetch reveals to the feed host and CDN the first 16 bits of one of the operator's content hashes, when the operator made the request, and its network address. Because operators fetch only after a Bloom positive, a fetch also tells the host that the content is probably curated: it is either a true match or one of the roughly 1% false positives. If the bucket holds only a few entries, the host can usually guess which one matched. Bucketing therefore protects the hashes of content that is not curated, which is most content, and gives little protection to content that is. An operator that does not accept this leakage downloads the full dataset instead.

**Access control.** Feeds are public by default: any operator can read them, with no credential. A public list of hashes, however, tells anyone who holds harmful material whether it is on the list, and which edits evade it. Child-safety hash lists are distributed only to vetted providers under agreement for this reason. Therefore:

- A feed that contains any entry with a `legal/*` reason MUST NOT be publicly readable. Its declaration sets `feed_access` to `"restricted"`. Every request for any of its feed files (head, index, pages, snapshots, Bloom filter, buckets) MUST carry an RFC 9421 signature by the requesting operator (Chapter 19), and the feed host MUST refuse requests from operators the curator has not admitted. How the curator admits operators is a matter for its agreements with them, not for this specification.
- A curator that also publishes public categories MUST publish them in a separate feed with its own Authority Declaration on a different host.
- The Authority Declaration itself is always public, so that anyone can see who the curator is and how to request access.

Integrity does not depend on access control: the head and entry signatures protect a restricted feed exactly as they protect a public one.

### CurationEntry Wire Format

A CurationEntry is stored as an attached JWS (Chapter 34) in the General JSON Serialization, with `corundumType` `"CurationEntry"`. Its payload is the entry object below. One entry occupies one line in an NDJSON file, so the JWS MUST be written without line breaks. As stored:

```json
{"payload":"<base64url of the entry bytes>","signatures":[{"protected":"<base64url of the protected header>","signature":"<base64url of the Ed25519 signature>"}]}
```

The decoded protected header:

```json
{"alg":"Ed25519","crit":["corundumType"],"corundumType":"CurationEntry","kid":"key-1"}
```

The decoded payload:

```json
{
  "type": "CurationEntry",
  "version": 1,
  "sequence": 48293,
  "subjects": [
    {
      "hash_type": "sha256",
      "hash_scope": "media-bytes",
      "hash_value": "<64 hex chars: SHA-256 of the image file>",
      "media_type": "image/jpeg"
    },
    {
      "hash_type": "pdq",
      "hash_scope": "perceptual-image",
      "hash_value": "<64 hex chars: PDQ hash of the image>",
      "pdq_quality": 97,
      "match_threshold": 31
    }
  ],
  "authority": "https://curator.example/.well-known/corundum-curator",
  "issued": "2025-01-15T12:34:56Z",
  "reason": "legal/csam-detected",
  "ordinal": 1.0,
  "evidence": null,
  "expires": null,
  "supersedes": null
}
```

**Field definitions:**

`type` (string, REQUIRED): Always `"CurationEntry"`.

`version` (integer, REQUIRED): Always `1` for this version of the spec.

`sequence` (integer, REQUIRED): Assigned by the curator, unique within this feed. Sequence numbers MUST be assigned in order of `issued` time, MUST be strictly increasing in log order, and MUST NOT be reused.

`subjects` (array, REQUIRED, minimum 1 element): The content being curated. Each element is a subject object (defined below).

`authority` (string, REQUIRED): URL of the Authority Declaration that governs this entry. MUST equal the declaration's `id`.

`issued` (string, REQUIRED): ISO 8601 datetime with UTC offset (`Z`), second precision. When the judgment was made.

`reason` (string, REQUIRED): A `category/subcode` reason string from the defined taxonomy (Chapter 29). Implementations MUST reject entries with unrecognized reason strings as malformed.

`ordinal` (number, REQUIRED): The strength of the judgment, from `0.0` to `1.0` inclusive (Chapter 29). Values outside that range MUST be rejected.

`evidence` (string or null, OPTIONAL): A CID or URL pointing to supporting evidence. If present, MUST be either a valid CID (Chapter 33) or a valid HTTPS URL. Operators MAY fetch evidence but are not required to.

`expires` (string or null, OPTIONAL): ISO 8601 datetime with UTC offset. After this time, operators MUST treat the entry as if it were never received. MUST be strictly later than `issued`.

`supersedes` (integer or null, OPTIONAL): The sequence number of an earlier entry in this feed that this entry replaces. The superseded entry's sequence number MUST be lower than this entry's, and this entry MUST list every subject of the superseded entry. Operators that have applied the superseded entry MUST unapply it and apply this entry instead.

**Subject object fields:**

`hash_type`, `hash_scope` (strings, REQUIRED): One of the defined pairs in Chapter 28.

`hash_value` (string, REQUIRED): The hash value, as defined for the pair in Chapter 28.

`media_type` (string, OPTIONAL): The MIME type of the content, if known. Informational only.

`pdq_quality` (integer, OPTIONAL): For `pdq` hashes, the PDQ quality score (0–100) of the source image. Images below quality 50 produce unreliable hashes; operators MAY skip matching for low-quality hashes.

`match_threshold` (integer, OPTIONAL): For `pdq` hashes, the maximum Hamming distance (out of 256 bits) at which two hashes match. If absent, the threshold is 31. Curators MAY specify a lower threshold for higher precision.

**Signing.** The entry is signed per Chapter 34. The `kid` is the `key_id` of a key in the curator's Authority Declaration. Operators MUST reject an entry unless every signature verifies, at least one signature is present, and each `kid` names a key that the current declaration lists and that is authorized for the entry's `reason` (`delegate_for`, below).

### Authority Declaration Wire Format

An Authority Declaration is stored and served as an attached JWS (Chapter 34) with `corundumType` `"AuthorityDeclaration"`, signed by a root key (`delegate_for` null) that the declaration itself lists. It is served at the curator's well-known URL (see Feed Discovery below) over HTTPS. Its decoded payload:

```json
{
  "type": "AuthorityDeclaration",
  "version": 1,
  "id": "https://curator.example/.well-known/corundum-curator",
  "organization": {
    "name": "Example Safety Organization",
    "type": "nonprofit",
    "url": "https://safety.example",
    "registration": "<registration identifier>"
  },
  "jurisdiction_claims": ["global"],
  "governance_url": "https://safety.example/governance",
  "appeal_url": "https://safety.example/appeals",
  "feed_url": "https://feeds.curator.example/feeds/safety",
  "feed_access": "restricted",
  "hash_capabilities": [
    { "hash_type": "sha256", "hash_scope": "media-bytes" },
    { "hash_type": "pdq",    "hash_scope": "perceptual-image" }
  ],
  "reason_capabilities": ["legal/csam-detected", "legal/csam-suspected"],
  "keys": [
    {
      "key_id": "key-1",
      "alg": "Ed25519",
      "public_key_multibase": "<z6Mk… multibase Ed25519 public key>",
      "created_at": "2024-01-01T00:00:00Z",
      "delegate_for": null
    },
    {
      "key_id": "key-2-classifier",
      "alg": "Ed25519",
      "public_key_multibase": "<z6Mk… multibase Ed25519 public key>",
      "created_at": "2024-06-01T00:00:00Z",
      "delegate_for": ["legal/csam-suspected"]
    },
    {
      "key_id": "key-3-feed",
      "alg": "Ed25519",
      "public_key_multibase": "<z6Mk… multibase Ed25519 public key>",
      "created_at": "2024-06-01T00:00:00Z",
      "delegate_for": ["feed-head"]
    }
  ],
  "valid_from": "2024-01-01T00:00:00Z",
  "valid_until": null
}
```

**Field definitions:**

`type` (string, REQUIRED): Always `"AuthorityDeclaration"`.

`version` (integer, REQUIRED): Always `1`.

`id` (string, REQUIRED): The URL at which this declaration is served. MUST match the URL from which it was fetched.

`organization.type` (string, REQUIRED): One of `government`, `nonprofit`, `commercial`, `community`.

`organization.registration` (string, OPTIONAL): Legal registration identifier (tax ID, company number, etc.). Informational.

`jurisdiction_claims` (array of strings, REQUIRED): ISO 3166-1 alpha-2 country codes, or `"global"`. An entry of `"global"` means the curator claims authority applicable to all jurisdictions. Operators MAY give different weight to jurisdiction claims based on their own legal context.

`feed_url` (string, REQUIRED): Base URL of the static curation feed. All feed files are served relative to this URL.

`feed_access` (string, REQUIRED): `"public"` or `"restricted"` (Chapter 32, Access control). MUST be `"restricted"` if `reason_capabilities` includes any `legal/*` reason.

`hash_capabilities` (array, REQUIRED): Hash pairs (Chapter 28) that this curator produces. Operators use this to know which hashes to compute when checking content against this curator's feed.

`reason_capabilities` (array of strings, REQUIRED): The reason codes this curator publishes. Operators MAY subscribe selectively — an operator that does not want editorial judgments can subscribe to a curator but ignore entries with `reason` in the `editorial/` category. Operators MUST reject entries whose reason is not listed here.

`keys[].alg` (string, REQUIRED): The key's JOSE algorithm from the registry in Chapter 36. A signature's `alg` MUST equal the `alg` of the key its `kid` names.

`keys[].public_key_multibase` (string, REQUIRED): For `Ed25519`, the multicodec `ed25519-pub` prefix (`0xed 0x01`) followed by the 32-byte public key, encoded as base58btc multibase (beginning `z6Mk`).

`keys[].delegate_for` (array of strings or null, REQUIRED): If null, this is a root key, authorized to sign any entry, any feed head, and the declaration itself. If an array, this is a delegate key authorized only for the listed patterns: an exact reason string, a category prefix (e.g., `"legal"` matches all `legal/*` reason codes), or `"feed-head"`, which authorizes signing feed heads. A delegate key MUST NOT sign the Authority Declaration itself.

A key is valid for as long as the current declaration lists it. To revoke a key, the curator removes it from the declaration; operators then reject every entry it signed, so before removing a key, the curator re-issues the entries it signed under another key as new entries that supersede them.

`valid_until` (string or null, OPTIONAL): If set, the entire declaration is invalid after this time. Operators MUST re-fetch the declaration before this time to get a renewed or replacement declaration.

### Feed Head Wire Format

The feed head is an attached JWS (Chapter 34) with `corundumType` `"CurationFeedHead"`, served at `{feed_url}/head.jws`. It MUST be signed by a key whose `delegate_for` is null or includes `"feed-head"`. Its decoded payload:

```json
{
  "type": "CurationFeedHead",
  "version": 1,
  "authority": "https://curator.example/.well-known/corundum-curator",
  "head_sequence": 9031,
  "previous_sha256": "<64 hex chars: SHA-256 of head 9030's bytes>",
  "issued": "2025-01-15T12:05:00Z",
  "expires": "2025-01-17T12:05:00Z",
  "latest_entry_sequence": 48293,
  "index_sha256": "<64 hex chars: SHA-256 of log/index.json>",
  "open_page_sha256": "<64 hex chars: SHA-256 of the open log page>",
  "exact_index": {
    "covers_sequence_through": 48000,
    "element_count": 2847392,
    "bloom_sha256": "<64 hex chars: SHA-256 of bloom.bin>",
    "buckets_sha256": "<64 hex chars: SHA-256 of buckets.bin>"
  }
}
```

**Field definitions:**

`authority` (string, REQUIRED): MUST equal the declaration's `id`.

`head_sequence` (integer, REQUIRED): `1` for the first head; each later head is exactly one greater than the one before it.

`previous_sha256` (string or null, REQUIRED): SHA-256 of the exact bytes of head `head_sequence − 1`; null only for head `1`.

`issued`, `expires` (strings, REQUIRED): ISO 8601 datetimes with UTC offset. `expires` MUST be later than `issued` and no more than 48 hours after it.

`latest_entry_sequence` (integer, REQUIRED): The highest entry sequence number in the log. MUST equal `latest_sequence` in `index.json`.

`index_sha256` (string, REQUIRED): SHA-256 of the exact bytes of `log/index.json`.

`open_page_sha256` (string or null, REQUIRED): SHA-256 of the open log page as it stands at this head, or null if `index.json` lists no open page. This is how the open page, whose `sha256` in `index.json` is null, is authenticated.

`exact_index` (object or null, REQUIRED): Null if the feed publishes no Bloom filter or buckets. Otherwise, `covers_sequence_through` is the highest entry sequence they cover, `element_count` is the number of elements inserted into the filter, and the two digests commit to `bloom.bin` and `buckets.bin`.

The curator MUST keep every head it has published, at `{feed_url}/heads/{head_sequence}.jws`, so that operators can verify the chain.

**Verifying a head.** On each poll, an operator:

1. Fetches `head.jws` and verifies it per Chapter 34 with `corundumType` `"CurationFeedHead"`, using a key the current declaration authorizes for heads. It checks that `authority` matches and that `expires` has not passed.
2. Compares `head_sequence` with the last head it accepted from this feed. If it is lower, the operator MUST reject the head. If it is equal, the head's bytes MUST be identical to the accepted head; two different validly signed heads with the same sequence are evidence of a compromised key or a faulty curator, and the operator MUST reject the new head and alert. If it is greater, the operator MUST fetch each intermediate head from `heads/` and verify that the `previous_sha256` links lead from the new head back to the accepted one. Only the new head's signature is checked; the hash links authenticate the intermediate heads.
3. Fetches `index.json` and verifies it against `index_sha256`. Every closed page and snapshot listed in the previously accepted index MUST still be listed with the same `sha256`; otherwise the operator MUST reject the head, because the log is append-only.
4. Verifies each page or snapshot it downloads against its `sha256` in the index, or, for the open page, against `open_page_sha256`; and, if it uses the exact-match index, verifies `bloom.bin` and `buckets.bin` against `exact_index`.

An operator MUST NOT use any file that does not match the digest the head commits to. Files and head may briefly disagree while a CDN updates its caches, so curators SHOULD upload all other files before the head, and operators SHOULD retry a mismatch on the next poll. If the operator holds no unexpired head, it keeps applying the entries it has already accepted, treats the feed as stale, and alerts its administrators.

### Bloom Filter Binary Format

The Bloom filter file at `{feed_url}/bloom.bin` has the following layout:

```
Offset  Size       Field
──────  ─────────  ─────────────────────────────────────────────
0       4          Magic: 0x434F524E ("CORN" in ASCII)
4       1          Version: 0x01
5       3          Reserved: 0x000000
8       8          m: bit-array size in bits (uint64, big-endian)
16      2          k: number of hash functions (uint16, big-endian)
18      6          Reserved: 0x000000000000
24      ceil(m/8)  Bit array
```

Total file size: 24 + ceil(m/8) bytes. Unused bits in the last byte MUST be zero.

**Bit packing.** Bit index `i` resides in byte `floor(i/8)` of the bit array, at bit position `7 - (i mod 8)`, where bit position 7 is the most significant bit. Bit 0 of the array is the most significant bit of the first byte.

**Elements.** One element is inserted for each `sha256` subject of each covered entry:

```
x = hash_type || 0x00 || hash_scope || 0x00 || hash_value_bytes
```

`hash_type` and `hash_scope` are their ASCII strings, and `hash_value_bytes` is the 32-byte binary value (hex-decoded, not the hex string). Including the type and scope keeps a `text-exact` hash from matching a `media-bytes` hash of the same bytes.

**Bit indexes** (Kirsch–Mitzenmacher double hashing):

1. Compute `D = SHA-256(x)`.
2. Let `h1` be bytes 0–7 of `D` and `h2` bytes 8–15 of `D`, each read as a big-endian unsigned 64-bit integer.
3. For `i = 0` to `k − 1`, bit index `g_i = (h1 + i × h2) mod m`, computed exactly as an integer, not modulo 2^64. (For example, set `g_0 = h1 mod m`, `s = h2 mod m`, and `g_{i+1} = (g_i + s) mod m`.)

To insert, set bits `g_0 … g_{k−1}`. To test, the result is positive only if all of them are set.

**Example.** The `media-bytes` subject of a file containing the three bytes `abc` has `hash_value` `ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad`. Its element `x` is the 51 bytes `736861323536006d656469612d627974657300ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad`, and `D` is `e9ae108e32cf5f0abb1b17e6941eef5a54a90747bc7cea32dc132bebfc19ce3e`, so `h1` = 16838414259708714762 and `h2` = 13482396188558683994. With `m` = 27292419 and `k` = 7, the bit indexes are 25275801, 6832445, 15681508, 24530571, 6087215, 14936278, and 23785341.

Operators MUST verify the magic bytes and version, and that the file length is `24 + ceil(m/8)`, before using the filter.

### index.json Schema

```json
{
  "version": 1,
  "authority": "https://curator.example/.well-known/corundum-curator",
  "feed_url": "https://feeds.curator.example/feeds/safety",
  "latest_sequence": 48293,
  "generated_at": "2025-01-15T12:05:00Z",
  "pages": [
    {
      "name": "page-0001",
      "path": "log/page-0001.ndjson.gz",
      "sequence_start": 1,
      "sequence_end": 500,
      "entry_count": 500,
      "size_bytes": 124832,
      "sha256": "<64 hex chars>",
      "closed_at": "2024-06-01T00:00:00Z"
    }
  ],
  "open_page": {
    "name": "page-0097",
    "path": "log/page-0097.ndjson.gz",
    "sequence_start": 47801,
    "sequence_end": 48293,
    "entry_count": 493,
    "size_bytes": 98441,
    "sha256": null
  },
  "snapshots": [
    {
      "name": "snapshot-2025-01-01",
      "path": "snapshots/snapshot-2025-01-01.ndjson.gz",
      "sequence_through": 40000,
      "entry_count": 2700000,
      "size_bytes": 485234892,
      "sha256": "<64 hex chars>",
      "generated_at": "2025-01-01T00:00:00Z"
    }
  ]
}
```

**Field definitions:**

`pages` (array): Closed log pages. A page is closed when it reaches the size threshold (RECOMMENDED: 10 MB compressed). Closed pages are immutable; their `sha256` MUST be set. Operators MUST verify `sha256` on closed pages. Pages MUST be listed in ascending order of `sequence_start`.

`open_page` (object or null): The currently active page, still receiving entries. Its `sha256` is null because the file is still being written; the feed head carries its current digest. Operators MUST NOT cache open pages; they MUST re-fetch the open page on every sync. An open page becomes a closed page when the curator seals it.

`snapshots` (array): Full-dataset snapshots. Each snapshot contains all entries with sequence number ≤ `sequence_through` as a single gzip-compressed NDJSON file. Operators doing initial sync SHOULD use the most recent snapshot as a starting point rather than reading all log pages from page 1.

`sha256` fields: Hex-encoded SHA-256 of the referenced file. REQUIRED for closed pages and snapshots. MUST be null for the open page.

### Feed Discovery

Curators publish an Authority Declaration at a well-known HTTPS path on their domain:

```
GET https://curator.example/.well-known/corundum-curator
```

The response MUST be `Content-Type: application/jose+json` and MUST be the Authority Declaration JWS defined above. The URL in the declaration's `id` field MUST exactly match the URL from which it was fetched (after following redirects). Operators MUST reject declarations where `id` does not match the fetch URL.

The `feed_url` field in the declaration gives the base URL of the static feed. All feed paths (`/head.jws`, `/heads/...`, `/log/index.json`, `/log/...`, `/snapshots/...`, and, if published, `/bloom.bin`, `/buckets.bin`, `/entries/...`) are resolved relative to this base URL.

Operators configure curator subscriptions by storing the well-known URL. Everything else — feed location, access mode, hash capabilities, signing keys — is discovered from the declaration at that URL.

### Polling Requirements

Operators MUST re-fetch `head.jws` at least once per hour for curators publishing in the `legal/` reason category.

Operators SHOULD re-fetch `head.jws` at least once per 24 hours for curators publishing in other categories.

Operators MUST use incremental sync (log pages from the last-seen sequence number) after initial load. Operators MUST NOT re-download snapshots on every poll cycle.

Operators SHOULD respect `Cache-Control` and `ETag` headers on `head.jws`. If the server returns `304 Not Modified`, the operator has no new entries to process.

Operators MUST re-fetch the Authority Declaration at least once per 24 hours to detect key rotation, revocation, or declaration updates. If `valid_until` is set on the declaration, operators MUST re-fetch before that time.

Operators MUST verify entry signatures on every entry processed, whether from snapshots, log pages, the open page, or buckets. An entry with an invalid signature MUST be discarded and MUST NOT be applied to the operator's policy. Operators SHOULD log the discarded entry for investigation.

---

