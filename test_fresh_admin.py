#!/usr/bin/env python3
"""
Test login with the fresh admin user we just created
"""
import requests
from bs4 import BeautifulSoup

def test_fresh_admin_login():
    """Test Django Admin login with fresh superuser"""
    print("🔍 Testing Fresh Admin User Login...")
    
    base_url = "https://develop.api.cms.itqan.dev"
    login_url = f"{base_url}/django-admin/login/"
    
    # Fresh admin credentials
    username = "newadmin@itqan.dev"
    password = "NewAdminPass123!"
    
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
        
        print(f"🔐 Attempting login with fresh admin: {username}")
        login_response = session.post(login_url, data=login_data)
        
        # Check response
        print(f"📊 Response Status: {login_response.status_code}")
        
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
        elif login_response.status_code == 400:
            print("❌ Bad Request - likely authentication issue")
            # Try to extract error details
            if 'error' in login_response.text.lower():
                print(f"   Error details: {login_response.text[:300]}...")
            return False
        else:
            print(f"❌ Unexpected response: HTTP {login_response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error during login test: {e}")
        return False

def test_wagtail_fresh_admin():
    """Test Wagtail CMS login with fresh superuser"""
    print("\n🔍 Testing Fresh Admin User - Wagtail CMS...")
    
    base_url = "https://develop.api.cms.itqan.dev"
    login_url = f"{base_url}/cms/login/"
    
    # Fresh admin credentials
    username = "newadmin@itqan.dev"
    password = "NewAdminPass123!"
    
    session = requests.Session()
    
    try:
        response = session.get(login_url)
        
        if response.status_code != 200:
            print(f"❌ Failed to fetch Wagtail login page: HTTP {response.status_code}")
            return False
            
        soup = BeautifulSoup(response.content, 'html.parser')
        csrf_token = soup.find('input', {'name': 'csrfmiddlewaretoken'})
        
        if not csrf_token:
            print("❌ CSRF token not found in Wagtail login page")
            return False
            
        csrf_value = csrf_token.get('value')
        print(f"✅ Wagtail CSRF token extracted: {csrf_value[:20]}...")
        
        login_data = {
            'username': username,
            'password': password,
            'csrfmiddlewaretoken': csrf_value,
            'next': '/cms/'
        }
        
        print(f"🔐 Attempting Wagtail login with fresh admin: {username}")
        login_response = session.post(login_url, data=login_data)
        
        print(f"📊 Wagtail Response Status: {login_response.status_code}")
        
        if login_response.status_code == 302:
            redirect_location = login_response.headers.get('location', '')
            if '/cms/login/' in redirect_location:
                print("❌ Wagtail login failed - redirected back to login page")
                return False
            else:
                print(f"✅ Wagtail login successful - redirected to: {redirect_location}")
                return True
        elif login_response.status_code == 200:
            if 'Your username and password didn\'t match' in login_response.text:
                print("❌ Wagtail login failed - incorrect credentials")
                return False
            else:
                print("✅ Wagtail login successful")
                return True
        else:
            print(f"❌ Wagtail unexpected response: HTTP {login_response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error during Wagtail login test: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Fresh Admin Login Test")
    print("=" * 50)
    
    # Test Django Admin
    django_success = test_fresh_admin_login()
    
    # Test Wagtail CMS
    wagtail_success = test_wagtail_fresh_admin()
    
    print("\n📊 Fresh Admin Test Results")
    print("=" * 50)
    print(f"Django Admin:  {'✅ SUCCESS' if django_success else '❌ FAILED'}")
    print(f"Wagtail CMS:   {'✅ SUCCESS' if wagtail_success else '❌ FAILED'}")
    
    if django_success and wagtail_success:
        print("\n🎉 ADMIN LOGIN WORKING!")
        print("📱 Admin Interface Access:")
        print("   → Django Admin: https://develop.api.cms.itqan.dev/django-admin/")
        print("   → Wagtail CMS:  https://develop.api.cms.itqan.dev/cms/")
        print("   → Credentials:  newadmin@itqan.dev / NewAdminPass123!")
    elif django_success or wagtail_success:
        print("\n🟡 Partial Success - One interface working")
    else:
        print("\n❌ Both interfaces still failing")
        print("   → The UserManager fix helped (HTTP 500 → HTTP 400)")
        print("   → Need to investigate authentication backend further")
