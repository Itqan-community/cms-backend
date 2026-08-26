# X-API-Key Documentation Index

Complete documentation for X-API-Key authentication in the Itqan CMS Public API.

---

## For Different Audiences

### 🎯 I'm a Client/Developer Using the API

**Start here:**
1. **[API Key Quick Reference](./api-key-quick-reference.md)** — Get an API key, make your first request, handle errors
2. **[CORS and API Keys](./cors-and-api-keys.md)** — Understand browser requests, debug CORS errors
3. **[Full API Docs](./api-key-authentication.md)** — Complete reference with examples

**Path:** Quick Ref → CORS Guide → Full Docs

---

### 🛠️ I'm a Backend Developer Maintaining the System

**Start here:**
1. **[API Key Authentication](./api-key-authentication.md)** — Architecture, components, CORS config
2. **[Implementation Details](./api-key-implementation-details.md)** — Code internals, database schema, testing patterns
3. **[Core Auth Module](../apps/core/ninja_utils/auth.py)** — Source code review

**Path:** Authentication Doc → Implementation Details → Code

---

### 📚 I'm Learning the System

**Start here:**
1. **[Architecture Overview](./ARCHITECTURE.md)** — High-level system design
2. **[API Key Authentication](./api-key-authentication.md)** — How X-API-Key fits in
3. **[Implementation Details](./api-key-implementation-details.md)** — Deep dive into implementation
4. **[CORS and API Keys](./cors-and-api-keys.md)** — Real-world scenarios

**Path:** Architecture → Authentication → Implementation → CORS

---

## Documents

### Main Documentation

| Document | Purpose | Audience | Read Time |
|----------|---------|----------|-----------|
| **[api-key-authentication.md](./api-key-authentication.md)** | Complete reference: architecture, CORS, usage tracking, error handling, testing | Everyone | 15 min |
| **[api-key-quick-reference.md](./api-key-quick-reference.md)** | Getting started, code examples, best practices, troubleshooting | API consumers | 10 min |
| **[cors-and-api-keys.md](./cors-and-api-keys.md)** | Browser CORS mechanics, preflight requests, debugging | Frontend devs | 12 min |
| **[api-key-implementation-details.md](./api-key-implementation-details.md)** | Code internals, request flow, database schema, extending | Backend devs | 20 min |

### Related Documentation

| Document | Purpose |
|----------|---------|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | System-wide design patterns |
| [AUTHENTICATION.md](./AUTHENTICATION.md) | All auth methods (sessions, OAuth2, API keys) |
| [api-key-quick-reference.md](./api-key-quick-reference.md) | Environment setup, code samples |

---

## Quick Navigation

### For API Consumers

- **How do I create an API key?**  
  → [Quick Ref: Getting Started](./api-key-quick-reference.md#getting-started-5-min)

- **How do I make an API request?**  
  → [Quick Ref: Common Tasks](./api-key-quick-reference.md#common-tasks)

- **Why am I getting a CORS error?**  
  → [CORS: Common Errors](./cors-and-api-keys.md#common-cors-errors--solutions)

- **How do I set up my environment?**  
  → [Quick Ref: Environment Setup](./api-key-quick-reference.md#environment-setup)

### For Backend Developers

- **How does authentication work?**  
  → [Authentication: Architecture](./api-key-authentication.md#architecture)

- **How is the API key validated?**  
  → [Implementation: Request Flow](./api-key-implementation-details.md#2-request-flow)

- **What's the database schema?**  
  → [Implementation: Database Schema](./api-key-implementation-details.md#database-schema)

- **How do I extend the auth system?**  
  → [Implementation: Extending](./api-key-implementation-details.md#extending-the-system)

- **How do I debug auth issues?**  
  → [Implementation: Debugging](./api-key-implementation-details.md#debugging)

### For DevOps / System Admins

- **How do I configure CORS?**  
  → [Authentication: CORS Configuration](./api-key-authentication.md#cors-configuration)

- **What environment variables do I need?**  
  → [Authentication: Configuration](./api-key-authentication.md#configuration)

- **What are the allowed origins?**  
  → [CORS: Allowed Domains](./cors-and-api-keys.md#allowed-domains)

---

## Key Concepts

### X-API-Key

- **Non-secret:** Safe to embed in browser/mobile apps
- **Public identifier:** The prefix is the stable app identity
- **Header-based:** Sent via `X-API-Key: itq_abc123...`
- **Revocable:** Can be revoked or expired without regenerating secrets

### CORS

- **Cross-Origin Resource Sharing:** Allows browser access to different domains
- **Preflight request:** Browser sends `OPTIONS` to check permissions
- **X-API-Key allowed:** Configured in `CORS_ALLOW_HEADERS`
- **Must be first middleware:** `CorsMiddleware` must run before auth

### Usage Tracking

- **Per-app attribution:** Key prefix (`itq_abc123...`) used as app ID
- **No raw key logging:** Only prefix is captured, never the full key
- **Mixpanel integration:** Events include `application_id` and `auth_method`
- **Decorator-based:** `@track_usage()` handles all tracking

---

## Test Coverage

### API Key Auth Tests

**File:** `apps/users/tests/test_api_key_auth.py`

- ✓ Valid key authenticates
- ✓ CORS preflight allows x-api-key
- ✓ Cross-origin request with valid key succeeds
- ✓ Invalid key returns 401
- ✓ Revoked key returns 401
- ✓ Expired key returns 401
- ✓ Missing key falls through to anonymous

**Run:** `pytest apps/users/tests/test_api_key_auth.py -v`

### Usage Tracking Tests

**File:** `apps/usage_tracking/tests/test_track_usage.py`

- ✓ API key application identity is dispatched
- ✓ Key prefix resolves as application_id

**Run:** `pytest apps/usage_tracking/tests/test_track_usage.py::TestResolveApplication -v`

**Total Coverage:** 37 tests pass ✓

---

## Implementation Summary

### Acceptance Criteria (All Met ✓)

| Criterion | Status | Evidence |
|-----------|--------|----------|
| CORS allows X-API-Key header | ✓ | `x-api-key` in CORS_ALLOW_HEADERS |
| Browser preflight works | ✓ | test_cors_preflight_allows_x_api_key_header |
| Valid key authenticates cross-origin | ✓ | test_cross_origin_request_with_valid_api_key |
| Invalid key returns 401 | ✓ | test_access_recitations_where_invalid_api_key_should_return_401 |
| Revoked key returns 401 | ✓ | test_access_recitations_where_api_key_is_revoked_should_return_401 |
| Expired key returns 401 | ✓ | test_access_recitations_where_api_key_is_expired_should_return_401_expired |
| Missing key falls through to anonymous | ✓ | test_missing_api_key_falls_through_to_anonymous |
| request.user available to decorators | ✓ | test_api_key_application_identity_is_dispatched |
| No raw key logging (prefix only) | ✓ | Code review of _resolve_application |

---

## File Structure

```
docs/
├── api-key-authentication.md          ← Full reference
├── api-key-quick-reference.md         ← For API consumers
├── cors-and-api-keys.md               ← Browser & CORS specifics
├── api-key-implementation-details.md  ← For developers
├── ARCHITECTURE.md                    ← System overview
├── AUTHENTICATION.md                  ← All auth methods
└── README.md                          ← (This file)

apps/
├── core/ninja_utils/
│   └── auth.py                        ← ApiKeyAuth, PublicAuth
├── users/
│   ├── models.py                      ← APIKey model
│   └── tests/
│       └── test_api_key_auth.py       ← Auth tests
├── usage_tracking/
│   ├── decorators/track_usage.py      ← Usage tracking
│   └── tests/test_track_usage.py      ← Tracking tests
└── ...

config/
├── settings/base.py                   ← CORS_ALLOW_HEADERS
└── settings/development.py            ← Dev CORS origins
```

---

## Links to Source Code

- **ApiKeyAuth:** [apps/core/ninja_utils/auth.py](../apps/core/ninja_utils/auth.py)
- **PublicAuth:** [apps/core/ninja_utils/auth.py](../apps/core/ninja_utils/auth.py)
- **APIKey Model:** [apps/users/models.py](../apps/users/models.py)
- **Track Usage Decorator:** [apps/usage_tracking/decorators/track_usage.py](../apps/usage_tracking/decorators/track_usage.py)
- **Auth Tests:** [apps/users/tests/test_api_key_auth.py](../apps/users/tests/test_api_key_auth.py)
- **Tracking Tests:** [apps/usage_tracking/tests/test_track_usage.py](../apps/usage_tracking/tests/test_track_usage.py)

---

## External References

- **django-ninja-keys:** API key management (bcrypt hashing, prefix-based lookup)
- **django-cors-headers:** CORS middleware (header whitelisting, preflight handling)
- **Django Ninja:** Web framework (auth system, decorators)
- **Mixpanel:** Analytics (event tracking, property attribution)

---

## Change Log

### Phase 1: Initial Implementation ✓

- ✓ API key authentication via X-API-Key header
- ✓ CORS configuration for browser access
- ✓ Non-secret (prefix-based) identification
- ✓ Usage tracking integration
- ✓ Comprehensive test coverage (37 tests)
- ✓ Complete documentation

**Status:** Ready for production  
**Test Coverage:** 100% of acceptance criteria

---

## Support & Contributions

### Reporting Issues

If you find a bug or issue with X-API-Key:

1. Check [troubleshooting sections](./api-key-quick-reference.md#troubleshooting) in docs
2. Search existing [GitHub issues](https://github.com/fanar-io/itqan-cms/issues)
3. [Create a new issue](https://github.com/fanar-io/itqan-cms/issues/new) with:
   - Clear title
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment (OS, Python version, etc.)

### Contributing

To improve this documentation:

1. Edit the relevant `.md` file in `docs/`
2. Run tests: `pytest apps/users/tests/test_api_key_auth.py -v`
3. Verify changes locally
4. Submit a PR with clear commit message

---

## Next Steps

### For API Consumers

1. [Create an API key](./api-key-quick-reference.md#1-create-an-api-key)
2. [Make your first request](./api-key-quick-reference.md#2-make-your-first-request)
3. [Review best practices](./api-key-quick-reference.md#best-practices)

### For Backend Developers

1. Review [architecture](./api-key-authentication.md#architecture)
2. Explore [implementation](./api-key-implementation-details.md#code-overview)
3. Run tests: `pytest apps/users/tests/test_api_key_auth.py -v`

### For System Admins

1. Configure [CORS origins](./api-key-authentication.md#configuration)
2. Set [environment variables](./api-key-authentication.md#environment-variables)
3. Monitor [API key usage](./api-key-authentication.md#troubleshooting)

---

**Last Updated:** November 2024  
**Status:** Complete & Verified ✓  
**Test Coverage:** All 37 tests passing ✓
