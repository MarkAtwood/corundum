# How Corundum Works — Specification Book

The specification has been split into per-part files for easier navigation.
All content lives in [`docs/spec/`](spec/).

## Files

| File | Contents |
|------|----------|
| [00-preface.md](spec/00-preface.md) | Preface and design philosophy |
| [01-overview.md](spec/01-overview.md) | Part I — The Big Picture (Ch 1–3) |
| [02-comparison.md](spec/02-comparison.md) | Part II — Context and Comparison (Ch 4) |
| [03-identity.md](spec/03-identity.md) | Part III — Identity (Ch 5–8) |
| [04-content-storage.md](spec/04-content-storage.md) | Part IV — Content Storage (Ch 9–13) |
| [05-activity-types.md](spec/05-activity-types.md) | Part V — Activity Types and Extension System (Ch 14–16) |
| [06-operators.md](spec/06-operators.md) | Part VI — Operators (Ch 17–20) |
| [07-reply-protocol.md](spec/07-reply-protocol.md) | Part VII — The Reply Protocol (Ch 21–24) |
| [08-social-graph.md](spec/08-social-graph.md) | Part VIII — The Social Graph (Ch 25–26) |
| [09-curation.md](spec/09-curation.md) | Part IX — Curation (Ch 27–32) |
| [10-crypto.md](spec/10-crypto.md) | Part X — Cryptographic Foundations (Ch 33–35) |
| [11-event-streams.md](spec/11-event-streams.md) | Part XI — Event Streams (Ch 36) |
| [12-error-pagination.md](spec/12-error-pagination.md) | Part XII — Error Handling and Pagination (Ch 37–38) |
| [13-content-retention.md](spec/13-content-retention.md) | Part XIII — Content Retention Conflicts (Ch 39) |
| [14-out-of-scope.md](spec/14-out-of-scope.md) | Part XIV — What Corundum Doesn't Define (Ch 40) |
| [15-implementation-guide.md](spec/15-implementation-guide.md) | Part XV — Implementation Guidance (Ch 41–46) |
| [16-interop-streams.md](spec/16-interop-streams.md) | Part XVI — Inter-Operator Event Streams (Ch 47–52) |
| [appendices.md](spec/appendices.md) | Appendix A (Spec Index) and Appendix B (Normative References) |

## Quick Reference for Implementers

When implementing a specific component, read:

- **Identity / DID / IPNS**: `03-identity.md`
- **Archive structure / timeline entries**: `04-content-storage.md`
- **Activity types / ATDs / media**: `05-activity-types.md`
- **Operator manifest / inter-operator auth**: `06-operators.md`
- **Reply protocol**: `07-reply-protocol.md`
- **Follows / blocks / social graph**: `08-social-graph.md`
- **Curation feeds / content moderation**: `09-curation.md`
- **Canonical JSON / signing / cryptographic agility**: `10-crypto.md`
- **Event streams (WebSocket/SSE)**: `11-event-streams.md`
- **Error handling / pagination**: `12-error-pagination.md`
- **GDPR / content retention / deletion**: `13-content-retention.md`
- **Minimal implementation / common mistakes / test vectors**: `15-implementation-guide.md`
- **IPFS operational setup**: `15-implementation-guide.md` (Ch 46)

Always read `00-preface.md` for design philosophy and `appendices.md` for normative references.
