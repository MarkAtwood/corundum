# Corundum

A protocol and reference implementation for federated social media that gives users portable identity, permanent content, and real moderation — without requiring trust in any single platform.

Named for the mineral basis of sapphire. The name comes from the original Bluesky proposal era; when Bluesky chose a different architecture (AT Protocol), this specification continued independently.

---

## What Corundum Is

Corundum specifies the **inter-operator backbone** of a federated social network: the data structures, wire formats, authentication mechanisms, and coordination protocols that let independently operated servers exchange content reliably and verifiably.

It deliberately leaves unspecified: client/server APIs, business models, recommendation algorithms, and client-side presentation. Those are policy decisions for operators, not protocol decisions for a spec.

### The core problem it solves

Every major social platform is a silo. Your identity, content, and social graph are rows in their database. When they shut down (Google+), kill a product (Vine), or change ownership (Twitter/X), you lose everything with no recourse and no portability.

Corundum separates four concerns that existing platforms conflate:

1. **Identity** — a DID that only keys you hold can change, not an account in their database
2. **Content storage** — IPFS-addressed by content hash, independent of any server
3. **Service provision** — operators who host you, but can't hold your data hostage
4. **Content moderation** — curators who publish signed judgments; operators who enforce them

When these layers are independent, moving operators is like switching ISPs: your phone number (identity), your files (content), and your contacts (social graph) all come with you.

---

## Repository Contents

```
docs/
  corundum-book.md              ← start here: index and quick-reference
  spec/
    00-preface.md               design philosophy, BCP 14 conventions
    01-overview.md              Part I    — The Big Picture
    02-comparison.md            Part II   — vs. ActivityPub, AT Protocol, Nostr, SSB
    03-identity.md              Part III  — Three-layer identity (Handles / DID / IPNS)
    04-content-storage.md       Part IV   — Immutable archive, StateMap and ReplyMap, edits and deletes
    05-activity-types.md        Part V    — ATD extension system, content references, media
    06-operators.md             Part VI   — Operator manifests, inter-operator auth (RFC 9421)
    07-reply-protocol.md        Part VII  — Reply submission, validation, reply trees, block enforcement
    08-social-graph.md          Part VIII — Follows, blocks, mutes; encrypted portable lists
    09-curation.md              Part IX   — Curation feeds, hash types, authority declarations
    10-crypto.md                Part X    — Signed bytes, JWS/Ed25519, algorithm registry
    11-error-pagination.md      Part XI   — Error envelope, cursor pagination
    12-content-retention.md     Part XII  — GDPR, deletion, legal holds
    13-out-of-scope.md          Part XIII — Intentional silences
    14-implementation-guide.md  Part XIV  — Minimal impl, common mistakes, test vectors, IPFS setup
    15-interop-streams.md       Part XV   — Inter-operator event streams
    appendices.md               Normative references
  client-api/                   Non-normative reference client API and Mastodon shim
  analysis/                     Non-normative analyses (DNS and well-known names)
tools/
  gen-test-vectors.py           Regenerates the Chapter 45 test vectors
```

The Rust implementation will live in `src/` once started.

---

## The Protocol in 60 Seconds

**Identity**: A user is a W3C DID (`did:webvh` by default), changed only by update keys the user holds. The DID document names the user's current IPNS name, which is both the Ed25519 key that signs their content and the pointer to their RootManifest. By default the operator holds that content key; users can hold it themselves instead. Handles look like email addresses (`alice@birdsite.example`, resolved with WebFinger) or are domains the user owns (`alice.example`, resolved with DNS), and are verified in both directions against the DID.

**Content**: Posts are ActivityStreams 2.0 objects stored unsigned in IPFS, addressed by the CID of their exact stored bytes. A separate `SigningRecord` object establishes authorship. The user's timeline is a two-level Merkle archive (epochs → ArchiveIndex) with O(1) lookup by sequence number.

**Operators**: Any HTTPS server that publishes an Operator Manifest at `/.well-known/corundum-operator`, runs an IPFS node, and speaks the protocol. No registration, no prior relationship needed. Operators authenticate to each other via HTTP Message Signatures (RFC 9421).

**Replies**: Federated through a defined protocol — Bob's operator submits to Alice's operator, which validates authorship, checks block lists and curation feeds, and either accepts (linking the reply into Alice's reply tree) or rejects with a reason code.

**Moderation**: Curators publish signed feeds of content-hash-based judgments. Operators subscribe independently and apply their own policies. No central enforcement authority.

---

## Specification Status

The specification is **complete and stable** for the core protocol. All major design decisions have been made and written down, including:

- Detached signatures (activities stored unsigned; CID stability + resignature support)
- DID as canonical user identifier (IPNS name is the current operational key)
- Migration by DID update (only the user's update key can move them; the old operator cannot block it)
- Two-level ArchiveIndex (O(1) lookups, dropped redundant hash chain)
- Downgrade attack prevention (require all signatures the sender's manifest declares)
- Reply tree portability (first-class IPFS objects; data export as fallback)

See [`docs/spec/00-preface.md`](docs/spec/00-preface.md) for design philosophy and [`docs/corundum-book.md`](docs/corundum-book.md) for the full index.

---

## Rust Implementation

The reference implementation will be written in Rust. This repository will contain it alongside the spec.

**Planned crate dependencies:**

| Purpose | Crate |
|---------|-------|
| Ed25519 signing | `ed25519-dalek` |
| SHA-256 | `sha2` |
| CID computation | `cid` |
| Multihash | `multihash` |
| Multibase encoding | `multibase` |
| JSON serialization | `serde_json` |
| HTTP server | `axum` |
| HTTP client (Kubo API) | `reqwest` |
| SQLite | `rusqlite` |

**IPFS**: Kubo (go-ipfs) via its localhost HTTP API. No full IPLD framework dependency — just a thin `reqwest`-based wrapper around the Kubo API endpoints.

**MVP scope** (first working operator):
- Detached JWS signing over stored bytes (RFC 7515, RFC 7797) with test vectors
- Ed25519 key generation, signing, verification
- IPFS object add/get/pin via Kubo HTTP API
- IPNS publish/resolve
- RootManifest creation and signing
- Timeline entries, epochs, and ArchiveIndex
- Operator Manifest endpoint
- HTTP Message Signatures (RFC 9421)
- Reply submission endpoint (inbound)
- Reply submission client (outbound)
- Standard error envelope and cursor pagination

---

## Design Principles

From the preface (Gall's Law applies):

> A complex system designed from scratch never works and cannot be made to work.

The response: ask at every decision, *what is the minimum standard that enables federation?* If a detail can vary between operators without breaking interoperability, it should not be specified. The protocol is a narrow waist, not a corset.

This shows up directly in scope decisions: client/server APIs are unspecified by design, business models are unspecified by design, recommendation algorithms are unspecified by design. The spec covers only what two operators must agree on to exchange content.

---

## Normative References

- RFC 7493 — I-JSON
- RFC 7515 — JSON Web Signature
- RFC 7797 — JWS Unencoded Payload Option
- RFC 9864 — Fully-Specified Algorithms for JOSE (`Ed25519`)
- RFC 9421 — HTTP Message Signatures
- RFC 8032 — Ed25519
- FIPS 180-4 — SHA-256
- W3C DID Core
- W3C ActivityStreams 2.0
- IPFS / IPNS / IPLD specifications
