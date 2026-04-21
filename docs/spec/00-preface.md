# How Corundum Works

### A Complete Guide to the Corundum Federated Social Media Protocol

---

## Preface

Corundum is a protocol specification for federated social media. It was originally drafted as a proposal for the Twitter Bluesky project; when Bluesky chose a different architecture (what became the AT Protocol), the specification continued independently. The name comes from the mineral basis of sapphire.

Two epigraphs capture the design philosophy:

> "A complex system designed from scratch never works and cannot be made to work." — Gall's 2nd Law

> "It Has To Work." — IETF RFC 1925, Truth #1

The first epigraph is not decorative. Gall's Law describes a specific failure mode that has claimed many ambitious protocol projects: the designer, freed from the constraints of an existing system, specifies every detail they wish the world had, produces a document of impressive completeness and internal consistency, and then discovers that nobody implements it because the implementation cost is too high, or implementations diverge on the many ambiguous details, or the real-world use cases don't quite fit the idealized model. Corundum's response to Gall's Law is to ask, at every design decision: what is the minimum standard that enables federation? If a detail can vary between operators without breaking interoperability, it should not be specified. The protocol should be a narrow waist, not a corset.

This philosophy shows up in what Corundum leaves undefined. It does not specify client-server APIs. It does not define business models. It does not define how operators present content to users, how recommendation algorithms work, what direct messaging looks like, or how curators make their internal decisions. These are all policy decisions, and policy decisions belong to the humans who run systems, not to protocol specifications. The protocol specifies only the inter-operator backbone: the data structures, wire formats, authentication mechanisms, and coordination protocols that allow independently operated servers to exchange content reliably and verifiably.

The phrase "inter-operator backbone" is worth unpacking. When a user on one Mastodon instance sends a reply to a user on another instance, the two servers exchange ActivityPub messages. That exchange is the backbone. Corundum's backbone covers the same territory — reply routing, content exchange, social graph synchronization, operator authentication — but also extends into areas ActivityPub doesn't address: portable identity, content-addressed archives, and the curation layer. The backbone is what lets operators federate. Everything client-facing — the app, the algorithm, the subscription tier — sits on top of the backbone and is the operator's own business.

This book explains the complete protocol as specified across its roughly two dozen interlocking specification documents, in a form suitable for understanding or building an implementation. It attempts to explain not just what the protocol requires but why it makes each choice, because the choices only make sense in the context of the problems they solve.

---

