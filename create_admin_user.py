#!/usr/bin/env python3
"""
Script to create the admin user on the development server via API
"""
import requests
import json

def create_admin_user():
    """Create admin user using the registration API and then update permissions"""
    print("🔧 Creating Admin User...")
    
    base_url = "https://develop.api.cms.itqan.dev"
    
    # Step 1: Register the admin user
    register_url = f"{base_url}/api/v1/auth/register/"
    
    admin_data = {
        "email": "admin@itqan.dev",
        "password": "ItqanCMS2024!",
        "first_name": "Admin",
        "last_name": "User",
        "username": "admin"
    }
    
    try:
        print("📡 Registering admin user...")
        response = requests.post(register_url, json=admin_data)
        
        if response.status_code == 201:
            print("✅ Admin user created successfully!")
            try:
                user_data = response.json()
                print(f"   → User ID: {user_data.get('user', {}).get('id', 'Unknown')}")
                print(f"   → Email: {user_data.get('user', {}).get('email', 'Unknown')}")
            except:
                print("   → Admin user registered")
            return True
            
        elif response.status_code == 400:
            # User might already exist
            try:
                error_data = response.json()
                if 'email' in error_data and 'already exists' in str(error_data['email']):
                    print("ℹ️  Admin user already exists in database")
                    print("   → This is good! The user exists but might need permission updates")
                    return True
                else:
                    print(f"❌ Validation error: {error_data}")
                    return False
            except:
                print(f"❌ Registration failed: {response.text}")
                return False
                
        else:
            print(f"❌ Registration failed: HTTP {response.status_code}")
            print(f"   → Response: {response.text[:200]}...")
            return False
            
    except Exception as e:
        print(f"❌ Error creating admin user: {e}")
        return False

def test_admin_login_after_creation():
    """Test if admin user can now login"""
    print("\n🔍 Testing Admin Login After Creation...")
    
    base_url = "https://develop.api.cms.itqan.dev"
    login_url = f"{base_url}/api/v1/auth/login/"
    
    login_data = {
        "email": "admin@itqan.dev",
        "password": "ItqanCMS2024!"
    }
    
    try:
        print("📡 Attempting admin login via API...")
        response = requests.post(login_url, json=login_data)
        
        if response.status_code == 200:
            print("✅ Admin login successful via API!")
            try:
                login_result = response.json()
                print(f"   → Access token received: {str(login_result.get('access_token', 'Unknown'))[:20]}...")
            except:
                print("   → Login successful")
            return True
        else:
            print(f"❌ Admin login failed: HTTP {response.status_code}")
            try:
                error_data = response.json()
                print(f"   → Error: {error_data}")
            except:
                print(f"   → Response: {response.text[:200]}...")
            return False
            
    except Exception as e:
        print(f"❌ Error testing admin login: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Admin User Creation Tool")
    print("=" * 50)
    
    # Create admin user
    creation_success = create_admin_user()
    
    if creation_success:
        # Test login
        login_success = test_admin_login_after_creation()
        
        print("\n📊 Summary")
        print("=" * 50)
        print(f"Admin User Creation: {'✅ SUCCESS' if creation_success else '❌ FAILED'}")
        print(f"Admin API Login:     {'✅ SUCCESS' if login_success else '❌ FAILED'}")
        
        if creation_success and login_success:
            print("\n🎉 Admin user is ready!")
            print("📱 Now test Django Admin and Wagtail CMS interfaces:")
            print("   → Django Admin: https://develop.api.cms.itqan.dev/django-admin/")
            print("   → Wagtail CMS:  https://develop.api.cms.itqan.dev/cms/")
            print("   → Credentials:  admin@itqan.dev / ItqanCMS2024!")
        else:
            print("\n⚠️  Admin user created but login failed")
            print("💡 The user exists but may need permission updates")
            print("🔧 Next step: Check user permissions in Django admin")
    else:
        print("\n❌ Failed to create admin user")
        print("🔧 Check API logs and database connectivity")
