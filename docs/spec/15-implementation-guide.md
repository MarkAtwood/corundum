## Part XV: Implementation Guidance

### Chapter 41: What a Minimal Operator Must Implement

To be a conforming Corundum operator, you must at minimum:

1. **Publish an Operator Manifest** at `/.well-known/corundum-operator` over HTTPS, with your keys, capabilities, and self-signature. Without this, other operators cannot verify your identity or your capabilities. When your reply submission arrives at another operator, the first thing they do is fetch your manifest and verify your signature. No manifest means the request is rejected — there is no fallback identity mechanism. The manifest is also how you declare what protocol features you support, so operators know what they can expect from you. An operator with no manifest is invisible to the protocol; nothing you send will be accepted.

2. **Store objects in IPFS as raw blocks** (Chapter 33). Every Corundum object's identifier is a CIDv1 with the `raw` codec and a `sha2-256` multihash over its exact bytes, so the identifier and the IPFS storage CID are the same value. You need an IPFS node (or a gateway plus a pinning service) to store, pin, and serve those blocks. Media files are the one exception: they are UnixFS files built with the fixed parameters of Chapter 15. A gateway-with-pinning approach is acceptable for a small operator; it gives up some performance and adds a dependency on the pinning service, but it conforms. A large operator needs local IPFS nodes to avoid the latency and throughput limits of an external gateway.

3. **Manage user identities** (Chapters 5–8). Users are keyed by DID. You must resolve `did:webvh` DIDs, and you must reject plain `did:web`: its document has no signed history, so whoever runs the web server could rewrite it. Supporting `did:plc` and `did:key` is optional. When you create a `did:webvh` DID for a user, you MUST set `portable: true` in its first log entry. You never hold a user's update keys. For each user you either hold the content key (the default) or accept the user's own. You resolve a DID document to its single `CorundumIdentity` service entry, and you never cache a DID document for longer than 24 hours.

4. **Resolve handles both ways** (Chapter 8). Implementations MUST support both methods: WebFinger (RFC 7033) for account handles (`alice@birdsite.example`) and the `_corundum.<domain>` DNS TXT record for domain handles. Serve WebFinger for your own users. A handle is shown as a user's only after the reverse check: the DID document must list it in `alsoKnownAs`. Without handles, users are identified by DIDs and 62-character IPNS names, and cross-operator mentions and search do not work.

5. **Publish and serve the content layer** (Chapters 9–13). Each user's RootManifest is an attached JWS, pointed to by an IPNS record under the user's content key. Behind it sit the archive tree (current chunk, epochs, ArchiveIndex), the StateMap, and a ReplyMap that you publish under your own IPNS name. Activities carry `seq`, and the archive tree never changes once written. Edits are new activities carrying `replaces`. Deletes are `Delete` activities, and you verify each one before acting on it. Serve IPNS records at the standard delegated routing endpoint, `GET /routing/v1/ipns/{name}`, so readers do not have to wait for the DHT. An operator that stores content as a flat list, or rewrites old epochs, is not conforming: other operators cannot navigate the first, and they will reject the second as a history rewrite (Chapter 34).

6. **Sign and verify with JWS under the strict Ed25519 profile** (Chapter 34). Use the General JSON Serialization. Activities get detached signatures (`"b64": false`) stored as SigningRecords; everything else gets attached signatures. The protected header contains exactly `alg`, `kid`, `corundumType`, `crit`, and, for detached signatures, `b64`. Sign and verify the exact bytes received. There is no canonicalization step, no Unicode normalization, and no re-serialization. For `alg` `"Ed25519"`, the verifier MUST make all four checks of the Chapter 34 profile. A verifier that skips them will disagree with other operators about which replies are valid.

7. **Support the Reply Protocol** (Chapter 21). Accept incoming reply submissions over authenticated HTTP POST. Verify the inline SigningRecord against the reply's bytes, check policies, and return either an acceptance or a `corundum:Error` with `code` `REPLY_REJECTED`. This is the core federation mechanism. Without it, your users cannot receive replies from users on other operators, and they cannot reply to posts hosted elsewhere. Federation without reply routing is read-only federation.

8. **Sign inter-operator requests** using HTTP Message Signatures (RFC 9421) with `ed25519` (the RFC 9421 registry name), covering the components of Chapter 19: `@method`, `@target-uri`, `@authority`, `content-digest`, and `corundum-timestamp`. Without signing, other operators cannot authenticate your requests. They cannot check federation policy, cannot rate-limit you per operator, and cannot tell your traffic from an attacker impersonating you. Expect `401 Unauthorized` on unsigned requests.

9. **Support the required algorithms**: Ed25519 for signatures and SHA-256 for hashes (Chapter 36). Reject every algorithm the registry does not list. Interoperability depends on everyone sharing this baseline.

10. **Implement the standard error envelope** (Chapter 37) for every non-2xx response with a body. Without it, every peer has to write custom error parsing for your API.

11. **Implement cursor-based pagination** (Chapter 38) for all collection endpoints. Offset pagination skips or repeats items when the collection changes during traversal; cursors do not.

### Chapter 42: What You Should Also Implement

Beyond the minimum:

- **Curation feed subscription**, including at least one CSAM hash database. This item is listed under "should also implement" because it is not technically required for protocol conformance. It is, however, legally required in the United States under 18 U.S.C. § 2258A, which requires electronic service providers to report apparent CSAM to NCMEC. Similar obligations exist in the EU, UK, Australia, and most other jurisdictions where you might operate commercially. Running a public Corundum operator without CSAM detection exposes you to criminal liability in most jurisdictions. The failure mode is not a bad user experience. It is prosecution.

- **Block and follow handling.** Block lists and follow lists are stored encrypted in the RootManifest (Chapter 25). When a reply arrives, the parent author's operator checks the author's block list with a local lookup; no probabilistic filter or proof structure is involved. Following always sends a FollowNotification to the followee's operator, so that followers-only replies work.

- **The inter-operator event stream** (Chapters 47–52) for high-volume federation: new posts, edits, deletions, and key changes, delivered over a persistent connection instead of per-request polling. Client-facing real-time streams are not part of the protocol; `docs/client-api/` describes the reference implementation's.

- **Content expiration handling.** Respect `expiresAt` on activities (Chapter 11). Time-limited content that keeps displaying after its expiry violates an explicit user choice. Expiry also matters for data-minimization obligations in some jurisdictions.

- **Migration support.** Accept inbound migrations and support outbound ones (Chapter 7). A migration is the user's DID update naming a new `ipnsName` and `operatorEndpoint`. A MigrationNotification is only a hint: re-resolve the DID and act on what it says. The new operator rebuilds the user's presence from IPFS; a cooperative old operator only makes this faster. Users trust an operator they can leave with their data intact.

- **ML-DSA-65 verification.** ML-DSA-65 is PROVISIONAL in the registry (Chapter 36), so users must not list ML-DSA-65 keys yet. Verifiers MAY implement it now. When the registry marks it REQUIRED, users will start adding ML-DSA-65 keys to their required sets, and a verifier that cannot check them will have to reject those users' content. Adding support while it is optional is a small task. Adding it under pressure, while federation with peers that have switched is already breaking, is an emergency.

### Chapter 43: Common Implementation Mistakes

**Re-serializing an object before verifying or forwarding it.** Parsing an activity into a struct and encoding it again changes its bytes: key order, whitespace, number formatting, and string escaping all drift. The new bytes have a different CID, and every signature over the original fails. Keep the received bytes. Hash and verify those bytes, and forward those bytes. Parse only to read fields (Chapter 33).

**Using a library's default Ed25519 verify.** Many Ed25519 libraries accept non-canonical encodings, small-order points, or `S ≥ L`, or use the cofactored equation. Two operators using different defaults will accept different sets of signatures, and will therefore build different reply trees from the same submissions. Use a verify function that makes exactly the four checks of Chapter 34, and test it against the edge-case vectors of Chapter 45.

**Treating IPNS name as primary identifier.** Store the DID as the primary identifier for users. The IPNS name changes whenever the content key changes, including on every migration. DID → IPNS is a cached value, not a primary key. Every protocol object names users by DID.

**Caching DID documents too long.** Never cache a DID document for longer than 24 hours, and prefer the method's own guidance (for `did:webvh`, the log's `ttl`, default one hour). A stale DID document routes to a user's old operator and accepts the old content key after the user has rotated it. When a MigrationNotification arrives, re-resolve the DID at once; do not wait for the cache to expire, and do not trust the notification's contents.

**Not verifying bidirectional handle claims.** It is not sufficient to verify that the handle resolves to the DID. The DID document must also list the handle in `alsoKnownAs`. Either check alone enables impersonation.

**Accepting reply submissions without verifying the inline signing record.** The submitting operator's HTTP signature proves the request came from a known operator; it does not prove the reply came from the claimed user. Verify the SigningRecord against the reply's bytes and the author's required set (Chapter 34).

**Putting the signature inside the activity.** Activities are stored unsigned. A signature field inside the activity changes its bytes and therefore its identifier. Signatures go in a separate SigningRecord (Chapter 12).

**Acting on a Delete without verifying it.** A `Delete` activity is an instruction to stop serving content. Before acting on it, verify that it is authentic (Chapter 34) and that its author is the author of the activity it names (Chapter 13). Otherwise anyone can take down anyone's posts.

**Trusting StateMap claims without checking the referenced activity.** `replacedBy` and `deletedBy` are pointers, not authority. Fetch the named activity and verify it. Confirm that it has the same author and that it names this post in `replaces` or `object` (Chapter 10). A pointer to an unverified or mismatched activity is ignored.

**Following `replacedBy` inside someone else's reply tree.** A reply tree shows the version of each reply that the parent's operator accepted. If a reader follows `replacedBy` there, anyone can get a harmless reply accepted and then edit it into abuse. Edited replies are new submissions, validated from scratch (Chapter 13).

**Rewriting archive objects.** Edits, deletions, and re-signatures go in the StateMap and new activities, never into existing entries or epochs. A RootManifest that commits to a different CID for an epoch a peer has already seen is treated as evidence of key compromise (Chapter 34).

**Adding objects with `ipfs add` defaults.** `ipfs add` wraps bytes in UnixFS, and its defaults (CIDv0, 256 KiB chunks, no raw leaves) produce a CID that is not the object's identifier. Store Corundum objects with `block/put` and the `raw` codec. Use `add` only for media, and only with the fixed parameters of Chapter 15, so that every operator computes the same CID for the same file.

**Off-by-one in ArchiveIndex epoch boundaries.** Epoch 0 covers entries 0–255, epoch 1 covers 256–511, and so on. `epoch_index = floor(seq / 256)` and `offset_in_epoch = seq % 256` are always correct. Any other arithmetic produces lookups that silently return the wrong entry. Check that the entry's `seq` equals the requested one, and that it equals the activity's `seq` (Chapter 10).

**Not distributing deletion notifications.** When a user deletes a post, notify the operators known to have fetched it (Chapter 13). If you only unpin locally, the content persists on other nodes despite the deletion.

**Treating curation checks as one-time-on-arrival.** Curators publish new entries continuously. When your curation sync pulls new entries, check each new hash against your stored content index. Content that was acceptable on arrival may match an entry published tomorrow.

**Retrying reply submissions without backoff.** When the target operator is unreachable, retry after 1, 4, 16, and 64 seconds, then keep backing off up to a configurable maximum (typically 1 hour), and abandon after 24 hours (Chapter 21). Tight retry loops hammer unreachable operators and get you rate-limited or blocked.

**Using offset pagination on a live collection endpoint.** Timelines and reply trees grow continuously, so `?page=3&size=20` produces duplicate and missing items. Use cursors.

### Chapter 44: Verification Checklist

**Signed objects.** Verify activities with the procedure in Chapter 34 ("Verifying an activity"), and attached JWS objects with the same header and profile checks. Do not reimplement the steps from memory. In outline: check the CID of the received bytes, check each protected header exactly, verify the signature under the strict profile, confirm that the required set is fully covered or that the activity is reachable from the current RootManifest, and defer if anything is unreachable.

**Reply submissions**, additionally:

1. Verify the submitting operator's HTTP Message Signature (Chapter 19), including `content-digest`, and check `corundum-timestamp` against the clock skew tolerance (default 300 seconds).
2. Verify the inline SigningRecord against the reply's bytes (Chapter 34). Activities not yet in an archive need signatures from every key in the author's current required set.
3. Check the parent author's reply policy against the reply author and the submitting operator (Chapter 22).
4. Look up the reply author's DID in the parent author's block list (Chapter 23).
5. Run the content against subscribed curation feeds (Chapter 31).
6. Apply rate limits.

Reject a failing submission with a `corundum:Error` whose `code` is `REPLY_REJECTED`, giving the reason in `details.reason` (Chapter 37).

### Chapter 45: Test Vectors

The spec will publish test vectors in these three groups. Implementations should pass all of them before claiming conformance:

1. **Activity bytes and raw CIDs.** Exact activity bytes, given as hex, with the CIDv1 (`raw`, `sha2-256`) of each. Implementations must reproduce the CID from the bytes without parsing them.
2. **Detached JWS.** SigningRecords over those activity bytes, made with a published RFC 8032 test key (for example, one from RFC 8032 §7.1). Each vector gives its protected header and the expected signature. Negative vectors carry an extra header parameter, the wrong `corundumType`, or a payload changed by one byte.
3. **Strict-profile Ed25519 edge cases.** Taken from an external source, such as the test vectors of "Taming the many EdDSAs" (Chalkias, Garillot, Nikolaenko, 2020). These cover non-canonical `A` and `R`, small-order points, `S ≥ L`, and the cofactored/cofactorless split. Each case gives the result required by the Chapter 34 profile.

One raw CID can be checked now. The 12 bytes `68 65 6c 6c 6f 20 77 6f 72 6c 64 0a` (ASCII `hello world` followed by a newline) have SHA-256 `a948904f2f0f479b8f8197694b30184b0d2ed1c1cd2a1ec0fb85d299a192a447` and the raw CID `bafkreifjjcie6lypi6ny7amxnfftagclbuxndqonfipmb64f2km2devei4`. That CID is the multibase prefix `b` followed by the unpadded lowercase base32 of the bytes `01 55 12 20` and the digest. `printf 'hello world\n' | ipfs block put --cid-codec=raw --mhtype=sha2-256` returns the same CID.

### Chapter 46: IPFS in Practice

The protocol specification describes what operators must store in IPFS and why. This chapter explains how: the software, the configuration patterns, and the operational tradeoffs.

**The reference implementation: Kubo.** The reference IPFS implementation is Kubo (formerly go-ipfs). Other IPFS implementations (Iroh, Helia for JavaScript) exist but have different APIs and maturity levels. Corundum operators should use Kubo. The relevant interface is Kubo's RPC API, on port 5001 by default. The Corundum protocol server talks to it with a plain HTTP client (`reqwest` in Rust); no IPFS client library is required.

Every Kubo RPC call is a `POST`, including the read-only ones; Kubo rejects `GET` on `/api/v0`. The operations a Corundum operator needs:

```
POST /api/v0/block/put?cid-codec=raw&mhtype=sha2-256     # store a Corundum object (multipart body); returns its CID
POST /api/v0/block/get?arg={cid}                         # fetch a Corundum object's exact bytes
POST /api/v0/add?cid-version=1&raw-leaves=true&chunker=size-1048576   # media files only (Chapter 15)
POST /api/v0/pin/add?arg={cid}                           # pin (prevent GC)
POST /api/v0/pin/rm?arg={cid}                            # unpin
POST /api/v0/pin/ls                                      # list pins
POST /api/v0/pin/remote/add?arg={cid}&service={service}&name={name}  # pin on a remote pinning service
POST /api/v0/key/gen?arg={keyname}&type=ed25519          # create a keystore key
POST /api/v0/name/publish?arg=/ipfs/{cid}&key={keyname}  # publish an IPNS record
POST /api/v0/name/resolve?arg=/ipns/{name}               # resolve an IPNS name
```

Use `block/put` for every Corundum object, never `add`. `add` wraps the bytes in UnixFS, which gives a different CID from the object's identifier. Corundum objects are at most 1 MiB, which is also the largest block Kubo accepts by default. After `block/put`, compare the returned CID with the one you computed yourself. Use `block/get`, not `cat`, to fetch objects; `cat` reads UnixFS files. For media, `add` must use the parameters shown above, which are the fixed parameters of Chapter 15.

**Pinning strategy.** IPFS garbage collection removes objects that are not pinned. Corundum objects are raw blocks with no IPFS-level links (Chapter 9), so pinning a RootManifest does not pin anything it references. Pin each object you keep individually: manifests, chunks, epochs, index pages, StateMap and ReplyMap pages, activities, SigningRecords, and media. When a user deletes a post, unpin the activity and its SigningRecords (Chapter 13), and GC will eventually reclaim the space.

Two pinning approaches:

*Local-only pinning* stores everything on the operator's own IPFS node. Simple to operate, all data under the operator's control, no external service dependencies. Suitable for small-to-medium operators. The risk is single-node data loss if the IPFS node's disk fails and there are no replicas.

*Hybrid pinning* combines a local node (for fast access, serving content to other IPFS nodes) with a remote pinning service (Pinata, Filebase, or similar) for durability. The operator pins content to both the local node and the pinning service. If the local node fails, content is still available through the pinning service's IPFS nodes. For production operators serving many users, hybrid pinning is recommended: it provides redundancy without requiring the operator to run a distributed IPFS cluster.

Kubo talks to remote services through the IPFS Pinning Service API. Register a service with `pin/remote/service/add`, then call `pin/remote/add` with the CID as `arg`.

**Garbage collection.** Never run IPFS GC automatically on a production Corundum node. Kubo does not run GC automatically unless the daemon is started with `--enable-gc`; check that your deployment does not do so. Automatic GC can delete objects that were added but whose pin call was interrupted. Run GC manually during maintenance, after confirming that every required object is pinned. Unpin first, confirm the unpin took effect, and only then run GC.

**IPNS publishing.** A user's IPNS name is their Ed25519 content key (Chapter 5). The operator also publishes its ReplyMap under an IPNS name of its own (Chapter 10). IPNS names are written as CIDv1 `libp2p-key` identifiers in base36: 62 characters, beginning `k51`. `name/publish` signs the record with a key from Kubo's keystore, publishes it to the DHT, and propagates it over minutes. Readers should not have to wait for that. Serve each current IPNS record at `GET /routing/v1/ipns/{name}` (Chapter 5) from the protocol server. Kubo returns the signed record from `routing/get?arg=/ipns/{name}`.

**Where content keys live.** Kubo's keystore is a directory of unencrypted private key files under the repository. It has no support for external key management or HSMs. Kubo is therefore not where operator-custodied content keys belong. Keep them in the operator's own key storage, such as an HSM, a cloud KMS, or an encrypted secrets store, with the same protection as the operator's own signing keys. One compromise of that storage compromises every user it holds. The consequence for publishing: `name/publish` only works with a key in Kubo's keystore. An operator that keeps content keys elsewhere must create IPNS records with its own signer. It can then serve those records directly from `/routing/v1/ipns/{name}`, and give them to Kubo for DHT publication with `routing/put?arg=/ipns/{name}`, which validates a record that someone else signed. Check that your Kubo version supports `routing/put` for IPNS records before relying on it. Importing content keys into Kubo's keystore is acceptable only where the keystore's disk protection meets the operator's key-storage requirements. Self-custody users sign their own records, and the operator only serves and republishes them.

**Content routing and connectivity.** Kubo connects to other IPFS nodes via the public IPFS DHT (libp2p). The DHT provides content routing: when another IPFS node wants to find who has a particular CID, it queries the DHT. A Corundum operator's IPFS node should be publicly reachable on libp2p ports (default: 4001) so that other IPFS nodes can fetch content from it.

In practice, direct libp2p connectivity is often blocked by NAT or firewalls. Kubo handles this via IPFS relay nodes (nodes that relay libp2p traffic between nodes that can't connect directly) and AutoNAT (automatic NAT traversal). For production operators, ensure that either the IPFS port is accessible from the internet, or that the deployment includes explicit relay configuration.

**Scaling IPFS.** For large operators (millions of users, billions of objects), a single Kubo node becomes a bottleneck. Two scaling options:

*IPFS Cluster* orchestrates multiple Kubo nodes, distributing pinning and replication across them. Cluster handles distributed pin tracking and replication factor management. An operator with three IPFS nodes in a cluster can configure a replication factor of 3, meaning every pinned object exists on all three nodes.

*Delegated routing* separates the DHT routing function from the storage function. A delegated routing server maintains the DHT index while storage nodes handle content. This allows content storage to scale independently of routing capacity.

Both approaches are non-trivial to operate. For most operators, starting with a single Kubo node (with a remote pinning service for redundancy) and migrating to IPFS Cluster when single-node limits are hit is the pragmatic path.

**The Kubo RPC API is not the user-facing API.** It is an admin interface. Anyone who can reach it can add, pin, and delete content, and can use every key in the keystore. Bind it to localhost and never expose it to the internet. The Corundum protocol server (the HTTP application that handles inter-operator requests) runs on a public port and talks to Kubo on localhost. The architecture is: internet → Corundum protocol server (authenticated, public) → Kubo RPC API (localhost-only).

---

