"""
Authentication views implementing the API contract
"""
import logging
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from drf_spectacular.utils import extend_schema, OpenApiResponse
from allauth.socialaccount.models import SocialApp
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from .auth_serializers import (
    RegisterSerializer, LoginSerializer, UserProfileSerializer,
    UserProfileUpdateSerializer, AuthResponseSerializer, ErrorResponseSerializer,
    TokenRefreshResponseSerializer, create_auth_response, create_error_response
)

User = get_user_model()
logger = logging.getLogger(__name__)


class RegisterView(APIView):
    """
    API 1.1: Register with Email/Password
    """
    permission_classes = [AllowAny]
    
    @extend_schema(
        summary="Register with email/password",
        description="Create new user account with email and password",
        request=RegisterSerializer,
        responses={
            201: OpenApiResponse(
                response=AuthResponseSerializer,
                description="User registered successfully"
            ),
            409: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Email already taken"
            )
        }
    )
    def post(self, request):
        """Register new user with email/password"""
        serializer = RegisterSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                user = serializer.save()
                
                # Create response with tokens
                response_data = create_auth_response(user)
                
                logger.info(f"User {user.email} registered successfully")
                return Response(response_data, status=status.HTTP_201_CREATED)
                
            except Exception as e:
                logger.error(f"Registration error: {e}")
                return Response(
                    create_error_response("REGISTRATION_FAILED", "Registration failed"),
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        # Handle validation errors with detailed field information
        if 'email' in serializer.errors:
            error_message = serializer.errors['email'][0]
            error_code = "EMAIL_TAKEN"
            status_code = status.HTTP_409_CONFLICT
        else:
            # Return detailed validation errors for better debugging
            error_code = "VALIDATION_ERROR"
            status_code = status.HTTP_400_BAD_REQUEST
            
            # Create detailed error message with field-specific errors
            error_details = {}
            for field, errors in serializer.errors.items():
                error_details[field] = errors if isinstance(errors, list) else [str(errors)]
            
            # Create a user-friendly error message
            if 'password' in serializer.errors:
                error_message = f"Password validation failed: {'; '.join(serializer.errors['password'])}"
            else:
                error_message = "Registration data validation failed"
            
            # Return response with detailed field errors
            return Response({
                "error": {
                    "code": error_code,
                    "message": error_message,
                    "details": error_details
                }
            }, status=status_code)
        
        return Response(
            create_error_response(error_code, error_message),
            status=status_code
        )


class LoginView(APIView):
    """
    API 1.2: Login with Email/Password
    """
    permission_classes = [AllowAny]
    
    @extend_schema(
        summary="Login with email/password",
        description="Authenticate user with email and password",
        request=LoginSerializer,
        responses={
            200: OpenApiResponse(
                response=AuthResponseSerializer,
                description="Login successful"
            ),
            401: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Invalid credentials"
            )
        }
    )
    def post(self, request):
        """Login user with email/password"""
        serializer = LoginSerializer(data=request.data)
        
        if serializer.is_valid():
            user = serializer.validated_data['user']
            
            # Update last login
            user.last_login = timezone.now()
            user.save(update_fields=['last_login'])
            
            # Create response with tokens
            response_data = create_auth_response(user)
            
            logger.info(f"User {user.email} logged in successfully")
            return Response(response_data, status=status.HTTP_200_OK)
        
        return Response(
            create_error_response("INVALID_CREDENTIALS", "Invalid email or password"),
            status=status.HTTP_401_UNAUTHORIZED
        )


class OAuthStartView(APIView):
    """
    API 1.3: OAuth2 - Google/GitHub Login Start
    """
    permission_classes = [AllowAny]
    
    @extend_schema(
        summary="Start OAuth2 authentication",
        description="Redirect to OAuth provider for authentication",
        responses={
            302: OpenApiResponse(description="Redirect to OAuth provider")
        }
    )
    def get(self, request, provider=None):
        """Start OAuth authentication flow"""
        # Get provider from URL kwargs if not in path
        if not provider:
            provider = self.kwargs.get('provider')
        
        if provider not in ['google', 'github']:
            return Response(
                create_error_response("INVALID_PROVIDER", "Unsupported OAuth provider"),
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Try to build the OAuth URL using allauth's URL patterns
            # Use provider-specific URL name (e.g., 'github_login', 'google_login')
            oauth_url = request.build_absolute_uri(
                reverse(f'{provider}_login')
            )
        except Exception as e:
            # If allauth URLs are not available, return a helpful message
            logger.warning(f"OAuth URL reverse failed for {provider}: {e}")
            return Response({
                'message': f'OAuth {provider} not fully configured. Please set up Google/GitHub app credentials.',
                'provider': provider,
                'error': 'OAuth provider not configured'
            }, status=status.HTTP_501_NOT_IMPLEMENTED)
        
        return Response({
            'auth_url': oauth_url,
            'provider': provider
        }, status=status.HTTP_200_OK)


class OAuthCallbackView(APIView):
    """
    API 1.3: OAuth2 - Google/GitHub Login Callback
    This will be handled by allauth's built-in views, but we provide this for documentation
    """
    permission_classes = [AllowAny]
    
    @extend_schema(
        summary="OAuth2 callback",
        description="Handle OAuth provider callback",
        responses={
            200: OpenApiResponse(
                response=AuthResponseSerializer,
                description="OAuth login successful"
            )
        }
    )
    def get(self, request, provider=None):
        """Handle OAuth callback - this is documented but handled by allauth"""
        # Get provider from URL kwargs if not in path
        if not provider:
            provider = self.kwargs.get('provider')
            
        # This view is for documentation purposes
        # Actual OAuth callback is handled by allauth's built-in views
        return Response({
            'message': f'This endpoint is handled by allauth socialaccount views for {provider}'
        })


class UserProfileView(APIView):
    """
    API 1.4: Get User Profile & API 1.5: Update User Profile
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Get user profile",
        description="Get authenticated user's profile information",
        responses={
            200: OpenApiResponse(
                response=UserProfileSerializer,
                description="User profile retrieved successfully"
            )
        }
    )
    def get(self, request):
        """Get current user's profile"""
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @extend_schema(
        summary="Update user profile",
        description="Update authenticated user's profile information",
        request=UserProfileUpdateSerializer,
        responses={
            200: OpenApiResponse(
                description="Profile updated successfully"
            )
        }
    )
    def put(self, request):
        """Update current user's profile"""
        serializer = UserProfileUpdateSerializer(
            request.user, 
            data=request.data, 
            partial=True
        )
        
        if serializer.is_valid():
            user = serializer.save()
            
            return Response({
                'message': 'Profile updated successfully',
                'profile': {
                    'id': user.id,
                    'profile_completed': user.profile_completed
                }
            }, status=status.HTTP_200_OK)
        
        return Response(
            create_error_response("VALIDATION_ERROR", "Invalid profile data"),
            status=status.HTTP_400_BAD_REQUEST
        )


# UserProfileUpdateView merged into UserProfileView above


class TokenRefreshView(TokenRefreshView):
    """
    API 1.6: Refresh Token
    """
    
    @extend_schema(
        summary="Refresh access token",
        description="Get new access token using refresh token",
        responses={
            200: OpenApiResponse(
                response=TokenRefreshResponseSerializer,
                description="Token refreshed successfully"
            )
        }
    )
    def post(self, request, *args, **kwargs):
        """Refresh access token"""
        try:
            response = super().post(request, *args, **kwargs)
            
            # Transform response to match API contract
            if response.status_code == 200:
                return Response({
                    'access_token': response.data['access']
                }, status=status.HTTP_200_OK)
            
            return response
            
        except (TokenError, InvalidToken):
            return Response(
                create_error_response("INVALID_TOKEN", "Invalid or expired refresh token"),
                status=status.HTTP_401_UNAUTHORIZED
            )


class LogoutView(APIView):
    """
    API 1.7: Logout
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Logout user",
        description="Logout authenticated user and invalidate tokens",
        responses={
            204: OpenApiResponse(description="Logout successful")
        }
    )
    def post(self, request):
        """Logout user"""
        try:
            # Get refresh token from request body
            refresh_token = request.data.get('refresh_token')
            
            if refresh_token:
                # Blacklist the refresh token
                token = RefreshToken(refresh_token)
                token.blacklist()
            
            logger.info(f"User {request.user.email} logged out successfully")
            return Response(status=status.HTTP_204_NO_CONTENT)
            
        except Exception as e:
            logger.warning(f"Logout error for user {request.user.email}: {e}")
            # Even if token blacklisting fails, consider logout successful
            return Response(status=status.HTTP_204_NO_CONTENT)



