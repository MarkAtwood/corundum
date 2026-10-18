# Corundum MVP Implementation Plan (Go)

## Scope Definition: What "Minimum Viable" Means

The full spec is ~48,000 lines across 20+ documents. An MVP strips it to the core loop: **a user creates an identity, publishes content to IPFS as a signed Merkle-linked timeline, an operator hosts that content and accepts replies from other operators**. Everything else is either deferrable or can be stubbed.

### What's IN the MVP
- Ed25519 keypair identity (IPNS names)
- RootManifest creation, signing, publishing to IPFS
- Timeline Merkle tree (chunks, entries, tombstones)
- Canonical JSON serialization (the foundation everything signs against)
- Activity objects (Note type only)
- Operator manifest at `/.well-known/corundum-operator`
- Inter-operator reply submission and acceptance
- Social graph basics (follow list, block list with Bloom filter)
- Standard error envelope
- Basic cursor-based pagination

### What's OUT of the MVP (deferred)
- DNS/handle resolution (skip, use IPNS identifiers directly)
- Client-server protocol (per your instruction)
- DID layer (use raw IPNS keypair identity; DID is a recovery/portability layer on top)
- Curation feeds (stub the interface, don't implement curator subscriptions)
- Chunked media / MediaManifest (just support inline content and simple IPFS CID refs)
- Extensible ATDs (hardcode the Note type; ATD system is a registry pattern on top)
- Event streams / WebSocket push (use polling)
- Algorithm sunset registry (only implement Ed25519 + SHA-256)
- Post-quantum anything
- Operator discovery via DNS SRV (use direct URL configuration)
- User migration between operators
- Content expiration/retention
- mTLS authentication (use HTTP Message Signatures only)
- Static curation hosting

---

## Architecture Overview

```
corundum/
├── cmd/
│   └── corundumd/          # Operator daemon binary
├── pkg/
│   ├── canonical/          # Canonical JSON serialization (RFC 8785 + extensions)
│   ├── crypto/             # Ed25519 signing, verification, content hashing
│   ├── identity/           # IPNS keypair management, RootManifest
│   ├── timeline/           # Merkle tree, chunks, epochs, entries
│   ├── activity/           # Activity objects (Note, Tombstone, Reply refs)
│   ├── operator/           # Operator manifest, HTTP API, inter-operator auth
│   ├── reply/              # Reply protocol: submission, acceptance, rejection
│   ├── social/             # Follow list, block list, Bloom filter
│   ├── pagination/         # Cursor-based pagination envelope
│   ├── errors/             # Standard error envelope (corundum:Error)
│   └── ipfs/               # IPFS client wrapper (add, get, pin, IPNS publish)
├── internal/
│   ├── store/              # Local persistence (SQLite for indexes, metadata)
│   └── config/             # Operator configuration
├── go.mod
└── go.sum
```

**Key dependencies:**
- `github.com/ipfs/kubo` (or the HTTP API client `github.com/ipfs/go-ipfs-api`) for IPFS operations
- `golang.org/x/crypto/ed25519` for signing
- `github.com/multiformats/go-cid` for CID construction
- `github.com/multiformats/go-multibase` for multibase encoding
- `github.com/multiformats/go-multihash` for multihash
- `mattn/go-sqlite3` for local indexing
- Standard library `net/http` for the operator HTTP API

---

## Implementation Phases

The phases are dependency-ordered. Each phase produces testable artifacts. No phase depends on something built in a later phase.

---

## PHASE 1: Canonical Serialization (`pkg/canonical/`)

**Why first:** Every other component signs or hashes objects. If canonical serialization is wrong, everything downstream produces non-interoperable signatures. This is the foundation.

### Step 1.1: Canonical JSON Encoder

Implement a function `CanonicalJSON(v interface{}) ([]byte, error)` that:

1. Marshals an arbitrary Go struct/map to JSON
2. Sorts all object keys lexicographically by UTF-8 byte values (recursive)
3. Strips all insignificant whitespace
4. Serializes numbers as shortest decimal representation (integers without `.0`, no leading `+`, `-0` → `0`)
5. Escapes only required characters in strings (`"`, `\`, control chars U+0000-U+001F as `\uXXXX` with lowercase hex)
6. Does NOT escape `/` or non-ASCII Unicode (emit literal UTF-8)
7. Serializes booleans as `true`/`false`, null as `null`

**Implementation approach:** Don't use `encoding/json` directly for output (it doesn't guarantee key ordering or minimal escaping). Write a recursive serializer that walks `reflect.Value` or works on `map[string]interface{}`. Alternatively, marshal to `map[string]interface{}` via `encoding/json`, then serialize that map with your canonical rules.

### Step 1.2: NFKC Unicode Normalization

Integrate `golang.org/x/text/unicode/norm` to apply NFKC normalization to all string values before serialization.

```go
import "golang.org/x/text/unicode/norm"

func normalizeString(s string) string {
    return norm.NFKC.String(s)
}
```

### Step 1.3: Timestamp Canonicalization

Implement timestamp serialization per §3.10:

1. Parse any RFC 3339 timestamp
2. Convert to UTC (suffix `Z`)
3. Uppercase `T` separator
4. Strip trailing zeros from fractional seconds
5. If all fractional digits are zero, remove the decimal point entirely

```go
func CanonicalTimestamp(t time.Time) string {
    // Format with nanosecond precision, then strip trailing zeros
    s := t.UTC().Format("2006-01-02T15:04:05.000000000Z")
    // Strip trailing zeros from fractional part
    // ... (trim logic)
}
```

### Step 1.4: CID String Encoding

CIDs in canonical JSON are serialized as strings. CIDv1 uses base32lower, CIDv0 uses base58btc. Use the `go-cid` library's `.String()` method, which already does this correctly.

### Step 1.5: Null/Field Omission

Implement the rule: fields with null/zero values are omitted unless the schema explicitly requires them. For the MVP, use Go struct tags:

```go
type RootManifest struct {
    Type      string `json:"@type" canonical:"required"`
    Version   int    `json:"version" canonical:"required"`
    Social    *SocialGraph `json:"social,omitempty"`
    // ...
}
```

### Step 1.6: Test Vectors

Implement the test vectors from the spec (§12 of the Canonical Serialization spec). The spec provides explicit input/output pairs. Every one of them must pass before moving on.

**Deliverable:** `pkg/canonical/` passes all spec test vectors. Functions: `CanonicalJSON()`, `CanonicalTimestamp()`, `NormalizeString()`.

---

## PHASE 2: Cryptographic Primitives (`pkg/crypto/`)

### Step 2.1: Ed25519 Key Generation

```go
func GenerateKeyPair() (ed25519.PublicKey, ed25519.PrivateKey, error)
```

Standard Go `crypto/ed25519.GenerateKey(rand.Reader)`. Wrap it with multibase encoding (base58btc, prefix `z`) for the `publicKeyMultibase` format used in manifests.

### Step 2.2: Signing Procedure

Per the spec's §6 (Canonical Serialization spec):

1. Take the object to be signed
2. Remove `signature`, `signatureAlgorithm`, and `resignatures` fields
3. Canonicalize all timestamp fields
4. Serialize to Canonical JSON (using Phase 1)
5. Sign the resulting byte slice with Ed25519

```go
func Sign(object map[string]interface{}, privateKey ed25519.PrivateKey) (string, error) {
    // 1. Deep copy, remove signature fields
    // 2. CanonicalJSON()
    // 3. ed25519.Sign()
    // 4. Return base64-encoded signature
}
```

### Step 2.3: Verification Procedure

Inverse of signing:

1. Extract and remove signature fields
2. Canonicalize remaining object
3. Verify Ed25519 signature against public key

```go
func Verify(object map[string]interface{}, publicKey ed25519.PublicKey) (bool, error)
```

### Step 2.4: Content Hashing

For content-addressed storage and content matching:

```go
func ContentHash(data []byte) multihash.Multihash {
    // SHA-256, wrapped in multihash format
}

func ContentCID(data []byte) cid.Cid {
    // SHA-256 hash → CIDv1 with dag-json codec
}
```

### Step 2.5: IPNS Name Derivation

An IPNS name is the multihash of the public key:

```go
func IPNSName(publicKey ed25519.PublicKey) string {
    // peer.IDFromPublicKey equivalent
    // Returns "k51qzi5uqu5d..." format
}
```

**Deliverable:** `pkg/crypto/` can generate keypairs, sign/verify arbitrary Corundum objects, compute content hashes and CIDs, derive IPNS names. Unit tests cover round-trip sign-verify, hash determinism.

---

## PHASE 3: IPFS Client Wrapper (`pkg/ipfs/`)

### Step 3.1: IPFS HTTP API Client

Wrap the IPFS Kubo HTTP API. The MVP needs exactly these operations:

```go
type Client interface {
    // Add a JSON object, get back its CID
    Add(data []byte) (cid.Cid, error)
    
    // Get an object by CID
    Get(c cid.Cid) ([]byte, error)
    
    // Pin a CID (keep it in local storage)
    Pin(c cid.Cid) error
    
    // Unpin a CID (allow garbage collection)
    Unpin(c cid.Cid) error
    
    // Publish an IPNS record pointing a key to a CID
    IPNSPublish(keyName string, c cid.Cid) error
    
    // Resolve an IPNS name to a CID
    IPNSResolve(name string) (cid.Cid, error)
    
    // Import an Ed25519 private key into Kubo's keystore
    KeyImport(name string, privateKey ed25519.PrivateKey) error
}
```

### Step 3.2: Local IPFS Node Assumption

The MVP assumes a local Kubo node running on `localhost:5001`. Configuration:

```go
type Config struct {
    APIAddr string // default "localhost:5001"
}
```

Don't overthink this. The `go-ipfs-api` library (`github.com/ipfs/go-ipfs-api`) already wraps the HTTP API cleanly. Thin adapter on top.

### Step 3.3: DAG-JSON vs DAG-CBOR

For the MVP, use DAG-JSON for everything (human-readable, debuggable). The spec says DAG-CBOR is optional for storage optimization. Defer CBOR.

**Deliverable:** `pkg/ipfs/` can add/get/pin objects, publish/resolve IPNS. Integration test against a running Kubo node.

---

## PHASE 4: Error Handling (`pkg/errors/`)

### Step 4.1: Standard Error Envelope

Every API error uses the `corundum:Error` format (extending RFC 9457):

```go
type Error struct {
    Type     string      `json:"type"`               // "corundum:Error"
    Code     string      `json:"code"`               // e.g. "reply:blocked-user"
    Title    string      `json:"title"`               // Human-readable
    Detail   string      `json:"detail,omitempty"`    // Extended explanation
    Status   int         `json:"status"`              // HTTP status code
    Instance string      `json:"instance,omitempty"`  // Request-specific URI
    Details  interface{} `json:"details,omitempty"`   // Spec-specific detail object
}
```

### Step 4.2: Error Code Registry

Define constants for error codes the MVP uses:

```go
const (
    // General
    ErrInvalidSignature   = "crypto:invalid-signature"
    ErrMalformedObject    = "canonical:malformed-object"
    
    // Reply protocol
    ErrBlockedUser        = "reply:blocked-user"
    ErrPolicyRejected     = "reply:policy-rejected"
    ErrParentNotFound     = "reply:parent-not-found"
    ErrInvalidReplyType   = "reply:invalid-reply-type"
    
    // Pagination
    ErrCursorExpired      = "pagination:cursor-expired"
    ErrCursorMalformed    = "pagination:cursor-malformed"
    
    // Operator
    ErrOperatorUnreachable = "operator:unreachable"
    ErrAuthFailed          = "auth:signature-invalid"
)
```

### Step 4.3: HTTP Status Mapping

Each error code maps to an HTTP status. Implement a `ToHTTPResponse()` method.

**Deliverable:** `pkg/errors/` provides the standard error envelope, error constructors, HTTP response helpers.

---

## PHASE 5: Pagination (`pkg/pagination/`)

### Step 5.1: Cursor Structure

Opaque, versioned, base64-encoded cursors:

```go
type Cursor struct {
    Version   int    `json:"v"`
    Position  string `json:"p"`  // Opaque position marker
    Direction string `json:"d"`  // "f" (forward) or "b" (backward)
    CreatedAt int64  `json:"c"`  // Unix timestamp for expiry
}

func EncodeCursor(c Cursor) string {
    // JSON marshal → base64url encode
}

func DecodeCursor(s string) (Cursor, error) {
    // base64url decode → JSON unmarshal → validate version, check expiry
}
```

### Step 5.2: Paginated Response Envelope

```go
type PaginatedResponse struct {
    Type       string      `json:"@type"`       // "corundum:PaginatedResponse"
    Items      interface{} `json:"items"`
    Cursor     *string     `json:"cursor,omitempty"`
    HasMore    bool        `json:"hasMore"`
    TotalCount *int        `json:"totalCount,omitempty"`
}
```

### Step 5.3: Pagination Query Parameters

Standard query params parsed from HTTP requests:

```go
type PaginationParams struct {
    Cursor    string
    Limit     int  // default 50, max 100
    Direction string // "forward" or "backward"
}
```

**Deliverable:** `pkg/pagination/` encodes/decodes cursors, wraps results in the standard envelope.

---

## PHASE 6: Activity Objects (`pkg/activity/`)

### Step 6.1: Core Activity Structure

The generalized activity from the Extensible Activity Types spec, but hardcoded for Note:

```go
type Activity struct {
    Context            string          `json:"@context"`
    Type               string          `json:"@type"`            // "Note" for MVP
    ID                 string          `json:"id"`               // CID of this activity
    Actor              string          `json:"actor"`            // IPNS identity
    Published          string          `json:"published"`        // RFC 3339
    Content            string          `json:"content,omitempty"` 
    ContentRef         *ContentRef     `json:"contentRef,omitempty"`
    InReplyTo          *ObjectReference `json:"inReplyTo,omitempty"`
    Language           string          `json:"language,omitempty"` // BCP 47
    SignatureAlgorithm string          `json:"signatureAlgorithm,omitempty"`
    Signature          string          `json:"signature"`
}
```

### Step 6.2: Content Reference (Simplified)

For MVP, support two content modes only: `inline` and `ipfs`.

```go
type ContentRef struct {
    Mode      string `json:"mode"`      // "inline" or "ipfs"
    MediaType string `json:"mediaType"` // e.g. "text/plain"
    // Inline mode
    Data      string `json:"data,omitempty"`
    // IPFS mode
    CID       string `json:"cid,omitempty"`
    Size      int64  `json:"size,omitempty"`
}
```

### Step 6.3: Object Reference

Used for `inReplyTo` and other cross-references:

```go
type ObjectReference struct {
    Type       string `json:"@type"`       // "corundum:ObjectReference"
    Author     string `json:"author"`      // IPNS identity of referenced content's author
    ContentCID string `json:"contentCid"`  // CID of the referenced activity
}
```

### Step 6.4: Tombstone

```go
type Tombstone struct {
    Type       string `json:"@type"`       // "corundum:Tombstone"
    Original   string `json:"original"`    // CID of deleted activity
    DeletedAt  string `json:"deletedAt"`   // RFC 3339
    Reason     string `json:"reason,omitempty"`
    Signature  string `json:"signature"`
}
```

### Step 6.5: Activity Construction + Signing

```go
func NewNote(actor string, content string, privKey ed25519.PrivateKey) (*Activity, error) {
    a := &Activity{
        Context:   "https://corundum.example/ns/activity/v1",
        Type:      "Note",
        Actor:     actor,
        Published: canonical.CanonicalTimestamp(time.Now()),
        Content:   content,
    }
    // Serialize to canonical JSON, hash for CID, sign
    // Set a.ID = CID string
    // Set a.Signature = base64(ed25519.Sign(...))
    return a, nil
}
```

**Deliverable:** `pkg/activity/` can construct, sign, and verify Note activities and Tombstones.

---

## PHASE 7: Timeline Merkle Tree (`pkg/timeline/`)

This is the most complex data structure in the protocol. Build it layer by layer.

### Step 7.1: Timeline Entry

Each entry wraps an activity CID in the timeline structure:

```go
type Entry struct {
    Type       string `json:"@type"`     // "corundum:Entry"
    Sequence   uint64 `json:"sequence"`
    ActivityCID string `json:"activityCid"`
    Timestamp  string `json:"timestamp"`
    Hash       string `json:"hash"`      // SHA-256 of canonical form
}
```

### Step 7.2: Timeline Chunk

Mutable container for recent entries (max 256):

```go
type Chunk struct {
    Type       string   `json:"@type"`      // "corundum:Chunk"
    StartSeq   uint64   `json:"startSeq"`
    Entries    []string `json:"entries"`     // CIDs in reverse chronological order
    Count      int      `json:"count"`
    MerkleRoot string   `json:"merkleRoot"` // SHA-256 Merkle root of entries
}
```

### Step 7.3: Merkle Root Computation

Implement a simple binary Merkle tree over the entries array:

```go
func ComputeMerkleRoot(entryCIDs []string) ([]byte, error) {
    // SHA-256 Merkle tree
    // Leaf = SHA-256(entry CID bytes)
    // Internal = SHA-256(left || right)
    // Odd leaf: promote to next level
}
```

### Step 7.4: Epoch (Finalized Archive)

When a chunk reaches 256 entries, it's finalized into an immutable Epoch:

```go
type Epoch struct {
    Type       string   `json:"@type"`      // "corundum:Epoch"
    StartSeq   uint64   `json:"startSeq"`
    EndSeq     uint64   `json:"endSeq"`
    Entries    []string `json:"entries"`     // CIDs
    MerkleRoot string   `json:"merkleRoot"`
}
```

### Step 7.5: Archive Index

Provides O(1) lookup into historical epochs:

```go
type ArchiveIndex struct {
    Type            string     `json:"@type"` // "corundum:ArchiveIndex"
    Epochs          []EpochRef `json:"epochs"`
    TotalMerkleRoot string     `json:"totalMerkleRoot"`
}

type EpochRef struct {
    StartSeq   uint64 `json:"startSeq"`
    EndSeq     uint64 `json:"endSeq"`
    CID        string `json:"cid"`
    MerkleRoot string `json:"merkleRoot"`
}
```

### Step 7.6: Timeline Manager

Coordinates the pieces:

```go
type TimelineManager struct {
    ipfs     ipfs.Client
    identity string       // IPNS name
    privKey  ed25519.PrivateKey
}

func (tm *TimelineManager) Append(activity *activity.Activity) error {
    // 1. Add activity to IPFS → get CID
    // 2. Create Entry with next sequence number
    // 3. Add Entry to IPFS → get entry CID
    // 4. Prepend entry CID to current chunk
    // 5. Recompute chunk merkle root
    // 6. If chunk full → finalize to epoch, create new chunk
    // 7. Update RootManifest (timeline.latest, timeline.count, timeline.currentChunk)
    // 8. Sign and re-publish RootManifest to IPNS
}

func (tm *TimelineManager) GetLatest(n int) ([]*activity.Activity, error) {
    // Read current chunk, return first n entries
}

func (tm *TimelineManager) GetBySequence(seq uint64) (*activity.Activity, error) {
    // Check chunk first, then archive index
}

func (tm *TimelineManager) Delete(activityCID string) error {
    // Create tombstone, append to timeline
    // Unpin original activity from IPFS
}
```

### Step 7.7: RootManifest

The top-level mutable pointer:

```go
type RootManifest struct {
    Type       string              `json:"@type"`     // "corundum:RootManifest"
    Version    int                 `json:"version"`   // 1
    Identity   Identity            `json:"identity"`
    Operator   OperatorDeclaration `json:"operator"`
    Timeline   TimelineState       `json:"timeline"`
    Social     *SocialGraph        `json:"social,omitempty"`
    Signature  string              `json:"signature"`
}

type Identity struct {
    PublicKey   string `json:"publicKey"`   // multibase-encoded
    DisplayName string `json:"displayName,omitempty"`
    Webfinger   string `json:"webfinger,omitempty"`
    Avatar      string `json:"avatar,omitempty"`
}

type OperatorDeclaration struct {
    OperatorID   string   `json:"operatorId"`
    Endpoint     string   `json:"endpoint"`
    DeclaredAt   string   `json:"declaredAt"`
    Capabilities []string `json:"capabilities,omitempty"`
}

type TimelineState struct {
    Latest       string `json:"latest,omitempty"`
    Count        uint64 `json:"count"`
    CurrentChunk string `json:"currentChunk,omitempty"`
    ArchiveRoot  string `json:"archiveRoot,omitempty"`
}
```

### Step 7.8: RootManifest Publish

```go
func (tm *TimelineManager) PublishManifest(manifest *RootManifest) error {
    // 1. Sign manifest with privKey
    // 2. Canonical JSON serialize
    // 3. Add to IPFS → CID
    // 4. Publish IPNS record: identity → CID
}
```

**Deliverable:** `pkg/timeline/` can create a fresh timeline, append entries, finalize chunks into epochs, read entries by sequence or recency, delete via tombstone, publish/update the RootManifest. Integration test: create user, post 300 notes, verify epoch finalization, verify Merkle roots, verify lookups.

---

## PHASE 8: Social Graph (`pkg/social/`)

### Step 8.1: Following List

```go
type FollowingList struct {
    Type    string        `json:"@type"` // "corundum:FollowingList"
    Entries []FollowEntry `json:"entries"`
    Count   int           `json:"count"`
    Signature string      `json:"signature"`
}

type FollowEntry struct {
    Identity  string `json:"identity"`  // IPNS name of followed user
    FollowedAt string `json:"followedAt"`
    DisplayName string `json:"displayName,omitempty"`
}
```

### Step 8.2: Block List

```go
type BlockList struct {
    Type    string       `json:"@type"` // "corundum:BlockList"
    Entries []BlockEntry `json:"entries"`
    Count   int          `json:"count"`
    Signature string     `json:"signature"`
}

type BlockEntry struct {
    Identity  string `json:"identity"`
    BlockedAt string `json:"blockedAt"`
    Reason    string `json:"reason,omitempty"`
}
```

### Step 8.3: Block Bloom Filter

The spec uses Bloom filters for privacy-preserving block verification. An operator can check "is this user blocked?" without downloading the full block list.

```go
type BlockBloomFilter struct {
    Type       string `json:"@type"` // "corundum:BlockBloomFilter"
    Filter     []byte `json:"filter"`     // Bit array
    NumHashes  int    `json:"numHashes"`  // Number of hash functions (spec says 7)
    Size       int    `json:"size"`       // Bit array size
    Count      int    `json:"count"`      // Number of items inserted
    FalsePositiveRate float64 `json:"falsePositiveRate"`
}

func NewBlockBloomFilter(identities []string) *BlockBloomFilter {
    // Size calculation: m = -(n * ln(p)) / (ln(2)^2) for 1% FPR
    // Hash functions: k = (m/n) * ln(2) ≈ 7 for 1% FPR
    // Use MurmurHash3 per spec
}

func (bf *BlockBloomFilter) MayContain(identity string) bool {
    // Test all k hash positions
}
```

### Step 8.4: Social Graph Manager

```go
type SocialGraphManager struct {
    ipfs    ipfs.Client
    privKey ed25519.PrivateKey
}

func (sg *SocialGraphManager) Follow(target string) error
func (sg *SocialGraphManager) Unfollow(target string) error
func (sg *SocialGraphManager) Block(target string) error
func (sg *SocialGraphManager) Unblock(target string) error
func (sg *SocialGraphManager) IsBlocked(target string) bool
func (sg *SocialGraphManager) GetFollowing() (*FollowingList, error)
func (sg *SocialGraphManager) GetBloomFilter() (*BlockBloomFilter, error)
```

**Deliverable:** `pkg/social/` manages follow/block lists, publishes them to IPFS, generates Bloom filters. Tests: follow/unfollow roundtrip, block with Bloom filter verification (false positives within 1% tolerance, zero false negatives).

---

## PHASE 9: Operator Manifest + HTTP API (`pkg/operator/`)

### Step 9.1: Operator Manifest

The self-signed JSON document at `/.well-known/corundum-operator`:

```go
type OperatorManifest struct {
    Context    []string         `json:"@context"`
    Type       string           `json:"@type"`           // "corundum:OperatorManifest"
    ID         string           `json:"id"`              // URL of this manifest
    Version    string           `json:"version"`         // "1.0"
    OperatorID string           `json:"operatorId"`      // Domain
    Endpoint   string           `json:"endpoint"`        // API base URL
    PublishedAt string          `json:"publishedAt"`
    UpdatedAt   string          `json:"updatedAt"`
    Keys       []KeyObject      `json:"keys"`
    Authentication AuthConfig   `json:"authentication"`
    Protocol   ProtocolConfig   `json:"protocol"`
    Signature  string           `json:"signature"`
    SignatureAlgorithm string   `json:"signatureAlgorithm"`
}

type KeyObject struct {
    ID                  string   `json:"id"`
    Type                string   `json:"type"`
    Controller          string   `json:"controller"`
    PublicKeyMultibase  string   `json:"publicKeyMultibase"`
    Purposes            []string `json:"purposes"`
    Status              string   `json:"status"`
    ActivatedAt         string   `json:"activatedAt"`
}

type AuthConfig struct {
    SupportedMethods []string `json:"supportedMethods"` // ["httpSig"]
    HttpSig          *HttpSigConfig `json:"httpSig,omitempty"`
}

type HttpSigConfig struct {
    SigningKeyId     string   `json:"signingKeyId"`
    Algorithm        string   `json:"algorithm"`          // "ed25519-v1"
    CoveredComponents []string `json:"coveredComponents"`  // ["@method","@target-uri","content-digest"]
}

type ProtocolConfig struct {
    SupportedVersions []string `json:"supportedVersions"` // ["1.0"]
    Capabilities      []string `json:"capabilities"`      // ["replies-v1"]
    SupportedActivityTypes []string `json:"supportedActivityTypes"` // ["Note"]
    MaxContentSize    int      `json:"maxContentSize"`    // bytes
    RateLimits        *RateLimitConfig `json:"rateLimits,omitempty"`
}
```

### Step 9.2: Operator Configuration

```go
type OperatorConfig struct {
    Domain       string   // e.g. "birdsite.example"
    ListenAddr   string   // e.g. ":8080"
    IPFSAddr     string   // e.g. "localhost:5001"
    DataDir      string   // e.g. "./data"
    PrivateKeyPath string // Ed25519 operator key
}
```

### Step 9.3: HTTP Router

Use standard library `net/http` (or `chi` for cleaner routing):

```
GET  /.well-known/corundum-operator          → Serve operator manifest
GET  /corundum/v1/users/{ipns}/manifest      → Serve user's RootManifest
GET  /corundum/v1/users/{ipns}/timeline      → Paginated timeline entries
GET  /corundum/v1/users/{ipns}/activity/{cid}→ Single activity by CID
GET  /corundum/v1/users/{ipns}/social/following → Following list
GET  /corundum/v1/users/{ipns}/social/blocks/bloom → Block Bloom filter
POST /corundum/v1/users/{ipns}/replies       → Submit a reply (inter-operator)
GET  /corundum/v1/users/{ipns}/replies/{cid} → Reply tree for an activity
```

### Step 9.4: Operator Daemon Bootstrap

`cmd/corundumd/main.go`:

```go
func main() {
    // 1. Load config
    // 2. Connect to IPFS
    // 3. Load or generate operator keypair
    // 4. Build and self-sign operator manifest
    // 5. Initialize SQLite for user indexes
    // 6. Start HTTP server
}
```

**Deliverable:** `cmd/corundumd` starts, serves the operator manifest, serves user timelines. `curl` test: fetch manifest, verify signature.

---

## PHASE 10: Inter-Operator Authentication (`pkg/operator/auth.go`)

### Step 10.1: HTTP Message Signatures (RFC 9421)

For outbound requests to other operators:

```go
func SignRequest(req *http.Request, keyID string, privKey ed25519.PrivateKey) error {
    // 1. Compute content-digest (SHA-256 of body, per RFC 9530) if body present
    // 2. Construct signature base string per RFC 9421
    //    - Covered components: @method, @target-uri, content-digest, content-type
    // 3. Sign with Ed25519
    // 4. Add Signature-Input and Signature headers
}
```

### Step 10.2: Request Verification

For inbound requests from other operators:

```go
func VerifyRequest(req *http.Request, getKey KeyResolver) (string, error) {
    // 1. Parse Signature-Input header
    // 2. Resolve signing key from the sender's operator manifest
    // 3. Reconstruct signature base string
    // 4. Verify Ed25519 signature
    // 5. Return operator ID if valid
}

type KeyResolver func(keyID string) (ed25519.PublicKey, error)
```

### Step 10.3: Operator Manifest Cache

Cache fetched operator manifests (with TTL from Cache-Control headers):

```go
type ManifestCache struct {
    mu    sync.RWMutex
    cache map[string]*CachedManifest
}

type CachedManifest struct {
    Manifest  *OperatorManifest
    FetchedAt time.Time
    TTL       time.Duration
}

func (mc *ManifestCache) Get(operatorID string) (*OperatorManifest, error) {
    // Check cache → if miss or expired, fetch from /.well-known/corundum-operator
    // Verify self-signature before caching
}
```

### Step 10.4: Auth Middleware

HTTP middleware that verifies inbound inter-operator requests:

```go
func AuthMiddleware(cache *ManifestCache) func(http.Handler) http.Handler {
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            operatorID, err := VerifyRequest(r, cache.KeyResolver())
            if err != nil {
                writeError(w, errors.NewAuthError(err))
                return
            }
            ctx := context.WithValue(r.Context(), "operatorID", operatorID)
            next.ServeHTTP(w, r.WithContext(ctx))
        })
    }
}
```

**Deliverable:** Outbound requests are signed, inbound requests are verified. Integration test: two operator instances authenticate to each other.

---

## PHASE 11: Reply Protocol (`pkg/reply/`)

This is where federation actually happens.

### Step 11.1: Reply Submission (Wire Format)

```go
type ReplySubmission struct {
    Type           string          `json:"@type"`           // "corundum:ReplySubmission"
    ProtocolVersion string         `json:"protocolVersion"` // "1.0"
    Reply          ReplyContent    `json:"reply"`
    Parent         ObjectReference `json:"parent"`
    Signature      string          `json:"signature"`
}

type ReplyContent struct {
    Author      string `json:"author"`      // Commenter's IPNS identity
    ContentCID  string `json:"contentCid"`  // CID of the reply activity on commenter's timeline
    ContentHash string `json:"contentHash"` // SHA-256 of canonical form of the activity
    ReplyType   string `json:"replyType"`   // "comment" for MVP
}
```

### Step 11.2: Reply Acceptance/Rejection

```go
type ReplyAcceptance struct {
    Type           string `json:"@type"`          // "corundum:ReplyAcceptance"
    SubmissionID   string `json:"submissionId"`
    AcceptedAt     string `json:"acceptedAt"`
    TreePosition   string `json:"treePosition"`   // Position in reply tree
}

type ReplyRejection struct {
    Type           string `json:"@type"`          // "corundum:ReplyRejection"
    SubmissionID   string `json:"submissionId"`
    RejectedAt     string `json:"rejectedAt"`
    ReasonCode     string `json:"reasonCode"`     // From rejection code registry
    ReasonDetail   string `json:"reasonDetail,omitempty"`
}
```

### Step 11.3: Reply Submission Handler (Receiving Operator)

```go
func (op *Operator) HandleReplySubmission(w http.ResponseWriter, r *http.Request) {
    // 1. Verify inter-operator auth (middleware already done)
    // 2. Parse ReplySubmission from body
    // 3. Resolve target user (the IPNS identity from the URL path)
    // 4. Check user's block list (Bloom filter first, then exact if positive)
    // 5. Verify reply signature (fetch commenter's RootManifest, verify activity)
    // 6. Verify contentHash matches the activity at contentCID
    // 7. Check reply policy (for MVP: accept from anyone not blocked)
    // 8. If accepted:
    //    a. Store reply reference in the reply tree
    //    b. Return ReplyAcceptance
    // 9. If rejected:
    //    a. Return ReplyRejection with reason code
}
```

### Step 11.4: Reply Submission Client (Sending Operator)

```go
func (op *Operator) SubmitReply(
    reply *activity.Activity,
    parentRef *activity.ObjectReference,
) (*ReplyAcceptance, *ReplyRejection, error) {
    // 1. Resolve parent author's RootManifest (via IPNS)
    // 2. Extract parent's operator endpoint
    // 3. Construct ReplySubmission
    // 4. Sign outbound HTTP request
    // 5. POST to parent's operator: /corundum/v1/users/{parent-ipns}/replies
    // 6. Parse response: acceptance or rejection
}
```

### Step 11.5: Reply Tree Storage

Simple tree structure stored per-activity:

```go
type ReplyTree struct {
    Type      string       `json:"@type"`      // "corundum:ReplyTree"
    ParentCID string       `json:"parentCid"`
    Replies   []ReplyRef   `json:"replies"`
    Count     int          `json:"count"`
}

type ReplyRef struct {
    Author     string `json:"author"`
    ContentCID string `json:"contentCid"`
    AcceptedAt string `json:"acceptedAt"`
    Depth      int    `json:"depth"`
}
```

For the MVP, store reply trees in SQLite (indexed by parent activity CID) rather than as separate IPFS objects. They're operator-managed data, not user-owned content.

**Deliverable:** Two operator instances can exchange replies. Integration test: Alice on Operator A posts a Note. Bob on Operator B replies. Alice's operator accepts the reply. Query reply tree and see Bob's reply.

---

## PHASE 12: Local Persistence (`internal/store/`)

### Step 12.1: SQLite Schema

IPFS is the canonical storage, but operators need fast indexes for lookups:

```sql
-- Users hosted on this operator
CREATE TABLE users (
    ipns_name TEXT PRIMARY KEY,
    public_key BLOB NOT NULL,
    display_name TEXT,
    root_manifest_cid TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Timeline index (fast sequence → CID lookup without walking IPFS)
CREATE TABLE timeline_entries (
    ipns_name TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    activity_cid TEXT NOT NULL,
    entry_cid TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    is_tombstone BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (ipns_name, sequence)
);

-- Reply tree index
CREATE TABLE reply_tree (
    parent_cid TEXT NOT NULL,
    reply_author TEXT NOT NULL,
    reply_cid TEXT NOT NULL,
    accepted_at TEXT NOT NULL,
    depth INTEGER NOT NULL,
    PRIMARY KEY (parent_cid, reply_cid)
);

-- Operator manifest cache
CREATE TABLE operator_cache (
    operator_id TEXT PRIMARY KEY,
    manifest_json TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

-- Social graph index
CREATE TABLE follows (
    follower TEXT NOT NULL,
    followed TEXT NOT NULL,
    followed_at TEXT NOT NULL,
    PRIMARY KEY (follower, followed)
);

CREATE TABLE blocks (
    blocker TEXT NOT NULL,
    blocked TEXT NOT NULL,
    blocked_at TEXT NOT NULL,
    PRIMARY KEY (blocker, blocked)
);
```

### Step 12.2: Store Interface

```go
type Store interface {
    // Users
    CreateUser(user *UserRecord) error
    GetUser(ipnsName string) (*UserRecord, error)
    UpdateUserManifest(ipnsName, manifestCID string) error
    
    // Timeline
    IndexEntry(ipnsName string, seq uint64, activityCID, entryCID string, ts time.Time) error
    GetEntriesByRange(ipnsName string, startSeq, endSeq uint64) ([]EntryIndex, error)
    GetLatestEntries(ipnsName string, limit int) ([]EntryIndex, error)
    
    // Replies
    AddReply(parentCID, replyAuthor, replyCID string, depth int) error
    GetReplies(parentCID string, cursor string, limit int) ([]ReplyIndex, string, error)
    
    // Blocks
    IsBlocked(blocker, blocked string) (bool, error)
    
    // Operator cache
    CacheManifest(operatorID string, manifest []byte, ttl time.Duration) error
    GetCachedManifest(operatorID string) ([]byte, error)
}
```

**Deliverable:** `internal/store/` wraps SQLite with the interfaces needed by all components. Schema migration on startup.

---

## PHASE 13: Operator Daemon Integration (`cmd/corundumd/`)

### Step 13.1: User Registration

A local CLI or admin API to create users on this operator:

```go
// POST /admin/users (admin-only, not part of the Corundum protocol)
func (op *Operator) RegisterUser(displayName string) (*UserRegistration, error) {
    // 1. Generate Ed25519 keypair
    // 2. Derive IPNS name
    // 3. Import key into IPFS Kubo keystore
    // 4. Create empty RootManifest with this operator's declaration
    // 5. Sign and publish to IPNS
    // 6. Insert into SQLite
    // Return: IPNS name, keypair (or just the public key; private key stored in Kubo)
}
```

### Step 13.2: Content Publishing

```go
// POST /admin/users/{ipns}/post (admin API)
func (op *Operator) PublishNote(ipnsName, content string) (*activity.Activity, error) {
    // 1. Load user's private key from Kubo keystore
    // 2. Create Note activity, sign it
    // 3. Append to user's timeline via TimelineManager
    // 4. Return the activity
}
```

### Step 13.3: Full Request Flow (Reply)

```
Bob's Client → Bob's Operator → [construct reply activity] → [append to Bob's timeline]
                                → [lookup Alice's operator from her RootManifest]
                                → [sign HTTP request with operator key]
                                → POST to Alice's Operator /corundum/v1/users/{alice-ipns}/replies
                                    → Alice's Operator verifies HTTP signature
                                    → Checks Alice's block list
                                    → Verifies reply content hash
                                    → Stores in reply tree
                                    → Returns ReplyAcceptance
                                ← Bob's Operator receives acceptance
```

### Step 13.4: Putting It All Together

```go
func main() {
    cfg := config.Load()
    
    ipfsClient := ipfs.New(cfg.IPFSAddr)
    store := store.NewSQLite(cfg.DataDir)
    
    operatorKey := crypto.LoadOrGenerate(cfg.PrivateKeyPath)
    manifest := operator.BuildManifest(cfg, operatorKey)
    
    manifestCache := operator.NewManifestCache(ipfsClient)
    
    op := &Operator{
        Config:   cfg,
        IPFS:     ipfsClient,
        Store:    store,
        Key:      operatorKey,
        Manifest: manifest,
        Cache:    manifestCache,
    }
    
    mux := http.NewServeMux()
    
    // Public endpoints
    mux.HandleFunc("GET /.well-known/corundum-operator", op.ServeManifest)
    mux.HandleFunc("GET /corundum/v1/users/{ipns}/manifest", op.ServeUserManifest)
    mux.HandleFunc("GET /corundum/v1/users/{ipns}/timeline", op.ServeTimeline)
    mux.HandleFunc("GET /corundum/v1/users/{ipns}/activity/{cid}", op.ServeActivity)
    mux.HandleFunc("GET /corundum/v1/users/{ipns}/replies/{cid}", op.ServeReplyTree)
    mux.HandleFunc("GET /corundum/v1/users/{ipns}/social/following", op.ServeFollowing)
    mux.HandleFunc("GET /corundum/v1/users/{ipns}/social/blocks/bloom", op.ServeBlockBloom)
    
    // Inter-operator (authenticated)
    authMux := operator.AuthMiddleware(manifestCache)(
        http.HandlerFunc(op.HandleReplySubmission),
    )
    mux.Handle("POST /corundum/v1/users/{ipns}/replies", authMux)
    
    // Admin endpoints (localhost only)
    mux.HandleFunc("POST /admin/users", op.AdminRegisterUser)
    mux.HandleFunc("POST /admin/users/{ipns}/post", op.AdminPublishNote)
    mux.HandleFunc("POST /admin/users/{ipns}/follow", op.AdminFollow)
    mux.HandleFunc("POST /admin/users/{ipns}/block", op.AdminBlock)
    
    log.Fatal(http.ListenAndServe(cfg.ListenAddr, mux))
}
```

**Deliverable:** A single binary (`corundumd`) that runs a Corundum operator. Two instances on different ports can federate.

---

## PHASE 14: End-to-End Integration Test

### Step 14.1: Test Scenario Script

Write a Go test (or shell script calling `curl`) that executes this exact scenario:

```
1. Start Kubo IPFS node
2. Start Operator A on :8081 (birdsite.test)
3. Start Operator B on :8082 (chirper.test)

4. Register Alice on Operator A → get Alice's IPNS
5. Register Bob on Operator B → get Bob's IPNS

6. Alice posts a Note: "Hello federation!"
7. Verify: GET Alice's timeline from Operator A returns the note
8. Verify: GET Alice's RootManifest from IPFS directly shows correct timeline state

9. Bob follows Alice
10. Bob replies to Alice's note: "Welcome to the fediverse!"
11. Verify: Operator B signed the request to Operator A
12. Verify: Operator A accepted the reply
13. Verify: GET Alice's reply tree shows Bob's reply

14. Alice blocks Bob
15. Bob tries to reply again: "More thoughts"
16. Verify: Operator A rejects with "reply:blocked-user"

17. Alice posts 300 more notes
18. Verify: At least one epoch has been finalized
19. Verify: Merkle roots are consistent
20. Verify: Lookup by sequence number works for any arbitrary sequence

21. Alice deletes her first note
22. Verify: Tombstone appears in timeline
23. Verify: Original note CID is unpinned
```

### Step 14.2: Verification Checks

For each step, verify:

- Signatures on all objects are valid
- Canonical JSON serialization is deterministic (serialize → deserialize → re-serialize produces identical bytes)
- CIDs match content hashes
- IPNS resolution returns current RootManifest
- Error responses use the standard envelope

**Deliverable:** All 23 steps pass. The core Corundum protocol loop works.

---

## Phase Dependency Graph

```
Phase 1: Canonical Serialization
    ↓
Phase 2: Crypto Primitives
    ↓
Phase 3: IPFS Client        Phase 4: Errors        Phase 5: Pagination
    ↓                            ↓                       ↓
Phase 6: Activity Objects  ←─────┴───────────────────────┘
    ↓
Phase 7: Timeline Merkle Tree
    ↓
Phase 8: Social Graph
    ↓
Phase 9: Operator Manifest + HTTP
    ↓
Phase 10: Inter-Operator Auth
    ↓
Phase 11: Reply Protocol
    ↓
Phase 12: Local Persistence (SQLite)
    ↓
Phase 13: Daemon Integration
    ↓
Phase 14: End-to-End Test
```

---

## Build/Run Prerequisites

1. **Go 1.22+** (for `net/http` routing patterns with `{param}`)
2. **IPFS Kubo node** running locally (`ipfs init && ipfs daemon`)
3. **SQLite3** (via CGo, `mattn/go-sqlite3`)
4. **No external services** required beyond IPFS

## Estimated Complexity Per Phase

| Phase | Description | Est. Lines of Go | Difficulty |
|-------|-------------|-------------------|------------|
| 1 | Canonical Serialization | 400-600 | Medium (edge cases) |
| 2 | Crypto Primitives | 200-300 | Low (well-known) |
| 3 | IPFS Client | 150-200 | Low (thin wrapper) |
| 4 | Error Handling | 100-150 | Low |
| 5 | Pagination | 150-200 | Low |
| 6 | Activity Objects | 200-300 | Low-Medium |
| 7 | Timeline Merkle Tree | 600-900 | High (core data structure) |
| 8 | Social Graph | 300-400 | Medium |
| 9 | Operator Manifest + HTTP | 400-500 | Medium |
| 10 | Inter-Operator Auth | 300-400 | Medium-High (RFC 9421) |
| 11 | Reply Protocol | 400-500 | Medium |
| 12 | Local Persistence | 300-400 | Low-Medium |
| 13 | Daemon Integration | 200-300 | Low (plumbing) |
| 14 | Integration Tests | 300-500 | Medium |
| **Total** | | **~4000-5500** | |

---

## What You Get at the End

A single Go binary (`corundumd`) that:

1. Runs as a Corundum operator
2. Creates users with Ed25519 keypair identities (IPNS names)
3. Publishes signed content to IPFS as Merkle-linked timelines
4. Serves operator manifest, user manifests, timelines, and social graphs via HTTP
5. Authenticates inter-operator requests via HTTP Message Signatures
6. Accepts and rejects cross-operator replies based on block lists
7. Manages reply trees
8. Supports content deletion via tombstones
9. Paginates all collection endpoints
10. Returns standardized error responses

Two instances of this binary can federate: users on different operators can follow each other, reply to each other's posts, and block each other, with all content cryptographically signed and stored in content-addressed IPFS.

This is the minimum viable Corundum. Everything else (DID recovery, curation feeds, chunked media, extensible ATDs, event streams, operator migration, DNS-based discovery) layers on top.
