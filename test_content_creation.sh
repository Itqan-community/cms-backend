#!/bin/bash

# Comprehensive Content Creation Test Script
# Tests JWT authentication and creates content for each model

BASE_URL="http://127.0.0.1:8000"
API_BASE="$BASE_URL/api/v1"

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

echo -e "${BLUE}=== ITQAN CMS - CONTENT CREATION TEST ===${NC}"
echo "Testing JWT authentication and content creation for all models"
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

# Wait for server to be ready
echo "Waiting for server to be ready..."
sleep 5

# Step 1: Create a test user and get JWT token
echo -e "${BLUE}=== Step 1: Authentication Setup ===${NC}"

# Create test credentials
TEST_EMAIL="test_admin@cms.itqan.dev"
TEST_PASSWORD="TestPassword123!"

# First, try to create a test user (may fail if user exists)
echo "Creating test user..."
curl -s -X POST "$API_BASE/auth/register/" \
  -H "Content-Type: application/json" \
  -d "{
    \"email\": \"$TEST_EMAIL\",
    \"password\": \"$TEST_PASSWORD\",
    \"first_name\": \"Test\",
    \"last_name\": \"Admin\",
    \"username\": \"testadmin\"
  }" > /dev/null

# Get JWT token
echo "Obtaining JWT token..."
JWT_RESPONSE=$(curl -s -X POST "$API_BASE/auth/token/" \
  -H "Content-Type: application/json" \
  -d "{
    \"email\": \"$TEST_EMAIL\",
    \"password\": \"$TEST_PASSWORD\"
  }")

# Extract access token
ACCESS_TOKEN=$(echo $JWT_RESPONSE | grep -o '"access":"[^"]*"' | cut -d'"' -f4)

if [[ -z "$ACCESS_TOKEN" ]]; then
    echo -e "${RED}❌ Failed to obtain JWT token${NC}"
    echo "Response: $JWT_RESPONSE"
    echo ""
    echo "Trying with admin credentials..."
    
    # Try with admin credentials
    ADMIN_JWT_RESPONSE=$(curl -s -X POST "$API_BASE/auth/token/" \
      -H "Content-Type: application/json" \
      -d "{
        \"email\": \"admin@localhost\",
        \"password\": \"ItqanCMS2024!\"
      }")
    
    ACCESS_TOKEN=$(echo $ADMIN_JWT_RESPONSE | grep -o '"access":"[^"]*"' | cut -d'"' -f4)
    
    if [[ -z "$ACCESS_TOKEN" ]]; then
        echo -e "${RED}❌ Failed to obtain JWT token with admin credentials${NC}"
        echo "Response: $ADMIN_JWT_RESPONSE"
        exit 1
    fi
fi

echo -e "${GREEN}✅ JWT Token obtained successfully${NC}"
echo "Token: ${ACCESS_TOKEN:0:20}..."
echo ""

# Set authorization header
AUTH_HEADER="Authorization: Bearer $ACCESS_TOKEN"

# Step 2: Test token validation
run_test "JWT Token Validation" \
    "curl -s -H '$AUTH_HEADER' '$API_BASE/auth/token/verify/' -d '{\"token\":\"$ACCESS_TOKEN\"}' -H 'Content-Type: application/json'" \
    "200"

echo -e "${BLUE}=== Step 2: Creating Test Content for Each Model ===${NC}"

# Model 1: Publishing Organization
echo -e "${BLUE}--- Publishing Organization ---${NC}"
ORG_DATA='{
  "name": "Test Quranic Institute",
  "slug": "test-quranic-institute",
  "summary": "A test organization for Quranic content",
  "description": "This is a test publishing organization created via API",
  "bio": "Dedicated to providing high-quality Quranic content",
  "location": "Test City",
  "website": "https://test-institute.example.com",
  "verified": false,
  "social_links": {"twitter": "@testinstitute"},
  "contact_email": "contact@test-institute.example.com"
}'

ORG_RESPONSE=$(curl -s -X POST "$API_BASE/publishers/" \
  -H "Content-Type: application/json" \
  -H "$AUTH_HEADER" \
  -d "$ORG_DATA")

ORG_ID=$(echo $ORG_RESPONSE | grep -o '"id":[0-9]*' | cut -d':' -f2)

run_test "Create Publishing Organization" \
    "curl -s -X POST '$API_BASE/publishers/' -H 'Content-Type: application/json' -H '$AUTH_HEADER' -d '$ORG_DATA'" \
    "201"

# Model 2: License
echo -e "${BLUE}--- License ---${NC}"
LICENSE_DATA='{
  "code": "test-cc0",
  "name": "Test Creative Commons Zero",
  "name_en": "Test Creative Commons Zero",
  "name_ar": "رخصة المشاع الإبداعي صفر تجريبية",
  "short_name": "Test CC0",
  "description": "Test license for public domain content",
  "description_en": "Test license for public domain content",
  "description_ar": "رخصة تجريبية للمحتوى في المجال العام",
  "url": "https://creativecommons.org/publicdomain/zero/1.0/",
  "permissions": ["commercial", "modify", "distribute"],
  "conditions": [],
  "limitations": [],
  "is_default": false
}'

run_test "Create License" \
    "curl -s -X POST '$API_BASE/licenses/' -H 'Content-Type: application/json' -H '$AUTH_HEADER' -d '$LICENSE_DATA'" \
    "201"

# Model 3: Resource
echo -e "${BLUE}--- Resource ---${NC}"
if [[ -n "$ORG_ID" ]]; then
    RESOURCE_DATA="{
      \"publishing_organization\": $ORG_ID,
      \"name\": \"Test Quran Recitation Dataset\",
      \"slug\": \"test-quran-recitation-dataset\",
      \"description\": \"A test dataset containing Quranic recitation data\",
      \"category\": \"recitation\",
      \"status\": \"ready\",
      \"default_license\": 1
    }"
    
    run_test "Create Resource" \
        "curl -s -X POST '$API_BASE/resources/' -H 'Content-Type: application/json' -H '$AUTH_HEADER' -d '$RESOURCE_DATA'" \
        "201"
fi

# Model 4: Resource Version
echo -e "${BLUE}--- Resource Version ---${NC}"
RESOURCE_VERSION_DATA='{
  "resource": 1,
  "name": "Test Recitation v1.0",
  "summary": "First version of test recitation dataset",
  "semvar": "1.0.0",
  "type": "json",
  "size_bytes": 1048576,
  "is_latest": true
}'

run_test "Create Resource Version" \
    "curl -s -X POST '$API_BASE/resource-versions/' -H 'Content-Type: application/json' -H '$AUTH_HEADER' -d '$RESOURCE_VERSION_DATA'" \
    "201"

# Model 5: Asset
echo -e "${BLUE}--- Asset ---${NC}"
ASSET_DATA='{
  "resource": 1,
  "name": "test-audio-file",
  "title": "Test Audio Recitation",
  "description": "A test audio file for Quranic recitation",
  "long_description": "This is a comprehensive test audio file containing sample Quranic recitation for testing purposes.",
  "category": "recitation",
  "license": 1,
  "file_size": "2.5 MB",
  "format": "MP3",
  "encoding": "UTF-8",
  "version": "1.0",
  "language": "ar",
  "download_count": 0,
  "view_count": 0
}'

run_test "Create Asset" \
    "curl -s -X POST '$API_BASE/assets/' -H 'Content-Type: application/json' -H '$AUTH_HEADER' -d '$ASSET_DATA'" \
    "201"

# Model 6: Asset Version
echo -e "${BLUE}--- Asset Version ---${NC}"
ASSET_VERSION_DATA='{
  "asset": 1,
  "resource_version": 1,
  "name": "Test Audio v1.0",
  "summary": "First version of test audio file",
  "size_bytes": 2621440
}'

run_test "Create Asset Version" \
    "curl -s -X POST '$API_BASE/asset-versions/' -H 'Content-Type: application/json' -H '$AUTH_HEADER' -d '$ASSET_VERSION_DATA'" \
    "201"

# Model 7: Distribution
echo -e "${BLUE}--- Distribution ---${NC}"
DISTRIBUTION_DATA='{
  "resource": 1,
  "format_type": "REST_JSON",
  "endpoint_url": "https://api.test-institute.example.com/recitation/v1",
  "version": "1.0",
  "access_config": {
    "authentication": {"required": true},
    "rate_limits": {"requests_per_minute": 100}
  },
  "metadata": {
    "response_format": "json",
    "pagination": true
  }
}'

run_test "Create Distribution" \
    "curl -s -X POST '$API_BASE/distributions/' -H 'Content-Type: application/json' -H '$AUTH_HEADER' -d '$DISTRIBUTION_DATA'" \
    "201"

# Model 8: Asset Access Request
echo -e "${BLUE}--- Asset Access Request ---${NC}"
ACCESS_REQUEST_DATA='{
  "developer_user": 1,
  "asset": 1,
  "developer_access_reason": "Testing API functionality for research purposes",
  "intended_use": "non-commercial"
}'

run_test "Create Asset Access Request" \
    "curl -s -X POST '$API_BASE/asset-access-requests/' -H 'Content-Type: application/json' -H '$AUTH_HEADER' -d '$ACCESS_REQUEST_DATA'" \
    "201"

# Model 9: Organization Member
echo -e "${BLUE}--- Organization Member ---${NC}"
if [[ -n "$ORG_ID" ]]; then
    MEMBER_DATA="{
      \"publishing_organization\": $ORG_ID,
      \"user\": 1,
      \"role\": \"manager\"
    }"
    
    run_test "Create Organization Member" \
        "curl -s -X POST '$API_BASE/organization-members/' -H 'Content-Type: application/json' -H '$AUTH_HEADER' -d '$MEMBER_DATA'" \
        "201"
fi

# Model 10: Usage Event
echo -e "${BLUE}--- Usage Event ---${NC}"
USAGE_EVENT_DATA='{
  "developer_user": 1,
  "usage_kind": "view",
  "subject_kind": "asset",
  "asset_id": 1,
  "metadata": {
    "asset_title": "Test Audio Recitation",
    "category": "recitation"
  },
  "ip_address": "127.0.0.1",
  "user_agent": "curl/test-script"
}'

run_test "Create Usage Event" \
    "curl -s -X POST '$API_BASE/usage-events/' -H 'Content-Type: application/json' -H '$AUTH_HEADER' -d '$USAGE_EVENT_DATA'" \
    "201"

# Model 11: Asset Access (usually created automatically when request is approved)
echo -e "${BLUE}--- Asset Access (Auto-created) ---${NC}"
echo "Asset Access is typically created automatically when an access request is approved."
echo "Testing the approval workflow..."

# Try to approve the access request (this should create an AssetAccess)
APPROVE_DATA='{"status": "approved", "admin_response": "Approved for testing"}'

run_test "Approve Asset Access Request" \
    "curl -s -X PATCH '$API_BASE/asset-access-requests/1/' -H 'Content-Type: application/json' -H '$AUTH_HEADER' -d '$APPROVE_DATA'" \
    "200"

echo -e "${BLUE}=== Step 3: Verification - List All Created Content ===${NC}"

# Verify created content by listing each model
run_test "List Publishing Organizations" \
    "curl -s -H '$AUTH_HEADER' '$API_BASE/publishers/'" \
    "200"

run_test "List Licenses" \
    "curl -s -H '$AUTH_HEADER' '$API_BASE/licenses/'" \
    "200"

run_test "List Resources" \
    "curl -s -H '$AUTH_HEADER' '$API_BASE/resources/'" \
    "200"

run_test "List Assets" \
    "curl -s -H '$AUTH_HEADER' '$API_BASE/assets/'" \
    "200"

run_test "List Distributions" \
    "curl -s -H '$AUTH_HEADER' '$API_BASE/distributions/'" \
    "200"

run_test "List Usage Events" \
    "curl -s -H '$AUTH_HEADER' '$API_BASE/usage-events/'" \
    "200"

echo -e "${BLUE}=== Final Test Summary ===${NC}"
echo "Total Tests: $TOTAL_TESTS"
echo -e "Passed: ${GREEN}$PASSED_TESTS${NC}"
echo -e "Failed: ${RED}$FAILED_TESTS${NC}"

if [[ $FAILED_TESTS -eq 0 ]]; then
    echo -e "${GREEN}🎉 ALL CONTENT CREATION TESTS PASSED!${NC}"
    echo -e "${GREEN}✅ Successfully created content for all models${NC}"
    echo -e "${GREEN}✅ JWT authentication working correctly${NC}"
    echo -e "${GREEN}✅ All API endpoints functional${NC}"
    exit 0
else
    echo -e "${RED}❌ Some content creation tests failed${NC}"
    echo -e "${YELLOW}📊 Success Rate: $(( PASSED_TESTS * 100 / TOTAL_TESTS ))%${NC}"
    exit 1
fi
