#!/bin/bash

# Comprehensive API Testing Script for All 11 Models
# Test against local development server at 127.0.0.1:8000

BASE_URL="http://127.0.0.1:8000"
API_BASE="$BASE_URL/api/v1"
ADMIN_BASE="$BASE_URL/django-admin"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test tracking
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

echo -e "${BLUE}=== ITQAN CMS - COMPREHENSIVE MODEL API TESTING ===${NC}"
echo "Testing all 11 models from Django admin interface"
echo "Base URL: $BASE_URL"
echo "API Base: $API_BASE"
echo "$(date)"
echo ""

# Function to run a test
run_test() {
    local test_name="$1"
    local curl_cmd="$2"
    local expected_status="$3"
    
    echo -e "${YELLOW}Testing: $test_name${NC}"
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    
    # Execute curl and capture both status and response
    response=$(eval "$curl_cmd" 2>/dev/null)
    status_code=$(eval "$curl_cmd -w '%{http_code}' -o /dev/null -s" 2>/dev/null)
    
    if [[ "$status_code" == "$expected_status" ]]; then
        echo -e "${GREEN}✅ PASSED${NC} - Status: $status_code"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        if [[ "$response" != "" ]]; then
            echo "Response: $(echo $response | head -c 200)..."
        fi
    else
        echo -e "${RED}❌ FAILED${NC} - Expected: $expected_status, Got: $status_code"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        if [[ "$response" != "" ]]; then
            echo "Error Response: $(echo $response | head -c 300)..."
        fi
    fi
    echo ""
}

# Function to test CRUD operations for a model
test_model_crud() {
    local model_name="$1"
    local endpoint="$2"
    local create_data="$3"
    
    echo -e "${BLUE}=== Testing $model_name CRUD Operations ===${NC}"
    
    # 1. List (GET)
    run_test "$model_name - List All" \
        "curl -s '$API_BASE/$endpoint/'" \
        "200"
    
    # 2. Create (POST) - if create_data provided
    if [[ "$create_data" != "" ]]; then
        run_test "$model_name - Create New" \
            "curl -s -X POST '$API_BASE/$endpoint/' -H 'Content-Type: application/json' -d '$create_data'" \
            "201"
    fi
    
    # 3. Get specific item (if any exist)
    run_test "$model_name - Get First Item" \
        "curl -s '$API_BASE/$endpoint/1/'" \
        "200"
    
    # 4. Options (check allowed methods)
    run_test "$model_name - Options" \
        "curl -s -X OPTIONS '$API_BASE/$endpoint/'" \
        "200"
}

# Wait for server to be ready
echo "Waiting for server to be ready..."
sleep 5

# Test 1: Asset Access Requests
test_model_crud "Asset Access Requests" "asset-access-requests" \
    '{"developer_user": 1, "asset": 1, "developer_access_reason": "Testing API", "intended_use": "non-commercial"}'

# Test 2: Asset Accesses  
test_model_crud "Asset Accesses" "asset-accesses" ""

# Test 3: Asset Versions
test_model_crud "Asset Versions" "asset-versions" \
    '{"asset": 1, "resource_version": 1, "name": "Test Version", "summary": "Test version", "size_bytes": 1024}'

# Test 4: Assets
test_model_crud "Assets" "assets" \
    '{"resource": 1, "name": "Test Asset", "title": "Test Asset Title", "description": "Test description", "category": "recitation", "license": 1, "file_size": "1 MB", "format": "JSON", "version": "1.0", "language": "ar"}'

# Test 5: Distributions
test_model_crud "Distributions" "distributions" \
    '{"resource": 1, "format_type": "REST_JSON", "endpoint_url": "http://example.com/api", "version": "1.0"}'

# Test 6: Licenses  
test_model_crud "Licenses" "licenses" \
    '{"code": "test-license", "name": "Test License", "description": "Test license description", "icon_url": "", "url": "http://example.com"}'

# Test 7: Organization Members
test_model_crud "Organization Members" "organization-members" \
    '{"publishing_organization": 1, "user": 1, "role": "manager"}'

# Test 8: Publishing Organizations
test_model_crud "Publishing Organizations" "publishing-organizations" \
    '{"name": "Test Organization", "slug": "test-org", "summary": "Test organization summary", "description": "Test description"}'

# Test 9: Resource Versions
test_model_crud "Resource Versions" "resource-versions" \
    '{"resource": 1, "semvar": "1.0.1", "summary": "Test resource version", "file_url": ""}'

# Test 10: Resources
test_model_crud "Resources" "resources" \
    '{"publishing_organization": 1, "name": "Test Resource", "slug": "test-resource", "description": "Test resource description", "category": "recitation", "default_license": 1}'

# Test 11: Usage Events
test_model_crud "Usage Events" "usage-events" \
    '{"developer_user": 1, "usage_kind": "view", "subject_kind": "asset", "asset_id": 1}'

echo -e "${BLUE}=== Additional API Endpoint Tests ===${NC}"

# Test API Root
run_test "API Root" \
    "curl -s '$API_BASE/'" \
    "200"

# Test OpenAPI Schema
run_test "OpenAPI Schema" \
    "curl -s '$BASE_URL/api/schema/'" \
    "200"

# Test Django Admin Access
run_test "Django Admin Login Page" \
    "curl -s '$ADMIN_BASE/login/'" \
    "200"

# Test specific model admin pages
run_test "Assets Admin" \
    "curl -s '$ADMIN_BASE/content/asset/'" \
    "302"  # Redirect to login

run_test "Resources Admin" \
    "curl -s '$ADMIN_BASE/content/resource/'" \
    "302"  # Redirect to login

echo -e "${BLUE}=== Testing Model Relationships ===${NC}"

# Test nested relationships
run_test "Assets with Resource Filter" \
    "curl -s '$API_BASE/assets/?resource=1'" \
    "200"

run_test "Asset Versions for Asset" \
    "curl -s '$API_BASE/asset-versions/?asset=1'" \
    "200"

run_test "Resources by Organization" \
    "curl -s '$API_BASE/resources/?publishing_organization=1'" \
    "200"

run_test "Usage Events by User" \
    "curl -s '$API_BASE/usage-events/?developer_user=1'" \
    "200"

echo -e "${BLUE}=== Authentication Tests ===${NC}"

# Test protected endpoints without auth
run_test "Protected Endpoint - No Auth" \
    "curl -s '$API_BASE/assets/1/download/'" \
    "401"

# Test with invalid token
run_test "Protected Endpoint - Invalid Token" \
    "curl -s -H 'Authorization: Bearer invalid-token' '$API_BASE/assets/1/download/'" \
    "401"

echo -e "${BLUE}=== Content-Type Tests ===${NC}"

# Test JSON content type
run_test "JSON Content-Type" \
    "curl -s -H 'Accept: application/json' '$API_BASE/assets/'" \
    "200"

# Test pagination
run_test "Pagination Test" \
    "curl -s '$API_BASE/assets/?page=1&page_size=5'" \
    "200"

echo -e "${BLUE}=== Search and Filter Tests ===${NC}"

# Test search functionality
run_test "Asset Search" \
    "curl -s '$API_BASE/assets/?search=test'" \
    "200"

run_test "Resource Category Filter" \
    "curl -s '$API_BASE/resources/?category=recitation'" \
    "200"

run_test "License Filter" \
    "curl -s '$API_BASE/assets/?license=1'" \
    "200"

echo -e "${BLUE}=== Final Test Summary ===${NC}"
echo "Total Tests: $TOTAL_TESTS"
echo -e "Passed: ${GREEN}$PASSED_TESTS${NC}"
echo -e "Failed: ${RED}$FAILED_TESTS${NC}"

if [[ $FAILED_TESTS -eq 0 ]]; then
    echo -e "${GREEN}🎉 ALL TESTS PASSED!${NC}"
    exit 0
else
    echo -e "${RED}❌ Some tests failed. Check the output above.${NC}"
    exit 1
fi
