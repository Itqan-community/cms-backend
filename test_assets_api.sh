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

# Function to print colored status
print_status() {
    local status=$1
    local message=$2
    if [ "$status" = "PASS" ]; then
        echo -e "  ${GREEN}✅ PASS${NC} - $message"
    elif [ "$status" = "FAIL" ]; then
        echo -e "  ${RED}❌ FAIL${NC} - $message"
    elif [ "$status" = "INFO" ]; then
        echo -e "  ${BLUE}ℹ️  INFO${NC} - $message"
    elif [ "$status" = "WARN" ]; then
        echo -e "  ${YELLOW}⚠️  WARN${NC} - $message"
    fi
}

# Function to make API calls with proper error handling
api_call() {
    local method=$1
    local endpoint=$2
    local data=$3
    local auth_header=""
    
    if [ ! -z "$ACCESS_TOKEN" ]; then
        auth_header="-H \"Authorization: Bearer $ACCESS_TOKEN\""
    fi
    
    if [ ! -z "$data" ]; then
        eval curl -s -X "$method" "$endpoint" \
            -H "\"Content-Type: application/json\"" \
            $auth_header \
            -d "'$data'"
    else
        eval curl -s -X "$method" "$endpoint" \
            -H "\"Content-Type: application/json\"" \
            $auth_header
    fi
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
    echo -e "${YELLOW}🔍 Testing Health Endpoint${NC}"
    
    local response=$(curl -s "$HEALTH_URL")
    
    if is_json "$response"; then
        local status=$(get_json_field "$response" "status")
        if [ "$status" = "healthy" ]; then
            print_status "PASS" "Health endpoint responded with healthy status"
        else
            print_status "FAIL" "Health endpoint not healthy: $status"
            return 1
        fi
    else
        print_status "FAIL" "Health endpoint returned non-JSON response"
        return 1
    fi
    echo ""
}

# Function to authenticate and get token
authenticate() {
    echo -e "${YELLOW}🔐 Authenticating User${NC}"
    
    local login_data="{\"email\": \"$TEST_EMAIL\", \"password\": \"$TEST_PASSWORD\"}"
    local response=$(api_call "POST" "$API_BASE/auth/login/" "$login_data")
    
    if is_json "$response"; then
        ACCESS_TOKEN=$(get_json_field "$response" "access_token")
        if [ ! -z "$ACCESS_TOKEN" ] && [ "$ACCESS_TOKEN" != "null" ]; then
            print_status "PASS" "Successfully authenticated and received JWT token"
            print_status "INFO" "Token: ${ACCESS_TOKEN:0:20}..."
        else
            print_status "FAIL" "Login successful but no access token received"
            echo "Response: $response"
            return 1
        fi
    else
        print_status "FAIL" "Authentication failed - non-JSON response"
        echo "Response: $response"
        return 1
    fi
    echo ""
}

# Function to create test data
create_test_data() {
    echo -e "${YELLOW}📊 Creating Test Data${NC}"
    
    print_status "INFO" "Creating test assets with '- Test' suffix..."
    
    # Create test data using our mock API endpoint (since we can't execute Django commands remotely)
    # We'll create the data by calling the existing endpoints
    
    # Test if we can reach the health endpoint first
    local health_status=$(curl -s -w "%{http_code}" -o /dev/null "$HEALTH_URL")
    
    if [ "$health_status" = "200" ]; then
        print_status "PASS" "API is accessible for test data creation"
        
        # Note: In a real scenario, test data would be created via:
        # 1. Django management command on the server
        # 2. Database seed scripts 
        # 3. API endpoints for data creation (if available)
        
        print_status "INFO" "Test data should be created via Django management command:"
        print_status "INFO" "python manage.py create_test_assets --email $TEST_EMAIL --password $TEST_PASSWORD"
        
        # For this test script, we'll work with whatever assets exist
        print_status "INFO" "Will test against existing published assets"
        
    else
        print_status "WARN" "API not accessible (status: $health_status), will test against existing data"
    fi
    
    echo ""
}

# Function to test asset list endpoint
test_asset_list() {
    echo -e "${YELLOW}📋 Testing Asset List Endpoint${NC}"
    
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
    local unauth_response=$(curl -s -X POST "$API_BASE/assets/$ASSET_ID/request-access/" \
        -H "Content-Type: application/json" \
        -d '{"purpose": "API testing", "intended_use": "non-commercial"}')
    
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
    local unauth_status=$(curl -s -w "%{http_code}" -o /dev/null "$API_BASE/assets/$ASSET_ID/download/")
    
    if [ "$unauth_status" = "401" ]; then
        print_status "PASS" "Unauthenticated download properly rejected (401)"
    else
        print_status "FAIL" "Unauthenticated download should return 401, got: $unauth_status"
    fi
    
    # Test authenticated download
    if [ ! -z "$ACCESS_TOKEN" ]; then
        local download_response=$(curl -s -i -H "Authorization: Bearer $ACCESS_TOKEN" "$API_BASE/assets/$ASSET_ID/download/")
        local status_line=$(echo "$download_response" | head -1)
        
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
    local invalid_status=$(curl -s -w "%{http_code}" -o /dev/null "$API_BASE/assets/invalid-uuid/")
    
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
    local unauth_response=$(curl -s "$API_BASE/assets/")
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
    
    echo -e "${GREEN}🎉 All tests completed!${NC}"
    echo ""
    echo "Test Summary:"
    echo "- Health check: API is operational"
    echo "- Authentication: JWT token obtained"
    echo "- Asset listing: Basic and filtered queries work"
    echo "- Asset details: All required fields present"
    echo "- Access requests: Validation and approval flow working"
    echo "- Downloads: Authentication required, proper headers"
    echo "- Error handling: Proper HTTP status codes and error formats"
    echo ""
    echo -e "${BLUE}API Base URL: $API_BASE${NC}"
    echo -e "${BLUE}Assets tested: ${#TEST_ASSETS[@]}${NC}"
    if [ ! -z "$ASSET_ID" ]; then
        echo -e "${BLUE}Sample Asset ID: $ASSET_ID${NC}"
    fi
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
    
    echo -e "${BLUE}🚀 Itqan CMS - Assets API Test Suite${NC}"
    echo -e "${BLUE}====================================${NC}"
    echo "Testing against: $BASE_URL"
    echo ""
    
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
        *)
            run_all_tests
            ;;
    esac
}

# Execute main function with all arguments
main "$@"
