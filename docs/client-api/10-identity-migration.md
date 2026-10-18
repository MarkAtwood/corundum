# Identity and Migration

Identity in Corundum belongs to the user, not to an operator (spec Chapters 5–7). The user's identity is their DID. The operator is a service provider: it hosts the user's content and delivers it to the network, but it cannot change the DID document, because only the user's update keys can. Migration moves the hosting relationship without changing the identity, so followers do not need to take any action when someone they follow moves.

This section has no Mastodon analogue.

## Concepts

**DID:** The account's persistent identifier and its Account `id` (`00-design.md`). Corundum accepts `did:webvh` (the default), `did:plc`, and `did:key` (spec Chapter 5). The DID never changes when the user changes operator, rotates keys, or changes handle.

**DID document:** Lists the user's handles in `alsoKnownAs` and contains exactly one `CorundumIdentity` service entry, whose `serviceEndpoint` has `ipnsName` (the current content key), `operatorEndpoint` (the current operator's origin, e.g. `https://birdsite.example`), and optionally `additionalKeys` (spec Chapter 6). For `did:webvh` the document is published as a hash-chained log, `did.jsonl`, at a URL derived from the DID: `did:webvh:<SCID>:birdsite.example:users:alice` resolves from `https://birdsite.example/users/alice/did.jsonl`. Clients resolve the log; they never trust a plain `did.json` copy.

**IPNS name:** The user's Ed25519 content-signing key, and the pointer to their RootManifest. It is not an account identifier: it changes whenever the content key changes, including on every move to a new operator. The DID document always names the current one.

**RootManifest:** The attached JWS (spec Chapter 9) that the IPNS name points to. It names the user's DID, operator endpoint, timeline and ArchiveIndex, StateMap, ReplyMap, and encrypted social-graph lists. It is signed by every content key the DID document lists.

**Update keys and recovery key:** The keys that change the DID document: `did:webvh` log `updateKeys` (with pre-rotation), or `did:plc` rotation keys. They are always held by the user, on the user's device, and an operator never sees them. The user should also keep a recovery key offline (the pre-rotated next key for `did:webvh`; a higher-priority rotation key for `did:plc`). Every identity change in this document is a DID update signed by the client with one of these keys; the operator only relays or publishes it.

**Migration:** A content key change plus a change of `operatorEndpoint`, made by the user's DID update (spec Chapter 7). There is one flow. A cooperative old operator can make it faster; a hostile one cannot stop it, because the DID update is the only step that carries authority and the archive is in IPFS.

---

## Key Custody

Every account has a `key_custody` mode, shown as `corundum.key_custody` on the Account entity (`02-entities.md`). It says who holds the content key. Update keys are user-held in both modes.

**`operator` (the default).** The operator holds the content key. When the user posts, edits, deletes, boosts, favourites, follows, or changes their profile, the operator builds the activity bytes, assigns `seq`, signs the SigningRecord, and signs and publishes the new RootManifest and IPNS record. This is the familiar experience, and it is the only mode in which the Mastodon shim can post (`13-mastodon-shim.md`).

**`self`.** The client holds the content key, so the operator cannot publish anything in the user's name. Operator-signing endpoints (`POST`, `PUT`, and `DELETE /api/corundum/v1/statuses`, reblog, favourite, and their undo endpoints) return `409 CUSTODY_MODE_MISMATCH`. Instead:

1. The client reads `next_seq` from `GET /api/corundum/v1/identity`, builds the activity with that `seq` and `attributedTo` set to the user's DID, and signs a detached-JWS SigningRecord over its exact bytes (`02-entities.md`).
2. The client submits both with `POST /api/corundum/v1/activities` (`03-statuses.md`), base64url-encoded so that JSON transport never re-serializes them. The operator verifies the CID, the signatures (spec Chapter 34), the `seq`, and the author.
3. The operator responds `202 Accepted` with a pending RootManifest:

```json
{
  "pending_root_manifest": {
    "payload": "<base64url of the RootManifest payload bytes>",
    "ipns_record": "<base64url of the unsigned IPNS record>"
  }
}
```

4. The client signs the payload as an attached JWS (`corundumType` `"RootManifest"`, one signature per content key), signs the IPNS record, and commits both with `PUT /api/corundum/v1/identity/root_manifest`.

Any other write that changes the RootManifest without publishing an activity (follow, block, and mute lists; profile fields) also returns `202` with a `pending_root_manifest` for a self-custody user, committed the same way.

A `did:key` user is always `self`: their only key is their identity.

---

## Identity Endpoints

### GET /api/corundum/v1/identity

Get the authenticated user's identity record.

**Authentication:** Required (`read:identity` scope)

**Returns:**

```json
{
  "did": "did:webvh:<SCID>:birdsite.example:users:alice",
  "did_method": "did:webvh",
  "did_log_url": "https://birdsite.example/users/alice/did.jsonl",
  "handles": ["acct:alice@birdsite.example"],
  "ipns_name": "<IPNS name>",
  "operator_endpoint": "https://birdsite.example",
  "root_manifest_cid": "<CID of the RootManifest>",
  "key_custody": "operator",
  "content_keys": [
    { "kid": "<IPNS name>", "alg": "Ed25519" }
  ],
  "next_seq": 1043
}
```

| Field | Type | Description |
|-------|------|-------------|
| `did` | string | The account's DID. This is the Account `id`. |
| `did_method` | string | `did:webvh`, `did:plc`, or `did:key`. |
| `did_log_url` | string or null | For `did:webvh`, the URL of the DID log (`did.jsonl`). `null` for other methods. |
| `handles` | array of strings | The handles the DID document lists in `alsoKnownAs` (`acct:` and `dns:` URIs). |
| `ipns_name` | string | The current content key and RootManifest pointer, as named by the DID document. |
| `operator_endpoint` | string | The origin of the operator the DID document names. |
| `root_manifest_cid` | string | CID of the RootManifest currently published under `ipns_name`. |
| `key_custody` | string | `operator` or `self` (see Key Custody). |
| `content_keys` | array | The required signing set: the key in `ipnsName` plus every key in `additionalKeys` (spec Chapter 34). `alg` values come from the spec Chapter 36 registry. |
| `next_seq` | integer | The `seq` the user's next activity must carry. |

---

### GET /api/corundum/v1/identity/root_manifest

Get the RootManifest currently published under the authenticated user's IPNS name.

**Authentication:** Required (`read:identity` scope)

**Returns:** The stored attached-JWS bytes, exactly as stored and never re-serialized, with `Content-Type: application/jose+json`. The response carries the manifest's CID in a `Corundum-CID` header, so the client can check the bytes by hashing them (spec Chapter 33). The payload structure is defined in spec Chapter 9.

---

### PUT /api/corundum/v1/identity/root_manifest

Commit a RootManifest that a self-custody client has signed (see Key Custody).

**Authentication:** Required (`write:identity` scope)

**Request Body:**

```json
{
  "root_manifest": "<base64url of the attached JWS bytes>",
  "ipns_record": "<base64url of the signed IPNS record>"
}
```

The operator checks that the JWS payload is byte-identical to the pending payload it issued, that every key in the required set signed it, and that the IPNS record is signed by the IPNS key and names the manifest's CID. It then stores and publishes both.

**Returns:** `200 OK` with `{ "root_manifest_cid": "<CID of the RootManifest>" }`.

**Errors:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 400 | `ACTIVITY_INVALID` | A signature is missing or invalid (`details.reason` `signature-invalid`), or the payload differs from the pending one. |
| 409 | `CUSTODY_MODE_MISMATCH` | The account is in `operator` custody. |
| 409 | `SEQ_CONFLICT` | The pending manifest is stale: another write has been committed since it was issued. Request a new one. |

---

### POST /api/corundum/v1/identity/content_key

Ask the operator to generate a new content key, for an `operator`-custody user who wants to replace a lost or compromised key (spec Chapter 7). This does not change anything by itself: the new key takes effect only when the user's DID update names it.

**Authentication:** Required (`write:identity` scope)

**Request Body:** None.

**Returns:** The proposed `CorundumIdentity` service endpoint, which the client puts into a DID update and signs with the user's update key:

```json
{
  "proposed_service": {
    "ipnsName": "<IPNS name of the new content key>",
    "operatorEndpoint": "https://birdsite.example"
  }
}
```

A self-custody client generates its own key and builds the DID update without calling this endpoint.

**Errors:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 409 | `CUSTODY_MODE_MISMATCH` | The account is in `self` custody. |
| 422 | `VALIDATION_FAILED` | The account's DID is a `did:key` (`details.reason` `did-key-immutable`). |

---

### POST /api/corundum/v1/identity/did_updates

Submit a DID update that the client has signed with the user's update key (or recovery key): a `did:webvh` log entry or a `did:plc` operation. This is how a user rotates their content key, adds a key (spec Chapter 35), changes handles, or moves to a new operator.

**Authentication:** Required (`write:identity` scope)

**Content-Type:** `application/json`

**Request Body:**

```json
{
  "method": "did:webvh",
  "update": "<base64url of the signed log entry or PLC operation>"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `method` | string | yes | `did:webvh` or `did:plc`. |
| `update` | string | yes | The signed log entry (one `did.jsonl` line) or PLC operation, base64url-encoded so it reaches the operator byte for byte. |

**Behavior:** The operator verifies the update: for `did:webvh`, that it chains to the current log and is signed by a currently authorized update key (or satisfies pre-rotation); for `did:plc`, that it is a valid operation for the DID. It MUST NOT alter the update. It then publishes it: for `did:webvh`, by appending it to the log it hosts; for `did:plc`, by submitting it to `plc.directory`. If the updated document names a content key this operator holds, the operator publishes a RootManifest under that IPNS name, committing to the same archive (the same epochs, with the same CIDs).

The operator holds no update key and cannot produce a DID update itself.

**Returns:** `200 OK` with the resolved identity record (same shape as `GET /api/corundum/v1/identity`).

**Errors:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 400 | `DID_UPDATE_INVALID` | The update does not verify, does not chain to the current log, or is not for this user's DID. |
| 422 | `VALIDATION_FAILED` | The DID is a `did:key` (`details.reason` `did-key-immutable`), which has no updates. |
| 502 | `DID_RESOLUTION_FAILED` | The current DID log or PLC state could not be fetched. |
| 502 | `UPSTREAM_UNAVAILABLE` | `plc.directory` did not accept the operation. |

---

## Migration Endpoints

### POST /api/corundum/v1/migration/export

Ask the current operator to prepare an export of the user's archive. This is optional: a cooperative operator saves the new operator some fetching, but everything the new operator needs is in IPFS. Exporting is an asynchronous traversal of every object reachable from the current RootManifest (spec Chapter 9), written as a CAR file.

**Authentication:** Required (`write:identity` scope)

**Request Body:** None.

**Returns:** Export job record.

```json
{
  "export_id": "<operator-assigned export id>",
  "status": "pending"
}
```

Poll `GET /api/corundum/v1/migration/export/:export_id` for progress.

**Completion response** (when `status` is `complete`):

```json
{
  "export_id": "<operator-assigned export id>",
  "status": "complete",
  "root_manifest_cid": "<CID of the RootManifest>",
  "car_url": "https://birdsite.example/api/corundum/v1/migration/export/<export id>/archive.car",
  "expires_at": "2025-04-10T12:00:00Z"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `root_manifest_cid` | string | The RootManifest the export was traversed from. Everything in the CAR file is reachable from it and can be verified against it. |
| `car_url` | string | Where the CAR file can be downloaded until `expires_at`. |
| `expires_at` | string (ISO 8601) | After this time the operator may delete the CAR file. The content stays in IPFS. |

**Errors:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 404 | `NOT_FOUND` | The export id does not exist or does not belong to the authenticated user. |
| 409 | `EXPORT_IN_PROGRESS` | An export is already in progress for this account. |

---

### POST /api/corundum/v1/migration/incoming

Begin a move to this operator. Called on the **new** operator, by a user who has authenticated to it (for example, with a newly created account that the migrated identity will replace).

**Authentication:** Required (`write:identity` scope)

**Content-Type:** `application/json`

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `did` | string | yes | The DID being moved. |
| `ipns_name` | string | no | For a self-custody user: the new content key the client generated. Omit to have this operator generate one (`operator` custody). |

**Behavior:**

1. The new operator resolves the DID and checks that it is not already hosted here.
2. It returns the proposed `CorundumIdentity` service endpoint: the new `ipnsName` (its own or the client's) and its own origin as `operatorEndpoint`.
3. The client builds a DID update naming that service endpoint, signs it with the user's update key, and submits it with `POST /api/corundum/v1/identity/did_updates` on the new operator. If the user's `did:webvh` log is hosted on the old operator's domain, the update also moves the DID to the new operator's domain, which the `portable: true` parameter permits (spec Chapter 7).
4. Once the update is published, the new operator fetches the archive from IPFS (or from an export, if one was provided), verifies every object by CID, pins it, and publishes a RootManifest under the new IPNS name that commits to the same epochs with the same CIDs.
5. The new operator sends a MigrationNotification to the operators of the user's followers and of the accounts they follow. A MigrationNotification is an unsigned hint sent as an RFC 9421-authenticated request; receivers re-resolve the DID and act only on what the DID document says.

**Returns:** Migration job record.

```json
{
  "migration_id": "<operator-assigned migration id>",
  "status": "awaiting_did_update",
  "proposed_service": {
    "ipnsName": "<IPNS name of the new content key>",
    "operatorEndpoint": "https://newop.example"
  }
}
```

Poll `GET /api/corundum/v1/migration/incoming/:migration_id` for progress.

**Status values:** `awaiting_did_update` → `fetching_archive` → `pinning_content` → `publishing_manifest` → `notifying` → `complete` | `failed`

**Completion response:**

```json
{
  "migration_id": "<operator-assigned migration id>",
  "status": "complete",
  "did": "did:webvh:<SCID>:newop.example:users:alice",
  "root_manifest_cid": "<CID of the RootManifest>",
  "entries_imported": 1042,
  "operators_notified": 14,
  "completed_at": "2025-03-10T14:32:00Z"
}
```

`did` reflects any move of the `did:webvh` log to the new domain; the SCID, and therefore the identity, is unchanged.

**Hostile migration.** The flow is the same. A hostile old operator can refuse to export and can keep publishing under the old IPNS name, but neither matters: the new operator fetches the archive from IPFS (from the old operator's node while it runs, or from any operator that cached it), and nothing the old key signs is authorized once the DID no longer names it (spec Chapter 34). The user's DID update is the only authority in either case. A user who has lost their update key signs the DID update with their recovery key.

**Errors:**

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 409 | `ALREADY_HOSTED` | This operator already hosts this DID. |
| 422 | `VALIDATION_FAILED` | The DID is a `did:key` and no `ipns_name` was supplied (`details.reason` `did-key-immutable`): a `did:key` user moves by publishing a RootManifest naming the new operator with their own key. |
| 502 | `DID_RESOLUTION_FAILED` | The DID document could not be resolved. |
