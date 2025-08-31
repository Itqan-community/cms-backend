"""
Core API views for authentication and user management
"""

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth import get_user_model
from django.utils.decorators import method_decorator
from django.views import View
import json
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

@require_http_methods(["GET"])
def health_check(request):
    """
    Health check endpoint
    """
    return JsonResponse({'status': 'ok'})

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