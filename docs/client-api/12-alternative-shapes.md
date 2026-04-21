# Alternative Client/Server API Shapes

The Corundum inter-operator protocol deliberately leaves the client/server API unspecified. The reference implementation's API (documented in the rest of this directory) is one reasonable choice shaped by familiarity with the Mastodon ecosystem. It is not the only choice, and for some use cases it is not the best choice.

This document surveys alternative shapes, their trade-offs, and the specific ways Corundum's architecture enables designs that are impossible or awkward on other federated social platforms.

---

## The Trust Axis

Before surveying shapes, it helps to name the most important design dimension: **where does signing happen, and who holds the keys?**

On traditional federated platforms, the server is the identity. `@alice@social.example` is a row in `social.example`'s database. The server signs things on Alice's behalf because the server *is* Alice, at the protocol level. There is no meaningful distinction between Alice and her operator.

Corundum breaks this conflation. Alice's identity is an Ed25519 keypair. The IPNS name — the hash of the public key — is her stable identifier. Her operator hosts her, but her operator is not her. This creates a design space that does not exist on ActivityPub: the operator can be a dumb relay with no signing authority whatsoever.

The trust axis runs from **operator-as-notary** (operator holds the key, signs on the user's behalf, can in principle impersonate the user) to **operator-as-relay** (client holds the key, pre-signs content before submission, operator cannot forge anything). Most interesting API designs can be located on this axis.

The reference API sits at the operator-as-notary end, which is familiar and works for web clients. The designs below explore other positions.

---

## Shape 1: End-to-End Signed

**Trust position**: operator-as-relay. The operator cannot impersonate the user.

**How it works**: The client holds the Ed25519 private key. Before submitting any content, the client:

1. Constructs the activity object locally
2. Serializes it to canonical JSON (NFKC-normalized, key-sorted, no insignificant whitespace)
3. Computes the CID: `SHA256(canonical_json)` encoded as a DAG-JSON CID
4. Creates the SigningRecord locally: signs `CID || timestamp || author_ipns` with the private key
5. Submits the activity, its CID, and the SigningRecord to the operator as a package

The operator receives pre-signed content. It can verify the signature (and should), pin the content in IPFS, update the ArchiveIndex, and relay to other operators — but it cannot produce a valid SigningRecord in the user's name because it does not have the private key.

**What the API looks like**: The submission endpoint accepts a bundle rather than raw post text:

```
POST /api/v1/activities/submit
Content-Type: application/json

{
  "activity_cid": "bafyreiemxf5...",
  "activity": { ...canonical activity object... },
  "signing_record": {
    "signed_at": "2024-03-10T12:34:56Z",
    "algorithm": "ed25519",
    "public_key_multibase": "z6Mk...",
    "signature_multibase": "zABC..."
  }
}
```

Read endpoints are unchanged — the operator still serves timelines, replies, and profiles. Only the write path fundamentally differs.

**Advantages**:
- The operator genuinely cannot forge content. "Trust me, I won't impersonate you" becomes "I couldn't even if I wanted to."
- Private key never leaves the client device. Operator compromise does not expose the signing key.
- Content authenticity is verifiable by any third party without trusting the operator.
- Aligns most directly with Corundum's stated goal of removing options that shouldn't exist.

**Disadvantages**:
- Web clients cannot easily hold private keys. Browsers have `SubtleCrypto` for key storage, but key export/recovery across devices is harder without a server-side component.
- Canonical JSON serialization must be implemented correctly in every client. The reference implementation provides test vectors; client implementations must be validated against them.
- Key rotation and recovery are the client's problem. Losing the private key without a backup means losing signing authority. DID-based recovery still works, but the operator cannot help.
- Session management becomes more complex: the access token authorizes submission to the operator, but the signing key authorizes content on the protocol level. These are different credentials with different lifetimes.

**Best suited for**: Native mobile apps, desktop apps, power users who want maximum key control, high-security deployments.

---

## Shape 2: GraphQL

**Trust position**: operator-as-notary (same as reference API; this is about the API shape, not the trust model — though GraphQL can be combined with E2E signing).

**How it works**: Replace the REST endpoint collection with a single GraphQL endpoint. The Corundum entity graph maps naturally to a GraphQL schema: entities have stable IDs (CIDs for content, IPNS names for accounts), relationships are typed and traversable, and the schema self-documents the data model.

A sketch of the core schema:

```graphql
type Account {
  id: ID!              # IPNS name
  username: String!
  displayName: String
  did: String!
  operatorEndpoint: String!
  rootManifestCid: String!
  archiveIndex: ArchiveIndex!
  statuses(first: Int, after: String): StatusConnection!
  followers(first: Int, after: String): AccountConnection!
  following(first: Int, after: String): AccountConnection!
}

type Status {
  id: ID!              # CID (base32lower)
  content: String!
  createdAt: DateTime!
  author: Account!
  signingRecord: SigningRecord!
  curationLabels: [CurationLabel!]!
  replies(first: Int, after: String): StatusConnection!
  inReplyTo: Status
  epoch: Int!
  sequenceNumber: Int!
}

type SigningRecord {
  cid: ID!
  activityCid: String!
  authorIpns: String!
  signedAt: DateTime!
  algorithm: String!
  publicKeyMultibase: String!
  signatureMultibase: String!
}

type Query {
  account(id: ID!): Account
  status(id: ID!): Status
  homeTimeline(first: Int, after: String): StatusConnection!
  publicTimeline(first: Int, after: String, local: Boolean): StatusConnection!
}

type Mutation {
  postStatus(input: PostStatusInput!): Status!
  deleteStatus(id: ID!): Boolean!
  followAccount(id: ID!): Relationship!
  blockAccount(id: ID!): Relationship!
}

type Subscription {
  homeTimeline: Status!
  notifications: Notification!
  publicTimeline(local: Boolean): Status!
}
```

**Advantages**:
- Clients query exactly the fields they need. A mobile client that never displays curation labels does not receive them.
- CID-addressed entities fit naturally as GraphQL node IDs. `node(id: "bafyrei...")` is unambiguous globally.
- Subscriptions replace polling for real-time feeds without requiring a separate streaming protocol.
- Schema introspection documents the API for free. Client developers can explore the schema with standard tooling.
- Corundum-specific fields (`signingRecord`, `curationLabels`, `archiveIndex`) are first-class schema members rather than extension objects bolted onto a Mastodon-shaped response.

**Disadvantages**:
- GraphQL responses are typically POST requests, which breaks HTTP caching. Persisted queries (sending a query hash instead of the full query text) recover some cacheability, but it requires additional infrastructure.
- Complexity cost is real. The reference REST API is easier to implement for a first operator.
- Mastodon client compatibility is zero. GraphQL and REST are different enough that no shim covers the gap.

**Best suited for**: Operators building first-party web or mobile clients that want tight control over data fetching. Good fit for operators with complex feed ranking or filtering requirements, where the client needs to specify exactly what it wants.

---

## Shape 3: Nostr-Style Relay

**Trust position**: closer to operator-as-relay; naturally combines with E2E signing.

**How it works**: Replace REST with a WebSocket-based publish/subscribe protocol. Clients connect to an operator's WebSocket endpoint and exchange structured messages. The basic interaction is:

- **Subscribe**: client sends a filter specifying what events it wants
- **Event**: server pushes matching activities as they arrive
- **Publish**: client sends a signed event; server relays it and stores it

A Corundum-flavored version of this would use CIDs and IPNS names in place of Nostr's raw pubkeys, and would extend filters to include Corundum-native dimensions:

```json
// Client subscribes
["REQ", "sub-1",
  { "authors": ["k51qzi5uqu5dlvj2..."],
    "kinds": ["Note", "Reply"],
    "since": 1709000000,
    "limit": 50 }
]

// Server pushes events
["EVENT", "sub-1",
  { "cid": "bafyreiemxf5...",
    "kind": "Note",
    "author_ipns": "k51qzi5uqu5dlvj2...",
    "created_at": 1709123456,
    "content": "Hello, federated world.",
    "signing_record_cid": "bafyreiabcdef..." }
]

// Client publishes (pre-signed; E2E model)
["PUBLISH",
  { "cid": "bafyreiemxf5...",
    "activity": { ... },
    "signing_record": { ... } }
]
```

**Advantages**:
- Real-time by default. No polling, no webhooks, no SSE as an afterthought.
- Conceptually simpler than REST: one connection, structured message types, filter-based subscriptions.
- Combines naturally with E2E signing: the publish message carries a pre-signed package, operators relay without generating signatures.
- Easy for clients to connect to multiple operators simultaneously (useful for building aggregated feeds across federation).

**Disadvantages**:
- WebSocket connections are stateful and more complex to scale than stateless HTTP.
- Query expressiveness is limited by filter design. Complex searches (full-text, ranked feeds) are awkward over a pub/sub protocol.
- Profile management, key rotation, migration — all the stateful write operations — need either a complementary REST API or protocol extensions.
- No standard Mastodon compatibility surface.

**Best suited for**: Real-time-first clients, bot operators that subscribe to specific feeds and react to events, read-heavy use cases where the client wants push rather than pull.

---

## Shape 4: Local-First / IPFS-Direct

**Trust position**: operator-as-notifier only. Content does not flow through the operator on the read path.

**How it works**: The client runs a local IPFS node (or has access to one). The operator's role on the read path shrinks to notification: "new content appeared at CID `bafyrei...` on IPNS name `k51qzi5...`". The client fetches the content directly from IPFS, verifying the CID locally. The operator is never in the content delivery path.

The API becomes a thin notification and write relay:

```
# Operator notifies client of new content
WebSocket push:
{ "type": "new_content", "author_ipns": "k51qzi5...", "cid": "bafyrei...", "sequence": 892 }

# Client fetches directly from IPFS (not the operator)
ipfs get bafyreiemxf5...

# Client verifies CID matches fetched content (independent of operator)

# Write path still goes through operator for federation
POST /submit { activity_cid, activity, signing_record }
```

The operator maintains IPNS resolution, stores follow lists, and handles the inter-operator federation protocol. It does not serve content.

**Advantages**:
- The operator cannot censor or modify content on the read path. It can refuse to notify (degraded experience) but cannot alter what the client sees.
- Content is available from any IPFS node that has it pinned, not just the operator. Operator downtime does not block reading.
- Most faithful expression of IPFS's design: content lives on the network, addressed by hash, retrieved from the nearest pin.
- Verifiability is automatic: IPFS refuses to return content that doesn't match the CID.

**Disadvantages**:
- Requires IPFS in the client environment. This is realistic for desktop apps and server-side clients; it is impractical for web browsers today.
- DHT lookups add latency compared to a direct HTTP response from a nearby server.
- The notification layer is still needed, which requires a live operator connection for real-time feeds.
- Full-text search, ranked timelines, and other server-side query operations require the operator's database, not IPFS.

**Best suited for**: Desktop native clients, server-side bots, archive and research tools, situations where censorship resistance on the read path matters.

---

## Shape 5: CQRS Split

**Trust position**: operator-as-notary; this is an architecture pattern, not a trust model change.

**How it works**: Separate the write API from the read API entirely, and design each for its actual access pattern.

**Write API** (thin, live): Accepts content submissions, returns CIDs. Does one thing:

```
POST /write/activity    → { cid: "bafyrei..." }
POST /write/follow      → { ok: true }
POST /write/block       → { ok: true }
```

**Read API** (fat, cacheable): Serves pre-computed feed state. Because CIDs are immutable by definition, any response keyed by CID can be cached indefinitely at the CDN layer with no invalidation logic:

```
GET /read/status/{cid}           # Immutable. Cache forever.
GET /read/account/{ipns}/feed    # Mutable. Cache with short TTL or ETag.
GET /read/account/{ipns}/archive/{epoch_cid}  # Immutable. Cache forever.
```

The read layer serves pre-serialized JSON blobs keyed by CID. An operator that stores content as CID → canonical JSON in a blob store can put a CDN in front of `/read/status/{cid}` with infinite cache lifetime. Timeline endpoints (which change as new posts arrive) use short TTLs or conditional requests.

**Advantages**:
- CID-addressed read endpoints are perfectly cacheable by construction. `GET /read/status/bafyreiemxf5...` will always return the same bytes; any CDN node in the world can serve it.
- Write path is simple and fast because it does not need to generate response objects. It writes to IPFS, updates indexes, returns a CID.
- Read and write paths can scale independently. A popular account generates heavy read traffic against an immutable CDN; write traffic is low regardless of account popularity.
- The separation makes the data flow explicit: all mutations go through the write API, all queries go through the read API.

**Disadvantages**:
- More moving parts than a unified REST API.
- Client code must handle two distinct API surfaces.
- Eventual consistency: a freshly written status may not appear in the read feed for a short window while indexing propagates.

**Best suited for**: Operators expecting high read volume, content-creator-focused platforms, operators that want to put static content on a CDN.

---

## Shape 6: AT Protocol XRPC

**Trust position**: operator-as-notary; this is about cross-ecosystem compatibility.

**How it works**: AT Protocol (Bluesky) uses XRPC — HTTP with a Lexicon type system for schema definition. Because Corundum and AT Protocol share meaningful architectural DNA (both use DIDs, both use content-addressed data, both have operator-style server nodes), a Corundum operator could expose an XRPC interface and accept clients built for AT Protocol.

The mapping is not clean but it is tractable:
- AT Protocol `did:plc` identifiers → Corundum IPNS names (both are content-addressed user identifiers)
- AT Protocol repository CIDs → Corundum activity CIDs (different encoding; same concept)
- AT Protocol Lexicons → Corundum activity types

A Corundum-to-XRPC bridge would let Bluesky clients (which already have a substantial developer ecosystem) connect to Corundum operators with no code changes.

**Advantages**:
- Instant access to the AT Protocol client ecosystem.
- Lowest conceptual impedance of any cross-protocol bridge (ActivityPub bridges require more translation because the identity and storage models differ more).
- Forces documentation of which Corundum concepts have no AT Protocol equivalent, which clarifies where the two protocols actually differ.

**Disadvantages**:
- AT Protocol XRPC ties the client API surface to AT Protocol's Lexicon evolution. Corundum-native features (signing transparency, curation authority declarations, GDPR tombstones) would appear as XRPC extensions that Bluesky clients ignore.
- Full fidelity is not achievable. A Bluesky client over an XRPC bridge cannot access Corundum's identity migration flow or curation layer.
- Maintenance burden: keeping a Lexicon shim current with AT Protocol's evolution is ongoing work.

**Best suited for**: Operators targeting the Bluesky user population, bridge implementations, federation experiments.

---

## Combining Shapes

These shapes are not mutually exclusive. Some combinations are particularly natural:

**E2E Signing + GraphQL**: The GraphQL mutation for posting a status accepts a pre-signed bundle. The read schema is unchanged. Clients that want key ownership get it; clients that don't can still delegate to the operator.

**E2E Signing + Nostr-style relay**: This is essentially what Nostr itself is, but with Corundum's richer identity model. Each signed event published over the WebSocket carries a complete SigningRecord. The operator relays but never forges.

**CQRS + Local-first**: The write API routes to the operator; the read API routes to IPFS directly. The operator's read layer becomes a notification system that tells clients which CIDs to fetch.

**GraphQL + CQRS**: The mutation layer is a thin write API; the query layer is served from a pre-computed read model that GraphQL translates into a typed interface.

---

## Decision Guide

| If you want... | Consider... |
|----------------|-------------|
| Familiarity for client developers | Reference REST API (`00-design.md` and siblings) |
| Maximum operator trust reduction | E2E Signing |
| Tight data fetching control, self-documenting schema | GraphQL |
| Real-time push, simplicity, bot-friendly | Nostr-style relay |
| CDN cacheability, high read volume | CQRS split |
| Censorship resistance on the read path | Local-first / IPFS-direct |
| Bluesky client ecosystem access | AT Protocol XRPC |

An operator is not required to choose one. A production deployment might offer the reference REST API for general clients, a Nostr-style WebSocket relay for real-time consumers, and a CQRS read layer behind a CDN for scale — all backed by the same Corundum inter-operator layer. The inter-operator protocol is fixed; everything above it is operator policy.
