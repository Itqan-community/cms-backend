# CMS V1 - API Contract for Frontend Development

**Project**: Itqan CMS V1  
**Version**: 1.0  
**Date**: Generated for Frontend Team  
**Base URL**: `https://api.cms.itqan.dev/v1`

## Overview

This document outlines the REST API contracts for the Itqan CMS V1 frontend implementation. The APIs support the platform's mission to distribute Quranic data with two main actors: Publishers (upload data) and Consumers/Developers (access data).

### Key V1 Constraints
- **Auto-granted CC0 license** for all resources initially
- **Auto-approve access requests** for streamlined access
- **Owner + Manager roles** only (expanded later)
- **Semi-manual processing** by the Itqan team

---

## 1. Authentication APIs

### 1.1 User Profile Management
**Used by**: Profile capture screen, user settings

#### GET /auth/profile
Get current user profile
```json
Response: {
  "id": "uuid-123",
  "email": "user@example.com",
  "name": "Ahmed Hassan",
  "avatar_url": "https://cdn.itqan.dev/avatars/uuid-123.jpg",
  "role": "consumer", // consumer, publisher, manager, owner
  "bio": "Developer interested in Quranic datasets",
  "organization": "Tech Solutions Inc",
  "location": "Cairo, Egypt",
  "website": "https://example.com",
  "github_username": "ahmeddev",
  "created_at": "2024-01-15T10:30:00Z",
  "email_verified": true,
  "profile_completed": true
}
```

#### PUT /auth/profile
Update user profile
```json
Request: {
  "name": "Ahmed Hassan",
  "bio": "Developer interested in Quranic datasets",
  "organization": "Tech Solutions Inc",
  "location": "Cairo, Egypt",
  "website": "https://example.com",
  "github_username": "ahmeddev"
}

Response: {
  "message": "Profile updated successfully",
  "profile": { /* updated profile object */ }
}
```

### 1.2 Role Management
**Used by**: Admin interfaces, role-based UI

#### GET /auth/permissions
Get user permissions and capabilities
```json
Response: {
  "role": "publisher",
  "permissions": {
    "can_publish_resources": true,
    "can_manage_assets": true,
    "can_approve_requests": false,
    "can_access_admin": false
  },
  "quotas": {
    "max_resources": 50,
    "max_assets_per_resource": 10,
    "storage_limit_gb": 5
  }
}
```

---

## 2. Assets Management APIs

### 2.1 Asset Discovery
**Used by**: Asset listing pages (authenticated/unauthenticated)

#### GET /assets
List assets with filtering and pagination
```json
Query Parameters:
- page: integer (default: 1)
- per_page: integer (default: 20, max: 100)
- search: string (search in title, description, tags)
- category: string (quran, hadith, tafsir, etc.)
- publisher_id: uuid
- license_type: string (cc0, cc-by, etc.)
- format: string (json, xml, csv, audio, etc.)
- language: string (ar, en, etc.)
- sort: string (created_at, updated_at, title, downloads)
- order: string (asc, desc)

Response: {
  "assets": [
    {
      "id": "asset-uuid-123",
      "title": "Complete Quran Text - Uthmani Script",
      "description": "Full Quranic text in Uthmani script with verse indexing",
      "thumbnail_url": "https://cdn.itqan.dev/thumbnails/asset-123.jpg",
      "publisher": {
        "id": "pub-uuid-456",
        "name": "Quran Foundation",
        "avatar_url": "https://cdn.itqan.dev/publishers/pub-456.jpg"
      },
      "category": "quran",
      "tags": ["quran", "uthmani", "arabic", "text"],
      "format": "json",
      "language": "ar",
      "license": {
        "type": "cc0",
        "name": "CC0 - Public Domain",
        "url": "https://creativecommons.org/publicdomain/zero/1.0/"
      },
      "stats": {
        "downloads": 1250,
        "size_mb": 2.5,
        "version": "1.0.0"
      },
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-20T14:20:00Z",
      "access_required": false, // V1: auto-approve access
      "has_access": true // for authenticated users
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 156,
    "pages": 8,
    "has_next": true,
    "has_prev": false
  },
  "filters": {
    "categories": [
      {"value": "quran", "label": "Quran", "count": 45},
      {"value": "hadith", "label": "Hadith", "count": 32}
    ],
    "formats": [
      {"value": "json", "label": "JSON", "count": 67},
      {"value": "xml", "label": "XML", "count": 34}
    ],
    "languages": [
      {"value": "ar", "label": "Arabic", "count": 89},
      {"value": "en", "label": "English", "count": 67}
    ]
  }
}
```

### 2.2 Asset Details
**Used by**: Asset details page, download dialogs

#### GET /assets/{asset_id}
Get detailed asset information
```json
Response: {
  "id": "asset-uuid-123",
  "title": "Complete Quran Text - Uthmani Script",
  "description": "Full Quranic text in Uthmani script with verse indexing and metadata",
  "long_description": "This comprehensive dataset contains...",
  "thumbnail_url": "https://cdn.itqan.dev/thumbnails/asset-123.jpg",
  "preview_images": [
    "https://cdn.itqan.dev/previews/asset-123-1.jpg",
    "https://cdn.itqan.dev/previews/asset-123-2.jpg"
  ],
  "publisher": {
    "id": "pub-uuid-456",
    "name": "Quran Foundation",
    "avatar_url": "https://cdn.itqan.dev/publishers/pub-456.jpg",
    "bio": "Dedicated to preserving Quranic texts",
    "verified": true
  },
  "resource": {
    "id": "resource-uuid-789",
    "title": "Quranic Text Collection",
    "description": "Collection of Quranic texts in various formats"
  },
  "category": "quran",
  "tags": ["quran", "uthmani", "arabic", "text", "indexed"],
  "format": "json",
  "language": "ar",
  "version": {
    "current": "1.0.0",
    "changelog": "Initial release with full Quran text",
    "release_date": "2024-01-15T10:30:00Z"
  },
  "license": {
    "type": "cc0",
    "name": "CC0 - Public Domain",
    "url": "https://creativecommons.org/publicdomain/zero/1.0/",
    "summary": "You can copy, modify, distribute...",
    "permissions": ["commercial-use", "modification", "distribution"],
    "conditions": [],
    "limitations": ["no-warranty", "trademark-use"]
  },
  "technical_details": {
    "file_size": "2.5 MB",
    "encoding": "UTF-8",
    "schema_version": "1.0",
    "checksum_md5": "abc123...",
    "structure": {
      "verses": 6236,
      "chapters": 114,
      "pages": 604
    }
  },
  "stats": {
    "downloads": 1250,
    "views": 5420,
    "likes": 89,
    "rating": 4.8
  },
  "access": {
    "required": false, // V1: auto-approve
    "has_access": true,
    "download_url": "https://api.cms.itqan.dev/v1/assets/asset-uuid-123/download",
    "expires_at": null // V1: no expiration
  },
  "related_assets": [
    {
      "id": "asset-uuid-124",
      "title": "Quran Audio - Al-Afasy",
      "thumbnail_url": "https://cdn.itqan.dev/thumbnails/asset-124.jpg"
    }
  ],
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-20T14:20:00Z"
}
```

### 2.3 Asset Access Management
**Used by**: Access request popups, download handling

#### POST /assets/{asset_id}/request-access
Request access to an asset (V1: auto-approved)
```json
Request: {
  "purpose": "Academic research on Quranic linguistics",
  "organization": "Cairo University",
  "intended_use": "non-commercial",
  "additional_notes": "Will be used in PhD dissertation"
}

Response: {
  "request_id": "req-uuid-789",
  "status": "approved", // V1: always auto-approved
  "message": "Access granted automatically",
  "access": {
    "download_url": "https://api.cms.itqan.dev/v1/assets/asset-uuid-123/download",
    "expires_at": null, // V1: no expiration
    "granted_at": "2024-01-25T15:30:00Z"
  }
}
```

#### GET /assets/{asset_id}/download
Download asset file (requires access)
```
Response: Binary file download with appropriate headers
Content-Type: application/json | application/xml | audio/mpeg | etc.
Content-Disposition: attachment; filename="quran-uthmani-v1.0.0.json"
Content-Length: 2621440
```

---

## 3. Resources Management APIs

### 3.1 Resource Discovery
**Used by**: Resource browsing, publisher pages

#### GET /resources
List resources with metadata
```json
Query Parameters: (similar to assets)

Response: {
  "resources": [
    {
      "id": "resource-uuid-789",
      "title": "Quranic Text Collection",
      "description": "Comprehensive collection of Quranic texts",
      "thumbnail_url": "https://cdn.itqan.dev/resources/resource-789.jpg",
      "publisher": {
        "id": "pub-uuid-456",
        "name": "Quran Foundation"
      },
      "category": "quran",
      "version": "1.2.0",
      "assets_count": 5,
      "total_downloads": 3450,
      "license": {
        "type": "cc0",
        "name": "CC0 - Public Domain"
      },
      "created_at": "2024-01-10T08:00:00Z",
      "updated_at": "2024-01-22T12:15:00Z"
    }
  ],
  "pagination": { /* similar to assets */ }
}
```

### 3.2 Resource Details
**Used by**: Resource detail pages, asset organization

#### GET /resources/{resource_id}
Get resource with associated assets
```json
Response: {
  "id": "resource-uuid-789",
  "title": "Quranic Text Collection",
  "description": "Comprehensive collection of Quranic texts in multiple formats",
  "long_description": "This resource collection provides...",
  "publisher": { /* full publisher object */ },
  "category": "quran",
  "version": {
    "current": "1.2.0",
    "changelog": "Added Tajweed annotations",
    "previous_versions": ["1.0.0", "1.1.0"]
  },
  "license": { /* full license object */ },
  "assets": [
    { /* asset objects */ }
  ],
  "stats": {
    "total_downloads": 3450,
    "total_size": "12.5 MB",
    "assets_count": 5
  },
  "created_at": "2024-01-10T08:00:00Z",
  "updated_at": "2024-01-22T12:15:00Z"
}
```

---

## 4. Publishers Management APIs

### 4.1 Publisher Discovery
**Used by**: Publisher listings, discovery

#### GET /publishers
List publishers with basic info
```json
Query Parameters:
- page, per_page, search, sort, order

Response: {
  "publishers": [
    {
      "id": "pub-uuid-456",
      "name": "Quran Foundation",
      "bio": "Dedicated to preserving and sharing Quranic knowledge",
      "avatar_url": "https://cdn.itqan.dev/publishers/pub-456.jpg",
      "location": "Medina, Saudi Arabia",
      "website": "https://quranfoundation.org",
      "verified": true,
      "stats": {
        "resources_count": 12,
        "assets_count": 45,
        "total_downloads": 15600
      },
      "joined_at": "2023-11-15T09:00:00Z"
    }
  ],
  "pagination": { /* standard pagination */ }
}
```

### 4.2 Publisher Details
**Used by**: Publisher profile pages

#### GET /publishers/{publisher_id}
Get publisher details with resources
```json
Response: {
  "id": "pub-uuid-456",
  "name": "Quran Foundation",
  "bio": "Dedicated to preserving and sharing Quranic knowledge worldwide",
  "avatar_url": "https://cdn.itqan.dev/publishers/pub-456.jpg",
  "cover_url": "https://cdn.itqan.dev/covers/pub-456.jpg",
  "location": "Medina, Saudi Arabia",
  "website": "https://quranfoundation.org",
  "social_links": {
    "twitter": "@quranfoundation",
    "github": "quranfoundation",
    "linkedin": "company/quran-foundation"
  },
  "verified": true,
  "specialties": ["Quranic Text", "Audio Recordings", "Translations"],
  "stats": {
    "resources_count": 12,
    "assets_count": 45,
    "total_downloads": 15600,
    "avg_rating": 4.7
  },
  "featured_resources": [
    { /* resource objects */ }
  ],
  "recent_assets": [
    { /* asset objects */ }
  ],
  "joined_at": "2023-11-15T09:00:00Z"
}
```

---

## 5. License Management APIs

### 5.1 License Information
**Used by**: License detail pages, terms popups

#### GET /licenses
List available licenses
```json
Response: {
  "licenses": [
    {
      "type": "cc0",
      "name": "CC0 - Public Domain",
      "short_name": "CC0",
      "url": "https://creativecommons.org/publicdomain/zero/1.0/",
      "icon_url": "https://cdn.itqan.dev/licenses/cc0.svg",
      "summary": "You can copy, modify, distribute and perform the work",
      "is_default": true, // V1: CC0 is default
      "permissions": [
        {
          "key": "commercial-use",
          "label": "Commercial use",
          "description": "You may use the material for commercial purposes"
        }
      ],
      "conditions": [],
      "limitations": [
        {
          "key": "no-warranty",
          "label": "No warranty",
          "description": "The material is provided as-is"
        }
      ]
    }
  ]
}
```

#### GET /licenses/{license_type}
Get detailed license information
```json
Response: {
  "type": "cc0",
  "name": "CC0 - Public Domain",
  "url": "https://creativecommons.org/publicdomain/zero/1.0/",
  "full_text": "The person who associated a work with this deed...",
  "legal_code_url": "https://creativecommons.org/publicdomain/zero/1.0/legalcode",
  "summary": "Detailed license summary...",
  "permissions": [ /* detailed permissions */ ],
  "conditions": [ /* detailed conditions */ ],
  "limitations": [ /* detailed limitations */ ],
  "compatible_licenses": ["cc-by", "cc-by-sa"],
  "usage_count": 1250 // number of assets using this license
}
```

---

## 6. Search & Discovery APIs

### 6.1 Global Search
**Used by**: Search functionality across all screens

#### GET /search
Global search across assets, resources, publishers
```json
Query Parameters:
- q: string (search query)
- type: string (assets, resources, publishers, all)
- filters: object (category, format, language, etc.)

Response: {
  "query": "quran arabic",
  "results": {
    "assets": {
      "count": 45,
      "items": [ /* asset objects */ ]
    },
    "resources": {
      "count": 12,
      "items": [ /* resource objects */ ]
    },
    "publishers": {
      "count": 3,
      "items": [ /* publisher objects */ ]
    }
  },
  "suggestions": ["quran arabic text", "quran audio arabic"],
  "filters": { /* available filters based on results */ }
}
```

### 6.2 Search Suggestions
**Used by**: Search autocomplete

#### GET /search/suggestions
Get search suggestions
```json
Query Parameters:
- q: string (partial query)

Response: {
  "suggestions": [
    {
      "text": "quran arabic",
      "type": "popular",
      "count": 45
    },
    {
      "text": "quran audio",
      "type": "category",
      "count": 23
    }
  ]
}
```

---

## 7. Content Standards APIs

### 7.1 Content Guidelines
**Used by**: Content standards page

#### GET /content-standards
Get content standards and guidelines
```json
Response: {
  "version": "1.0",
  "last_updated": "2024-01-01T00:00:00Z",
  "sections": [
    {
      "title": "Data Quality Standards",
      "content": "All Quranic data must be verified against...",
      "subsections": [
        {
          "title": "Text Accuracy",
          "content": "Text must match the Uthmani script..."
        }
      ]
    },
    {
      "title": "Metadata Requirements",
      "content": "All resources must include...",
      "required_fields": [
        "title", "description", "category", "language"
      ]
    },
    {
      "title": "Licensing Guidelines",
      "content": "Default license is CC0 for V1...",
      "default_license": "cc0"
    }
  ],
  "file_formats": {
    "supported": ["json", "xml", "csv", "mp3", "wav"],
    "recommended": ["json", "xml"],
    "specifications": {
      "json": {
        "schema_url": "https://schemas.itqan.dev/quran-v1.json",
        "example_url": "https://examples.itqan.dev/quran.json"
      }
    }
  }
}
```

---

## 8. System APIs

### 8.1 Application Configuration
**Used by**: App initialization, feature flags

#### GET /config
Get application configuration
```json
Response: {
  "version": "1.0.0",
  "features": {
    "auto_approve_access": true, // V1 constraint
    "manual_license_review": false, // V1 constraint
    "advanced_analytics": false,
    "api_access": false // V1: files only
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
  "external_links": {
    "docs": "https://docs.itqan.dev",
    "support": "https://support.itqan.dev",
    "github": "https://github.com/itqan-dev"
  }
}
```

### 8.2 Health Check
**Used by**: Monitoring, uptime checks

#### GET /health
System health status
```json
Response: {
  "status": "healthy",
  "timestamp": "2024-01-25T15:30:00Z",
  "version": "1.0.0",
  "services": {
    "database": "healthy",
    "search": "healthy",
    "storage": "healthy",
    "auth": "healthy"
  }
}
```

---

## Authentication & Headers

### Required Headers
```
Authorization: Bearer <auth0-jwt-token>
Content-Type: application/json
Accept: application/json
User-Agent: Itqan-CMS-Frontend/1.0.0
```

### Error Responses
All APIs follow consistent error format:
```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "The requested asset was not found",
    "details": {
      "asset_id": "invalid-uuid"
    },
    "timestamp": "2024-01-25T15:30:00Z"
  }
}
```

### HTTP Status Codes
- `200` - Success
- `201` - Created
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden  
- `404` - Not Found
- `422` - Validation Error
- `500` - Internal Server Error

---

## Rate Limiting

- **Anonymous users**: 100 requests/hour
- **Authenticated users**: 1000 requests/hour  
- **Publishers**: 2000 requests/hour
- **Download endpoints**: 10 downloads/hour per user

Rate limit headers included in responses:
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1640995200
```

---

## Notes for Frontend Implementation

1. **V1 Simplifications**: Access is auto-approved, CC0 license is default
2. **Authentication**: Integration with Auth0 SPA SDK required
3. **Error Handling**: Implement consistent error display across all components  
4. **Pagination**: Use consistent pagination component for all lists
5. **Real-time Updates**: Not required for V1, but consider WebSocket placeholders
6. **Offline Support**: Not required for V1
7. **Caching**: Implement reasonable caching for static data (licenses, config)
8. **Analytics**: Basic download/view tracking only

---

**Document Version**: 1.0  
**Last Updated**: Generated for V1 Development  
**Contact**: development@itqan.dev
