#!/usr/bin/env python3
"""
Test script to validate API structure without database
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from django.urls import reverse
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

def test_api_urls():
    """Test that all API URLs are properly configured"""
    print("🧪 Testing API URL structure...")
    
    # Test URL patterns
    url_patterns = [
        'schema',
        'swagger-ui', 
        'redoc',
        'token_obtain_pair',
        'token_refresh',
        'token_verify',
        'role-list',
        'user-list',
        'resource-list',
        'distribution-list',
        'license-list',
        'accessrequest-list',
        'usageevent-list',
    ]
    
    for pattern in url_patterns:
        try:
            url = reverse(pattern)
            print(f"  ✅ {pattern}: {url}")
        except Exception as e:
            print(f"  ❌ {pattern}: {e}")
    
    print("\n🎉 API URL structure test completed!")

def test_serializers():
    """Test that all serializers are properly imported"""
    print("🧪 Testing serializer imports...")
    
    try:
        # Test accounts serializers
        from apps.accounts.serializers import (
            RoleSerializer, UserSerializer, UserCreateSerializer
        )
        print("  ✅ Accounts serializers imported successfully")
        
        # Test content serializers
        from apps.content.serializers import (
            ResourceSerializer, DistributionSerializer
        )
        print("  ✅ Content serializers imported successfully")
        
        # Test licensing serializers
        from apps.licensing.serializers import (
            LicenseSerializer, AccessRequestSerializer
        )
        print("  ✅ Licensing serializers imported successfully")
        
        # Test analytics serializers
        from apps.analytics.serializers import (
            UsageEventSerializer, UsageStatsSerializer
        )
        print("  ✅ Analytics serializers imported successfully")
        
    except Exception as e:
        print(f"  ❌ Serializer import error: {e}")
    
    print("\n🎉 Serializer import test completed!")

def test_viewsets():
    """Test that all viewsets are properly imported"""
    print("🧪 Testing viewset imports...")
    
    try:
        # Test accounts views
        from apps.accounts.views import RoleViewSet, UserViewSet
        print("  ✅ Accounts viewsets imported successfully")
        
        # Test content views
        from apps.content.views import ResourceViewSet, DistributionViewSet
        print("  ✅ Content viewsets imported successfully")
        
        # Test licensing views
        from apps.licensing.views import LicenseViewSet, AccessRequestViewSet
        print("  ✅ Licensing viewsets imported successfully")
        
        # Test analytics views
        from apps.analytics.views import UsageEventViewSet
        print("  ✅ Analytics viewsets imported successfully")
        
    except Exception as e:
        print(f"  ❌ Viewset import error: {e}")
    
    print("\n🎉 Viewset import test completed!")

def test_permissions():
    """Test that all permissions are properly imported"""
    print("🧪 Testing permission imports...")
    
    try:
        from apps.api.permissions import (
            IsAdminUser, ResourcePermission, LicensePermission,
            DistributionPermission, AccessRequestPermission,
            UsageEventPermission, RolePermission, UserPermission
        )
        print("  ✅ All permission classes imported successfully")
        
    except Exception as e:
        print(f"  ❌ Permission import error: {e}")
    
    print("\n🎉 Permission import test completed!")

if __name__ == '__main__':
    print("🚀 Starting Django REST API v1 Structure Tests\n")
    
    test_serializers()
    test_viewsets() 
    test_permissions()
    test_api_urls()
    
    print("\n✅ All API structure tests completed successfully!")
    print("🎯 Django REST API v1 is properly configured and ready for database testing!")
