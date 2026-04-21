## Part XV: Implementation Guidance

### Chapter 41: What a Minimal Operator Must Implement

To be a conforming Corundum operator, you must at minimum:

1. **Publish an Operator Manifest** at `/.well-known/corundum-operator` over HTTPS, with your keys, capabilities, and self-signature. Without this, other operators cannot verify your identity or your capabilities. When your reply submission arrives at another operator, the first thing they do is fetch your manifest and verify your signature. No manifest means the request is rejected — there is no fallback identity mechanism. The manifest is also how you declare what protocol features you support, so operators know what they can expect from you. An operator with no manifest is invisible to the protocol; nothing you send will be accepted.

2. **Maintain an IPFS node** (or use a gateway with pinning) for content-addressed storage. Without content-addressed storage, you cannot issue CIDs for user content, and CIDs are the currency of the entire system. Every post, every social graph update, every media item is identified by its CID. If you do not have IPFS storage, you have no way to assign valid CIDs (fabricating them would break all content verification), no way to pin content for durable availability, and no way to serve content to operators who fetch by CID. A gateway-with-pinning approach — using a service like Pinata or a public IPFS gateway for fetch, and a pinning service API for persistence — is acceptable for a small operator. It gives up some performance and adds a dependency on the pinning service, but it is a conforming implementation. A large operator needs a local IPFS cluster to avoid the latency and throughput limits of an external gateway.

3. **Manage user identities** — generate or accept IPNS keypairs, publish RootManifests, maintain timelines as content-addressed archives using the epoch/ArchiveIndex structure. Without this, you cannot create users in any meaningful sense. The IPNS keypair is the user's identity; without generating and securely managing that keypair, there is no user — only a row in a database with no protocol-level presence. The ArchiveIndex structure is required, not optional: it is the canonical way other operators navigate a user's content history, and an operator that stores content as a flat list without an ArchiveIndex is not a conforming implementation. Other operators that try to fetch that user's content will find a structure they cannot parse.

4. **Support the Reply Protocol** — accept incoming reply submissions via authenticated HTTP POST, validate signatures using the inline signing record, check policies, return acceptance or rejection. This is the core federation mechanism. Without it, your users cannot receive replies from users on other operators. Your users also cannot send replies to cross-operator posts — without the submission path, those replies are silently dropped. Federation without reply routing is read-only federation: your users can follow cross-operator accounts but cannot talk to them. That is a severe constraint that eliminates most of the value of federation for conversational use cases.

5. **Sign inter-operator requests** using HTTP Message Signatures (RFC 9421) with at least Ed25519, including the required components: `@method`, `@target-uri`, `@authority`, `content-digest`, and `corundum-timestamp`. Without signing, other operators cannot authenticate your requests. There is no other mechanism for an operator to know that a request claiming to come from `birdsite.example` actually came from Birdsite and not from an attacker spoofing the header. Unsigned requests have no operator identity attached, which means the receiving operator cannot check federation policy, cannot apply rate limits per-operator, and cannot distinguish your legitimate traffic from an attacker impersonating you. Most conforming operators will return `401 Unauthorized` on unsigned requests, full stop.

6. **Implement Canonical JSON serialization** for all signing and hashing operations, including NFKC normalization. Without canonical serialization, your signatures will fail to verify on other implementations. This is one of the most common sources of interoperability failures in practice. The failure mode is subtle: you generate a keypair, sign an object, send it to another operator, and their signature verification fails — not because you used the wrong key or the wrong algorithm, but because you serialized the JSON object with different key ordering or different Unicode normalization than the verifier expects. The content of the object was identical; the bytes were not. Canonical serialization is what makes "sign here, verify anywhere" work across independent implementations.

7. **Support Ed25519 signatures and SHA-256 hashes** for signing and content addressing. These are the required algorithms. Every other algorithm in the spec is optional. An operator that supports only the required algorithms can still interoperate fully with all other conforming operators. The reason this matters: if your implementation supports only an optional algorithm (say, only P-256 and not Ed25519), other operators that implement only the required algorithms cannot verify your signatures and cannot produce signatures you can verify. The required algorithms are the common denominator that guarantees baseline interoperability. Optional algorithms are for operators that want additional properties (post-quantum resistance, hardware security module compatibility) but must still support the baseline.

8. **Implement the standard error envelope** for all API responses. Without a standard error format, other operators and their clients cannot programmatically interpret your error responses. A non-standard error body means that when your API returns `400 Bad Request`, the caller receives an opaque blob instead of a machine-readable error code and message. Every operator that integrates with you has to write custom error-parsing logic for your API rather than using shared library code. The error envelope is a small implementation investment; skipping it creates friction for every integration.

9. **Implement cursor-based pagination** for all collection endpoints. Without it, your collection endpoints have no standard way to handle large result sets. The failure modes: clients either receive truncated results without knowing they are truncated (because there is no `nextCursor` to signal more results exist), or they must invent custom pagination logic specific to your API (breaking client portability). Cursor-based pagination is also correct for content that can change between pages — offset-based pagination can skip or repeat items when the underlying collection is modified during traversal; cursors do not have this problem.

### Chapter 42: What You Should Also Implement

Beyond the minimum:

- **DID integration** — `did:web` at minimum. `did:plc` if you want AT Protocol compatibility. Without DID, users have no identity recovery mechanism on key loss. A user identified only by their raw IPNS name (the hash of their public key) who loses their private key has permanently lost their identity — there is no recovery path, no way to prove continuity with the old account, and no way to notify followers that the new key is the same person. `did:web` users can recover by updating their web-hosted DID document to point to a new key; `did:plc` users have a key rotation mechanism built into the DID method. Skipping DID is a defensible choice for an operator serving technical users who understand and accept the tradeoff. It is not acceptable for operators serving general users who expect account recovery.

- **Handle resolution** — at least the DNS method. Without handle resolution, your users have no human-readable identity. They are identified by IPNS names, which are 52-character base58 strings. Other operators displaying your users in their timelines cannot show `@alice@birdsite.example`; they show the IPNS hash. Cross-operator mentions, replies, and search by username all require the handle system. This is a severe user experience degradation for anyone interacting across operator boundaries, which is to say: for any user participating in the federated network rather than just within your own silo.

- **Curation feed subscription** — at least one CSAM hash database. This item is listed under "should also implement" because it is not technically required for protocol conformance. It is, however, legally required in the United States under 18 U.S.C. § 2258A (the PROTECT Our Children Act), which mandates that electronic service providers report known CSAM to NCMEC. Equivalent obligations exist in the EU, UK, Australia, and most other jurisdictions where you might operate commercially. "Should also implement before you open to the public" understates the situation: operating a public Corundum operator without CSAM detection in place exposes you to criminal liability in most jurisdictions. The failure mode is not a bad user experience. It is federal prosecution.

- **Block list enforcement with Bloom filter support** for efficient negative checks. Without Bloom filters, every incoming reply submission and every new post requires a database query to check all subscribed block lists. For a low-volume operator receiving a few hundred items per day, a database query per item is fine. For an operator receiving thousands of items per second, database queries at that rate become a performance bottleneck before almost anything else does. The Bloom filter shifts the majority of checks to a local memory operation — a microsecond per check for a filter sized to 1% FPR — with only the roughly 1% of Bloom positives needing a database lookup to confirm. At scale, the difference between "a microsecond in RAM" and "a round-trip to the database" is the difference between handling the load and not.

- **Event streaming** via WebSocket or SSE for real-time updates. Without event streaming, clients must poll for new replies, follows, and timeline updates. Polling at any reasonable frequency — say, every 30 seconds — introduces up to 30 seconds of notification latency for real-time conversational use. Social media at its best feels like a conversation; 30-second latency makes it feel like email. Polling at higher frequency reduces latency but increases server load proportionally. Event streaming is the correct solution: the client holds one long-lived connection and receives push notifications the moment an event arrives, with essentially zero latency overhead and much lower server load than polling.

- **Content expiration handling** — respect retention hints and `expires` fields on content. Without this, time-limited content (stories, time-limited posts) continues displaying after the expiry time the user set. A user who posts a story that expires in 24 hours and then watches it still appear 72 hours later has had an explicit user preference violated. This erodes trust in the feature. Content expiration also has legal dimensions in some jurisdictions (right to erasure, data minimization obligations); respecting expiration fields is part of a credible compliance posture.

- **Migration support** — accept inbound migrations and support outbound migrations. Without inbound migration support, users moving to your operator from another operator cannot bring their content history. They arrive with an empty timeline, no followers ported, no archive of their posts. This is a significant friction for adoption, because moving to a new operator feels like starting over. Without outbound migration support, users are effectively locked in to your operator by the cost of losing their data. The ability to leave with your data intact is a precondition for users trusting your operator with their data in the first place. An operator that makes data export easy and migration cooperation smooth is an operator users can trust. An operator that silently loses data on export or refuses to cooperate with migration notifications is an operator users are right to distrust.

- **Post-quantum algorithm support** — accept dual signatures (Ed25519 + Dilithium) even if you do not require Dilithium yet. Today, Dilithium is optional and Ed25519 is sufficient. When the ecosystem begins transitioning to post-quantum signing — driven by advances in quantum computing or regulatory mandates — operators that have not added Dilithium support will start rejecting valid signatures from operators that have switched. The early operators to transition will be the ones with the strongest security posture: governments, financial institutions, large platform operators. If you cannot verify their signatures, you cannot receive their content or accept their users' cross-operator activity. Adding Dilithium support while it is optional is a small implementation task. Adding it under pressure after it is required — when you are actively breaking federation with peers that have already switched — is an emergency. The window to do this incrementally is now.

### Chapter 43: Common Implementation Mistakes

**Incorrect canonical serialization.** The most common source of signature verification failures across implementations. Three specific pitfalls:

1. Forgetting NFKC normalization. Non-ASCII characters in content (emojis, non-Latin scripts) will produce different bytes if NFKC normalization is not applied consistently.
2. Including the `signature` field in the bytes to be signed. Always strip signature fields before serializing for signing.
3. Floating point representation. Use ECMAScript's `Number.toString()` rules exactly. `1.0` must serialize as `1`; `1e10` must serialize as `10000000000`.

**Treating IPNS name as primary identifier.** Operators must store the DID as the primary identifier for users, not the IPNS name. If you store only the IPNS name, you will be unable to re-resolve the user's current key when they migrate. DID → IPNS mapping should be a cached value, not a stored primary key.

**Not verifying bidirectional handle claims.** It is not sufficient to verify that the DID claims a handle. You must also verify that the handle points back to the DID. Omitting the reverse check enables handle impersonation.

**Accepting reply submissions without verifying the inline signing record.** The submitting operator's HTTP signature proves the request came from a known operator; it does not prove the reply came from the claimed user. You must verify the inline signing record independently.

**Missing the detached signing record.** Activities are stored unsigned. If you sign the activity object itself (adding a signature field), you will produce a different CID than expected, and your implementation will be incompatible with others.

**Using the wrong CID as the `id` field.** The activity's `id` is the CID of the *id-less canonical form* — the activity with no `id` field, serialized to Canonical JSON, then CID-calculated. A common mistake is computing the CID of the fully-formed object (with `id` already present), or computing the CID before performing NFKC normalization and timestamp canonicalization. The correct procedure: strip the `id` field, canonicalize the remaining fields, compute the CID of those bytes, then add the `id` field with that CID. Any other ordering produces a different CID and breaks signature verification, because the signing record's `content` field is this same CID.

**Off-by-one in ArchiveIndex epoch boundaries.** Epoch 0 covers entries 0–255, epoch 1 covers 256–511, and so on. A common mistake is treating the epoch index and the sequence number modulo as if they might overlap. `epoch_index = floor(seq / 256)` and `offset_in_epoch = seq % 256` are always correct. An implementation that uses `floor(seq / 256) - 1` for the epoch index or `(seq % 256) + 1` for the offset will produce O(1) lookups that point to the wrong entry with no visible error — the wrong entry is returned and its sequence number won't match the requested one.

**Not distributing tombstone notifications.** When a user deletes a post, the operator must notify downstream operators that previously received that content. Operators that only unpin locally and publish a tombstone to their own archive — without notifying subscribers — will have content that persists on other nodes despite deletion. The tombstone notification path must be implemented and tested, not just the local deletion path.

**Building the DID→IPNS cache without expiry.** The cache must have a TTL. If a user migrates to a new IPNS key (via hostile migration, or after key rotation), and your cache holds the old IPNS name indefinitely, you will continue routing to the wrong identity. The recommended TTL is 24 hours. On expiry, re-resolve via the DID document. On receiving a MigrationNotification: update immediately, don't wait for TTL expiry.

**Treating curation checks as one-time-on-arrival.** Curators publish new entries continuously. Content that was acceptable when it arrived may match a new curation entry published tomorrow. Retroactive matching must be implemented: when your curation feed sync pulls new entries, check each new hash against your stored content index. An operator that checks content only on arrival will miss curation entries published after the content was stored.

**Not implementing exponential backoff for reply submission retries.** When Alice's operator is temporarily unreachable, Bob's operator must retry with exponential backoff — not immediate retries. Implementations that retry in a tight loop (or with a fixed 1-second delay) will hammer unreachable operators and may be rate-limited or blocked by other operators' anti-abuse systems. Correct behavior: exponential backoff starting at 1 second, doubling each attempt, up to a configurable maximum (typically 1 hour), with a 24-hour total retry window.

**Using offset pagination on a live collection endpoint.** Any endpoint that returns a timeline or reply tree grows continuously. Offset-based pagination (`?page=3&size=20`) will produce duplicate and missing items when the collection changes between pages. Every collection endpoint must use cursor-based pagination.

### Chapter 44: Verification Checklist

When receiving a signed object, verify in this order:

1. Check that the `signatureAlgorithm` is acceptable per your policy and is not on the PROHIBITED list.
2. If the primary algorithm is unacceptable, check `resignatures` for an acceptable alternative.
3. Check that all algorithms you REQUIRE (based on the sender's declared active keys in their manifest) have valid signatures present.
4. Extract and decode the signature.
5. Remove `signature`, `signatureAlgorithm`, and `resignatures` from the object.
6. Canonicalize all timestamps.
7. Apply NFKC normalization to all strings.
8. Serialize to Canonical JSON.
9. Verify the signature against the claimed public key.
10. Verify the public key belongs to the claimed identity (via IPNS resolution, DID document, or operator manifest).

When receiving a reply submission, additionally:

1. Verify the submitting operator's HTTP Message Signature, including `content-digest` and `corundum-timestamp`.
2. Check that the timestamp is within the acceptable clock skew window (default: 300 seconds).
3. Verify the inline signing record's signature against the reply content.
4. Compute the content hash of the reply content and verify it matches the claimed `contentHash`.
5. Check the target user's reply policy against the submitting operator's trust level.
6. Check the reply author's IPNS identity against the target user's block list (Bloom filter fast path, then full check if needed).
7. Run the content against subscribed curation feeds.
8. Apply rate limits based on the submitting operator's trust level.

### Chapter 45: Canonical Serialization Test Vectors

Implementations should validate against these test vectors before considering serialization conformant.

**Key sort**: `{"z":3,"a":1,"m":2}` → `{"a":1,"m":2,"z":3}`

**Nested key sort**: `{"b":{"y":2,"a":1},"a":3}` → `{"a":3,"b":{"a":1,"y":2}}`

**No whitespace**: `{ "a" : 1 }` → `{"a":1}`

**Timestamp normalization**:
- `"2025-02-01T14:30:00.000Z"` → `"2025-02-01T14:30:00Z"` (trailing zeros stripped)
- `"2025-02-01T14:30:00.100Z"` → `"2025-02-01T14:30:00.1Z"` (trailing zeros stripped, significant digit kept)
- `"2025-02-01t14:30:00z"` → `"2025-02-01T14:30:00Z"` (uppercase T and Z)

**Number representation**:
- `1.0` → `1`
- `1.5` → `1.5`
- `1e10` → `10000000000`
- `-0.0` → `0`

**Null field omission**: `{"a":1,"b":null,"c":3}` where `b` is an optional field → `{"a":1,"c":3}`

**Unicode normalization**: Any string containing `\u0065\u0301` (e + combining acute) must be normalized to `\u00e9` (precomposed é) before serialization.

The spec provides a complete example RootManifest, its Canonical JSON form, and a test Ed25519 keypair for end-to-end implementation verification.

### Chapter 46: IPFS in Practice

The protocol specification describes what operators must store in IPFS and why. This chapter explains how: the software, the configuration patterns, and the operational tradeoffs.

**The reference implementation: Kubo.** The reference IPFS implementation is Kubo (formerly go-ipfs), maintained by Protocol Labs. Kubo is the de facto standard; other IPFS implementations (Iroh, Helia for JavaScript) exist but have different APIs and maturity levels. Corundum operators should use Kubo. The relevant interface is Kubo's HTTP API, which runs on port 5001 by default: a REST-ish API for adding, pinning, and fetching IPFS objects. The Corundum protocol implementation communicates with Kubo via this API using HTTP requests; no IPFS client library is required. A thin HTTP client (`reqwest` in Rust) is sufficient.

The Kubo HTTP API's key operations for a Corundum operator:

```
POST /api/v0/add           # add an object, returns CID
GET  /api/v0/cat?arg={cid} # fetch an object by CID
POST /api/v0/pin/add?arg={cid}   # pin an object (prevent GC)
POST /api/v0/pin/rm?arg={cid}    # unpin an object
GET  /api/v0/pin/ls              # list pinned objects
POST /api/v0/name/publish?arg={cid}&key={keyname}  # publish IPNS name
GET  /api/v0/name/resolve?arg={ipns}               # resolve IPNS name
```

**Pinning strategy.** IPFS garbage collection removes objects that are not pinned. An operator must pin everything it wants to retain: user manifests, all timeline entries, all activity objects, all signing records, all media manifests and chunks. "Pin" means "do not garbage collect this object." The flip side: when a user deletes a post (publishes a tombstone), the operator unpins the activity object, and GC will eventually reclaim the space.

Two pinning approaches:

*Local-only pinning* stores everything on the operator's own IPFS node. Simple to operate, all data under the operator's control, no external service dependencies. Suitable for small-to-medium operators. The risk is single-node data loss if the IPFS node's disk fails and there are no replicas.

*Hybrid pinning* combines a local node (for fast access, serving content to other IPFS nodes) with a remote pinning service (Pinata, Web3.Storage, Filebase, or similar) for durability. The operator pins content to both the local node and the pinning service. If the local node fails, content is still available through the pinning service's IPFS nodes. For production operators serving many users, hybrid pinning is recommended: it provides redundancy without requiring the operator to run a distributed IPFS cluster.

The Kubo HTTP API supports remote pinning services via the `pinner` API: `POST /api/v0/pin/remote/add?service={service}&cid={cid}&name={name}`.

**Garbage collection.** Never run IPFS GC automatically on a production Corundum node. The default Kubo configuration has GC disabled by default, but this should be verified. Automatic GC can delete objects that are needed but not yet pinned — for example, objects that were just added but whose pin call was interrupted before completing. On a Corundum operator, all content should either be pinned or available for deletion; there should be no ambiguous intermediate state. Manual GC can be run during scheduled maintenance windows after verifying that all required objects are pinned. Unpinning and GC should be strictly ordered: unpin first, then verify the unpin took effect, then run GC.

**IPNS publishing.** Each user's identity requires a Kubo keypair for IPNS. Kubo stores keys by name; the operator assigns each user a key name (typically the user's DID or a derived identifier). IPNS publishing calls: `POST /api/v0/name/publish?arg={rootManifestCID}&key={userKeyName}`. Kubo signs the IPNS record and publishes it to the DHT.

IPNS publication is not instantaneous: the DHT announcement propagates over minutes. For time-sensitive operations (immediate visibility of a new post), other operators that have an HTTP connection to the operator can fetch the current manifest directly via the operator's HTTP API rather than via DHT resolution. DHT is the fallback for operators that don't have a direct connection.

Kubo supports keeping keys in memory (ephemeral, lost on restart), in the keystore (persisted on disk), or in an external key management system via the keystore API. For production operators, use the Kubo keystore with encrypted disk storage, not in-memory ephemeral keys. Consider using HSM-backed key storage for large deployments where key compromise would affect many users.

**Content routing and connectivity.** Kubo connects to other IPFS nodes via the public IPFS DHT (libp2p). The DHT provides content routing: when another IPFS node wants to find who has a particular CID, it queries the DHT. A Corundum operator's IPFS node should be publicly reachable on libp2p ports (default: 4001) so that other IPFS nodes can fetch content from it.

In practice, direct libp2p connectivity is often blocked by NAT or firewalls. Kubo handles this via IPFS relay nodes (nodes that relay libp2p traffic between nodes that can't connect directly) and AutoNAT (automatic NAT traversal). For production operators, ensure that either the IPFS port is accessible from the internet, or that the deployment includes explicit relay configuration.

**Scaling IPFS.** For large operators (millions of users, billions of objects), a single Kubo node becomes a bottleneck. Two scaling options:

*IPFS Cluster* orchestrates multiple Kubo nodes, distributing pinning and replication across them. Cluster handles leader election, distributed pin tracking, and replication factor management. An operator with three IPFS nodes in a cluster can configure a replication factor of 3, meaning every pinned object exists on all three nodes.

*Delegated routing* separates the DHT routing function from the storage function. A delegated routing server maintains the DHT index while storage nodes handle content. This allows content storage to scale independently of routing capacity.

Both approaches are non-trivial to operate. For most operators, starting with a single Kubo node (with a remote pinning service for redundancy) and migrating to IPFS Cluster when single-node limits are hit is the pragmatic path.

**The Kubo HTTP API is not the user-facing API.** The Kubo HTTP API runs on localhost and should not be exposed to the internet. It has no authentication by default — anyone who can reach it can add, pin, and delete content. The Corundum protocol server (the Axum/HTTP application that handles inter-operator requests) runs on a public port and talks to Kubo on localhost. The architecture is: internet → Corundum protocol server (authenticated, public) → Kubo HTTP API (unauthenticated, localhost-only).

---

