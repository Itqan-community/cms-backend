# Itqan CMS API Documentation

## API Overview

The Itqan CMS API provides endpoints for content management, user authentication, and system operations.

**Base URL**: `http://127.0.0.1:8000/api/v1/` (Development)
**Production URL**: `https://api.yourdomain.com/api/v1/`

## Interactive Documentation

### Swagger UI
- **URL**: [http://127.0.0.1:8000/swagger/](http://127.0.0.1:8000/swagger/)
- **Alternative**: [http://127.0.0.1:8000/docs/](http://127.0.0.1:8000/docs/)
- Interactive API documentation with request/response examples
- Test API endpoints directly from the browser

### ReDoc
- **URL**: [http://127.0.0.1:8000/redoc/](http://127.0.0.1:8000/redoc/)
- Clean, responsive API documentation
- Better for reading and understanding API structure

### OpenAPI Schema
- **JSON**: [http://127.0.0.1:8000/swagger.json](http://127.0.0.1:8000/swagger.json)
- **YAML**: [http://127.0.0.1:8000/swagger.yaml](http://127.0.0.1:8000/swagger.yaml)
- Machine-readable API specification

## Authentication

The API uses Auth0 JWT tokens for authentication.

### Headers
```http
Authorization: Bearer <jwt_token>
Content-Type: application/json
```

### Getting a Token
1. Authenticate via Auth0 (frontend handles this)
2. Token is automatically included in API requests
3. Token expires after 24 hours (configurable)

## API Endpoints

### System Endpoints

#### GET `/api/v1/`
Get API information and available endpoints.

**Response:**
```json
{
  "name": "Itqan CMS API",
  "version": "1.0.0",
  "description": "Content Management System API for Itqan platform",
  "endpoints": {
    "health": "/api/v1/health/",
    "auth": {
      "me": "/api/v1/auth/me/",
      "complete-profile": "/api/v1/auth/complete-profile/"
    },
    "docs": {
      "swagger": "/swagger/",
      "redoc": "/redoc/",
      "openapi": "/swagger.json"
    }
  }
}
```

#### GET `/api/v1/health/`
Health check endpoint to verify API status.

**Response:**
```json
{
  "status": "ok",
  "timestamp": "2024-01-01T12:00:00Z",
  "version": "1.0.0"
}
```

### Authentication Endpoints

#### GET `/api/v1/auth/me/`
Get current authenticated user information.

**Authentication**: Required
**Response:**
```json
{
  "id": "user-uuid",
  "email": "user@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "auth_provider": "auth0",
  "auth_provider_id": "auth0|123456",
  "is_active": true,
  "profile_completed": true,
  "created_at": "2024-01-01T12:00:00Z",
  "updated_at": "2024-01-01T12:00:00Z"
}
```

#### POST `/api/v1/auth/complete-profile/`
Complete user profile after Auth0 authentication.

**Authentication**: Required
**Request Body:**
```json
{
  "first_name": "John",
  "last_name": "Doe",
  "job_title": "Software Developer",
  "phone_number": "+1234567890",
  "business_model": "B2B",
  "team_size": "10-50",
  "about_yourself": "Experienced developer..."
}
```

**Response:**
```json
{
  "id": "user-uuid",
  "email": "user@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "auth_provider": "auth0",
  "auth_provider_id": "auth0|123456",
  "is_active": true,
  "profile_completed": true,
  "created_at": "2024-01-01T12:00:00Z",
  "updated_at": "2024-01-01T12:00:00Z"
}
```

## Error Responses

### Standard Error Format
```json
{
  "error": "Error message description",
  "code": "ERROR_CODE",
  "details": {
    "field": "Additional error details"
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
- `500` - Internal Server Error

### Common Errors

#### Authentication Errors
```json
{
  "error": "Authorization header required"
}
```

```json
{
  "error": "Invalid or expired token"
}
```

#### Validation Errors
```json
{
  "error": "Invalid JSON",
  "details": {
    "line": 1,
    "column": 15
  }
}
```

## Rate Limiting

- **Development**: No rate limiting
- **Production**: 1000 requests per hour per IP
- **Authenticated**: 5000 requests per hour per user

Rate limit headers:
```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1640995200
```

## CORS Policy

### Allowed Origins (Development)
- `http://localhost:3000`
- `http://127.0.0.1:3000`

### Allowed Origins (Production)
- `https://yourdomain.com`
- `https://www.yourdomain.com`

### Allowed Methods
- GET, POST, PUT, PATCH, DELETE, OPTIONS

### Allowed Headers
- Authorization, Content-Type, X-Requested-With

## Testing the API

### Using cURL

#### Health Check
```bash
curl -X GET http://127.0.0.1:8000/api/v1/health/
```

#### Get User Info (with token)
```bash
curl -X GET http://127.0.0.1:8000/api/v1/auth/me/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

#### Complete Profile
```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/complete-profile/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "John",
    "last_name": "Doe",
    "job_title": "Developer"
  }'
```

### Using JavaScript/Fetch

```javascript
// Get API info
const response = await fetch('http://127.0.0.1:8000/api/v1/');
const data = await response.json();

// Authenticated request
const userResponse = await fetch('http://127.0.0.1:8000/api/v1/auth/me/', {
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  }
});
const userData = await userResponse.json();
```

## SDK and Client Libraries

### JavaScript/TypeScript
```bash
npm install @itqan/cms-api-client
```

### Python
```bash
pip install itqan-cms-client
```

## Changelog

### v1.0.0 (Current)
- Initial API release
- Auth0 authentication
- User profile management
- Health check endpoints
- Swagger documentation

## Support

- **Documentation**: [Swagger UI](http://127.0.0.1:8000/swagger/)
- **Issues**: GitHub Issues
- **Email**: api@itqan.com
