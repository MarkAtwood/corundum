# Authentication

Corundum operators use OAuth 2.0 with the PKCE extension for client authentication. All API endpoints that operate on user data require a Bearer token obtained through this flow.

## Why OAuth 2.0 + PKCE

OAuth 2.0 is the standard for delegated authorization in HTTP APIs. PKCE (Proof Key for Code Exchange, RFC 7636) is the required extension for public clients — mobile apps, desktop apps, single-page web apps — that cannot keep a client secret confidential. A native app embedded on a user's device cannot store a secret securely; any secret in the app binary is extractable. PKCE solves this by replacing the static client secret with a per-authorization code verifier that is generated fresh for each login and never transmitted until the authorization code is being exchanged. An intercepted authorization code is useless without the corresponding verifier.

PKCE is well-supported in OAuth libraries across all major platforms. Operators MUST support PKCE and MUST reject authorization code exchanges that arrive without a verifier when the client was registered as a public client.

---

## App Registration

Before a client application can request authorization, it must register with the operator. Registration is a one-time step per operator.

### `POST /api/v1/apps`

No authentication required.

**Request body** (form-encoded or JSON):

| Parameter | Required | Description |
|-----------|----------|-------------|
| `client_name` | Yes | Human-readable name of the application (e.g., `"Birdsong for iOS"`). Displayed to users on the authorization consent screen. |
| `redirect_uris` | Yes | Newline-separated list of redirect URIs the app will use. For native apps, use a custom scheme (e.g., `birdsong://oauth/callback`) or `urn:ietf:wg:oauth:2.0:oob` for out-of-band. |
| `scopes` | No | Space-separated list of requested scopes. Defaults to `read`. |
| `website` | No | URL of the application's homepage. Displayed to users on the consent screen. |

**Response** `200 OK`:

```json
{
  "id": "01J8K2M4N6P8Q0R2S4T6V8W0X2",
  "name": "Birdsong for iOS",
  "website": "https://birdsong.example",
  "client_id": "xKiLmNpQrStUvWxYz0123456",
  "client_secret": null,
  "redirect_uri": "birdsong://oauth/callback"
}
```

`client_secret` is `null` for public/native clients. Confidential clients (server-side web apps that can store secrets securely) receive a non-null `client_secret`. The distinction is made at registration time based on the `redirect_uris` provided: a `redirect_uri` using `https://` with a non-localhost host is treated as a confidential client; custom schemes and localhost are treated as public clients.

Store the returned `client_id` persistently. For confidential clients, store `client_secret` securely.

---

## Scopes

Scopes limit what an access token can do. Clients should request the minimum scopes they need. Users see the requested scopes on the authorization consent screen.

| Scope | Access Granted |
|-------|----------------|
| `read` | Read all data (shorthand for all `read:*` scopes) |
| `read:statuses` | Read statuses and timelines |
| `read:accounts` | Read account profiles and relationships |
| `read:notifications` | Read notifications |
| `read:identity` | Read DID document, IPNS name, and signing records |
| `write` | Write all data (shorthand for all `write:*` scopes) |
| `write:statuses` | Post, edit, and delete statuses |
| `write:accounts` | Update profile fields and preferences |
| `write:follows` | Follow and unfollow accounts |
| `write:blocks` | Block and unblock accounts |
| `write:media` | Upload media attachments |
| `write:identity` | Key rotation and identity migration operations |
| `admin:read` | Read operator-level data (moderation queue, federation policy, operator logs) |
| `admin:write` | Operator-level actions (federation decisions, forced content removal, operator configuration) |

`read` grants all `read:*` scopes. `write` grants all `write:*` scopes. Granting `write` does not grant `admin:read` or `admin:write`; admin scopes must be requested explicitly and are only grantable to users with operator-level accounts.

---

## Authorization Flow

### Step 1 — Generate a Code Verifier and Challenge

The client generates a fresh `code_verifier` for each authorization attempt. It MUST NOT be reused.

```
code_verifier = base64url(random_bytes(32))   # 43 characters when base64url-encoded without padding
code_challenge = base64url(SHA256(ASCII(code_verifier)))
code_challenge_method = "S256"
```

`code_verifier` is 43–128 characters of unreserved URI characters (`[A-Z a-z 0-9 - . _ ~]`). 32 random bytes base64url-encoded without padding produces 43 characters, which is the recommended minimum. The verifier MUST be stored locally until step 5.

`code_challenge` is the URL-safe base64 encoding of the SHA-256 hash of the ASCII representation of the `code_verifier`, without padding.

### Step 2 — Redirect the User to the Authorization Endpoint

```
GET /oauth/authorize
  ?response_type=code
  &client_id=xKiLmNpQrStUvWxYz0123456
  &redirect_uri=birdsong%3A%2F%2Foauth%2Fcallback
  &scope=read+write%3Astatuses
  &code_challenge=E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM
  &code_challenge_method=S256
  &state=randomOpaqueStateValue
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `response_type` | Yes | Must be `code`. |
| `client_id` | Yes | The `client_id` from app registration. |
| `redirect_uri` | Yes | Must exactly match one of the registered redirect URIs. |
| `scope` | No | Scopes to request. Defaults to the scopes declared at registration. |
| `code_challenge` | Yes | The computed code challenge (PKCE). |
| `code_challenge_method` | Yes | Must be `S256`. Plain is not supported. |
| `state` | Recommended | Random opaque value the client generates. Returned unmodified in the redirect. Used to prevent CSRF attacks by verifying the state value in step 4 matches the one generated in this step. |

The user is presented with the operator's authorization consent screen showing the app name, website, and requested scopes. If the user approves, the operator redirects to `redirect_uri`.

### Step 3 — User Authenticates and Approves

The operator handles user authentication (password, passkey, session cookie, or whatever mechanism the operator implements). This is internal to the operator and not part of this API. The user sees the app's name, website, and the list of scopes being requested, and chooses to approve or deny.

### Step 4 — Receive the Authorization Code

On approval, the operator redirects to:

```
birdsong://oauth/callback?code=AUTH_CODE_HERE&state=randomOpaqueStateValue
```

The client MUST verify that the `state` parameter matches the value generated in step 2 before proceeding. A mismatch indicates a CSRF attempt; the client MUST discard the code and abort.

### Step 5 — Exchange the Code for an Access Token

```
POST /oauth/token
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code
&code=AUTH_CODE_HERE
&client_id=xKiLmNpQrStUvWxYz0123456
&redirect_uri=birdsong%3A%2F%2Foauth%2Fcallback
&code_verifier=dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `grant_type` | Yes | Must be `authorization_code`. |
| `code` | Yes | The authorization code from step 4. |
| `client_id` | Yes | The `client_id` from app registration. |
| `redirect_uri` | Yes | Must match the URI used in step 2. |
| `code_verifier` | Yes | The original code verifier generated in step 1. |

The operator verifies that `SHA256(code_verifier)` matches the `code_challenge` that was submitted in step 2. If they match and all other parameters are valid, the operator issues an access token.

**Response** `200 OK`:

```json
{
  "access_token": "ZA-Yj3aBD8U8Cm7lKUp-lm9O9BmDgdhHzDeqsv8QVZc",
  "token_type": "Bearer",
  "scope": "read write:statuses",
  "created_at": 1749427200
}
```

| Field | Description |
|-------|-------------|
| `access_token` | The Bearer token to use in subsequent API requests. |
| `token_type` | Always `Bearer`. |
| `scope` | Space-separated list of scopes that were actually granted. May be a subset of what was requested if the user or operator restricted the grant. |
| `created_at` | Unix timestamp (seconds since epoch) of when the token was issued. |

Access tokens do not expire by default. Operators MAY implement token expiry with refresh tokens, but MUST document this if they do. Clients that store tokens long-term SHOULD handle `401 Unauthorized` responses by re-initiating the authorization flow.

---

## Using the Token

Include the access token in the `Authorization` header of every authenticated request:

```
Authorization: Bearer ZA-Yj3aBD8U8Cm7lKUp-lm9O9BmDgdhHzDeqsv8QVZc
```

Tokens are bearer credentials. They must be protected in transit (HTTPS only) and in storage (platform secure storage, not plaintext files or shared preferences).

If the token is invalid or expired, the server returns:

```
HTTP/1.1 401 Unauthorized
```
```json
{
  "error": "unauthorized",
  "error_description": "The access token is invalid or has been revoked"
}
```

---

## Token Revocation

To revoke an access token (e.g., on user logout):

### `POST /oauth/revoke`

**Request body** (form-encoded):

| Parameter | Required | Description |
|-----------|----------|-------------|
| `token` | Yes | The access token to revoke. |
| `client_id` | Yes | The `client_id` of the app that owns the token. |

**Response** `200 OK` with an empty JSON object `{}`.

Revocation always returns `200 OK` even if the token was already revoked or was never valid. This prevents token enumeration.

---

## Instance Info

### `GET /api/v1/instance`

No authentication required. Returns information about the operator.

**Response** `200 OK`:

```json
{
  "uri": "birdsite.example",
  "title": "Birdsite",
  "description": "A federated social platform for everyone.",
  "version": "corundum/1.0.0",
  "corundum": {
    "protocol_version": "1.0",
    "operator_did": "did:web:birdsite.example",
    "operator_endpoint": "https://birdsite.example",
    "supported_algorithms": ["Ed25519"]
  },
  "contact_account": {
    "ipns_name": "k51qzi5uqu5dj4nl2xvwya5k4y6a4xy9jh0jrh5e5c5w0n9i7r3i4j8fmq4gh",
    "acct": "admin@birdsite.example"
  },
  "rules": []
}
```

| Field | Description |
|-------|-------------|
| `uri` | The operator's domain. |
| `title` | Display name of this operator instance. |
| `description` | Short description of this operator. |
| `version` | Software version string. Format: `corundum/<semver>`. |
| `corundum.protocol_version` | Corundum protocol version implemented by this operator. |
| `corundum.operator_did` | The operator's own DID. Used to verify the operator's signed artifacts. |
| `corundum.operator_endpoint` | Canonical base URL for this operator's API. |
| `corundum.supported_algorithms` | List of signing algorithms accepted for user content. Currently `["Ed25519"]`. |
| `contact_account` | The operator's administrative contact account. `ipns_name` is the stable Corundum identifier; `acct` is the human-readable handle. |
| `rules` | Array of content rules published by this operator. Each entry has `id` (string) and `text` (string). May be empty. |

This endpoint is used by clients to discover what software and protocol version an operator runs before initiating the authorization flow. It corresponds to the Mastodon `GET /api/v1/instance` endpoint with the addition of the `corundum` object.
