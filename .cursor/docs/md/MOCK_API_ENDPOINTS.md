# Mock API - Dummy Data Endpoints

**Date:** 2025-09-02  
**Author:** Assistant  

## Overview
Created a comprehensive mock API that returns dummy data for all endpoints defined in the OpenAPI specification. This enables frontend development and testing without requiring a fully implemented backend.

## Objectives
- Provide dummy data endpoints for all CMS API endpoints
- Enable frontend development and testing
- Match OpenAPI specification exactly
- Return realistic sample data

## Implementation Details
- Created new Django app: `mock_api`
- Organized views into multiple files for maintainability
- Added comprehensive dummy data that matches API schemas
- Implemented all authentication, assets, publishers, licenses, resources, content standards, and system endpoints

### Key Files Created
- `src/mock_api/dummy_data.py` - All dummy data constants
- `src/mock_api/views.py` - Authentication endpoints
- `src/mock_api/asset_views.py` - Asset-related endpoints
- `src/mock_api/other_views.py` - Publishers, licenses, resources, content standards, system endpoints
- `src/mock_api/urls.py` - URL routing configuration
- `src/mock_api/apps.py` - Django app configuration

### URL Structure
All mock API endpoints are available under the `/mock-api/` prefix:

#### Authentication Endpoints
- `POST /mock-api/auth/register` - User registration
- `POST /mock-api/auth/login` - User login with email/password
- `GET /mock-api/auth/oauth/google/start` - Start Google OAuth
- `GET /mock-api/auth/oauth/github/start` - Start GitHub OAuth
- `GET /mock-api/auth/oauth/google/callback` - Google OAuth callback
- `GET /mock-api/auth/oauth/github/callback` - GitHub OAuth callback
- `GET /mock-api/auth/profile` - Get user profile
- `PUT /mock-api/auth/profile` - Update user profile
- `POST /mock-api/auth/token/refresh` - Refresh access token
- `POST /mock-api/auth/logout` - User logout
- `GET /mock-api/auth/test-users` - List all test users and credentials (dev only)

#### Assets Endpoints
- `GET /mock-api/assets` - List assets (supports ?category= and ?license_code= filters)
- `GET /mock-api/assets/{asset_id}` - Get asset details
- `POST /mock-api/assets/{asset_id}/request-access` - Request asset access
- `GET /mock-api/assets/{asset_id}/download` - Download asset file

#### Publishers Endpoints
- `GET /mock-api/publishers/{publisher_id}` - Get publisher details with assets

#### Resources Endpoints
- `GET /mock-api/resources/{resource_id}/download` - Download resource package

#### Licenses Endpoints
- `GET /mock-api/licenses` - List all licenses
- `GET /mock-api/licenses/{license_code}` - Get specific license details

#### Content Standards Endpoints
- `GET /mock-api/content-standards` - Get content quality standards

#### System Endpoints
- `GET /mock-api/config` - Get application configuration
- `GET /mock-api/health` - Health check

## Testing Results
| Test | Method | Outcome |
|---|-----|---|
| Assets List | `curl http://localhost:8000/mock-api/assets` | ✅ |
| User Profile | `curl http://localhost:8000/mock-api/auth/profile` | ✅ |
| Licenses List | `curl http://localhost:8000/mock-api/licenses` | ✅ |
| Publisher Details | `curl http://localhost:8000/mock-api/publishers/1` | ✅ |
| App Config | `curl http://localhost:8000/mock-api/config` | ✅ |
| Health Check | `curl http://localhost:8000/mock-api/health` | ✅ |
| Content Standards | `curl http://localhost:8000/mock-api/content-standards` | ✅ |
| User Login | `curl -X POST /mock-api/auth/login` | ✅ |
| Asset Access Request | `curl -X POST /mock-api/assets/2/request-access` | ✅ |
| Asset Download | `curl /mock-api/assets/2/download` | ✅ |

## Acceptance Criteria Verification
- [x] All OpenAPI endpoints have corresponding dummy implementations
- [x] Endpoints return realistic dummy data matching API schemas
- [x] Authentication endpoints work with proper JWT token responses
- [x] Asset endpoints support filtering and access control simulation
- [x] Download endpoints return proper file responses
- [x] Error handling for non-existent resources
- [x] POST endpoints accept and process request data
- [x] All endpoints are accessible without authentication (AllowAny permission)

## Next Steps
1. Frontend can now be developed against these mock API endpoints
2. Add more diverse dummy data if needed for specific test scenarios
3. Consider adding query parameter support for pagination/sorting
4. Real backend implementation can replace mock API endpoints incrementally

## Dummy Data Highlights
- **9 Test Users**: Various profiles with different auth providers and roles
  - Email Auth: Ahmed Hassan, Aisha Mohamed, Test User, Admin User
  - Google Auth: Fatima Ali, Yusuf Khan  
  - GitHub Auth: Omar Ibrahim, Mariam Zahid, GitHub Developer
- **2 Publishers**: Tafsir Center and Quranic Audio Foundation
- **4 Assets**: Mix of Quran texts, Tafsir, and audio recitations
- **2 Licenses**: CC0 and CC BY 4.0 with full license details
- **Content Standards**: Text and audio quality standards
- **App Config**: Feature flags, limits, UI settings, and external links

### Test User Credentials
Use `GET /mock-api/auth/test-users` to see all available test users and their passwords, or use these quick examples:
- **Simple Test**: `test@example.com` / `test`
- **Admin**: `admin@example.com` / `admin123`
- **GitHub User**: `omar.ibrahim@example.com` / `github789`
- **Developer**: `developer@github.com` / `opensource`

## Usage
Start the development server and access mock API endpoints:
```bash
python3 manage.py runserver

# List all test users and credentials
curl http://localhost:8000/mock-api/auth/test-users

# Test login with simple credentials
curl -X POST http://localhost:8000/mock-api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "test"}'

# Test GitHub OAuth callback
curl http://localhost:8000/mock-api/auth/oauth/github/callback

# List assets
curl http://localhost:8000/mock-api/assets
```

All endpoints return JSON data matching the OpenAPI specification and include proper HTTP status codes and error responses.
