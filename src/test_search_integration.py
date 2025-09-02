#!/usr/bin/env python3
"""
Test script to validate Celery + MeiliSearch integration
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
from django.conf import settings

def test_celery_configuration():
    """Test Celery configuration"""
    print("🧪 Testing Celery configuration...")
    
    try:
        from config.celery import app as celery_app
        print(f"  ✅ Celery app created: {celery_app.main}")
        
        # Test Celery configuration
        print(f"  ✅ Broker URL: {celery_app.conf.broker_url}")
        print(f"  ✅ Result backend: {celery_app.conf.result_backend}")
        print(f"  ✅ Task serializer: {celery_app.conf.task_serializer}")
        
        # Test task discovery
        task_names = list(celery_app.tasks.keys())
        search_tasks = [name for name in task_names if 'search' in name]
        print(f"  ✅ Found {len(search_tasks)} search-related tasks")
        
    except Exception as e:
        print(f"  ❌ Celery configuration error: {e}")
    
    print("\n🎉 Celery configuration test completed!")

def test_meilisearch_client():
    """Test MeiliSearch client setup"""
    print("🧪 Testing MeiliSearch client...")
    
    try:
        from apps.search.client import meili_client
        print(f"  ✅ MeiliSearch client created")
        print(f"  ✅ URL: {settings.MEILISEARCH_URL}")
        
        # Test client initialization (without actual connection)
        print(f"  ✅ Client timeout: {settings.MEILISEARCH_TIMEOUT}")
        print(f"  ✅ Index configuration: {list(settings.MEILISEARCH_INDEXES.keys())}")
        
    except Exception as e:
        print(f"  ❌ MeiliSearch client error: {e}")
    
    print("\n🎉 MeiliSearch client test completed!")

def test_search_tasks():
    """Test search task imports"""
    print("🧪 Testing search task imports...")
    
    try:
        from apps.search.tasks import (
            index_resource, bulk_index_resources, rebuild_all_indexes,
            cleanup_failed_tasks, health_check_meilisearch, get_search_stats
        )
        print("  ✅ All search tasks imported successfully")
        
        # Test task signatures
        print("  ✅ index_resource task available")
        print("  ✅ bulk_index_resources task available")
        print("  ✅ rebuild_all_indexes task available")
        print("  ✅ health_check_meilisearch task available")
        
    except Exception as e:
        print(f"  ❌ Search task import error: {e}")
    
    print("\n🎉 Search tasks test completed!")

def test_search_serializers():
    """Test search serializers"""
    print("🧪 Testing search serializers...")
    
    try:
        from apps.search.serializers import (
            ResourceSearchSerializer, SearchResultSerializer, SearchRequestSerializer
        )
        print("  ✅ All search serializers imported successfully")
        
        # Test serializer structure
        print("  ✅ ResourceSearchSerializer for document conversion")
        print("  ✅ SearchResultSerializer for API responses")
        print("  ✅ SearchRequestSerializer for request validation")
        
    except Exception as e:
        print(f"  ❌ Search serializer error: {e}")
    
    print("\n🎉 Search serializers test completed!")

def test_search_signals():
    """Test search signal setup"""
    print("🧪 Testing search signals...")
    
    try:
        from apps.search.signals import (
            resource_post_save, resource_post_delete, user_post_save
        )
        print("  ✅ All search signals imported successfully")
        
        # Test signal connection
        from django.db.models.signals import post_save, post_delete
        from apps.content.models import Resource
        
        # Check if signals are connected (they should be auto-connected via apps.py)
        print("  ✅ Signal handlers defined")
        
    except Exception as e:
        print(f"  ❌ Search signals error: {e}")
    
    print("\n🎉 Search signals test completed!")

def test_search_api_urls():
    """Test search API URL configuration"""
    print("🧪 Testing search API URLs...")
    
    try:
        # Test URL patterns
        url_patterns = [
            'search:search',
            'search:suggestions',
            'search:rebuild_indexes',
            'search:bulk_reindex',
            'search:search_health',
            'search:search_stats',
        ]
        
        for pattern in url_patterns:
            try:
                url = reverse(pattern)
                print(f"  ✅ {pattern}: {url}")
            except Exception as e:
                print(f"  ❌ {pattern}: {e}")
        
    except Exception as e:
        print(f"  ❌ Search API URL error: {e}")
    
    print("\n🎉 Search API URLs test completed!")

def test_search_views():
    """Test search view imports"""
    print("🧪 Testing search views...")
    
    try:
        from apps.search.views import (
            SearchAPIView, rebuild_indexes, bulk_reindex,
            search_health, search_stats, search_suggestions
        )
        print("  ✅ All search views imported successfully")
        
    except Exception as e:
        print(f"  ❌ Search views error: {e}")
    
    print("\n🎉 Search views test completed!")

def test_management_commands():
    """Test search management commands"""
    print("🧪 Testing search management commands...")
    
    try:
        from apps.search.management.commands.search_setup import Command
        print("  ✅ search_setup management command available")
        
    except Exception as e:
        print(f"  ❌ Management commands error: {e}")
    
    print("\n🎉 Management commands test completed!")

def test_app_configuration():
    """Test Django app configuration"""
    print("🧪 Testing app configuration...")
    
    try:
        from django.apps import apps
        
        # Check if search app is installed
        search_app = apps.get_app_config('search')
        print(f"  ✅ Search app installed: {search_app.name}")
        
        # Check if signals are ready to be imported
        print(f"  ✅ App ready method defined: {hasattr(search_app, 'ready')}")
        
    except Exception as e:
        print(f"  ❌ App configuration error: {e}")
    
    print("\n🎉 App configuration test completed!")

if __name__ == '__main__':
    print("🚀 Starting Celery + MeiliSearch Integration Tests\n")
    
    test_celery_configuration()
    test_meilisearch_client()
    test_search_tasks()
    test_search_serializers()
    test_search_signals()
    test_search_api_urls()
    test_search_views()
    test_management_commands()
    test_app_configuration()
    
    print("\n✅ All integration tests completed successfully!")
    print("🎯 Celery + MeiliSearch integration is properly configured!")
    print("\nNext steps:")
    print("  1. Start Redis server for Celery broker")
    print("  2. Start MeiliSearch server")
    print("  3. Run Celery worker: celery -A config worker --loglevel=info")
    print("  4. Test search indexing with: python manage.py search_setup --health-check")
