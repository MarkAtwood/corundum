## Part VII: The Reply Protocol

### Chapter 21: How Replies Work

Replies are the protocol's trickiest coordination problem. When Bob replies to Alice's post, the reply needs to appear in Alice's reply tree, which is hosted by Alice's operator. Bob publishes through his own operator. These two operators may never have interacted before.

**The reply tree defines the thread.** An activity's `inReplyTo` is only the replier's claim. A reply is part of Alice's thread when, and only when, Alice's operator has accepted it into the reply tree for her post. Alice's operator publishes reply trees through its ReplyMap (Chapter 10): the ReplyMap slot for the post's `seq` holds the CID of its reply tree. Readers MUST NOT present an activity as a reply in a thread because of its `inReplyTo` alone; an activity that names Alice's post but is absent from its reply tree is Bob's own post, which may quote or reference hers (Chapter 24).

Here is the complete reply flow:

**Step 1: Bob writes a reply.**
Bob's client submits the reply content to Bob's operator. Bob's operator creates the reply activity, with `inReplyTo` set to the identifier of Alice's post, appends it to Bob's timeline, and signs it, producing its SigningRecord (Chapter 12). For a self-custody user, Bob's client signs instead.

**Step 2: Bob's operator discovers Alice's operator.**
Bob's operator reads Alice's DID from her post's `attributedTo`, resolves her DID document (or uses a cached copy), and reads the `operatorEndpoint` of her `CorundumIdentity` service entry (Chapter 20).

**Step 3: Bob's operator submits the reply.**
Bob's operator sends an authenticated HTTP POST (Chapter 19) to Alice's operator's reply submission endpoint. The request body is a `ReplySubmission`:

```json
{
  "@type": "corundum:ReplySubmission",
  "parentId": "<identifier of Alice's post>",
  "parentAuthor": "did:webvh:<SCID>:birdsite.example:users:alice",
  "reply": {
    "id": "<identifier of Bob's reply>",
    "activity": "<base64url of the reply activity's bytes>",
    "signingRecord": "<base64url of the reply's SigningRecord bytes>"
  },
  "submittingOperator": "https://wobble.example"
}
```

The activity and its SigningRecord travel inline, as their exact bytes. Alice's operator can verify and store the reply without fetching anything from IPFS, and because the bytes are never re-serialized, it can check them against the reply's identifier directly.

**Step 4: Alice's operator validates.**
Alice's operator checks, roughly from cheapest to most expensive, that:

1. the HTTP Message Signature is valid and comes from the operator named in `submittingOperator`;
2. the bytes match the reply's identifier, and the reply's `inReplyTo` is Alice's post;
3. the reply's author is a user of the submitting operator;
4. neither the author nor the submitting operator is blocked (a local lookup in Alice's block list and the operator's own federation policy);
5. the SigningRecord is a valid signature by the author's current keys;
6. the reply is allowed by the reply policy of Alice's post (Chapter 22);
7. the content passes the curation feeds Alice's operator enforces (Chapter 28);
8. the submission is within rate limits.

**Step 5: Acceptance or rejection.**
If accepted, Alice's operator stores and pins the reply and its SigningRecord, adds them to the reply tree for Alice's post, and republishes its ReplyMap. It returns a `ReplyAcceptance`. If rejected, it returns a `ReplyRejection` with a reason code.

```
Bob's Operator              Alice's Operator
     |                              |
     |-- ReplySubmission POST ----> |
     |                              |-- Check HTTP signature
     |                              |-- Check bytes, CID, inReplyTo
     |                              |-- Check author's operator
     |                              |-- Check blocks
     |                              |-- Verify SigningRecord
     |                              |-- Check reply policy
     |                              |-- Check curation feeds
     |                              |-- Check rate limits
     |                              |
     |                              |-- [if accepted]
     |                              |   Pin reply and SigningRecord
     |                              |   Update reply tree, ReplyMap
     |                              |
     | <-- ReplyAcceptance/---------|
     |     ReplyRejection           |
```

**What if Alice's operator is temporarily unreachable?**
Bob's operator retries with exponential backoff: after 1 second, then 4, 16, 64 seconds, up to a configurable maximum delay (typically 1 hour). If the operator remains unreachable for more than 24 hours, the submission is abandoned and Bob's operator can optionally notify Bob's client. A retry must still pass check 7 against the author's keys at the time of the retry: if the author's content keys changed in the meantime (a rotation or a move), the author's operator re-signs the reply with the current keys, producing a new SigningRecord for the same activity, before retrying. Retrying is always safe, because submission is idempotent: a reply that was accepted on an attempt whose response was lost is simply acknowledged again.

**Edited replies.** When Bob edits his reply, the new version (an activity with `replaces`; Chapter 13) is submitted as a new reply and validated from scratch. If it is accepted, Alice's operator puts it in the reply tree in place of the version it replaces. If it is rejected, the tree keeps the version that was accepted.

**Reply tree portability:**
Reply trees contain only moderation-approved content: replies that passed all of Alice's block list, policy, and curation checks at the time of submission. Because the tree is already filtered, it is safe to treat as portable user data.

Reply trees MUST be stored as IPFS objects, named by the ReplyMap. When Earl migrates from his self-hosted instance to Birdsite, Birdsite fetches the old operator's ReplyMap from IPFS (its IPNS name is in Earl's last RootManifest), and publishes a new ReplyMap starting from a copy of it (Chapter 10). This works in a hostile migration too: the old ReplyMap and its reply trees are already in IPFS, and the new operator needs nothing from the old one but the ability to fetch them, from the old operator's node while it runs or from any other node that kept them.

### Normative Reply Submission Specification

**Endpoint declaration.** Operators that declare `capabilities.replies: true` in their Operator Manifest MUST expose:

```
POST /corundum/v1/replies/submit
Content-Type: application/json
```

The request MUST be authenticated per Chapter 19. The request body MUST be a `ReplySubmission` object.

**`ReplySubmission` schema:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `@type` | string | REQUIRED | MUST be `"corundum:ReplySubmission"` |
| `parentId` | string | REQUIRED | Identifier of the parent post (Chapter 33). |
| `parentAuthor` | string | REQUIRED | DID of the parent post's author. |
| `reply.id` | string | REQUIRED | Identifier of the reply activity. |
| `reply.activity` | string | REQUIRED | The reply activity's exact bytes, base64url-encoded without padding. The decoded bytes MUST NOT exceed 1,048,576 bytes (Chapter 33). |
| `reply.signingRecord` | string | REQUIRED | The reply's SigningRecord (Chapter 12), as its exact bytes, base64url-encoded without padding. |
| `submittingOperator` | string | REQUIRED | Origin of the submitting operator. MUST equal its manifest `id` and the origin of the request's `keyid` (Chapter 19). |

**Validation.** The receiving operator MUST perform these checks and MUST reject the submission with the given reason if one fails. It MAY perform them in any order, but MUST NOT accept a submission until all of them pass.

1. **Authentication.** The request is authenticated per Chapter 19, and `submittingOperator` is the sending origin. Otherwise `invalid-operator-signature` or `insufficient-signature-coverage`.
2. **Form.** The body is a valid `ReplySubmission`; `reply.activity` decodes to I-JSON (Chapter 33) within the size limit; its CID equals `reply.id`; and its `inReplyTo` equals `parentId`. Otherwise `malformed-submission`.
3. **Already decided.** If `reply.id` is already in the parent's reply tree, the operator MUST make no change and return `200` with a `ReplyAcceptance` carrying the original `acceptedAt`. If the reply's author has deleted it or replaced it with an edit — its slot in the author's StateMap (Chapter 10) has `deletedBy` or `replacedBy` — the operator MUST reject it with `reply-withdrawn`. The author's StateMap is public and moves with the author, so this check needs no record kept by the parent's operator and survives the parent's migration. Every other resubmission is evaluated again from the start.
4. **Parent.** `parentAuthor` is a user of this operator and `parentId` identifies a post in their timeline that is not deleted. If the operator does not host `parentAuthor`, it resolves the DID; if the DID document names another operator, it rejects with `parent-migrated` and puts that operator's origin in `details.currentOperator`; otherwise `unknown-parent`.
5. **Author's operator.** The reply's author is the DID in its `attributedTo`. The operator resolves the author's DID document (Chapter 6), and its `operatorEndpoint` MUST equal `submittingOperator`. Otherwise `author-operator-mismatch`. An operator may submit replies only for its own users.
6. **Blocks.** If the parent author has blocked the reply's author, `blocked-user`. If the parent author has blocked the submitting operator, or this operator's federation policy refuses it, `blocked-operator`. Both are local lookups (Chapter 25).
7. **Content signature.** The SigningRecord verifies over the activity bytes under Chapter 34, with `corundumType` `"Activity"`, as an activity not yet in an archive: it carries a valid signature by every key in the author's current required set. Otherwise `invalid-content-signature`.
8. **Time.** The activity's `published` time is no more than 5 minutes in the future (Chapter 34). Otherwise the error `TIMESTAMP_SKEW`.
9. **Reply policy.** The reply is allowed by the parent's reply policy (Chapter 22). Otherwise `replies-disabled`, `follow-not-yet-known`, or `policy-violation`.
10. **Curation.** The content matches no curation entry this operator enforces. Otherwise `curation-match`.
11. **Rate limits.** The submission is within this operator's limits and the policy's `maxRepliesPerUser`. Otherwise `rate-limited`.

If the activity has a `replaces` member naming a reply in the parent's reply tree by the same author, then on acceptance the new version takes that reply's place in the tree, and the old version is withdrawn (check 3). Otherwise it is accepted as a new reply.

If a check cannot be completed because something the operator depends on is unavailable, the operator MUST NOT accept the reply. It returns `DID_RESOLUTION_FAILED` (`502`) when the author's or parent author's DID document cannot be fetched, and `503 Service Unavailable` for other transient failures; the submitter retries with backoff.

**On acceptance**, the operator MUST store and pin the activity and SigningRecord bytes exactly as received (their CIDs are computed over those bytes), add the reply to the parent's reply tree, and update the parent's slot in its ReplyMap (Chapter 10).

**Deleting a reply.** When the author of an accepted reply deletes it (Chapter 13), the author's operator MUST submit the `Delete` activity to the parent's operator through the same endpoint, as a `ReplySubmission` whose `reply` is the `Delete` activity and whose `parentId` is the post the deleted reply answered. For such a submission, check 2 requires the `Delete`'s `object` to name a reply in that post's reply tree instead of requiring `inReplyTo`, and checks 9 to 11 do not apply. On acceptance, the operator removes the reply from the tree; check 3 then rejects any resubmission of it.

**Reply tree format.** A reply tree lists the direct replies to one post; a reply to a reply belongs to the reply tree of the post it answers, published by that post's author's operator. It is a chain of `corundum:ReplyList` pages, each at most 1 MiB (Chapter 33):

```json
{
  "@type": "corundum:ReplyList",
  "replies": [
    { "id": "<identifier of the reply>", "signingRecord": "<CID of its SigningRecord>", "acceptedAt": "2025-03-15T14:30:12Z" }
  ],
  "next": "<CID of the next, older page, or null>"
}
```

Replies appear newest first. The ReplyMap slot holds the CID of the first page. Adding a reply rewrites the first page, starting a new one when it is full; removing one rewrites the page that holds it and every page before it in the chain. Reply trees are not part of the author's archive, so these rewrites never touch it.

**Replies to edited posts.** A post's thread is keyed by its original version. When a post has been edited, its versions form a chain through `replaces` (Chapter 13), and replies to any version are stored in the reply tree in the ReplyMap slot of the original version's `seq`. A reader holding any version finds the thread by following `replaces` back to the original.

**`ReplyAcceptance` response:**

HTTP status `200 OK`. `Content-Type: application/json`.

| Field | Type | Description |
|-------|------|-------------|
| `@type` | string | MUST be `"corundum:ReplyAcceptance"` |
| `parentId` | string | Identifier of the parent post. Echoed from the submission. |
| `replyId` | string | Identifier of the accepted reply. Echoed from the submission. |
| `replyTreeCid` | string | CID of a reply tree for the parent that contains this reply. |
| `acceptedAt` | string | RFC 3339 datetime when the reply was first accepted. |

**`ReplyRejection` response:**

`Content-Type: application/json`. A `ReplyRejection` is a `corundum:Error` (Chapter 37) with these fields:

| Field | Type | Description |
|-------|------|-------------|
| `@type` | string | MUST be `"corundum:Error"` |
| `code` | string | MUST be `"REPLY_REJECTED"` |
| `message` | string | Human-readable explanation for operators and logs. Not for display to end users. |
| `httpStatus` | integer | The HTTP status from the table below. |
| `retryable` | boolean | `true` only when `details.reason` is `"rate-limited"` or `"follow-not-yet-known"`. |
| `details.reason` | string | Machine-readable reason code (normative list below). |
| `details.parentId` | string | Identifier of the parent post. Echoed from the submission. MAY be absent if the submission was too malformed to parse. |
| `details.replyId` | string | Identifier of the rejected reply. MAY be absent for the same reason. |
| `details.retryAfter` | integer | OPTIONAL. Seconds until the submitter MAY retry. MUST be present when `reason` is `"rate-limited"`. |
| `details.currentOperator` | string | Present only with `parent-migrated`: the origin the parent author's DID document now names. |

**HTTP status codes and normative reason codes:**

| HTTP Status | `reason` | Meaning |
|-------------|----------|---------|
| `200 OK` | — | Reply accepted, or already accepted. Body is `ReplyAcceptance`. |
| `400 Bad Request` | `malformed-submission` | The body is invalid or missing required fields, the activity is too large or not I-JSON, its CID is not `reply.id`, or its `inReplyTo` is not `parentId`. |
| `400 Bad Request` | `invalid-content-signature` | The SigningRecord does not verify, or lacks a signature by a key in the author's required set. |
| `401 Unauthorized` | `invalid-operator-signature` | The request's HTTP Message Signature is absent, invalid, expired, or by an unknown or revoked key, or `submittingOperator` is not the signing origin (Chapter 19). |
| `401 Unauthorized` | `insufficient-signature-coverage` | The request lacks a valid signature by an active key of the submitting operator (Chapter 19). |
| `403 Forbidden` | `author-operator-mismatch` | The reply's author's DID document does not name the submitting operator. |
| `403 Forbidden` | `blocked-user` | The parent author has blocked the reply's author. |
| `403 Forbidden` | `blocked-operator` | The parent author or this operator's federation policy blocks the submitting operator. |
| `403 Forbidden` | `policy-violation` | The reply violates the parent's reply policy for a reason other than those below. |
| `403 Forbidden` | `replies-disabled` | The parent's reply policy is `allowFrom: nobody`. |
| `403 Forbidden` | `curation-match` | The reply content matches a curation entry this operator enforces. |
| `404 Not Found` | `unknown-parent` | `parentId` is not a current post of `parentAuthor` on this operator, and the author has not moved elsewhere. |
| `409 Conflict` | `follow-not-yet-known` | The policy requires the reply's author to follow the parent author, and this operator has no FollowNotification for that follow (Chapter 22). |
| `410 Gone` | `parent-migrated` | The parent author has moved to another operator, named in `details.currentOperator`. |
| `410 Gone` | `reply-withdrawn` | The reply was deleted by its author or replaced by an accepted edit, and cannot be resubmitted. |
| `429 Too Many Requests` | `rate-limited` | Rate limit exceeded. `Retry-After` header and `details.retryAfter` MUST both be present, with the same value in seconds. |

The reply endpoints also use these generic codes (Chapter 37): `TIMESTAMP_SKEW` (`400`) for a `published` time too far in the future, `DID_RESOLUTION_FAILED` (`502`) when a DID document cannot be fetched, and `503 Service Unavailable`, whose body MAY be absent, for other transient failures. The submitter MUST retry the retryable ones with exponential backoff.

The reason code list is normative. Receiving operators MUST use one of the defined codes. Submitting operators MUST handle unknown reason codes gracefully by treating them as the generic meaning of the HTTP status code.

**Handling `parent-migrated`.** `details.currentOperator` is a hint. The submitter MUST resolve the parent author's DID itself and submit to the operator the DID document names.

**Batch submission.** Operators that declare `capabilities.batchSubmission: true` MUST expose `POST /corundum/v1/replies/batch`, authenticated per Chapter 19. The body is:

```json
{
  "@type": "corundum:ReplyBatch",
  "submissions": ["<ReplySubmission>", "<ReplySubmission>"]
}
```

`submissions` holds 1 to 100 `ReplySubmission` objects, all with the same `submittingOperator`, and the body MUST NOT exceed 8,388,608 bytes. The receiver evaluates each submission exactly as if it had arrived alone. If the request as a whole fails (authentication, a malformed or oversized batch), the response is a single error: `REPLY_REJECTED` with the reason the single endpoint would use, or `INVALID_REQUEST` for a batch that exceeds the limits. Otherwise the response is `200 OK` with:

```json
{
  "@type": "corundum:ReplyBatchResult",
  "results": ["<ReplyAcceptance or corundum:Error>", "<ReplyAcceptance or corundum:Error>"]
}
```

`results` has one entry per submission, in the same order: the `ReplyAcceptance` or the error (with its `httpStatus`) that the single endpoint would have returned for it. The submitter retries only the entries whose errors are retryable.

### Chapter 22: Reply Policies

Reply policies give users control over who can engage with their content.

**The policy is part of the post.** A post's reply policy is the `replyPolicy` member of the activity itself, so it is signed by the author and travels with the post: any operator that holds the post can enforce it without querying a separate policy endpoint. Because an activity never changes, the policy changes only through an edit (Chapter 13). The parent's operator applies the policy of the newest version of the post that the author's StateMap names, so an author can close replies on a post by editing it.

```json
"replyPolicy": {
  "allowFrom": "mutuals-only",
  "requireRecoverableIdentity": true,
  "maxRepliesPerUser": 5,
  "rateLimitWindow": 3600
}
```

A post without `replyPolicy` accepts replies from everyone. A user's "default policy" is an operator or client setting that fills in `replyPolicy` when a post is created; changing it does not change posts already published.

**`allowFrom`** is the primary control:

- `"everyone"` — any authenticated submission is accepted for further evaluation. This does not bypass other checks (blocks, curation, rate limits); it only means that the set of candidate submitters is not restricted by relationship.
- `"followers-only"` — only users who follow Alice. Alice's operator checks the reply's author against Alice's followers cache, which holds the signed FollowNotifications it has received (Chapter 26). The check is against the author's DID, not the submitting operator: an operator cannot submit on behalf of a user who isn't a follower because other users of that operator are.
- `"mutuals-only"` — only users who follow Alice and whom Alice follows. Both directions are checked: the author must be in Alice's followers cache, and in Alice's following list. This is the tightest social filter below "nobody": every allowed replier is someone Alice has explicitly chosen to engage with, and who has chosen to follow her.
- `"mentioned-only"` — only users explicitly @mentioned in the post. The check is against the DIDs in the post's `Mention` tags. This is useful for "announcement" style posts where the author wants to allow responses only from the people directly addressed.
- `"nobody"` — replies disabled. The operator rejects any reply submission with reason `replies-disabled`. Threads can be closed without deleting the post.

**A missing follow is not a final answer.** Following lists are private, so Alice's operator knows that Bob follows Alice only if it received Bob's FollowNotification, and a notification can be lost (Chapter 26). When `followers-only` or `mutuals-only` requires a follow that Alice's operator has no record of, it rejects the reply with `follow-not-yet-known`. If Bob does follow Alice, Bob's operator resends the FollowNotification and then resubmits the reply. If Bob does not follow Alice, Bob's operator treats the rejection as final. When the failed check is Alice following Bob (for `mutuals-only`), Alice's operator holds her following list and its answer is final: `policy-violation`.

The "mutuals-only" setting is valuable for users who want a more intimate conversation environment. A journalist who broadcasts to a large audience might set "everyone" for most posts and "mutuals-only" for more personal ones. A researcher discussing sensitive topics might use "mutuals-only" to limit participation to people they know.

**`requireRecoverableIdentity`**: Only accept replies from authors whose DID method supports key rotation and recovery, which today means `did:webvh` and `did:plc`, and not `did:key` (Chapter 5). A `did:key` identity cannot be rotated or recovered, so if its key is stolen, the thief is that identity forever. This filter lets an author limit replies to identities that have a recovery path. Violations are rejected with `policy-violation`.

Operator-level restrictions are not part of a user's policy. Each operator's view of other operators is its own federation policy (Chapter 19), so a user who wants to refuse a whole operator blocks it (Chapter 25).

**`maxRepliesPerUser`** and **`rateLimitWindow`**: Optional rate limiting fields. Any given author may post at most `maxRepliesPerUser` replies to this post in any rolling window of `rateLimitWindow` seconds. This prevents a single user from flooding a thread, whether or not they're on the block list. Excess replies are rejected with `rate-limited`.

**Fail-closed moderation** is the default posture: when a check cannot be completed, the reply is not accepted. If Alice's operator cannot resolve the reply author's DID, or cannot consult the curation data it enforces, it returns a retryable error (`DID_RESOLUTION_FAILED` or `503`) and Bob's operator retries later; the reply is not accepted provisionally. The asymmetry is intentional: a delayed reply is a recoverable situation; abusive content that slips through because a check was skipped is harder to undo once it's in the thread and visible to followers. Operators that want fail-open behavior for research or testing must explicitly configure it.

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

The strong block is enforced at the architectural level, not the client level. Steve's operator's attempts to submit replies to Alice's content will be rejected by Alice's operator with `REPLY_REJECTED` and reason `blocked-user`. No client-side filtering is involved; the architecture itself enforces it. The block is not hidden from Steve's operator: the rejection reason tells it, and so does the BlockNotification (Chapter 26). What stays private is the rest of Alice's block list (Chapter 25).

Retroactive removal is the most operationally significant part. When Alice blocks Steve, Alice's operator must scan her reply trees, find any replies from Steve's DID, remove them from the trees, and republish its ReplyMap with the new tree CIDs. This is not merely hiding Steve's replies from Alice's view; it is removing them from the reply trees that the ReplyMap names. Anyone who follows Alice's ReplyMap after the block will not see Steve's replies. Copies of the old trees can still exist in IPFS under their old CIDs, but nothing current points to them.

### Chapter 24: Quotes vs. Replies

The protocol draws a sharp distinction between quotes and replies because they serve different social functions and have different protocol semantics.

A **reply** is a direct response that appears in the parent post's reply tree. It goes through the reply protocol, requires the parent operator's cooperation, and is subject to the parent user's policies. The parent author controls whether a reply appears in their thread.

A **quote** is content that embeds or references another activity, published on the quoting user's own timeline. It does not appear in the quoted post's reply tree. It does not go through the reply protocol. The quoting user simply creates a new activity with a reference to the quoted content. The quoted author has no veto over being quoted.

This distinction maps to a real social norm: there is a difference between replying to someone (entering their conversational space, asking permission to participate in their thread) and writing a post that references their content (speaking from your own space, building on or reacting to their content). The first requires cooperation; the second does not.

The practical consequence: a user cannot be prevented from quoting someone (it's published on the quoting user's own timeline, under their operator's policies), but a block will prevent the quote from showing up as a reply in the original author's thread. If Steve quotes Alice's post from his own timeline, Alice won't see it (she blocked Steve, so his content is filtered from her feed), but Steve hasn't violated Alice's conversational space in the way that submitting a reply would.

---
