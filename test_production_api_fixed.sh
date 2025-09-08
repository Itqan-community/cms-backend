#!/bin/bash

# Production API Testing Script for https://api.cms.itqan.dev
# This script tests all available endpoints with correct URL patterns

BASE_URL="https://api.cms.itqan.dev"
API_VERSION="/api/v1"
TEST_RESULTS_FILE="production_api_test_results_fixed.txt"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Function to log results
log_result() {
    local endpoint="$1"
    local status="$2"
    local response_time="$3"
    local method="$4"
    local description="$5"
    local response_preview="$6"
    
    if [[ $status -eq 200 || $status -eq 201 || $status -eq 204 ]]; then
        color=$GREEN
        result="✅ PASS"
    elif [[ $status -eq 302 ]]; then
        color=$PURPLE
        result="🔄 REDIRECT"
    elif [[ $status -eq 401 || $status -eq 403 ]]; then
        color=$YELLOW
        result="🔒 AUTH REQUIRED"
    elif [[ $status -eq 404 ]]; then
        color=$YELLOW
        result="❓ NOT FOUND"
    elif [[ $status -eq 500 ]]; then
        color=$RED
        result="💥 SERVER ERROR"
    else
        color=$RED
        result="❌ FAIL"
    fi
    
    printf "${color}%-15s${NC} | %-6s | %-50s | %3s | %6ss\n" \
        "$result" "$method" "$endpoint" "$status" "$response_time"
    
    # Show preview for successful responses
    if [[ $status -eq 200 && ${#response_preview} -gt 0 && ${#response_preview} -lt 200 ]]; then
        echo "    📄 Response: $response_preview"
    fi
    
    echo "[$method] $endpoint - Status: $status - Time: ${response_time}s - $description" >> "$TEST_RESULTS_FILE"
}

# Function to test endpoint
test_endpoint() {
    local method="$1"
    local endpoint="$2"
    local description="$3"
    local data="$4"
    local headers="$5"
    
    echo -e "${BLUE}Testing:${NC} $method $endpoint - $description"
    
    local curl_cmd="curl -s -w '|%{http_code}|%{time_total}'"
    
    if [[ -n "$headers" ]]; then
        curl_cmd="$curl_cmd $headers"
    fi
    
    if [[ -n "$data" && "$method" != "GET" ]]; then
        curl_cmd="$curl_cmd -X $method -d '$data'"
    else
        curl_cmd="$curl_cmd -X $method"
    fi
    
    curl_cmd="$curl_cmd $endpoint"
    
    local response=$(eval $curl_cmd)
    local status=$(echo "$response" | grep -o '|[0-9]*|[0-9.]*$' | sed 's/|//g' | cut -d'|' -f1)
    local time=$(echo "$response" | grep -o '|[0-9]*|[0-9.]*$' | sed 's/|//g' | cut -d'|' -f2)
    local body=$(echo "$response" | sed 's/|[0-9]*|[0-9.]*$//')
    
    # Get response preview
    local preview=""
    if [[ $status -eq 200 && ${#body} -lt 200 && ${#body} -gt 5 ]]; then
        preview=$(echo "$body" | tr -d '\n' | sed 's/  */ /g')
    fi
    
    log_result "$endpoint" "$status" "$time" "$method" "$description" "$preview"
    echo ""
}

# Initialize test results file
echo "Production API Test Results - $(date)" > "$TEST_RESULTS_FILE"
echo "Testing Base URL: $BASE_URL" >> "$TEST_RESULTS_FILE"
echo "============================================" >> "$TEST_RESULTS_FILE"

echo -e "${BLUE}🚀 Starting Production API Tests${NC}"
echo -e "${BLUE}Base URL: $BASE_URL${NC}"
echo -e "${BLUE}API Base: $BASE_URL$API_VERSION${NC}"
echo ""

# System Endpoints (Root level)
echo -e "${YELLOW}=== SYSTEM ENDPOINTS (Root Level) ===${NC}"
test_endpoint "GET" "$BASE_URL/health/" "Health check endpoint"
test_endpoint "GET" "$BASE_URL/openapi.yaml" "OpenAPI specification"

# Documentation endpoints
echo -e "${YELLOW}=== DOCUMENTATION ENDPOINTS ===${NC}"
test_endpoint "GET" "$BASE_URL$API_VERSION/docs/" "API documentation (Scalar)"
test_endpoint "GET" "$BASE_URL$API_VERSION/swagger/" "Swagger UI documentation"
test_endpoint "GET" "$BASE_URL$API_VERSION/redoc/" "ReDoc documentation"
test_endpoint "GET" "$BASE_URL$API_VERSION/schema/" "OpenAPI schema endpoint"

# Content Standards (Public)
echo -e "${YELLOW}=== CONTENT STANDARDS (Public) ===${NC}"
test_endpoint "GET" "$BASE_URL$API_VERSION/content-standards/" "Content quality standards"
test_endpoint "GET" "$BASE_URL$API_VERSION/content-standards/simple/" "Simple content standards"

# Assets (Public)
echo -e "${YELLOW}=== ASSETS (Public) ===${NC}"
test_endpoint "GET" "$BASE_URL$API_VERSION/assets/" "List all assets"
test_endpoint "GET" "$BASE_URL$API_VERSION/assets/?category=mushaf" "Filter assets by mushaf category"
test_endpoint "GET" "$BASE_URL$API_VERSION/assets/?category=tafsir" "Filter assets by tafsir category"
test_endpoint "GET" "$BASE_URL$API_VERSION/assets/?category=recitation" "Filter assets by recitation category"
test_endpoint "GET" "$BASE_URL$API_VERSION/assets/?license_code=cc0" "Filter assets by CC0 license"
test_endpoint "GET" "$BASE_URL$API_VERSION/assets/1/" "Get asset details for ID 1"
test_endpoint "GET" "$BASE_URL$API_VERSION/assets/999/" "Test non-existent asset"

# Publishers (Public)
echo -e "${YELLOW}=== PUBLISHERS (Public) ===${NC}"
test_endpoint "GET" "$BASE_URL$API_VERSION/publishers/" "List all publishers"
test_endpoint "GET" "$BASE_URL$API_VERSION/publishers/1/" "Get publisher details for ID 1"
test_endpoint "GET" "$BASE_URL$API_VERSION/publishers/999/" "Test non-existent publisher"

# Licenses (Public)
echo -e "${YELLOW}=== LICENSES (Public) ===${NC}"
test_endpoint "GET" "$BASE_URL$API_VERSION/licenses/" "List all licenses"
test_endpoint "GET" "$BASE_URL$API_VERSION/licenses/default/" "Get default license"
test_endpoint "GET" "$BASE_URL$API_VERSION/licenses/cc0/" "Get CC0 license details"
test_endpoint "GET" "$BASE_URL$API_VERSION/licenses/cc-by-4.0/" "Get CC BY 4.0 license details"

# Landing Page Endpoints (Public)
echo -e "${YELLOW}=== LANDING PAGE (Public) ===${NC}"
test_endpoint "GET" "$BASE_URL$API_VERSION/landing/statistics/" "Platform statistics"
test_endpoint "GET" "$BASE_URL$API_VERSION/landing/features/" "Platform features"
test_endpoint "GET" "$BASE_URL$API_VERSION/landing/recent-content/" "Recent content"

# JWT Authentication endpoints
echo -e "${YELLOW}=== JWT AUTHENTICATION ===${NC}"
test_endpoint "POST" "$BASE_URL$API_VERSION/auth/token/" "JWT token obtain" \
    '{"username":"admin","password":"wrong"}' \
    '-H "Content-Type: application/json"'
test_endpoint "POST" "$BASE_URL$API_VERSION/auth/token/refresh/" "JWT token refresh" \
    '{"refresh":"invalid_token"}' \
    '-H "Content-Type: application/json"'
test_endpoint "POST" "$BASE_URL$API_VERSION/auth/token/verify/" "JWT token verify" \
    '{"token":"invalid_token"}' \
    '-H "Content-Type: application/json"'

# Django-Allauth Authentication (under /api/v1/auth/)
echo -e "${YELLOW}=== DJANGO-ALLAUTH AUTHENTICATION ===${NC}"
test_endpoint "GET" "$BASE_URL/api/v1/auth/login/" "Allauth login form"
test_endpoint "GET" "$BASE_URL/api/v1/auth/signup/" "Allauth signup form"
test_endpoint "GET" "$BASE_URL/api/v1/auth/google/login/" "Google OAuth login"
test_endpoint "GET" "$BASE_URL/api/v1/auth/github/login/" "GitHub OAuth login"

# Search endpoints
echo -e "${YELLOW}=== SEARCH ENDPOINTS ===${NC}"
test_endpoint "GET" "$BASE_URL$API_VERSION/search/" "Search endpoint"

# Protected Endpoints (Should return 401/403 without auth)
echo -e "${YELLOW}=== PROTECTED ENDPOINTS (Should require auth) ===${NC}"
test_endpoint "POST" "$BASE_URL$API_VERSION/assets/1/request-access/" "Request asset access (protected)" \
    '{"purpose":"Testing","intended_use":"non-commercial"}' \
    '-H "Content-Type: application/json"'
test_endpoint "GET" "$BASE_URL$API_VERSION/assets/1/download/" "Download asset (protected)"
test_endpoint "GET" "$BASE_URL$API_VERSION/assets/1/access-status/" "Asset access status (protected)"

# Admin endpoints (should be protected)
echo -e "${YELLOW}=== ADMIN ENDPOINTS (Protected) ===${NC}"
test_endpoint "GET" "$BASE_URL$API_VERSION/users/" "List users (admin)"
test_endpoint "GET" "$BASE_URL$API_VERSION/roles/" "List roles (admin)"
test_endpoint "GET" "$BASE_URL$API_VERSION/resources/" "List resources (admin)"

# Test invalid endpoints
echo -e "${YELLOW}=== INVALID ENDPOINTS ===${NC}"
test_endpoint "GET" "$BASE_URL$API_VERSION/invalid/" "Non-existent endpoint"
test_endpoint "GET" "$BASE_URL$API_VERSION/assets/abc/" "Invalid asset ID format"
test_endpoint "POST" "$BASE_URL$API_VERSION/assets/" "Unsupported method on assets"

echo -e "${GREEN}🏁 Testing Complete!${NC}"
echo -e "${BLUE}Results saved to: $TEST_RESULTS_FILE${NC}"
echo ""
echo -e "${YELLOW}Summary:${NC}"

# Generate summary
total_tests=$(wc -l < "$TEST_RESULTS_FILE" | xargs echo)
total_tests=$((total_tests - 3)) # Subtract header lines

passed=$(grep -c "✅ PASS" "$TEST_RESULTS_FILE" 2>/dev/null || echo "0")
auth_required=$(grep -c "🔒 AUTH REQUIRED" "$TEST_RESULTS_FILE" 2>/dev/null || echo "0")
not_found=$(grep -c "❓ NOT FOUND" "$TEST_RESULTS_FILE" 2>/dev/null || echo "0")
server_error=$(grep -c "💥 SERVER ERROR" "$TEST_RESULTS_FILE" 2>/dev/null || echo "0")
redirects=$(grep -c "🔄 REDIRECT" "$TEST_RESULTS_FILE" 2>/dev/null || echo "0")
failed=$(grep -c "❌ FAIL" "$TEST_RESULTS_FILE" 2>/dev/null || echo "0")

echo -e "${GREEN}✅ Passed: $passed${NC}"
echo -e "${YELLOW}🔒 Auth Required: $auth_required${NC}"
echo -e "${YELLOW}❓ Not Found: $not_found${NC}"
echo -e "${RED}💥 Server Errors: $server_error${NC}"
echo -e "${PURPLE}🔄 Redirects: $redirects${NC}"
echo -e "${RED}❌ Failed: $failed${NC}"
echo -e "${BLUE}📊 Total Tests: $total_tests${NC}"
