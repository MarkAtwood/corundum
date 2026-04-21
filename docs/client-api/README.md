# Corundum Client/Server API

The Corundum client/server API is the interface between social media client applications and the Corundum operator they are homed on. When a user installs a Corundum app and connects it to their operator, every action the app takes — posting a status, reading a timeline, following another account, uploading media — goes through this API. This is not the inter-operator protocol (the protocol by which operators communicate with each other to federate content and deliver replies); that is documented separately in the operator protocol specification. This API is scoped entirely to the relationship between an app and the single operator that app is authenticated against.

## Files

| File | Description |
|------|-------------|
| `README.md` | This file. Index and overview. |
| `00-design.md` | Design principles: why Corundum diverges from Mastodon, comparison table, pagination model, error envelope. |
| `01-auth.md` | Authentication: OAuth 2.0 + PKCE flow, app registration, scopes, token use, instance info endpoint. |
| `02-entities.md` | Entity reference: Account, Status, CurationLabel, SigningRecord, Notification, MediaAttachment, Relationship. |
| `03-statuses.md` | Status endpoints: post, edit, delete, fetch by CID, boosts, favourites, reply context, signing record, curation. |
| `04-timelines.md` | Timeline endpoints: home, public, hashtag, list, and Corundum archive timeline (IPFS-backed, sequence-ordered). |
| `05-accounts.md` | Account endpoints: profile read/write, statuses, followers, following, lookup, search, archive index. |
| `06-notifications.md` | Notification endpoints: list, get, clear, dismiss. Includes Corundum-specific types (block enforcement, migration, curation). |
| `07-relationships.md` | Social graph endpoints: follow, block, mute, follow requests. Documents block vs. mute semantics. |
| `08-media.md` | Media upload: sync, async, and chunked (Corundum extension). IPFS-backed storage. |
| `09-search.md` | Search endpoints: full-text search plus Corundum-specific lookup by CID and by IPNS name. |
| `10-identity-migration.md` | Identity and migration: DID, keys, key rotation, RootManifest, archive export, operator migration (cooperative and hostile). |
| `11-curation.md` | Curation: subscribed curator feeds, per-content label lookup, appeal flow, admin policy management. |

## Mastodon Compatibility

Apps written for the Mastodon API may work against a compatibility shim built on top of this API. Such a shim is not part of the Corundum specification; it is an optional layer that operators may choose to provide. This document set describes the **native Corundum API**, which has full fidelity with the protocol: content is addressed by CID, accounts are identified by IPNS name, and Corundum-specific features (signing transparency, curation labels, identity migration) are available directly rather than being omitted or approximated.

Mastodon-compatible client apps that work only against a compatibility shim will not be able to use any Corundum-native features. Native Corundum client apps should target this API directly.

## Quick Reference

| Endpoint Group | Path Prefix | Documentation |
|----------------|-------------|---------------|
| OAuth / Authentication | `/oauth/` | `01-auth.md` |
| App Registration | `/api/v1/apps` | `01-auth.md` |
| Instance Info | `/api/v1/instance` | `01-auth.md` |
| Statuses | `/api/v1/statuses/` | `03-statuses.md` |
| Timelines | `/api/v1/timelines/` | `04-timelines.md` |
| Accounts | `/api/v1/accounts/` | `05-accounts.md` |
| Notifications | `/api/v1/notifications/` | `06-notifications.md` |
| Follow/Block/Mute | `/api/v1/accounts/:id/{follow,block,mute}` | `07-relationships.md` |
| Media | `/api/v1/media/`, `/api/v2/media/` | `08-media.md` |
| Search | `/api/v2/search` | `09-search.md` |
| Identity | `/api/v1/identity/` | `10-identity-migration.md` |
| Migration | `/api/v1/migration/` | `10-identity-migration.md` |
| Curation | `/api/v1/corundum/curators/`, `/api/v1/corundum/curation/` | `11-curation.md` |
| CID/IPNS Lookup | `/api/v1/corundum/search/` | `09-search.md` |
| Signing Record | `/api/v1/statuses/:id/signing_record` | `03-statuses.md` |
| Chunked Media | `/api/v1/corundum/media/chunked/` | `08-media.md` |
