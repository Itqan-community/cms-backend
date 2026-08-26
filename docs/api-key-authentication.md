# X-API-Key Authentication

## Overview

The Itqan CMS Public API uses **X-API-Key** for application authentication. Unlike traditional API secrets that must be kept private, X-API-Key is designed to be safely embedded in browser and mobile clients.

### Key Properties

- **Non-secret:** Safe to expose in client-side code (browsers, mobile apps)
- **Public identifier:** The key prefix serves as the application's stable identity
- **Per-app attribution:** Request tracking attributes usage to the key's owner app
- **Revocable:** Keys can be revoked or expired without regenerating secrets
- **CORS-compatible:** Works seamlessly with browser cross-origin requests (preflight)

---

## Architecture

### Authentication Flow

```
Client Request
    ↓
X-API-Key Header (e.g., "itq_abc123...")
    ↓
ApiKeyAuth.authenticate()
    ├─ Hash the key
    ├─ Look up in database (by prefix)
    ├─ Check expiry & revocation status
    └─ Return APIKey object → request.auth
    ↓
request.user = APIKey.user
(the key's owner, used for per-asset access checks)
    ↓
PublicAuth chains: ApiKeyAuth → OAuth2Auth → Anonymous
(first match wins; missing key → anonymous if enabled)
```

### Components

#### 1. **ApiKeyAuth** (`apps/core/ninja_utils/auth.py`)

```python
class ApiKeyAuth(BaseApiKeyAuth):
    """API key auth that binds the key's owner to request.user."""
    
    def authenticate(self, request, key):
        if not key:
            return None
        model = self.model
        try:
            api_key = model.objects.get_from_key(key)
        except model.DoesNotExist:
            return None
        if api_key.has_expired:
            raise AuthenticationError(message=str(_("API key has expired.")))
        
        request.user = api_key.user
        return api_key
```

**Returns:** `APIKey` object (stored in `request.auth`)  
**Sets:** `request.user` to the key's owner (User)  
**Raises:** `AuthenticationError` if expired or revoked

#### 2. **PublicAuth** (`apps/core/ninja_utils/auth.py`)

```python
class PublicAuth:
    """Chains authentication methods; falls back to anonymous."""
    
    def __call__(self, request):
        methods = []
        if settings.ENABLE_API_KEY_AUTH:
            methods.append(ApiKeyAuth())
        if settings.ENABLE_OAUTH2:
            methods.append(OAuth2Auth())
        
        for auth_method in methods:
            result = auth_method(request)
            if result is not None:
                return result
        
        if settings.ENABLE_ANONYMOUS_TRAFFIC:
            return AnonymousUser()
        return None
```

**Priority:** API Key → OAuth2 → Anonymous  
**Used on:** All public endpoints (developers_api)

#### 3. **APIKey Model** (`apps/users/models.py`)

Managed by `django-ninja-keys`:
- **Prefix:** Non-secret, human-readable identifier (e.g., `itq_abc123...`)
- **Hashed key:** Stored as bcrypt hash (raw key shown only on creation)
- **User:** ForeignKey to the owner
- **Expiry:** Optional expiration date
- **Revoked:** Boolean flag for immediate revocation

---

## CORS Configuration

### Headers Allowed

**File:** `config/settings/base.py`

```python
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "baggage",
    "content-type",
    "dnt",
    "origin",
    "sentry-trace",
    "user-agent",
    "x-api-key",           # ← API Key header
    "x-csrftoken",
    "x-requested-with",
    "x-tenant",
    "x-session-token",
    "x-email-verification-key",
    "x-password-reset-key",
]
```

### Browser Preflight Flow

```
Browser (http://localhost:3000)
    ↓
Sends OPTIONS preflight request
    ├─ Origin: http://localhost:3000
    ├─ Access-Control-Request-Method: GET
    └─ Access-Control-Request-Headers: x-api-key
    ↓
Server (corsheaders middleware)
    ├─ Checks if origin is allowed
    ├─ Checks if x-api-key is in CORS_ALLOW_HEADERS
    └─ Returns 200 OK with:
        ├─ Access-Control-Allow-Origin: http://localhost:3000
        ├─ Access-Control-Allow-Methods: GET, POST, ...
        └─ Access-Control-Allow-Headers: x-api-key, ...
    ↓
Browser grants permission
    ↓
Browser sends actual request with X-API-Key header
```

### Allowed Origins

**Development** (`config/settings/base.py`):
```python
CORS_ALLOWED_ORIGINS = [
    "http://localhost:4200",
    "http://127.0.0.1:4200",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
```

**Production:** Restrict to your actual domains (set via environment).

---

## Usage Tracking Integration

### Per-App Attribution

The X-API-Key prefix is used for **stable, per-app usage tracking**. This allows attribution without exposing the raw key.

**Implementation:** `apps/usage_tracking/decorators/track_usage.py`

```python
def _resolve_application(request) -> tuple[int | str | None, str | None]:
    """Return the application identity for OAuth2 or API-key requests."""
    
    # OAuth2 takes precedence
    token = getattr(request, "access_token", None)
    if token is not None:
        application = getattr(token, "application", None)
        if application is not None:
            return getattr(application, "id", None), getattr(application, "name", None)
    
    # API key: use the prefix as the application ID
    auth = getattr(request, "auth", None)
    prefix = getattr(auth, "prefix", None)
    if prefix:
        return prefix, None  # e.g., ("itq_abc123...", None)
    
    return None, None
```

### Decorator Usage

Endpoints automatically capture app identity when using `@track_usage()`:

```python
from apps.usage_tracking.decorators.track_usage import track_usage

@router.get("recitations/", response=list[RecitationListOut])
@track_usage(entity_type="recitation", publisher_from="publisher")
def list_recitations(request):
    # API key ID captured as "application_id" in Mixpanel
    ...
```

### Mixpanel Event Properties

When a request is made with an API key, the tracking event includes:

```json
{
  "application_id": "itq_abc123...",
  "application_name": null,
  "auth_method": "api_key",
  "entity_ids": [1, 2, 3],
  "entity_names": ["Recitation A", "Recitation B", ...],
  "latency_ms": 125,
  "status_code": 200
}
```

---

## Client Usage

### From Browser (JavaScript)

```javascript
// Get the API key (set at app startup, e.g., from localStorage or server)
const apiKey = localStorage.getItem('apiKey');

// Make a cross-origin request
fetch('https://api.itqan.dev/recitations/', {
  method: 'GET',
  headers: {
    'X-API-Key': apiKey,
  },
})
.then(response => response.json())
.then(data => console.log(data));
```

### From cURL

```bash
curl -H "X-API-Key: itq_abc123..." https://api.itqan.dev/recitations/
```

### From Python

```python
import requests

headers = {'X-API-Key': 'itq_abc123...'}
response = requests.get('https://api.itqan.dev/recitations/', headers=headers)
print(response.json())
```

---

## Security Considerations

### What X-API-Key Is NOT

- **Not a password:** Do not use it in place of user authentication
- **Not secret:** Treating it as public is intentional; it's meant to be exposed
- **Not a user identifier:** It's an app identifier, not tied to a person

### What X-API-Key IS

- **A revocable app token:** Tied to an app registration, not a person
- **A stable identifier:** Use for tracking and attribution, not secrets
- **Rate-limited per key:** Each API key has its own quota (when enforced)

### Best Practices

1. **Create a separate API key per app/client**
   - Don't share keys between production and development
   - Rotate keys periodically (create new ones, expire old ones)

2. **Never commit raw keys to source control**
   - Load from environment variables or secure storage
   - Even though they're non-secret, this is good practice

3. **Monitor usage**
   - Check the app's usage metrics in Mixpanel
   - Revoke keys that show unusual patterns

4. **Expire old keys**
   - Set an expiry date when creating keys for time-limited integrations
   - Expired keys return 401 (same as invalid keys)

---

## Error Handling

### Invalid Key → 401 Unauthorized

```json
{
  "error_name": "authentication_error",
  "message": "Invalid API key."
}
```

### Revoked Key → 401 Unauthorized

```json
{
  "error_name": "authentication_error",
  "message": "API key is revoked."
}
```

### Expired Key → 401 Unauthorized

```json
{
  "error_name": "authentication_error",
  "message": "API key has expired."
}
```

### Missing Key + Anonymous Enabled → 200 OK (Anonymous)

If `ENABLE_ANONYMOUS_TRAFFIC=True` and no X-API-Key header is provided:
- Request is treated as anonymous
- `request.user = AnonymousUser()`
- Response returns public data (no 401)

### Missing Key + Anonymous Disabled → 401 Unauthorized

If `ENABLE_ANONYMOUS_TRAFFIC=False` and no X-API-Key header is provided:
- Request is rejected
- Returns 401 with error_name="authentication_error"

---

## Testing

### Test Suite

**File:** `apps/users/tests/test_api_key_auth.py`

```bash
pytest apps/users/tests/test_api_key_auth.py -v
```

**Coverage:**
- ✓ Valid key authenticates
- ✓ CORS preflight allows x-api-key header
- ✓ Cross-origin request with valid key succeeds
- ✓ Invalid key returns 401 with error_name
- ✓ Revoked key returns 401 with error_name
- ✓ Expired key returns 401 with error_name
- ✓ Missing key falls through to anonymous (when enabled)

### Usage Tracking Tests

**File:** `apps/usage_tracking/tests/test_track_usage.py`

```bash
pytest apps/usage_tracking/tests/test_track_usage.py::TestResolveApplication -v
pytest apps/usage_tracking/tests/test_track_usage.py::TestTrackUsageDecorator::test_api_key_application_identity_is_dispatched -v
```

**Coverage:**
- ✓ API key prefix resolves as application_id
- ✓ Application identity is dispatched to tracking backend

---

## Configuration

### Environment Variables

```bash
# Enable/disable API key authentication
ENABLE_API_KEY_AUTH=True

# Enable/disable anonymous access (when no key provided)
ENABLE_ANONYMOUS_TRAFFIC=True

# CORS origins (comma-separated)
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:4200
```

### Django Settings

```python
# config/settings/base.py

ENABLE_API_KEY_AUTH = config("ENABLE_API_KEY_AUTH", default=True, cast=bool)
ENABLE_ANONYMOUS_TRAFFIC = config("ENABLE_ANONYMOUS_TRAFFIC", default=True, cast=bool)

CORS_ALLOWED_ORIGINS = [
    "http://localhost:4200",
    "http://localhost:3000",
]

CORS_ALLOW_HEADERS = [
    "x-api-key",
    # ... other headers
]
```

---

## Troubleshooting

### "Cross-Origin Request Blocked" (Browser)

**Cause:** CORS preflight failed  
**Solution:** Check that:
1. Origin is in `CORS_ALLOWED_ORIGINS`
2. `"x-api-key"` is in `CORS_ALLOW_HEADERS`
3. `corsheaders` middleware is before auth middleware

### "API key has expired" (401)

**Cause:** Key's expiry date has passed  
**Solution:**
1. Create a new API key
2. Or extend the expiry date (if you have admin access)

### "API key is revoked" (401)

**Cause:** Key was explicitly revoked  
**Solution:**
1. Create a new API key
2. The revoked key cannot be re-activated

### Missing Key Returns 401 Instead of Anonymous

**Cause:** `ENABLE_ANONYMOUS_TRAFFIC=False`  
**Solution:**
1. Set `ENABLE_ANONYMOUS_TRAFFIC=True` in settings
2. Or provide an X-API-Key header on every request

---

## References

- **Django-Ninja-Keys:** https://github.com/alric45/django-ninja-keys
- **CORS Headers (django-cors-headers):** https://github.com/adamchainz/django-cors-headers
- **Django Ninja:** https://django-ninja.rest-framework.com/

---

## See Also

- [Usage Tracking](./usage-tracking.md) — Per-app event attribution
- [Public API](./public-api.md) — Endpoint documentation
- [Authentication](./authentication.md) — OAuth2 and session auth
