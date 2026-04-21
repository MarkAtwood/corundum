# PRFAQ: Corundum Federated Social Protocol — Rust Reference Implementation

---

## Press Release

**FOR IMMEDIATE RELEASE**

### Corundum Reference Implementation Ships in Rust — Federated Social Media With Portable Identity, IPFS-Backed Content, and Verifiable Moderation

*The first conforming implementation of the Corundum protocol gives developers a working operator they can build on, fork, or federate with.*

**[LOCATION] —** The Corundum project today released its Rust reference implementation, completing the path from protocol specification to working software. Corundum is a federated social media protocol built on three ideas that no major platform offers together: cryptographic identity you own, content stored in IPFS that no single server controls, and a moderation architecture that separates judgment from enforcement.

The reference implementation ships as a single operator binary — a conforming Corundum operator that any developer can run, federate with, or use as the foundation for their own social platform. It implements the complete inter-operator backbone: identity management backed by W3C Decentralized Identifiers, a two-level Merkle archive for user timelines stored in IPFS, authenticated inter-operator communication via HTTP Message Signatures (RFC 9421), and the reply protocol with its block enforcement and curation feed integration.

"The problem with centralized social media isn't that the platforms are evil," the project notes in its specification preface. "It's that the architecture gives them options that shouldn't exist: the option to hold your identity hostage, the option to lose your content when they shut down, the option to change the rules on you with no recourse. Corundum removes those options at the protocol level."

The reference implementation is written in Rust and uses Kubo (the IPFS reference implementation) for content-addressed storage. It requires no configuration to federate with other Corundum operators — federation is permissionless by design. An operator that knows another operator's domain can authenticate to it, submit replies to its users, and receive replies from its users, with no prior agreement required.

The implementation is available at [repository URL] under [LICENSE].

---

## Frequently Asked Questions

### About the Protocol

---

**Q: What is Corundum, in one sentence?**

A: Corundum is a protocol that lets independently operated social media servers exchange content, while ensuring users own their identity, their content is stored permanently in IPFS, and content moderation decisions are made by accountable entities rather than hidden in platform black boxes.

---

**Q: How is this different from Mastodon / ActivityPub?**

A: ActivityPub ties your identity to your server. `@alice@social.example` only works as long as `social.example` is running. If the server shuts down, Alice loses her identity, her post history, and her follower list. Moving requires the old server's cooperation and still loses post history.

Corundum separates identity from hosting. Alice's identity is an IPNS name (a hash of her public key) anchored to a W3C DID document. Her content lives in IPFS, addressed by content hash. Her operator hosts her — but her identity and content exist independently of her operator. Moving operators is like switching ISPs: the number, the files, and the contacts all come with her.

Corundum also adds a formalized curation layer that ActivityPub lacks: cryptographically signed moderation feeds with mandatory governance declarations and appeal processes. The block enforcement model is stronger: blocks reject at the inter-operator level, not just client-side filtering.

---

**Q: How is this different from Bluesky / AT Protocol?**

A: The closest architectural comparison. Both use content-addressed data and DIDs. The key differences:

- **Storage substrate**: AT Protocol uses its own repository format served by PDS nodes. Corundum uses IPFS directly — any IPFS node can serve Corundum content.
- **Global indexer**: AT Protocol defines a "Big Graph Service" that crawls all PDS nodes. Corundum has no global relay or indexer by design; federation is operator-to-operator.
- **DID methods**: AT Protocol standardized on `did:plc`. Corundum supports `did:web`, `did:plc`, and `did:key` — more flexibility, more to implement.
- **Curation**: AT Protocol's labeler system is functional but less formally specified — no mandatory governance declarations, no required accountability mechanism. Corundum requires curators to publish authority declarations with governance and appeal processes before any judgments.

Neither is strictly superior. AT Protocol has millions of users and production validation. Corundum has a more formally specified curation system and stronger decentralization (no global relay).

---

**Q: How is this different from Nostr?**

A: Nostr gets the core identity insight right (keypair = identity) and the storage separation right (relays are just storage, not identity). But it leaves unspecified the things that become serious problems at scale: key recovery (lose your key, lose your identity — no recovery), content archive structure (your content is wherever relays have cached it, with no formal portability), inter-relay authentication (none), and moderation (ad hoc per relay).

Corundum adds DID-based recovery on top of keypair identity, a formalized content-addressed archive with O(1) lookups, authenticated inter-operator communication via RFC 9421, and the full curation infrastructure. It's more complex than Nostr, and the complexity serves specific purposes.

---

**Q: What problem does the curation system solve that existing moderation doesn't?**

A: Today's platform moderation is opaque, non-transferable, and unaccountable. A post is removed; you don't know who decided, what authority they had, or how to challenge it. The platform is judge, jury, and executioner with no separation of roles.

Corundum's curation system separates three things:
1. **Judgment**: Curators publish signed statements — "content with hash X is CSAM," "content with hash Y is spam." The judgment is attributable, verifiable, and auditable.
2. **Authority**: Before publishing any judgments, curators must publish an Authority Declaration: who they are, how they make decisions, and how judgments can be appealed. No anonymous curators.
3. **Enforcement**: Operators subscribe to curator feeds and apply their own policies. The curator says what; the operator decides what to do about it.

The practical consequence: a CSAM hash database publishes once and propagates to every subscribing operator on their next poll. No per-platform integration. No bilateral agreement for every pair. And an operator serving adults can subscribe to the CSAM database (legally required in most jurisdictions) without subscribing to the NSFW classifier — because those are different policy decisions.

---

**Q: How does block enforcement work? Why is it "stronger" than other platforms?**

A: When Alice blocks Steve, Alice's operator rejects all reply submissions from Steve's identity at the protocol level. Steve cannot submit a reply to Alice's post; his operator receives `BLOCKED_USER` rejection. The reply never appears in Alice's thread — not just hidden from Alice's view, but absent for everyone.

On most existing platforms, blocks are client-side filters. You don't see the person's content, but they can still reply to your posts, still visible to your other followers, still using your content as a harassment venue — you just don't see it directly. Corundum's block is enforced at the inter-operator authentication layer, not the client layer.

Retroactive removal is also architectural: when Alice blocks Steve, her operator scans her existing reply trees and removes Steve's prior replies, republishing the updated tree CIDs. The removal is propagated, not just cached locally.

---

**Q: What does "portable identity" actually mean when I migrate operators?**

A: When Earl moves from his self-hosted server to Birdsite:

1. Earl provides his IPNS private key (or a migration key) to Birdsite.
2. Birdsite resolves Earl's existing RootManifest, reads the ArchiveIndex, and fetches his complete content archive from IPFS. Every item is verified by CID.
3. Birdsite publishes a new RootManifest under Earl's IPNS name, declaring itself as the new operator.
4. Birdsite broadcasts a MigrationNotification signed with Earl's key.
5. Other operators that receive the notification update their DID→IPNS cache.

Earl's followers don't notice anything change. His IPNS name — the hash of his public key — is unchanged. His DID is unchanged. His handle is unchanged (if he controls his domain). His post history is intact. He turns off his old server.

In a hostile migration (old operator uncooperative or offline): Earl uses his DID recovery key to authorize a new IPNS keypair. The presence of the DID recovery key signature in the MigrationNotification is what proves the migration is authorized — even without the old operator's participation.

---

**Q: If content is stored in IPFS, how does deletion work? What about GDPR?**

A: IPFS content addressing is designed for permanence — a CID is the hash of the content, and any node that has pinned it can serve it. This creates a genuine tension with GDPR's right to erasure.

Corundum's approach:
- The archive structure (ArchiveIndex, epochs, entries) remains intact for integrity. You can't remove entries from epochs without breaking the chain.
- What can be removed is the content the entry points to: the operator unpins the activity from its IPFS node and publishes a tombstone. The entry's `content` field becomes null.
- The operator distributes tombstone notifications to operators known to have requested that content, who are expected to unpin on receipt (SHOULD-level obligation).
- For legal holds (`retainUntil`): content is hidden from display but retained in storage until the hold expires. GDPR Art. 17(3)(e) provides an explicit exception for legal proceedings.

Corundum does not claim to make IPFS GDPR-proof. It provides the mechanisms (tombstones, erasure notifications, retention metadata) that a GDPR-compliant deployment needs. Compliance depends on operators entering into data processing agreements with each other and faithfully implementing the tombstone pathway. The protocol provides the plumbing; the compliance depends on the humans operating it.

---

### About the Implementation

---

**Q: Why Rust?**

A: The protocol's requirements map well to Rust's strengths:

- **Correctness is non-negotiable**: A signature verification failure means interoperability breaks. Canonical JSON serialization with NFKC normalization has multiple failure modes that are easy to get subtly wrong. Rust's type system makes many of these errors compile-time failures.
- **Cryptographic code**: `ed25519-dalek` is a well-audited, timing-resistant Ed25519 implementation. Using it in Rust gives us the full benefits without an FFI boundary.
- **Performance**: A Corundum operator is I/O-bound (IPFS fetches, database queries, network), but the hot path (canonical JSON serialization, signature verification for incoming reply submissions) benefits from fast execution.
- **Async ecosystem**: `tokio` + `axum` + `reqwest` is a mature, well-understood async stack for HTTP servers and clients.
- **Deployment**: A single statically-linked binary with minimal runtime dependencies is easy to deploy.

---

**Q: What does the reference implementation include?**

A: The MVP scope covers the minimum needed to run a conforming operator:

- Canonical JSON serialization with NFKC normalization and full test vector suite
- Ed25519 key generation, signing, and verification
- CID computation (SHA-256 + dag-json codec, using the `cid` and `multihash` crates)
- Kubo HTTP API client (add/get/pin/unpin, IPNS publish/resolve)
- RootManifest creation, signing, and IPFS publication
- Timeline management: entries, chunks, epoch finalization, ArchiveIndex
- Operator Manifest at `/.well-known/corundum-operator` via HTTPS
- HTTP Message Signatures (RFC 9421) for all inter-operator requests
- Reply submission endpoint (inbound validation: HTTP sig, block list, signing record, content hash, curation check, rate limits)
- Reply submission client (outbound: sign and POST to a remote operator)
- Standard error envelope and cursor-based pagination for collection endpoints
- SQLite for user records, DID→IPNS cache, and metadata indexes

Deferred to post-MVP: DID layer (raw IPNS only for MVP), handle resolution, curation feed subscriptions beyond stub interface, chunked media, extensible ATD system, WebSocket/SSE event streams, user migration, post-quantum algorithm support.

---

**Q: How does the implementation talk to IPFS?**

A: Kubo (the reference IPFS implementation, formerly go-ipfs) runs as a separate process. The Corundum implementation talks to Kubo's localhost HTTP API on port 5001 — a thin `reqwest`-based wrapper around a handful of endpoints (`/api/v0/add`, `/api/v0/cat`, `/api/v0/pin/add`, `/api/v0/name/publish`, etc.).

No IPFS client library or IPLD framework is pulled in. The IPFS heavy lifting (DHT, peer-to-peer connectivity, bitswap, garbage collection) is entirely Kubo's responsibility. The Corundum binary is a protocol server; Kubo is the storage backend.

The Kubo HTTP API is localhost-only and must not be exposed publicly. The architecture is: `internet → Corundum server (authenticated, TLS) → Kubo HTTP API (unauthenticated, localhost)`.

---

**Q: What's the database story?**

A: SQLite via `rusqlite`. The IPFS content store is the authoritative source of truth for all Corundum objects (activities, signing records, manifests). SQLite is an index that makes the content store queryable.

Specifically, SQLite stores:
- User records (DID, current IPNS name, current operator endpoint, last-seen timestamp)
- DID→IPNS cache (with TTL; expires after 24 hours, re-resolved from DID document)
- Content hash index (SHA-256 → list of entry CIDs; required for efficient retroactive curation matching)
- Rate limiting counters (per-operator, per-user, rolling time windows)
- Pending reply submission queue (for retry backoff)
- Bloom filter parameters and pinned filter CIDs for block lists

For a single-operator deployment, SQLite on local disk is entirely sufficient. Multi-node deployments will need a different approach; that's a post-MVP problem.

---

**Q: How hard is it to build a social platform on top of this?**

A: The reference implementation exposes the inter-operator backbone. Building a user-facing social platform on top of it means adding:

1. A client-facing API (REST, GraphQL, whatever) for your own users — entirely your design, completely unspecified by Corundum
2. A user interface (web app, mobile app)
3. A recommendation algorithm for feed ranking — your choice
4. Business logic for subscriptions, account tiers, etc. — your choice

The Corundum layer handles: storing and retrieving your users' content from IPFS, publishing their manifests, accepting replies from other operators' users, enforcing your users' block lists, applying curation policies to incoming content, and sending your users' replies to other operators.

Think of Corundum as the SMTP layer for social media. You don't think about SMTP when you design a mail client; it's just what mail servers speak to each other. Corundum is what social media servers speak to each other.

---

**Q: Can existing platforms (Mastodon, Bluesky) interoperate with Corundum operators?**

A: Not directly out of the box — they speak different protocols. Bridge implementations are future work, explicitly listed in the spec as such.

The data model compatibility makes ActivityPub bridges tractable at the content level: Corundum activities are ActivityStreams 2.0 objects, so the mapping exists. The identity model differences require careful handling (Mastodon `@alice@instance.social` vs. Corundum IPNS-anchored DID).

AT Protocol interoperability is more interesting: both use DIDs and content-addressed data, so a bridge that speaks both protocols is conceptually cleaner than an ActivityPub bridge.

Neither bridge is in the reference implementation's initial scope.

---

**Q: Is this ready for production use?**

A: The specification is mature and stable. The reference implementation, once complete, will be a correct, tested implementation of that specification — suitable for development, testing federation, and building on.

"Production use" for a real social platform involves concerns the reference implementation deliberately doesn't address: horizontal scaling, CDN integration, high-availability database setup, operational monitoring, abuse response processes. The reference implementation is the correct foundation for building that, not a turnkey solution.

---

**Q: What's the license?**

A: [TBD — to be determined before first release.]

---

**Q: How do I get involved?**

A: Read the spec. Start with [`docs/corundum-book.md`](docs/corundum-book.md) for orientation, then whichever part covers what you want to build or understand. File issues. Send PRs. The implementation roadmap is tracked in the project's issue tracker.

The most valuable contributions right now are the unglamorous ones: canonical JSON serialization test vectors, CID computation verification against known-good implementations, and HTTP Message Signature conformance testing. The cryptographic underpinnings must be correct before anything else matters.
