"""
Core API views for authentication and user management
"""

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth import get_user_model, authenticate
from django.utils.decorators import method_decorator
from django.views import View
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import json
import jwt
import datetime
from django.conf import settings
from .auth0 import auth0_required, verify_auth0_token, get_or_create_user_from_auth0, Auth0Error

User = get_user_model()

@method_decorator(csrf_exempt, name='dispatch')
class AuthMeView(View):
    """
    Get current authenticated user information
    """
    
    @auth0_required
    def get(self, request):
        user = request.user
        
        # Check if user has completed profile
        profile_completed = bool(
            user.first_name and 
            user.last_name and
            hasattr(user, 'job_title') and user.job_title and
            hasattr(user, 'phone_number') and user.phone_number
        )
        
        return JsonResponse({
            'id': str(user.id),
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'auth_provider': user.auth_provider,
            'auth_provider_id': user.auth_provider_id,
            'is_active': user.is_active,
            'profile_completed': profile_completed,
            'created_at': user.created_at.isoformat(),
            'updated_at': user.updated_at.isoformat(),
        })

@method_decorator(csrf_exempt, name='dispatch')
class CompleteProfileView(View):
    """
    Complete user profile after Auth0 authentication
    """
    
    @auth0_required
    def post(self, request):
        try:
            data = json.loads(request.body)
            user = request.user
            
            # Update user basic info
            user.first_name = data.get('first_name', user.first_name)
            user.last_name = data.get('last_name', user.last_name)
            
            # Add profile fields (these would typically be in a separate UserProfile model)
            # For now, we'll add them as additional fields to the User model
            if hasattr(user, 'job_title'):
                user.job_title = data.get('job_title', '')
            if hasattr(user, 'phone_number'):
                user.phone_number = data.get('phone_number', '')
            if hasattr(user, 'business_model'):
                user.business_model = data.get('business_model', '')
            if hasattr(user, 'team_size'):
                user.team_size = data.get('team_size', '')
            if hasattr(user, 'about_yourself'):
                user.about_yourself = data.get('about_yourself', '')
            
            user.save()
            
            return JsonResponse({
                'id': str(user.id),
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'auth_provider': user.auth_provider,
                'auth_provider_id': user.auth_provider_id,
                'is_active': user.is_active,
                'profile_completed': True,
                'created_at': user.created_at.isoformat(),
                'updated_at': user.updated_at.isoformat(),
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

@swagger_auto_schema(
    method='get',
    operation_description="Health check endpoint to verify API status",
    responses={
        200: openapi.Response(
            description="API is healthy",
            examples={
                "application/json": {
                    "status": "ok",
                    "timestamp": "2024-01-01T12:00:00Z",
                    "version": "1.0.0"
                }
            }
        )
    },
    tags=['System']
)
@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    Health check endpoint to verify API status
    """
    from datetime import datetime
    return Response({
        'status': 'ok',
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'version': '1.0.0'
    })

@swagger_auto_schema(
    method='get',
    operation_description="Get API information and available endpoints",
    responses={
        200: openapi.Response(
            description="API information",
            examples={
                "application/json": {
                    "name": "Itqan CMS API",
                    "version": "1.0.0",
                    "description": "Content Management System API",
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
            }
        )
    },
    tags=['System']
)
@api_view(['GET'])
@permission_classes([AllowAny])
def api_info(request):
    """
    Get API information and available endpoints
    """
    return Response({
        'name': 'Itqan CMS API',
        'version': '1.0.0',
        'description': 'Content Management System API for Itqan platform',
        'endpoints': {
            'health': '/api/v1/health/',
            'auth': {
                'me': '/api/v1/auth/me/',
                'complete-profile': '/api/v1/auth/complete-profile/'
            },
            'docs': {
                'swagger': '/swagger/',
                'redoc': '/redoc/',
                'openapi': '/swagger.json'
            }
        }
    })

@method_decorator(csrf_exempt, name='dispatch')
class AuthCallbackView(View):
    """
    Handle Auth0 callback (if needed for server-side flows)
    """
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            token = data.get('access_token')
            
            if not token:
                return JsonResponse({'error': 'Missing access token'}, status=400)
            
            # Verify token and get user
            payload = verify_auth0_token(token)
            user = get_or_create_user_from_auth0(payload)
            
            # Check if profile is completed
            profile_completed = bool(
                user.first_name and 
                user.last_name and
                hasattr(user, 'job_title') and user.job_title and
                hasattr(user, 'phone_number') and user.phone_number
            )
            
            return JsonResponse({
                'user': {
                    'id': str(user.id),
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'profile_completed': profile_completed,
                },
                'requires_profile_completion': not profile_completed
            })
            
        except Auth0Error as e:
            return JsonResponse({'error': str(e)}, status=401)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': 'Authentication failed'}, status=500)


def generate_jwt_token(user):
    """Generate JWT token for user authentication"""
    payload = {
        'user_id': str(user.id),
        'email': user.email,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7),
        'iat': datetime.datetime.utcnow(),
    }
    
    # Use Django's SECRET_KEY for JWT signing
    secret_key = getattr(settings, 'SECRET_KEY', 'fallback-secret-key')
    return jwt.encode(payload, secret_key, algorithm='HS256')


@method_decorator(csrf_exempt, name='dispatch')
class RegisterView(View):
    """
    User registration with email and password
    """
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            
            # Extract and validate required fields
            email = data.get('email', '').strip().lower()
            password = data.get('password', '')
            first_name = data.get('firstName', '').strip()
            last_name = data.get('lastName', '').strip()
            job_title = data.get('jobTitle', '').strip()
            phone_number = data.get('phoneNumber', '').strip()
            
            # Validation
            if not email:
                return JsonResponse({'error': 'Email is required'}, status=400)
            
            if not password:
                return JsonResponse({'error': 'Password is required'}, status=400)
                
            if len(password) < 8:
                return JsonResponse({'error': 'Password must be at least 8 characters long'}, status=400)
            
            if not first_name:
                return JsonResponse({'error': 'First name is required'}, status=400)
                
            if not last_name:
                return JsonResponse({'error': 'Last name is required'}, status=400)
            
            # Validate email format
            try:
                validate_email(email)
            except ValidationError:
                return JsonResponse({'error': 'Invalid email format'}, status=400)
            
            # Check if user already exists
            if User.objects.filter(email=email).exists():
                return JsonResponse({'error': 'Email already exists'}, status=400)
            
            # Create user
            try:
                user = User.objects.create_user(
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    job_title=job_title,
                    phone_number=phone_number,
                    auth_provider='email',
                    is_active=True
                )
                
                # Generate JWT token
                token = generate_jwt_token(user)
                
                return JsonResponse({
                    'success': True,
                    'token': token,
                    'user': {
                        'id': str(user.id),
                        'email': user.email,
                        'firstName': user.first_name,
                        'lastName': user.last_name,
                        'jobTitle': user.job_title,
                        'phoneNumber': user.phone_number,
                        'provider': 'email',
                        'profileCompleted': True
                    }
                })
                
            except IntegrityError:
                return JsonResponse({'error': 'Email already exists'}, status=400)
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': f'Registration failed: {str(e)}'}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class LoginView(View):
    """
    User login with email and password
    """
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            
            email = data.get('email', '').strip().lower()
            password = data.get('password', '')
            
            if not email or not password:
                return JsonResponse({'error': 'Email and password are required'}, status=400)
            
            # Authenticate user
            user = authenticate(request, username=email, password=password)
            
            if user is None:
                return JsonResponse({'error': 'Invalid credentials'}, status=401)
            
            if not user.is_active:
                return JsonResponse({'error': 'Account is disabled'}, status=401)
            
            # Generate JWT token
            token = generate_jwt_token(user)
            
            # Check if profile is completed
            profile_completed = bool(
                user.first_name and 
                user.last_name and
                user.job_title and
                user.phone_number
            )
            
            return JsonResponse({
                'success': True,
                'token': token,
                'user': {
                    'id': str(user.id),
                    'email': user.email,
                    'firstName': user.first_name,
                    'lastName': user.last_name,
                    'jobTitle': user.job_title or '',
                    'phoneNumber': user.phone_number or '',
                    'provider': user.auth_provider,
                    'profileCompleted': profile_completed
                }
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': f'Login failed: {str(e)}'}, status=500)