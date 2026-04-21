## Appendix A: Specification Document Index

The complete protocol is specified across these documents:

| Document | What It Defines |
|----------|-----------------|
| Canonical Serialization Spec | Deterministic JSON/CBOR serialization, signing, verification, content hashing |
| DID Identity Spec | DID documents, supported methods, handle resolution, key rotation, recovery |
| Timeline Merkle Tree Spec | RootManifest, chunks, epochs, entries, tombstones, migration audit trail |
| Activity Types Spec | Standard activity types (Note, Article, Image, etc.) |
| Extensible Activity Types Spec | ATD system, content modes, reply types, reactions, type registry |
| Reply Protocol Spec | Inter-operator reply submission, validation, acceptance, rejection, thread management |
| Social Graph Spec | Follows, blocks, mutes, Bloom filters, cross-operator synchronization |
| Curation Feed Spec | Authority declarations, curation entries, hash types, reason taxonomy |
| Static Curation Hosting Spec | S3/CDN-compatible static hosting for curation feeds |
| Operator Authentication Spec | HTTP Message Signatures, trust levels, key management |
| Operator Manifest Spec | `/.well-known/corundum-operator` schema and semantics |
| Operator Discovery Spec | How operators find each other |
| Operator Best Practices | Non-normative operational guidance |
| Large Media Handling Spec | MediaManifest, chunked storage, resumable uploads, adaptive streaming |
| Event Stream Spec | WebSocket/SSE real-time events |
| Pagination Spec | Cursor-based pagination envelope |
| Error Response Spec | Standard error envelope and error codes |
| Algorithm Sunset Registry | Cryptographic algorithm lifecycle |
| Content Retention Guide | Conflict resolution for retention/deletion |
| Language Tagging Guide | Language metadata best practices |
| Timestamp Precision Guide | RFC 3339 timestamp rules |
| Consolidated Bibliography | All normative and informative references |

## Appendix B: Normative Standards Referenced

The protocol builds on:

- **IPFS/IPNS/IPLD**: Content-addressed storage, naming, and linked data
- **W3C DIDs**: Decentralized Identifiers
- **W3C ActivityStreams 2.0**: Social activity data model
- **RFC 8032**: Ed25519 signatures
- **RFC 8785**: JSON Canonicalization Scheme
- **RFC 9421**: HTTP Message Signatures
- **RFC 3339**: Timestamps
- **FIPS 180-4**: SHA-256
- **FIPS 204/205/206**: Post-quantum algorithms (Dilithium, SPHINCS+, FALCON)
- **RFC 8949**: CBOR
- **RFC 9457**: Problem Details for HTTP APIs

---

*End of book.*
