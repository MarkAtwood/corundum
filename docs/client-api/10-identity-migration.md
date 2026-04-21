# Identity and Migration

Identity in Corundum is decoupled from operators. A user's identity is their IPNS keypair and DID document. The operator is a service provider: it hosts the user's content and delivers it to the network, but it does not own the identity. Migration moves the hosting relationship without changing the identity. Followers do not need to take any action when their contact migrates.

This section has no Mastodon analogue.

## Concepts

**IPNS name:** The account's stable, globally portable identifier. It is the base36lower-encoded hash of the user's Ed25519 public key. It does not change when the user migrates operators.

**DID document:** A W3C Decentralized Identifier document that records the account's current public key, operator endpoint, and recovery key. Published at a well-known URL and also pinned in IPFS.

**RootManifest:** A signed JSON object stored in IPFS that is the canonical record of an account's state: current operator, current public key, archive epoch list, and profile metadata. The IPNS name resolves to the CID of the current RootManifest.

**Recovery key:** A DID recovery key is separate from the signing key used for day-to-day posting. It is used only for hostile migrations, where the old operator is offline or uncooperative. The user holds the recovery key offline; the operator never sees it.

**Cooperative migration:** The old operator is available and willing to provide a signed migration statement and export the user's archive.

**Hostile migration:** The old operator is unavailable or uncooperative. The user proves ownership via their DID recovery key and the new operator fetches the archive directly from IPFS using the IPNS-linked ArchiveIndex. No cooperation from the old operator is required.

---

## Identity Endpoints

### GET /api/v1/identity

Get the authenticated user's full identity record.

**Authentication:** Required (`read:identity` scope)

**Returns:**

```json
{
  "ipns_name": "k51qzi5uqu5dh9ihj4p2v5sl3hxvv27ryx2w0xrsv6jmmui2qbv7bhg4c1jbdx",
  "did": "did:web:alice.example",
  "did_document_url": "https://alice.example/.well-known/did.json",
  "current_operator": "https://social.example",
  "current_root_manifest_cid": "bafyreiabcdefghijklmnopqrstuvwxyz234567abcdefghijklmnopq",
  "signing_algorithms": ["ed25519"],
  "key_count": 2,
  "recovery_key_present": true
}
```

| Field | Type | Description |
|-------|------|-------------|
| `ipns_name` | string | The account's IPNS name (base36lower). This is the stable identity that persists across operator migrations. |
| `did` | string | The account's W3C Decentralized Identifier. |
| `did_document_url` | string | URL where the DID document is published. Typically `https://<domain>/.well-known/did.json`. |
| `current_operator` | string | Base URL of the operator currently hosting this account. |
| `current_root_manifest_cid` | string | CID of the RootManifest currently published under this IPNS name. |
| `signing_algorithms` | array of strings | Algorithm(s) supported for this account's signing key(s). |
| `key_count` | integer | Number of active signing keys registered for this account. |
| `recovery_key_present` | boolean | Whether a DID recovery key has been registered. Accounts without a recovery key cannot perform hostile migrations. |

---

### GET /api/v1/identity/keys

List the signing keys registered for the authenticated user's account.

**Authentication:** Required (`read:identity` scope)

**Returns:** Array of key objects.

```json
[
  {
    "key_id": "key-1",
    "algorithm": "ed25519",
    "public_key_multibase": "z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
    "created_at": "2024-01-15T09:00:00Z",
    "active": true
  },
  {
    "key_id": "key-0",
    "algorithm": "ed25519",
    "public_key_multibase": "z6MkpGuzuD38tpgZKPfmLmmD8R6gihP9S6jK3LsE7tCrBFfQ",
    "created_at": "2023-06-01T12:00:00Z",
    "active": false
  }
]
```

| Field | Type | Description |
|-------|------|-------------|
| `key_id` | string | Opaque identifier for this key within the account's key history. |
| `algorithm` | string | Signing algorithm, e.g. `ed25519`. |
| `public_key_multibase` | string | The public key encoded in multibase format (base58btc, prefix `z`). |
| `created_at` | string (ISO 8601) | When this key was registered. |
| `active` | boolean | Whether this key is currently the active signing key. At most one key is active at a time. Inactive keys remain valid for a grace period after rotation to allow in-flight signatures to verify. |

---

### POST /api/v1/identity/keys/rotate

Rotate the signing key. The new key becomes the active signing key. The old key remains valid for a grace period (operator-configurable, default 7 days) to allow in-flight content signatures to be verified.

The operator publishes an updated RootManifest with the new public key and broadcasts a `KeyRotationNotification` to known peers.

**Authentication:** Required (`write:identity` scope)

**Content-Type:** `application/json`

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `new_public_key_multibase` | string | yes | The new public key in multibase format. |
| `proof` | string | yes | A signature over the new public key bytes, produced with the current active private key. This proves the key rotation is authorized by the current key holder. |

**Returns:** Updated array of key objects (same shape as `GET /api/v1/identity/keys`). The new key appears as `active: true`; the previous key appears as `active: false`.

**Errors:**

| Code | Error | Description |
|------|-------|-------------|
| 400 | `invalid_proof` | The `proof` signature does not verify against the current active key and the provided new public key. |
| 409 | `rotation_in_progress` | A key rotation is already in progress for this account. Wait for the previous rotation to complete before initiating another. |
| 422 | `unsupported_algorithm` | The key algorithm implied by the multibase encoding is not supported by this operator. |

---

### GET /api/v1/identity/root_manifest

Get the full RootManifest currently published under the authenticated user's IPNS name.

**Authentication:** Required (`read:identity` scope)

**Returns:** The RootManifest JSON object as it is stored in IPFS. The exact structure is defined in the Corundum protocol specification. The `cid` field in the response wrapper is the CID of this manifest object.

```json
{
  "cid": "bafyreiabcdefghijklmnopqrstuvwxyz234567abcdefghijklmnopq",
  "manifest": {
    "version": 1,
    "ipns_name": "k51qzi5uqu5dh9ihj4p2v5sl3hxvv27ryx2w0xrsv6jmmui2qbv7bhg4c1jbdx",
    "operator_endpoint": "https://social.example",
    "current_public_key": "z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
    "epochs": [
      { "epoch": 0, "archive_index_cid": "bafyreiabc..." }
    ],
    "profile_cid": "bafyreiabc...",
    "signed_at": "2024-03-10T12:00:00Z",
    "signature": "..."
  }
}
```

---

## Migration Endpoints

### POST /api/v1/migration/export

Request the operator to prepare a migration export package. This is an asynchronous operation: the operator assembles the ArchiveIndex and confirms all epoch CIDs are available in IPFS, then returns a completion record with the root CID of the export. The export package is an IPFS DAG that can be fetched by any new operator, with or without cooperation from the current operator.

**Authentication:** Required (`write:identity` scope)

**Request Body:** None.

**Returns:** Export job record.

```json
{
  "export_id": "abc123",
  "status": "pending"
}
```

Poll `GET /api/v1/migration/export/:export_id` for progress.

**Completion response** (when `status` is `complete`):

```json
{
  "export_id": "abc123",
  "status": "complete",
  "archive_index_cid": "bafyreiabcdefghijklmnopqrstuvwxyz234567abcdefghijklmnopq",
  "total_entries": 891,
  "ipfs_dag_root": "bafyreiabcdefghijklmnopqrstuvwxyz234567abcdefghijklmnopq",
  "expires_at": "2024-04-10T12:00:00Z"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `archive_index_cid` | string | CID of the ArchiveIndex object, which is the root of the user's content history. Any new operator can use this CID to fetch the full archive from IPFS. |
| `total_entries` | integer | Number of content entries (statuses, boosts, etc.) in the archive. |
| `ipfs_dag_root` | string | CID of the top-level DAG node encompassing the full migration package. Identical to `archive_index_cid` for single-epoch accounts; may differ for multi-epoch accounts where the root points to a manifest that lists all epoch CIDs. |
| `expires_at` | string (ISO 8601) | The export pin will be retained by this operator until this time. After expiry, the content remains in IPFS but may be unpinned by this operator. |

**Errors:**

| Code | Error | Description |
|------|-------|-------------|
| 404 | `not_found` | Export job ID does not exist or does not belong to the authenticated user |
| 409 | `export_in_progress` | An export is already in progress for this account |

---

### POST /api/v1/migration/incoming

Begin an incoming migration. Called on the **new** operator — the operator the user is migrating to. The user must have already authenticated to the new operator (e.g., by creating a new account that will be replaced by the migrated identity, or by a pre-migration authentication flow the new operator provides).

The new operator uses the supplied information to resolve the user's IPNS name, fetch the ArchiveIndex from IPFS, pin all content, and publish a new RootManifest that declares the new operator as the current hosting endpoint.

**Authentication:** Required (`write:identity` scope)

**Content-Type:** `application/json`

**Request Body:**

```json
{
  "ipns_name": "k51qzi5uqu5dh9ihj4p2v5sl3hxvv27ryx2w0xrsv6jmmui2qbv7bhg4c1jbdx",
  "source_operator": "https://old.example",
  "migration_proof": "...",
  "did_document": { "..." : "..." }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `ipns_name` | string | yes | The IPNS name of the identity being migrated (base36lower). |
| `source_operator` | string | no | Base URL of the previous operator. Provided when known; the new operator may use this to attempt a cooperative fetch of the migration package. Omit for hostile migrations where the old operator is unreachable. |
| `migration_proof` | string | yes | A signed migration statement authorizing this move. For cooperative migrations, this is signed with the IPNS private key. For hostile migrations, this is signed with the DID recovery key. The new operator verifies the proof against the public key in the DID document before proceeding. |
| `did_document` | object | yes | The current DID document for this identity. The new operator verifies the document and uses it to resolve the signing key for the `migration_proof` verification. |

**Migration proof verification:**

- For cooperative migrations, the proof is a signature over the string `migrate:<ipns_name>:<new_operator_base_url>`, produced with the IPNS private key.
- For hostile migrations, the proof is the same statement signed with the DID recovery key.

The new operator verifies the proof before accepting the migration. If verification fails, the request is rejected with `invalid_proof`.

**Returns:** Migration job record.

```json
{
  "migration_id": "xyz789",
  "status": "fetching_archive"
}
```

Poll `GET /api/v1/migration/incoming/:migration_id` for progress.

**Status values:** `fetching_archive` → `pinning_content` → `publishing_manifest` → `complete` | `failed`

**Completion response:**

```json
{
  "migration_id": "xyz789",
  "status": "complete",
  "ipns_name": "k51qzi5uqu5dh9ihj4p2v5sl3hxvv27ryx2w0xrsv6jmmui2qbv7bhg4c1jbdx",
  "new_root_manifest_cid": "bafyreiabcdefghijklmnopqrstuvwxyz234567abcdefghijklmnopq",
  "entries_imported": 891,
  "completed_at": "2024-03-10T14:32:00Z"
}
```

**Errors:**

| Code | Error | Description |
|------|-------|-------------|
| 400 | `invalid_proof` | The `migration_proof` signature does not verify against the key in the supplied DID document. |
| 409 | `already_hosted` | This operator already hosts an account with this IPNS name. |
| 422 | `unresolvable_identity` | The IPNS name could not be resolved and no `source_operator` was provided or that operator did not respond. |

---

### POST /api/v1/migration/notify

Broadcast a migration notification to operators known to this account's social graph. Called after an incoming migration completes. The new operator sends a signed `MigrationNotification` to all operators that have interacted with this account, informing them of the new hosting endpoint. Followers' operators update their records so future deliveries go to the correct operator.

**Authentication:** Required (`write:identity` scope)

**Request Body:** None. The operator constructs the signed `MigrationNotification` from its own records (the account's IPNS name, the new operator endpoint, and the current RootManifest CID).

**Returns:**

```json
{
  "notified_count": 14,
  "failed_count": 2,
  "failed_operators": [
    "https://failing.example"
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `notified_count` | integer | Number of remote operators that acknowledged the notification. |
| `failed_count` | integer | Number of remote operators that could not be reached or returned an error. |
| `failed_operators` | array of strings | Base URLs of operators that could not be notified. The operator will retry these asynchronously; this list reflects the state at the time of the API response. |

Failures are non-fatal. Operators that are temporarily unreachable will receive the migration notification the next time they attempt to deliver a reply or follow request to the old operator endpoint, at which point the routing will be corrected. The `MigrationNotification` is also published in IPFS and linked from the new RootManifest, so any operator can discover the migration independently.
