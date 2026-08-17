# Authentication Guide

This document explains how authentication works in Itqan CMS, covering both internal users and external developers.

---

## Overview

Itqan CMS uses **two distinct authentication systems** for different user types:

| User Type | API | Authentication Method | Use Case |
|-----------|-----|----------------------|----------|
| **Internal Frontend Users** | `cms-api` | django-allauth (Headless JWT) | Publishers and staff managing content |
| **Developers** | Public API (`/`) | django-oauth-toolkit (OAuth2) | External developers accessing resources programmatically |

---

## 1. Internal Frontend Users (CMS)

### Authentication System: django-allauth

The `cms-api` is designed for **Publishers** and **staff members** who manage the content platform.

### Features

- **Headless Mode**: API-first authentication using JWT tokens
- **Social Authentication**: Login with Google, GitHub, etc.
- **Email/Password**: Traditional email-based authentication
- **Multi-Factor Authentication (MFA)**: Optional TOTP, recovery codes, and WebAuthn
- **Session Management**: Track and manage active sessions

### Authentication Flow

```mermaid
sequenceDiagram
    participant User as Publisher
    participant Frontend as CMS Frontend
    participant CMS as cms-api
    participant Auth as django-allauth

    User->>Frontend: Navigate to login page
    Frontend->>CMS: POST /cms-api/auth/login
    CMS->>Auth: Validate credentials

    alt Email/Password Login
        Auth->>Auth: Verify email & password
        Auth->>CMS: Return JWT tokens
    else Social Login (Google/GitHub)
        Auth->>Google/GitHub: OAuth redirect
        Google/GitHub->>Auth: Return user info
        Auth->>CMS: Return JWT tokens
    end

    CMS->>Frontend: access_token + refresh_token
    Frontend->>User: Logged in successfully

    Note over Frontend,CMS: Subsequent requests use access_token

    Frontend->>CMS: GET /cms-api/resources<br/>Authorization: Bearer {access_token}
    CMS->>Frontend: Return resources
```

### Key Endpoints (django-allauth)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/cms-api/auth/login` | POST | Login with email/password |
| `/cms-api/auth/signup` | POST | Register new account |
| `/cms-api/auth/logout` | POST | Logout and invalidate tokens |
| `/cms-api/auth/token/refresh` | POST | Refresh access token |
| `/cms-api/auth/providers/google` | GET | Google OAuth login |
| `/cms-api/auth/providers/github` | GET | GitHub OAuth login |

### Documentation

For detailed django-allauth headless documentation, see:
- [django-allauth Headless Documentation](https://docs.allauth.org/en/latest/headless/introduction.html)

---

## 2. Developers (OAuth2 Client Credentials)

### Authentication System: django-oauth-toolkit

The public API (mounted at `/`) is designed for **external developers** who want to integrate Itqan resources into their applications.

---

## Developer Journey: Getting Started

### Step 1: Register an Account

Developers must first create an account via the **CMS Frontend GUI**.

```mermaid
flowchart LR
    A["Visit CMS Frontend"] --> B{"Choose Registration Method"}
    B --> C["Email/Password"]
    B --> D["Google OAuth"]
    B --> E["GitHub OAuth"]
    C & D & E --> F["Account Created"]
    F --> G["Email Verification<br/>(if required)"]
    G --> H["Login to CMS"]
```

**Registration Options:**
- Email/Password
- Google OAuth
- GitHub OAuth

---

### Step 2: Create an OAuth Application

After logging in, navigate to `/o/applications/` to create and manage OAuth applications.

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant CMS as CMS Frontend
    participant OAuth as django-oauth-toolkit
    participant DB as Database

    Dev->>CMS: Login to account
    Dev->>CMS: Navigate to /o/applications/
    Dev->>CMS: Click "Create Application"

    Note over Dev,CMS: Fill out application form

    Dev->>CMS: Submit application details
    CMS->>OAuth: Create OAuth2 Application
    OAuth->>OAuth: Generate client_id
    OAuth->>OAuth: Generate client_secret
    OAuth->>DB: Save application
    OAuth->>CMS: Return credentials
    CMS->>Dev: Display client_id & client_secret

    Note over Dev: ⚠️ COPY AND SAVE client_secret<br/>It will only be shown once!
```

### Application Configuration

When creating an application, you can configure:

| Field | Description | Example |
|-------|-------------|---------|
| **Name** | Application name | "My Quran App Backend" |
| **Client Type** | `Confidential` (recommended) or `Public` | Confidential |
| **Authorization Grant Type** | OAuth flow type | `Client credentials` |
| **Redirect URIs** | Callback URLs (not needed for client credentials) | N/A |

### Auto-Generated Credentials

Each application receives:

- **`client_id`**: Public identifier for your application
- **`client_secret`**: Secret key (treat like a password!)

> ⚠️ **IMPORTANT**: The `client_secret` is shown **only once** during creation. Store it securely!

---

### Step 3: Obtain an Access Token

Use the `client_credentials` grant type to obtain an access token.

```mermaid
sequenceDiagram
    participant App as Developer App
    participant API as Public API
    participant OAuth as OAuth2 Provider

    App->>API: POST /o/token/<br/>grant_type=client_credentials<br/>client_id={client_id}<br/>client_secret={client_secret}

    API->>OAuth: Validate credentials

    alt Valid Credentials
        OAuth->>OAuth: Generate access_token
        OAuth->>API: Return access_token
        API->>App: {<br/>  "access_token": "abc123...",<br/>  "token_type": "Bearer",<br/>  "expires_in": 3600<br/>}
    else Invalid Credentials
        OAuth->>API: Authentication failed
        API->>App: 401 Unauthorized
    end
```

### Token Request Example

```bash
curl -X POST https://api.itqan.com/o/token/ \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials" \
  -d "client_id=YOUR_CLIENT_ID" \
  -d "client_secret=YOUR_CLIENT_SECRET"
```

**Response:**

```json
{
  "access_token": "AbCdEf123456...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "scope": "read write"
}
```

---

### Step 4: Use the Access Token

Include the access token in the `Authorization` header for all API requests.

```mermaid
sequenceDiagram
    participant App as Developer App
    participant API as Public API
    participant System as Itqan CMS

    App->>API: GET /assets<br/>Authorization: Bearer {access_token}
    API->>API: Validate access_token

    alt Valid Token
        API->>System: Fetch assets
        System->>API: Return assets
        API->>App: 200 OK + assets data
    else Invalid/Expired Token
        API->>App: 401 Unauthorized
        Note over App: Request new token
    end
```

### API Request Example

```bash
curl -X GET https://api.itqan.com/assets \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

---

## Complete Developer OAuth Flow

```mermaid
flowchart TB
    Start["🚀 Start"] --> Register["1️⃣ Register Account<br/>(CMS Frontend)"]
    Register --> Login["2️⃣ Login to CMS"]
    Login --> CreateApp["3️⃣ Create OAuth Application<br/>(/o/applications/)"]
    CreateApp --> SaveCreds["4️⃣ Save client_id<br/>& client_secret"]

    SaveCreds --> Backend["5️⃣ Store credentials<br/>on Backend Server"]

    Backend --> RequestToken["6️⃣ Request Access Token<br/>POST /o/token/"]
    RequestToken --> ReceiveToken["7️⃣ Receive access_token"]

    ReceiveToken --> UseAPI["8️⃣ Make API Requests<br/>with Authorization header"]

    UseAPI --> TokenExpired{"Token<br/>Expired?"}
    TokenExpired -->|Yes| RequestToken
    TokenExpired -->|No| UseAPI

    style SaveCreds fill:#ff9
    style Backend fill:#f96
```

---

## Security Best Practices

### 🔐 Client Secret Protection

The `client_secret` represents **your application's identity** and access to our APIs.

| ✅ DO | ❌ DON'T |
|-------|----------|
| Store `client_secret` on your **backend server** | Embed in mobile apps or web frontend |
| Use environment variables or secret management | Commit to version control (Git) |
| Rotate credentials if compromised | Share credentials publicly |
| Keep credentials encrypted at rest | Hardcode in source code |

### Recommended Architecture

```mermaid
flowchart LR
    subgraph Client["Client-Side (Insecure)"]
        Mobile["📱 Mobile App"]
        Web["🌐 Web App"]
    end

    subgraph Backend["Your Backend Server (Secure)"]
        Server["🖥️ Backend API"]
        Secrets[("🔒 client_secret<br/>(Environment Variable)")]
    end

    subgraph Itqan["Itqan CMS"]
        DevAPI["Public API (/)"]
    end

    Mobile & Web -->|"User requests"| Server
    Server -->|"Uses client_secret"| DevAPI
    Secrets -.->|"Reads"| Server
    DevAPI -->|"Returns data"| Server
    Server -->|"Returns data"| Mobile & Web

    style Secrets fill:#f96
    style Server fill:#9f9
```

**Why?**
- Mobile apps and web frontends can be **decompiled or inspected**
- Anyone with your `client_secret` can impersonate your application
- Keep secrets on the backend where they're protected

---

## Rate Limiting & Fair Use

### Application Monitoring

Each OAuth application represents your usage of Itqan APIs. We monitor application behavior to ensure fair use.

### Enforcement Actions

| Violation | Example | Action |
|-----------|---------|--------|
| **Excessive Requests** | 1000+ requests/second | Rate limiting |
| **Denial of Service (DoS)** | Intentional API flooding | Client blocking |
| **Terms of Service Violation** | Unauthorized data scraping | Account suspension |

### Rate Limits (Default)

| User Type | Limit |
|-----------|-------|
| Anonymous | 100 requests/hour |
| Authenticated (OAuth) | 1000 requests/hour |

> 📧 **Need Higher Limits?** Contact us to discuss your use case and request a rate limit increase.

### Fair Use Policy

We reserve the right to:
- **Rate limit** applications making excessive requests
- **Temporarily block** clients engaged in abusive behavior
- **Permanently revoke** access for repeated violations

**Recommendations:**
- Implement **caching** to reduce API calls
- Use **exponential backoff** for retries
- **Batch requests** when possible
- Monitor your application's **error rates**

---

## OAuth2 Scopes (Future)

Currently, all authenticated applications have full read/write access. Future versions will support granular scopes:

| Scope | Description |
|-------|-------------|
| `read:assets` | Read asset metadata and download files |
| `read:resources` | Read resource metadata |
| `write:assets` | Upload and modify assets |
| `admin` | Full administrative access |

---

## Planned: Self-Identification Auth (App Header + Per-User Identifier)

OAuth2 client-credentials requires a confidential backend to protect `client_secret`,
which blocks developers who only want a mobile or web client with no backend of their
own. A lower-friction, header-based self-identification model is planned to sit alongside
OAuth2: apps identify themselves via a request header (no secret exchange), and
optionally attach a developer-chosen, non-PII per-end-user identifier so usage can be
measured per user as well as per app — without Itqan ever holding end-user PII. This
also gives publishers visibility into how their licensed content is actually used
downstream.

**Phase 1 decisions:** it does **not** replace OAuth2 or any existing auth method.
App identifiers are open (not secret-backed) — spoofing is technically possible and
accepted for now; a stricter scheme will follow only if abuse becomes a real problem.
Since the per-user identifier is fully anonymised (no PII), its usage history can be
retained indefinitely.

See [ROADMAP.md — §1](./ROADMAP.md#1-appuser-scoped-authentication-self-identification-model)
for the full problem statement and open questions.

## API Keys: Public Identifiers, Not Secrets

> **Note:** this section applies only to the `X-API-Key` identifier, not the OAuth2
> `client_secret` described above. The OAuth2 `client_secret` remains a true secret and
> must stay server-side per the guidance in **Security Best Practices**.

API keys issued by Itqan (`X-API-Key`) are **public application identifiers, not secrets**.
They are designed to be embedded directly in frontend and mobile client code. Unlike a
traditional API secret, an Itqan API key does not need to be protected from exposure by
the developer using it, that exposure is expected and is not a security incident.

### Threat model

An Itqan API key identifies *which application* is calling the API. It does **not** grant
privileged access, and it is not a bearer credential in the traditional sense:

- A leaked key allows the app to be identified and attributed, nothing more.
- A leaked key does **not** grant access to another developer's data, another app's
  identity, or any administrative capability.
- Abuse from a leaked or misused key is handled through **revocation and rate limiting**
  (with spoofing accepted as a known limitation in this Phase 1), not through treating
  the key as a confidential secret.

If a key is exposed in a public client bundle, no rotation is required as a security
response, though a developer may still choose to rotate it simply to obtain a new
identifier.

### Rotation and revocation

- **Rotation** is reframed: a developer rotates a key to get a *new identifier*, not
  because the old one "leaked." Rotation is a routine action, not an incident response.
- **Revocation** is unchanged and remains the primary abuse-control mechanism, it lets a
  developer (or Itqan) disable a specific app identity independent of whether the key was
  ever exposed.

### Storage

Because the key is non-secret to its intended developer audience, developers can view and
copy it from the dashboard at any time. There is no reveal-once restriction, and no
"click to reveal" gating — hiding the key by default would imply a secrecy requirement
that no longer applies.

This "view/copy anytime" behavior is only possible because of a storage change. Two
different threats are relevant here, and they are not the same thing:

1. A developer exposing *their own* key in a public client bundle, accepted, non-incident.
2. A breach of Itqan's own database, a single incident that could expose *every* app's
   key at once if keys were stored in plaintext.

The previous hash-only storage (irreversible by design) cannot support "view anytime" at
all, a one-way hash cannot be turned back into the original key. To enable re-viewability
while still protecting against (2), the raw key is stored **encrypted at rest**
(AES-256-GCM), with the encryption key managed separately from the database (e.g. via a
KMS or Django's secret management), rather than hashed irreversibly, and rather than
stored in plaintext. This is a deliberate departure from the hashed-at-rest default,
acceptable specifically because the key does not grant privileged access.


---

## Token Lifecycle

### Access Token Expiration

- **Lifetime**: 3600 seconds (1 hour)
- **Refresh**: Request a new token when expired
- **No Refresh Tokens**: Client credentials flow doesn't use refresh tokens

### Token Refresh Flow

```mermaid
sequenceDiagram
    participant App as Developer App
    participant API as Public API

    App->>API: API Request with access_token
    API->>App: 401 Unauthorized (Token expired)

    Note over App: Token expired, request new one

    App->>API: POST /o/token/<br/>grant_type=client_credentials<br/>client_id + client_secret
    API->>App: New access_token

    App->>API: Retry API request with new token
    API->>App: 200 OK + data
```

---

## Troubleshooting

### Common Issues

| Error | Cause | Solution |
|-------|-------|----------|
| `401 Unauthorized` | Invalid or expired token | Request a new access token |
| `403 Forbidden` | Insufficient permissions | Check application scopes |
| `429 Too Many Requests` | Rate limit exceeded | Implement backoff and caching |
| `invalid_client` | Wrong client_id or client_secret | Verify credentials |

### Getting Help

- 📚 [django-oauth-toolkit Documentation](https://django-oauth-toolkit.readthedocs.io/)
- 📚 [django-allauth Documentation](https://docs.allauth.org/en/latest/)
- 📧 Contact: [support@itqan.com](mailto:support@itqan.com)

---

## Quick Reference

### For Publishers (Internal Users)

1. Login via CMS Frontend
2. Use `cms-api` with JWT tokens
3. Supports email/password and social login

### For Developers (External)

1. Register account on CMS Frontend
2. Create OAuth application at `/o/applications/`
3. Save `client_id` and `client_secret`
4. Request access token via `POST /o/token/`
5. Use token in API requests: `Authorization: Bearer {token}`
6. **Keep `client_secret` on backend server only!**

---

**See also:**
- [Architecture Documentation](./ARCHITECTURE.md)
- [Roadmap](./ROADMAP.md) — planned self-identification auth model
- [API Documentation](http://localhost:8000/docs/)
