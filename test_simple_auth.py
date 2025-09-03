#!/usr/bin/env python3
"""
Simple test to check basic authentication differences
"""
import requests
from bs4 import BeautifulSoup

def test_with_valid_login():
    """Test with a user we know exists and works"""
    print("🔍 Testing Authentication with Different Approaches...")
    
    base_url = "https://develop.api.cms.itqan.dev"
    
    # First, verify our admin user works via API
    print("\n1. Testing API Authentication (known working):")
    try:
        api_login = requests.post(f"{base_url}/api/v1/auth/login/", json={
            "email": "admin@itqan.dev",
            "password": "ItqanCMS2024!"
        })
        print(f"   → API Login: HTTP {api_login.status_code} {'✅' if api_login.status_code == 200 else '❌'}")
    except Exception as e:
        print(f"   → API Login Error: {e}")
    
    # Test with mock user that we know exists
    print("\n2. Testing with Mock User (if admin fails):")
    try:
        # Get a mock user that might work
        mock_users = requests.get(f"{base_url}/mock-api/auth/test-users")
        if mock_users.status_code == 200:
            users_data = mock_users.json()
            test_user = None
            
            # Find a test user
            for user in users_data.get('users', []):
                if user.get('email') == 'test@example.com':
                    test_user = user
                    break
            
            if test_user:
                print(f"   → Found test user: {test_user['email']}")
                
                # Try Django admin with test user
                session = requests.Session()
                login_page = session.get(f"{base_url}/django-admin/login/")
                
                if login_page.status_code == 200:
                    soup = BeautifulSoup(login_page.content, 'html.parser')
                    csrf_token = soup.find('input', {'name': 'csrfmiddlewaretoken'})
                    
                    if csrf_token:
                        login_data = {
                            'username': 'test@example.com',
                            'password': 'test',  # From mock data
                            'csrfmiddlewaretoken': csrf_token.get('value'),
                            'next': '/django-admin/'
                        }
                        
                        test_login = session.post(f"{base_url}/django-admin/login/", data=login_data)
                        print(f"   → Test User Django Admin: HTTP {test_login.status_code}")
                        
                        if test_login.status_code == 500:
                            print("   → Same 500 error - system-wide authentication issue")
                        elif test_login.status_code == 302:
                            redirect_url = test_login.headers.get('location', '')
                            if 'login' in redirect_url:
                                print("   → Test user authentication rejected (expected)")
                            else:
                                print("   → Test user authentication successful!")
                        else:
                            print(f"   → Unexpected response: {test_login.status_code}")
            else:
                print("   → No suitable test user found")
    except Exception as e:
        print(f"   → Mock user test error: {e}")

def test_authentication_backends():
    """Test if authentication backends are working"""
    print("\n3. Testing Authentication Backend Issues:")
    
    base_url = "https://develop.api.cms.itqan.dev"
    
    # Test with intentionally wrong credentials
    session = requests.Session()
    
    try:
        login_page = session.get(f"{base_url}/django-admin/login/")
        if login_page.status_code == 200:
            soup = BeautifulSoup(login_page.content, 'html.parser')
            csrf_token = soup.find('input', {'name': 'csrfmiddlewaretoken'})
            
            if csrf_token:
                # Test with wrong password
                bad_login_data = {
                    'username': 'admin@itqan.dev',
                    'password': 'wrong_password',
                    'csrfmiddlewaretoken': csrf_token.get('value'),
                    'next': '/django-admin/'
                }
                
                bad_login = session.post(f"{base_url}/django-admin/login/", data=bad_login_data)
                print(f"   → Wrong Password Test: HTTP {bad_login.status_code}")
                
                if bad_login.status_code == 500:
                    print("   → 500 error even with wrong password - authentication backend issue")
                elif bad_login.status_code == 200:
                    if 'Please enter a correct' in bad_login.text:
                        print("   → Authentication backend working (proper error message)")
                    else:
                        print("   → Unexpected response to wrong password")
                else:
                    print(f"   → Unexpected response to wrong password: {bad_login.status_code}")
    except Exception as e:
        print(f"   → Authentication backend test error: {e}")

def check_user_model_issue():
    """Check if there's still a user model issue"""
    print("\n4. Checking for Remaining User Model Issues:")
    
    print("   → Django setting AUTH_USER_MODEL should be 'accounts.User'")
    print("   → We removed duplicate User model from core.models")
    print("   → User was promoted to staff/superuser status")
    
    # The issue might be:
    print("\n   🤔 Possible remaining issues:")
    print("   → User model manager issue (create_user vs create_superuser)")
    print("   → Missing required fields (role field is required but might be NULL)")
    print("   → Authentication backend configuration")
    print("   → Database migration inconsistency")

if __name__ == "__main__":
    print("🔧 Advanced Authentication Diagnostic")
    print("=" * 60)
    
    test_with_valid_login()
    test_authentication_backends()
    check_user_model_issue()
    
    print("\n📊 Next Steps")
    print("=" * 60)
    print("If all tests show HTTP 500 errors:")
    print("1. Check server logs for exact error details")
    print("2. Verify database migrations are applied")
    print("3. Check if role field is properly set (not NULL)")
    print("4. Test creating a fresh superuser with management command")
