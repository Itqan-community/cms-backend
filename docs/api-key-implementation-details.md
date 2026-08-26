# X-API-Key Implementation Details

## For Developers

This document covers the internals of X-API-Key authentication for anyone extending or debugging the system.

---

## Code Overview

### 1. Authentication Pipeline

**Entry point:** `apps/core/ninja_utils/auth.py`

```python
# PublicAuth is applied to all public endpoints
public_auth = [PublicAuth()]

# Usage in developers_api (config/developers_api.py)
developers_api = create_ninja_api(
    auth=public_auth,  # ← All public endpoints use this
)
```

### 2. Request Flow

#### Step 1: Request Arrives

```python
GET /recitations/
Headers: X-API-Key: itq_abc123...
```

#### Step 2: CORS Middleware (First)

`corsheaders.middleware.CorsMiddleware` runs first (check middleware order in `config/settings/base.py`):
- Reads `X-API-Key` from request headers
- Matches against `CORS_ALLOW_HEADERS`
- If preflight: returns 200 with CORS headers
- If actual request: passes through to Django

#### Step 3: Auth Middleware (Later)

`PublicAuth.__call__(request)` is invoked by Django Ninja:

```python
class PublicAuth:
    def __call__(self, request):
        # Try each auth method in order
        for auth_method in [ApiKeyAuth(), OAuth2Auth()]:
            result = auth_method(request)
            if result is not None:
                return result
        
        # Fallback to anonymous
        if settings.ENABLE_ANONYMOUS_TRAFFIC:
            return AnonymousUser()
        return None
```

#### Step 4: ApiKeyAuth.authenticate()

```python
class ApiKeyAuth(BaseApiKeyAuth):
    def authenticate(self, request, key):
        # 1. Extract X-API-Key header
        if not key:
            return None
        
        # 2. Hash and lookup in database
        try:
            api_key = self.model.objects.get_from_key(key)
        except self.model.DoesNotExist:
            return None  # Invalid key → continue to next auth method
        
        # 3. Check expiry
        if api_key.has_expired:
            raise AuthenticationError(...)  # Expired → 401 (stop)
        
        # 4. Set request.user to key owner
        request.user = api_key.user
        
        # 5. Return APIKey object → stored in request.auth
        return api_key
```

**Key detail:** The `key` parameter is automatically extracted from the `X-API-Key` header by Django Ninja's auth system.

#### Step 5: View Executes

```python
@router.get("recitations/")
@track_usage(entity_type="recitation")
def list_recitations(request):
    # request.user = User who owns the API key
    # request.auth = APIKey object (with .prefix attribute)
    # → Tracking decorator reads request.auth.prefix for app ID
    ...
```

---

## Database Schema

### APIKey Model

**Managed by:** `django-ninja-keys` (installed via `pyproject.toml`)

```python
class APIKey(models.Model):
    user = ForeignKey(User)
    name = CharField(max_length=255)  # e.g., "Mobile App v2"
    prefix = CharField(unique=True)   # e.g., "itq_abc123..."
    hashed_key = CharField()          # bcrypt hash of full key
    created = DateTimeField(auto_now_add=True)
    expiry_date = DateTimeField(null=True, blank=True)
    revoked = BooleanField(default=False)
    
    class Meta:
        unique_together = ('user', 'name')
        indexes = [
            Index(fields=['prefix']),  # Fast prefix-based lookup
        ]
```

### Key Fields

| Field | Purpose | Example |
|-------|---------|---------|
| `user` | Owner of the key | User(id=42) |
| `prefix` | Non-secret ID (safe to log) | `itq_abc123...` |
| `hashed_key` | Bcrypt hash of full key | `$2b$12$...` |
| `expiry_date` | Optional expiration | 2024-12-31 |
| `revoked` | Is key disabled? | False |

### Lookup Process

```python
# User submits full key (only time it's visible)
raw_key = "itq_abc123...def456..."

# Library extracts prefix and hashes key
prefix = raw_key[:13]  # "itq_abc123..."
hashed = bcrypt.hashpw(raw_key.encode(), salt)

# Query database by prefix (fast)
api_key = APIKey.objects.filter(prefix=prefix).first()

# Verify bcrypt hash matches
if bcrypt.checkpw(raw_key.encode(), api_key.hashed_key):
    # Key is valid
    request.user = api_key.user
```

---

## Usage Tracking Integration

### How the Decorator Gets App Identity

**Decorator:** `@track_usage()`  
**File:** `apps/usage_tracking/decorators/track_usage.py`

```python
def _dispatch(request, result, **kwargs):
    # Resolve the application identity
    application_id, application_name = _resolve_application(request)
    
    # ... extract entity ids, names, etc. ...
    
    # Build Mixpanel event
    properties = {
        "application_id": application_id,      # "itq_abc123..." for API keys
        "application_name": application_name,  # None for API keys
        # ... other properties ...
    }
    
    # Push to Redis for async processing
    redis_client.rpush(TRACKING_BUFFER_KEY, json.dumps(event))
```

### Full Flow

```
Request with X-API-Key
    ↓
ApiKeyAuth sets request.auth = APIKey(prefix="itq_abc123...")
    ↓
View decorated with @track_usage()
    ↓
_dispatch() called after view returns
    ↓
_resolve_application(request) reads request.auth.prefix
    ↓
Event pushed to Redis:
    {
        "distinct_id": "...",
        "event": "public_api_request",
        "properties": {
            "application_id": "itq_abc123...",
            "entity_ids": [1, 2, 3],
            ...
        }
    }
    ↓
Async task flushes to Mixpanel
```

---

## CORS Mechanics

### Browser Preflight (OPTIONS)

```
Browser Request:
    OPTIONS /recitations/
    Origin: http://localhost:3000
    Access-Control-Request-Method: GET
    Access-Control-Request-Headers: x-api-key

Django corsheaders middleware:
    1. Check if origin is allowed
       → CORS_ALLOWED_ORIGINS contains "http://localhost:3000"? YES
    
    2. Check if requested headers are allowed
       → CORS_ALLOW_HEADERS contains "x-api-key"? YES
    
    3. Generate response headers
       Access-Control-Allow-Origin: http://localhost:3000
       Access-Control-Allow-Methods: GET, POST, PUT, DELETE, ...
       Access-Control-Allow-Headers: x-api-key, authorization, content-type, ...
       Access-Control-Max-Age: 3600
    
    → Return 200 OK

Browser sees OK response → Grants permission → Sends actual request

Browser Request:
    GET /recitations/
    Origin: http://localhost:3000
    X-API-Key: itq_abc123...

Django:
    1. corsheaders middleware:
       → Adds Access-Control-Allow-Origin: http://localhost:3000
    
    2. Django Ninja:
       → Calls PublicAuth (extracts X-API-Key)
       → Calls ApiKeyAuth (validates key)
       → Calls view with authenticated request
    
    → Return 200 OK with data and CORS headers
```

### Middleware Order (Important)

**File:** `config/settings/base.py`

```python
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",  # ← MUST BE FIRST
    "django.middleware.security.SecurityMiddleware",
    # ... other middleware ...
]
```

If `CorsMiddleware` is not first, preflight responses won't include CORS headers.

---

## Error Handling

### Invalid Key (Not Found)

```python
def authenticate(self, request, key):
    try:
        api_key = self.model.objects.get_from_key(key)
    except self.model.DoesNotExist:
        return None  # ← Continue to next auth method (OAuth2, then Anonymous)
```

**Behavior:** If `ENABLE_ANONYMOUS_TRAFFIC=False`, returns 401. If `True`, falls back to anonymous.

### Expired Key

```python
if api_key.has_expired:
    raise AuthenticationError(message="API key has expired.")
    # ← Stops immediately, returns 401
```

**Behavior:** Always returns 401, regardless of `ENABLE_ANONYMOUS_TRAFFIC`.

### Revoked Key

```python
# Check performed by django-ninja-keys (model property)
@property
def has_expired(self):
    if self.revoked:
        return True
    if self.expiry_date and timezone.now() > self.expiry_date:
        return True
    return False
```

**Behavior:** Same as expired key — always 401.

---

## Testing Patterns

### Unit Test: Mocking the Request

```python
from unittest.mock import Mock, patch
from apps.core.ninja_utils.auth import ApiKeyAuth

def test_api_key_auth():
    auth = ApiKeyAuth()
    request = Mock()
    
    # Case 1: Valid key
    with patch('apps.core.ninja_utils.auth.APIKey.objects.get_from_key') as mock_get:
        api_key = Mock(has_expired=False, user=Mock(is_authenticated=True))
        mock_get.return_value = api_key
        
        result = auth.authenticate(request, "itq_abc123...")
        assert result == api_key
        assert request.user == api_key.user
    
    # Case 2: Invalid key
    with patch('apps.core.ninja_utils.auth.APIKey.objects.get_from_key') as mock_get:
        mock_get.side_effect = APIKey.DoesNotExist()
        
        result = auth.authenticate(request, "invalid")
        assert result is None
```

### Integration Test: Real Request

```python
from apps.users.models import APIKey, User
from django.test import Client

def test_api_key_request():
    # Create user and API key
    user = User.objects.create_user(email="test@example.com")
    api_key, raw_key = APIKey.objects.create_key(name="Test", user=user)
    
    # Make request with key
    client = Client()
    response = client.get(
        "/recitations/",
        headers={"x-api-key": raw_key}
    )
    
    assert response.status_code == 200
```

---

## Performance Considerations

### Database Queries

**Lookup time:** O(1) via indexed prefix

```python
# Fast: indexed by prefix
api_key = APIKey.objects.filter(prefix="itq_abc123...").first()

# Slow: linear scan (don't do this)
api_key = APIKey.objects.filter(name__contains="test").first()
```

### Caching

Currently, no caching layer for API key lookups (each request hits the DB).

**Future optimization:** Redis cache with prefix → APIKey_id mapping, TTL 1 hour.

```python
# Pseudo-code
cache_key = f"api_key_prefix:{prefix}"
cached_api_key_id = redis.get(cache_key)
if cached_api_key_id:
    api_key = APIKey.objects.get(id=cached_api_key_id)
else:
    api_key = APIKey.objects.filter(prefix=prefix).first()
    redis.setex(cache_key, 3600, api_key.id)
```

---

## Extending the System

### Adding a New Auth Method

1. Create a new auth class in `apps/core/ninja_utils/auth.py`:

```python
class CustomAuth:
    def __call__(self, request):
        token = request.headers.get("X-Custom-Token")
        if token:
            # Validate token
            user = validate_token(token)
            if user:
                request.user = user
                return user
        return None
```

2. Add to `PublicAuth`:

```python
class PublicAuth:
    def __call__(self, request):
        methods = []
        if settings.ENABLE_API_KEY_AUTH:
            methods.append(ApiKeyAuth())
        if settings.ENABLE_CUSTOM_AUTH:
            methods.append(CustomAuth())
        if settings.ENABLE_OAUTH2:
            methods.append(OAuth2Auth())
        
        for auth_method in methods:
            result = auth_method(request)
            if result is not None:
                return result
        
        return AnonymousUser() if settings.ENABLE_ANONYMOUS_TRAFFIC else None
```

### Adding Usage Tracking to a New Endpoint

```python
from apps.usage_tracking.decorators.track_usage import track_usage

@router.get("new-endpoint/")
@track_usage(entity_type="custom", publisher_from="publisher")
def new_endpoint(request):
    # Automatically tracked with API key identity
    ...
```

---

## Debugging

### Enable Django Debug Toolbar

Add to `INSTALLED_APPS` (development only):

```python
INSTALLED_APPS = [
    # ...
    "debug_toolbar",
]

MIDDLEWARE = [
    # ...
    "debug_toolbar.middleware.DebugToolbarMiddleware",
]

INTERNAL_IPS = ["127.0.0.1"]
```

Then access `/__debug__/` in browser.

### Log Auth Attempts

Add to your view:

```python
import logging
logger = logging.getLogger(__name__)

@router.get("recitations/")
def list_recitations(request):
    logger.info(f"Auth method: {type(request.auth).__name__}")
    logger.info(f"User: {request.user}")
    logger.info(f"Is authenticated: {request.user.is_authenticated}")
    ...
```

### Inspect request.auth

```python
@router.get("recitations/")
def list_recitations(request):
    if hasattr(request, 'auth') and request.auth:
        print(f"API Key prefix: {request.auth.prefix}")
        print(f"Expiry: {request.auth.expiry_date}")
        print(f"Revoked: {request.auth.revoked}")
    ...
```

---

## References

- **django-ninja-keys docs:** Package handles APIKey model and bcrypt hashing
- **django-cors-headers docs:** https://github.com/adamchainz/django-cors-headers
- **Django Ninja auth:** https://django-ninja.rest-framework.com/guides/authentication/
