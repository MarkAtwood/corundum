# DNS Names, Well-Known URIs, and Fixed Paths

**Status:** Non-normative analysis, 2026-10-18, against commit `024bdf5` (plus the uncommitted spec edits present in the working tree that day). It lists every DNS name and URL path Corundum claims, then the real conflicts and risks. The spec chapters are authoritative; where this note and a chapter disagree, the chapter wins and this note is stale.

## Registry

"Owner" is the party that publishes the name: **user** (a handle holder or DID controller), **operator**, or **curator**. "Normative" means `docs/spec/`; the client API (`docs/client-api/`) is non-normative.

| Name | Kind | Defined in | Purpose | Owner |
|---|---|---|---|---|
| `_corundum.<domain>` | DNS TXT, `"did=<DID>"` | `03-identity.md` Ch 8 | Domain handle to DID | user |
| `/.well-known/webfinger?resource=acct:<user>@<host>` | Well-known URI (RFC 7033) | `03-identity.md` Ch 8 | Account handle to DID, via a JRD link | operator |
| `https://corundum.example/ns/v1/did` | WebFinger link relation (extension URI) | `03-identity.md` Ch 8 | Marks the JRD link whose `href` is the DID | spec |
| `/.well-known/did.jsonl` | Well-known URI (did:webvh method) | did:webvh spec; used by `03-identity.md` Ch 5 | DID log for a host-level DID `did:webvh:<SCID>:<host>` | user |
| `/<path>/did.jsonl` | Path (did:webvh method) | did:webvh spec; example `users:alice` in `03-identity.md` Ch 5 | DID log for an operator-hosted DID; path chosen by the operator | operator (hosts), user (controls) |
| `/routing/v1/ipns/{name}` | Path (IPFS Delegated Routing V1) | `03-identity.md` Ch 5, `15-implementation-guide.md` | Fast-path IPNS record fetch, at the `operatorEndpoint` origin | operator |
| `/ipfs/{cid}` | Path (IPFS path gateway) | `05-activity-types.md` (example on a CDN host) | Media segment fetch by CID | operator or CDN |
| `/.well-known/corundum-operator` | Well-known URI | `06-operators.md` Ch 18-20 | Operator Manifest | operator |
| `/corundum/v1/replies/submit`, `/replies/batch` | Path | `06-operators.md` endpoint table, `07-reply-protocol.md` | Inter-operator reply submission | operator |
| `/corundum/v1/migration/notify` | Path | `06-operators.md` endpoint table | MigrationNotification hint | operator |
| `/corundum/v1/events`, `/events/snapshots/...` | Path | `16-interop-streams.md` Ch 47-52, `06-operators.md` table | Normative inter-operator event stream | operator |
| `/api/v1/corundum/streaming` | Path | `docs/client-api/14-event-stream.md` | Client event stream (formerly Ch 36) | operator |
| `/.well-known/corundum-curator` | Well-known URI | `09-curation.md` Feed Discovery | Authority Declaration | curator |
| `<feed_url>/head.jws`, `/heads/...`, `/log/...`, `/snapshots/...`, `/bloom.bin`, `/buckets.bin`, `/entries/...` | Paths relative to a curator-chosen base | `09-curation.md` | Static curation feed | curator |
| `/api/v1/...`, `/api/v2/media`, `/api/v2/search`, `/oauth/...` | Paths (Mastodon-shaped) | `docs/client-api/00-design.md` and later files | Native client API | operator |
| `/api/v1/corundum/...`, `/api/v1/admin/corundum/...` | Paths | `docs/client-api/08`, `09`, `11` | Corundum-only client endpoints | operator |
| `/api/v1/...`, `/api/v1/streaming`, `/oauth/...` | Paths (Mastodon API) | `docs/client-api/13-mastodon-shim.md` | Mastodon compatibility shim | operator |
| `/api/v0/...` | Path (Kubo RPC) | `15-implementation-guide.md` | IPFS node admin. Localhost only (15: "never expose it to the internet") | operator (internal) |

The current spec defines no SRV records and no other underscored DNS names.

## Checked and fine

**`_corundum` has one meaning.** The only `_corundum` record left in the spec is the domain-handle record in Ch 8. Operators are discovered by `/.well-known/corundum-operator`, by the DID document's `operatorEndpoint`, through directories, and through peer lists. No DNS record is involved. The old collision between handle TXT and operator-discovery TXT (old Issue 1) is gone. A domain can carry both kinds of handle: `alice.example` as a domain handle (TXT) and `acct:bob@alice.example` as an account handle (WebFinger). These don't collide, because `alsoKnownAs` keeps them apart (`dns:` versus `acct:`).

**WebFinger shared with Mastodon/ActivityPub.** RFC 7033 §4.4.4 lets a JRD carry any number of links, and clients ignore relations they don't recognize. A single JRD can therefore carry Mastodon's `{"rel":"self","type":"application/activity+json","href":...}` and Corundum's `{"rel":"https://corundum.example/ns/v1/did","href":"did:..."}` at the same time. Both kinds of client keep working. The coexistence limit is operational: one process answers `/.well-known/webfinger` for a host, and an `acct:` resource has one subject. If Mastodon and Corundum share a host, either one stack emits both links or a proxy merges them, and `acct:alice@host` has to mean the same person in both systems.

**did:webvh paths and operator paths.** Under the did:webvh method, `did:webvh:<SCID>:host` resolves to `https://host/.well-known/did.jsonl`, and a DID with path segments resolves to `https://host/<segments>/did.jsonl`. The method also puts optional `did-witness.json` and `whois.vp` files beside the log. None of these overlaps `corundum-operator`, `corundum-curator`, or `/corundum/v1/`. The Operator Manifest `id` is an HTTPS origin, not a DID, so it never claims `/.well-known/did.jsonl`. A host-level `did.jsonl` appears only when a user self-hosts a DID at their own domain. On a host shared with Mastodon, the operator-chosen path in the example (`/users/alice/did.jsonl`) sits under Mastodon's `/users/:username` routes. That needs a proxy rule, or a different path segment such as `dids:alice`.

**`/corundum/v1/` beside the IPFS paths.** `/corundum/v1/`, `/routing/v1/`, `/ipfs/`, and `/ipns/` are disjoint prefixes, so one origin can route each to a different backend. Ch 15 has the protocol server serve `/routing/v1/ipns/{name}` itself. An operator that instead forwards `/routing/v1/` to a Kubo gateway exposes the whole Delegated Routing API (providers and peers as well as IPNS), so the forward should be limited to `GET /routing/v1/ipns/`.

**Curation feeds.** Feed paths are relative to the curator's declared `feed_url`, so Corundum claims no fixed prefix there. The only fixed curator name is `/.well-known/corundum-curator`. A host can be both an operator and a curator without collision.

## Conflicts and risks

### 1. `operatorEndpoint` is a path, but the endpoint rules assume an origin

The DID document example (`03-identity.md:66`) has `operatorEndpoint: "https://birdsite.example/corundum/v1"`, described as "the base URL of the user's operator". Ch 19 says all inter-operator paths are "relative to the operator's `id` base URL", and `id` "MUST match the origin" (`06-operators.md:114, 299`). Ch 20 step 3 fetches `{endpoint}/.well-known/corundum-operator` (`06-operators.md:293`). Taken together, those rules yield `https://birdsite.example/corundum/v1/.well-known/corundum-operator`, which RFC 8615 §3 does not allow: well-known URIs live only at the origin root. They also yield `.../corundum/v1/corundum/v1/replies/submit`. Step 2 also still reads the endpoint from a RootManifest `operator` field, but under the identity decisions it comes from the DID document. **Fix:** make `operatorEndpoint` an HTTPS origin with no path, required to equal the manifest `id`. Endpoint paths then stay absolute (`/corundum/v1/...`), and the manifest is always at `<origin>/.well-known/corundum-operator`.

### 2. `/routing/v1/ipns/{name}` is required in prose but missing from the endpoint table

Ch 5 (`03-identity.md:31`) now places `GET /routing/v1/ipns/{name}` at the origin of `operatorEndpoint`, and Ch 15 tells operators to serve it. The Ch 19 table, which claims to be "the complete Corundum inter-operator protocol", still doesn't list it, so its requirement level (MVP or not) is undefined. **Fix:** add a row: no capability flag, no auth, with the level stated.

### 3. The domain-handle TXT record has no parsing rules

Ch 8 shows the record and nothing more. It doesn't say what happens when there are several TXT RRs at the name, when an RR doesn't start with `did=`, or when an RR is split into several character-strings. All of these come up in practice: a name can hold other TXT data, some providers split long strings, and a wildcard `*.alice.example TXT` record also answers for `_corundum.alice.example` when no explicit record exists (RFC 4592 §2.1.1, which uses closest-encloser matching). Long `did:webvh` DIDs (SCID plus host plus path) can approach the 255-octet character-string limit. **Fix (a constraint, not a mechanism):** join the character-strings within an RR; ignore RRs that don't start with `did=`; require exactly one `did=` RR, and treat zero or more than one as "no handle".

### 4. Native client API and Mastodon shim claim the same `/api/v1/` paths

`00-design.md:36` says native endpoints have "the same path" as Mastodon (`/api/v1/statuses/:id` and so on), with CIDs and IPNS names as IDs. The shim (`13-mastodon-shim.md:28`) serves `/api/v1/` on the same `:443` with integer IDs. Its diagram puts the native API at `/corundum/`, which neither matches the native API's documented paths nor stays clear of the inter-operator `/corundum/v1/` prefix. A request to `GET /api/v1/statuses/{id}` on one origin can't be both. The ID shapes are distinguishable, but the response entities differ. **Fix (non-normative):** on any one origin, `/api/v1/` is either the native API or the shim. The other goes on its own origin or port. Remove `/corundum/` from the shim diagram.

### 5. Placeholder namespace in a wire identifier

`https://corundum.example/ns/v1/did` is a real protocol constant, but `.example` is reserved (RFC 6761 §6.5) and can never be owned or dereferenced. Under RFC 8288 §2.1.2, extension relation types need no IANA registration, but they should be URIs their minter controls. **Fix:** before any implementation ships, replace the `corundum.example/ns/v1` namespace (used for both the JSON-LD context and this relation) with a domain the project controls. Changing it later breaks deployed resolvers.

### Leftover outside this note

`docs/client-api/10-identity-migration.md:37, 50` describes `did_document_url` as "typically `https://<domain>/.well-known/did.json`". That is the plain `did:web` location, and plain `did:web` is rejected. For `did:webvh` it should be the `did.jsonl` log URL.

## Resolved by removal

Issue 1 of the first draft of this rewrite (the client event stream and the interop stream both at `GET /corundum/v1/events`) was resolved during the 2026-10-18 edits: the client stream moved to `docs/client-api/14-event-stream.md` as `/api/v1/corundum/streaming`.

Old Issues 1-6 and 8 described text that the current spec no longer contains: the operator-discovery TXT record, `_corundum-caps`, `_corundum-verify`, the `_corundum._tcp` SRV record, duplicate manifest definitions in separate Auth and Manifest specs, `/.well-known/corundum/{name}`, `corundum-directory`, `corundum-namespace`, the mTLS `.pem` files, and the plain `did:web` `did.json` path. All of these were dropped along with the retired specs.

Old Issue 7 was also wrong on its own terms. `_corundum.*.birdsite.example` is not a DNS wildcard. Under RFC 4592 §2.1.1, `*` acts as a wildcard only as the leftmost label, and an asterisk anywhere else is a literal label. The old example would have matched nothing but the literal name `_corundum.*.birdsite.example`. One TXT record cannot serve per-subdomain handles. An operator that issues subdomain handles publishes one record per handle, or runs a DNS server that synthesizes them.

## IANA registrations worth doing

| Registry | Policy (checked 2026-10-18) | Entry | Notes |
|---|---|---|---|
| Well-Known URIs (RFC 8615) | Specification Required, designated expert | `corundum-operator`, `corundum-curator` | Neither is registered. The template asks for the URI suffix, change controller, specification reference, and status. A provisional entry is available for a non-IETF specification, as `nodeinfo` and `did.json` have done. A stable, publicly reachable spec URL is required. |
| Underscored and Globally Scoped DNS Node Names (RFC 8552) | Expert Review | `TXT` / `_corundum` | Not registered. Fields: RR type, node name, reference. Registering it prevents another protocol from claiming `_corundum` for something else. |
| Link Relation Types (RFC 8288) | Specification Required | none | The DID relation is an extension URI and needs no registration (RFC 8288 §2.1.2). Registering a short name such as `did` would be a cross-ecosystem effort beyond Corundum's scope. Issue 5 is the action item. |

`did.jsonl` is not in the Well-Known URIs registry. Registering it belongs to the did:webvh maintainers, not to Corundum.
