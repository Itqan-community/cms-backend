"""
Mock API Views - Dummy data endpoints for all CMS API endpoints
"""

from datetime import datetime, timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.http import HttpResponse
from .dummy_data import (
    DUMMY_USERS, DUMMY_LICENSES, DUMMY_PUBLISHERS, DUMMY_ASSETS,
    CONTENT_STANDARDS, APP_CONFIG, TEST_CREDENTIALS
)


# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):
    """Register with email and password"""
    data = request.data
    
    user_data = {
        "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.dummy_token",
        "refresh_token": "refresh_token_dummy_12345",
        "user": {
            "id": 3,
            "email": data.get('email', 'new.user@example.com'),
            "name": data.get('name', 'New User'),
            "avatar_url": None,
            "bio": None,
            "organization": None,
            "location": None,
            "website": None,
            "github_username": None,
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
        "access_token": f"eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.dummy_token_user_{user['id']}",
        "refresh_token": f"refresh_token_user_{user['id']}_67890",
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
        "access_token": f"eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.oauth_google_token_user_{user['id']}",
        "refresh_token": f"refresh_token_google_user_{user['id']}_123",
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
        "access_token": f"eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.oauth_github_token_user_{user['id']}",
        "refresh_token": f"refresh_token_github_user_{user['id']}_456",
        "user": user
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_user_profile(request):
    """Get user profile"""
    return Response(DUMMY_USERS[0], status=status.HTTP_200_OK)


@api_view(['PUT'])
@permission_classes([AllowAny])
def update_user_profile(request):
    """Update user profile"""
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
    """Refresh access token"""
    return Response({
        "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.new_refreshed_token"
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
            "organization": user["organization"],
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