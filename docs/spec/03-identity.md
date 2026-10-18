## Part III: Identity

### Chapter 5: The Three-Layer Identity System

Identity in Corundum is a three-layer system designed so that no single layer's failure is catastrophic. Each layer provides a different guarantee, and the layers reinforce each other. From the top:

**Layer 1: Handles (human-readable names).** A handle is what people type and recognize. Corundum has two forms:

- **Account handles** look like email addresses: `alice@birdsite.example`. They belong to an operator's namespace, the way an email address belongs to a mail provider, and are resolved with WebFinger (Chapter 8).
- **Domain handles** are a domain the user controls: `alice.example`. They are resolved with a DNS TXT record (Chapter 8).

A handle is a convenience layer. If it stops resolving, the DID and everything below it are unaffected.

**Layer 2: DID (the persistent identifier).** Every Corundum user is identified by a W3C Decentralized Identifier. The DID is the *canonical persistent* identifier: operators MUST store the DID as the primary identifier for a user, and every reference to a user in a protocol object names the DID. The DID never changes when the user changes operator, rotates keys, or changes handle.

The DID document is changed only by the user's **update keys**, which the user holds and operators MUST NOT hold (Chapter 7). This is what makes the user, not any operator, the owner of the identity: an operator can stop serving a user, but it cannot take the identity, rewrite it, or block the user from moving.

Corundum accepts three DID methods:

- **`did:webvh`** (the default). A `did:web`-style identifier with a verifiable history: every change is an entry in a hash-chained log signed by the user's update keys, with pre-rotation of those keys for recovery. Operators can host these DIDs for their users under paths of their own domain (`did:webvh:<SCID>:birdsite.example:users:alice`) without being able to change them.
- **`did:plc`** (opt-in). An operation-log method from the AT Protocol ecosystem, run as a single public registry (`plc.directory`). Operations are signed by the user's rotation keys and the log is publicly auditable, but the registry is one service, not a distributed system.
- **`did:key`** (opt-in). The DID is the public key itself. It has no document to update, no update keys, and no recovery: whoever holds the key is the identity, forever.

Plain `did:web` is not accepted. A `did:web` document has no signed history, so whoever controls the web server can rewrite it, which would let an operator that hosts a user's DID take the identity. A `did:webvh` controller may publish a parallel `did:web` copy for older tools, but Corundum resolvers MUST resolve the `did:webvh` log and ignore the copy.

**Layer 3: IPNS (the content key and content pointer).** The DID document names the user's current **IPNS name** (Chapter 6). The IPNS name does two jobs:

- It is the user's **content-signing key**. For Ed25519, the IPNS name embeds the public key itself (as an identity multihash), so anyone who has the name has the key. This key signs the user's activities and RootManifests (Chapter 34).
- It is the **pointer to the user's RootManifest** (Chapter 9). An IPNS record is a small signed object, issued by the IPNS key, that names the current RootManifest's CID and carries a sequence number so readers can reject old records.

An IPNS record is self-verifying, so it does not matter who serves it. Readers fetch it the fast way first: from the user's operator, using the standard IPFS delegated routing endpoint (`GET /routing/v1/ipns/{name}`) at the user's `operatorEndpoint`, and then fetch the RootManifest by CID. DHT resolution (typically 30–60 seconds) is the fallback for when the operator is unreachable.

The IPNS name changes whenever the content key changes, for example when the user moves to a new operator. Nobody needs to remember it: the DID always names the current one.

**Who holds the content key.** By default the user's operator holds the content key and signs on the user's behalf, so a user like Alice, who never sees a key, gets a familiar experience. A user may instead hold the content key on their own devices (**self-custody**), so that their operator cannot publish anything in their name. Either way, the update keys stay with the user, and they can replace the content key at any time by changing the DID document. A `did:key` user is always self-custodied: their only key is their identity.

**The verification chain.** Handle → DID → IPNS → RootManifest, with each step checked against the one before:

1. The handle resolves to a DID (WebFinger or DNS), and the DID document lists the handle back in `alsoKnownAs` (Chapter 8).
2. The DID document names the current IPNS name and operator endpoint (Chapter 6).
3. The IPNS record, signed by that IPNS key, names the RootManifest CID.
4. The RootManifest is signed by every content key the DID document lists, and its identity block names the same DID (Chapter 9).

If any step fails, verification fails and the system reports which step. Identity verification is therefore not just "is this signature valid?" but "is the signer who they claim to be, through a verifiable chain of declarations?"

### Chapter 6: DID Documents

A DID document for a Corundum user declares the user's content keys, their operator, and their handles. Here is an example for Alice:

```json
{
  "@context": [
    "https://www.w3.org/ns/did/v1",
    "https://corundum.example/ns/v1"
  ],
  "id": "did:webvh:<SCID>:birdsite.example:users:alice",
  "alsoKnownAs": [
    "acct:alice@birdsite.example"
  ],
  "service": [
    {
      "id": "did:webvh:<SCID>:birdsite.example:users:alice#corundum",
      "type": "CorundumIdentity",
      "serviceEndpoint": {
        "ipnsName": "<IPNS name of Alice's content key>",
        "operatorEndpoint": "https://birdsite.example",
        "listKey": "<multibase X25519 public key>"
      }
    }
  ]
}
```

The `CorundumIdentity` service entry is what connects the DID to the Corundum content layer. A DID document MUST contain exactly one. Its `serviceEndpoint` object has these members:

| Member | Required | Meaning |
|---|---|---|
| `ipnsName` | REQUIRED | The user's current IPNS name: the Ed25519 content-signing key and the pointer to the RootManifest. |
| `operatorEndpoint` | REQUIRED | The origin (scheme, host, and optional port, with no path) of the user's operator. It equals the `id` of the operator's Operator Manifest, which is served at `{operatorEndpoint}/.well-known/corundum-operator` (Chapter 18); the operator's protocol paths are relative to it. |
| `listKey` | REQUIRED | The X25519 public key, as multibase, to which the user's encrypted follow, block, and mute lists are encrypted (Chapter 25). Its private half is kept with the user's recovery material. |
| `additionalKeys` | OPTIONAL | Further content-signing keys, each an object with `kid`, `alg` (Chapter 36), and `publicKeyMultibase`. Used to add an algorithm alongside Ed25519 (Chapter 35). |

The user's **content-signing keys** are the key in `ipnsName` plus every key in `additionalKeys`. Together they form the required set: every object the user signs carries a signature from each of them (Chapter 34).

Content keys appear only in the service entry, and in no verification relationship (`authentication`, `assertionMethod`, or any other). A content key may be held by the user's operator, so it must not be usable as the user for anything outside Corundum. Generic DID software does not treat service entries as keys, so it never treats a content key as able to authenticate as the user or assert claims for them. Other protocols may add their own keys and service entries to the same document; Corundum ignores them.

The update keys that change this document are not in it. For `did:webvh` they are parameters of the DID log (`updateKeys`, with pre-rotation through `nextKeyHashes`); for `did:plc` they are the operation log's rotation keys.

The `alsoKnownAs` array lists the user's handles: `acct:alice@birdsite.example` for an account handle, `dns:alice.example` for a domain handle. This is the DID's half of the bidirectional handle check (Chapter 8).

**For `did:key` users** there is no document to carry a service entry. The DID and the IPNS name encode the same Ed25519 public key, so a resolver derives the IPNS name directly from the DID, and the RootManifest names the operator endpoint. Such a user has exactly one content key, which never changes.

**One DID, one Corundum identity.** A DID document has one `CorundumIdentity` entry, so one DID is one timeline. Everything in a DID document is public, so anyone who resolves it sees everything it lists. A user who wants personas that cannot be linked to each other uses a separate DID for each.

### Chapter 7: Key Rotation, Migration, and Recovery

Corundum has two kinds of keys, and they are replaced in different ways:

- **Update keys** change the DID document. The user holds them; operators never do. They are replaced through the DID method's own mechanism: a pre-rotated next key for `did:webvh`, or a higher-priority rotation key for `did:plc`. A user SHOULD keep one update key on their own device for routine changes and a **recovery key** offline (a hardware key, or a paper backup in a safe). For `did:webvh` the recovery key is the pre-rotated next key; for `did:plc` it is a higher-priority rotation key.
- **The content key** (the IPNS key) signs content and points to the RootManifest. Replacing it is a change to the DID document: the user's update key signs a new DID log entry naming a new `ipnsName`.

The user also holds a **list key**, an X25519 key that can decrypt their encrypted follow, block, and mute lists (Chapter 25). It is not a signing key and changes nothing; it SHOULD be kept with the recovery key, so that a user moving away from a hostile operator can take their lists with them.

**Moving to a new operator** is a content key rotation plus a change of `operatorEndpoint`, made by the user:

1. Alice tells Operator B she wants to move there.
2. Operator B generates a new content key for her. A self-custody user generates it on their own device instead.
3. Alice's client signs a DID update with her update key, naming the new `ipnsName` and B's `operatorEndpoint`.
4. Operator B fetches Alice's archive from IPFS and pins it. Every object is content-addressed, so B verifies everything it fetches.
5. Operator B publishes a RootManifest under the new IPNS name, signed with the new content key. It commits to the same archive tree: the same epochs, with the same CIDs.
6. Operator B sends a MigrationNotification to the operators of Alice's followers and to the operators she follows.

The DID update is the only step that carries authority, and only Alice can make it. A **cooperative** old operator makes the move faster: it can hand over the reply index and followers cache directly and re-key Alice's encrypted lists for B (Chapter 25). A **hostile** old operator cannot stop the move. Everything B needs is in IPFS, and can be fetched from Operator A's node while it still runs or from any other operator that cached it.

The old operator still holds the old content key and can keep publishing under the old IPNS name. That does not matter: the DID no longer names that key, so nothing it signs is authorized (Chapter 34).

**The MigrationNotification** is a hint, not an authority. It contains the DID, the old and new IPNS names, and the new operator endpoint, and it is sent as an authenticated inter-operator request (Chapter 19). A receiving operator MUST NOT act on its contents directly; it re-resolves the DID and uses what the DID document says. Operators that miss the notification find the change when their cached copy of the DID document expires. Operators MUST NOT cache a DID document for longer than 24 hours, and SHOULD use the DID method's own cache guidance (for `did:webvh`, the log's `ttl`, default one hour).

**If the old operator served the DID itself.** A `did:webvh` DID hosted on Operator A's domain (`did:webvh:<SCID>:a.example:users:alice`) stops resolving if A stops serving its log. To keep users able to leave, operators that create `did:webvh` DIDs for their users MUST set `portable: true` in the first log entry. The user can then move the DID to B's domain with a log entry signed by their update key. The SCID stays the same, and the new document lists the old DID in `alsoKnownAs`. Operators MUST key users by the SCID-bearing DID, accept such a move when the log proves it, and SHOULD keep a copy of the DID log of every user they follow, so that a hostile host deleting the log does not erase the record.

**Losing keys.**

- **Lost or compromised content key:** the user signs a DID update naming a new content key. The old key's signatures on content already in the archive stay valid by inclusion (Chapter 34); anything signed with it afterwards is rejected.
- **Lost update key:** the user recovers with their recovery key.
- **Lost update key and recovery key:** the identity can no longer be changed. Content keeps working, but the user can never move operator or replace the content key again.

**The `did:key` tradeoff.** A `did:key` user's DID is their content key. They can still move operators: they publish a RootManifest naming a new operator endpoint, because they hold the key themselves. But there is no rotation and no recovery. If the key is lost or stolen, the identity is gone, and a new identity cannot prove continuity with the old one. Users who care about recovery should use `did:webvh` or `did:plc` with an offline recovery key.

### Chapter 8: Handle Resolution

Handles serve a human need that cryptographic identifiers don't meet: humans recognize `alice@birdsite.example` where they would not recognize a DID or an IPNS name. Handles are the socially meaningful layer of identity: the name people use, search for, and recognize.

**Bidirectional verification.** A handle is verified only when both directions agree: the handle resolves to a DID, and that DID's document lists the handle in `alsoKnownAs`. Either direction alone allows impersonation. If only the DID's claim counted, anyone could publish a DID document claiming `alice@birdsite.example`. If only the handle's record counted, a domain owner could point a handle at someone else's DID and make it appear that person chose it.

**Account handles (WebFinger).** An account handle `alice@birdsite.example` is resolved with WebFinger (RFC 7033):

```
GET https://birdsite.example/.well-known/webfinger?resource=acct:alice@birdsite.example
```

The JSON Resource Descriptor in the response contains a link to the DID:

```json
{
  "subject": "acct:alice@birdsite.example",
  "links": [
    {
      "rel": "https://corundum.example/ns/v1/did",
      "href": "did:webvh:<SCID>:birdsite.example:users:alice"
    }
  ]
}
```

The DID document then lists `acct:alice@birdsite.example` in `alsoKnownAs`. Account handles are the form operators give their users. WebFinger is also how Mastodon and other ActivityPub software look up accounts, so the same endpoint can serve both.

An account handle belongs to the operator's namespace, as an email address belongs to its mail provider. The operator controls the WebFinger answer, so it can reassign the handle, but it cannot make another DID claim it: bidirectional verification fails unless that DID's document also lists it. A user who leaves an operator normally leaves its account handles behind, along with their followers' memory of them. Their DID, followers, and content move with them. A user who wants a handle no operator controls uses a domain handle.

**Domain handles (DNS).** A domain handle `alice.example` is resolved with a TXT record:

```
_corundum.alice.example. 3600 IN TXT "did=did:webvh:<SCID>:birdsite.example:users:alice"
```

The DID document then lists `dns:alice.example` in `alsoKnownAs`. A resolver concatenates the character-strings of each TXT record at the name and considers only records that begin with `did=`. Exactly one such record MUST be present; zero or several is a resolution failure. Other records at the name are ignored. A DNS wildcard can make the name resolve for handles nobody set up, but that is harmless: bidirectional verification fails unless the DID document also lists the handle. The record names only the DID, not the IPNS name, so it does not go stale when the content key changes. Its integrity depends on DNS, so resolvers SHOULD validate DNSSEC where it is deployed.

**Requirements.** Implementations MUST support both methods. The verification is always: resolve the handle to a DID, check that the DID document lists the handle, and only then display the handle as the user's.
