# A Corundum Client/Server API (Reference Implementation)

**This API is non-normative.** The Corundum specification (`docs/spec/`) defines only what operators say to each other; it deliberately does not specify a client/server API (spec Chapter 40). What follows is **the reference implementation's chosen client/server API**, a design other operators are free to adopt, change, or ignore. Nothing here overrides the specification. Where this document describes protocol behavior (identifiers, signing, the archive, reply rejection), the specification is authoritative and this document only projects it into an HTTP API.

This API is the interface between social media client applications and the Corundum operator they are homed on. Posting a status, reading a timeline, following an account, uploading media: every action such an app takes goes through this API. It is not the inter-operator protocol, which operators use to federate content and deliver replies.

## Files

| File | Description |
|------|-------------|
| `README.md` | This file. Index and overview. |
| `00-design.md` | Design principles: why Corundum diverges from Mastodon, identifiers and path encoding, pagination, error envelope and code registry. |
| `01-auth.md` | Authentication: OAuth 2.0 + PKCE flow, app registration, scope registry, token use, instance info endpoint. |
| `02-entities.md` | Entity reference: Account, Status, CurationLabel, SigningRecord (with the verification procedure), Notification, MediaAttachment, Relationship. |
| `03-statuses.md` | Status endpoints: post, edit, delete, fetch by activity id, boosts, favourites, reply context, signing record, self-custody publishing. |
| `04-timelines.md` | Timeline endpoints: home, public, hashtag, list, and the archive timeline (sequence-ordered). |
| `05-accounts.md` | Account endpoints: profile read/write, statuses, followers, following, lookup, search, archive summary. |
| `06-notifications.md` | Notification endpoints: list, get, clear, dismiss. Includes Corundum-specific types (reply rejection, account migration, curation). |
| `07-relationships.md` | Social graph endpoints: follow, block, mute, follow requests. Documents block vs. mute semantics. |
| `08-media.md` | Media upload: single-request and chunked (resumable). IPFS-backed storage. |
| `09-search.md` | Search endpoints: full-text search plus lookup by activity id and by IPNS name. |
| `10-identity-migration.md` | Identity and migration: DID, key custody, content-key rotation, DID updates, RootManifest, archive export, operator migration. |
| `11-curation.md` | Curation: subscribed curators, per-status labels, appeals, admin policy management. |
| `12-alternative-shapes.md` | Alternative API shapes: client-signed, GraphQL, Nostr-style relay, local-first/IPFS-direct, CQRS, AT Protocol XRPC, and how to combine them. |
| `13-mastodon-shim.md` | Mastodon compatibility shim: path layout, ID mapping, key custody limits, endpoint translation, streaming, and limitations. |
| `14-event-stream.md` | Event stream: real-time SSE updates (timelines, threads, notifications, curation) for the user's own client. Non-normative. |

## Mastodon Compatibility

This API is shaped like the Mastodon API where the models agree, but it is not the Mastodon API: accounts are identified by DID, statuses by activity id (a CID), and Corundum-specific features (signing transparency, key custody, curation labels, identity migration) are exposed directly. Existing Mastodon apps connect through the compatibility shim described in `13-mastodon-shim.md`, which serves the Mastodon API at `/api/v1/` and `/api/v2/` and translates to this API. Mastodon apps using the shim cannot use Corundum-native features, and users who hold their own content key cannot post through it. Apps that want full Corundum fidelity target this API, or any other operator-defined API that exposes the same capabilities.

## Quick Reference

The native API lives under `/api/corundum/v1/`. The Mastodon shim owns `/api/v1/` and `/api/v2/`. Nothing client-facing lives under `/corundum/`, which is the server-to-server protocol's prefix. One OAuth authorization server at `/oauth/` serves both.

| Endpoint Group | Path Prefix | Documentation |
|----------------|-------------|---------------|
| OAuth / Authentication | `/oauth/` | `01-auth.md` |
| App Registration | `/api/corundum/v1/apps` | `01-auth.md` |
| Instance Info | `/api/corundum/v1/instance` | `01-auth.md` |
| Statuses | `/api/corundum/v1/statuses/` | `03-statuses.md` |
| Self-custody publishing | `/api/corundum/v1/activities` | `03-statuses.md` |
| Timelines | `/api/corundum/v1/timelines/` | `04-timelines.md` |
| Accounts | `/api/corundum/v1/accounts/` | `05-accounts.md` |
| Notifications | `/api/corundum/v1/notifications/` | `06-notifications.md` |
| Follow/Block/Mute | `/api/corundum/v1/accounts/:id/{follow,block,mute}` | `07-relationships.md` |
| Media | `/api/corundum/v1/media/` | `08-media.md` |
| Search | `/api/corundum/v1/search` | `09-search.md` |
| Identity | `/api/corundum/v1/identity/` | `10-identity-migration.md` |
| Migration | `/api/corundum/v1/migration/` | `10-identity-migration.md` |
| Curation | `/api/corundum/v1/curation/`, `/api/corundum/v1/admin/curation/` | `11-curation.md` |
| Event stream | `/api/corundum/v1/streaming` | `14-event-stream.md` |
| Mastodon shim | `/api/v1/`, `/api/v2/` | `13-mastodon-shim.md` |
