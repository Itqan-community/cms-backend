<aside>
💡

CMS Backend Base URLs for both Staging and Production

- Develop: `develop.api.cms.itqan.dev`
- Staging: `staging.api.cms.itqan.dev`
- Production: `api.cms.itqan.dev`
</aside>

# Wireframes + APIs

## Global Configuration

### Required Headers (All APIs)
```
Authorization: Bearer <jwt_token>
Content-Type: application/json
Accept: application/json
```

### Error Response Format
```json
{
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Invalid or expired token"
  }
}
```

## 1) User Signup + Login + Profile

**Related Wireframes:**
- `backend/ai-memory-bank/docs/screens/2c-email-register.png`
- `backend/ai-memory-bank/docs/screens/2a-login.png`
- `backend/ai-memory-bank/docs/screens/2d-after-register-extra-profile-details-capture.png`
- `backend/ai-memory-bank/docs/screens/2b-github-google-register.png`

### 1.1) Register with Email/Password
- **HTTP Method:** POST
- **API URL:** `/auth/register`
- **Request Body:**
```json
{
  "email": "ahmed@example.com",
  "password": "secret123",
  "first_name": "Ahmed",
  "last_name": "AlRajhy",
  "phone_number": "009650000000",
  "title": "Software Engineer"
}
```
- **Response:**
  - Success - 201
```json
{
  "access_token": "jwt_token_here",
  "refresh_token": "refresh_token_here",
  "user": {
    "id": 1,
    "email": "ahmed@example.com",
    "name": "Ahmed AlRajhy",
    "first_name": "Ahmed",
    "last_name": "AlRajhy",
    "phone_number": "009650000000",
    "title": "Software Engineer",
    "email_verified": false,
    "profile_completed": false,
    "auth_provider": "email"
  }
}
```
  - Error - 409 (Email taken)
```json
{
  "error": {
    "code": "EMAIL_TAKEN",
    "message": "Email already exists"
  }
}
```

### 1.2) Login with Email/Password
- **HTTP Method:** POST
- **API URL:** `/auth/login`
- **Request Body:**
```json
{
  "email": "user@example.com",
  "password": "secret123"
}
```
- **Response:**
  - Success - 200
```json
{
  "access_token": "jwt_token_here",
  "refresh_token": "refresh_token_here",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "name": "Ahmed Hassan",
    "email_verified": true,
    "profile_completed": true
  }
}
```
  - Error - 401 (Invalid credentials)
```json
{
  "error": {
    "code": "INVALID_CREDENTIALS",
    "message": "Invalid email or password"
  }
}
```

### 1.3) OAuth2 - Google/GitHub Login
- **HTTP Method:** GET
- **API URL:** `/auth/oauth/google/start` or `/auth/oauth/github/start`
- **Response:** 302 redirect to OAuth provider

- **HTTP Method:** GET
- **API URL:** `/auth/oauth/google/callback` or `/auth/oauth/github/callback`
- **Query Params:** `code`, `state`
- **Response:**
  - Success - 200
```json
{
  "access_token": "jwt_token_here",
  "refresh_token": "refresh_token_here",
  "user": {
    "id": 1,
    "email": "user@gmail.com",
    "name": "Ahmed Hassan",
    "avatar_url": "https://...",
    "auth_provider": "google",
    "email_verified": true,
    "profile_completed": false
  }
}
```

### 1.4) Get User Profile
- **HTTP Method:** GET
- **API URL:** `/auth/profile`
- **Headers:** Authorization: Bearer <jwt_token>
- **Response:**
  - Success - 200
```json
{
  "id": 1,
  "email": "ahmed@example.com",
  "name": "Ahmed AlRajhy",
  "first_name": "Ahmed",
  "last_name": "AlRajhy",
  "phone_number": "009650000000",
  "title": "Software Engineer",
  "avatar_url": "https://...",
  "bio": "Developer interested in Quranic datasets",
  "organization": "Tech Solutions Inc",
  "location": "Cairo, Egypt",
  "website": "https://example.com",
  "github_username": "ahmeddev",
  "email_verified": true,
  "profile_completed": true,
  "auth_provider": "email"
}
```

### 1.5) Update User Profile
- **HTTP Method:** PUT
- **API URL:** `/auth/profile`
- **Headers:** Authorization: Bearer <jwt_token>
- **Request Body:**
```json
{
  "name": "Ahmed AlRajhy",
  "first_name": "Ahmed",
  "last_name": "AlRajhy",
  "phone_number": "009650000000",
  "title": "Software Engineer",
  "bio": "Developer interested in Quranic datasets",
  "organization": "Tech Solutions Inc",
  "location": "Cairo, Egypt",
  "website": "https://example.com",
  "github_username": "ahmeddev"
}
```
- **Response:**
  - Success - 200
```json
{
  "message": "Profile updated successfully",
  "profile": {
    "id": 1,
    "profile_completed": true
  }
}
```

### 1.6) Refresh Token
- **HTTP Method:** POST
- **API URL:** `/auth/token/refresh`
- **Request Body:**
```json
{
  "refresh_token": "refresh_token_here"
}
```
- **Response:**
  - Success - 200
```json
{
  "access_token": "new_jwt_token_here"
}
```

### 1.7) Logout
- **HTTP Method:** POST
- **API URL:** `/auth/logout`
- **Headers:** Authorization: Bearer <jwt_token>
- **Response:**
  - Success - 204 (No Content)

## 2) Assets Listing

**Related Wireframes:**
- `backend/ai-memory-bank/docs/screens/1-authenticated-assets-listing.png`
- `backend/ai-memory-bank/docs/screens/1-unauthenticated-assets-listing.png`

- **HTTP Method:** GET
- **API URL:** `/assets`
- **Headers:** Authorization: Bearer <jwt_token> (Optional - for authenticated view)
- **Query Parameters:**
    - `category=mushaf|tafsir|recitation` (Filter by category)
    - `license_code=cc0|cc-by-4.0` (Filter by license)
- **Response:**
    - Success - 200
```json
{
  "assets": [
    {
      "id": 1,
      "title": "Quran Uthmani",
      "description": "Quran Uthmani Description Summary",
      "thumbnail_url": "https://cdn.example.com/thumbnails/asset-1.jpg",
      "category": "mushaf",
      "license": {
        "code": "cc0",
        "name": "CC0 - Public Domain"
      },
      "publisher": {
        "id": 1,
        "name": "Tafsir Center",
        "thumbnail_url": "https://cdn.example.com/publishers/publisher-1.jpg"
      },
      "has_access": false,
      "download_count": 1250,
      "file_size": "2.5 MB"
    },
    {
      "id": 2,
      "title": "Tafsir Ibn Katheer",
      "description": "Tafsir Ibn Katheer Description Summary",
      "thumbnail_url": "https://cdn.example.com/thumbnails/asset-2.jpg",
      "category": "tafsir",
      "license": {
        "code": "cc-by-4.0",
        "name": "CC BY 4.0"
      },
      "publisher": {
        "id": 1,
        "name": "Tafsir Center",
        "thumbnail_url": "https://cdn.example.com/publishers/publisher-1.jpg"
      },
      "has_access": true,
      "download_count": 890,
      "file_size": "15.2 MB"
    }
  ]
}
```

- **Notes:**
    - JWT token is optional - unauthenticated users can view assets but `has_access` will be false
    - Categories limited to: **Mushaf, Tafsir, Recitation**
    - No pagination for V1 simplicity
    - Authenticated users see `has_access` status for each asset

## 3) Asset Details Page

**Related Wireframes:**
- `backend/ai-memory-bank/docs/screens/3a-asset-details-page.png`

- **HTTP Method:** GET
- **API URL:** `/assets/{asset_id}`
- **Headers:** Authorization: Bearer <jwt_token> (Optional - for access status)
- **Response:**
    - Success - 200
```json
{
  "id": 10,
  "title": "Quran Uthmani Script",
  "description": "Complete Quran text in Uthmani script with verse indexing and metadata",
  "long_description": "This comprehensive dataset contains the full Quranic text in the traditional Uthmani script...",
  "thumbnail_url": "https://cdn.example.com/thumbnails/asset-10.jpg",
  "category": "mushaf",
  "license": {
    "code": "cc0",
    "name": "CC0 - Public Domain"
  },
  "snapshots": [
    {
      "thumbnail_url": "https://cdn.example.com/snapshots/asset-10-1.jpg",
      "title": "لقطة من المحتوى ١",
      "description": "كما هو مبين في اللقطة المرفقة ١ .. كلام"
    },
    {
      "thumbnail_url": "https://cdn.example.com/snapshots/asset-10-2.jpg",
      "title": "لقطة من المحتوى ٢",
      "description": "كما هو مبين في اللقطة المرفقة ٢ .. كلام"
    }
  ],
  "publisher": {
    "id": 1,
    "name": "Tafsir Center",
    "thumbnail_url": "https://cdn.example.com/publishers/publisher-1.jpg",
    "bio": "Dedicated to preserving Quranic texts",
    "verified": true
  },
  "resource": {
    "id": 5,
    "title": "Quranic Text Collection",
    "description": "Collection of Quranic texts in various formats"
  },
  "technical_details": {
    "file_size": "2.5 MB",
    "format": "json",
    "encoding": "UTF-8",
    "version": "1.0.0",
    "language": "ar"
  },
  "stats": {
    "download_count": 1250,
    "view_count": 5420,
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-20T14:20:00Z"
  },
  "access": {
    "has_access": false,
    "requires_approval": false
  },
  "related_assets": [
    {
      "id": 11,
      "title": "Quran Audio - Al-Afasy",
      "thumbnail_url": "https://cdn.example.com/thumbnails/asset-11.jpg"
    }
  ]
}
```

- **Notes:**
    - JWT token is optional - unauthenticated users can view details but `has_access` will be false
    - V1: `requires_approval` is always false (auto-approve)

## 4) Asset Details Page > Download Asset

**Related Wireframes:**
- `backend/ai-memory-bank/docs/screens/3a-asset-details-page.png`
- `backend/ai-memory-bank/docs/screens/4a-asset-details-page-access-request-popup-questions.png`

### 4.1) Request Asset Access
- **HTTP Method:** POST
- **API URL:** `/assets/{asset_id}/request-access`
- **Headers:** Authorization: Bearer <jwt_token>
- **Request Body:**
```json
{
  "purpose": "Academic research on Quranic linguistics",
  "intended_use": "non-commercial"
}
```
- **Response:**
    - Success - 200
```json
{
  "request_id": 123,
  "status": "approved",
  "message": "Access granted automatically",
  "access": {
    "download_url": "/assets/10/download",
    "expires_at": null,
    "granted_at": "2024-01-25T15:30:00Z"
  }
}
```

### 4.2) Download Asset File
- **HTTP Method:** GET
- **API URL:** `/assets/{asset_id}/download`
- **Headers:** Authorization: Bearer <jwt_token>
- **Response:**
    - Success - 200
```
# Binary file download with appropriate headers
Content-Type: application/json | application/xml | audio/mpeg | etc.
Content-Disposition: attachment; filename="quran-uthmani-v1.0.0.json"
Content-Length: 2621440
```
    - Error - 403 (No access)
```json
{
  "error": {
    "code": "ACCESS_DENIED",
    "message": "You need to request access to download this asset"
  }
}
```

- **Notes:**
    - Requires JWT token
    - V1: Auto-approve all access requests
    - Auto-creates AssetAccessRequest & AssetAccess objects implicitly

## 5) Download Original Resource

**Related Wireframes:**
- `backend/ai-memory-bank/docs/screens/3a-asset-details-page.png`

- **HTTP Method:** GET
- **API URL:** `/resources/{resource_id}/download`
- **Headers:** Authorization: Bearer <jwt_token>
- **Response:**
    - Success - 200
```
# Binary file download with appropriate headers
Content-Type: application/zip | application/tar.gz | etc.
Content-Disposition: attachment; filename="quranic-text-collection-v1.2.0.zip"
Content-Length: 15728640
```
    - Error - 403 (No access)
```json
{
  "error": {
    "code": "ACCESS_DENIED",
    "message": "You need access to at least one asset in this resource to download"
  }
}
```

- **Notes:**
    - Requires JWT token
    - Downloads the complete resource package containing all assets user has access to

## 6) Publisher Details Page

**Related Wireframes:**
- `backend/ai-memory-bank/docs/screens/3c-publisher-page-details-with-all-related-assets.png`

- **HTTP Method:** GET
- **API URL:** `/publishers/{publisher_id}`
- **Headers:** Authorization: Bearer <jwt_token> (Optional - for access status)
- **Response:**
    - Success - 200
```json
{
  "id": 5,
  "name": "Tafsir Center",
  "description": "Tafsir Center Description Summary",
  "bio": "Dedicated to preserving and sharing Quranic knowledge worldwide",
  "thumbnail_url": "https://cdn.example.com/publishers/publisher-5.jpg",
  "cover_url": "https://cdn.example.com/covers/publisher-5.jpg",
  "location": "Medina, Saudi Arabia",
  "website": "https://tafsircenter.org",
  "verified": true,
  "social_links": {
    "twitter": "@tafsircenter",
    "github": "tafsircenter"
  },
  "stats": {
    "resources_count": 12,
    "assets_count": 45,
    "total_downloads": 15600,
    "joined_at": "2023-11-15T09:00:00Z"
  },
  "assets": [
    {
      "id": 1,
      "title": "Quran Uthmani",
      "description": "Quran Uthmani Description Summary",
      "thumbnail_url": "https://cdn.example.com/thumbnails/asset-1.jpg",
      "category": "mushaf",
      "license": {
        "code": "cc0",
        "name": "CC0 - Public Domain"
      },
      "has_access": false,
      "download_count": 1250,
      "file_size": "2.5 MB"
    },
    {
      "id": 2,
      "title": "Tafsir Ibn Katheer",
      "description": "Tafsir Ibn Katheer Description Summary",
      "thumbnail_url": "https://cdn.example.com/thumbnails/asset-2.jpg",
      "category": "tafsir",
      "license": {
        "code": "cc-by-4.0",
        "name": "CC BY 4.0"
      },
      "has_access": true,
      "download_count": 890,
      "file_size": "15.2 MB"
    }
  ]
}
```

- **Notes:**
    - JWT token is optional - unauthenticated users can view publisher but `has_access` will be false for assets
    - Assets array contains same structure as Assets Listing API

## 7) License Details

**Related Wireframes:**
- `backend/ai-memory-bank/docs/screens/3b-resource-license-details-page.png`
- `backend/ai-memory-bank/docs/screens/4b-asset-details-page-popup-license-terms-term1.png`
- `backend/ai-memory-bank/docs/screens/4b-asset-details-page-popup-license-terms-term2.png`
- `backend/ai-memory-bank/docs/screens/4b-asset-details-page-popup-license-terms-term3.png`

### 7.1) Get License by Code
- **HTTP Method:** GET
- **API URL:** `/licenses/{license_code}`
- **Headers:** Authorization: Bearer <jwt_token> (Optional)
- **Response:**
    - Success - 200
```json
{
  "code": "cc0",
  "name": "CC0 - Public Domain",
  "short_name": "CC0",
  "url": "https://creativecommons.org/publicdomain/zero/1.0/",
  "icon_url": "https://cdn.example.com/licenses/cc0.svg",
  "summary": "You can copy, modify, distribute and perform the work",
  "full_text": "The person who associated a work with this deed has dedicated the work to the public domain...",
  "legal_code_url": "https://creativecommons.org/publicdomain/zero/1.0/legalcode",
  "license_terms": [
    {
      "title": "البند الأول",
      "description": "يحق لك نسخ وتعديل وتوزيع العمل",
      "order": 1
    },
    {
      "title": "البند الثاني",
      "description": "لا يوجد ضمان للعمل",
      "order": 2
    },
    {
      "title": "البند الثالث",
      "description": "لا تنطبق قيود العلامات التجارية",
      "order": 3
    }
  ],
  "permissions": [
    {
      "key": "commercial_use",
      "label": "Commercial use",
      "description": "You may use the material for commercial purposes"
    },
    {
      "key": "modification",
      "label": "Modify",
      "description": "You may adapt, remix, transform, and build upon the material"
    }
  ],
  "conditions": [],
  "limitations": [
    {
      "key": "no_warranty",
      "label": "No warranty",
      "description": "The material is provided as-is without warranties"
    }
  ],
  "usage_count": 1250
}
```

### 7.2) List All Licenses
- **HTTP Method:** GET
- **API URL:** `/licenses`
- **Headers:** Authorization: Bearer <jwt_token> (Optional)
- **Response:**
    - Success - 200
```json
{
  "licenses": [
    {
      "code": "cc0",
      "name": "CC0 - Public Domain",
      "short_name": "CC0",
      "icon_url": "https://cdn.example.com/licenses/cc0.svg",
      "is_default": true
    },
    {
      "code": "cc-by-4.0",
      "name": "Creative Commons Attribution 4.0",
      "short_name": "CC BY 4.0",
      "icon_url": "https://cdn.example.com/licenses/cc-by-4.0.svg",
      "is_default": false
    }
  ]
}
```

- **Notes:**
    - JWT token is optional - public information
    - V1: CC0 is the default license for all assets

## 8) Content Standards Page

**Related Wireframes:**
- `backend/ai-memory-bank/docs/screens/0-content-standards-page.png`

- **HTTP Method:** GET
- **API URL:** `/content-standards`
- **Headers:** Authorization: Bearer <jwt_token> (Optional)
- **Response:**
    - Success - 200
```json
{
  "version": "1.0",
  "last_updated": "2024-01-01T00:00:00Z",
  "sections": [
    {
      "title": "Data Quality Standards",
      "content": "All Quranic data must be verified against authentic sources and follow established scholarly standards...",
      "subsections": [
        {
          "title": "Text Accuracy",
          "content": "Text must match the Uthmani script and be verified by qualified scholars..."
        },
        {
          "title": "Audio Quality",
          "content": "Audio recordings must be clear, properly segmented, and from qualified reciters..."
        }
      ]
    },
    {
      "title": "Metadata Requirements",
      "content": "All resources must include comprehensive metadata...",
      "required_fields": [
        "title",
        "description",
        "category",
        "language",
        "license"
      ]
    },
    {
      "title": "Licensing Guidelines",
      "content": "Default license is CC0 for V1. All content must be properly licensed...",
      "default_license": "cc0"
    }
  ],
  "file_formats": {
    "supported": ["json", "xml", "csv", "mp3", "wav", "pdf"],
    "recommended": ["json", "xml"],
    "specifications": {
      "json": {
        "schema_url": "https://schemas.itqan.dev/quran-v1.json",
        "example_url": "https://examples.itqan.dev/quran.json"
      },
      "xml": {
        "schema_url": "https://schemas.itqan.dev/quran-v1.xsd",
        "example_url": "https://examples.itqan.dev/quran.xml"
      }
    }
  }
}
```

- **Notes:**
    - JWT token is optional - public information
    - Content standards are version controlled

## 9) Global System APIs

### 9.1) Application Configuration
- **HTTP Method:** GET
- **API URL:** `/config`
- **Headers:** Authorization: Bearer <jwt_token> (Optional)
- **Response:**
    - Success - 200
```json
{
  "version": "1.0.0",
  "features": {
    "auto_approve_access": true,
    "manual_license_review": false,
    "advanced_analytics": false,
    "api_access": false
  },
  "limits": {
    "max_file_size_mb": 100,
    "max_files_per_resource": 10,
    "max_resources_per_publisher": 50
  },
  "ui": {
    "primary_color": "#669B80",
    "dark_color": "#22433D",
    "supported_locales": ["en", "ar"],
    "default_locale": "en"
  },
  "categories": [
    {
      "key": "mushaf",
      "name": "Mushaf",
      "description": "Complete Quran text and manuscripts"
    },
    {
      "key": "tafsir",
      "name": "Tafsir",
      "description": "Quranic commentary and interpretation"
    },
    {
      "key": "recitation",
      "name": "Recitation",
      "description": "Audio recordings of Quranic recitation"
    }
  ],
  "external_links": {
    "docs": "https://docs.itqan.dev",
    "support": "https://support.itqan.dev",
    "github": "https://github.com/itqan-dev"
  }
}
```

### 9.2) Health Check
- **HTTP Method:** GET
- **API URL:** `/health`
- **Response:**
    - Success - 200
```json
{
  "status": "healthy",
  "timestamp": "2024-01-25T15:30:00Z",
  "version": "1.0.0",
  "services": {
    "database": "healthy",
    "storage": "healthy",
    "auth": "healthy"
  }
}
```

- **Notes:**
    - No authentication required
    - Used for monitoring and uptime checks
