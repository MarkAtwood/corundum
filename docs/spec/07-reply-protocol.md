## Part VII: The Reply Protocol

### Chapter 21: How Replies Work

Replies are the protocol's trickiest coordination problem. When Bob replies to Alice's post, the reply needs to appear in Alice's reply tree, which is hosted by Alice's operator. Bob publishes through his own operator. These two operators may never have interacted before.

Here is the complete reply flow, with timing notes:

**Step 1: Bob writes a reply.**
Bob's client submits the reply content to Bob's operator. Bob's operator creates the reply activity: an unsigned activity object with `inReplyTo` pointing to Alice's post's `id`. The operator creates the signing record. The reply CID and signing record CID are ready.

**Step 2: Bob's operator discovers Alice's operator.**
Bob's operator looks up Alice's IPNS name in its cache. If found and not expired, it has Alice's operator endpoint. If not found, it resolves Alice's IPNS name to get her RootManifest, reads the operator declaration, and caches the endpoint. This discovery step is typically sub-second for cached entries.

**Step 3: Bob's operator submits the reply.**
Bob's operator sends an authenticated HTTP POST to Alice's operator's reply submission endpoint. The request body is a `ReplySubmission`:

```json
{
  "@type": "corundum:ReplySubmission",
  "parentId": "bafyreib2vek...",
  "parentAuthor": "ipns://k51qzi5...",
  "reply": {
    "content": "bafyreid...",
    "contentHash": "sha256:3a7bd...",
    "signingRecord": {
      "@type": "corundum:SigningRecord",
      "content": "bafyreid...",
      "signer": "ipns://k51qzi5...bob...",
      "algorithm": "ed25519-v1",
      "signature": "7cKpTH..."
    }
  },
  "submittingOperator": "https://wobble.example"
}
```

Note that the signing record is included inline (not by CID) — this allows Alice's operator to verify Bob's authorship without an additional IPFS fetch.

**Step 4: Alice's operator validates.**
Alice's operator runs the following checks, roughly in order from cheapest to most expensive:

1. Is the HTTP Message Signature from Bob's operator valid? (Verify the request came from Wobble's declared key.)
2. Does Alice's policy accept replies from Wobble's trust level?
3. Is Bob's IPNS identity on Alice's block list? (Bloom filter fast-path: if definitely not blocked, proceed. If maybe blocked, check the full block list.)
4. Is the signing record's signature valid? (Does this activity actually come from Bob?)
5. Does the declared `contentHash` match the actual content?
6. Does the content pass curation checks? (Hash the content, check against subscribed curation feeds.)
7. Does the content pass rate limits?

If all checks pass: accepted. If any check fails: rejected with a specific reason code.

**Step 5: Acceptance or rejection.**
If accepted, Alice's operator links the reply into Alice's timeline's reply tree for the parent entry. The reply tree is an IPFS object — a Merkle tree of accepted replies. The operator returns a `ReplyAcceptance` with a position identifier.

If rejected, the operator returns a `ReplyRejection` with a reason code: `blocked-user`, `blocked-operator`, `policy-violation`, `curation-match`, `rate-limited`, `content-hash-mismatch`, etc.

```
Bob's Operator              Alice's Operator
     |                              |
     |-- ReplySubmission POST ----> |
     |                              |-- Check HTTP sig
     |                              |-- Check trust level
     |                              |-- Check block list
     |                              |-- Verify signing record
     |                              |-- Check content hash
     |                              |-- Check curation feeds
     |                              |-- Check rate limits
     |                              |
     |                              |-- [if accepted]
     |                              |   Update reply tree
     |                              |   Pin reply to IPFS
     |                              |
     | <-- ReplyAcceptance/---------|
     |     ReplyRejection           |
```

**What if Alice's operator is temporarily unreachable?**
Bob's operator uses an exponential backoff retry strategy. The first retry after 1 second, then 4, 16, 64 seconds, up to a configurable maximum delay (typically 1 hour). If the operator remains unreachable for more than 24 hours, the submission is abandoned and Bob's operator can optionally notify Bob's client. The reply is not silently dropped on the first failure; the retry window gives Alice's operator time to recover from transient outages.

**Reply tree portability:**
Reply trees contain only moderation-approved content: replies that passed all of Alice's block list, policy, and curation checks at the time of submission. Because the tree is already filtered, it is safe to treat as portable user data.

Reply trees MUST be stored as IPFS objects. The receiving operator pins the reply tree CID and updates it as new replies arrive. When Earl migrates from his self-hosted instance to Birdsite, Birdsite reads his reply trees from IPFS as part of the migration. The reply trees port with everything else.

In a hostile migration where the old operator did not publish final reply tree snapshots, the new operator starts with empty reply trees for historical entries. Users can provide a data export from their old operator (operators must provide data exports on request) that includes reply trees; the new operator accepts this as a seed.

### Chapter 22: Reply Policies

Reply policies give users control over who can engage with their content. They are per-user defaults but can be overridden per-post. When a post-level override exists, it applies instead of the user's default; when no override is set on a post, the user's default applies.

**Per-post policy overrides** are stored in the timeline entry's `replyPolicy` field. This is intentional: the policy travels with the entry in the archive, so any operator that fetches the entry can enforce it without querying a separate policy endpoint. A user can post a personal reflection with `"allowFrom": "mutuals-only"` while their default is `"allowFrom": "everyone"`, and the policy difference is self-contained in the entry.

**`allowFrom`** is the primary control:

- `"everyone"` — any authenticated submission is accepted for further evaluation. This does not bypass other checks (block list, curation, trust level); it only means that the set of candidate submitters is not restricted by relationship.
- `"followers-only"` — only operators whose users follow Alice can submit replies. Alice's operator checks the submitting operator against the followers cache: is the reply's author in Alice's followers list? The check is against the author's identity (IPNS), not the submitting operator. An operator can submit on behalf of a user who isn't a follower even if other users of that operator are followers; the per-user check is what matters.
- `"mutuals-only"` — only users that Alice follows back. The check requires looking up the reply author's identity in Alice's following list. This is the tightest social filter below "nobody": every allowed replier is someone Alice has explicitly chosen to engage with.
- `"mentioned-only"` — only users explicitly @mentioned in the post. The check is against the post's `mentions` field. This is useful for "announcement" style posts where the author wants to allow responses only from the people directly addressed.
- `"nobody"` — replies disabled. The operator immediately rejects any reply submission with `REPLY_REJECTED` and reason `replies-disabled`. Comments threads can be closed without deleting the post.

The "mutuals-only" setting is valuable for users who want a more intimate conversation environment. A journalist who broadcasts to a large audience might set "everyone" for most posts and "mutuals-only" for more personal ones. A researcher discussing sensitive topics might use "mutuals-only" to limit participation to people they know.

**`requireVerifiedIdentity`**: Only accept replies from users with DID-verified identity (not `did:key` users, who have unrecoverable identities). This is an accountability filter: `did:key` users cannot be recovered or verified through a chain back to any accountable entity. Requiring verified identity (via `did:web` or `did:plc`) means every replier has some form of accountable identity — a domain they control, or an operation-log DID with a known history.

**`requireMinimumTrustLevel`**: Only accept replies from operators at `authenticated-unknown` or higher (no anonymous submissions), or `authenticated-known` or higher (established operators only). This is a federation trust filter at the operator level rather than the user level. An operator with trust level `authenticated-unknown` has a valid manifest and signature but has never been explicitly verified or allowed-listed by Alice's operator. `authenticated-known` means the operator has been explicitly listed as a known peer. The distinction allows users to restrict their engagement to a curated set of operators they trust.

**`maxRepliesPerUser`** and **`rateLimitWindow`**: Optional rate limiting fields. A user can configure that any given identity may post at most N replies in a rolling time window. This prevents a single user from flooding a thread, whether or not they're on the block list. The operator enforces this by tracking per-author reply counts in the rate limit table.

**Fail-closed moderation** is the default posture: when there is any ambiguity, doubt, or failure in the validation chain, the reply is rejected. If Alice's operator cannot resolve the reply author's identity to check the followers list, the reply is rejected — not deferred, not accepted provisionally. If the curation feed is temporarily unreachable, the reply is held for retry rather than accepted. The asymmetry is intentional: a missed reply is a recoverable situation; abusive content that slips through because a check was skipped is harder to undo once it's in the thread and visible to followers. Operators that want fail-open behavior for research or testing must explicitly configure it.

### Chapter 23: Block Semantics

Blocks in Corundum are strong — stronger than blocks on most existing social platforms — by design.

When Alice blocks Steve:

- Alice never sees anything Steve posts anywhere.
- Alice never sees Steve's replies on her posts.
- **Nobody else sees Steve's replies on Alice's posts either** — Alice's operator rejects submissions from Steve's identity.
- Existing replies from Steve on Alice's posts are retroactively removed.
- Steve's follow of Alice is terminated.
- Alice's follow of Steve (if any) is terminated.

The alternative — "weak blocks" — would have Steve unable to see Alice's content in his feed and unable to see Alice's replies on his posts, but would still allow Steve to reply to Alice's posts, visible to others in the thread. Several existing platforms implement weak blocks. Corundum chose strong blocks because the weak variant fails the use case that matters most: a user being harassed should not have to watch their content become a venue for their harasser to perform harassment to the harasser's own audience, even if the harassed user doesn't see it directly.

The strong block is enforced at the architectural level, not the client level. Steve's operator's attempts to submit replies to Alice's content will be rejected by Alice's operator with `BLOCKED_USER`. No client-side filtering is involved; the architecture itself enforces it.

Retroactive removal is the most operationally significant part. When Alice blocks Steve, Alice's operator must scan her reply trees, find any replies from Steve's identity, remove them from the trees, and publish updated reply tree CIDs. This is not merely hiding Steve's replies from Alice's view; it is removing them from the publicly-accessible reply trees stored in IPFS. Anyone fetching Alice's reply tree after the block will not see Steve's replies.

### Chapter 24: Quotes vs. Replies

The protocol draws a sharp distinction between quotes and replies because they serve different social functions and have different protocol semantics.

A **reply** is a direct response that appears in the parent post's reply tree. It goes through the reply protocol, requires the parent operator's cooperation, and is subject to the parent user's policies. The parent author controls whether a reply appears in their thread.

A **quote** is content that embeds or references another activity, published on the quoting user's own timeline. It does not appear in the quoted post's reply tree. It does not go through the reply protocol. The quoting user simply creates a new activity with a reference to the quoted content. The quoted author has no veto over being quoted.

This distinction maps to a real social norm: there is a difference between replying to someone (entering their conversational space, asking permission to participate in their thread) and writing a post that references their content (speaking from your own space, building on or reacting to their content). The first requires cooperation; the second does not.

The practical consequence: a user cannot be prevented from quoting someone (it's published on the quoting user's own timeline, under their operator's policies), but a block will prevent the quote from showing up as a reply in the original author's thread. If Steve quotes Alice's post from his own timeline, Alice won't see it (she blocked Steve, so his content is filtered from her feed), but Steve hasn't violated Alice's conversational space in the way that submitting a reply would.

---

