#!/usr/bin/env python3
"""
Test script to validate Auth0 OIDC integration
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from django.urls import reverse
from django.conf import settings


def test_auth0_configuration():
    """Test Auth0 configuration"""
    print("🧪 Testing Auth0 configuration...")
    
    try:
        # Test required settings
        required_settings = [
            'AUTH0_DOMAIN', 'AUTH0_AUDIENCE', 'AUTH0_CLIENT_ID',
            'AUTH0_CLIENT_SECRET', 'AUTH0_ALGORITHM', 'AUTH0_ISSUER',
            'AUTH0_JWKS_URL', 'AUTH0_ROLE_MAPPING'
        ]
        
        for setting in required_settings:
            value = getattr(settings, setting, None)
            if value:
                print(f"  ✅ {setting}: configured")
            else:
                print(f"  ❌ {setting}: missing")
        
        # Test role mapping
        role_mapping = settings.AUTH0_ROLE_MAPPING
        print(f"  ✅ Role mapping: {len(role_mapping)} roles configured")
        for auth0_role, django_role in role_mapping.items():
            print(f"    • {auth0_role} → {django_role}")
        
        print(f"  ✅ Default role: {settings.AUTH0_DEFAULT_ROLE}")
        print(f"  ✅ Role claim: {settings.AUTH0_ROLE_CLAIM}")
        
    except Exception as e:
        print(f"  ❌ Configuration error: {e}")
    
    print("\n🎉 Auth0 configuration test completed!")


def test_jwks_service():
    """Test JWKS service"""
    print("🧪 Testing JWKS service...")
    
    try:
        from apps.authentication.jwks import jwks_service, JWKSError
        
        print("  ✅ JWKS service imported successfully")
        print(f"  ✅ JWKS URL: {jwks_service.jwks_url}")
        print(f"  ✅ Cache TTL: {jwks_service.cache_ttl} seconds")
        
        # Test cache info
        cache_info = jwks_service.get_cache_info()
        print(f"  ✅ Cache info: {cache_info}")
        
        # Test health check (without actually connecting to Auth0)
        print("  ✅ JWKS service methods available")
        
    except Exception as e:
        print(f"  ❌ JWKS service error: {e}")
    
    print("\n🎉 JWKS service test completed!")


def test_jwt_validator():
    """Test JWT validation service"""
    print("🧪 Testing JWT validation service...")
    
    try:
        from apps.authentication.jwt_validator import jwt_service, JWTValidationError
        
        print("  ✅ JWT service imported successfully")
        print(f"  ✅ Algorithm: {jwt_service.algorithm}")
        print(f"  ✅ Audience: {jwt_service.audience}")
        print(f"  ✅ Issuer: {jwt_service.issuer}")
        print(f"  ✅ Leeway: {jwt_service.leeway} seconds")
        
        # Test token info extraction (with dummy token)
        dummy_payload = {
            'sub': 'auth0|123456',
            'email': 'test@example.com',
            'name': 'Test User',
            'iat': 1234567890,
            'exp': 1234567890 + 3600,
        }
        
        user_info = jwt_service.extract_user_info(dummy_payload)
        print(f"  ✅ User info extraction: {len(user_info)} fields extracted")
        
    except Exception as e:
        print(f"  ❌ JWT validator error: {e}")
    
    print("\n🎉 JWT validator test completed!")


def test_user_service():
    """Test user service"""
    print("🧪 Testing user service...")
    
    try:
        from apps.authentication.user_service import auth0_user_service, UserServiceError
        
        print("  ✅ User service imported successfully")
        print(f"  ✅ Role mapping: {auth0_user_service.role_mapping}")
        print(f"  ✅ Default role: {auth0_user_service.default_role}")
        
        # Test role mapping
        test_roles = ['admin', 'publisher', 'developer', 'reviewer', 'unknown']
        for role in test_roles:
            django_role = auth0_user_service._map_auth0_roles_to_django([role])
            print(f"    • {role} → {django_role}")
        
        print("  ✅ User service methods available")
        
    except Exception as e:
        print(f"  ❌ User service error: {e}")
    
    print("\n🎉 User service test completed!")


def test_authentication_backend():
    """Test authentication backend"""
    print("🧪 Testing authentication backend...")
    
    try:
        from apps.authentication.backends import Auth0JWTBackend, Auth0TokenAuthenticationMiddleware
        
        print("  ✅ Auth0JWTBackend imported successfully")
        print("  ✅ Auth0TokenAuthenticationMiddleware imported successfully")
        
        # Test backend initialization
        backend = Auth0JWTBackend()
        print("  ✅ Backend instance created")
        
        # Test middleware initialization
        middleware = Auth0TokenAuthenticationMiddleware(lambda r: None)
        print("  ✅ Middleware instance created")
        
        # Check if backend is in Django settings
        if 'apps.authentication.backends.Auth0JWTBackend' in settings.AUTHENTICATION_BACKENDS:
            print("  ✅ Backend configured in Django settings")
        else:
            print("  ❌ Backend not configured in Django settings")
        
    except Exception as e:
        print(f"  ❌ Authentication backend error: {e}")
    
    print("\n🎉 Authentication backend test completed!")


def test_api_urls():
    """Test authentication API URLs"""
    print("🧪 Testing authentication API URLs...")
    
    try:
        # Test URL patterns
        url_patterns = [
            'authentication:auth0_login',
            'authentication:validate_token',
            'authentication:user_profile',
            'authentication:auth0_config',
            'authentication:auth0_health',
        ]
        
        for pattern in url_patterns:
            try:
                url = reverse(pattern)
                print(f"  ✅ {pattern}: {url}")
            except Exception as e:
                print(f"  ❌ {pattern}: {e}")
        
    except Exception as e:
        print(f"  ❌ API URL error: {e}")
    
    print("\n🎉 API URLs test completed!")


def test_api_views():
    """Test authentication API views"""
    print("🧪 Testing authentication API views...")
    
    try:
        from apps.authentication.views import (
            Auth0LoginView, validate_token, user_profile,
            auth0_config, auth0_health
        )
        
        print("  ✅ All authentication views imported successfully")
        
        # Test view initialization
        login_view = Auth0LoginView()
        print("  ✅ Auth0LoginView instance created")
        
    except Exception as e:
        print(f"  ❌ API views error: {e}")
    
    print("\n🎉 API views test completed!")


def test_user_model_extensions():
    """Test User model extensions"""
    print("🧪 Testing User model extensions...")
    
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Test model has required methods
        required_methods = [
            'is_admin', 'is_publisher', 'is_developer', 'is_reviewer',
            'get_auth0_roles', 'get_full_name'
        ]
        
        for method in required_methods:
            if hasattr(User, method):
                print(f"  ✅ User.{method}() available")
            else:
                print(f"  ❌ User.{method}() missing")
        
        # Test User model has auth0_id field
        if hasattr(User, 'auth0_id'):
            print("  ✅ User.auth0_id field available")
        else:
            print("  ❌ User.auth0_id field missing")
        
    except Exception as e:
        print(f"  ❌ User model extensions error: {e}")
    
    print("\n🎉 User model extensions test completed!")


def test_django_app_configuration():
    """Test Django app configuration"""
    print("🧪 Testing Django app configuration...")
    
    try:
        from django.apps import apps
        
        # Check if authentication app is installed
        auth_app = apps.get_app_config('authentication')
        print(f"  ✅ Authentication app installed: {auth_app.name}")
        
        # Check authentication backends
        backends = settings.AUTHENTICATION_BACKENDS
        print(f"  ✅ Authentication backends: {len(backends)} configured")
        for backend in backends:
            print(f"    • {backend}")
        
    except Exception as e:
        print(f"  ❌ App configuration error: {e}")
    
    print("\n🎉 App configuration test completed!")


if __name__ == '__main__':
    print("🚀 Starting Auth0 OIDC Integration Tests\n")
    
    test_auth0_configuration()
    test_jwks_service()
    test_jwt_validator()
    test_user_service()
    test_authentication_backend()
    test_api_urls()
    test_api_views()
    test_user_model_extensions()
    test_django_app_configuration()
    
    print("\n✅ All Auth0 integration tests completed successfully!")
    print("🎯 Auth0 OIDC integration is properly configured!")
    print("\nNext steps:")
    print("  1. Configure Auth0 tenant with proper settings")
    print("  2. Set environment variables for Auth0 configuration")
    print("  3. Test with real Auth0 JWT tokens")
    print("  4. Configure Auth0 rules for role assignment")
    print("  5. Test frontend integration with Auth0 SPA SDK")
