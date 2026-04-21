## Part VI: Operators

### Chapter 17: What Operators Do

An operator is any entity that runs server infrastructure for Corundum users. The word "operator" was chosen deliberately over "server" or "instance" to emphasize the role: operators operate a service, and that service relationship is the contractual core of what they do.

Operators don't need any pre-existing business relationship with each other. There is no operator registration, no central directory that must approve new operators, no inter-operator agreement required before federation begins. They just speak the protocol.

**User hosting.** The operator maintains the user's IPFS content: pinning their posts, serving their manifest, and publishing their IPNS records so other operators can find them. When a user posts, the operator creates the appropriate IPFS objects, pins them, and updates the user's RootManifest and current chunk.

**Reply routing.** When Bob replies to Alice's post, Bob's operator contacts Alice's operator and submits the reply through the reply protocol. Alice's operator validates it and, if accepted, links it into Alice's timeline. This inter-operator coordination is what makes Corundum federated rather than merely decentralized — each operator is not just serving its own users but actively coordinating with other operators to make the social graph work.

**Curation enforcement.** Operators subscribe to curator feeds and apply their judgments to incoming and outgoing content. This is where the abstract moderation framework becomes concrete enforcement: when a reply arrives that matches a subscribed curation entry, the operator can reject it before it enters the timeline.

**Client service.** Each operator presents its own client/server API to its own users. This is explicitly not specified by Corundum. Birdsite might have a sophisticated REST API with extensive filter capabilities. Niǎogē might have a different API with different response structures. A minimal operator might just serve static files. The Corundum protocol is the inter-operator backbone; the client-facing interface is the operator's own business.

**The permissionless federation model.** There is no operator registration, no central directory that must approve new operators, and no inter-operator handshake required before federation can begin. A new operator publishes its Operator Manifest, starts speaking the protocol, and is immediately able to federate with any other operator that chooses to accept it.

This is a deliberate anti-centralization choice. Any system that requires new operators to register with a central authority hands that authority the power to deny access. Call it a "trusted operator registry" or a "federation whitelist" — it doesn't matter what you name it. If one entity controls who is allowed to federate, that entity controls the network. Corundum rejects this by making federation a technical capability rather than a granted permission.

The comparison with email is instructive. SMTP was originally designed the same way: any server that spoke the protocol could send mail to any other server. That openness worked for decades. The failure mode email eventually hit — spam, phishing, the gradual dominance of a handful of large providers — came from the economics of content delivery, not from the architecture. Gmail doesn't mandate that small operators register before sending; it just imposes increasingly strict reputation requirements that are effectively impossible to meet without engineering resources most small operators lack. Email became centralized not because the protocol required it but because the operational realities pushed in that direction.

Some ActivityPub implementations have introduced what their communities call "hand-knocking" — a prior relationship requirement before another instance can federate. An unknown instance trying to follow a user on a hand-knocking server may be silently dropped or queued for manual approval by the receiving instance's administrator. This is a community moderation tool, and it solves a real problem (unwanted federation with harassment servers), but it has a cost: it makes the network harder to enter for legitimate new operators, and it recreates a soft registration requirement through the back door.

Corundum's answer to the same problem is different. What replaces central registration is cryptographic authentication: operators don't need to introduce themselves in advance because the Operator Manifest provides a verifiable identity mechanism on first contact. When Birdsite receives a reply submission from an operator it has never seen before, it fetches that operator's Operator Manifest, verifies the signature, and evaluates the request against its federation policy — all in a single request. No prior relationship required. The manifest is the introduction. The policy is the operator's choice of whether to accept it.

**Operator autonomy.** Operators choose who to federate with. Birdsite can refuse to accept reply submissions from YuckChat's users. YuckChat can still attempt to submit, but Birdsite's Operator Manifest declares its federation policy, and Birdsite is entitled to reject based on that policy. There is no "must federate" rule in the protocol.

This mirrors email again: gmail.com is not required to accept mail from your self-hosted server, but it must at minimum be technically capable of receiving it if it chooses to. The obligation is to speak the protocol; cooperation is a choice. Corundum's federation is the same. The protocol provides the infrastructure for operators to cooperate. It does not require that they do so with any particular peer.

What this means in practice: an operator that wants to be a closed community can declare a restrictive federation policy that only accepts submissions from a named list of partner operators. An operator that wants to be maximally open can accept submissions from any operator with a valid manifest signature. Both are valid. The protocol provides the mechanism; the policy is the operator's.

**What operators are not responsible for.** An operator's obligations extend to its own users and to its own federation choices. They do not extend to what other operators do.

If YuckChat's operator chooses to host users who post harassment, that is YuckChat's responsibility to manage, not Birdsite's. Birdsite can defederate from YuckChat — stop accepting submissions from YuckChat users, stop displaying YuckChat content to Birdsite users. That is a legitimate and appropriate response. What Birdsite cannot be expected to do is monitor YuckChat's behavior or be held accountable for it. The two operators are independent entities with independent responsibilities.

This liability isolation is one of the features that makes it viable to run a Corundum operator without a full-time trust-and-safety team. Your moderation obligations are bounded: you are responsible for what your users post, and for the federation decisions you make. You are not responsible for policing the entire network or for the decisions of operators you have no control over. An operator that defederates from bad actors has done its job. An operator that stays federated with bad actors bears some responsibility for surfacing that content to its users. But neither operator bears responsibility for the existence of the bad actors in the first place.

**The practical operational footprint.** A conforming Corundum operator needs four things: an HTTPS server, an IPFS node (or gateway with pinning), a database, and the protocol implementation.

The HTTPS server serves the Operator Manifest, handles incoming reply submissions, and serves any client-facing API the operator wants to build. The IPFS node (or a pinning-service-backed gateway) stores and serves content by CID. The database stores user records, the DID-to-IPNS mapping cache, and whatever operational state the operator needs. The protocol implementation speaks all of the above in the formats the spec requires.

This is genuinely more complex than running a Mastodon instance. Mastodon is a single application with a single database and a well-understood deployment story. Corundum requires operating a distributed content store alongside the protocol server. That is a higher operational floor.

The tradeoff is what you get in return: user portability and the curation infrastructure that Mastodon does not have. A Mastodon user whose instance shuts down loses their identity and history. A Corundum user whose operator shuts down takes their IPNS keypair to a new operator and picks up exactly where they left off. The complexity cost buys a durable property that federated-but-not-portable systems cannot provide.

At the small end: a personal operator for one or a few users runs on a single VPS. IPFS, a PostgreSQL instance, and the protocol server fit comfortably on hardware available for $20/month. At the large end: a commercial operator running millions of accounts needs a distributed IPFS cluster, database replicas, and horizontally scaled protocol servers behind a load balancer. The protocol does not specify how to scale; it just specifies what a conforming operator must do.

### Chapter 18: The Operator Manifest

Every Corundum operator must publish an Operator Manifest at `/.well-known/corundum-operator`. This single document is the operator's identity credential and capability advertisement. Here is an abbreviated example:

```json
{
  "@type": "corundum:OperatorManifest",
  "id": "https://birdsite.example",
  "protocolVersion": "1.0",
  "published": "2025-01-15T00:00:00Z",
  "lastUpdated": "2025-03-01T12:00:00Z",
  "keys": [
    {
      "id": "https://birdsite.example#key-2025-01",
      "algorithm": "ed25519-v1",
      "publicKey": "z6Mkf5rGMoatrSj1f9CyvgZVBj3A4...",
      "status": "active",
      "activatedAt": "2025-01-15T00:00:00Z"
    }
  ],
  "auth": {
    "required": ["ed25519-v1"],
    "clockSkewTolerance": 300,
    "requiredComponents": ["@method", "@target-uri", "@authority", "content-digest", "corundum-timestamp"]
  },
  "capabilities": {
    "replies": true,
    "curation": true,
    "batchSubmission": true,
    "didIdentity": true,
    "migration": true,
    "postQuantum": false,
    "handleResolution": ["dns", "did"]
  },
  "info": {
    "displayName": "Birdsite",
    "userCount": 4200000,
    "region": "US",
    "languages": ["en"],
    "termsOfService": "https://birdsite.example/terms",
    "privacyPolicy": "https://birdsite.example/privacy"
  },
  "signature": {
    "algorithm": "ed25519-v1",
    "keyId": "https://birdsite.example#key-2025-01",
    "value": "MEUCIQDj..."
  }
}
```

The manifest is the single fetch that gives any other operator everything it needs to authenticate and communicate with Birdsite. The `keys` array lists every signing key Birdsite has, with statuses, activation dates, and algorithm identifiers. The `auth` section specifies what authentication Birdsite requires from operators that want to interact with it. The `capabilities` section tells other operators what features are supported.

**The self-signature trust model** is important to understand. The manifest is signed with Birdsite's own key — but this alone does not establish trust. When Operator A fetches Operator B's manifest for the first time, the self-signature proves that the manifest was created by whoever controls the key listed in the manifest. It does not prove that Operator B is who they claim to be. That's why the manifest must be served over HTTPS: the HTTPS transport security (TLS certificate chain, domain validation) provides the initial identity anchor. If the TLS certificate for `birdsite.example` is valid and the manifest at `/.well-known/corundum-operator` is signed with a key in that manifest, then you have reasonable confidence that you're talking to whoever controls `birdsite.example`.

HTTPS is required (not optional) for the operator manifest endpoint for exactly this reason: without TLS, there is no initial trust anchor for the self-signature. The self-signature is then used for subsequent requests (it's faster than a full TLS handshake for each request), but the initial manifest fetch must be over HTTPS.

### Chapter 19: Inter-Operator Authentication

Operators authenticate to each other using HTTP Message Signatures (RFC 9421). This standard, published in 2024, defines a mechanism for signing HTTP requests and responses in a way that is independent of the transport layer and resistant to replay attacks.

**The signature base string.** The core concept in RFC 9421 is the "signature base string" — a canonical, newline-delimited representation of the HTTP message components that are actually signed. The components to be covered are declared in the `Signature-Input` header, and the signature is computed over those bytes. Corundum requires five components:

- `@method`: The HTTP method (GET, POST, etc.)
- `@target-uri`: The full target URI of the request
- `@authority`: The HTTP Host header value
- `content-digest`: A SHA-256 hash of the request body (for POST requests), formatted as a Structured Field
- `corundum-timestamp`: A Corundum-specific header containing the request time as a Unix epoch integer

An abbreviated example of what the signature base string looks like for a reply submission POST:

```
"@method": POST
"@target-uri": https://birdsite.example/corundum/v1/replies/submit
"@authority": birdsite.example
"content-digest": sha-256=:X48E9qOokqqrvdts8nOJRJN3OWDUoyWxBf7kbu9DBPE=:
"corundum-timestamp": 1742044931
"@signature-params": ("@method" "@target-uri" "@authority" "content-digest" "corundum-timestamp");created=1742044931;keyid="https://wobble.example#key-2025-01";alg="ed25519-v1"
```

These bytes are what the signing operator feeds to its Ed25519 signing function.

**What the headers look like in a real request.** A POST from Wobble to Birdsite submitting a reply will carry two additional headers:

```
Signature-Input: sig1=("@method" "@target-uri" "@authority" "content-digest" "corundum-timestamp");created=1742044931;keyid="https://wobble.example#key-2025-01";alg="ed25519-v1"
Signature: sig1=:7cKpTH+5oE3ukmGXp8qZKRlHa2EvM9X1p4J7R3LmN0Z+KvBdQ9A8Ts1f...base64...:
```

The `Signature-Input` header is the declaration: it names the label (`sig1`), lists the components covered, and carries metadata including when the signature was created and which key signed it. The `Signature` header is the actual base64-encoded Ed25519 signature over the base string assembled from those components.

**Why those specific components were chosen.** Each component prevents a specific attack:

Covering `@method` and `@target-uri` together prevents a signed GET from being replayed as a signed POST to a different endpoint, and prevents a signed POST to one endpoint from being replayed to a different endpoint. A signature over the body alone would not catch either of these redirections.

Covering `content-digest` (a SHA-256 of the request body) ensures the body cannot be tampered with in transit. An attacker who intercepts the request and modifies the reply content would produce a different body hash, which would not match the signed `content-digest`, and the receiving operator would reject the request.

Covering `corundum-timestamp` prevents replay attacks. A valid signed request cannot be saved and replayed hours or days later, because the timestamp will no longer be within the acceptable window.

**Clock skew tolerance.** The `corundum-timestamp` header contains the request time as a Unix epoch integer. Receiving operators reject requests where the timestamp is more than the configured tolerance from the current time; the default is 300 seconds (5 minutes). This means an attacker who captures a signed request has at most a 10-minute window (the tolerance before and after the signature time) to replay it, and in practice far less since they must intercept and re-transmit quickly.

The 300-second default is a deliberate balance between security and operational robustness. Clocks on real servers drift. Operators in different regions may have modest NTP offsets. A window of a few minutes accommodates practical clock skew while keeping the replay window narrow enough to be meaningless for any realistic attack.

**Key rotation.** If Operator A rotates its signing key — replacing the key in its manifest — requests that were in-flight during the rotation may have been signed with the old key. Operator B may have cached Operator A's manifest and not yet fetched the new version, so it still has the old key. Alternatively, Operator B may have fetched the new manifest and no longer have the old key in cache.

To handle both cases, Operator A must keep the old key in its manifest with `status: "deprecated"` for at least the cache TTL period (typically 1 hour, governed by the `Cache-Control` header on the manifest response). During this window, Operator B may present either the old or new key ID on incoming requests, and both should be accepted. After the TTL has elapsed, the deprecated key can be removed from the manifest.

```json
{
  "keys": [
    {
      "id": "https://wobble.example#key-2025-03",
      "algorithm": "ed25519-v1",
      "publicKey": "z6MknewKey...",
      "status": "active",
      "activatedAt": "2025-03-01T00:00:00Z"
    },
    {
      "id": "https://wobble.example#key-2025-01",
      "algorithm": "ed25519-v1",
      "publicKey": "z6MkoldKey...",
      "status": "deprecated",
      "activatedAt": "2025-01-15T00:00:00Z",
      "deprecatedAt": "2025-03-01T00:00:00Z"
    }
  ]
}
```

Operators MUST NOT remove a deprecated key until at least one full cache TTL has elapsed since it was deprecated. Removing it prematurely would cause valid in-flight requests signed with the old key to fail verification.

The authentication flow:

1. Operator A wants to submit a reply to Operator B.
2. Operator A fetches Operator B's manifest from `/.well-known/corundum-operator` (served over HTTPS, cached).
3. Operator A constructs the HTTP request.
4. Operator A computes the signature base string from the required components, signs it with its own private key, and adds `Signature-Input` and `Signature` headers.
5. Operator B receives the request, reads the `keyId` from the `Signature-Input` header.
6. Operator B fetches Operator A's manifest (cached), finds the key with the matching ID, and verifies the signature.
7. Based on verification, Operator B assigns a trust level to the request.

**Trust levels** determine what operations are permitted and at what rate limits:

- **Unauthenticated**: No valid signature. Aggressively rate-limited. Only basic read access permitted.
- **Authenticated-unknown**: Valid signature, operator not in any directory or peer list. Default rate limits. Basic federation permitted.
- **Authenticated-known**: Valid signature, operator appears in known directories or has been manually vetted. Elevated rate limits. Full federation permitted.
- **Authenticated-trusted**: Valid signature, operator has an established trust relationship (explicit peer agreement, long shared history). Full rate limits. Possibly elevated quotas.

Trust levels allow operators to make graduated policy decisions rather than binary allow/deny. An operator might allow anyone to query content but only accept reply submissions from authenticated-known operators.

### Chapter 20: Operator Discovery

Operators are discovered through multiple mechanisms, forming a redundant discovery system with no single point of failure.

**Well-known endpoint**: Any domain running a Corundum operator can be discovered by fetching `/.well-known/corundum-operator`. If you know the domain, you can discover the operator.

**User RootManifest**: Every user's manifest declares their current operator's endpoint. This means that once you know a user's IPNS name, you can discover their operator — and from their operator, you can discover peers.

**Directories**: Operators can register with Corundum directory services, which provide searchable indexes of operators. Directories are not trusted in the protocol sense — they're just lists. The manifests they point to must be independently verified.

**Peer lists**: Operators can declare known peers in their manifests. This creates a web-of-trust-like discovery graph where following peer links from known operators leads to new operators.

The full discovery flow when Operator A needs to reach Operator B for the first time (triggered by needing to submit a reply to a user on Operator B):

1. Fetch the target user's RootManifest via their IPNS name (using the DHT or a known fast-path endpoint).
2. Read the `operator` field to find Operator B's endpoint URL.
3. Fetch Operator B's manifest from `{endpoint}/.well-known/corundum-operator` over HTTPS.
4. Verify the manifest's self-signature using the key declared in the manifest.
5. Cache the manifest for future requests (TTL from the `Cache-Control` header, typically 1 hour).

---

