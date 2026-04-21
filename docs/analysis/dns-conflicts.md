# DNS and Well-Known Endpoint Conflicts

Open specification issues identified by cross-spec analysis. Each issue is independent; they can be resolved in any order.

---

## Issue 1: `_corundum.{domain}` TXT Record Collision (CRITICAL)

**Status: OPEN**

Two specs use the same DNS name pattern for different purposes with different schemas:

| Use | Record | Required Fields | Defined In |
|-----|--------|----------------|------------|
| Handle resolution | `_corundum.alice.birdsite.example.` | `v`, `did`, `ipns` | DID Identity §6.4.1 |
| Operator discovery | `_corundum.birdsite.example.` | `v`, `endpoint` | Discovery §4.2 |

Both use `v=corundum1`. There is no `type=` field or other explicit discriminator. A resolver can only tell them apart by which keys are present (`did+ipns` vs `endpoint+pubkey`). The specs never call this out.

**The breaking case:** If a handle is a bare domain (explicitly supported), and the operator domain is the same, then `_corundum.earl.example` must serve both purposes simultaneously. The specs provide no guidance.

**Proposed fix:** Rename to disambiguate:
- Operator discovery: `_corundum-op.{domain}`
- Handle resolution: `_corundum-id.{handle}`

**Scope of changes for `_corundum-op`** (Discovery Spec only):
- §4.2 TXT Records — normative definition (2 occurrences)
- §4.4 Resolution algorithm — `dns_lookup(f"_corundum.{domain}", "TXT")`
- §10 Handle Resolution Method Detection — same lookup
- §9.1 New Operator Bootstrap — example record
- Appendix B.2 DNS Configuration example

**Scope of changes for `_corundum-id`** (DID Identity Spec, ~15 edits; Discovery Spec, 2 edits):

*DID Identity Spec:*
- §6.4.1 TXT Record Format — location definition and examples
- §6.4.1 — Wildcard example `_corundum.*.birdsite.example.`
- §6.4.2 — `resolve_dns_handle()` lookup: `f"_corundum.{handle}"`
- §8.5 — Migration step prose
- §11.5.1 — DNS Security prose
- §14 — Example walkthrough
- Appendix B.3 — DNS Configuration
- Appendix D.1 — DNS Resolution Example (`dig TXT` command and result)

*Discovery Spec:*
- §4.3 Handle Resolution DNS Records — cross-reference example
- Appendix B.2 — user handle record line

*Protocol Overview:* Optional — prose only says "DNS TXT records", no prefix shown.

---

## Issue 2: `/.well-known/corundum-operator` Triple Definition

**Status: OPEN**

Three specs independently define this endpoint:

- **Auth Spec §3.1** — "Operators MUST publish their Operator Manifest at..." Full response requirements, HTTPS, redirect handling, ancillary files. Claims to be normative.
- **Manifest Spec §2** — Identical text. Also claims to be the normative definition.
- **Discovery Spec §3.1** — Correctly defers to [Corundum-Manifest] §2.

Auth and Manifest Spec both claim normative authority. If they ever diverge, implementers have no tiebreaker.

**Proposed fix:** Auth Spec should explicitly defer to Manifest Spec (as Discovery Spec does), dropping its own normative claim for this endpoint.

---

## Issue 3: `OperatorManifest` Schema Duplicated

**Status: OPEN**

The full JSON schema for `corundum:OperatorManifest` — including all field definitions, validation rules, and examples — appears in both Auth Spec and Manifest Spec. Field tables are largely identical but have minor presentation differences that could become substantive divergences.

**Proposed fix:** Single definition in Manifest Spec; Auth Spec cross-references it.

---

## Issue 4: Error Response Definitions Duplicated

**Status: OPEN**

All three specs (Auth, Manifest, Discovery) define error response behavior for `/.well-known/corundum-operator`, including the error envelope format and specific error codes.

**Proposed fix:** Define once in Manifest Spec; others cross-reference.

---

## Issue 5: `_corundum-caps.{domain}` TXT Record Underdefined

**Status: OPEN**

Discovery Spec §4.2 defines an optional overflow TXT record:

```
_corundum-caps.example.com. 300 IN TXT "replies-v1,curation-v1,batch-submit,did-identity"
```

No spec defines:
- How the value is parsed
- How it relates to the `caps=` field in the primary `_corundum` TXT record
- Which takes priority if they conflict
- Whether absence of `_corundum-caps` is different from an empty one

The appendix example shows different capability lists in `_corundum` and `_corundum-caps` for the same domain with no normative explanation.

**Note:** If Issue 1 is resolved by renaming to `_corundum-op`, consider renaming this to `_corundum-op-caps` for consistency.

---

## Issue 6: `_corundum-verify.{domain}` TXT Record Spec-by-Example Only

**Status: OPEN**

Directory verification via DNS TXT appears in a JSON response example and a DNS config example, but there is no normative section defining:
- Record format
- TTL expectations
- Lifecycle (when to create, when to delete)
- Security properties

---

## Issue 7: Wildcard TXT Record Interaction Underdefined

**Status: OPEN**

DID Identity Spec shows wildcard DNS at `_corundum.*.birdsite.example`. DNS wildcards only match when there is no explicit record, so this works correctly for `_corundum.bob.birdsite.example` (no explicit record → wildcard matches). But the spec never states this explicitly.

Implementers unfamiliar with DNS wildcard semantics may not know that a per-user record at `_corundum.alice.birdsite.example` silently takes precedence over the wildcard.

**Proposed fix:** Add a normative note in DID Identity §6.4 explicitly stating that per-user records override wildcards.

---

## Issue 8: `/.well-known/corundum/{name}` Has No Reservation List

**Status: OPEN**

The `/.well-known/corundum/{name}` wildcard path (DID Identity Spec) could collide with future well-known paths if a handle matches a reserved name (e.g., `operator`, `directory`, `namespace`). No reservation list exists.

**Proposed fix:** Define a list of reserved handles in DID Identity Spec or a shared appendix.

---

## Missing: Consolidated DNS and Well-Known Registry

No single document provides a complete registry of all DNS names and `.well-known` paths the protocol uses.

**DNS records (extracted):**

| DNS Name Pattern | Type | Purpose | Defined In |
|-----------------|------|---------|-----------|
| `_corundum._tcp.{domain}` | SRV | Operator service discovery | Discovery §4.1 |
| `_corundum.{domain}` | TXT | Operator identity/capability | Discovery §4.2 |
| `_corundum.{handle}` | TXT | Handle → DID+IPNS resolution | DID Identity §6.4 |
| `_corundum-caps.{domain}` | TXT | Extended capabilities | Discovery §4.2 |
| `_corundum-verify.{domain}` | TXT | Directory verification | Discovery §5.3 (example only) |
| `_corundum.*.{domain}` | TXT | Wildcard operator redirect | DID Identity §6.4 |

**`.well-known` paths (extracted):**

| Path | Spec | Purpose |
|------|------|---------|
| `/.well-known/corundum-operator` | Manifest / Auth / Discovery | Operator manifest |
| `/.well-known/corundum-operator.pem` | Manifest / Auth | mTLS cert |
| `/.well-known/corundum-ca.pem` | Manifest / Auth | mTLS CA cert |
| `/.well-known/corundum-directory` | Discovery | Directory metadata |
| `/.well-known/corundum-namespace` | Activity Type Defs | Namespace declaration |
| `/.well-known/corundum/{name}` | DID Identity | Handle resolution |
| `/.well-known/did.json` | DID Identity (did:web) | DID document |

**Proposed fix:** Add a "DNS and Well-Known Registry" appendix to the Discovery Spec (or as a standalone reference doc) that is the single authoritative source for all of the above, and resolves Issue 1 in its normative text.
