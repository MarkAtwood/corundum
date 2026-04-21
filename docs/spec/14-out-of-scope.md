## Part XIV: What Corundum Doesn't Define

### Chapter 40: Intentional Silences

The specification is deliberately silent on several categories of concern. These silences are design decisions, not omissions.

#### Out of Scope by Design

**Client/server protocols.** Corundum is an inter-operator backbone, not a client-facing protocol. Each operator uses whatever API it wants with its own users. Specifying client/server APIs would constrain operator innovation and create a monoculture of client software. The diversity of client experiences — different apps, different interfaces, different feature sets — is a feature, not a bug. Corundum only specifies what operators say to each other.

**Business models.** Operators and curators can charge, run ads, operate as nonprofits, or do whatever makes sense for their operation. The protocol provides no mechanisms for monetization because monetization is a business decision, not an interoperability concern. An operator that requires payment for federation with it is free to implement that through its own authentication layer; Corundum provides the authenticated channel, not the business logic.

**Direct messages and private groups.** The protocol covers "the public conversation" only. Private communication requires end-to-end encryption and group key management, which are substantially more complex than public content federation. Including DMs in scope would have doubled the protocol's complexity for a use case that is orthogonal to the core federation problem. The explicit scope limitation is "the plumbing for public social media."

**Curator governance.** How curators make their decisions, how they're funded, how they're held accountable beyond publishing a governance document — these are not protocol concerns. The protocol requires that a governance model be declared and published; it does not specify what that model must be. Different curators will have different governance structures appropriate to their role: NCMEC is a government-designated nonprofit with congressional oversight; a community-run spam detection service might be governed by its members; a commercial classifier might be governed by its investors. Specifying curator governance in the protocol would be regulatory overreach by a technical specification.

**Content recommendation algorithms.** Operators rank and recommend content however they choose. The recommendation algorithm is the single most differentiating feature of a social media platform. It is also the most contested: questions of algorithmic amplification, filter bubbles, and radicalization pipelines are live social and political debates. Specifying a recommendation algorithm in the protocol would make Corundum take a position on these debates. The protocol provides the data; the algorithm is the operator's.

#### Future Work

**End-to-end encryption.** Private messaging with E2E encryption is listed as a future consideration. The protocol infrastructure — IPFS content addressing, DID-based key management — would support it, but the specific key exchange protocols, group key management, and forward secrecy mechanisms are not yet specified.

**Compact membership proofs.** The current social graph structure uses Bloom filters for efficient block list membership checks. A more rigorous approach would use cryptographic accumulators or zk-SNARKs for membership proofs that are both compact and zero-knowledge. The ArchiveIndex was designed to be compatible with adding a Merkle-based membership proof layer without changing the fundamental structure.

**Private groups.** Group content that is visible only to members, with operator-enforced access control and potentially E2E encryption for the content. Related to but distinct from private messaging.

**Cross-protocol bridges.** Formal bridge specifications for ActivityPub (Mastodon) and AT Protocol (Bluesky) interoperability are future work. The data model compatibility (ActivityStreams) makes ActivityPub bridges straightforward at the content level; the identity model differences require careful handling.

---

