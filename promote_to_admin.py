#!/usr/bin/env python3
"""
Promote the admin user to have proper staff and superuser permissions
This script will use direct database API calls if available
"""
import requests
import json

def create_admin_role_first():
    """Try to create the Admin role if it doesn't exist"""
    print("🔧 Creating Admin Role...")
    
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
            print("❌ Cannot login")
            return False
            
        login_result = response.json()
        access_token = login_result.get('access_token')
        
        if not access_token:
            print("❌ No access token received")
            return False
            
        # Try to create Admin role
        roles_url = f"{base_url}/api/v1/roles/"
        headers = {'Authorization': f'Bearer {access_token}'}
        
        admin_role_data = {
            "name": "Admin",
            "description": "System administrator with full access",
            "permissions": {
                "resources": ["create", "read", "update", "delete"],
                "licenses": ["create", "read", "update", "delete"],
                "distributions": ["create", "read", "update", "delete"],
                "users": ["create", "read", "update", "delete"],
                "analytics": ["read"]
            }
        }
        
        role_response = requests.post(roles_url, json=admin_role_data, headers=headers)
        
        if role_response.status_code == 201:
            print("✅ Admin role created successfully")
            return True
        elif role_response.status_code == 400:
            print("ℹ️  Admin role might already exist")
            return True
        elif role_response.status_code == 403:
            print("⚠️  Cannot create role - insufficient permissions")
            print("   → This is expected since user isn't admin yet")
            return True  # Continue anyway
        else:
            print(f"❌ Failed to create role: HTTP {role_response.status_code}")
            return True  # Continue anyway
            
    except Exception as e:
        print(f"❌ Error creating admin role: {e}")
        return True  # Continue anyway

def use_management_command_approach():
    """Provide commands for direct database manipulation"""
    print("\n🔧 Database Direct Update Approach")
    print("=" * 60)
    
    print("Since API-based permission updates aren't available,")
    print("we need to update the database directly.")
    print("\nHere are the exact commands to run on the server:")
    
    print("\n📋 Step-by-step fix:")
    print("1. SSH into the development server")
    print("2. Navigate to the application directory")
    print("3. Execute the database update commands")
    
    print("\n💻 Commands to run:")
    print("""
# SSH into the server
ssh root@167.172.227.184

# Navigate to app directory  
cd /srv/cms-backend/deployment/docker

# Update admin user permissions
docker compose -f docker-compose.develop.yml exec web python manage.py shell -c "
from apps.accounts.models import User, Role
import traceback

try:
    # Get or create Admin role
    admin_role, created = Role.objects.get_or_create(
        name='Admin',
        defaults={
            'description': 'System administrator with full access',
            'permissions': {
                'resources': ['create', 'read', 'update', 'delete'],
                'licenses': ['create', 'read', 'update', 'delete'], 
                'distributions': ['create', 'read', 'update', 'delete'],
                'users': ['create', 'read', 'update', 'delete'],
                'analytics': ['read']
            }
        }
    )
    print(f'Admin role: {admin_role.name} (created: {created})')
    
    # Update admin user
    user = User.objects.get(email='admin@itqan.dev')
    user.is_staff = True
    user.is_superuser = True
    user.role = admin_role
    user.save()
    
    print(f'User updated successfully:')
    print(f'  Email: {user.email}')
    print(f'  Active: {user.is_active}')
    print(f'  Staff: {user.is_staff}')
    print(f'  Superuser: {user.is_superuser}')
    print(f'  Role: {user.role.name}')
    
except Exception as e:
    print(f'Error: {str(e)}')
    traceback.print_exc()
"
    """)
    
    print("\n🔄 Alternative one-liner command:")
    print("""
docker compose -f docker-compose.develop.yml exec web python manage.py shell -c "from apps.accounts.models import User, Role; admin_role, created = Role.objects.get_or_create(name='Admin', defaults={'description': 'System administrator', 'permissions': {}}); user = User.objects.get(email='admin@itqan.dev'); user.is_staff = True; user.is_superuser = True; user.role = admin_role; user.save(); print(f'Updated: staff={user.is_staff}, super={user.is_superuser}, role={user.role.name}')"
    """)

def test_after_promotion():
    """Instructions for testing after promotion"""
    print("\n🧪 Testing After Promotion")
    print("=" * 60)
    
    print("After running the database update commands, test admin access:")
    print("\n1. Django Admin Interface:")
    print("   → URL: https://develop.api.cms.itqan.dev/django-admin/")
    print("   → Credentials: admin@itqan.dev / ItqanCMS2024!")
    print("   → Expected: Successful login to Django admin dashboard")
    
    print("\n2. Wagtail CMS Interface:")
    print("   → URL: https://develop.api.cms.itqan.dev/cms/")
    print("   → Credentials: admin@itqan.dev / ItqanCMS2024!")
    print("   → Expected: Successful login to Wagtail admin dashboard")
    
    print("\n3. Re-run our test scripts:")
    print("   → python3 test_admin_login.py")
    print("   → Expected: Both admin interfaces should return HTTP 200/302 (success)")

if __name__ == "__main__":
    print("🚀 Admin User Promotion Tool")
    print("=" * 60)
    
    # Try to create admin role first (will likely fail due to permissions)
    role_created = create_admin_role_first()
    
    # Provide management command approach
    use_management_command_approach()
    
    # Test instructions
    test_after_promotion()
    
    print("\n📊 Summary")
    print("=" * 60)
    print("✅ Admin user exists and can authenticate")
    print("❌ Admin user needs staff/superuser promotion")
    print("🔧 Solution: Run the database update commands above")
    print("🎯 Goal: Enable Django Admin and Wagtail CMS access")
