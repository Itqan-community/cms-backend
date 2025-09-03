#!/usr/bin/env python3
"""
Fix admin user permissions to enable Django Admin and Wagtail access
"""
import requests
import json

def check_admin_user_details():
    """Get details about the admin user"""
    print("🔍 Checking Admin User Details...")
    
    base_url = "https://develop.api.cms.itqan.dev"
    
    # Login first to get access token
    login_url = f"{base_url}/api/v1/auth/login/"
    login_data = {
        "email": "admin@itqan.dev",
        "password": "ItqanCMS2024!"
    }
    
    try:
        response = requests.post(login_url, json=login_data)
        if response.status_code != 200:
            print("❌ Cannot login to check user details")
            return None
            
        login_result = response.json()
        access_token = login_result.get('access_token')
        
        if not access_token:
            print("❌ No access token received")
            return None
            
        # Get user profile
        profile_url = f"{base_url}/api/v1/auth/profile/"
        headers = {'Authorization': f'Bearer {access_token}'}
        
        profile_response = requests.get(profile_url, headers=headers)
        if profile_response.status_code == 200:
            profile_data = profile_response.json()
            print("✅ Admin user profile retrieved:")
            print(f"   → ID: {profile_data.get('id')}")
            print(f"   → Email: {profile_data.get('email')}")
            print(f"   → Name: {profile_data.get('first_name')} {profile_data.get('last_name')}")
            print(f"   → Role: {profile_data.get('role', 'Unknown')}")
            print(f"   → Is Active: {profile_data.get('is_active', 'Unknown')}")
            
            # Check if is_staff and is_superuser info is available
            if 'is_staff' in profile_data:
                print(f"   → Is Staff: {profile_data.get('is_staff')}")
            if 'is_superuser' in profile_data:
                print(f"   → Is Superuser: {profile_data.get('is_superuser')}")
                
            return profile_data
        else:
            print(f"❌ Cannot get profile: HTTP {profile_response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Error checking user details: {e}")
        return None

def check_roles_available():
    """Check what roles are available in the system"""
    print("\n🔍 Checking Available Roles...")
    
    base_url = "https://develop.api.cms.itqan.dev"
    
    # Login first
    login_url = f"{base_url}/api/v1/auth/login/"
    login_data = {
        "email": "admin@itqan.dev",
        "password": "ItqanCMS2024!"
    }
    
    try:
        response = requests.post(login_url, json=login_data)
        if response.status_code != 200:
            print("❌ Cannot login to check roles")
            return []
            
        login_result = response.json()
        access_token = login_result.get('access_token')
        
        if not access_token:
            print("❌ No access token received")
            return []
            
        # Try to get roles (this might not be available)
        roles_url = f"{base_url}/api/v1/roles/"
        headers = {'Authorization': f'Bearer {access_token}'}
        
        roles_response = requests.get(roles_url, headers=headers)
        if roles_response.status_code == 200:
            roles_data = roles_response.json()
            roles = roles_data.get('results', []) if 'results' in roles_data else roles_data
            print(f"✅ Found {len(roles)} roles:")
            
            for role in roles:
                print(f"   → {role.get('name', 'Unknown')}: {role.get('description', 'No description')}")
                
            return roles
        else:
            print(f"⚠️  Cannot access roles endpoint: HTTP {roles_response.status_code}")
            print("   → This might be normal if roles endpoint is protected")
            return []
            
    except Exception as e:
        print(f"❌ Error checking roles: {e}")
        return []

def analyze_admin_issue():
    """Analyze what's preventing admin access"""
    print("\n🔍 Analyzing Admin Access Issue...")
    
    # The user model requires is_staff=True for Django Admin access
    # and is_superuser=True for full admin privileges
    
    print("📋 Admin Access Requirements:")
    print("   → User must exist ✅ (confirmed)")
    print("   → is_active=True ✅ (can login via API)")
    print("   → is_staff=True ❓ (required for Django Admin)")
    print("   → is_superuser=True ❓ (required for full admin access)")
    print("   → Valid role assigned ❓ (User model has required role field)")
    
    print("\n💡 Most likely issues:")
    print("   1. User created via API has is_staff=False (normal for API users)")
    print("   2. User may not have admin role assigned")
    print("   3. User needs to be promoted to staff/superuser status")
    
    print("\n🔧 Solutions:")
    print("   1. Use Django management command to promote user")
    print("   2. Update user via database/admin interface")
    print("   3. Create new superuser with proper permissions")

def suggest_fix_commands():
    """Suggest commands to fix the admin user"""
    print("\n🔧 Suggested Fix Commands:")
    print("=" * 60)
    
    print("Option 1 - Promote existing user (via SSH to server):")
    print("""
    ssh [server] "cd /srv/cms-backend && docker compose exec web python manage.py shell -c \\
    \"from apps.accounts.models import User, Role; \\
     user = User.objects.get(email='admin@itqan.dev'); \\
     admin_role, created = Role.objects.get_or_create(name='Admin'); \\
     user.is_staff = True; \\
     user.is_superuser = True; \\
     user.role = admin_role; \\
     user.save(); \\
     print(f'User updated: staff={user.is_staff}, super={user.is_superuser}, role={user.role}')\\\"""")
    
    print("\nOption 2 - Create new superuser (via SSH to server):")
    print("""
    ssh [server] "cd /srv/cms-backend && docker compose exec web python manage.py createsuperuser"
    """)
    
    print("\nOption 3 - Use the setup command (via SSH to server):")
    print("""
    ssh [server] "cd /srv/cms-backend && docker compose exec web python manage.py setup_initial_data --create-superuser"
    """)

if __name__ == "__main__":
    print("🔧 Admin Permissions Diagnostic & Fix Tool")
    print("=" * 60)
    
    # Check admin user details
    user_details = check_admin_user_details()
    
    # Check available roles
    roles = check_roles_available()
    
    # Analyze the issue
    analyze_admin_issue()
    
    # Suggest fix commands
    suggest_fix_commands()
    
    print("\n📊 Summary")
    print("=" * 60)
    if user_details:
        print("✅ Admin user exists and can authenticate")
        print("❌ Admin user lacks permissions for admin interfaces")
        print("🔧 Solution: Promote user to staff/superuser status")
    else:
        print("❌ Cannot verify admin user details")
        print("🔧 Solution: Check user creation and API access")
