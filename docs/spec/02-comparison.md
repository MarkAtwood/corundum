## Part II: Context and Comparison

### Chapter 4: How Corundum Differs from Other Protocols

Before diving into the technical details of Corundum's design, it is worth situating it against the landscape of existing decentralized social protocols. The design decisions that follow only make sense when you understand what problems Corundum is trying to solve that other approaches do not, and vice versa. Every protocol in this space makes tradeoffs; none is simply better than the others across all dimensions.

**vs. ActivityPub / Mastodon**

ActivityPub is the W3C standard for federated social media, currently deployed at scale across the Mastodon network and dozens of compatible platforms. It is a mature, working system with millions of users. Understanding why Corundum does not build on ActivityPub requires understanding ActivityPub's specific limitations.

ActivityPub's identity model ties a user to a server. Your identity is `@alice@social.example`, which means Alice at the server `social.example`. The server hosts not just Alice's content but Alice's *identity*. Alice's followers know her as a specific URL on a specific server. When another instance wants to send Alice a message, it sends an HTTP POST to `social.example`. When a follower wants to fetch Alice's posts, they fetch them from `social.example`.

The consequence of server-tied identity is that Alice cannot move without losing something. Mastodon's "move account" feature lets Alice redirect followers to a new account on a different server, but it does not transfer her post history. Her old posts remain on the old server (until it shuts down) and do not appear on the new server. If `social.example` shuts down without notice — as many Mastodon instances have — Alice loses everything: her identity, her post history, her accumulated followers, all of it. Followers who didn't see the migration notice simply lose contact with Alice entirely.

Corundum's response is to separate identity from hosting. Alice's identity is a DID (`did:webvh` by default), resolved from her handle and controlled by update and recovery keys that Alice holds, not her operator. The DID names an IPNS name, which resolves to her signed RootManifest. Her content is stored in IPFS, addressed by content hash. By default her operator holds the IPNS key and signs on her behalf; Alice can hold it herself instead. Moving to a new operator means updating the DID to name the new operator's IPNS name; her DID and the identifiers of her existing content do not change, and signatures made by the old IPNS key after that update are rejected (Chapter 7).

ActivityPub also has no formalized curation infrastructure. Each Mastodon instance runs its own moderation in isolation. There is no mechanism for one instance's moderation team to share their judgments with another instance in a structured, verifiable way. Blocklists exist (lists of servers to defederate from) but they are informal, non-verifiable, and operated by third parties with no accountability mechanism. Corundum's curation system provides a formalized, cryptographically verifiable mechanism for sharing moderation judgments across the network.

One area where Corundum explicitly borrows from the ActivityPub ecosystem is the data model: Corundum uses ActivityStreams 2.0 objects (Notes, Articles, Images, Events, etc.) as its activity format. This is deliberate — ActivityStreams is a well-designed, widely-deployed standard for representing social activities. Corundum uses the data model but not the federation protocol.

**vs. AT Protocol / Bluesky**

The AT Protocol is the closest architectural comparison to Corundum, and deserves the most detailed treatment. Both systems were designed to solve the same fundamental problem: portable identity and content in a federated social network. Both use content-addressed data and DIDs. But they make different architectural choices, with different tradeoffs.

AT Protocol's data model is based on a "repository": a Merkle Search Tree (MST) of records (posts, follows, likes) representing the user's current state. Each published version of the tree is a commit, signed by the account's signing key, that points to the MST root by CID. The repository is not a history log: deleting a record removes it from the tree without a tombstone. The repository is served by a Personal Data Server (PDS), which is AT Protocol's equivalent of a Corundum operator. Corundum's archive is the opposite: an append-only tree that never changes once written, where edits and deletions are new signed entries (Chapter 13).

Corundum uses IPFS as the storage substrate. Posts are IPFS objects addressed by CID. The archive structure (epochs, ArchiveIndex) is an IPFS Merkle tree. This provides content-addressing and distributed availability natively — any IPFS node can pin and serve any piece of Corundum content. AT Protocol's repository format is its own, and content is served through PDS nodes, not through the broader IPFS network.

AT Protocol supports two DID methods: `did:plc`, a custom operation-log-based method used by most accounts, and `did:web`. `did:plc` has real advantages — it doesn't require owning a domain, the operation log provides a recovery mechanism, and it's designed specifically for the portability use case — but its log is held by a single directory service. Corundum defaults to `did:webvh`, which adds a verifiable, self-certifying history to `did:web`, and accepts `did:plc` and `did:key` as opt-in alternatives. This provides more flexibility but requires implementations to support multiple methods.

Perhaps the most significant architectural difference is the aggregation layer. AT Protocol defines two roles beyond the PDS. A **Relay** (early name: "Big Graph Service") subscribes to many PDSes and re-publishes their repository updates as one combined event stream (the "firehose"). An **AppView** consumes that stream, indexes it, and serves feeds, search, and thread views. Neither role is required to be singular — anyone can run a Relay or an AppView — but in practice Bluesky's own instances carry most traffic, and network-wide features (full-text search, trending topics) depend on running services of that scale. Corundum does not define a relay or AppView role. Federation is between operators directly; there is no global crawl. This makes Corundum more decentralized by design but means network-wide features must be implemented differently.

AT Protocol's moderation system is called "labelers." Labelers are accounts that apply labels to content. The labeler system is functional and in production use on Bluesky, Labels are cryptographically signed by a label key published in the labeler's DID document. The difference from Corundum is governance, not signatures: AT Protocol has no mandatory Authority Declaration and no required governance statement. Corundum's curation system requires curators to publish authority declarations with governance and appeal mechanisms (Chapter 30), and all curation entries are signed by a declared key.

Neither system is strictly superior. AT Protocol is deployed and in production with millions of users, which gives it a substantial advantage in real-world validation. Corundum is an undeployed specification that makes different tradeoffs around decentralization.

**vs. Scuttlebutt (SSB)**

Secure Scuttlebutt is a peer-to-peer gossip protocol, not a federated one, and takes a radically different approach: rather than relying on servers to host and serve content, it pushes all content to end-user devices. Every user's app replicates the signed, append-only feeds of the accounts they follow (and, typically, accounts a hop or two further out). Content propagates peer to peer, gossip-style.

This approach has real appeal: no central servers, no operator dependencies, genuine peer-to-peer distribution. But it runs into severe scalability problems in practice. SSB's initial sync has been documented to take up to an hour and consume several gigabytes of data, even for a modest social graph. The "push everything to the client" model works for small communities but breaks down as the network grows. Recommendation algorithms, search, and curation are essentially impossible at scale on a purely client-side model.

Corundum explicitly preserves the operator/server model because servers are where large-data operations — curation, recommendation, full-text search, real-time notifications — can work. The Scuttlebutt experience showed that full decentralization at the data layer is incompatible with acceptable user experience at scale. Corundum's answer is not to push data to clients but to make the server relationship portable: users depend on operators for service, but not for identity or data ownership.

**vs. Nostr**

Nostr is the simplest of the four systems: a keypair is your identity, relays store and serve your content, and clients connect to multiple relays. There's no federation protocol — you just post to relays and fetch from relays. The simplicity is genuinely appealing, and Nostr has attracted a real user base.

Nostr gets several things right. Keypair-based identity is the correct answer to the "who are you?" question. Separating content storage (relays) from identity (keypairs) is the right separation. The protocol's simplicity makes implementation easy.

What Nostr leaves underspecified is the hard part. There is no recovery mechanism if you lose your private key. There is no portable content archive structure — your content is wherever you happened to post it, and if a relay goes down, the content is gone unless another relay cached it. There is no formalized curation system: spam and abuse are handled ad hoc by relay operators. Relays do not talk to each other at all, so there is nothing to authenticate between them; instead every event is signed by its author's key, which makes events self-certifying and portable across relays — the same property Corundum's signed activities have. Nostr's simplicity is also its limitation — the things it doesn't specify are the things that become serious problems at scale.

Corundum adds a DID recovery layer on top of keypair identity, a formalized content-addressed archive structure, an authenticated operator-to-operator federation protocol (which Nostr deliberately does not have), and a formalized curation system. This makes Corundum more complex than Nostr, but the complexity serves specific purposes: recovery, portability, verifiability, and scalable moderation.

---

