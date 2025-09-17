"""
Mock API Views - Dummy data endpoints for all CMS API endpoints
Fully compliant with OpenAPI 3.1.0 specification in src/openapi.yaml
"""

import json
import uuid
from datetime import datetime, timezone, timedelta
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.http import HttpResponse
from .dummy_data import (
    DUMMY_USERS, DUMMY_LICENSES, DUMMY_PUBLISHERS, DUMMY_ASSETS,
    CONTENT_STANDARDS, APP_CONFIG, TEST_CREDENTIALS
)

def generate_jwt_token(user_id, token_type="access"):
    """Generate a realistic-looking JWT token for mock purposes"""
    import base64
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "user_id": user_id,
        "type": token_type,
        "exp": int((datetime.now() + timedelta(hours=24)).timestamp()),
        "iat": int(datetime.now().timestamp())
    }
    
    # Base64 encode header and payload (mock JWT structure)
    header_b64 = base64.b64encode(json.dumps(header).encode()).decode().rstrip('=')
    payload_b64 = base64.b64encode(json.dumps(payload).encode()).decode().rstrip('=')
    signature = f"mock_signature_{user_id}_{token_type}"
    
    return f"{header_b64}.{payload_b64}.{signature}"


# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):
    """Register with email and password - matches OpenAPI spec exactly"""
    data = request.data
    
    # Validate required fields as per OpenAPI spec
    required_fields = ['email', 'password', 'first_name', 'last_name']
    for field in required_fields:
        if not data.get(field):
            return Response({
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": f"Field '{field}' is required"
                }
            }, status=status.HTTP_400_BAD_REQUEST)
    
    # Check if email already exists (simulate)
    existing_emails = [user['email'] for user in DUMMY_USERS]
    if data.get('email') in existing_emails:
        return Response({
            "error": {
                "code": "EMAIL_TAKEN",
                "message": "Email already exists"
            }
        }, status=status.HTTP_409_CONFLICT)
    
    # Create user response matching OpenAPI AuthResponse schema
    new_user_id = 99
    user_data = {
        "access_token": generate_jwt_token(new_user_id, "access"),
        "refresh_token": generate_jwt_token(new_user_id, "refresh"),
        "user": {
            "id": new_user_id,
            "email": data.get('email'),
            "name": f"{data.get('first_name')} {data.get('last_name')}",
            "first_name": data.get('first_name'),
            "last_name": data.get('last_name'),
            "phone_number": data.get('phone_number', ''),
            "title": data.get('title', ''),
            "avatar_url": '',
            "bio": '',
            "publisher": '',
            "location": '',
            "website": '',
            "github_username": '',
            "email_verified": False,
            "profile_completed": False,
            "auth_provider": "email"
        }
    }
    
    return Response(user_data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_user(request):
    """Login with email and password"""
    data = request.data
    email = data.get('email', '')
    password = data.get('password', '')
    
    # Check if credentials match any test user
    valid_credential = next((c for c in TEST_CREDENTIALS if c['email'] == email and c['password'] == password), None)
    
    if not valid_credential:
        return Response({
            "error": {
                "code": "INVALID_CREDENTIALS", 
                "message": "Invalid email or password"
            }
        }, status=status.HTTP_401_UNAUTHORIZED)
    
    # Find the corresponding user
    user = next((u for u in DUMMY_USERS if u['email'] == email), None)
    
    if not user:
        return Response({
            "error": {
                "code": "USER_NOT_FOUND",
                "message": "User not found"
            }
        }, status=status.HTTP_401_UNAUTHORIZED)
    
    auth_response = {
        "access_token": generate_jwt_token(user['id'], "access"),
        "refresh_token": generate_jwt_token(user['id'], "refresh"),
        "user": user
    }
    
    return Response(auth_response, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def oauth_google_start(request):
    """Start Google OAuth flow"""
    return Response({
        "redirect_url": "https://accounts.google.com/oauth/authorize?client_id=dummy"
    }, status=status.HTTP_302_FOUND)


@api_view(['GET'])
@permission_classes([AllowAny])
def oauth_github_start(request):
    """Start GitHub OAuth flow"""
    return Response({
        "redirect_url": "https://github.com/login/oauth/authorize?client_id=dummy"
    }, status=status.HTTP_302_FOUND)


@api_view(['GET'])
@permission_classes([AllowAny])
def oauth_google_callback(request):
    """Handle Google OAuth callback"""
    # Return a random Google-authenticated user
    google_users = [u for u in DUMMY_USERS if u['auth_provider'] == 'google']
    user = google_users[0] if google_users else DUMMY_USERS[1]  # Fallback to Fatima Ali
    
    return Response({
        "access_token": generate_jwt_token(user['id'], "access"),
        "refresh_token": generate_jwt_token(user['id'], "refresh"),
        "user": user
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def oauth_github_callback(request):
    """Handle GitHub OAuth callback"""
    # Return a GitHub-authenticated user (Omar Ibrahim or Mariam Zahid or GitHub Developer)
    github_users = [u for u in DUMMY_USERS if u['auth_provider'] == 'github']
    user = github_users[0] if github_users else DUMMY_USERS[2]  # Fallback to Omar Ibrahim
    
    return Response({
        "access_token": generate_jwt_token(user['id'], "access"),
        "refresh_token": generate_jwt_token(user['id'], "refresh"),
        "user": user
    }, status=status.HTTP_200_OK)


@api_view(['GET', 'PUT'])
@permission_classes([AllowAny])
def user_profile(request):
    """Get or update user profile - matches OpenAPI spec exactly"""
    if request.method == 'GET':
        # Return user profile matching OpenAPI User schema
        return Response(DUMMY_USERS[0], status=status.HTTP_200_OK)
    
    elif request.method == 'PUT':
        # Update user profile
        return Response({
            "message": "Profile updated successfully",
            "profile": {
                "id": 1,
                "profile_completed": True
            }
        }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def refresh_token(request):
    """Refresh access token - matches OpenAPI spec exactly"""
    data = request.data
    
    # Validate required refresh_token field
    if not data.get('refresh_token'):
        return Response({
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Field 'refresh_token' is required"
            }
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Extract user_id from refresh token (mock extraction)
    refresh_token = data.get('refresh_token', '')
    # In real implementation, you'd decode and validate the token
    # For mock, we'll use a default user ID
    user_id = 1  # Default to first user for mock
    
    # Return only access_token as per OpenAPI spec
    return Response({
        "access_token": generate_jwt_token(user_id, "access")
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def logout_user(request):
    """Logout user"""
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
@permission_classes([AllowAny])
def list_test_users(request):
    """List all available test users and their credentials for development"""
    test_users = []
    
    for user in DUMMY_USERS:
        # Find the test credential for this user
        credential = next((c for c in TEST_CREDENTIALS if c['email'] == user['email']), None)
        
        test_user_info = {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "auth_provider": user["auth_provider"],
            "publisher": user["publisher"],
            "location": user["location"],
            "github_username": user.get("github_username"),
            "password": credential["password"] if credential else "N/A"
        }
        test_users.append(test_user_info)
    
    return Response({
        "message": "Available test users for development",
        "total_users": len(test_users),
        "users": test_users,
        "usage": {
            "email_login": "POST /mock-api/auth/login with email and password",
            "google_oauth": "GET /mock-api/auth/oauth/google/callback (returns random Google user)",
            "github_oauth": "GET /mock-api/auth/oauth/github/callback (returns random GitHub user)"
        }
    }, status=status.HTTP_200_OK)