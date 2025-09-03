#!/usr/bin/env python3
"""
Test script to verify admin login functionality for both Django Admin and Wagtail CMS
"""
import requests
import sys
from bs4 import BeautifulSoup

def test_admin_login():
    """Test Django Admin login"""
    print("🔍 Testing Django Admin Login...")
    
    base_url = "https://develop.api.cms.itqan.dev"
    login_url = f"{base_url}/django-admin/login/"
    
    # Credentials from deployment script
    username = "admin@itqan.dev"
    password = "ItqanCMS2024!"
    
    session = requests.Session()
    
    try:
        # Get login page and CSRF token
        print(f"📡 Fetching login page: {login_url}")
        response = session.get(login_url)
        
        if response.status_code != 200:
            print(f"❌ Failed to fetch login page: HTTP {response.status_code}")
            return False
            
        soup = BeautifulSoup(response.content, 'html.parser')
        csrf_token = soup.find('input', {'name': 'csrfmiddlewaretoken'})
        
        if not csrf_token:
            print("❌ CSRF token not found in login page")
            return False
            
        csrf_value = csrf_token.get('value')
        print(f"✅ CSRF token extracted: {csrf_value[:20]}...")
        
        # Attempt login
        login_data = {
            'username': username,
            'password': password,
            'csrfmiddlewaretoken': csrf_value,
            'next': '/django-admin/'
        }
        
        print(f"🔐 Attempting login with username: {username}")
        login_response = session.post(login_url, data=login_data)
        
        # Check if login was successful
        if login_response.status_code == 302:
            redirect_location = login_response.headers.get('location', '')
            if '/django-admin/login/' in redirect_location:
                print("❌ Login failed - redirected back to login page")
                print(f"   Redirect location: {redirect_location}")
                return False
            else:
                print(f"✅ Login successful - redirected to: {redirect_location}")
                return True
        elif login_response.status_code == 200:
            # Check if we're still on login page (failed login)
            if 'Please enter a correct' in login_response.text:
                print("❌ Login failed - incorrect credentials")
                return False
            else:
                print("✅ Login successful - logged in")
                return True
        else:
            print(f"❌ Unexpected response: HTTP {login_response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error during login test: {e}")
        return False

def test_wagtail_login():
    """Test Wagtail CMS login"""
    print("\n🔍 Testing Wagtail CMS Login...")
    
    base_url = "https://develop.api.cms.itqan.dev"
    login_url = f"{base_url}/cms/login/"
    
    # Same credentials as Django Admin
    username = "admin@itqan.dev"
    password = "ItqanCMS2024!"
    
    session = requests.Session()
    
    try:
        # Get login page and CSRF token
        print(f"📡 Fetching login page: {login_url}")
        response = session.get(login_url)
        
        if response.status_code != 200:
            print(f"❌ Failed to fetch login page: HTTP {response.status_code}")
            return False
            
        soup = BeautifulSoup(response.content, 'html.parser')
        csrf_token = soup.find('input', {'name': 'csrfmiddlewaretoken'})
        
        if not csrf_token:
            print("❌ CSRF token not found in login page")
            return False
            
        csrf_value = csrf_token.get('value')
        print(f"✅ CSRF token extracted: {csrf_value[:20]}...")
        
        # Attempt login
        login_data = {
            'username': username,
            'password': password,
            'csrfmiddlewaretoken': csrf_value,
            'next': '/cms/'
        }
        
        print(f"🔐 Attempting login with username: {username}")
        login_response = session.post(login_url, data=login_data)
        
        # Check if login was successful
        if login_response.status_code == 302:
            redirect_location = login_response.headers.get('location', '')
            if '/cms/login/' in redirect_location:
                print("❌ Login failed - redirected back to login page")
                print(f"   Redirect location: {redirect_location}")
                return False
            else:
                print(f"✅ Login successful - redirected to: {redirect_location}")
                return True
        elif login_response.status_code == 200:
            # Check for error messages
            if 'Your username and password didn\'t match' in login_response.text:
                print("❌ Login failed - incorrect credentials")
                return False
            else:
                print("✅ Login successful - logged in")
                return True
        else:
            print(f"❌ Unexpected response: HTTP {login_response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error during login test: {e}")
        return False

def check_user_exists():
    """Check if admin user exists in database"""
    print("\n🔍 Checking if admin user exists...")
    
    try:
        # This would require direct database access or Django shell
        # For now, we'll rely on the login tests
        print("ℹ️  User existence check requires database access")
        print("ℹ️  Will be determined by login success/failure")
        return True
    except Exception as e:
        print(f"❌ Error checking user: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Admin Login Test Suite")
    print("=" * 50)
    
    # Test admin user existence
    check_user_exists()
    
    # Test Django Admin login
    django_success = test_admin_login()
    
    # Test Wagtail CMS login
    wagtail_success = test_wagtail_login()
    
    print("\n📊 Summary")
    print("=" * 50)
    print(f"Django Admin Login: {'✅ PASS' if django_success else '❌ FAIL'}")
    print(f"Wagtail CMS Login:  {'✅ PASS' if wagtail_success else '❌ FAIL'}")
    
    if not django_success or not wagtail_success:
        print("\n🔧 Troubleshooting Steps:")
        print("1. Verify admin user exists: python manage.py shell -c \"from apps.accounts.models import User; print(User.objects.filter(email='admin@itqan.dev').exists())\"")
        print("2. Create admin user: python manage.py createsuperuser")
        print("3. Check user permissions: python manage.py shell -c \"from apps.accounts.models import User; u=User.objects.get(email='admin@itqan.dev'); print(f'Active: {u.is_active}, Staff: {u.is_staff}, Super: {u.is_superuser}')\"")
        print("4. Reset password: python manage.py shell -c \"from apps.accounts.models import User; u=User.objects.get(email='admin@itqan.dev'); u.set_password('ItqanCMS2024!'); u.save()\"")
        
        sys.exit(1)
    else:
        print("\n🎉 All tests passed!")
        sys.exit(0)
