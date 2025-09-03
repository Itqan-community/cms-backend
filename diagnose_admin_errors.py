#!/usr/bin/env python3
"""
Detailed diagnostic script to identify admin login issues
"""
import requests
import sys
from bs4 import BeautifulSoup

def get_detailed_error(url, login_data):
    """Get detailed error information from login attempt"""
    session = requests.Session()
    
    try:
        # Get login page first
        print(f"📡 Fetching login page: {url}")
        response = session.get(url)
        
        if response.status_code != 200:
            print(f"❌ Login page error: HTTP {response.status_code}")
            return None
            
        # Extract CSRF token
        soup = BeautifulSoup(response.content, 'html.parser')
        csrf_token = soup.find('input', {'name': 'csrfmiddlewaretoken'})
        
        if not csrf_token:
            print("❌ No CSRF token found")
            return None
            
        csrf_value = csrf_token.get('value')
        login_data['csrfmiddlewaretoken'] = csrf_value
        
        print(f"🔐 Attempting login...")
        # Attempt login with verbose error handling
        login_response = session.post(url, data=login_data, allow_redirects=False)
        
        print(f"📊 Response Status: {login_response.status_code}")
        print(f"📊 Response Headers: {dict(login_response.headers)}")
        
        if login_response.status_code == 500:
            print("🔍 Server Error Details:")
            # Try to extract error information
            error_content = login_response.text
            if 'OperationalError' in error_content:
                print("   → Database connection error detected")
            elif 'ImportError' in error_content:
                print("   → Missing module/import error detected")
            elif 'AttributeError' in error_content:
                print("   → Attribute/configuration error detected")
            elif 'User matching query does not exist' in error_content:
                print("   → User does not exist in database")
            else:
                print("   → Unknown server error")
                # Show first 500 characters of error
                print(f"   → Error snippet: {error_content[:500]}...")
                
        return login_response
        
    except Exception as e:
        print(f"❌ Exception during request: {e}")
        return None

def test_database_connection():
    """Test basic database connectivity via API"""
    print("\n🔍 Testing Database Connection via API...")
    
    try:
        # Try a simple API endpoint that requires database
        response = requests.get("https://develop.api.cms.itqan.dev/mock-api/auth/test-users")
        
        if response.status_code == 200:
            print("✅ Database connection appears to be working (API responds)")
            data = response.json()
            print(f"   → Found {len(data.get('users', []))} test users")
        else:
            print(f"❌ API test failed: HTTP {response.status_code}")
            
    except Exception as e:
        print(f"❌ Database test error: {e}")

def test_static_files():
    """Test if static files are accessible"""
    print("\n🔍 Testing Static Files...")
    
    static_urls = [
        "https://develop.api.cms.itqan.dev/static/admin/css/base.css",
        "https://develop.api.cms.itqan.dev/static/wagtailadmin/css/core.css"
    ]
    
    for url in static_urls:
        try:
            response = requests.head(url)
            if response.status_code == 200:
                print(f"✅ Static file accessible: {url.split('/')[-1]}")
            else:
                print(f"❌ Static file error: {url.split('/')[-1]} (HTTP {response.status_code})")
        except Exception as e:
            print(f"❌ Static file test error for {url}: {e}")

def test_csrf_protection():
    """Test CSRF protection is working"""
    print("\n🔍 Testing CSRF Protection...")
    
    try:
        # Try login without CSRF token
        session = requests.Session()
        login_url = "https://develop.api.cms.itqan.dev/django-admin/login/"
        
        bad_data = {
            'username': 'test',
            'password': 'test',
            'next': '/django-admin/'
        }
        
        response = session.post(login_url, data=bad_data, allow_redirects=False)
        
        if response.status_code == 403:
            print("✅ CSRF protection is working (403 without token)")
        elif response.status_code == 500:
            print("❌ CSRF causes 500 error (configuration issue)")
        else:
            print(f"⚠️  Unexpected CSRF behavior: HTTP {response.status_code}")
            
    except Exception as e:
        print(f"❌ CSRF test error: {e}")

if __name__ == "__main__":
    print("🔧 Admin Error Diagnostic Tool")
    print("=" * 60)
    
    # Test database connection
    test_database_connection()
    
    # Test static files
    test_static_files()
    
    # Test CSRF protection
    test_csrf_protection()
    
    print("\n🔍 Testing Django Admin Login Error...")
    django_login_url = "https://develop.api.cms.itqan.dev/django-admin/login/"
    django_data = {
        'username': 'admin@itqan.dev',
        'password': 'ItqanCMS2024!',
        'next': '/django-admin/'
    }
    
    django_response = get_detailed_error(django_login_url, django_data)
    
    print("\n🔍 Testing Wagtail CMS Login Error...")
    wagtail_login_url = "https://develop.api.cms.itqan.dev/cms/login/"
    wagtail_data = {
        'username': 'admin@itqan.dev',
        'password': 'ItqanCMS2024!',
        'next': '/cms/'
    }
    
    wagtail_response = get_detailed_error(wagtail_login_url, wagtail_data)
    
    print("\n📋 Diagnostic Summary")
    print("=" * 60)
    
    if django_response and wagtail_response:
        if django_response.status_code == 500 and wagtail_response.status_code == 500:
            print("🔴 Both admin interfaces have server errors")
            print("💡 Likely causes:")
            print("   - Database connection issues")
            print("   - Missing/corrupted admin user")
            print("   - Authentication backend misconfiguration")
            print("   - Missing environment variables")
            print("   - Static files collection issues")
        else:
            print("🟡 Mixed results - investigate individual errors")
    else:
        print("🔴 Could not complete diagnostic tests")
    
    print("\n🔧 Recommended Next Steps:")
    print("1. Check server logs for detailed error traces")
    print("2. Verify admin user exists in database")
    print("3. Check Django settings configuration")
    print("4. Verify database connectivity")
    print("5. Check static files collection")
