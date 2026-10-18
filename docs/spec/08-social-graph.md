## Part VIII: The Social Graph

### Chapter 25: Follows, Blocks, and Mutes

The social graph is stored as part of the user's RootManifest, so it is signed by the user's content keys and moves with the user's identity. A user who changes operator takes their follows, blocks, and mutes with them, even if the old operator does not cooperate.

**Following list**: The DIDs the user follows, each with the time the follow began and an optional label or list assignment. Following lists are private by default (see "Encrypted lists" below). A user may also publish all or part of their following list as a plaintext list, which the RootManifest names separately; friend-of-friend discovery works only through published lists.

**Block list**: The DIDs, and optionally the operator domains, the user has blocked. Block lists are always encrypted, so no one but the user and their operator can read them. A block is not secret from the person blocked: their operator learns of it, because their replies are rejected with the reason `blocked-user` and because the blocking operator sends a BlockNotification (Chapter 26). What the encryption protects is the list as a whole: no one can read it to learn whom else the user has blocked, or to find which of their own accounts are not yet blocked.

**Mute list**: Similar to blocks but softer. Muted users are hidden from the muting user's view but can still interact. Mutes are purely operator-side filtering. The muted user doesn't know and their content is still accepted. A mute doesn't affect reply submissions — muted users can still reply; the replies just aren't shown to the muting user. Mutes can be timed (mute for 24 hours, 7 days, indefinitely). Mute lists are always encrypted.

**Followers cache**: The operator's record of who follows the user, built from the signed FollowNotifications it has received (Chapter 26). Following lists are private, so these notifications are the only evidence a user's operator has of who follows them. The operator keeps each notification as the proof of that follow.

**Encrypted lists.** The following list (except any part the user publishes), the block list, and the mute list are each stored as a JWE (RFC 7516) in the General JSON Serialization, with content encryption `A256GCM` and two recipients, each using key agreement `ECDH-ES+A256KW` with an X25519 key (RFC 8037):

- the user's **list key**, an X25519 public key named in the `listKey` member of the user's `CorundumIdentity` service entry (Chapter 6); and
- the current operator's encryption key, from its Operator Manifest (Chapter 18).

The operator decrypts the lists to enforce blocks and mutes and to build the user's feed. The user's list key is what makes the lists portable. Its private half is kept with the user's recovery material (Chapter 7), and the user's client may keep a copy. Because the list key is named in the DID document, only the user's update key can change it, so an operator cannot quietly encrypt the lists to a key the user does not hold.

A list too large for one object (Chapter 33) is split into several JWEs, and the RootManifest names them in order. The RootManifest commits to each list's CID, so the lists are authenticated by the same signature as the rest of the manifest. Encryption hides who is on a list but not when it changes or roughly how long it is: each change produces a new CID, and the ciphertext length tracks the plaintext length. Writers SHOULD pad the plaintext to a multiple of 4,096 bytes.

**Moving lists to a new operator.** Every change of recipient produces a new JWE with a fresh content encryption key, encrypted to the user's list key and the new operator's key. In a cooperative move, the old operator re-encrypts the lists for the new operator. In a hostile move, the user's client decrypts the lists with the user's list key and re-encrypts them for the new operator. The old operator can still read the lists it already had; nothing can take back what it already knew.

### Chapter 26: Cross-Operator Graph Synchronization

The social graph is eventually consistent across operators. Notifications are best-effort with retries; there is no two-phase commit. This means there are windows where different operators have different views of who follows whom, or whether a block has propagated. The protocol is designed around this reality rather than pretending it can be avoided.

**FollowNotification.** A FollowNotification is an attached JWS (Chapter 34) with `corundumType` `"FollowNotification"`, signed by the follower's content keys. Its payload names the follower's DID, the followee's DID, whether this is a follow or an unfollow, and the time (Chapter 20 gives its format). It is sent to the followee's operator as an authenticated inter-operator request (Chapter 19). Because following lists are private, the signed notification is how the followee's operator knows the follow is real, and it is what that operator relies on when it enforces followers-only replies (Chapter 22).

**The follow protocol:**

1. Alice decides to follow Bob.
2. Alice's operator adds Bob's DID to Alice's following list, re-encrypts it, and publishes an updated RootManifest. This is the authoritative record of what Alice follows.
3. Alice's operator MUST send a FollowNotification to Bob's operator, found from Bob's DID document. Every follow is notified: following someone is never invisible to the person followed.
4. Bob's operator verifies the notification's signature against Alice's DID document, checks Bob's block list, and applies its federation policies. If Bob has blocked Alice, it rejects the notification with `NOTIFICATION_REJECTED` and reason `blocked-user`.
5. If accepted, Bob's operator records the follow in Bob's followers cache, keeping the notification as proof, and Alice's operator may subscribe to Bob's operator's event stream to receive Bob's new posts (Chapter 47).

**Notification failure and retries.** When Alice's operator cannot reach Bob's operator (network partition, server down, DNS failure), it queues the notification for retry, with exponential backoff and a maximum of 7 days. If the notification is lost anyway, the follow still exists in Alice's manifest, but Bob's operator does not know about it. The gap is repaired when it matters: if Alice replies to a followers-only post of Bob's, Bob's operator rejects the reply with a retryable reason, and Alice's operator resends the FollowNotification and retries the reply (Chapter 22).

**Unfollow** is handled the same way: Alice's operator removes Bob from her following list and sends a FollowNotification marked as an unfollow, and Bob's operator removes Alice from Bob's followers cache. A later notification supersedes an earlier one for the same pair. If an unfollow is lost, Bob's operator goes on believing Alice follows Bob, which at most lets her reply to his followers-only posts until he blocks her or the notification is retried.

**The block protocol:**

1. Alice blocks Steve.
2. Alice's operator adds Steve to Alice's block list, re-encrypts it, and publishes an updated RootManifest. The block takes effect immediately for Alice's operator: it begins rejecting all submissions from Steve, checking each submission against Alice's block list directly.
3. Alice's operator removes Steve from Alice's followers cache.
4. Alice's operator SHOULD send a `BlockNotification` to Steve's operator, as an authenticated inter-operator request (Chapter 19) naming Alice's and Steve's DIDs. Steve's operator stops retrying any pending submissions from Steve to Alice and ends Steve's follow of Alice. The notification only saves wasted traffic: Steve's operator would learn of the block from the first rejection anyway.
5. Alice's operator removes Steve's existing replies from Alice's reply trees and republishes its ReplyMap (Chapter 10). The removal is not instantaneous — it may take a few minutes. Until it completes, Steve's existing replies remain in the current trees, and copies of the old trees may stay cached elsewhere; once the ReplyMap is republished, readers that follow it no longer see them.
6. Alice's operator permanently rejects any future submissions from Steve, and from Steve's operator if Alice has blocked the whole operator.

**Mutes** are handled differently from blocks. A mute is local to the muting user's operator: Alice's operator simply filters Steve's content from Alice's feed. No notification is sent to Steve or Steve's operator. Steve can still reply to Alice's posts (his submissions go through the reply protocol, and Alice's operator accepts them if Steve is not blocked), but Alice will not see his replies in her own view. The mute is invisible to the network; only Alice's operator knows about it. This matches user expectations: muting someone is a personal coping mechanism, not a social statement.

**Eventual consistency consequences.** There is no global lock on the social graph. When Alice blocks Steve, there may be a brief window where Steve's pending reply (in transit from Steve's operator to Alice's operator) is still accepted by Alice's operator before the block is fully in effect. This is acceptable: the reply will be retroactively removed during the retroactive scan. Operators should not build logic that assumes blocks are atomic with respect to in-flight messages.

---

