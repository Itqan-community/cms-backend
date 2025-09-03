#!/usr/bin/env python3
"""
Test script to check if we can create users and identify the specific authentication issue
"""
import requests
import json

def test_direct_user_creation():
    """Test if we can create a user through the API"""
    print("🔍 Testing User Creation via API...")
    
    base_url = "https://develop.api.cms.itqan.dev"
    
    # First check if we can access the mock API which works
    try:
        print("📡 Testing mock API user list...")
        response = requests.get(f"{base_url}/mock-api/auth/test-users")
        if response.status_code == 200:
            print("✅ Mock API works - database connection OK")
            users = response.json()
            print(f"   → Found {len(users.get('users', []))} mock users")
        else:
            print(f"❌ Mock API failed: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Mock API error: {e}")
        return False
    
    # Test the actual auth API to see if it has different errors
    try:
        print("📡 Testing real auth API registration...")
        register_url = f"{base_url}/api/v1/auth/register/"
        
        test_user_data = {
            "email": "test-user-creation@example.com",
            "password": "TestPassword123!",
            "first_name": "Test",
            "last_name": "User",
            "username": "testusercreation"
        }
        
        response = requests.post(register_url, json=test_user_data)
        print(f"📊 Registration Response: HTTP {response.status_code}")
        
        if response.status_code == 400:
            print("⚠️  Validation error (expected for duplicate/invalid data)")
            try:
                error_data = response.json()
                print(f"   → Error details: {error_data}")
            except:
                print(f"   → Response text: {response.text[:200]}...")
        elif response.status_code == 500:
            print("❌ Server error in user creation - same as admin login")
            return False
        elif response.status_code == 201:
            print("✅ User creation works - admin issue is different")
            try:
                user_data = response.json()
                print(f"   → Created user: {user_data.get('email', 'Unknown')}")
            except:
                print("   → User created successfully")
        else:
            print(f"🟡 Unexpected response: {response.status_code}")
            print(f"   → Response: {response.text[:200]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Auth API error: {e}")
        return False

def test_admin_user_exists():
    """Check if we can find admin user through different endpoints"""
    print("\n🔍 Testing Admin User Existence...")
    
    base_url = "https://develop.api.cms.itqan.dev"
    
    # Check if admin email exists in mock users
    try:
        response = requests.get(f"{base_url}/mock-api/auth/test-users")
        if response.status_code == 200:
            data = response.json()
            admin_found = False
            
            for user in data.get('users', []):
                if user.get('email') == 'admin@itqan.dev':
                    admin_found = True
                    print(f"✅ Found admin user in mock data:")
                    print(f"   → Email: {user.get('email')}")
                    print(f"   → Name: {user.get('name')}")
                    break
            
            if not admin_found:
                print("❌ Admin user not found in mock data")
                print("ℹ️  This suggests the admin user may not exist in the real database")
            
            return admin_found
        else:
            print(f"❌ Could not fetch test users: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error checking admin user: {e}")
        return False

def test_role_dependency():
    """Check if roles exist in the system"""
    print("\n🔍 Testing Role Dependency...")
    
    # The User model requires a Role - check if roles exist
    base_url = "https://develop.api.cms.itqan.dev"
    
    try:
        # Try to access any endpoint that might tell us about roles
        print("📡 Checking system configuration...")
        
        # Check if we can access any info endpoint
        response = requests.get(f"{base_url}/api/v1/")
        print(f"📊 API Root Response: HTTP {response.status_code}")
        
        if response.status_code == 401:
            print("✅ API requires authentication (normal behavior)")
        elif response.status_code == 500:
            print("❌ API root also returns 500 - system-wide issue")
        elif response.status_code == 200:
            print("✅ API root accessible")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing role dependency: {e}")
        return False

if __name__ == "__main__":
    print("🔧 User Creation & Admin Diagnostic Tool")
    print("=" * 60)
    
    # Test user creation functionality
    creation_success = test_direct_user_creation()
    
    # Test admin user existence
    admin_exists = test_admin_user_exists()
    
    # Test role dependency
    role_test = test_role_dependency()
    
    print("\n📊 Summary")
    print("=" * 60)
    print(f"User Creation Test: {'✅ PASS' if creation_success else '❌ FAIL'}")
    print(f"Admin User Exists:  {'✅ PASS' if admin_exists else '❌ FAIL'}")
    print(f"Role System Test:   {'✅ PASS' if role_test else '❌ FAIL'}")
    
    if not admin_exists:
        print("\n💡 Likely Issue: Admin user does not exist in database")
        print("🔧 Solution: Create admin user through deployment script or management command")
    elif not creation_success:
        print("\n💡 Likely Issue: System-wide authentication/database problem")
        print("🔧 Solution: Check database migrations and model configuration")
    else:
        print("\n💡 Issue is specific to admin authentication vs. user creation")
        print("🔧 Solution: Check admin user permissions and role assignment")
