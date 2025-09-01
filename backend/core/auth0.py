"""
Auth0 JWT Authentication for Django
"""

import json
import requests
from functools import wraps
from django.http import JsonResponse
from django.contrib.auth import get_user_model
from django.conf import settings
from jose import jwt as jose_jwt
from jose.exceptions import JWTError, ExpiredSignatureError, JWTClaimsError

User = get_user_model()

# Auth0 Configuration
AUTH0_DOMAIN = getattr(settings, 'AUTH0_DOMAIN', 'dev-itqan.eu.auth0.com')
AUTH0_AUDIENCE = getattr(settings, 'AUTH0_AUDIENCE', None)
AUTH0_CLIENT_ID = getattr(settings, 'AUTH0_CLIENT_ID', 'N3S0JhhYSWaLuhVMuBb9ZTX4gEPJ0G8f')
AUTH0_CLIENT_SECRET = getattr(settings, 'AUTH0_CLIENT_SECRET', 'AjwysVUiFkVbZ1SEjFBbAcNMIPEEQSimbMKx_aMraEW5SiKGZgu_7Smoei8T8kUk')

class Auth0Error(Exception):
    """Custom exception for Auth0 authentication errors"""
    pass

def get_auth0_public_key():
    """Fetch Auth0 public key for JWT verification"""
    try:
        jwks_url = f"https://{AUTH0_DOMAIN}/.well-known/jwks.json"
        response = requests.get(jwks_url)
        response.raise_for_status()
        jwks = response.json()
        return jwks
    except requests.RequestException as e:
        raise Auth0Error(f"Failed to fetch Auth0 public key: {str(e)}")

def get_user_info_from_auth0(access_token):
    """
    Get user information from Auth0 using access token
    """
    try:
        userinfo_url = f"https://{AUTH0_DOMAIN}/userinfo"
        headers = {'Authorization': f'Bearer {access_token}'}
        response = requests.get(userinfo_url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise Auth0Error(f"Failed to get user info from Auth0: {str(e)}")

def verify_auth0_token(token):
    """
    Verify Auth0 JWT token and return user info
    """
    try:
        # Get the public key
        jwks = get_auth0_public_key()
        
        # Get the header to find the key ID
        unverified_header = jose_jwt.get_unverified_header(token)
        
        # Find the correct key
        rsa_key = {}
        for key in jwks["keys"]:
            if key["kid"] == unverified_header["kid"]:
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"]
                }
                break
        
        if not rsa_key:
            raise Auth0Error("Unable to find appropriate key")
        
        # Verify the token
        payload = jose_jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            audience=AUTH0_AUDIENCE,
            issuer=f"https://{AUTH0_DOMAIN}/"
        )
        
        return payload
        
    except ExpiredSignatureError:
        raise Auth0Error("Token has expired")
    except JWTClaimsError:
        raise Auth0Error("Invalid token claims")
    except JWTError as e:
        raise Auth0Error(f"Invalid token: {str(e)}")
    except Exception as e:
        raise Auth0Error(f"Token verification failed: {str(e)}")

def get_or_create_user_from_auth0(auth0_payload, access_token=None, fallback_email=None, fallback_sub=None):
    """
    Get or create a user based on Auth0 payload
    """
    auth0_id = auth0_payload.get('sub')
    email = auth0_payload.get('email')
    
    # If missing user info and we have an access token, try to get user info from Auth0
    if (not auth0_id or not email) and access_token:
        try:
            user_info = get_user_info_from_auth0(access_token)
            auth0_id = auth0_id or user_info.get('sub')
            email = email or user_info.get('email')
        except Exception as e:
            print(f"Failed to get user info from Auth0: {e}")

    # Final fallback to values provided in the request body (if present)
    if not auth0_id and fallback_sub:
        auth0_id = fallback_sub
    if not email and fallback_email:
        email = fallback_email
    
    if not auth0_id or not email:
        raise Auth0Error("Missing required user information in token")
    
    try:
        # Try to find existing user by auth0_id
        user = User.objects.get(auth_provider_id=auth0_id)
        return user
    except User.DoesNotExist:
        # Try to find by email
        try:
            user = User.objects.get(email=email)
            # Update with Auth0 info if not already set
            if not user.auth_provider_id:
                user.auth_provider = 'auth0'
                user.auth_provider_id = auth0_id
                user.save()
            return user
        except User.DoesNotExist:
            # Create new user
            user = User.objects.create(
                email=email,
                first_name=auth0_payload.get('given_name', ''),
                last_name=auth0_payload.get('family_name', ''),
                auth_provider='auth0',
                auth_provider_id=auth0_id,
                is_active=True
            )
            return user

def auth0_required(view_func):
    """
    Decorator to require Auth0 authentication for a view
    """
    @wraps(view_func)
    def wrapper(self, request, *args, **kwargs):
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        
        if not auth_header:
            return JsonResponse({'error': 'Authorization header required'}, status=401)
        
        try:
            # Extract token from "Bearer <token>"
            token = auth_header.split(' ')[1] if auth_header.startswith('Bearer ') else None
            if not token:
                return JsonResponse({'error': 'Invalid authorization header format'}, status=401)
            
            # Verify token
            payload = verify_auth0_token(token)
            
            # Try to extract email/sub from request body as a fallback
            fallback_email = None
            fallback_sub = None
            try:
                if request.body:
                    body_data = json.loads(request.body)
                    fallback_email = body_data.get('email')
                    fallback_sub = body_data.get('auth0_id')
            except Exception:
                pass

            # Get or create user
            user = get_or_create_user_from_auth0(payload, token, fallback_email, fallback_sub)
            
            # Add user to request
            request.user = user
            request.auth0_payload = payload
            
            return view_func(self, request, *args, **kwargs)
            
        except Auth0Error as e:
            return JsonResponse({'error': str(e)}, status=401)
        except Exception as e:
            return JsonResponse({'error': 'Authentication failed'}, status=401)
    
    return wrapper

class Auth0Middleware:
    """
    Middleware to handle Auth0 authentication for API requests
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Skip authentication for certain paths
        skip_paths = [
            '/admin/',
            '/api/v1/health',
            '/api/v1/licenses',
            '/api/v1/publishers',
            '/api/v1/resources',
            '/api/v1/assets',
        ]
        
        # Check if this is an API request that needs authentication
        if request.path.startswith('/api/v1/') and not any(request.path.startswith(path) for path in skip_paths):
            auth_header = request.META.get('HTTP_AUTHORIZATION')
            
            if auth_header and auth_header.startswith('Bearer '):
                try:
                    token = auth_header.split(' ')[1]
                    payload = verify_auth0_token(token)
                    user = get_or_create_user_from_auth0(payload, token)
                    
                    request.user = user
                    request.auth0_payload = payload
                    
                except Auth0Error:
                    # Let the view handle the authentication error
                    pass
                except Exception:
                    # Let the view handle the authentication error
                    pass
        
        response = self.get_response(request)
        return response
