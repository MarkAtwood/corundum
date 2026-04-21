## Part IX: Curation

### Chapter 27: How Curation Works

Curation is Corundum's most distinctive design, and it is worth understanding the philosophical motivation before the technical details.

Today, platform moderation works like this: the platform makes decisions internally, applies them through opaque systems, and provides no accountability for those decisions. A post that is removed, an account that is suspended, an algorithm that suppresses content — none of these come with a clear statement of who made the decision, what authority they had, or how it can be appealed. The platform is simultaneously the content publisher, the judgment-maker, and the enforcer. There is no separation of these roles.

Corundum's curation system separates who makes the judgment from who enforces it. A curator announces a judgment — "content with this hash is CSAM" — but does not have the ability to remove content from any platform. The platform (operator) subscribes to the curator's feed and decides how to apply the judgment. This separation has several important consequences.

First, propagation at network scale. Consider a child safety organization that maintains a hash database of known CSAM. In the current world, they must integrate separately with every platform — a different API, a different agreement, a different technical integration for each platform. In Corundum, they publish a signed curation feed. Every Corundum operator that subscribes to their feed receives the judgment. A new hash is propagated to all subscribing operators the next time they poll the feed. No per-platform integration required; the protocol provides the distribution mechanism.

Second, accountability. Curators must publish an Authority Declaration before publishing any curations. The declaration includes their governance model (how decisions are made), their appeal process (how judgments can be challenged), their jurisdiction claims, and the organizational identity behind the operation. Every curation entry is signed by a declared key and traceable to the declaration. There are no anonymous curators; every judgment is attributable to a declared entity.

Third, operator flexibility. Operators choose which curators to trust and decide how to apply their judgments. A children's platform might subscribe to CSAM hash lists, spam detection, NSFW classification, and a curated whitelist of age-appropriate content, and block anything that doesn't pass all checks. An adults-only platform might subscribe to CSAM hash lists (legally required) but not to NSFW classification, since NSFW content is what their users want. A general-purpose platform might subscribe to several curators and apply them with different severity thresholds. The protocol provides the infrastructure; the policy is the operator's.

A **curator** is any entity that publishes signed judgments about content, identified by content hash. A judgment (a `CurationEntry`) says: "content with hash X has been judged as reason Y with severity Z by authority W."

Curators operate on content hashes, not on platform-specific post IDs. This means:

- A CSAM hash flagged by one curator is flagged everywhere, regardless of which operator hosts it.
- A spam template identified by one curator can be blocked across all subscribing operators.
- Content can be flagged before it even appears on the network (pre-emptive curation from known-bad hash databases).
- The same content posted by multiple users matches a single curation entry.

### Chapter 28: Hash Types for Content Matching

The curation system supports multiple hash types because different matching needs require fundamentally different hash functions.

**Cryptographic hashes** (SHA-256) provide exact byte-for-byte content matching. If Alice and Bob both post the exact same JPEG file, their SHA-256 hashes will match. But if one of them recompresses the JPEG at slightly different quality settings, or resizes it, or strips the EXIF data, the hash will differ entirely. SHA-256 alone is insufficient for any use case where the harmful content might be re-encoded.

**Perceptual image hashes** (pHash, PhotoDNA, PDQ) solve the re-encoding problem. A perceptual hash is computed from the visual content of an image — the pixels, not the bytes. Two images that look the same to a human but differ in encoding, compression, resolution, or format will produce similar or identical perceptual hash values. PhotoDNA is the industry standard for CSAM detection (used by Microsoft, Facebook, and most major platforms). PDQ is Facebook's open-source alternative, designed to be more computationally efficient than PhotoDNA for high-volume processing.

The critical insight about perceptual hashes: they measure perceptual similarity, not byte equality. A photo that's been cropped slightly, converted from JPEG to PNG, reduced to 720p from 1080p, or had its metadata stripped will still match the original's perceptual hash within the matching threshold. This is what makes perceptual hashing useful for content matching: perpetrators routinely re-encode content to defeat SHA-256 matching.

**Perceptual video hashes** (TMK+PDQ) extend the perceptual approach to video. TMK+PDQ combines temporal matching (comparing frame sequences over time) with per-frame PDQ hashing, allowing matching across transcodes, quality reductions, trimming, and watermarking.

**Perceptual audio hashes** (Chromaprint) match audio content across different encodings, bitrates, and formats by capturing the acoustic fingerprint of the content.

**Text similarity hashes** (SimHash) use locality-sensitive hashing for near-duplicate text detection. SimHash maps similar texts to similar hash values, so two texts that differ by a few words (typical spam template variations) produce hash values that are "close" by a defined distance metric. This allows a spam detection system to flag a template once and match all the variations.

**Hash scopes** specify which part of the content was hashed, enabling precise curation entries:

- `media-bytes`: Raw media file bytes (for exact matches)
- `media-pixels`: Decoded pixel/sample data (for format-agnostic matching)
- `perceptual-image`: Perceptual hash of image content
- `perceptual-video`: Perceptual hash of video content
- `perceptual-audio`: Audio fingerprint
- `text-exact`: Raw text bytes (for exact text matching)
- `text-normalized`: Unicode-normalized, whitespace-collapsed text (for text matching regardless of formatting)

### Chapter 29: Curation Entries

A `CurationEntry` contains:

- **subjects**: One or more content hash references (same content hashed with different algorithms)
- **authority**: The curator issuing the judgment (URI identifying the Authority Declaration)
- **issued**: When the judgment was made
- **reason**: A structured reason code from the defined taxonomy
- **ordinal**: A numeric severity/confidence score
- **evidence**: Optional supporting evidence (itself a content-addressed reference)
- **expires**: Optional expiration (for temporary curations — e.g., electoral misinformation expires after the election)
- **supersedes**: Optional reference to an earlier curation this one replaces

**The `subjects` array.** A single curation entry can list multiple subject hashes because the same content may be representable in multiple ways. Consider a JPEG image of known CSAM: it has a SHA-256 hash (a precise byte-for-byte fingerprint of this exact file) and a PDQ hash (a perceptual fingerprint capturing the visual content). A perpetrator who recompresses the image will produce a different SHA-256 but a PDQ hash that still matches the original within the perceptual similarity threshold. By including both hashes as subjects of the same entry, the curator issues a single judgment that can be matched by exact-match systems (using SHA-256) and by perceptual-match systems (using PDQ). Operators that support both hash types can check both; operators that support only one type will still benefit from whichever subject hash they can compute. The single entry also means there is one canonical judgment for the content — the authority, the reason, the ordinal, and any evidence are stated once, not duplicated.

**The `ordinal` field.** The ordinal is a single numeric field used across all categories, but its semantics vary by category in well-defined ways:

- For `legal/csam-detected`, the only meaningful value is `1.0` — meaning "this is confirmed CSAM." There is no confidence spectrum for a confirmed CSAM hash: it either matches a known hash or it doesn't. An ordinal of `0.5` for CSAM would be meaningless; `0.0` means not flagged; `1.0` means flagged.

- For `spam/spam-commercial`, an ordinal of `0.85` means "85% confidence this is commercial spam." An operator might block at `0.9` and label-as-spam at `0.7`. The ordinal is a classifier confidence score that operators can threshold according to their policy.

- For `editorial/editor-pick`, an ordinal of `5.0` means "ranked 5th in the editor's picks." Higher ordinals are better picks; ordinal `1.0` is the top pick. Operators can sort by ordinal descending to display the editor's ranking in order.

- For suppression use cases, an ordinal of `-1.0` means "suppress this content." Negative values signal removal-strength rather than presence-strength; the more negative, the stronger the suppression signal.

A single field is used for all these semantics because it makes the matching logic uniform: an operator configures a threshold for each (category, action) pair and compares the entry's ordinal against it. An operator policy might say: `legal/csam-detected` ordinal >= 1.0 → immediate block; `spam/spam-commercial` ordinal >= 0.8 → block; `spam/spam-commercial` ordinal >= 0.6 → label. The comparison is always the same operation regardless of whether the number represents a confidence score, a rank, or a binary flag. A more complex field (separate confidence and rank fields, enum action types) would require category-specific matching logic in every operator implementation. The single numeric field keeps the common case simple.

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

- `legal/csam-detected` at ordinal `1.0`: Published by child safety organizations (NCMEC, IWF) and law enforcement-designated bodies. An operator receiving this entry has no discretion: they block the content immediately and in most jurisdictions are legally required to report it. There is no "label but allow" response to a confirmed CSAM hash.

- `quality/low-quality` at ordinal `0.6`: Published by community moderation organizations, editorial boards, or algorithmic quality detectors. An operator might downrank the content (show it lower in feeds) rather than block it. A children's platform might block it; a general-purpose platform might only suppress it from recommendations. There is operator discretion here, which is appropriate for a judgment about quality rather than law.

- `editorial/editor-pick` at ordinal `10.0`: Published by editorial organizations, curated content boards, or trusted communities. An operator might surface entries with high ordinals in a "curated" or "featured" feed, or use them as signals for recommendation algorithms. These entries represent positive curation rather than suppression.

**The `expires` and `supersedes` fields.** These fields handle two common operational realities.

`expires` is used for curations that are inherently time-bounded. Electoral misinformation (`misinfo-electoral`) entered during an election campaign should expire after the election, since the same content may not be misleading in a historical context. A temporary account suspension (flagged with a safety reason) might be set to expire in 30 days. After expiration, operators should treat the entry as if it never existed; they should not apply an expired curation to incoming content.

`supersedes` is used when a curator updates a prior judgment. An investigation might proceed in stages: an initial entry at `legal/csam-suspected` is published when content is flagged for review; after the investigation concludes, a second entry at `legal/csam-detected` (or a retraction entry) supersedes the original. The superseding entry carries the CID of the entry it replaces. Operators that receive both entries should apply only the superseding one. This allows curators to correct mistakes (a false positive that is subsequently cleared) without requiring all subscribing operators to be notified out-of-band; the feed itself carries the correction.

### Chapter 30: Curation Authority Declarations

Before publishing curations, a curator must publish an Authority Declaration. This is not merely a formality — it is the accountability mechanism that distinguishes a legitimate curator from an anonymous content-removal service with no oversight.

Without a declaration, curations are anonymous assertions: a signed statement that some content has some property, with no way to determine who made the judgment, on what basis, or how to challenge it. Accountability requires knowing who is speaking. The declaration creates that accountability: it names the organization, describes how it makes decisions, establishes how errors can be corrected, and commits the organization to a published set of procedures. Every curation entry is traceable to this declaration. An operator that subscribes to a curator's feed is not subscribing to an opaque list of hashes; it is subscribing to the judgments of a named entity with a declared governance structure and an appeal mechanism.

The Authority Declaration contains:

- **Public key**: For verifying the curator's signatures.
- **Organization details**: Name, type (government agency, nonprofit, commercial entity), registration information.
- **Jurisdiction claims**: Which regions' laws the curator operates under. A `"global"` claim covers all jurisdictions; specific claims like `"US"` or `"EU"` indicate jurisdiction-specific curations.
- **Governance model**: A link to documentation of how the organization makes its curation decisions. What's the process? Who makes decisions? What oversight exists?
- **Appeal process**: A link to documentation of how content creators and operators can challenge a curation judgment.
- **Hash capabilities**: Which hash types the curator produces, so operators know which of their content-hashing infrastructure to use for matching.
- **Delegate keys**: Automated systems (ML classifiers, batch processing pipelines) authorized to sign curation entries on behalf of the authority.

**`governanceModel`.** This field links to documentation explaining how the curator makes its decisions. The field is a transparency requirement, not a quality bar: the protocol requires that something be published, not that it meet any particular standard of governance rigor. Different curators will have very different governance structures, and all of them are legitimate.

NCMEC's governance is defined by US federal law (the Protect Our Children Act and similar legislation), by congressional oversight, and by its status as a government-designated nonprofit. Its governance document would reference those legal instruments. A community-operated spam detection service might be governed by a committee of volunteer operators, with decisions made by majority vote and documented in a GitHub repo with an RFC-style proposal process. A commercial classifier might be governed by the company's internal policies with an external audit. The point is that the governance document exists and is linked — operators that subscribe to a curator's feed can read how that curator operates. An operator choosing to subscribe to a spam detection feed can evaluate whether the governance model is appropriate for the trust they're placing in that feed.

**`appealProcess`.** This field links to documentation explaining how judgments can be challenged and corrected. It is specifically required because automated classifiers make mistakes, and false positives have real consequences for legitimate creators.

A photographer whose artistic nude work is flagged as `nsfw-sexual` needs a mechanism to have that judgment reconsidered or overturned. A journalist whose legitimate reporting on extremism is flagged for containing extremist content needs a way to explain the context. A security researcher whose post about malware is flagged as spam needs recourse. The appeal process is how these errors get corrected. An authority declaration without an appeal mechanism would mean curations are effectively irreversible — a curator could flag content with no accountability for errors. The protocol requires the mechanism to exist; it does not specify how long appeals take or what criteria the curator uses, because those are governance decisions for the curator.

**`jurisdictionClaims`.** Curators may have legal authority only within certain jurisdictions, and operators in different jurisdictions appropriately give different weight to different curator authority claims.

A government agency's copyright enforcement body claims authority within its jurisdiction. A US Digital Millennium Copyright Act takedown notice carries legal weight for operators subject to US law, but an operator in Germany running under German law may give it different weight than a `court-order` entry from a German court. A global CSAM hash database operated by an international coalition (with mandates from multiple governments) claims global authority and is treated as high-authority by operators in all those jurisdictions.

This field allows operators to implement jurisdiction-appropriate trust hierarchies. An operator serving primarily European users might give higher weight to entries from EU-authorized bodies; a global operator might treat entries from global authorities as universally applicable and jurisdiction-specific entries as applicable only to users in the named jurisdiction.

**`delegateKeys`.** Automated systems sign curation entries on behalf of the authority rather than requiring a human to sign each entry manually. This is a practical necessity for high-volume curation.

A CSAM detection service might process tens of millions of images per day across all content uploaded to subscribing platforms. Having a human examine and sign each flagged curation entry is physically infeasible. An ML classifier that flags content at scale must be able to sign entries automatically. Delegate keys allow this: the authority declaration lists one or more delegate keys with a description of what systems they are authorized to represent. A curation entry signed by a delegate key is treated as if it were signed by the authority, because the authority declaration itself (signed by the authority's root key) names the delegate key and authorizes it.

Delegate keys have narrower authority than the authority's root key. The declaration specifies what categories and hash types each delegate key is authorized to produce. A delegate key used by a CSAM classifier might be authorized only for `legal/csam-detected` and `legal/csam-suspected` entries, not for editorial or quality judgments. If a delegate key's private key is compromised (e.g., a server breach), the authority can revoke it by publishing an updated declaration that removes the key, without affecting the authority's root key or other delegate keys.

### Chapter 31: How Operators Use Curations

Operators subscribe to whichever curators they choose. A typical operator might subscribe to:

- An NCMEC/CSAM hash database curator (legally required in many jurisdictions)
- A general spam detection curator
- An NSFW classification curator
- An editorial/quality curator (for recommending high-quality content)

**The policy table.** An operator's curation policy is a table of `(curator, reason-pattern, ordinal-threshold, action)` rules. Each row says: when this curator signals this reason at this confidence level or above, take this action. A concrete example:

```
Curator: NCMEC CSAM Database
  legal/csam-detected  ≥ 1.0  → BLOCK_IMMEDIATELY + REPORT
  legal/csam-suspected ≥ 0.8  → QUARANTINE + HUMAN_REVIEW

Curator: SpamShield Pro
  spam/spam-commercial  ≥ 0.9  → BLOCK
  spam/spam-commercial  ≥ 0.6  → LABEL("spam")
  spam/spam-phishing    ≥ 0.7  → BLOCK + WARN_USERS

Curator: NSFW Classifier
  nsfw/nsfw-sexual     ≥ 0.8  → HIDE_FROM_MINORS
  nsfw/nsfw-gore       ≥ 0.9  → BLOCK

Curator: Editorial Board
  editorial/editor-pick ≥ 1.0  → BOOST_IN_RECOMMENDATIONS
```

This is not a wire format — it is illustrative of the data structure an operator maintains internally to drive policy evaluation. The protocol specifies what curators publish and what operators must check; how the operator stores and evaluates its policy rules is an implementation choice.

**The content check pipeline.** When content arrives — either a new local post or an incoming reply submission — the operator runs it through its curation policy before publishing. The pipeline:

1. Compute all hash types that any subscribed curator uses. SHA-256 is always computed. PDQ perceptual hashes are computed if any curator uses perceptual image matching. TMK+PDQ video hashes are computed if any curator uses video matching. The operator knows which hash types are needed based on the `hashTypes` declared in each subscribed curator's authority declaration.
2. Check each hash against the Bloom filters for all subscribed curators. A Bloom filter negative is a fast, local memory operation. Hashes that are definitely not in any curator's filter skip the network lookup entirely — this is the fast negative path, and it handles the vast majority of content.
3. For hashes that produce a Bloom filter positive, fetch the sharded-path entry to get the actual CurationEntry and confirm the match (or discard the false positive).
4. Apply the policy table. Evaluate rules in order of severity. If the highest-severity match action is `BLOCK_IMMEDIATELY`: block and stop — do not evaluate further. If the action is `QUARANTINE`: hold for human review, do not publish. If the action is `LABEL`: publish with the label attached. If no rules match: publish.

**Conflicting curator signals.** Curators will sometimes disagree about the same content. A perceptual hash match from an NSFW classifier might assign `nsfw/nsfw-sexual` at ordinal 0.85. The same post might be in an editorial curator's list with `editorial/editor-pick` at ordinal 3.0. These are signals from different categories with different stakes.

The recommended resolution policy: reason categories have an operator-configured severity ranking, and higher-severity categories override lower-severity ones. Legal and safety categories always outrank editorial categories. Within the same category, the more conservative action prevails — block beats label, label beats allow. An `nsfw` signal that requires hiding content from minors does not prevent the content from being boosted in adult recommendations on an adult-oriented platform; the actions apply to different dimensions of content handling. An operator is free to configure its own priority logic; this recommendation is not a protocol requirement.

**Retroactive matching in practice.** When a new curation entry arrives in a subscribed curator's feed, the operator must check whether any content it has already stored matches the new entry. A new CSAM hash appearing in NCMEC's database means the operator must search its own content store for that hash and apply its policy if found.

The implementation challenge is doing this at scale without disrupting service. An operator with billions of stored content items cannot scan them linearly every time a new curation entry arrives. The recommended implementation: maintain a content hash index — a database table mapping each content hash to the list of CIDs that contain it. When new curation entries arrive, query this index for each new hash. Matches trigger immediate policy application. For operators with large content stores, this index is not optional; it is the only way retroactive matching completes in bounded time.

The protocol requires that retroactive matching happen. It does not specify how to implement the index. That is an operator concern.

**No global enforcement.** The operator enforces curations within its own infrastructure boundary. It checks content it hosts and content flowing through its reply protocol. It cannot reach into another operator's IPFS node and remove content from there.

If Operator B hosts content that Operator A has curated as harmful, Operator A's options are: refuse to display it to its own users, refuse to forward it in reply chains that pass through Operator A, and optionally defederate from Operator B entirely. What Operator A cannot do is force Operator B to remove the content. The enforcement boundary is the operator's own infrastructure. This is the correct model: enforcement authority should be limited to what you actually control. Accountability without control is a recipe for liability without remediation.

### Chapter 32: Static Curation Hosting

Not every curator needs to run a live API server. A child safety organization maintaining a CSAM hash database may prefer to publish it as static files on S3 or a CDN — simpler to operate, cheaper to scale, and compatible with any HTTP client. The static hosting specification enables this: curation feeds can be served from static infrastructure with no custom server software.

**The design constraint** is that curation databases can be large (tens of millions of hashes) and are queried by content hash. Serving a single file containing all entries doesn't work: downloading gigabytes to check one hash is impractical. The solution is a two-layer structure: path sharding for individual-entry lookups, plus a Bloom filter for fast bulk screening.

**Directory sharding.** Entries are stored in a path hierarchy based on the content hash being curated. The first two hex characters of the hash form the first directory level; the next two form the second level. A CurationEntry covering hash `a3f9c2...` is stored at:

```
/feeds/example-authority/entries/a3/f9/a3f9c2...ndjson
```

A client that wants to check whether hash `a3f9c2...` has any curation entries fetches that path. If the file exists, it contains one or more CurationEntries (NDJSON format, one per line) for that hash. If the path returns 404, the hash has no entries. This lookup is exactly two path components and one HTTP GET — cacheable, CDN-compatible, O(1).

Why two levels of sharding (4 hex characters)? With SHA-256 hashes and millions of entries, two levels (256 × 256 = 65,536 directories) distributes the entries into small files of manageable size. One level (256 directories) would produce files with tens of thousands of entries per shard for large databases; three levels would produce mostly empty directories.

**The Bloom filter.** Individual hash lookups work for known content, but an operator receiving a new post needs to check it efficiently. Fetching the sharded path for every piece of content would mean one HTTP request per piece of content, which is acceptable but not ideal for high-volume operators. The feed provides a Bloom filter at:

```
/feeds/example-authority/bloom.bin
```

This file contains a serialized Bloom filter covering all hashes in the feed. An operator downloads the Bloom filter once (typically a few MB, even for databases of tens of millions of hashes, at 1% FPR with 10 bits per element) and checks content hashes locally. A Bloom filter negative — the hash is definitely not in the filter — means the content is definitely not curated by this authority. No HTTP request needed. A Bloom filter positive — the hash may be in the filter — triggers a sharded-path lookup to get the actual entry and confirm (or discard the false positive).

The Bloom filter is published alongside a metadata file that records its parameters: the number of hash functions, the bit-array size, the hash function family (double hashing: `(hash1 + i * hash2) mod m` with SHA-256-derived h1 and h2), and the count of inserted elements. This allows operators to check the FPR and decide whether to trust the filter's negative results.

**Incremental synchronization.** The feed publishes an append-only log of new entries at:

```
/feeds/example-authority/log/page-0001.ndjson.gz
/feeds/example-authority/log/page-0002.ndjson.gz
/feeds/example-authority/log/index.json
```

The `index.json` file lists the available log pages and the latest page's last sequence number. An operator that last synced to sequence 4820 fetches `index.json`, finds which pages contain sequences after 4820, downloads those pages, and applies the new entries. Pages are immutable once closed (a new page is opened when the current page exceeds a size threshold, typically 10 MB compressed). Immutability makes pages CDN-cacheable indefinitely.

A new operator that has never synced the feed downloads the **full snapshot**: a single large NDJSON.gz file containing all current entries as of a known sequence number. The feed provides snapshots at:

```
/feeds/example-authority/snapshots/snapshot-2025-01-01.ndjson.gz
```

After loading the snapshot, the operator switches to incremental sync from the snapshot's sequence number forward. The snapshot + incremental approach means a new operator can onboard a large dataset (tens of millions of entries) efficiently without paginating through millions of incremental log entries.

**No authentication required for reads.** Static curation feeds are public by design. Any operator can read any feed; there is no API key, no subscription credential, no access control. The integrity of the feed comes from the cryptographic signatures on the individual CurationEntries — each entry is signed by the curator's declared key, and the authority of the signature can be verified independently of the hosting infrastructure. A malicious CDN that serves modified entries cannot forge valid signatures without the curator's private key. This means operators don't need to trust the CDN; they trust the signatures.

---

