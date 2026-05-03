from django.conf import settings

from apps.core.ninja_utils.auth import ninja_oauth2_auth
from apps.core.ninja_utils.autodiscover import auto_discover_ninja_routers
from apps.core.ninja_utils.error_handling import register_exception_handlers

from .ninja_api import assert_all_itqan_routers, create_ninja_api

_DESCRIPTION = """
Itqan CMS Public APIs For Developers. All endpoints require a valid OAuth2 token.

## Step 1 — Create an application

You need a `client_id` and `client_secret` before you can call any endpoint.
There are two ways to get them:

### Option A — CMS website *(coming soon)*

Register or log in at [cms.itqan.dev](https://cms.itqan.dev), navigate to **Applications**, and create a new application.
Your `client_id` and `client_secret` will be shown — **save the secret immediately**, it is displayed only once.

### Option B — CMS API

If you already have a CMS account, you can create an application programmatically using your CMS JWT token:

```
POST https://api.cms.itqan.dev/cms-api/applications/
Authorization: Bearer <your_jwt_token>
Content-Type: application/json

{ "name": "my-app" }
```

Response:
```json
{ "id": 1, "name": "my-app", "client_id": "abc...", "client_secret": "xyz..." }
```

> The `client_secret` is shown **once** and cannot be retrieved again. If lost, delete the application and create a new one.

---

## Step 2 — Get an access token

Exchange your credentials for a bearer token:

```
POST https://api.cms.itqan.dev/token/
Authorization: Basic base64(client_id:client_secret)
```

Response:
```json
{ "access_token": "...", "expires_in": 86400, "token_type": "Bearer" }
```

Tokens are valid for **24 hours**. When one expires you will receive a `401` — simply request a new one.

---

## Step 3 — Call the API

Pass the token as a `Bearer` header on every request:

```
GET https://api.cms.itqan.dev/recitations/
Authorization: Bearer <access_token>
```
"""

_DESCRIPTION = _DESCRIPTION if settings.ENABLE_OAUTH2 else """"""

developers_api = create_ninja_api(
    title="Itqan CMS Public APIs For Developers",
    description=_DESCRIPTION,
    urls_namespace="",
    auth=ninja_oauth2_auth,
)

register_exception_handlers(developers_api)

auto_discover_ninja_routers(developers_api, "api/public")

# Safety check: ensure routers are of type ItqanRouter
assert_all_itqan_routers(developers_api)
