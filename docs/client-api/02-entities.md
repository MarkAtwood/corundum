# Entity Definitions

This document defines the JSON entity shapes returned by the Corundum client API. Each entity is described with an example and field-by-field explanation. Where Corundum extends a Mastodon-shaped entity, **every** extension field is nested under a `corundum` key; no Corundum field appears at the top level. Placeholders in angle brackets (`<activity id>`, `<SCID>`) stand for real values; no example here is a real hash or key.

---

## Account

An Account entity represents a user. Its `id` is the user's DID, the canonical persistent identifier that the specification requires operators to key users by (spec Chapter 5). It does not change when the user moves operator, rotates keys, or changes handle. When used in a path, it is percent-encoded as described in `00-design.md` (Identifiers).

```json
{
  "id": "did:webvh:<SCID>:birdsite.example:users:alice",
  "username": "alice",
  "acct": "alice@birdsite.example",
  "display_name": "Alice Liddell",
  "locked": false,
  "created_at": "2024-01-15T00:00:00.000Z",
  "note": "<p>Profile bio</p>",
  "url": "https://birdsite.example/@alice",
  "avatar": "https://birdsite.example/avatars/alice.jpg",
  "header": "https://birdsite.example/headers/alice.jpg",
  "followers_count": 142,
  "following_count": 38,
  "statuses_count": 891,
  "corundum": {
    "ipns_name": "<IPNS name>",
    "operator_endpoint": "https://birdsite.example",
    "root_manifest_cid": "<CID of the RootManifest>",
    "key_custody": "operator"
  }
}
```

### Fields

**`id`** — The user's DID (`did:webvh`, `did:plc`, or `did:key`; spec Chapter 5). Used as the account identifier in every endpoint path and in every reference to the user, such as `in_reply_to_account_id`.

**`username`** — The local part of the user's account handle. For `alice@birdsite.example`, `username` is `alice`.

**`acct`** — The handle in `user@domain` form, shown only if it verifies bidirectionally: the handle resolves to this DID, and the DID document lists the handle in `alsoKnownAs` (spec Chapter 8). For local accounts this is the short form; for remote accounts it is fully qualified. If no handle verifies, `acct` is the DID. A user who moves operator usually leaves the old operator's handle behind, so `acct` may change while `id` stays the same.

**`display_name`** — The user's chosen display name. May contain Unicode.

**`locked`** — If true, the user manually approves follow requests.

**`created_at`** — When this account was registered with the operator. Not necessarily when the DID was created.

**`note`** — Profile bio as sanitized HTML.

**`url`** — The account's public profile page on the serving operator.

**`avatar`**, **`header`** — Image URLs.

**`followers_count`**, **`following_count`**, **`statuses_count`** — Counts as known to the serving operator; approximate for remote accounts. Following lists are private by default (spec Chapter 25), so `following_count` may be absent for accounts that have not published theirs.

**`corundum.ipns_name`** — The user's current IPNS name, as named by their DID document's `CorundumIdentity` service (spec Chapter 6). It is the user's Ed25519 content-signing key and the pointer to their RootManifest. It changes whenever the content key changes, including on every migration, so it is never used as an account identifier.

**`corundum.operator_endpoint`** — The origin of the operator currently serving this user, as named by the DID document (for example `https://birdsite.example`).

**`corundum.root_manifest_cid`** — CID of the user's current RootManifest (spec Chapter 9), as last resolved by the serving operator. Clients with IPFS access can walk the user's archive from it.

**`corundum.key_custody`** — `operator` if the operator holds the user's content key and signs for them, `self` if the user holds it (`10-identity-migration.md`). Clients use this to choose between the status endpoints and client-signed publishing (`03-statuses.md`).

The user's content-signing keys are not repeated here. They are the key in `ipnsName` plus any `additionalKeys` in the DID document (spec Chapter 6); clients that verify signatures resolve the DID document themselves.

---

## Status

A Status entity represents one published activity: a post, reply, or boost. Its `id` is the activity's identifier: a CIDv1 with the `raw` codec and a SHA-256 multihash over the activity's exact stored bytes, in base32 (`bafkrei…`; spec Chapter 33). The operator never re-serializes an activity, so the identifier never changes.

```json
{
  "id": "<activity id>",
  "created_at": "2025-03-15T14:22:11.000Z",
  "in_reply_to_id": null,
  "in_reply_to_account_id": null,
  "sensitive": false,
  "spoiler_text": "",
  "visibility": "public",
  "language": "en",
  "uri": "https://birdsite.example/statuses/<activity id>",
  "url": "https://birdsite.example/@alice/<activity id>",
  "replies_count": 3,
  "reblogs_count": 7,
  "favourites_count": 42,
  "content": "<p>Just finished the most fascinating book on distributed systems.</p>",
  "reblog": null,
  "account": { "...": "Account entity" },
  "media_attachments": [],
  "tags": [],
  "emojis": [],
  "corundum": {
    "seq": 1042,
    "epoch": 4,
    "signing_record_cid": "<CID of the SigningRecord>",
    "replaces": null,
    "replaced_by": null,
    "curation_labels": []
  }
}
```

### Fields

**`id`** — The activity identifier. Used as the status identifier in all endpoint paths. Any client that has the activity's bytes can check them against `id` by hashing them; the operator cannot alter content without changing the identifier. The bytes can be fetched by CID from any IPFS gateway, including the operator's (`01-auth.md`, `corundum.ipfs_gateway`).

**`created_at`** — The activity's `published` time, as declared by the author and covered by the signature.

**`in_reply_to_id`** — The activity identifier of the parent, or `null` for top-level posts.

**`in_reply_to_account_id`** — The DID of the parent's author, or `null`.

**`sensitive`**, **`spoiler_text`** — The activity's `sensitive` flag and `summary` (content warning).

**`visibility`** — Always `public`. Corundum covers the public conversation only (spec Chapter 40); the field is kept for Mastodon shape compatibility.

**`language`** — The activity's BCP 47 `language` tag, or `null` if the author did not declare one.

**`uri`**, **`url`** — The status's canonical and human-readable URLs on the serving operator.

**`replies_count`**, **`reblogs_count`**, **`favourites_count`** — Counts as known to the serving operator.

**`content`** — The activity's content rendered as sanitized HTML. This is a rendering, not the signed bytes; to verify, fetch the activity bytes by `id`.

**`reblog`** — For a boost (`Announce` activity), the boosted Status entity; otherwise `null`.

**`account`** — The author's Account entity. Its `id` equals the activity's `attributedTo`.

**`media_attachments`**, **`tags`**, **`emojis`** — As in Mastodon.

**`corundum.seq`** — The activity's `seq`: its position in the author's timeline (spec Chapters 10 and 11). Gaps or reordering in an author's sequence numbers are detectable.

**`corundum.epoch`** — `floor(seq / 256)`: the archive epoch, a fixed 256-entry chunk of the author's timeline, that holds this entry, or will hold it once the current chunk fills (spec Chapter 9). Epoch `k` covers sequence numbers `256k` through `256k + 255`. It has nothing to do with keys.

**`corundum.signing_record_cid`** — CID of the activity's current SigningRecord (see below). This is the record named by the archive entry, or a later one if the activity was re-signed (spec Chapter 12).

**`corundum.replaces`** — For an edit, the identifier of the version this one replaces (the activity's `replaces` field, spec Chapter 13); otherwise `null`.

**`corundum.replaced_by`** — If this version has been edited, the identifier of the version that replaces it, from the author's StateMap (spec Chapter 10); otherwise `null`. The operator has checked the replacing activity as spec Chapter 10 requires. Not set for a reply shown inside someone else's reply tree, which always shows the version the parent's operator accepted (spec Chapter 13).

**`corundum.curation_labels`** — CurationLabel entities applied to this status by curators the operator or the user subscribes to (`11-curation.md`). Empty if none.

---

## CurationLabel

A CurationLabel is the client-facing projection of one curation entry (spec Chapter 29) that matched a status. Labels are advisory to clients except where the operator's own policy acts on them (`operator_action`).

```json
{
  "authority": "https://curator.example/.well-known/corundum-curator",
  "curator_display_name": "Spam Detection Service",
  "sequence": 48293,
  "reason": "spam/spam-commercial",
  "ordinal": 0.85,
  "issued": "2025-01-15T12:34:56Z",
  "expires": null,
  "matched_subject": { "hash_type": "sha256", "hash_scope": "text-exact" },
  "entry": "<the CurationEntry JWS, verbatim>",
  "operator_action": "label",
  "appeal_url": "https://curator.example/appeals"
}
```

### Fields

**`authority`** — The URL of the curator's Authority Declaration (the entry's `authority`, equal to the declaration's `id`). This is how curators are identified (`11-curation.md`).

**`curator_display_name`** — The organization name from the Authority Declaration. Informational only.

**`sequence`** — The entry's sequence number in the curator's feed.

**`reason`** — The `category/subcode` reason from the spec Chapter 29 taxonomy, for example `spam/spam-commercial` or `nsfw/nsfw-sexual`.

**`ordinal`** — The strength of the judgment, from `0.0` to `1.0`. Higher is stronger.

**`issued`**, **`expires`** — When the judgment was made, and when it stops applying (`null` if it does not expire).

**`matched_subject`** — Which of the entry's subjects matched this status: its `hash_type` and `hash_scope` (spec Chapter 28).

**`entry`** — The stored CurationEntry, an attached JWS (spec Chapter 29 wire format), exactly as the curator published it. A client that wants to verify the label checks this JWS against the keys in the curator's Authority Declaration, as spec Chapter 29 describes; it does not need to trust the operator.

**`operator_action`** — What this operator's policy does with the label: `label`, `warn`, or `block` (`11-curation.md`).

**`appeal_url`** — The appeal process URL from the Authority Declaration.

---

## SigningRecord

A SigningRecord is the detached proof of authorship for an activity: a JSON Web Signature in the General JSON Serialization, with no payload, over the activity's exact stored bytes (spec Chapters 12 and 34). `GET /api/corundum/v1/statuses/:id/signing_record` returns its stored bytes exactly as they were written, with no wrapper; it can equally be fetched from IPFS by `corundum.signing_record_cid`. Neither requires authentication.

```json
{
  "signatures": [
    {
      "protected": "<base64url of the protected header>",
      "signature": "<base64url of the Ed25519 signature>"
    }
  ]
}
```

Each protected header, decoded, contains exactly:

```json
{"alg":"Ed25519","b64":false,"crit":["b64","corundumType"],"corundumType":"Activity","kid":"<IPNS name of the signing key>"}
```

A SigningRecord does not name the activity it signs; it verifies against the activity's bytes or not at all. It has one signature per key in the author's required set (every content-signing key the author's DID document lists).

### Verifying a Status

This is the only verification procedure in this API; other documents refer here. It follows spec Chapter 34 ("Verifying an activity"), which is authoritative.

1. Fetch the activity's bytes by its `id` from any IPFS gateway, and the SigningRecord's bytes by `corundum.signing_record_cid` (or from the `signing_record` endpoint). Do not parse and re-encode either one.
2. Compute the CID of the activity bytes (CIDv1, `raw` codec, SHA-256) and compare it with `id`.
3. For each signature, decode the protected header and check that it has exactly the parameters above, with `corundumType` `"Activity"` and an `alg` from the spec Chapter 36 registry.
4. Build the signing input (the ASCII base64url protected header, `.`, then the raw activity bytes; RFC 7797) and verify the signature with the key named by `kid`, under the Ed25519 verification profile of spec Chapter 34.
5. Resolve the DID named by the activity's `attributedTo` and take its required set of content keys (spec Chapter 6).
6. If the activity is in the author's archive, confirm it is reachable from the author's current, validly signed RootManifest (spec Chapter 9). Otherwise, confirm that every key in the required set produced a valid signature.

If something needed for verification cannot be fetched, the status is *unverified*, not invalid (spec Chapter 34).

---

## Notification

Notification entities have the same shape as Mastodon notifications, with Corundum-specific data under `corundum` (`06-notifications.md`). The `type` field identifies what triggered the notification.

Standard types (same as Mastodon): `mention`, `reblog`, `favourite`, `follow`, `follow_request`, `poll`, `status`.

Corundum-specific types:

- **`corundum.reply_rejected`** — A reply you submitted was rejected by the parent post's operator. `corundum.rejected_status_id` is your reply's activity identifier and `corundum.reason` is the `REPLY_REJECTED` reason code from spec Chapter 21 (for example `blocked-user` or `replies-disabled`). You learn which post rejected the reply, and therefore, for `blocked-user`, that its author blocked you; Corundum does not pretend a block can be hidden from the blocked user.
- **`corundum.account_migrated`** — An account you follow now names a new operator in its DID document. `corundum.previous_operator` and `corundum.operator_endpoint` are the old and new operator origins. The account's `id` is unchanged, because the DID is unchanged; your operator has already redirected its follow records.
- **`corundum.curation_flagged`** — A curator you or your operator subscribe to has labeled one of your statuses. `corundum.label` is the CurationLabel; `status` is the labeled status.

---

## MediaAttachment

MediaAttachment entities have the same shape as Mastodon media attachments (`08-media.md`). The `id` is an operator-local identifier for one upload by one user, not a content hash: two users who upload the same file get the same CID but different media ids, so ownership and editing rights attach to the media id.

Standard fields (same as Mastodon): `id`, `type` (`image`, `video`, `gifv`, `audio`, `unknown`), `url`, `preview_url`, `remote_url`, `description` (alt text), `blurhash`, `meta`.

**`corundum.media_cid`** — The CID of the media file's bytes, built with the fixed UnixFS parameters of spec Chapter 15 (CIDv1, SHA-256, raw leaves, 1,048,576-byte fixed-size chunks, balanced layout with at most 174 links per node). Anyone who has the file computes the same CID, and clients with IPFS access can fetch it from any node. A file of at most 1 MiB is a single raw block and its CID begins `bafkrei`; a larger file's root begins `bafybei`. This is the CID that appears in the activity's `ipfs`-mode ContentRef. `null` for remote media that is referenced by URL.

---

## Relationship

Relationship entities have the same shape as Mastodon relationships and carry no Corundum extension fields. `id` is the other account's DID.

Standard fields (same as Mastodon): `id`, `following`, `showing_reblogs`, `notifying`, `followed_by`, `blocking`, `blocked_by`, `muting`, `muting_notifications`, `requested`, `domain_blocking`, `endorsed`, `note`.

A Corundum block is always enforced at the protocol level, so there is no separate "enforced" flag: your operator rejects reply submissions from accounts you block (`07-relationships.md`). `blocked_by` is `true` only when your operator has learned of the block, for example from a `REPLY_REJECTED` with reason `blocked-user`.
