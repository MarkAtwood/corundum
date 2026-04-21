## Part II: Context and Comparison

### Chapter 4: How Corundum Differs from Other Protocols

Before diving into the technical details of Corundum's design, it is worth situating it against the landscape of existing federated social protocols. The design decisions that follow only make sense when you understand what problems Corundum is trying to solve that other approaches do not, and vice versa. Every protocol in this space makes tradeoffs; none is simply better than the others across all dimensions.

**vs. ActivityPub / Mastodon**

ActivityPub is the W3C standard for federated social media, currently deployed at scale across the Mastodon network and dozens of compatible platforms. It is a mature, working system with millions of users. Understanding why Corundum does not build on ActivityPub requires understanding ActivityPub's specific limitations.

ActivityPub's identity model ties a user to a server. Your identity is `@alice@social.example`, which means Alice at the server `social.example`. The server hosts not just Alice's content but Alice's *identity*. Alice's followers know her as a specific URL on a specific server. When another instance wants to send Alice a message, it sends an HTTP POST to `social.example`. When a follower wants to fetch Alice's posts, they fetch them from `social.example`.

The consequence of server-tied identity is that Alice cannot move without losing something. Mastodon's "move account" feature lets Alice redirect followers to a new account on a different server, but it does not transfer her post history. Her old posts remain on the old server (until it shuts down) and do not appear on the new server. If `social.example` shuts down without notice — as many Mastodon instances have — Alice loses everything: her identity, her post history, her accumulated followers, all of it. Followers who didn't see the migration notice simply lose contact with Alice entirely.

Corundum's response is to separate identity from hosting entirely. Alice's identity is an IPNS name (a hash of her public key) and a DID, neither of which has any connection to any specific server. Her content is stored in IPFS, addressed by content hash. An operator hosts Alice, but Alice's identity and content exist independently of the operator. Moving to a new operator is a matter of updating the IPNS record to point to a new operator; the identity and content remain unchanged.

ActivityPub also has no formalized curation infrastructure. Each Mastodon instance runs its own moderation in isolation. There is no mechanism for one instance's moderation team to share their judgments with another instance in a structured, verifiable way. Blocklists exist (lists of servers to defederate from) but they are informal, non-verifiable, and operated by third parties with no accountability mechanism. Corundum's curation system provides a formalized, cryptographically verifiable mechanism for sharing moderation judgments across the network.

One area where Corundum explicitly borrows from the ActivityPub ecosystem is the data model: Corundum uses ActivityStreams 2.0 objects (Notes, Articles, Images, Events, etc.) as its activity format. This is deliberate — ActivityStreams is a well-designed, widely-deployed standard for representing social activities. Corundum uses the data model but not the federation protocol.

**vs. AT Protocol / Bluesky**

The AT Protocol is the closest architectural comparison to Corundum, and deserves the most detailed treatment. Both systems were designed to solve the same fundamental problem: portable identity and content in a federated social network. Both use content-addressed data and DIDs. But they make different architectural choices, with different tradeoffs.

AT Protocol's data model is based on a "repository" — a data structure (similar to a Git repo) that records every action a user takes as a signed commit. Every post, follow, like, and deletion is a record in this repository. The repository is served by a Personal Data Server (PDS), which is AT Protocol's equivalent of a Corundum operator. The key/signing layer uses `com.atproto.repo.commit` records with CIDs.

Corundum uses IPFS as the storage substrate. Posts are IPFS objects addressed by CID. The archive structure (epochs, ArchiveIndex) is an IPFS Merkle tree. This provides content-addressing and distributed availability natively — any IPFS node can pin and serve any piece of Corundum content. AT Protocol's repository format is its own, and content is served through PDS nodes, not through the broader IPFS network.

AT Protocol standardized on a single DID method: `did:plc`, a custom operation-log-based DID method. `did:plc` has real advantages — it doesn't require owning a domain, the operation log provides a recovery mechanism, and it's designed specifically for the portability use case. Corundum supports multiple DID methods (`did:web`, `did:plc`, `did:key`) rather than standardizing on one. This provides more flexibility but requires implementations to support multiple methods.

Perhaps the most significant architectural difference is the global indexer question. AT Protocol defines an "AppView" pattern: a global service (the "Big Graph Service") crawls all PDS nodes, indexes all content, and provides search and feed generation across the entire network. This enables powerful features (full-text search across the entire Bluesky network, network-wide trending topics) but requires a centralized service. Corundum explicitly does not define a global relay or indexer. Federation is between operators directly; there is no global crawl. This makes Corundum more decentralized by design but means network-wide features must be implemented differently.

AT Protocol's moderation system is called "labelers." Labelers are accounts that apply labels to content. The labeler system is functional and in production use on Bluesky, but it is less formalized than Corundum's curation system: there is no mandatory Authority Declaration, no required governance statement, no cryptographic verifiability of the labeler's identity beyond a DID. Corundum's curation system requires curators to publish authority declarations with governance and appeal mechanisms, and all curation entries are signed by a declared key.

Neither system is strictly superior. AT Protocol is deployed and in production with millions of users, which gives it a substantial advantage in real-world validation. Corundum's architecture is more formally specified and makes different tradeoffs around decentralization.

**vs. Scuttlebutt (SSB)**

Secure Scuttlebutt is a federated protocol that takes a radically different approach: rather than relying on servers to host and serve content, it pushes all content to end-user devices. Every user's app syncs a copy of the social graph they follow. Content propagates through the network gossip-style.

This approach has real appeal: no central servers, no operator dependencies, genuine peer-to-peer distribution. But it runs into severe scalability problems in practice. SSB's initial sync has been documented to take up to an hour and consume several gigabytes of data, even for a modest social graph. The "push everything to the client" model works for small communities but breaks down as the network grows. Recommendation algorithms, search, and curation are essentially impossible at scale on a purely client-side model.

Corundum explicitly preserves the operator/server model because servers are where large-data operations — curation, recommendation, full-text search, real-time notifications — can work. The Scuttlebutt experience showed that full decentralization at the data layer is incompatible with acceptable user experience at scale. Corundum's answer is not to push data to clients but to make the server relationship portable: users depend on operators for service, but not for identity or data ownership.

**vs. Nostr**

Nostr is the simplest of the four systems: a keypair is your identity, relays store and serve your content, and clients connect to multiple relays. There's no federation protocol — you just post to relays and fetch from relays. The simplicity is genuinely appealing, and Nostr has attracted a real user base.

Nostr gets several things right. Keypair-based identity is the correct answer to the "who are you?" question. Separating content storage (relays) from identity (keypairs) is the right separation. The protocol's simplicity makes implementation easy.

What Nostr leaves underspecified is the hard part. There is no recovery mechanism if you lose your private key. There is no portable content archive structure — your content is wherever you happened to post it, and if a relay goes down, the content is gone unless another relay cached it. There is no formalized curation system: spam and abuse are handled ad hoc by relay operators. There is no inter-relay authentication: relays have no way to verify the identity of other relays. Nostr's simplicity is also its limitation — the things it doesn't specify are the things that become serious problems at scale.

Corundum adds a DID recovery layer on top of keypair identity, a formalized content-addressed archive structure, a formalized inter-operator authentication mechanism, and a formalized curation system. This makes Corundum more complex than Nostr, but the complexity serves specific purposes: recovery, portability, verifiability, and scalable moderation.

---

