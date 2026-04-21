## Part X: Cryptographic Foundations

### Chapter 33: Canonical Serialization

All signed or hashed objects must be serialized deterministically. Two implementations given the same logical object must produce identical byte sequences. The reason this matters is simple: if the verifier produces different bytes than the signer did, the signature will not verify, even though neither party made an error. Canonical serialization is the agreement about exactly which bytes represent any given object.

Corundum defines **Canonical JSON**, based on RFC 8785 (JSON Canonicalization Scheme) with extensions for Corundum-specific needs:

- **Field ordering**: Object keys sorted lexicographically by Unicode code point. This ensures that `{"b":2,"a":1}` and `{"a":1,"b":2}` produce the same bytes: `{"a":1,"b":2}`. Without key ordering, two implementations could both correctly represent the same logical object but produce different byte sequences and thus different hashes.

- **No whitespace**: No spaces, newlines, or indentation. Whitespace is not meaningful in JSON values, so any whitespace in the serialization is noise. Eliminating it ensures there's no ambiguity about which whitespace is included.

- **Number representation**: Integers as-is; floating point per ECMAScript's `Number.toString()` rules. This prevents the representation `1.0` from differing from `1`, and ensures there is a single canonical form for every floating point value.

- **String escaping**: Minimal escaping — only characters that must be escaped. This prevents the same character from being represented as `\u00e9` in one implementation and `é` in another.

- **Unicode normalization**: NFKC normalization for all strings. This is an extension beyond RFC 8785, and it matters. The word "café" can be represented in two valid Unicode sequences: as the precomposed character `é` (U+00E9) or as the letter `e` (U+0065) followed by the combining acute accent (U+0301). These produce different bytes but represent the same text. NFKC normalization ensures they produce the same canonical form. Without this, a French user typing "café" on a keyboard that produces combining characters would produce a different hash than the same text typed on a keyboard that produces precomposed characters.

- **Null handling**: Null-valued optional fields are omitted entirely; only explicitly nullable fields include null.

- **CID encoding**: CIDs are encoded as base32 strings in JSON, not as CBOR-tagged links. This ensures consistent representation across implementations that may or may not use CBOR.

- **Timestamp canonicalization**: UTC with `Z` suffix, uppercase `T` separator, trailing zeros stripped from fractional seconds. `"2025-02-01T14:30:00.000Z"` becomes `"2025-02-01T14:30:00Z"`.

The pitfall of not canonicalizing: if an operator creates an object, serializes it one way, signs it, and then serializes it again for transmission (perhaps with different key ordering because they used a hash map internally), the receiver's signature verification will fail even though no one tampered with the content. Canonical serialization is not just a nicety — it is required for signatures to work reliably across implementations.

**Canonical CBOR** is also defined (following RFC 8949 §4.2 deterministic encoding), used for efficient binary storage. However, Canonical JSON is the REQUIRED format for all signature operations. The spec chose JSON rather than CBOR for signing because JSON is human-inspectable, which makes debugging signature failures significantly easier.

**Test vectors:**

- `{"b":2,"a":1}` → Canonical: `{"a":1,"b":2}` (key sort)
- `{"ts":"2025-02-01T14:30:00.000Z"}` → `{"ts":"2025-02-01T14:30:00Z"}` (timestamp normalization)
- Object with NFKC-needed string: `"café"` (combining) → same as `"café"` (precomposed) after normalization
- Number: `1.0` → `1`; `1.5` → `1.5`; `1e10` → `10000000000`

### Chapter 34: Signing and Verification

**Why Ed25519.** Every cryptographic signature scheme involves tradeoffs among key size, signature size, signing speed, verification speed, and security properties. Ed25519 was chosen because it wins on most of these simultaneously.

RSA-2048 produces 256-byte signatures and requires ~2048-byte public keys. An Ed25519 public key is 32 bytes; an Ed25519 signature is 64 bytes. On a server processing thousands of signature verifications per second — validating incoming inter-operator messages, checking reply submissions, verifying curation entries — this compactness matters both for wire efficiency and for in-memory cache density.

ECDSA (including ECDSA P-256, the most common alternative) has a critical security property that makes it dangerous in practice: each ECDSA signature requires a fresh random nonce. If the nonce is ever reused, or if it is even slightly biased by a weak random number generator, the private key can be recovered by an attacker from two signatures. This is not a theoretical concern — Sony's PlayStation 3 was broken this way, and numerous Bitcoin wallets have been drained by the same attack on secp256k1 ECDSA. Ed25519 is a deterministic scheme: the nonce is derived from the message and the private key using a cryptographic hash. There is no per-signature randomness requirement, so a bad RNG during signing cannot compromise key security. For a federated protocol running on diverse server infrastructure, this property is essential.

secp256k1 is the curve used for Bitcoin ECDSA. It is in the optional list because some deployments will want to reuse existing Bitcoin/Ethereum key infrastructure. It is not the default because it is a historical artifact of Bitcoin's design choices — its security margin is similar to P-256 but it has no advantages over Ed25519 that would justify recommending it for new deployments.

Ed25519 also has a designed resistance to timing side-channels: the reference implementation (and all standard implementations) run in constant time regardless of key or message values. RSA and many ECDSA implementations have historically leaked key bits through timing variation; Ed25519's design closes this attack surface.

**The signing procedure.** The procedure must be followed exactly; any deviation produces a different byte sequence and causes verification to fail:

1. Remove the `signature`, `signatureAlgorithm`, and `resignatures` fields from the object.
2. Canonicalize all timestamps per the rules in Chapter 33.
3. Serialize the result to Canonical JSON.
4. Compute the Ed25519 signature over the resulting bytes.
5. Add the `signature`, `signatureAlgorithm`, and any other metadata back to the original object.

**The exact bytes that are signed.** After step 3, the payload is the UTF-8 encoding of the Canonical JSON string. No length prefix, no framing, no binary encoding: just the raw UTF-8 bytes of the JSON text. This is important for implementors: the signature verifier must produce exactly those bytes. Do not add a BOM. Do not wrap in a binary envelope. Do not hash the JSON before signing — Ed25519 handles its own internal hashing; the input to the signing function is the raw message bytes.

**The key identifier and how identity links to keys.** The `signatureAlgorithm` field (e.g., `"ed25519-v1"`) is included in the signed object before stripping, so it becomes part of the signed payload. However, a specific key ID is NOT embedded in the signed payload. The connection between the signature and a specific public key is made externally: for user-authored content, the verifier resolves the user's IPNS name to their `RootManifest`, which lists the user's current and historical signing keys. For operator-signed messages, the verifier fetches the sender's `OperatorManifest` and looks at its `keys` array. The signing record's `signer` field identifies the identity (IPNS name or operator URL), not a specific key.

This design is deliberate. If the key ID were embedded in the signed payload, an attacker could forge a message claiming to be signed by an arbitrary key, then create that key and claim it's the right one. By anchoring key lookup to the identity's manifest — which is itself controlled by the identity's private key via IPNS update — the verifier is trusting the key list that the identity itself declared, not a key ID embedded in the message.

**Key rotation and historical signature validity.** What if the identity has rotated keys since the signature was made? The verifier checks whether the signing time (from the `ts` field in the activity or SigningRecord) falls within the validity window of any key listed in the signer's manifest. A key entry includes an `activatedAt` timestamp and, once rotated out, a `deactivatedAt` timestamp. A signature made at time T with a key that was active from T-30d to T+5d is valid — the key was active when the signature was made. Corundum does not retroactively invalidate signatures made with old-but-then-valid keys. If it did, a key rotation would invalidate the entire historical archive, which would defeat the purpose of a permanent, verifiable content record.

**Verification when the manifest is unavailable.** If the verifier cannot fetch the signer's manifest — the operator is down, the IPNS resolution times out, the DID document is unreachable — the signature cannot be verified. The correct response is to mark the signature status as "unverified" (or "deferred"), not to accept or reject the content. Treating unavailability as rejection would let an attacker take down an operator's manifest to suppress their content. Treating unavailability as acceptance would let an attacker present unverifiable content as trusted. Deferral is the only sound policy: retry when the manifest becomes available.

**Future timestamps.** If an activity has a `ts` in the future, the verifier should allow a tolerance of up to 5 minutes to account for clock differences between operators running on different infrastructure. An activity timestamped more than 5 minutes in the future is likely a clock misconfiguration and should be rejected with error code `TIMESTAMP_SKEW`. This tolerance applies only to the verification step; operators should log and alert on large clock skews in their own infrastructure.

**A worked example.** Consider an activity object that, after step 1 (field stripping), looks like:

```json
{
  "@type": "corundum:Activity",
  "activityType": "bafyreiabc...Note",
  "author": "k51qzi5uqu5dj4nl2xvwya5k4y6a4xy9jh0jrh5e5c5w0n9i7r3i4j8fmq4gh",
  "content": { "mode": "inline", "mediaType": "text/plain", "value": "Hello, world!" },
  "signatureAlgorithm": "ed25519-v1",
  "ts": "2025-06-01T12:00:00Z"
}
```

After step 2 (timestamp canonicalization, already canonical here) and step 3 (Canonical JSON serialization with sorted keys and no whitespace), the bytes fed to the Ed25519 signing function are the UTF-8 encoding of:

```
{"@type":"corundum:Activity","activityType":"bafyreiabc...Note","author":"k51qzi5uqu5...","content":{"mediaType":"text/plain","mode":"inline","value":"Hello, world!"},"signatureAlgorithm":"ed25519-v1","ts":"2025-06-01T12:00:00Z"}
```

The resulting 64-byte signature is base64url-encoded and placed in the `signature` field. A verifier performs the identical strip-canonicalize-serialize steps and calls the Ed25519 verify function with those bytes, the signature, and the public key retrieved from the signer's manifest.

### Chapter 35: Cryptographic Agility

The specification explicitly plans for the eventual failure of its own algorithms. Cryptographic algorithms don't last forever. SHA-1 was broken. RSA-1024 is now considered insecure. MD5 should not be used for any security purpose. Ed25519, currently considered strong, will eventually face the same fate — perhaps from advances in quantum computing.

Every algorithm in Corundum has a registered identifier with a version suffix: `ed25519-v1`, `dilithium3-v1`. The version suffix means:

- If Ed25519 is found to be weak and needs to be updated, a new identifier `ed25519-v2` (or an entirely new algorithm identifier) can be introduced without ambiguity.
- Objects self-describe which algorithm was used, so verifiers can apply the right verification procedure.
- Multiple algorithms can coexist during transition periods.

Objects can carry **multiple signatures** via a `resignatures` array. During a transition from Ed25519 to post-quantum signing, an operator might include both an Ed25519 signature (for backward compatibility) and a Dilithium signature (for forward security). Receivers that understand both can verify both; receivers that only understand Ed25519 can still verify the Ed25519 signature.

**The downgrade attack problem:** Naively, multiple signatures create a vulnerability. If Operator B's manifest declares active Ed25519 and Dilithium keys, and Operator A receives a message with only an Ed25519 signature, should it accept? An attacker who intercepted the message could have stripped the Dilithium signature, knowing that the receiver might accept whichever signature validates.

Corundum's solution: verifiers MUST require all signatures they have reason to expect, based on the sender's declared active keys. The procedure is:

1. Fetch the sender's current manifest.
2. Enumerate all active signing keys.
3. For each algorithm family with an active key: require a valid signature from that family.
4. If a required signature is absent or invalid: reject the object.

This prevents the downgrade attack: if Operator B's manifest says it has an active Dilithium key, then Operator A will require a Dilithium signature on all of Operator B's messages. An attacker cannot strip the Dilithium signature without causing Operator A to reject the message.

Post-quantum adoption is gradual and per-sender. An operator starts requiring post-quantum signatures from a peer when that peer declares an active post-quantum key in their manifest. There is no protocol-wide flag day. The ecosystem migrates gradually as operators add post-quantum keys to their manifests. This is better than a flag-day approach in two ways: operators can migrate on their own schedule, and the mandatory-signature mechanism means there is no window where post-quantum signatures are declared but not enforced.

The **Algorithm Sunset Registry** (Chapter 36) tracks the lifecycle of every algorithm identifier:

- **REQUIRED**: Must be supported. Currently: `ed25519-v1` (signatures), `sha2-256-v1` (hashes).
- **OPTIONAL**: Supported but not required. Currently: ECDSA P-256, secp256k1, Dilithium, SPHINCS+, FALCON, SHA-512, SHA3-256, BLAKE2b-256.
- **SUNSET**: Deprecated with a warning date and sunset date. Implementations SHOULD warn on use before the sunset date; implementations MUST reject after the sunset date. Currently: `sha1-v1`, `rsa-1024-v1`, `dsa-2048-v1`.
- **PROHIBITED**: No transition period; reject immediately. Currently: `md5-v1`, `md4-v1`.

See Chapter 36 for the complete registry, active sunset declarations, sunset declaration JSON schema, and the sunset process.

---

### Chapter 36: Algorithm Sunset Registry

**Status:** Living Document
**Registry Version:** 1.1
**Last Updated:** 2026-02-02
**Maintainer:** Corundum Working Group

---

#### Registered Algorithms

##### Signature Algorithms: Currently Required

| Identifier | Algorithm | Specification | Status |
|------------|-----------|---------------|--------|
| `ed25519-v1` | EdDSA over Curve25519 | RFC 8032 | REQUIRED |

##### Signature Algorithms: Currently Optional (Pre-Quantum)

| Identifier | Algorithm | Specification | Status |
|------------|-----------|---------------|--------|
| `ecdsa-p256-v1` | ECDSA over secp256r1 | RFC 6979 | OPTIONAL |
| `ecdsa-secp256k1-v1` | ECDSA over secp256k1 | RFC 6979 | OPTIONAL |

##### Signature Algorithms: Currently Optional (Post-Quantum)

| Identifier | Algorithm | Specification | Status |
|------------|-----------|---------------|--------|
| `dilithium3-v1` | CRYSTALS-Dilithium Level 3 | FIPS 204 | OPTIONAL |
| `dilithium5-v1` | CRYSTALS-Dilithium Level 5 | FIPS 204 | OPTIONAL |
| `sphincs-sha2-256f-v1` | SPHINCS+ SHA2-256f | FIPS 205 | OPTIONAL |
| `falcon512-v1` | FALCON-512 | FIPS 206 | OPTIONAL |

##### Signature Algorithms: Sunset

| Identifier | Algorithm | Specification | Status | Warning Date | Sunset Date |
|------------|-----------|---------------|--------|--------------|-------------|
| `rsa-1024-v1` | RSA-1024 | RFC 8017 | SUNSET | 2025-02-04 | 2026-02-04 |
| `dsa-2048-v1` | DSA-2048 | FIPS 186-4 | SUNSET | 2025-02-04 | 2026-08-04 |

##### Hash Algorithms: Currently Required

| Identifier | Algorithm | Specification | Status |
|------------|-----------|---------------|--------|
| `sha2-256-v1` | SHA-256 | FIPS 180-4 | REQUIRED |

##### Hash Algorithms: Currently Optional

| Identifier | Algorithm | Specification | Status |
|------------|-----------|---------------|--------|
| `sha2-512-v1` | SHA-512 | FIPS 180-4 | OPTIONAL |
| `sha3-256-v1` | SHA3-256 | FIPS 202 | OPTIONAL |
| `blake2b-256-v1` | BLAKE2b-256 | RFC 7693 | OPTIONAL |

##### Hash Algorithms: Sunset

| Identifier | Algorithm | Specification | Status | Warning Date | Sunset Date |
|------------|-----------|---------------|--------|--------------|-------------|
| `sha1-v1` | SHA-1 | FIPS 180-4 | SUNSET | 2025-02-04 | 2026-08-04 |

##### Hash Algorithms: Prohibited

| Identifier | Algorithm | Specification | Status | Effective Date |
|------------|-----------|---------------|--------|----------------|
| `md5-v1` | MD5 | RFC 1321 | PROHIBITED | 2025-02-04 |
| `md4-v1` | MD4 | RFC 1320 | PROHIBITED | 2025-02-04 |

Algorithms with PROHIBITED status MUST be rejected immediately by conforming implementations. No transition period applies. These algorithms have known practical attacks that produce collisions trivially; accepting them in any context represents an immediate security failure.

---

#### Active Sunset Declarations

##### SHA-1 (`sha1-v1`)

**Declared:** 2025-02-04
**Warning Date:** 2025-02-04 (immediate)
**Sunset Date:** 2026-08-04
**Reason:** `cryptanalysis-weakness`
**Replacement Algorithms:** `sha2-256-v1`, `sha2-512-v1`, `sha3-256-v1`

SHA-1 collision resistance was practically broken by the SHAttered attack (2017) and further weakened by chosen-prefix collision attacks (2020). SHA-1 MUST NOT be used for new content after the sunset date. Existing SHA-1 references (e.g., content-addressed identifiers) MUST be migrated to a replacement algorithm before the sunset date.

The standard 36-month minimum transition period is waived under the expedited sunset procedure. SHA-1 collision resistance has been publicly broken since 2017; the 18-month transition period reflects operational migration needs only.

```json
{
  "@type": "corundum:AlgorithmSunset",
  "algorithm": "sha1-v1",
  "sunsetDate": "2026-08-04",
  "warningDate": "2025-02-04",
  "reason": "cryptanalysis-weakness",
  "replacementAlgorithms": [
    "sha2-256-v1",
    "sha2-512-v1",
    "sha3-256-v1"
  ],
  "declaredBy": "corundum-working-group",
  "declaredAt": "2025-02-04T00:00:00Z",
  "transitionGuidance": {
    "minimumOverlapMonths": 18,
    "resignatureDeadline": "2026-06-04"
  },
  "signatureAlgorithm": "ed25519-v1",
  "signature": "..."
}
```

##### RSA-1024 (`rsa-1024-v1`)

**Declared:** 2025-02-04
**Warning Date:** 2025-02-04 (immediate)
**Sunset Date:** 2026-02-04
**Reason:** `key-size-insufficient`
**Replacement Algorithms:** `ed25519-v1`, `ecdsa-p256-v1`, `dilithium3-v1`

RSA with 1024-bit keys is factorable with current academic and state-level resources. NIST deprecated RSA-1024 in 2013. Conforming implementations MUST warn immediately on RSA-1024 signatures and MUST reject them after the sunset date.

The standard 36-month minimum transition period is waived under the expedited sunset procedure. RSA-1024 has been considered insecure since at least 2013.

```json
{
  "@type": "corundum:AlgorithmSunset",
  "algorithm": "rsa-1024-v1",
  "sunsetDate": "2026-02-04",
  "warningDate": "2025-02-04",
  "reason": "key-size-insufficient",
  "replacementAlgorithms": [
    "ed25519-v1",
    "ecdsa-p256-v1",
    "dilithium3-v1"
  ],
  "declaredBy": "corundum-working-group",
  "declaredAt": "2025-02-04T00:00:00Z",
  "transitionGuidance": {
    "minimumOverlapMonths": 12,
    "resignatureDeadline": "2026-01-04"
  },
  "signatureAlgorithm": "ed25519-v1",
  "signature": "..."
}
```

##### DSA (`dsa-2048-v1`)

**Declared:** 2025-02-04
**Warning Date:** 2025-02-04 (immediate)
**Sunset Date:** 2026-08-04
**Reason:** `standards-deprecated`
**Replacement Algorithms:** `ed25519-v1`, `ecdsa-p256-v1`, `dilithium3-v1`

DSA was formally deprecated by NIST in FIPS 186-5 (2023). DSA signatures are no longer permitted for generating digital signatures per NIST guidance. Existing DSA-signed content MUST be resignatured with a replacement algorithm before the sunset date.

The standard 36-month minimum transition period is waived under the expedited sunset procedure. NIST formally deprecated DSA in 2023.

```json
{
  "@type": "corundum:AlgorithmSunset",
  "algorithm": "dsa-2048-v1",
  "sunsetDate": "2026-08-04",
  "warningDate": "2025-02-04",
  "reason": "standards-deprecated",
  "replacementAlgorithms": [
    "ed25519-v1",
    "ecdsa-p256-v1",
    "dilithium3-v1"
  ],
  "declaredBy": "corundum-working-group",
  "declaredAt": "2025-02-04T00:00:00Z",
  "transitionGuidance": {
    "minimumOverlapMonths": 18,
    "resignatureDeadline": "2026-06-04"
  },
  "signatureAlgorithm": "ed25519-v1",
  "signature": "..."
}
```

---

#### Historical Prohibitions

##### MD5 (`md5-v1`)

**Effective:** 2025-02-04
**Status:** PROHIBITED
**Reason:** `cryptanalysis-weakness`

MD5 collision resistance was broken by Wang and Yu (2004). Practical collision attacks now run in seconds on commodity hardware. The Flame malware (2012) demonstrated real-world exploitation of MD5 collisions against code signing infrastructure. MD5 was never accepted in the Corundum protocol; this declaration formalizes its prohibition.

##### MD4 (`md4-v1`)

**Effective:** 2025-02-04
**Status:** PROHIBITED
**Reason:** `cryptanalysis-weakness`

MD4 has been catastrophically broken since Dobbertin (1995). Full collisions can be generated in microseconds. MD4 was never accepted in the Corundum protocol; this declaration formalizes its prohibition.

---

#### Future Considerations

##### Ed25519 (`ed25519-v1`)

**Current Status:** REQUIRED, no sunset scheduled.

Ed25519 is vulnerable to quantum computers running Shor's algorithm. Current estimates suggest 2030–2040 for cryptographically relevant quantum computers. Projected timeline:

- **2026–2028:** Begin requiring dual signatures (classical + post-quantum)
- **2029–2031:** Warning period for Ed25519-only content
- **2032–2035:** Potential sunset (dependent on quantum computing progress)

Migration path: add post-quantum keys to operator manifests → sign new content with both algorithms → resignature historical content → eventually reject Ed25519-only content.

##### ECDSA variants (`ecdsa-p256-v1`, `ecdsa-secp256k1-v1`)

**Current Status:** OPTIONAL, no sunset scheduled. Same quantum vulnerability as Ed25519. May be sunset concurrently with Ed25519.

##### RIPEMD-160

**Current Status:** Not registered. 160-bit output provides only 80-bit collision resistance; theoretical attacks have reduced effective security below design parameters. If registered in the future, would likely enter at SUNSET or PROHIBITED status. Implementations SHOULD NOT introduce new dependencies on RIPEMD-160.

---

#### Algorithm Identifier Format

Algorithm identifiers follow the pattern `{algorithm-family}-{variant}-v{version}`:

| Component | Description | Constraints |
|-----------|-------------|-------------|
| `algorithm-family` | Base algorithm name | Lowercase alphanumeric |
| `variant` | Specific instantiation | Lowercase alphanumeric, optional |
| `version` | Identifier version | Integer, starts at 1 |

The version number indicates the identifier format version, not the algorithm version. A new version is created when the signing or verification procedure changes. Algorithm parameters (curve, hash function) are fixed within a version.

Valid: `ed25519-v1`, `dilithium3-v1`, `sphincs-sha2-256f-v1`, `ecdsa-p256-v1`, `sha2-256-v1`

Invalid: `Ed25519-v1` (uppercase), `ed25519` (missing version), `ed25519_v1` (underscore not allowed)

---

#### Algorithm Strength Ordering

When multiple acceptable signatures exist, prefer stronger algorithms.

**Recommended signature preference order (2025):**

1. `dilithium5-v1` (highest post-quantum security)
2. `dilithium3-v1` (good post-quantum security, smaller signatures)
3. `sphincs-sha2-256f-v1` (conservative post-quantum, hash-based)
4. `falcon512-v1` (efficient post-quantum)
5. `ed25519-v1` (current standard, pre-quantum)
6. `ecdsa-p256-v1` (legacy compatibility)
7. `ecdsa-secp256k1-v1` (blockchain compatibility)

**Recommended hash preference order (2025):**

1. `sha3-256-v1` (independent design from SHA-2 family)
2. `sha2-512-v1` (larger state, higher security margin)
3. `sha2-256-v1` (current standard, widely deployed)
4. `blake2b-256-v1` (high performance, strong security margin)

Algorithms with SUNSET or PROHIBITED status MUST NOT appear in preference ordering. Implementations MUST NOT select a sunset or prohibited algorithm when an acceptable alternative is available.

---

#### Sunset Declaration Process

**Phase 1 — Proposal:** Working group identifies algorithm weakness or better alternative. Draft sunset declaration created with proposed timeline. Minimum 36-month total transition period required.

**Phase 2 — Public Comment:** Draft published for public comment (minimum 90 days). Feedback collected from operators and implementers. Timeline adjusted based on feedback.

**Phase 3 — Final Declaration:** Final declaration published with firm warning date and sunset date, and replacement algorithms listed.

**Phase 4 — Implementation:** Operators update manifests with sunset information. Implementers add warnings for deprecated algorithms. Migration tools provided for resignature.

**Phase 5 — Enforcement:** During the warning period, verifiers warn on use of the deprecated algorithm. After the sunset date, verifiers reject the deprecated algorithm.

**Expedited sunset procedure:** The standard 36-month minimum transition period MAY be waived when ALL of the following are met:

1. The algorithm has a publicly demonstrated practical attack (not merely theoretical)
2. The attack has been known for at least 24 months prior to the sunset declaration
3. A recognized standards body (NIST, IETF, or equivalent) has deprecated or disrecommended the algorithm
4. Replacement algorithms are already registered and available in the protocol

Algorithms meeting these criteria may be declared SUNSET with a reduced transition period (minimum 12 months) or PROHIBITED with immediate effect. The expedited rationale MUST be documented in the sunset declaration.

**Recommended migration timeline (standard procedure):**

| Phase | Duration | Activities |
|-------|----------|------------|
| Announcement | 12 months | Publish sunset, update docs |
| Key Generation | 12 months | Users add replacement keys |
| Dual Signing | 12 months | Sign with both algorithms |
| Warning | 12 months | Warn on deprecated-only content |
| Resignature | 12 months | Automated resignature campaigns |
| Soft Enforcement | 6 months | Deprioritize deprecated content |
| Hard Enforcement | Ongoing | Reject deprecated signatures |

**Minimum total:** 36 months from announcement to sunset. PROHIBITED algorithms require no migration timeline; implementations MUST reject them immediately.

---

#### Sunset Declaration Format

```json
{
  "@type": "corundum:AlgorithmSunset",
  "algorithm": "ed25519-v1",
  "sunsetDate": "2032-01-01",
  "warningDate": "2029-01-01",
  "reason": "quantum-computing-threat",
  "replacementAlgorithms": [
    "dilithium3-v1",
    "dilithium5-v1",
    "sphincs-sha2-256f-v1"
  ],
  "declaredBy": "corundum-working-group",
  "declaredAt": "2028-01-01T00:00:00Z",
  "transitionGuidance": {
    "minimumOverlapMonths": 36,
    "resignatureDeadline": "2031-06-01"
  },
  "signatureAlgorithm": "ed25519-v1",
  "signature": "..."
}
```

**Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `@type` | string | REQUIRED | MUST be `"corundum:AlgorithmSunset"` |
| `algorithm` | string | REQUIRED | Algorithm identifier being sunset |
| `sunsetDate` | date | REQUIRED | Date after which algorithm is untrusted |
| `warningDate` | date | RECOMMENDED | Date to begin warnings |
| `reason` | string | REQUIRED | Reason code (see below) |
| `replacementAlgorithms` | array | REQUIRED | Acceptable replacement algorithm identifiers |
| `declaredBy` | string | REQUIRED | Entity declaring sunset |
| `declaredAt` | datetime | REQUIRED | Declaration timestamp (RFC 3339; millisecond precision RECOMMENDED) |
| `transitionGuidance` | object | RECOMMENDED | Migration guidance |
| `signatureAlgorithm` | string | REQUIRED | Algorithm used to sign this declaration |
| `signature` | string | REQUIRED | Signature over this declaration |

`declaredAt` supports sub-second precision per RFC 3339. Trailing zeros in fractional seconds are removed before signing per canonical serialization rules (Chapter 33).

**Reason codes:**

| Code | Description |
|------|-------------|
| `quantum-computing-threat` | Vulnerable to quantum attacks |
| `cryptanalysis-weakness` | Classical cryptanalysis has weakened algorithm |
| `implementation-flaw` | Implementation defects discovered |
| `key-size-insufficient` | Key size no longer meets security requirements |
| `protocol-upgrade` | Protocol changes require new algorithm |
| `standards-deprecated` | Algorithm deprecated by a recognized standards body (NIST, IETF, or equivalent) |

---

#### Sunset Declaration JSON Schema (Normative)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "AlgorithmSunsetDeclaration",
  "type": "object",
  "required": ["@type", "algorithm", "sunsetDate", "reason", "replacementAlgorithms", "declaredBy", "declaredAt", "signatureAlgorithm", "signature"],
  "properties": {
    "@type": {
      "type": "string",
      "const": "corundum:AlgorithmSunset"
    },
    "algorithm": {
      "type": "string",
      "pattern": "^[a-z0-9]+-([a-z0-9]+-)?v[0-9]+$"
    },
    "sunsetDate": {
      "type": "string",
      "format": "date"
    },
    "warningDate": {
      "type": "string",
      "format": "date"
    },
    "reason": {
      "type": "string",
      "enum": [
        "quantum-computing-threat",
        "cryptanalysis-weakness",
        "implementation-flaw",
        "key-size-insufficient",
        "protocol-upgrade",
        "standards-deprecated"
      ]
    },
    "replacementAlgorithms": {
      "type": "array",
      "items": {"type": "string"},
      "minItems": 1
    },
    "declaredBy": {
      "type": "string"
    },
    "declaredAt": {
      "type": "string",
      "format": "date-time",
      "pattern": "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(\\.\\d{1,9})?Z$"
    },
    "transitionGuidance": {
      "type": "object",
      "properties": {
        "minimumOverlapMonths": {"type": "integer", "minimum": 0},
        "resignatureDeadline": {"type": "string", "format": "date"},
        "documentationUrl": {"type": "string", "format": "uri"}
      }
    },
    "signatureAlgorithm": {
      "type": "string",
      "pattern": "^[a-z0-9]+-([a-z0-9]+-)?v[0-9]+$"
    },
    "signature": {
      "type": "string"
    }
  }
}
```

---

