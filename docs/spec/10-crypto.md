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

The **Algorithm Sunset Registry** tracks the lifecycle:

- **REQUIRED**: Ed25519 (signatures), SHA-256 (hashes). Must be supported.
- **OPTIONAL**: ECDSA P-256, secp256k1, Dilithium, SPHINCS+, FALCON. Supported but not required.
- **SUNSET**: Deprecated with a timeline; implementations SHOULD warn on use; implementations MUST reject after sunset date.
- **PROHIBITED**: Reject immediately. Currently: MD5, MD4, SHA-1, RSA-1024, DSA.

---

