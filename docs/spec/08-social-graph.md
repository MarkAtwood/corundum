## Part VIII: The Social Graph

### Chapter 25: Follows, Blocks, and Mutes

The social graph is stored as part of the user's RootManifest. Because the RootManifest is an IPFS object signed by the user's IPNS key, the user's social graph is cryptographically authored by the user and portable with their identity.

**Following list**: An array of IPNS identities the user follows, each with a timestamp, optional label/list assignment, and a signature. The following list is public by default (operators can offer privacy options). When Alice follows Bob, her operator sends a FollowNotification to Bob's operator, which updates Bob's followers cache.

**Block list**: An array of blocked identities. Block lists are private by default and should never be exposed to the blocked user, other users, or the general public. Exposing block lists would allow blocked users to know they're blocked, which enables harassment patterns where abusers probe block lists to find gaps. Block entries can be for specific identities or entire operators.

Block list membership verification uses two techniques:

- **Bloom filter**: A Bloom filter is a compact probabilistic data structure built on a bit-array and a set of independent hash functions. To add an element to the filter, you compute several hash functions over that element and set the corresponding bits in the array to 1. To test whether an element is in the set, you compute the same hash functions and check whether all the corresponding bits are 1. If any bit is 0, the element is definitely not in the set. If all bits are 1, the element is probably in the set — but not certainly, because different elements can hash to overlapping bit positions.

  This gives a Bloom filter a characteristic guarantee: it never produces false negatives (if something is in the set, the filter will always say so), but it can produce false positives at a tunable rate (elements not in the set may occasionally be reported as present). With typical parameters, a 1% false positive rate is achievable with about 10 bits per element and a handful of hash functions.

  Why Bloom filters are appropriate for block lists specifically: Alice's block list may contain thousands of entries. Most incoming replies are from people Alice has not blocked. Without a Bloom filter, every incoming reply submission would require a membership check against a potentially large block list — a list that can't be handed to the submitting operator because that would reveal who Alice has blocked. The Bloom filter solves the common case efficiently: the filter is a compact summary (a few kilobytes even for thousands of entries) that can be checked locally. If the filter says "definitely not blocked," the operator proceeds without any list lookup. Only when the filter says "probably blocked" — roughly 1% of non-blocked senders — does the operator need the authoritative answer.

  This matters at scale. An operator serving a user with 5,000 blocked identities and receiving hundreds of reply attempts per hour would face constant full-list lookups without the Bloom filter. With the filter, the vast majority of lookups terminate immediately on a local bit check.

  When the Bloom filter indicates "probably blocked," the operator must perform an authoritative check to determine whether the match is a true positive or a false positive. The authoritative check must not reveal the full block list to the submitting operator — that would violate Alice's privacy by exposing who she has blocked. Instead, the receiving operator provides a **Merkle proof**: a cryptographic path through a Merkle tree of the block list that demonstrates either that the queried identity IS present or that it IS NOT present, without revealing any other entries. A proof of non-membership shows where the identity would appear in the sorted tree and that no entry occupies that position. The submitting operator receives a proof about one specific identity, not about any others.

  At a 1% false positive rate, roughly 1 in 100 non-blocked senders triggers the "probably blocked" response and the Merkle proof path. In practice this is acceptable: the Merkle proof is fast to compute and verify, and the 99% common case (fast negative) requires only the local Bloom filter check.

- **Merkle proof**: For authoritative verification (e.g., when an operator needs to definitively confirm a specific identity is or isn't blocked), operators can provide Merkle proofs. A proof that an identity is NOT in the block list is a path through the Merkle tree that shows where the identity would appear if it were present, and that no entry exists there.

  The privacy property of this two-layer system is important. Publishing the full block list would reveal exactly who Alice has blocked — private information that could be used for harassment (a blocked user discovering they are blocked and escalating, or a harasser probing the list to find which of their accounts is not yet blocked). The Bloom filter, by contrast, reveals only a bound on the number of blocked identities (roughly inferable from the bit-array size) and allows membership testing without revealing the list contents. The Merkle proof reveals only the presence or absence of one specific queried identity. Alice's full block list remains private.

**Mute list**: Similar to blocks but softer. Muted users are hidden from the muting user's view but can still interact. Mutes are purely client-side/operator-side filtering. The muted user doesn't know and their content is still accepted. A mute doesn't affect reply submissions — muted users can still reply; the replies just aren't shown to the muting user. Mutes can be timed (mute for 24 hours, 7 days, indefinitely).

**Followers cache**: A non-authoritative cache of identities following the user, maintained by the operator from incoming follow notifications. This is a cache, not a source of truth. The source of truth for "who follows Alice" is distributed across all operators whose users follow Alice — it's encoded in those users' following lists, which are stored on their respective operators. No single operator has a complete authoritative count of Alice's followers. The followers cache is the operator's best approximation, used for notification routing and analytics.

### Chapter 26: Cross-Operator Graph Synchronization

The social graph is eventually consistent across operators. Notifications are best-effort with retries; there is no two-phase commit. This means there are windows where different operators have different views of who follows whom, or whether a block has propagated. The protocol is designed around this reality rather than pretending it can be avoided.

**The follow protocol:**

1. Alice decides to follow Bob.
2. Alice's operator adds Bob's IPNS to Alice's following list and signs the updated RootManifest. This is the authoritative record: Alice's signed manifest is the ground truth of her follow list, regardless of whether notifications succeed.
3. Alice's operator sends a signed `FollowNotification` to Bob's operator (discovered from Bob's RootManifest via IPNS). The notification is authenticated with an HTTP Message Signature (RFC 9421) so Bob's operator can verify it came from Alice's actual operator.
4. Bob's operator validates the notification: checks Alice's signature in the notification body, checks Bob's block list for Alice, and checks any operator-level federation policies. If Alice is on Bob's block list, the notification is silently dropped — Bob is not notified that Alice attempted to follow him, because that information is useful to a harasser.
5. If accepted, Bob's operator updates Bob's followers cache and may begin proactively pushing Bob's timeline updates to Alice's operator (if the operators have an established streaming relationship and Alice's operator has subscribed).

**Notification failure and retries.** When Alice's operator cannot reach Bob's operator (network partition, server down, DNS failure), it queues the notification for retry. The retry schedule is exponential backoff with a maximum TTL of 7 days. After 7 days, the follow still exists in Alice's signed manifest (the ground truth), but no further notification attempts are made. When Bob's operator comes back online, the normal mechanism for catching up is for Bob's operator to pull Alice's current RootManifest, which will reflect the follow. The eventual convergence guarantee is: as long as Alice's manifest is eventually fetchable and Bob's operator eventually polls it (via social graph synchronization or when Alice's operator retries), the follow will be reflected on Bob's side.

**Unfollow** is handled similarly: Alice removes Bob from her following list, signs the updated manifest, and sends an `UnfollowNotification`. Bob's operator removes Alice from Bob's followers cache. If the notification is lost, the discrepancy is resolved the next time Bob's operator fetches Alice's manifest and finds Bob absent from the following list. Followers caches are therefore soft state — they should be periodically reconciled against the authoritative manifests they mirror.

**The block protocol:**

1. Alice blocks Steve.
2. Alice's operator adds Steve to Alice's block list and signs the updated social graph. The block takes effect immediately for Alice's operator: it begins rejecting all submissions from Steve's identity.
3. Alice's operator sends a `BlockNotification` to Steve's operator. The notification has two effects at Steve's operator: it terminates Steve's follow of Alice (removes Alice from Steve's following list from Steve's operator's perspective, though Steve's own manifest is the authority), and it provides an opportunity for Steve's operator to clean up any pending reply submissions from Steve to Alice.
4. Alice's operator scans Alice's reply trees for Steve's replies and retroactively removes them from the tree structures stored in IPFS. The retroactive removal is not instantaneous — it may take a few minutes to republish the affected tree CIDs. During the window between the block being placed and the retroactive removal completing, Steve's existing replies remain visible in the old (now-superseded) tree CIDs. Once Alice's operator publishes the updated trees, those CIDs are superseded by the new ones referenced in Alice's RootManifest.
5. Alice's operator permanently rejects any future submissions from Steve's IPNS identity and from Steve's operator if operator-level blocking is configured.

**Mutes** are handled differently from blocks. A mute is local to the muting user's operator: Alice's operator simply filters Steve's content from Alice's feed. No notification is sent to Steve or Steve's operator. Steve can still reply to Alice's posts (his submissions go through the reply protocol, and Alice's operator accepts them if Steve is not blocked), but Alice will not see his replies in her own view. The mute is invisible to the network; only Alice's operator knows about it. This matches user expectations: muting someone is a personal coping mechanism, not a social statement.

**Eventual consistency consequences.** There is no global lock on the social graph. When Alice blocks Steve, there may be a brief window where Steve's pending reply (in transit from Steve's operator to Alice's operator) is still accepted by Alice's operator before the block is fully in effect. This is acceptable: the reply will be retroactively removed during the retroactive scan. Operators should not build logic that assumes blocks are atomic with respect to in-flight messages.

---

