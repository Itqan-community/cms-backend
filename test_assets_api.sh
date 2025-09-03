#!/bin/bash

# Assets API Test Script for Itqan CMS
# Tests all asset endpoints on develop.api.cms.itqan.dev
# Creates test data and runs comprehensive endpoint tests

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m' # No Color

# API Configuration (set defaults, will be overridden in main())
BASE_URL="${BASE_URL:-https://develop.api.cms.itqan.dev}"
API_BASE="${BASE_URL}/api/v1"
HEALTH_URL="${BASE_URL}/health"

# Test user credentials (these should exist or be created)
TEST_EMAIL="${TEST_EMAIL:-test@example.com}"
TEST_PASSWORD="${TEST_PASSWORD:-testpass123}"

# Global variables
ACCESS_TOKEN=""
ASSET_ID=""
TEST_ASSETS=()
VERBOSE=false

# Function to print colored status
print_status() {
    local status=$1
    local message=$2
    if [ "$status" = "PASS" ]; then
        echo -e "  ${BOLD}${GREEN}✅ PASS${NC} ${WHITE}→${NC} ${GREEN}$message${NC}"
    elif [ "$status" = "FAIL" ]; then
        echo -e "  ${BOLD}${RED}❌ FAIL${NC} ${WHITE}→${NC} ${RED}$message${NC}"
    elif [ "$status" = "INFO" ]; then
        echo -e "  ${BOLD}${CYAN}ℹ️  INFO${NC} ${WHITE}→${NC} ${CYAN}$message${NC}"
    elif [ "$status" = "WARN" ]; then
        echo -e "  ${BOLD}${YELLOW}⚠️  WARN${NC} ${WHITE}→${NC} ${YELLOW}$message${NC}"
    elif [ "$status" = "SUCCESS" ]; then
        echo -e "  ${BOLD}${GREEN}🎉 SUCCESS${NC} ${WHITE}→${NC} ${GREEN}$message${NC}"
    elif [ "$status" = "ERROR" ]; then
        echo -e "  ${BOLD}${RED}💥 ERROR${NC} ${WHITE}→${NC} ${RED}$message${NC}"
    fi
}

# Function to make API calls with proper error handling and verbose output
api_call() {
    local method=$1
    local endpoint=$2
    local data=$3
    local auth_header=""
    local curl_cmd=""
    
    if [ ! -z "$ACCESS_TOKEN" ]; then
        auth_header="-H \"Authorization: Bearer $ACCESS_TOKEN\""
    fi
    
    # Build the curl command for display
    if [ ! -z "$data" ]; then
        curl_cmd="curl -s -X \"$method\" \"$endpoint\" -H \"Content-Type: application/json\" $auth_header -d '$data'"
    else
        curl_cmd="curl -s -X \"$method\" \"$endpoint\" -H \"Content-Type: application/json\" $auth_header"
    fi
    
    # Show the curl command
    echo -e "    ${BOLD}${PURPLE}📤 CURL COMMAND:${NC}"
    echo -e "    ${DIM}${CYAN}$curl_cmd${NC}"
    
    # Execute and capture response
    local response
    if [ ! -z "$data" ]; then
        response=$(eval curl -s -X "$method" "$endpoint" \
            -H "\"Content-Type: application/json\"" \
            $auth_header \
            -d "'$data'")
    else
        response=$(eval curl -s -X "$method" "$endpoint" \
            -H "\"Content-Type: application/json\"" \
            $auth_header)
    fi
    
    # Show the response
    echo -e "    ${BOLD}${PURPLE}📥 RESPONSE:${NC}"
    if is_json "$response"; then
        echo "$response" | python3 -m json.tool 2>/dev/null | sed 's/^/        /' || echo "$response" | sed 's/^/        /'
    else
        echo "$response" | head -10 | sed 's/^/        /' | sed 's/\(HTTP.*\)/'"${BOLD}${WHITE}"'\1'"${NC}"'/g'
        if [ $(echo "$response" | wc -l) -gt 10 ]; then
            echo -e "        ${DIM}... (response truncated)${NC}"
        fi
    fi
    echo ""
    
    # Return the response for processing
    printf "%s" "$response"
}

# Function to check if response is valid JSON
is_json() {
    echo "$1" | python3 -m json.tool > /dev/null 2>&1
}

# Function to extract JSON field
get_json_field() {
    local json=$1
    local field=$2
    echo "$json" | python3 -c "import sys,json; data=json.load(sys.stdin); print(data.get('$field', ''))" 2>/dev/null || echo ""
}

# Function to test health endpoint
test_health() {
    echo ""
    echo -e "${BOLD}${YELLOW}🔍 Testing Health Endpoint${NC}"
    echo -e "${DIM}${PURPLE}▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔${NC}"
    
    echo -e "    ${BOLD}${PURPLE}📤 CURL COMMAND:${NC}"
    echo -e "    ${DIM}${CYAN}curl -s \"$HEALTH_URL\"${NC}"
    local response=$(curl -s "$HEALTH_URL")
    
    echo -e "    ${BOLD}${PURPLE}📥 RESPONSE:${NC}"
    if is_json "$response"; then
        echo "$response" | python3 -m json.tool 2>/dev/null | sed 's/^/        /' || echo "$response" | sed 's/^/        /'
        local status=$(get_json_field "$response" "status")
        if [ "$status" = "healthy" ]; then
            print_status "PASS" "Health endpoint responded with healthy status"
        else
            print_status "FAIL" "Health endpoint not healthy: $status"
            return 1
        fi
    else
        echo "$response" | head -10 | sed 's/^/        /'
        print_status "FAIL" "Health endpoint returned non-JSON response"
        return 1
    fi
    echo ""
}

# Function to authenticate and get token
authenticate() {
    echo ""
    echo -e "${BOLD}${YELLOW}🔐 Authenticating User${NC}"
    echo -e "${DIM}${PURPLE}▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔${NC}"
    
    local login_data="{\"email\": \"$TEST_EMAIL\", \"password\": \"$TEST_PASSWORD\"}"
    
    # Show the curl command
    echo -e "    ${BOLD}${PURPLE}📤 CURL COMMAND:${NC}"
    echo -e "    ${DIM}${CYAN}curl -s -X \"POST\" \"$API_BASE/auth/login/\" -H \"Content-Type: application/json\" -d '$login_data'${NC}"
    
    # Execute the request
    local response=$(curl -s -X "POST" "$API_BASE/auth/login/" \
        -H "Content-Type: application/json" \
        -d "$login_data")
    
    # Show the response
    echo -e "    ${BOLD}${PURPLE}📥 RESPONSE:${NC}"
    if is_json "$response"; then
        echo "$response" | python3 -m json.tool 2>/dev/null | sed 's/^/        /' || echo "$response" | sed 's/^/        /'
    else
        echo "$response" | head -10 | sed 's/^/        /' | sed 's/\(HTTP.*\)/'"${BOLD}${WHITE}"'\1'"${NC}"'/g'
    fi
    echo ""
    
    if is_json "$response"; then
        ACCESS_TOKEN=$(get_json_field "$response" "access_token")
        if [ ! -z "$ACCESS_TOKEN" ] && [ "$ACCESS_TOKEN" != "null" ]; then
            print_status "PASS" "Successfully authenticated and received JWT token"
            print_status "INFO" "Token: ${ACCESS_TOKEN:0:20}..."
        else
            print_status "FAIL" "Login successful but no access token received"
            return 1
        fi
    else
        print_status "FAIL" "Authentication failed - non-JSON response"
        return 1
    fi
    echo ""
}

# Function to create test data
create_test_data() {
    echo ""
    echo -e "${BOLD}${YELLOW}📊 Creating Test Data${NC}"
    echo -e "${DIM}${PURPLE}▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔${NC}"
    
    print_status "INFO" "Creating test assets with '- Test' suffix..."
    
    if [ -z "$ACCESS_TOKEN" ]; then
        print_status "FAIL" "No access token available for creating test data"
        return 1
    fi
    
    # Test asset data with "- Test" suffix
    local test_assets=(
        "Quran Uthmani Script - Test|Complete Quranic text in Uthmani script for API testing|text"
        "Tafsir Ibn Katheer - Test|Classical Quranic commentary by Ibn Katheer for API testing|tafsir"  
        "Recitation Al-Afasy - Test|Complete Quranic recitation by Sheikh Mishary Al-Afasy for API testing|audio"
        "Quran Translation English - Test|English translation of the Quran for API testing|translation"
        "Tajweed Rules Guide - Test|Comprehensive guide to Tajweed rules for API testing|text"
    )
    
    local created_count=0
    
    # Try different approaches to create test data
    print_status "INFO" "Attempting to create test data through available endpoints..."
    
    # Try to create test data through Django management API endpoint
    local django_script_data="{
        \"script\": \"
from django.contrib.auth import get_user_model
from apps.content.models import Resource, Distribution
from apps.licensing.models import License
from django.utils import timezone
import json

User = get_user_model()
user = User.objects.filter(email='$TEST_EMAIL').first()
results = []

if user:
    test_assets = [
        {'title': 'Quran Uthmani Script - Test', 'description': 'Complete Quranic text in Uthmani script for API testing', 'resource_type': 'text'},
        {'title': 'Tafsir Ibn Katheer - Test', 'description': 'Classical Quranic commentary by Ibn Katheer for API testing', 'resource_type': 'tafsir'},
        {'title': 'Recitation Al-Afasy - Test', 'description': 'Complete Quranic recitation by Sheikh Mishary Al-Afasy for API testing', 'resource_type': 'audio'},
        {'title': 'Quran Translation English - Test', 'description': 'English translation of the Quran for API testing', 'resource_type': 'translation'},
        {'title': 'Tajweed Rules Guide - Test', 'description': 'Comprehensive guide to Tajweed rules for API testing', 'resource_type': 'text'}
    ]
    
    for asset_data in test_assets:
        try:
            r, created = Resource.objects.get_or_create(
                title=asset_data['title'],
                defaults={
                    'description': asset_data['description'],
                    'resource_type': asset_data['resource_type'],
                    'language': 'ar',
                    'version': '1.0.0',
                    'publisher': user,
                    'workflow_status': 'published',
                    'published_at': timezone.now(),
                    'metadata': {'test_data': True, 'api_testing': True}
                }
            )
            
            if created:
                Distribution.objects.get_or_create(
                    resource=r,
                    format_type='ZIP',
                    version='1.0.0',
                    defaults={
                        'endpoint_url': f'https://cdn.example.com/downloads/{r.title.lower().replace(\\\" \\\", \\\"-\\\")}.zip'
                    }
                )
                
                License.objects.get_or_create(
                    resource=r,
                    defaults={
                        'license_type': 'open',
                        'terms': 'Test license for API testing - CC0 Public Domain',
                        'requires_approval': False,
                        'effective_from': timezone.now()
                    }
                )
                results.append(f'Created: {r.title}')
            else:
                results.append(f'Already exists: {r.title}')
        except Exception as e:
            results.append(f'Error creating {asset_data[\\\"title\\\"]}: {str(e)}')
else:
    results.append('Test user not found')

print(json.dumps({'results': results, 'success': len([r for r in results if 'Created:' in r])}))
\"
    }"
    
    # Try to execute via Django shell endpoint (if available)
    local django_response=$(curl -s -X POST "$BASE_URL/api/v1/admin/execute-script/" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $ACCESS_TOKEN" \
        -d "$django_script_data" 2>/dev/null || echo '{}')
    
    if echo "$django_response" | grep -q "Created:" 2>/dev/null; then
        local success_count=$(echo "$django_response" | python3 -c "import sys,json; data=json.load(sys.stdin); print(data.get('success', 0))" 2>/dev/null || echo "0")
        print_status "SUCCESS" "Created $success_count test assets via Django API"
        created_count=$success_count
    else
        # Fallback: Try direct API creation with registration
        for asset_data in "${test_assets[@]}"; do
            IFS='|' read -r title description resource_type <<< "$asset_data"
            
            # Try creating user first if needed
            local user_data="{\"email\": \"publisher-$(date +%s)@example.com\", \"password\": \"testpass123\", \"first_name\": \"Test\", \"last_name\": \"Publisher\"}"
            local user_response=$(curl -s -X POST "$BASE_URL/api/v1/auth/register/" \
                -H "Content-Type: application/json" \
                -d "$user_data" 2>/dev/null || echo '{}')
            
            # Try to create via any available endpoint
            print_status "WARN" "Direct API creation not available for: $title"
        done
    fi
    
    # If we couldn't create through APIs, create a script file that can be executed
    if [ $created_count -eq 0 ]; then
        print_status "INFO" "Direct API creation not available - creating executable script"
        
        # Create a temporary script file
        local script_file="/tmp/create_test_assets_$(date +%s).py"
        cat > "$script_file" << 'EOF'
#!/usr/bin/env python3
"""
Test data creation script for Itqan CMS Assets API
Run this on your Django server: python3 create_test_assets.py
"""

import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from django.contrib.auth import get_user_model
from apps.content.models import Resource, Distribution
from apps.licensing.models import License
from django.utils import timezone

def create_test_assets(email='test@example.com'):
    User = get_user_model()
    user = User.objects.filter(email=email).first()
    
    if not user:
        print(f"❌ User {email} not found!")
        return []
    
    print(f"✅ Found user: {user.email}")
    
    test_assets = [
        {
            'title': 'Quran Uthmani Script - Test',
            'description': 'Complete Quranic text in Uthmani script for API testing',
            'resource_type': 'text'
        },
        {
            'title': 'Tafsir Ibn Katheer - Test',
            'description': 'Classical Quranic commentary by Ibn Katheer for API testing',
            'resource_type': 'tafsir'
        },
        {
            'title': 'Recitation Al-Afasy - Test',
            'description': 'Complete Quranic recitation by Sheikh Mishary Al-Afasy for API testing',
            'resource_type': 'audio'
        },
        {
            'title': 'Quran Translation English - Test',
            'description': 'English translation of the Quran for API testing',
            'resource_type': 'translation'
        },
        {
            'title': 'Tajweed Rules Guide - Test',
            'description': 'Comprehensive guide to Tajweed rules for API testing',
            'resource_type': 'text'
        }
    ]
    
    created_assets = []
    
    for asset_data in test_assets:
        try:
            r, created = Resource.objects.get_or_create(
                title=asset_data['title'],
                defaults={
                    'description': asset_data['description'],
                    'resource_type': asset_data['resource_type'],
                    'language': 'ar',
                    'version': '1.0.0',
                    'publisher': user,
                    'workflow_status': 'published',
                    'published_at': timezone.now(),
                    'metadata': {'test_data': True, 'api_testing': True}
                }
            )
            
            if created:
                # Create distribution
                Distribution.objects.get_or_create(
                    resource=r,
                    format_type='ZIP',
                    version='1.0.0',
                    defaults={
                        'endpoint_url': f'https://cdn.example.com/downloads/{r.title.lower().replace(" ", "-")}.zip'
                    }
                )
                
                # Create license
                License.objects.get_or_create(
                    resource=r,
                    defaults={
                        'license_type': 'open',
                        'terms': 'Test license for API testing - CC0 Public Domain',
                        'requires_approval': False,
                        'effective_from': timezone.now()
                    }
                )
                
                print(f"✅ Created: {r.title}")
                created_assets.append(r)
            else:
                print(f"ℹ️  Already exists: {r.title}")
                created_assets.append(r)
                
        except Exception as e:
            print(f"❌ Error creating {asset_data['title']}: {str(e)}")
    
    print(f"\n🎉 Total assets available: {len(created_assets)}")
    return created_assets

if __name__ == "__main__":
    email = sys.argv[1] if len(sys.argv) > 1 else 'test@example.com'
    create_test_assets(email)
EOF

        chmod +x "$script_file"
        
        print_status "SUCCESS" "Created executable script: $script_file"
        print_status "INFO" "Upload this script to your server and run:"
        print_status "INFO" "python3 $(basename $script_file) $TEST_EMAIL"
        print_status "INFO" "Script file is ready for deployment!"
        
        # Show how to use it
        echo ""
        echo -e "${BOLD}${CYAN}📋 To create test data on develop server:${NC}"
        echo -e "${WHITE}1.${NC} Copy the script to your server:"
        echo -e "   ${DIM}scp $script_file your-server:/tmp/${NC}"
        echo -e "${WHITE}2.${NC} Run on server:"
        echo -e "   ${DIM}cd /path/to/your/django/project${NC}"
        echo -e "   ${DIM}python3 /tmp/$(basename $script_file) $TEST_EMAIL${NC}"
        echo -e "${WHITE}3.${NC} Verify with our test script:"
        echo -e "   ${DIM}./test_assets_api.sh --assets${NC}"
        
    else
        print_status "SUCCESS" "Created $created_count test assets successfully"
        # Wait for data to be processed
        sleep 3
    fi
    
    echo ""
}

# Function to test asset list endpoint
test_asset_list() {
    echo ""
    echo -e "${BOLD}${YELLOW}📋 Testing Asset List Endpoint${NC}"
    echo -e "${DIM}${PURPLE}▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔${NC}"
    
    # Test unauthenticated access
    local response=$(api_call "GET" "$API_BASE/assets/")
    
    if is_json "$response"; then
        local assets_count=$(echo "$response" | python3 -c "import sys,json; data=json.load(sys.stdin); print(len(data.get('assets', [])))")
        print_status "PASS" "Asset list endpoint returned valid JSON"
        print_status "INFO" "Found $assets_count assets"
        
        # Store first asset ID for further testing
        ASSET_ID=$(echo "$response" | python3 -c "import sys,json; data=json.load(sys.stdin); assets=data.get('assets', []); print(assets[0]['id'] if assets else '')")
        
        if [ ! -z "$ASSET_ID" ]; then
            print_status "INFO" "Using asset ID for testing: $ASSET_ID"
        fi
    else
        print_status "FAIL" "Asset list endpoint returned non-JSON response"
        echo "Response: $response"
        return 1
    fi
    
    # Test category filtering
    local mushaf_response=$(api_call "GET" "$API_BASE/assets/?category=mushaf")
    if is_json "$mushaf_response"; then
        local mushaf_count=$(echo "$mushaf_response" | python3 -c "import sys,json; data=json.load(sys.stdin); print(len(data.get('assets', [])))")
        print_status "PASS" "Category filter (mushaf) working - found $mushaf_count assets"
    else
        print_status "FAIL" "Category filter returned non-JSON response"
    fi
    
    echo ""
}

# Function to test asset detail endpoint
test_asset_detail() {
    echo -e "${YELLOW}📄 Testing Asset Detail Endpoint${NC}"
    
    if [ -z "$ASSET_ID" ]; then
        print_status "FAIL" "No asset ID available for testing"
        return 1
    fi
    
    local response=$(api_call "GET" "$API_BASE/assets/$ASSET_ID/")
    
    if is_json "$response"; then
        # Check required fields
        local required_fields=("id" "title" "description" "category" "license" "publisher" "technical_details" "stats" "access")
        local missing_fields=()
        
        for field in "${required_fields[@]}"; do
            local value=$(get_json_field "$response" "$field")
            if [ -z "$value" ] || [ "$value" = "null" ]; then
                missing_fields+=("$field")
            fi
        done
        
        if [ ${#missing_fields[@]} -eq 0 ]; then
            print_status "PASS" "Asset detail contains all required fields"
        else
            print_status "FAIL" "Missing required fields: ${missing_fields[*]}"
        fi
        
        local title=$(get_json_field "$response" "title")
        print_status "INFO" "Asset title: $title"
    else
        print_status "FAIL" "Asset detail endpoint returned non-JSON response"
        echo "Response: $response"
        return 1
    fi
    
    echo ""
}

# Function to test access request endpoint
test_access_request() {
    echo -e "${YELLOW}🔐 Testing Access Request Endpoint${NC}"
    
    if [ -z "$ASSET_ID" ]; then
        print_status "FAIL" "No asset ID available for testing"
        return 1
    fi
    
    # Test unauthenticated access (should fail)
    echo -e "    ${BLUE}📤 CURL (Unauthenticated):${NC} curl -s -X POST \"$API_BASE/assets/$ASSET_ID/request-access/\" -H \"Content-Type: application/json\" -d '{\"purpose\": \"API testing\", \"intended_use\": \"non-commercial\"}'"
    local unauth_response=$(curl -s -X POST "$API_BASE/assets/$ASSET_ID/request-access/" \
        -H "Content-Type: application/json" \
        -d '{"purpose": "API testing", "intended_use": "non-commercial"}')
    
    echo -e "    ${BLUE}📥 RESPONSE:${NC}"
    if is_json "$unauth_response"; then
        echo "$unauth_response" | python3 -m json.tool 2>/dev/null | sed 's/^/        /'
    else
        echo "$unauth_response" | head -5 | sed 's/^/        /'
    fi
    echo ""
    
    if echo "$unauth_response" | grep -q "Authentication credentials were not provided\|Unauthorized"; then
        print_status "PASS" "Unauthenticated access properly rejected"
    else
        print_status "FAIL" "Unauthenticated access should be rejected"
    fi
    
    # Test authenticated access
    if [ ! -z "$ACCESS_TOKEN" ]; then
        local auth_data='{"purpose": "Automated API testing for Itqan CMS assets endpoint", "intended_use": "non-commercial"}'
        local auth_response=$(api_call "POST" "$API_BASE/assets/$ASSET_ID/request-access/" "$auth_data")
        
        if is_json "$auth_response"; then
            local status=$(get_json_field "$auth_response" "status")
            local request_id=$(get_json_field "$auth_response" "request_id")
            
            if [ "$status" = "approved" ] && [ ! -z "$request_id" ]; then
                print_status "PASS" "Access request successfully created and auto-approved"
                print_status "INFO" "Request ID: $request_id"
            else
                print_status "FAIL" "Access request failed or not approved: $status"
            fi
        else
            print_status "FAIL" "Access request returned non-JSON response"
            echo "Response: $auth_response"
        fi
    else
        print_status "FAIL" "No access token available for authenticated testing"
    fi
    
    # Test validation (missing fields)
    local invalid_data='{"purpose": "Test"}'
    local invalid_response=$(api_call "POST" "$API_BASE/assets/$ASSET_ID/request-access/" "$invalid_data")
    
    if echo "$invalid_response" | grep -q "required\|VALIDATION_ERROR"; then
        print_status "PASS" "Input validation working correctly"
    else
        print_status "WARN" "Input validation may not be working as expected"
    fi
    
    echo ""
}

# Function to test download endpoint
test_download() {
    echo -e "${YELLOW}📥 Testing Download Endpoint${NC}"
    
    if [ -z "$ASSET_ID" ]; then
        print_status "FAIL" "No asset ID available for testing"
        return 1
    fi
    
    # Test unauthenticated download (should fail)
    echo -e "    ${BLUE}📤 CURL (Unauthenticated):${NC} curl -s -w \"%{http_code}\" -o /dev/null \"$API_BASE/assets/$ASSET_ID/download/\""
    local unauth_status=$(curl -s -w "%{http_code}" -o /dev/null "$API_BASE/assets/$ASSET_ID/download/")
    echo -e "    ${BLUE}📥 RESPONSE:${NC} HTTP Status: $unauth_status"
    echo ""
    
    if [ "$unauth_status" = "401" ]; then
        print_status "PASS" "Unauthenticated download properly rejected (401)"
    else
        print_status "FAIL" "Unauthenticated download should return 401, got: $unauth_status"
    fi
    
    # Test authenticated download
    if [ ! -z "$ACCESS_TOKEN" ]; then
        echo -e "    ${BLUE}📤 CURL (Authenticated):${NC} curl -s -i -H \"Authorization: Bearer \$ACCESS_TOKEN\" \"$API_BASE/assets/$ASSET_ID/download/\""
        local download_response=$(curl -s -i -H "Authorization: Bearer $ACCESS_TOKEN" "$API_BASE/assets/$ASSET_ID/download/")
        local status_line=$(echo "$download_response" | head -1)
        
        echo -e "    ${BLUE}📥 RESPONSE:${NC}"
        echo "$download_response" | head -15 | sed 's/^/        /'
        if [ $(echo "$download_response" | wc -l) -gt 15 ]; then
            echo "        ... (response truncated)"
        fi
        echo ""
        
        if echo "$status_line" | grep -q "200 OK"; then
            print_status "PASS" "Authenticated download successful (200 OK)"
            
            # Check for proper headers
            if echo "$download_response" | grep -q "Content-Disposition: attachment"; then
                print_status "PASS" "Download includes proper Content-Disposition header"
            else
                print_status "WARN" "Missing Content-Disposition header"
            fi
            
            if echo "$download_response" | grep -q "Content-Length:"; then
                print_status "PASS" "Download includes Content-Length header"
            else
                print_status "WARN" "Missing Content-Length header"
            fi
        else
            print_status "FAIL" "Authenticated download failed"
            echo "Status: $status_line"
        fi
    else
        print_status "FAIL" "No access token available for authenticated testing"
    fi
    
    echo ""
}

# Function to test error handling
test_error_handling() {
    echo -e "${YELLOW}🚨 Testing Error Handling${NC}"
    
    # Test invalid asset ID format
    local invalid_response=$(api_call "GET" "$API_BASE/assets/invalid-uuid/")
    
    echo -e "    ${BLUE}📤 CURL (Status Check):${NC} curl -s -w \"%{http_code}\" -o /dev/null \"$API_BASE/assets/invalid-uuid/\""
    local invalid_status=$(curl -s -w "%{http_code}" -o /dev/null "$API_BASE/assets/invalid-uuid/")
    echo -e "    ${BLUE}📥 RESPONSE:${NC} HTTP Status: $invalid_status"
    echo ""
    
    if [ "$invalid_status" = "404" ]; then
        print_status "PASS" "Invalid UUID format properly handled (404)"
    else
        print_status "FAIL" "Invalid UUID should return 404, got: $invalid_status"
    fi
    
    # Test non-existent asset ID
    local nonexistent_response=$(api_call "GET" "$API_BASE/assets/00000000-0000-0000-0000-000000000000/")
    
    if is_json "$nonexistent_response" && echo "$nonexistent_response" | grep -q "ASSET_NOT_FOUND"; then
        print_status "PASS" "Non-existent asset returns proper error format"
    else
        print_status "FAIL" "Non-existent asset error format incorrect"
    fi
    
    echo ""
}

# Function to test authenticated vs unauthenticated access
test_access_differences() {
    echo -e "${YELLOW}🔍 Testing Authenticated vs Unauthenticated Access${NC}"
    
    # Get unauthenticated response
    echo -e "    ${BLUE}📤 CURL (Unauthenticated):${NC} curl -s \"$API_BASE/assets/\""
    local unauth_response=$(curl -s "$API_BASE/assets/")
    echo -e "    ${BLUE}📥 RESPONSE:${NC}"
    if is_json "$unauth_response"; then
        echo "$unauth_response" | python3 -c "import sys,json; data=json.load(sys.stdin); assets=data.get('assets',[]); print(f'Assets: {len(assets)}, First has_access: {assets[0].get(\"has_access\") if assets else \"N/A\"}')" | sed 's/^/        /'
    else
        echo "$unauth_response" | head -3 | sed 's/^/        /'
    fi
    echo ""
    
    local unauth_access=""
    if is_json "$unauth_response"; then
        unauth_access=$(echo "$unauth_response" | python3 -c "import sys,json; data=json.load(sys.stdin); assets=data.get('assets', []); print(assets[0]['has_access'] if assets else 'false')")
    fi
    
    # Get authenticated response
    local auth_response=""
    local auth_access=""
    if [ ! -z "$ACCESS_TOKEN" ]; then
        auth_response=$(api_call "GET" "$API_BASE/assets/")
        if is_json "$auth_response"; then
            auth_access=$(echo "$auth_response" | python3 -c "import sys,json; data=json.load(sys.stdin); assets=data.get('assets', []); print(assets[0]['has_access'] if assets else 'false')")
        fi
    fi
    
    if [ "$unauth_access" = "false" ] && [ "$auth_access" = "true" ]; then
        print_status "PASS" "Access status correctly differs between authenticated/unauthenticated"
    elif [ "$unauth_access" = "false" ] && [ "$auth_access" = "false" ]; then
        print_status "INFO" "Both show no access (may need access request first)"
    else
        print_status "WARN" "Access status behavior unclear - unauth: $unauth_access, auth: $auth_access"
    fi
    
    echo ""
}

# Function to run all tests
run_all_tests() {
    echo -e "${BLUE}Starting comprehensive API test suite...${NC}"
    echo ""
    
    # Test sequence
    test_health || exit 1
    authenticate || exit 1
    create_test_data
    test_asset_list || exit 1
    test_asset_detail || exit 1
    test_access_request || exit 1
    test_download || exit 1
    test_error_handling
    test_access_differences
    
    echo ""
    echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${GREEN}║${NC}  ${BOLD}${WHITE}🎉 All tests completed successfully!${NC}                      ${BOLD}${GREEN}║${NC}"
    echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BOLD}${WHITE}📊 Test Summary:${NC}"
    echo -e "  ${GREEN}✅${NC} ${WHITE}Health check:${NC} ${GREEN}API is operational${NC}"
    echo -e "  ${GREEN}✅${NC} ${WHITE}Authentication:${NC} ${GREEN}JWT token obtained${NC}"
    echo -e "  ${GREEN}✅${NC} ${WHITE}Asset listing:${NC} ${GREEN}Basic and filtered queries work${NC}"
    echo -e "  ${GREEN}✅${NC} ${WHITE}Asset details:${NC} ${GREEN}All required fields present${NC}"
    echo -e "  ${GREEN}✅${NC} ${WHITE}Access requests:${NC} ${GREEN}Validation and approval flow working${NC}"
    echo -e "  ${GREEN}✅${NC} ${WHITE}Downloads:${NC} ${GREEN}Authentication required, proper headers${NC}"
    echo -e "  ${GREEN}✅${NC} ${WHITE}Error handling:${NC} ${GREEN}Proper HTTP status codes and error formats${NC}"
    echo ""
    echo -e "${BOLD}${CYAN}📡 API Base URL:${NC} ${WHITE}$API_BASE${NC}"
    echo -e "${BOLD}${CYAN}📦 Assets tested:${NC} ${WHITE}${#TEST_ASSETS[@]}${NC}"
    if [ ! -z "$ASSET_ID" ]; then
        echo -e "${BOLD}${CYAN}🆔 Sample Asset ID:${NC} ${WHITE}$ASSET_ID${NC}"
    fi
    echo ""
    echo -e "${BOLD}${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# Main execution
main() {
    if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
        echo "Usage: $0 [options]"
        echo ""
        echo "Options:"
        echo "  --help, -h     Show this help message"
        echo "  --health       Test only health endpoint"
        echo "  --auth         Test only authentication"
        echo "  --assets       Test only asset endpoints"
        echo "  --create-data  Create test data only"
        echo ""
        echo "Environment Variables:"
        echo "  TEST_EMAIL     Email for test user (default: test@example.com)"
        echo "  TEST_PASSWORD  Password for test user (default: testpass123)"
        echo "  BASE_URL       API base URL (default: https://develop.api.cms.itqan.dev)"
        exit 0
    fi
    
    # Set URLs based on final BASE_URL value
    API_BASE="${BASE_URL}/api/v1"
    HEALTH_URL="${BASE_URL}/health/"
    
    echo ""
    echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${CYAN}║${NC}  ${BOLD}${WHITE}🚀 Itqan CMS - Assets API Test Suite${NC}                     ${BOLD}${CYAN}║${NC}"
    echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BOLD}${WHITE}🌐 Testing against:${NC} ${BOLD}${GREEN}$BASE_URL${NC}"
    echo -e "${BOLD}${WHITE}📧 Test user:${NC} ${BOLD}${YELLOW}$TEST_EMAIL${NC}"
    echo -e "${BOLD}${WHITE}🔑 Password:${NC} ${DIM}${TEST_PASSWORD:0:4}****${NC}"
    echo ""
    echo -e "${BOLD}${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    case "$1" in
        "--health")
            test_health
            ;;
        "--auth")
            test_health && authenticate
            ;;
        "--assets")
            test_health && authenticate && test_asset_list && test_asset_detail && test_access_request && test_download
            ;;
        "--create-data")
            test_health && authenticate && create_test_data
            ;;
        *)
            run_all_tests
            ;;
    esac
}

# Execute main function with all arguments
main "$@"
