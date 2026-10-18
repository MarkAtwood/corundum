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

Corundum separates identity from hosting. Alice's identity is a W3C DID that only keys she holds can change; it names her current operator and the key that signs her content. Her content lives in IPFS, addressed by content hash. Her operator hosts her — but her identity and content exist independently of her operator. Moving operators is like switching ISPs: the number, the files, and the contacts all come with her.

Corundum also adds a formalized curation layer that ActivityPub lacks: cryptographically signed moderation feeds with mandatory governance declarations and appeal processes. The block enforcement model is stronger: blocks reject at the inter-operator level, not just client-side filtering.

---

**Q: How is this different from Bluesky / AT Protocol?**

A: The closest architectural comparison. Both use content-addressed data and DIDs. The key differences:

- **Storage substrate**: AT Protocol uses its own repository format served by PDS nodes. Corundum uses IPFS directly — any IPFS node can serve Corundum content.
- **Relays and indexers**: AT Protocol has Relays (originally called the Big Graph Service) that aggregate repository updates from PDS nodes into a firehose, and AppViews that index it. Corundum has no relay or indexer layer; federation is operator-to-operator.
- **DID methods**: AT Protocol supports `did:plc` and `did:web`. Corundum uses `did:webvh` by default and also accepts `did:plc` and `did:key`; it does not accept plain `did:web`, because a `did:web` document has no signed history.
- **Curation**: AT Protocol labels are signed by the labeler's key, but the protocol does not require labelers to declare how they decide or how to appeal. Corundum requires curators to publish authority declarations with governance and appeal processes before any judgments.

Neither is strictly superior. AT Protocol has millions of users and production validation. Corundum has mandatory curator accountability and no relay layer.

---

**Q: How is this different from Nostr?**

A: Nostr gets the core identity insight right (keypair = identity) and the storage separation right (relays are just storage, not identity). But it leaves unspecified the things that become serious problems at scale: key recovery (lose your key, lose your identity — no recovery), content archive structure (your content is wherever relays have cached it, with no formal portability), and moderation (ad hoc per relay).

Corundum adds DID-based recovery on top of keypair identity, a formalized content-addressed archive with O(1) lookups, authenticated inter-operator communication via RFC 9421, and the full curation infrastructure. It's more complex than Nostr, and the complexity serves specific purposes.

---

**Q: What problem does the curation system solve that existing moderation doesn't?**

A: Today's platform moderation is opaque, non-transferable, and unaccountable. A post is removed; you don't know who decided, what authority they had, or how to challenge it. The platform is judge, jury, and executioner with no separation of roles.

Corundum's curation system separates three things:
1. **Judgment**: Curators publish signed statements — "content with hash X is CSAM," "content with hash Y is spam." The judgment is attributable, verifiable, and auditable.
2. **Authority**: Before publishing any judgments, curators must publish an Authority Declaration: who they are, how they make decisions, and how judgments can be appealed. No anonymous curators.
3. **Enforcement**: Operators subscribe to curator feeds and apply their own policies. The curator says what; the operator decides what to do about it.

The practical consequence: a curator publishes once and its judgments reach every subscribing operator on their next poll. No per-platform integration, and no bilateral agreement for every pair. Legal categories such as CSAM hash lists are the exception to open publication: those lists are distributed only to vetted providers, so their feeds require authenticated access. And an operator serving adults can subscribe to a CSAM feed without subscribing to an NSFW classifier, because those are different policy decisions.

---

**Q: How does block enforcement work? Why is it "stronger" than other platforms?**

A: When Alice blocks Steve, Alice's operator rejects all reply submissions from Steve's identity at the protocol level. Steve cannot submit a reply to Alice's post; his operator receives a `REPLY_REJECTED` error with reason `blocked-user`. The reply never enters Alice's reply tree — not just hidden from Alice's view, but absent from her thread for everyone. Steve can still say what he likes on his own timeline; he cannot attach it to Alice's conversation.

On most existing platforms, blocks are client-side filters. You don't see the person's content, but they can still reply to your posts, still visible to your other followers, still using your content as a harassment venue — you just don't see it directly. Corundum's block is enforced at the inter-operator authentication layer, not the client layer.

Retroactive removal is also architectural: when Alice blocks Steve, her operator scans her existing reply trees and removes Steve's prior replies, republishing her reply index. The removal is propagated, not just cached locally.

---

**Q: What does "portable identity" actually mean when I migrate operators?**

A: When Earl moves from his self-hosted server to Birdsite:

1. Birdsite generates a new content-signing key for Earl.
2. Earl's app signs an update to his DID document with his update key, naming Birdsite's new key and Birdsite as his operator. Earl never hands anyone a private key.
3. Birdsite fetches his complete content archive from IPFS. Every item is verified by CID.
4. Birdsite publishes a RootManifest under the new key, committing to exactly the same archive.
5. Birdsite sends a MigrationNotification to the operators of Earl's followers, which re-resolve his DID and see the change.

Earl's followers don't notice anything change. His DID is unchanged. His handle is unchanged (if he controls his domain). His post history is intact. He turns off his old server.

A hostile old operator cannot stop this. The DID update is the only step that carries authority, and only Earl's update key can make it. Everything else Birdsite needs is in IPFS. The old operator still has the old content key, but Earl's DID no longer names it, so nothing it signs is accepted.

---

**Q: If content is stored in IPFS, how does deletion work? What about GDPR?**

A: IPFS content addressing is designed for permanence — a CID is the hash of the content, and any node that has pinned it can serve it. This creates a genuine tension with GDPR's right to erasure.

Corundum's approach:
- The archive tree never changes once written. A deletion is a new signed tombstone entry that names the deleted post.
- The operator unpins the deleted activity and its signing record from its IPFS node.
- The operator notifies operators known to have fetched that content, who are expected to unpin it too (SHOULD-level obligation).
- The deleted post's identifier stays in the archive tree. It is a hash, but a hash of personal data is still personal data under GDPR, so Corundum treats it that way and retains it on an integrity basis.
- A legal hold binds only the operator that is subject to it; it never obliges other operators to keep content.

Corundum does not claim to make IPFS GDPR-proof. It provides the mechanisms (tombstones, erasure notifications, retention metadata) that a GDPR-compliant deployment needs. Compliance depends on operators entering into data sharing agreements with each other and faithfully implementing the tombstone pathway. The protocol provides the plumbing; the compliance depends on the humans operating it.

---

### About the Implementation

---

**Q: Why Rust?**

A: The protocol's requirements map well to Rust's strengths:

- **Correctness is non-negotiable**: A signature verification failure means interoperability breaks. Byte-exact signing, CID computation, and the strict Ed25519 verification profile have failure modes that are easy to get subtly wrong. Rust's type system makes many of these errors compile-time failures.
- **Cryptographic code**: `ed25519-dalek` is a well-audited, timing-resistant Ed25519 implementation. Using it in Rust gives us the full benefits without an FFI boundary.
- **Performance**: A Corundum operator is I/O-bound (IPFS fetches, database queries, network), but the hot path (CID hashing, signature verification for incoming reply submissions) benefits from fast execution.
- **Async ecosystem**: `tokio` + `axum` + `reqwest` is a mature, well-understood async stack for HTTP servers and clients.
- **Deployment**: A single statically-linked binary with minimal runtime dependencies is easy to deploy.

---

**Q: What does the reference implementation include?**

A: The MVP scope covers the minimum needed to run a conforming operator:

- Detached JWS signing and verification over stored bytes, with a full test vector suite
- Ed25519 key generation, signing, and verification
- CID computation (SHA-256 + raw codec, using the `cid` and `multihash` crates)
- Kubo HTTP API client (add/get/pin/unpin, IPNS publish/resolve)
- RootManifest creation, signing, and IPFS publication
- Timeline management: entries, chunks, epoch finalization, ArchiveIndex
- Operator Manifest at `/.well-known/corundum-operator` via HTTPS
- HTTP Message Signatures (RFC 9421) for all inter-operator requests
- Reply submission endpoint (inbound validation: HTTP sig, block list, signing record, content hash, curation check, rate limits)
- Reply submission client (outbound: sign and POST to a remote operator)
- Standard error envelope and cursor-based pagination for collection endpoints
- SQLite for user records, DID→IPNS cache, and metadata indexes

Deferred to post-MVP: `did:plc` and `did:key` (the MVP resolves `did:webvh` only), handle resolution, curation feed subscriptions beyond stub interface, chunked media, extensible ATD system, WebSocket/SSE event streams, user migration, post-quantum algorithm support.

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

For a single-operator deployment, SQLite on local disk is entirely sufficient. Multi-node deployments will need a different approach; that's a post-MVP problem.

---

**Q: How hard is it to build a social platform on top of this?**

A: The reference implementation exposes the inter-operator backbone. Building a user-facing social platform on top of it means adding:

1. A client-facing API (REST, GraphQL, whatever) for your own users — entirely your design and not part of the protocol (`docs/client-api/` describes a non-normative reference API you can use or ignore)
2. A user interface (web app, mobile app)
3. A recommendation algorithm for feed ranking — your choice
4. Business logic for subscriptions, account tiers, etc. — your choice

The Corundum layer handles: storing and retrieving your users' content from IPFS, publishing their manifests, accepting replies from other operators' users, enforcing your users' block lists, applying curation policies to incoming content, and sending your users' replies to other operators.

Think of Corundum as the SMTP layer for social media. You don't think about SMTP when you design a mail client; it's just what mail servers speak to each other. Corundum is what social media servers speak to each other.

---

**Q: Can existing platforms (Mastodon, Bluesky) interoperate with Corundum operators?**

A: Not directly out of the box — they speak different protocols. Bridge implementations are future work, explicitly listed in the spec as such.

Corundum activities are ActivityStreams 2.0 objects, so the vocabulary maps, but bridging is not easy. Corundum identifies posts by CID and authenticates them with detached signatures; ActivityPub expects dereferenceable `https` identifiers and HTTP Signatures. A bridge has to mint and serve `https` identities for Corundum content and vouch for it with its own keys. AT Protocol shares DIDs and content addressing, but its repositories, records, and labels are different structures, so a bridge there is a translation layer too.

Mastodon *client apps* are a different matter: `docs/client-api/13-mastodon-shim.md` describes a non-normative shim that lets them talk to a Corundum operator. That is a client API, not a federation bridge.

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

The most valuable contributions right now are the unglamorous ones: JWS signing test vectors, CID computation verification against known-good implementations, and HTTP Message Signature conformance testing. The cryptographic underpinnings must be correct before anything else matters.
