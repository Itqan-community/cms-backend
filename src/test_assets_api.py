#!/usr/bin/env python3
"""
Test script to verify the new /assets/ API endpoints
This script documents the expected behavior and can be run to test the implementation

Usage:
    python src/test_assets_api.py
"""

import os
import sys
import django
import json
from django.test import Client
from django.contrib.auth import get_user_model

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')
django.setup()

User = get_user_model()

def test_assets_api():
    """Test the assets API endpoints"""
    client = Client()
    
    print("🧪 Testing Asset API Endpoints")
    print("=" * 50)
    
    # Test 1: List Assets (GET /api/v1/assets/)
    print("\n1️⃣ Testing GET /api/v1/assets/")
    try:
        response = client.get('/api/v1/assets/')
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Response keys: {list(data.keys())}")
            if 'assets' in data:
                print(f"   Assets count: {len(data['assets'])}")
                if data['assets']:
                    asset = data['assets'][0]
                    print(f"   First asset fields: {list(asset.keys())}")
        else:
            print(f"   Error: {response.content.decode()}")
    except Exception as e:
        print(f"   Exception: {e}")
    
    # Test 2: List Assets with category filter
    print("\n2️⃣ Testing GET /api/v1/assets/?category=mushaf")
    try:
        response = client.get('/api/v1/assets/?category=mushaf')
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Filtered assets count: {len(data.get('assets', []))}")
    except Exception as e:
        print(f"   Exception: {e}")
    
    # Test 3: Asset Detail (need to get an asset ID first)
    print("\n3️⃣ Testing GET /api/v1/assets/{asset_id}/")
    try:
        # First get asset list to get an ID
        response = client.get('/api/v1/assets/')
        if response.status_code == 200:
            data = response.json()
            if data.get('assets'):
                asset_id = data['assets'][0]['id']
                detail_response = client.get(f'/api/v1/assets/{asset_id}/')
                print(f"   Status: {detail_response.status_code}")
                if detail_response.status_code == 200:
                    detail_data = detail_response.json()
                    print(f"   Detail fields: {list(detail_data.keys())}")
                    # Check required fields from OpenAPI spec
                    required_fields = ['id', 'title', 'description', 'category', 'license', 'publisher', 'technical_details', 'stats', 'access']
                    missing_fields = [f for f in required_fields if f not in detail_data]
                    if missing_fields:
                        print(f"   ⚠️  Missing required fields: {missing_fields}")
                    else:
                        print("   ✅ All required fields present")
                else:
                    print(f"   Error: {detail_response.content.decode()}")
            else:
                print("   No assets available for testing detail view")
        else:
            print("   Cannot test detail view - asset list failed")
    except Exception as e:
        print(f"   Exception: {e}")
    
    # Test 4: Request Access (requires authentication)
    print("\n4️⃣ Testing POST /api/v1/assets/{asset_id}/request-access/ (unauthenticated)")
    try:
        # First get an asset ID
        response = client.get('/api/v1/assets/')
        if response.status_code == 200:
            data = response.json()
            if data.get('assets'):
                asset_id = data['assets'][0]['id']
                access_response = client.post(f'/api/v1/assets/{asset_id}/request-access/', 
                    data=json.dumps({
                        'purpose': 'Academic research',
                        'intended_use': 'non-commercial'
                    }),
                    content_type='application/json'
                )
                print(f"   Status: {access_response.status_code}")
                if access_response.status_code == 401:
                    print("   ✅ Correctly requires authentication")
                else:
                    print(f"   Response: {access_response.content.decode()}")
    except Exception as e:
        print(f"   Exception: {e}")
    
    # Test 5: Download Asset (requires authentication)
    print("\n5️⃣ Testing GET /api/v1/assets/{asset_id}/download/ (unauthenticated)")
    try:
        # First get an asset ID
        response = client.get('/api/v1/assets/')
        if response.status_code == 200:
            data = response.json()
            if data.get('assets'):
                asset_id = data['assets'][0]['id']
                download_response = client.get(f'/api/v1/assets/{asset_id}/download/')
                print(f"   Status: {download_response.status_code}")
                if download_response.status_code == 401:
                    print("   ✅ Correctly requires authentication")
                else:
                    print(f"   Response: {download_response.content.decode()}")
    except Exception as e:
        print(f"   Exception: {e}")
    
    print("\n" + "=" * 50)
    print("✅ Asset API endpoint testing completed!")
    print("\nExpected endpoints:")
    print("  GET    /api/v1/assets/                     - List assets (public)")
    print("  GET    /api/v1/assets/{asset_id}/          - Asset details (public)")
    print("  POST   /api/v1/assets/{asset_id}/request-access/  - Request access (auth required)")
    print("  GET    /api/v1/assets/{asset_id}/download/ - Download asset (auth required)")


if __name__ == '__main__':
    test_assets_api()
