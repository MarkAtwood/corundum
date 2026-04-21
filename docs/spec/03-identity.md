## Part III: Identity

### Chapter 5: The Three-Layer Identity System

Identity in Corundum is a three-layer system designed so that no single layer's failure is catastrophic. Each layer provides a different guarantee, and the layers reinforce each other.

**Layer 1: IPNS (Operational Identity).** A user's IPNS name — the hash of a cryptographic keypair — is their stable operational identifier. This keypair signs all content the user publishes. The IPNS name points to the user's RootManifest (their current profile, timeline, operator declaration, and social graph). This is the operational layer: the identifier operators and other users interact with on a daily basis.

In practice, operators resolve user manifests via operator HTTP APIs (`GET /corundum/v1/users/{ipns}/manifest`) rather than via DHT lookup. DHT resolution is slow (typically 30–60 seconds) and is reserved for bootstrap and fallback situations — used when an operator endpoint is unknown or unreachable. The DHT is the substrate; the operator API is the fast path.

The blast radius of an IPNS key loss depends on which layer you still have. If you lose your IPNS private key but retain your DID recovery key, you can generate a new IPNS keypair, publish a new DID document declaring the new keypair, and broadcast a MigrationNotification. Your old content, signed with the old key, remains verifiable — signatures don't expire. Your new content will be signed with the new key. Your social graph and followers will update over time as their operators re-resolve your DID. The blast radius is temporary disruption and the loss of the ability to prove continuity between old and new content via key lineage (though the DID audit trail provides this instead).

**Layer 2: DID (Root of Trust).** Above the IPNS key sits a W3C Decentralized Identifier. The DID is the *canonical persistent* identifier for a user; the IPNS name is the *current operational key* associated with that DID. The distinction matters: operators MUST store the DID as the primary identifier for a user, not the IPNS name. The IPNS name is cached alongside the DID but treated as the current answer to the question "which key is this DID using right now?" — an answer that can change.

The DID document declares which IPNS key(s) belong to this identity, what handles the user claims, and what operators serve them. The DID provides recovery: if a user loses their IPNS private key, or if an operator goes rogue, the DID's recovery key can authorize a new IPNS keypair and re-anchor the identity. This is why the DID, not the IPNS name, is the canonical identifier: the IPNS name can be replaced under DID authority, but the DID persists.

The blast radius of DID document loss depends on the DID method. For `did:web`, DID document loss means losing control of the domain that hosts the DID document. This is serious but recoverable if the user still has the signing key — they can publish a new DID document at a new domain and broadcast the change. For `did:plc`, the operation log is distributed, so individual operator failures don't affect it. The blast radius is bounded in all cases where the user retains cryptographic keys.

Corundum supports three DID methods:

- `did:web` — DNS-based, easy to deploy, widely understood, but depends on domain availability and DNS security. Operators can issue `did:web` DIDs on behalf of their users (e.g., `did:web:birdsite.example:users:alice`).
- `did:plc` — operation-log-based, AT Protocol compatible, no domain required, designed specifically for the social media portability use case.
- `did:key` — self-describing, instant to create, maximum privacy, but no recovery if the key is lost. The DID IS the public key; there is no separate recovery key; the DID cannot be updated.

**Layer 3: Handles (Human-Readable Names).** Handles are identifiers like `alice.birdsite.example` or `@美玲@鸟歌.中文网`. They're human-readable aliases for the cryptographic identity below them. Handles are resolved via DNS TXT records, DID service entries, IPNS resolution, or ENS/HNS lookups.

The blast radius of handle DNS failure is limited: the handle stops resolving, but the underlying IPNS name and DID are unaffected. Users who already know Alice's IPNS name can still reach her. The handle is a convenience layer; losing it is annoying but not catastrophic.

The full verification chain is: Handle → DID → IPNS → RootManifest → Handle. If any link breaks, verification fails and the system reports which link is the problem. This chain property means that identity verification is not just "is this signature valid?" but "is the signer who they claim to be, through a verifiable chain of declarations?"

### Chapter 6: DID Documents

A DID document for a Corundum user is a JSON-LD document that declares the keys, services, and handles associated with an identity. Here is an example DID document for a user named Alice:

```json
{
  "@context": [
    "https://www.w3.org/ns/did/v1",
    "https://corundum.example/ns/v1"
  ],
  "id": "did:web:birdsite.example:users:alice",
  "verificationMethod": [
    {
      "id": "did:web:birdsite.example:users:alice#signing-key",
      "type": "Ed25519VerificationKey2020",
      "controller": "did:web:birdsite.example:users:alice",
      "publicKeyMultibase": "z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK"
    },
    {
      "id": "did:web:birdsite.example:users:alice#recovery-key",
      "type": "Ed25519VerificationKey2020",
      "controller": "did:web:birdsite.example:users:alice",
      "publicKeyMultibase": "z6MkpTHR8VNsBxYAAWHut2Geadd9jSwuias8sisDArDJF"
    }
  ],
  "authentication": [
    "#signing-key"
  ],
  "capabilityInvocation": [
    "#recovery-key"
  ],
  "service": [
    {
      "id": "did:web:birdsite.example:users:alice#corundum-identity",
      "type": "CorundumIdentity",
      "serviceEndpoint": {
        "ipnsName": "k51qzi5uqu5dj4nl2xvwya5k4y6a4xy9jh0jrh5e5c5w0n9i7r3i4j8fmq4gh",
        "operatorEndpoint": "https://birdsite.example/corundum/v1",
        "handles": ["alice.birdsite.example"],
        "role": "primary",
        "status": "active"
      }
    }
  ],
  "alsoKnownAs": [
    "https://alice.birdsite.example",
    "at://alice.birdsite.example"
  ]
}
```

Each field serves a specific purpose. The `verificationMethod` array lists every key associated with this identity. The signing key is the operational key that signs posts day-to-day. The recovery key is ideally stored offline (a hardware security key, a paper backup in a safe) and is only used for key rotation and recovery operations.

The `authentication` array says which keys can authenticate as this identity. The `capabilityInvocation` array says which keys can invoke capabilities — in Corundum's use, this means which keys can authorize key rotations and migrations.

The `service` entry for `CorundumIdentity` is what connects the DID to the Corundum operational layer. It specifies the IPNS name (the current operational key), the operator endpoint (where to send API requests), any handles associated with this identity, whether this is the primary identity or a secondary persona, and whether the identity is active or migrating or deactivated.

The `alsoKnownAs` field links this identity to other representations: a web profile URL, an AT Protocol handle. This enables cross-protocol identity claims.

A single DID can control multiple Corundum identities. Alice might have a primary persona on Birdsite and a photography persona on ArtBase, both controlled by the same DID, each with its own IPNS key, timeline, and social graph. She would have two `CorundumIdentity` service entries in her DID document, one marked `role: "primary"` and one `role: "secondary"`. This enables pseudonymous personas with a shared root of trust — Alice can prove she controls both without revealing which posts belong to which persona to audiences that don't know about the connection.

### Chapter 7: Key Rotation and Recovery

Key rotation is a first-class operation in Corundum. The protocol distinguishes two scenarios: cooperative migration, where the old operator participates in the transition, and hostile migration, where it does not.

**Cooperative migration**: Both the old and new operator sign the transition. The flow is:

1. Alice decides to move from Operator A to Operator B.
2. Alice authenticates to Operator B and initiates the migration process.
3. Operator B generates a new IPNS keypair for Alice (or accepts one she provides).
4. Alice uses her DID recovery key to authorize the new IPNS keypair in her DID document.
5. Operator A signs a `MigrationConsent` record, acknowledging the transfer.
6. Operator B begins fetching Alice's content archive from IPFS.
7. Operator B publishes a new RootManifest under Alice's (updated) IPNS name, declaring itself as the new operator.
8. Both operators co-sign a MigrationNotification.
9. The MigrationNotification is broadcast to known peers and directory services.

In a cooperative migration, nothing is lost. Alice's complete content history, social graph, reply trees, and followers cache all transfer. The migration audit trail records the full history with signatures from all parties.

**Hostile migration**: The old operator is uncooperative — it may have shut down, refused to release the key, gone technically dark, or is actively adversarial. The flow is:

1. Alice invokes DID authority. She uses her DID recovery key (which she holds independently of any operator) to publish a new IPNS keypair declaration in her DID document.
2. Alice authenticates to Operator B with the DID recovery key and the new IPNS keypair.
3. Operator B begins fetching Alice's content archive from IPFS. If Operator A was still running, the content is still pinned there; if Operator A has shut down, other operators that cached Alice's content can serve it.
4. Operator B publishes a new RootManifest under the new IPNS name.
5. Operator B broadcasts a MigrationNotification signed with the new IPNS key and the DID recovery key. The presence of the DID recovery key signature is what allows receiving operators to trust this as an authorized migration despite the absence of Operator A's signature.

The MigrationNotification contains: the DID, the old IPNS name, the new IPNS name, timestamp, a migration type (`cooperative` or `hostile`), and signatures. For a cooperative migration, it carries signatures from both operators. For a hostile migration, it carries the new operator's signature and the DID recovery key signature.

Receiving operators update their DID→IPNS cache upon receiving a valid MigrationNotification. Operators that did not receive the notification will discover the new IPNS name naturally when their cache TTL expires (recommended: 24 hours). On cache expiry, operators re-resolve via the DID document rather than relying on the cached IPNS name.

**The did:key tradeoff:** Users who chose `did:key` made a deliberate tradeoff. The `did:key` method derives the DID directly from the public key. There is no separate recovery key, no operation log, no rotation mechanism. The DID cannot be updated. This provides maximum privacy (no external service knows your DID; it's just math) and maximum self-sovereignty (no one can interfere with your identity), at the cost of no recovery path.

For `did:key` users, a hostile migration where the old operator controls the IPNS key results in a permanent identity break. The user can create a new identity, but they cannot prove continuity with the old one. Their followers will not automatically find them. This is not a bug — it is the documented consequence of the `did:key` tradeoff. Users who care about recovery should use `did:web` or `did:plc` with an offline recovery key.

### Chapter 8: Handle Resolution

Handles serve a human need that cryptographic identifiers don't meet: humans recognize `@alice.birdsite.example` where they would not recognize `k51qzi5uqu5dj4nl2xvwya5k4y6a4xy9jh0jrh5e5c5w0n9i7r3i4j8fmq4gh`. Handles are the socially meaningful layer of identity — the name people use, search for, and recognize.

The reason handles require bidirectional verification is to prevent impersonation attacks. Consider what would happen with unidirectional verification. If only the DID needed to claim a handle (but the DNS record didn't need to point back to the DID), then anyone could publish a DID document claiming to be `alice.birdsite.example`. The claim alone would pass verification. Bidirectional verification requires that both the DID claims the handle AND the DNS record at `alice.birdsite.example` points to the DID. An attacker who doesn't control `alice.birdsite.example`'s DNS cannot publish a valid DNS record pointing to their malicious DID. An attacker who does control `alice.birdsite.example`'s DNS but doesn't control Alice's DID could publish a DNS record, but it wouldn't match any DID that claims the handle.

The spec defines four handle resolution methods:

**DNS method**: A TXT record at `_corundum.alice.birdsite.example` contains the DID and IPNS name. For example:

```
_corundum.alice.birdsite.example. 3600 IN TXT "did=did:web:birdsite.example:users:alice ipns=k51qzi5uqu5..."
```

This is the simplest and most widely deployed method. It leverages the existing DNS infrastructure that every domain already uses. It depends on DNSSEC for security against tampering, though implementations should validate as best they can given DNSSEC deployment realities.

**DID method**: The DID document's `alsoKnownAs` field lists the handle. Verification checks that the DID claims the handle and the handle points back to the DID. This is useful when the DID document is the authoritative source.

**ENS method**: For Ethereum Name Service handles (e.g., `alice.eth`), the ENS registry stores a text record with the DID and IPNS name. This provides a blockchain-anchored handle for users who prefer that trust model.

**IPNS method**: The RootManifest itself declares handles with their verification method. This is the fallback for self-sovereign identities that prefer not to depend on DNS or external systems.

Implementations must support DNS and should support DID. The other methods are optional. The verification chain is always: resolve the handle → get a DID → check that the DID claims this handle → verified.

---

