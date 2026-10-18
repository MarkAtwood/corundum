## Part X: Cryptographic Foundations

### Chapter 33: Signed Bytes and Content Identifiers

**Corundum never re-serializes a signed or content-addressed object.** The bytes an author produces are the bytes that are hashed, stored, transmitted, and verified. A verifier checks a signature over the bytes it received, never over bytes it rebuilt from a parsed object.

Canonicalization schemes exist so that two parties can independently rebuild identical bytes from the same logical object. Corundum never needs to do that: every object is stored in IPFS and moved between operators as bytes. Signing the exact bytes removes a whole class of interoperability failures (key ordering, number formatting, string escaping, Unicode normalization) instead of specifying a fix for each one.

Earlier drafts of this specification signed a Canonical JSON form (RFC 8785 with NFKC normalization, timestamp rewriting, and null omission). It was removed for two reasons. First, NFKC folds distinct text together (`ﬁ` and `fi`, `x²` and `x2`, full-width and ASCII letters), so two different stored objects could share one identifier and one valid signature. Second, once signatures cover exact bytes, the canonical form has no remaining job.

**Rules for every Corundum JSON object:**

1. The object MUST be valid I-JSON (RFC 7493): UTF-8 with no byte order mark, no duplicate member names, and numbers representable as IEEE 754 double-precision values.
2. Producers SHOULD write text in Unicode Normalization Form C. Verifiers MUST NOT normalize anything; they hash and verify the bytes as received.
3. Implementations MUST keep and forward the original bytes of any object they store or relay. An object that has been parsed and re-encoded is a different object with a different identifier, and its signatures will not verify.

**Content identifiers.** The identifier of a content-addressed object is a CIDv1 over its exact bytes, with the `raw` codec (`0x55`) and a `sha2-256` multihash (`0x12`). In JSON it is written as a lowercase base32 multibase string, which always begins `bafkrei`. Because the CID is computed over the stored bytes, an object's identifier and its IPFS storage CID are the same value: anyone can fetch the object from IPFS by its identifier and check it by hashing what they receive.

A content-addressed object MUST NOT exceed 1,048,576 bytes, so that it is stored as a single IPFS block and its CID does not depend on any chunking parameters. Media and other large payloads are carried by reference (Chapter 15).

A receiver MUST compute the CID of received bytes and compare it with the expected identifier before it uses the object for any trust decision.

An identifier names one object, not a piece of text. Two authors who post identical text produce different objects (the author and timestamp differ) and therefore different identifiers. Curation that needs to match the same text or media across authors uses the content hash types of Chapter 28, which are computed over the text or media itself.

### Chapter 34: Signing and Verification

**Why Ed25519.** Every cryptographic signature scheme involves tradeoffs among key size, signature size, signing speed, verification speed, and security properties. Ed25519 was chosen because it wins on most of these simultaneously.

RSA-2048 produces 256-byte signatures and requires ~2048-byte public keys. An Ed25519 public key is 32 bytes; an Ed25519 signature is 64 bytes. On a server processing thousands of signature verifications per second — validating incoming inter-operator messages, checking reply submissions, verifying curation entries — this compactness matters both for wire efficiency and for in-memory cache density.

ECDSA (including ECDSA P-256, the most common alternative) has a critical security property that makes it dangerous in practice: each ECDSA signature requires a fresh random nonce. If the nonce is ever reused, or if it is even slightly biased by a weak random number generator, the private key can be recovered by an attacker from two signatures. This is not a theoretical concern — Sony's PlayStation 3 was broken this way, and numerous Bitcoin wallets have been drained by the same attack on secp256k1 ECDSA. Ed25519 is a deterministic scheme: the nonce is derived from the message and the private key using a cryptographic hash. There is no per-signature randomness requirement, so a bad RNG during signing cannot compromise key security. For a federated protocol running on diverse server infrastructure, this property is essential.

Ed25519 also has a designed resistance to timing side-channels: the reference implementation (and all standard implementations) run in constant time regardless of key or message values. RSA and many ECDSA implementations have historically leaked key bits through timing variation; Ed25519's design closes this attack surface.

**Signature format.** Every Corundum signature is a JSON Web Signature (RFC 7515) in the General JSON Serialization (RFC 7515 §7.2.1), so that one object can carry several signatures. There are two forms:

- **Detached.** Used for objects that are referenced by identifier and whose identifier must never change: activities (Chapter 11). The JWS omits the payload (RFC 7515 Appendix F) and uses the unencoded payload option (RFC 7797, `"b64": false`). The payload is the object's stored bytes. The JWS is stored as its own object, the SigningRecord (Chapter 12). Adding a signature later produces a new SigningRecord and leaves the activity and its identifier unchanged.
- **Attached.** Used for objects that are their own envelope and are replaced rather than referenced, such as the RootManifest (Chapter 9). The stored object is the JWS itself, with the object's bytes base64url-encoded in the `payload` member. Its identifier is the CID of the JWS bytes.

For both forms, the signing input is defined by RFC 7515 §5.1 (attached) or RFC 7797 §3 (detached): the ASCII bytes of the base64url-encoded protected header, a period (`.`), and then the payload (base64url-encoded for attached, raw bytes for detached). The signature is computed over that input directly; it is not hashed first. All base64url values are unpadded, per RFC 7515.

**Protected header.** Each signature has a protected header containing exactly these parameters, and no unprotected `header` member:

| Parameter | Value |
|---|---|
| `alg` | An algorithm from the registry in Chapter 36, for example `"Ed25519"`. |
| `kid` | The signing key. For a user's Ed25519 content key, its IPNS name (`k51…`). For any other user key, its identifier in the user's DID document (Chapter 6). For an operator key, its key identifier in the Operator Manifest (Chapter 18). For a curator key, its `key_id` in the curator's Authority Declaration (Chapter 30). |
| `corundumType` | The type of the signed object, for example `"Activity"` or `"RootManifest"`. |
| `crit` | `["b64", "corundumType"]` for detached signatures; `["corundumType"]` for attached. |
| `b64` | `false`. Present only in detached signatures. |

Verifiers MUST reject a signature whose protected header contains any other parameter, contains an unprotected `header` member, or names a `corundumType` other than the one expected where the object was found. The type check is domain separation: a signature over one kind of object can never be presented as a signature over another, even though the same key signs both.

An Ed25519 IPNS name embeds the public key itself (as an identity multihash), so a verifier obtains the Ed25519 public key directly from `kid`. Whether that key is authorized to sign for the identity is a separate question, answered below.

**Ed25519 verification profile.** Operators must agree on whether every signature is valid; if two operators disagree, they build different reply trees from the same submissions. Ed25519 libraries disagree on edge cases unless told exactly which checks to make. For `alg` `"Ed25519"`, signers use pure Ed25519 (RFC 8032 §5.1, not Ed25519ph or Ed25519ctx), and verifiers MUST:

1. Reject the signature if the scalar `S` is not less than the group order `L`.
2. Reject the signature if the encoding of the public key `A` or of the point `R` is not canonical (an encoded `y` coordinate that is not less than the field prime `p`).
3. Reject the signature if `A` or `R` is a point of small order.
4. Accept only if `[S]B = R + [k]A` (the cofactorless equation of RFC 8032 §5.1.7).

Many libraries' default verify functions do not make all of these checks. Implementers must confirm that the function they call does.

**Which keys may sign.** A key in `kid` is authorized to sign for a user when the user's DID document lists it as a Corundum content-signing key (Chapter 6). The user is the identity the signed object names as its author: `attributedTo` for an activity, or the identity block of a RootManifest. For an operator, `kid` must name a key in the operator's manifest whose status permits signing (Chapter 18).

**Historical content is authenticated by inclusion, not by timestamps.** Keys are rotated and sometimes compromised. A rule that accepts an old key for signatures dated before its rotation lets anyone who holds a compromised old key forge content by backdating it. Corundum does not use the signer's own timestamps for this decision:

- An activity that is in the user's archive is authentic if it is reachable from the user's current, validly signed RootManifest (Chapter 9). The archive tree never changes once written, and the current manifest commits to all of it, so the current keys vouch for everything already published. Old content does not need to be re-signed when keys change, and a signature by a retired key needs no validity window.
- An activity that is not yet in an archive (for example, one arriving in a reply submission) is authentic only if it is signed by keys that are authorized now.

Because the archive tree never changes, history cannot be rewritten without changing the CID of an epoch that already exists. A verifier that has seen an epoch's CID before MUST treat a RootManifest that commits to a different CID for the same epoch as evidence that the signing key is compromised, and MUST NOT accept it. Operators that follow a user therefore detect an attempt to rewrite that user's history even if it is made with the current key.

This rule also defeats a hostile former operator. After a user rotates their content key, anything the old operator signs with the old key is neither in an archive reachable from a manifest the user's current key signed, nor signed by a currently authorized key.

**Multiple signatures and downgrade.** A verifier MUST require one valid signature for every key in the signer's current required set, and MUST reject the object if any is missing or invalid. For a user, the required set is every content-signing key the user's DID document currently lists. Signatures by keys outside the required set are ignored. The required set comes from the DID document, which is changed only by the user's update keys (Chapter 6), not by any content key. An attacker who breaks one signature algorithm therefore cannot remove the user's other keys and strip their signatures. Chapter 35 explains how this supports moving to new algorithms.

**Verifying an activity.** Given an activity's bytes, its expected identifier, and its SigningRecord:

1. Compute the CID of the bytes (Chapter 33) and compare it with the expected identifier.
2. For each signature in the SigningRecord, decode the protected header and check it as described above, with `corundumType` `"Activity"`.
3. Build the signing input from the protected header and the activity bytes, and verify the signature with the key named by `kid` under the profile for its `alg`.
4. Resolve the author's DID document and determine the required set.
5. If the activity is in the author's archive, confirm it is reachable from the current RootManifest; otherwise, confirm that every key in the required set produced a valid signature.

**Verification when the manifest is unavailable.** If the verifier cannot fetch what it needs — the operator is down, the IPNS resolution times out, the DID document is unreachable — the signature cannot be verified. The correct response is to mark the signature status as "unverified" (or "deferred"), not to accept or reject the content. Treating unavailability as rejection would let an attacker take down an operator's manifest to suppress their content. Treating unavailability as acceptance would let an attacker present unverifiable content as trusted. Deferral is the only sound policy: retry when the manifest becomes available.

**Future timestamps.** If an activity's `published` time is in the future, the verifier should allow a tolerance of up to 5 minutes to account for clock differences between operators running on different infrastructure. An activity timestamped more than 5 minutes in the future is likely a clock misconfiguration and should be rejected with error code `TIMESTAMP_SKEW`. This tolerance applies only to the verification step; operators should log and alert on large clock skews in their own infrastructure.

### Chapter 35: Cryptographic Agility

The specification explicitly plans for the eventual failure of its own algorithms. Ed25519, currently considered strong, will eventually be broken, most likely by quantum computers running Shor's algorithm.

Algorithm identifiers are not invented by Corundum. Signature algorithms are named by their JOSE `alg` values (the IANA JSON Web Signature and Encryption Algorithms registry). Hash algorithms are named by their multihash codes inside CIDs. Chapter 36 lists which of these Corundum accepts.

**Adding an algorithm.** A user adds a key for the new algorithm to their DID document and signs with both keys from then on. Each JWS carries one entry in its `signatures` array per key. A verifier that implements both algorithms checks both. Because the new key is now in the user's required set (Chapter 34), a verifier rejects any new object that lacks the new signature, so an attacker cannot strip it.

**Old content does not need re-signing.** Historical content is authenticated by inclusion: it is authentic if the current RootManifest reaches it (Chapter 34). The RootManifest is signed with every current key each time it is published, so a single new manifest signed with a post-quantum key extends that protection to the whole archive. Re-signing individual old activities is permitted but never required. A user who does re-sign one publishes a new SigningRecord containing all of its signatures; the activity and its identifier are unchanged, and the archive tree is not rewritten (Chapter 12).

**No flag day.** Adoption is gradual and per user and per operator. A verifier starts requiring a new algorithm from a signer when that signer lists a key for it. The ecosystem migrates as signers add keys, and at no point is a new key listed but not enforced.

### Chapter 36: Algorithm Registry

This registry lists every algorithm Corundum accepts. **An algorithm that is not listed here MUST be rejected.** There is therefore no separate list of prohibited algorithms: MD5, SHA-1, RSA, DSA, and every other unlisted algorithm are rejected because they are not listed.

#### Signature algorithms

| `alg` | Algorithm | Specification | Status |
|---|---|---|---|
| `Ed25519` | Pure Ed25519, with the verification profile of Chapter 34 | RFC 8032, RFC 9864 | REQUIRED |
| `ML-DSA-65` | ML-DSA at security category 3 | FIPS 204; draft-ietf-cose-dilithium | PROVISIONAL |

`Ed25519` is the fully specified JOSE name from RFC 9864. The older polymorphic name `EdDSA` (RFC 8037) is deprecated by RFC 9864 and is not accepted.

`ML-DSA-65` is PROVISIONAL because its JOSE registration has not yet been published as an RFC. Verifiers MAY implement it. Users MUST NOT list an ML-DSA-65 key among their content-signing keys until this registry marks it REQUIRED, because every listed key is in the required set (Chapter 34), and a verifier that cannot check a required signature must reject the object.

#### Hash algorithms

| Multihash | Algorithm | Specification | Status |
|---|---|---|---|
| `sha2-256` (`0x12`) | SHA-256 | FIPS 180-4 | REQUIRED |

SHA-256 is the only hash used in Corundum CIDs. A second hash would give the same object two identifiers.

#### Status values

| Status | Signers | Verifiers |
|---|---|---|
| REQUIRED | MAY use | MUST implement |
| PROVISIONAL | MUST NOT put in a required set | MAY implement |
| DEPRECATED | MUST NOT use for new signatures | MUST still accept |
| REMOVED | MUST NOT use | MUST reject |

#### Changing the registry

Changes to this registry are revisions of this specification; there is no separately signed declaration format. An algorithm moves from REQUIRED to DEPRECATED when a replacement is REQUIRED, and from DEPRECATED to REMOVED no sooner than 36 months later. When an algorithm suffers a practical break, it moves directly to REMOVED.

Removing a signature algorithm does not break the archive. Historical content is authenticated by inclusion (Chapter 34), so it stays authentic as long as the current RootManifest is signed with an algorithm that is still accepted.
