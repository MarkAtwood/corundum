# Entity Definitions

This document defines the JSON entity shapes returned by the Corundum client API. Each entity is described with a complete example and field-by-field explanation. Where Corundum extends a Mastodon-shaped entity, the extension fields are grouped under a `corundum` key so that Mastodon-compatible clients that ignore unknown object keys continue to work correctly.

---

## Account

An Account entity represents a user identity. The `id` field is the user's IPNS name (base36lower encoding), which is the hash of their Ed25519 public key. This is the stable operational identifier for the user — not a database-assigned integer or UUID.

```json
{
  "id": "k51qzi5uqu5dlvj2baxnqndepeb86cbk3ng6bn9tx0dv7azvq7rjz47q2",
  "username": "alice",
  "acct": "alice@social.example",
  "display_name": "Alice Liddell",
  "locked": false,
  "created_at": "2024-01-15T00:00:00.000Z",
  "note": "<p>Profile bio</p>",
  "url": "https://social.example/@alice",
  "avatar": "https://social.example/avatars/alice.jpg",
  "header": "https://social.example/headers/alice.jpg",
  "followers_count": 142,
  "following_count": 38,
  "statuses_count": 891,
  "corundum": {
    "ipns_name": "k51qzi5uqu5dlvj2baxnqndepeb86cbk3ng6bn9tx0dv7azvq7rjz47q2",
    "did": "did:web:alice.example",
    "operator_endpoint": "https://social.example",
    "root_manifest_cid": "bafyreig2e7....",
    "archive_index_cid": "bafyreibcd...",
    "public_key_multibase": "z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK"
  }
}
```

### Fields

**`id`** — The user's IPNS name in base36lower encoding (e.g., `k51qzi5u...`). This is the same value as `corundum.ipns_name`. It is set here as `id` for Mastodon API shape compatibility: Mastodon clients expect `id` to be the account identifier used in endpoint paths. In Corundum, that identifier is the IPNS name.

**`username`** — The local part of the user's handle, without the domain. For a user known as `alice@social.example`, `username` is `alice`.

**`acct`** — The full handle in `user@domain` form. For local accounts (served by the operator being queried) this is the short form; for remote accounts fetched from another operator it is always the full qualified form. Mastodon-compatible clients use this for display.

**`display_name`** — The user's chosen display name. May contain Unicode. Not the same as `username`.

**`locked`** — If true, the account manually approves follow requests. If false, follows are accepted automatically.

**`created_at`** — ISO 8601 timestamp of when this account was registered with the operator. Not necessarily when the cryptographic identity was first created — that is not determinable in general.

**`note`** — Profile bio as sanitized HTML. May contain `<p>`, `<br>`, `<a>`, `<span>` with emoji class, and similar inline elements. Script tags and other executable content are stripped.

**`url`** — The canonical HTTP URL for this account's public profile page, as served by the operator.

**`avatar`** — URL of the user's avatar image.

**`header`** — URL of the user's profile header/banner image.

**`followers_count`** — Number of accounts that follow this account, as known to the serving operator. This count may be approximate for remote accounts.

**`following_count`** — Number of accounts this account follows, as known to the serving operator.

**`statuses_count`** — Number of statuses this account has published, as known to the serving operator.

**`corundum.ipns_name`** — The user's IPNS name, identical to `id`. Included here explicitly so that code working with the `corundum` object does not have to read the outer `id` field.

**`corundum.did`** — The user's W3C Decentralized Identifier. This is the root-of-trust identity that persists across IPNS key rotation. Corundum supports `did:web`, `did:plc`, and `did:key` methods.

**`corundum.operator_endpoint`** — The base URL of the operator that currently serves this user. Clients can use this to direct API calls for remote accounts to the correct endpoint.

**`corundum.root_manifest_cid`** — CID of this user's current RootManifest: the IPFS object that points to their profile, timeline, social graph, and operator declaration. Resolving this CID gives the complete machine-readable identity document.

**`corundum.archive_index_cid`** — CID of this user's ArchiveIndex: the content-addressed manifest of all their published statuses. Clients with IPFS access can walk the archive without going through the API.

**`corundum.public_key_multibase`** — The user's Ed25519 public key, encoded in multibase format (prefix `z` indicates base58btc). Clients can use this to verify signatures on statuses and signing records independently of the operator.

---

## Status

A Status entity represents a single published activity — a post, reply, or reblog. The `id` field is the CID of the activity object stored in IPFS (base32lower encoding, prefixed `bafyrei...`). Because `id` is a content hash, any client can independently verify that the content it received matches the claimed identifier.

```json
{
  "id": "bafyreiemxf5abjwjbikoz4mc3a3dla6ual3jsgpdr4cjr3oz3evfyavhwq",
  "created_at": "2024-03-10T12:34:56.789Z",
  "in_reply_to_id": null,
  "in_reply_to_account_id": null,
  "sensitive": false,
  "spoiler_text": "",
  "visibility": "public",
  "language": "en",
  "uri": "https://social.example/statuses/bafyrei...",
  "url": "https://social.example/@alice/bafyrei...",
  "replies_count": 3,
  "reblogs_count": 7,
  "favourites_count": 42,
  "content": "<p>Hello, federated world.</p>",
  "reblog": null,
  "account": { "...": "Account entity" },
  "media_attachments": [],
  "tags": [],
  "emojis": [],
  "corundum": {
    "cid": "bafyreiemxf5abjwjbikoz4mc3a3dla6ual3jsgpdr4cjr3oz3evfyavhwq",
    "signing_record_cid": "bafyreiabcdef...",
    "sequence_number": 42,
    "epoch": 0,
    "curation_labels": []
  }
}
```

### Fields

**`id`** — The CID of the activity object in base32lower encoding. This is the same value as `corundum.cid`. It is used as the status identifier in all API endpoint paths. Because the `id` is a content hash, it is computed from the canonical JSON of the activity — any client with the content can verify the identifier is correct by computing `SHA256(canonical_json(activity))` and checking it matches the CID. There are no server-assigned opaque IDs.

**`created_at`** — ISO 8601 timestamp of when the status was published, as declared in the activity object. This timestamp is part of the signed content and cannot be altered after publication without changing the CID.

**`in_reply_to_id`** — If this status is a reply, the CID of the status it replies to. `null` for top-level posts.

**`in_reply_to_account_id`** — If this status is a reply, the IPNS name (Account `id`) of the author of the parent status. `null` for top-level posts.

**`sensitive`** — If true, the status contains sensitive content and clients should hide the content behind a click-through.

**`spoiler_text`** — If `sensitive` is true, this is the content warning text displayed before the click-through. Empty string when not used.

**`visibility`** — One of `public`, `unlisted`, `private`, or `direct`. Controls who can see the status and whether it appears in public timelines.

**`language`** — BCP 47 language tag (e.g., `en`, `fr`, `zh-TW`). Set by the author at post time.

**`uri`** — The canonical URI for this status. Federated systems use this to refer to the status across operator boundaries.

**`url`** — The human-readable URL for this status on the serving operator's web interface.

**`replies_count`** — Number of replies to this status, as known to the serving operator.

**`reblogs_count`** — Number of times this status has been reblogged (boosted), as known to the serving operator.

**`favourites_count`** — Number of times this status has been favourited, as known to the serving operator.

**`content`** — The rendered HTML content of the status. Sanitized: only inline elements are permitted. Mention handles and hashtags are wrapped in `<a>` tags by the server.

**`reblog`** — If this status is a reblog of another status, the full Status entity of the reblogged status. `null` for original posts.

**`account`** — The full Account entity of the author of this status.

**`media_attachments`** — Array of MediaAttachment entities. Empty array if no media is attached.

**`tags`** — Array of hashtag objects with `name` and `url` fields.

**`emojis`** — Array of custom emoji objects used in the content.

**`corundum.cid`** — The CID of the activity, identical to `id`. Included here explicitly for code working only with the `corundum` object.

**`corundum.signing_record_cid`** — CID of the detached SigningRecord for this activity. The SigningRecord contains the author's public key, the signature over the activity CID, and metadata that binds the signature to this specific activity. Clients can fetch the SigningRecord via `GET /api/v1/statuses/:id/signing_record` to verify authorship independently.

**`corundum.sequence_number`** — The author's monotonically increasing publication sequence number at the time this status was published. Sequence numbers allow detection of gaps or reordering in an author's publish stream.

**`corundum.epoch`** — The epoch counter, incremented when the author performs a key rotation. A sequence number is only meaningful within a single epoch. The combination of `(author_ipns, epoch, sequence_number)` uniquely orders all statuses from a given author.

**`corundum.curation_labels`** — Array of CurationLabel entities applied to this status by subscribed curators. Empty array if no labels have been applied. The operator includes only labels from curators that the authenticated user has subscribed to; unauthenticated requests receive labels from the operator's default curator subscriptions.

---

## CurationLabel

A CurationLabel is an element of a status's `corundum.curation_labels` array. It represents a judgment about the status made by an external curator that the user or operator has chosen to subscribe to. Labels are advisory: clients decide how to act on them (hide, warn, collapse). The signing record for the label is available via the `authority_declaration_cid`.

```json
{
  "curator_id": "k51qzi5...",
  "curator_display_name": "Safety Curator",
  "judgment": "spam",
  "confidence": 0.95,
  "signed_at": "2024-03-10T14:00:00.000Z",
  "authority_declaration_cid": "bafyrei...",
  "appeal_url": "https://curator.example/appeals"
}
```

### Fields

**`curator_id`** — IPNS name of the curator that issued this label. Curators are Corundum identities, same as users.

**`curator_display_name`** — Display name of the curator at the time the label was issued. Informational only; do not use for identity verification.

**`judgment`** — The label string, e.g., `spam`, `harassment`, `misinformation`, `adult-content`, `violence`. The vocabulary is defined by the curator's AuthorityDeclaration document (referenced by `authority_declaration_cid`). Clients should treat unknown judgment strings as opaque labels rather than errors.

**`confidence`** — A float in [0.0, 1.0] expressing the curator's stated confidence in the label. 1.0 means certain; values below 1.0 indicate probabilistic or automated labeling. Clients may use this to decide whether to show a soft warning or hard filter.

**`signed_at`** — ISO 8601 timestamp of when the curator issued this label. The label is part of a signed record; `signed_at` is declared in the label's content.

**`authority_declaration_cid`** — CID of the curator's AuthorityDeclaration document, which describes the curator's scope, labeling vocabulary, accountability contact, and signing key. Clients that want to independently verify a label fetch this document and verify the label signature against the declared key.

**`appeal_url`** — URL where the status author or affected users can file an appeal against this label. May be `null` if the curator does not offer an appeals process.

---

## SigningRecord

A SigningRecord is the detached cryptographic proof of authorship for a status. It binds an activity CID to an author's public key with an Ed25519 signature. SigningRecords are stored in IPFS and are themselves content-addressed. They are returned by `GET /api/v1/statuses/:id/signing_record` and require no authentication — any client can fetch and verify them.

```json
{
  "activity_cid": "bafyreiemxf5abjwjbikoz4mc3a3dla6ual3jsgpdr4cjr3oz3evfyavhwq",
  "author_ipns": "k51qzi5...",
  "signed_at": "2024-03-10T12:34:56.789Z",
  "algorithm": "ed25519",
  "public_key_multibase": "z6MkhaXgBZ...",
  "signature_multibase": "zABC123...",
  "signing_record_cid": "bafyreiabcdef..."
}
```

### Fields

**`activity_cid`** — The CID of the activity this signing record covers. The signature is over the bytes of this CID (specifically, over the canonical encoding of the activity content that hashes to this CID).

**`author_ipns`** — The IPNS name of the author who signed. The corresponding public key is `public_key_multibase`. Clients verify authorship by (a) resolving the author's DID to confirm the key is currently authorized, or (b) checking the account's `corundum.public_key_multibase` field.

**`signed_at`** — ISO 8601 timestamp declared in the signing record. This is part of the signed content.

**`algorithm`** — Signature algorithm used. Currently always `ed25519`. Future versions of the protocol may add additional algorithms; clients should treat unrecognized algorithm values as unverifiable rather than as valid.

**`public_key_multibase`** — The Ed25519 public key used to produce this signature, in multibase encoding. The `z` prefix indicates base58btc encoding. Clients use this key to verify `signature_multibase` over `activity_cid`.

**`signature_multibase`** — The Ed25519 signature in multibase encoding. The signed payload is the canonical encoding of the activity content identified by `activity_cid`.

**`signing_record_cid`** — The CID of this SigningRecord object itself. Because SigningRecords are stored in IPFS, the record is also content-addressed. This CID is what appears in the status entity as `corundum.signing_record_cid`.

---

## Notification

Notification entities have the same shape as Mastodon notifications. The `type` field identifies what triggered the notification. Corundum adds three notification types beyond the Mastodon set.

Standard types (same as Mastodon):

- **`mention`** — Another user mentioned you in a status.
- **`reblog`** — Another user reblogged your status.
- **`favourite`** — Another user favourited your status.
- **`follow`** — Another user followed you.
- **`follow_request`** — Another user sent you a follow request (only if your account is locked).
- **`poll`** — A poll you voted in or created has ended.
- **`status`** — A user you have enabled notifications for posted a new status.

Corundum-specific types:

- **`corundum.block_enforcement`** — A status or interaction from you was rejected at the inter-operator protocol level because the recipient has a block in effect that propagated to their operator. This is distinct from a client-side filter: the rejection was signaled back to your operator by the remote operator. The notification exists so that you know the block is in force — you cannot silently assume delivery.
- **`corundum.migration_completed`** — An account you follow has completed an identity migration to a new IPNS name or operator. The notification carries both the old and new identifiers so you can update your mental model. Your operator will have already updated its follow records.
- **`corundum.curation_flagged`** — A curator you or your operator subscribes to has applied a label to one of your own statuses. The notification carries the label and links to the signing record and appeal URL.

---

## MediaAttachment

MediaAttachment entities have the same shape as Mastodon media attachments. For media uploaded through a Corundum operator, the `url` field points to an IPFS gateway URL (the content is stored in IPFS). Corundum adds one field under `corundum`.

Standard fields (same as Mastodon): `id`, `type` (`image`, `video`, `gifv`, `audio`, `unknown`), `url`, `preview_url`, `remote_url`, `description` (alt text), `blurhash`, `meta`.

**`corundum.media_cid`** — The raw IPFS CID of the media content, without a gateway URL wrapper. Clients with direct IPFS access can fetch the content at this CID from any IPFS gateway or node. If the media was not uploaded through a Corundum operator (e.g., it is a remote attachment referenced by URL), this field is `null`.

---

## Relationship

Relationship entities have the same shape as Mastodon relationships. They describe the relationship between the authenticated user and another account. Corundum adds one field under `corundum`.

Standard fields (same as Mastodon): `id`, `following`, `showing_reblogs`, `notifying`, `followed_by`, `blocking`, `blocked_by`, `muting`, `muting_notifications`, `requested`, `domain_blocking`, `endorsed`.

**`corundum.block_enforced`** — Boolean. If `true`, the block between you and this account is enforced at the inter-operator protocol level: your operator and their operator have exchanged block declarations, and the remote operator will reject interactions from your account at the protocol layer, not just filter them at the client layer. If `false` (or absent), any block is client-side only and does not propagate to the inter-operator protocol.
