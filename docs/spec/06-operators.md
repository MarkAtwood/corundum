## Part VI: Operators

### Chapter 17: What Operators Do

An operator is any entity that runs server infrastructure for Corundum users. The word "operator" was chosen deliberately over "server" or "instance" to emphasize the role: operators operate a service, and that service relationship is the contractual core of what they do.

Operators don't need any pre-existing business relationship with each other. There is no operator registration, no central directory that must approve new operators, no inter-operator agreement required before federation begins. They just speak the protocol.

**User hosting.** The operator maintains the user's IPFS content: pinning their posts, serving their RootManifest and IPNS record, and publishing the ReplyMap for their posts (Chapter 10). When a user posts, the operator creates the appropriate IPFS objects, pins them, and updates the user's current chunk and RootManifest. By default the operator holds the user's content key and signs on their behalf; for a self-custody user, the user's client signs and the operator only stores and serves (Chapter 5). An operator never holds a user's DID update keys (Chapter 7).

**Reply routing.** When Bob replies to Alice's post, Bob's operator contacts Alice's operator and submits the reply through the reply protocol. Alice's operator validates it and, if accepted, links it into Alice's timeline. This inter-operator coordination is what makes Corundum federated rather than merely decentralized — each operator is not just serving its own users but actively coordinating with other operators to make the social graph work.

**Curation enforcement.** Operators subscribe to curator feeds and apply their judgments to incoming and outgoing content. This is where the abstract moderation framework becomes concrete enforcement: when a reply arrives that matches a subscribed curation entry, the operator can reject it before it enters the timeline.

**Client service.** Each operator presents its own client/server API to its own users. This is explicitly not specified by Corundum. Birdsite might have a sophisticated REST API with extensive filter capabilities. Niǎogē might have a different API with different response structures. A minimal operator might just serve static files. The Corundum protocol is the inter-operator backbone; the client-facing interface is the operator's own business.

**The permissionless federation model.** There is no operator registration, no central directory that must approve new operators, and no inter-operator handshake required before federation can begin. A new operator publishes its Operator Manifest, starts speaking the protocol, and is immediately able to federate with any other operator that chooses to accept it.

This is a deliberate anti-centralization choice. Any system that requires new operators to register with a central authority hands that authority the power to deny access. Call it a "trusted operator registry" or a "federation whitelist" — it doesn't matter what you name it. If one entity controls who is allowed to federate, that entity controls the network. Corundum rejects this by making federation a technical capability rather than a granted permission.

The comparison with email is instructive. SMTP was originally designed the same way: any server that spoke the protocol could send mail to any other server. That openness worked for decades. The failure mode email eventually hit — spam, phishing, the gradual dominance of a handful of large providers — came from the economics of content delivery, not from the architecture. Gmail doesn't mandate that small operators register before sending; it just imposes increasingly strict reputation requirements that are effectively impossible to meet without engineering resources most small operators lack. Email became centralized not because the protocol required it but because the operational realities pushed in that direction.

Some ActivityPub implementations have introduced what their communities call "hand-knocking" — a prior relationship requirement before another instance can federate. An unknown instance trying to follow a user on a hand-knocking server may be silently dropped or queued for manual approval by the receiving instance's administrator. This is a community moderation tool, and it solves a real problem (unwanted federation with harassment servers), but it has a cost: it makes the network harder to enter for legitimate new operators, and it recreates a soft registration requirement through the back door.

Corundum's answer to the same problem is different. What replaces central registration is cryptographic authentication: operators don't need to introduce themselves in advance because the Operator Manifest provides a verifiable identity mechanism on first contact. When Birdsite receives a reply submission from an operator it has never seen before, it fetches that operator's Operator Manifest over HTTPS, verifies the request's signature against the keys it lists, and evaluates the request against its federation policy — all while handling that one request. No prior relationship required. The manifest is the introduction. The policy is the operator's choice of whether to accept it.

**Operator autonomy.** Operators choose who to federate with. Birdsite can refuse to accept reply submissions from YuckChat's users. YuckChat can still attempt to submit, but Birdsite's Operator Manifest declares its federation policy, and Birdsite is entitled to reject based on that policy. There is no "must federate" rule in the protocol.

This mirrors email again: gmail.com is not required to accept mail from your self-hosted server, but it must at minimum be technically capable of receiving it if it chooses to. The obligation is to speak the protocol; cooperation is a choice. Corundum's federation is the same. The protocol provides the infrastructure for operators to cooperate. It does not require that they do so with any particular peer.

What this means in practice: an operator that wants to be a closed community can declare a restrictive federation policy that only accepts submissions from a named list of partner operators. An operator that wants to be maximally open can accept submissions from any operator with a valid manifest signature. Both are valid. The protocol provides the mechanism; the policy is the operator's.

**What operators are not responsible for.** An operator's obligations extend to its own users and to its own federation choices. They do not extend to what other operators do.

If YuckChat's operator chooses to host users who post harassment, that is YuckChat's responsibility to manage, not Birdsite's. Birdsite can defederate from YuckChat — stop accepting submissions from YuckChat users, stop displaying YuckChat content to Birdsite users. That is a legitimate and appropriate response. What Birdsite cannot be expected to do is monitor YuckChat's behavior or be held accountable for it. The two operators are independent entities with independent responsibilities.

This liability isolation is one of the features that makes it viable to run a Corundum operator without a full-time trust-and-safety team. Your moderation obligations are bounded: you are responsible for what your users post, and for the federation decisions you make. You are not responsible for policing the entire network or for the decisions of operators you have no control over. An operator that defederates from bad actors has done its job. An operator that stays federated with bad actors bears some responsibility for surfacing that content to its users. But neither operator bears responsibility for the existence of the bad actors in the first place.

**The practical operational footprint.** A conforming Corundum operator needs four things: an HTTPS server, an IPFS node (or gateway with pinning), a database, and the protocol implementation.

The HTTPS server serves the Operator Manifest, handles incoming reply submissions, and serves any client-facing API the operator wants to build. The IPFS node (or a pinning-service-backed gateway) stores and serves content by CID. The database stores user records, the DID document cache, and whatever operational state the operator needs. The protocol implementation speaks all of the above in the formats the spec requires.

This is genuinely more complex than running a Mastodon instance. Mastodon is a single application with a single database and a well-understood deployment story. Corundum requires operating a distributed content store alongside the protocol server. That is a higher operational floor.

The tradeoff is what you get in return: user portability and the curation infrastructure that Mastodon does not have. A Mastodon user whose instance shuts down loses their identity and history. A Corundum user whose operator shuts down updates their DID to name a new operator and content key, and the new operator picks up their archive from IPFS exactly where it left off (Chapter 7). The complexity cost buys a durable property that federated-but-not-portable systems cannot provide.

At the small end: a personal operator for one or a few users runs on a single VPS. IPFS, a PostgreSQL instance, and the protocol server fit comfortably on hardware available for $20/month. At the large end: a commercial operator running millions of accounts needs a distributed IPFS cluster, database replicas, and horizontally scaled protocol servers behind a load balancer. The protocol does not specify how to scale; it just specifies what a conforming operator must do.

### Chapter 18: The Operator Manifest

Every Corundum operator must publish an Operator Manifest at `/.well-known/corundum-operator`. This single document is the operator's key list and capability advertisement. Here is an abbreviated example of the manifest's contents:

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
      "algorithm": "Ed25519",
      "publicKeyMultibase": "<base58btc multibase of the Ed25519 public key>",
      "status": "active",
      "activatedAt": "2025-01-15T00:00:00Z"
    }
  ],
  "encryptionKeys": [
    {
      "id": "https://birdsite.example#enc-2025-01",
      "publicKeyMultibase": "<base58btc multibase of the X25519 public key>",
      "status": "active"
    }
  ],
  "capabilities": {
    "replies": true,
    "curation": true,
    "batchSubmission": true,
    "migration": true,
    "postQuantum": false
  },
  "info": {
    "displayName": "Birdsite",
    "userCount": 4200000,
    "region": "US",
    "languages": ["en"],
    "termsOfService": "https://birdsite.example/terms",
    "privacyPolicy": "https://birdsite.example/privacy"
  }
}
```

What is served is not this object but an attached JWS over its bytes (Chapter 34), with one signature per active signing key:

```json
{
  "payload": "<base64url of the manifest bytes>",
  "signatures": [
    {
      "protected": "<base64url of {\"alg\":\"Ed25519\",\"crit\":[\"corundumType\"],\"corundumType\":\"OperatorManifest\",\"kid\":\"https://birdsite.example#key-2025-01\"}>",
      "signature": "<base64url of the Ed25519 signature>"
    }
  ]
}
```

The manifest is the single fetch that gives any other operator everything it needs to authenticate and communicate with Birdsite. The `keys` array lists Birdsite's signing keys with their statuses and algorithms. `encryptionKeys` lists the key users' encrypted social-graph lists are encrypted to (Chapter 25). The `capabilities` section tells other operators what features are supported. Authentication requirements are not advertised, because they are fixed by this specification (Chapter 19).

**What the self-signature proves.** The identity anchor for a manifest is TLS: a manifest fetched over HTTPS from `https://birdsite.example/.well-known/corundum-operator`, with a valid certificate for `birdsite.example`, is Birdsite's because whoever controls that domain served it. The self-signature adds no trust beyond that, since anyone who can serve the URL can also sign with keys they list. What it does prove is possession: every active key listed was used to sign, so an operator cannot list a public key it does not hold. A copy of a manifest obtained any other way (from a directory, a cache, or another operator) is only as trustworthy as its source, and operators MUST NOT use it to authenticate requests; they fetch the manifest from the well-known URL.

### Normative Manifest Specification

**Response requirements.** The manifest MUST be served over HTTPS at `{id}/.well-known/corundum-operator` as an attached JWS in the General JSON Serialization (Chapter 34), with `Content-Type: application/jose+json`. Each signature's protected header has `corundumType` `"OperatorManifest"` and a `kid` equal to the `id` of a signing key in the payload. The JWS MUST carry one valid signature by every signing key whose `status` is `"active"`, and verifiers MUST reject a manifest that lacks one or carries a signature by a key that is not active. The response SHOULD include `Cache-Control: max-age=3600` and MUST NOT set `max-age` below 60 seconds.

**Field requirements.**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `@type` | string | REQUIRED | MUST be `"corundum:OperatorManifest"` |
| `id` | string | REQUIRED | The operator's origin: `https://` followed by the host (and port, if not 443), with no path or trailing slash. MUST equal the origin of the URL from which the manifest was fetched. |
| `protocolVersion` | string | REQUIRED | Currently `"1.0"`. Receivers MUST reject manifests with unrecognized protocol versions. |
| `published` | string | REQUIRED | RFC 3339 datetime (UTC, `Z` suffix). When this manifest was first published. |
| `lastUpdated` | string | REQUIRED | RFC 3339 datetime (UTC, `Z` suffix). When this manifest was last modified. |
| `keys` | array | REQUIRED | Signing keys. At least one MUST have `status: "active"`, and at most one active key per algorithm. |
| `encryptionKeys` | array | REQUIRED | X25519 keys for encrypted lists (below). Exactly one MUST have `status: "active"`. |
| `capabilities` | object | OPTIONAL | If absent, all capabilities are treated as false/unsupported. |
| `info` | object | OPTIONAL | Human-readable operator information. All subfields are OPTIONAL. |

**Signing key fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | REQUIRED | The key identifier, used as `kid` in JWS headers and as `keyid` in HTTP message signatures. MUST be the manifest `id` followed by `#` and a name, for example `https://birdsite.example#key-2025-01`. |
| `algorithm` | string | REQUIRED | A JOSE `alg` name with status REQUIRED in the Chapter 36 registry that also has an RFC 9421 algorithm name. Currently only `"Ed25519"` qualifies (RFC 9421 name `ed25519`). |
| `publicKeyMultibase` | string | REQUIRED | The public key as a multicodec-prefixed key (`ed25519-pub`, `0xed`) in base58btc multibase (prefix `z`), as in `did:key`. |
| `status` | string | REQUIRED | One of `"active"`, `"deprecated"`, `"revoked"`. `active` keys sign new manifests and requests. `deprecated` keys are accepted for verification but MUST NOT be used for new signatures. `revoked` keys MUST NOT be accepted for any signature verification. |
| `activatedAt` | string | REQUIRED | RFC 3339 datetime when this key was first activated. |
| `deprecatedAt` | string | CONDITIONAL | RFC 3339 datetime. MUST be present if `status` is `"deprecated"`. |
| `revokedAt` | string | CONDITIONAL | RFC 3339 datetime. MUST be present if `status` is `"revoked"`. |

**Encryption key fields.** Each entry in `encryptionKeys` has an `id` (same form as a signing key `id`, used as the JWE recipient `kid`), a `publicKeyMultibase` (an `x25519-pub`, `0xec`, multicodec-prefixed key in base58btc multibase), and a `status` of `"active"` or `"deprecated"`. Senders encrypt only to the active key. To rotate, an operator adds a new active key, marks the old one deprecated, and re-encrypts every list it holds to the new key (Chapter 25); this produces a new RootManifest for each affected user, which a self-custody user's client must sign. The operator removes the deprecated key once no list it holds is encrypted to it.

**Capabilities semantics.**

| Capability | Type | Meaning |
|------------|------|-------------------|
| `replies` | boolean | Operator exposes `POST /corundum/v1/replies/submit`. |
| `curation` | boolean | Operator subscribes to and enforces external curation feeds. Informational; does not alter the reply protocol. |
| `batchSubmission` | boolean | Operator exposes `POST /corundum/v1/replies/batch`. Only meaningful when `replies` is also true. |
| `migration` | boolean | Operator exposes `POST /corundum/v1/migration/notify`. |
| `eventStream` | boolean | Operator exposes `GET /corundum/v1/events` (Chapter 48). |
| `eventStreamRetentionDays` | integer | Days of event history retained; default assumption 7 (Chapter 51). |
| `postQuantum` | boolean | Operator supports post-quantum signature algorithms (post-MVP). |

An operator that receives a request for an endpoint its capabilities declare as unsupported MUST return `404 Not Found`.

### Chapter 19: Inter-Operator Authentication

Operators authenticate requests to each other using HTTP Message Signatures (RFC 9421). The signature tells the receiver which operator sent a request and that the covered parts of the request were not changed in transit. It does not, by itself, stop a captured request from being sent again (RFC 9421 §7.2.2); Corundum handles that by making every request safe to repeat (below).

Responses are not signed. The requester reached the responder over HTTPS at a URL derived from its origin, so TLS already authenticates the response.

**The signature base.** RFC 9421 signs a "signature base": a newline-delimited representation of the covered message components followed by the signature parameters. The covered components are declared in the `Signature-Input` header. For a reply submission POST from Wobble to Birdsite, the signature base looks like this:

```
"@method": POST
"@target-uri": https://birdsite.example/corundum/v1/replies/submit
"@authority": birdsite.example
"content-digest": sha-256=:<base64 of the SHA-256 of the request body>:
"@signature-params": ("@method" "@target-uri" "@authority" "content-digest");created=1742044931;expires=1742045231;keyid="https://wobble.example#key-2025-01";alg="ed25519"
```

These bytes are what the signing operator feeds to its Ed25519 signing function. The request carries:

```
Content-Digest: sha-256=:<base64 of the SHA-256 of the request body>:
Signature-Input: sig1=("@method" "@target-uri" "@authority" "content-digest");created=1742044931;expires=1742045231;keyid="https://wobble.example#key-2025-01";alg="ed25519"
Signature: sig1=:<base64 of the 64-byte Ed25519 signature>:
```

**Why those components.** Covering `@method` and `@target-uri` prevents a signed request from being redirected to a different method or endpoint. Covering `content-digest`, the SHA-256 of the body (RFC 9530), prevents the body from being changed. The `created` and `expires` signature parameters bound how long a signature is accepted, so a captured request cannot be used hours or days later.

**Replay.** A signature is valid until it expires, so a captured request can be resent within that window. Corundum does not track nonces. Instead, every inter-operator request is idempotent: sending it twice has the same effect as sending it once.

- Reply submissions are keyed by the identifier (CID) of the reply activity they carry. Resubmitting a reply that was already accepted changes nothing and returns the original acceptance (Chapter 21).
- FollowNotifications are keyed by the CID of the notification, and a later notification for the same pair of users supersedes an earlier one (Chapter 26). Receiving one again, or receiving an older one, changes nothing.
- MigrationNotifications and BlockNotifications are hints: the receiver re-reads the authoritative state (the DID document, its own records) and acts on that, so repeating one has no further effect.
- GET requests do not change state.

New inter-operator endpoints MUST also be idempotent. No current endpoint needs a nonce.

**Key rotation.** If Operator A rotates its signing key, Operator B may still have A's old manifest in its cache. When B sees a `keyid` it does not know, it re-fetches A's manifest (rate-limited, below) and finds the new key. In the other direction, B may have fetched the new manifest while requests signed with the old key are still in flight. Operator A therefore keeps the old key in its manifest with `status: "deprecated"` for at least 3600 seconds (the maximum manifest cache time) after it stops signing with it:

```json
{
  "keys": [
    {
      "id": "https://wobble.example#key-2025-03",
      "algorithm": "Ed25519",
      "publicKeyMultibase": "<new public key>",
      "status": "active",
      "activatedAt": "2025-03-01T00:00:00Z"
    },
    {
      "id": "https://wobble.example#key-2025-01",
      "algorithm": "Ed25519",
      "publicKeyMultibase": "<old public key>",
      "status": "deprecated",
      "activatedAt": "2025-01-15T00:00:00Z",
      "deprecatedAt": "2025-03-01T00:00:00Z"
    }
  ]
}
```

**Revocation lags.** A revoked key stops working at a peer only when that peer's cached manifest expires, which can take up to 3600 seconds. An operator whose key is compromised revokes it and must expect forged requests to be accepted for up to an hour. This is why the cache time is capped at one hour rather than a day.

The authentication flow:

1. Operator A wants to submit a reply to Operator B.
2. Operator A constructs the HTTP request, computes the `Content-Digest`, builds the signature base, and signs it with each of its active keys.
3. Operator B receives the request and reads each `keyid` from `Signature-Input`. The origin of the `keyid` is the sender's origin.
4. Operator B fetches Operator A's manifest from `{origin}/.well-known/corundum-operator` over HTTPS (or uses its cached copy), checks that the manifest `id` equals that origin, finds the keys, and verifies the signatures.
5. Operator B checks that any operator named in the request body (such as `submittingOperator`) is that same origin, and applies its federation policy.

**Federation policy, not trust levels.** Corundum defines no trust levels on the wire. A receiver knows one fact from authentication: which operator origin sent the request, or that the request was not authenticated. Everything beyond that is the receiver's local policy: an allow list of peers it has vetted, a deny list, per-origin rate limits, or quotas that grow with a peer's history. Directory listings confer nothing, because directories are unauthenticated lists (Chapter 20) that anyone can be added to. A user's reply policy cannot name an operator trust level, because each operator's policy is its own.

### Normative Authentication Specification

**Covered components.** Every inter-operator request other than `GET /.well-known/corundum-operator` MUST carry an RFC 9421 signature covering:

| Request type | Required components |
|---|---|
| POST with body | `"@method"`, `"@target-uri"`, `"@authority"`, `"content-digest"` |
| GET or HEAD (no body) | `"@method"`, `"@target-uri"`, `"@authority"` |

Requests with a body MUST include a `Content-Digest` header (RFC 9530) with a `sha-256` digest of the body, and the receiver MUST check that it matches the body received.

**Signature parameters.** Each signature's parameters MUST include:

- `created` and `expires`, as integer Unix times, with `expires` no more than 300 seconds after `created`;
- `keyid`, the `id` of a signing key in the sender's manifest;
- `alg`, the RFC 9421 algorithm name of that key's algorithm (`"ed25519"` for `Ed25519`).

The receiver MUST reject a signature if `expires` minus `created` exceeds 300, if `created` is more than 60 seconds after the receiver's current time, if the current time is more than 60 seconds after `expires`, or if `alg` does not match the key's `algorithm`. The 60-second allowance absorbs ordinary clock differences between servers.

**Binding to the sender.** All signatures on one request MUST have `keyid`s with the same origin, and that origin is the sending operator. The receiver MUST fetch the sender's manifest from that origin, MUST check that the manifest `id` equals it, and MUST reject a request whose body names a different operator (for example, a `submittingOperator` that is not that origin).

**Signature coverage.** A sender MUST sign each request with every one of its active keys, giving each signature its own label. The receiver MUST verify that the request carries a valid signature by every active key in the sender's manifest. A request that lacks one MUST be rejected with reason `insufficient-signature-coverage`. Requiring every active key, rather than any one, prevents an attacker who breaks one algorithm from stripping the other signatures.

**Errors.** Authentication failures are `SIGNATURE_INVALID` (`401`) with `details.reason` `invalid-operator-signature` (missing, malformed, expired, or invalid signature; a revoked or deprecated-and-removed key; a sender binding mismatch) or `insufficient-signature-coverage` (Chapter 37). A `keyid` that is not in the sender's manifest after the re-fetch below is `KEY_NOT_FOUND`. On the reply endpoints these conditions are reported as `REPLY_REJECTED` with the same reasons (Chapter 21).

**Manifest cache and re-fetch.** Operators SHOULD cache a remote manifest for the duration given by its `Cache-Control` header, or 3600 seconds if none is present, and MUST NOT cache it for longer than 3600 seconds. If a request names a `keyid` that is not in the cached manifest, the receiver MUST re-fetch the manifest before rejecting it, but MUST NOT re-fetch any one origin's manifest more than once per 60 seconds; while that limit applies, it rejects the request with `KEY_NOT_FOUND`. This bounds the work an attacker can cause by sending made-up key identifiers. A `keyid` that the cached manifest lists as `revoked` is rejected without a re-fetch.

### Chapter 20: Operator Discovery

An operator is reached through its origin. Every route to an operator ends at the same place: fetching `{origin}/.well-known/corundum-operator` over HTTPS.

**From a user.** Every user's DID document names their operator in the `operatorEndpoint` of its `CorundumIdentity` service entry (Chapter 6). That value is the operator's origin, equal to its manifest `id`. For a `did:key` user, whose DID has no document, the operator endpoint is in their RootManifest.

**From a domain.** If you know the domain, you can fetch its manifest from the well-known URL.

**Directories and peers.** Operators may also learn of each other from directory services or from other operators. Directories are not trusted in the protocol sense — they're just lists. They confer no standing on the operators they list, and the manifests they point to must be fetched from the well-known URL and verified.

The full discovery flow when Operator A needs to reach Operator B for the first time (triggered by needing to submit a reply to a user on Operator B):

1. Read the DID of the parent post's author from its `attributedTo` field.
2. Resolve the DID (Chapter 6), or use a cached DID document no older than permitted (Chapter 7), and read `operatorEndpoint`.
3. Fetch Operator B's manifest from `{operatorEndpoint}/.well-known/corundum-operator` over HTTPS.
4. Verify the manifest JWS and check that its `id` equals `operatorEndpoint` (Chapter 18).
5. Cache the manifest for future requests (no longer than 3600 seconds; Chapter 19).

### Normative Inter-Operator Endpoint Table

The following endpoints constitute the complete Corundum inter-operator protocol. All paths are relative to the operator's `id` origin. All endpoints MUST be served over HTTPS. "Auth required" means an RFC 9421 signature per Chapter 19.

| Method | Path | Capability gate | Auth required | Status |
|--------|------|-----------------|---------------|--------|
| `GET` | `/.well-known/corundum-operator` | none | No | MVP |
| `GET` | `/routing/v1/ipns/{name}` | none | No | MVP, REQUIRED for operators that host users |
| `POST` | `/corundum/v1/replies/submit` | `replies: true` | Yes | MVP |
| `POST` | `/corundum/v1/follows/notify` | none | Yes | MVP |
| `POST` | `/corundum/v1/blocks/notify` | none | Yes | Post-MVP |
| `POST` | `/corundum/v1/replies/batch` | `batchSubmission: true` | Yes | Post-MVP |
| `POST` | `/corundum/v1/migration/notify` | `migration: true` | Yes | Post-MVP |
| `GET` | `/corundum/v1/events` | `eventStream: true` | Yes | Post-MVP |
| `GET` | `/corundum/v1/events/snapshots/index.json` | `eventStream: true` | Yes | Post-MVP (optional) |

`/routing/v1/ipns/{name}` is the standard IPFS delegated routing endpoint; it serves the signed IPNS record of each user the operator hosts (Chapter 5). The record is self-verifying, so the request needs no signature. Content is fetched by CID through IPFS. `/corundum/v1/follows/notify` receives FollowNotifications (follows and unfollows) and `/corundum/v1/blocks/notify` receives BlockNotifications (Chapter 26).

**Capability gate**: if the capability is not declared `true` in the operator's manifest, the endpoint MUST return `404 Not Found`. This makes "endpoint absent" and "endpoint present but rejecting this request" unambiguous.

**MVP scope**: implementations are required to support `GET /.well-known/corundum-operator`, `GET /routing/v1/ipns/{name}` (if they host users), `POST /corundum/v1/replies/submit`, and `POST /corundum/v1/follows/notify`, which followers-only reply policies depend on. All other endpoints are post-MVP and MAY be absent.

---
