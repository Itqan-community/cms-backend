#!/bin/bash

# Production API Testing Script for https://api.cms.itqan.dev
# This script tests all available endpoints from the OpenAPI specification

BASE_URL="https://api.cms.itqan.dev"
API_VERSION="/api/v1"
TEST_RESULTS_FILE="production_api_test_results.txt"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to log results
log_result() {
    local endpoint="$1"
    local status="$2"
    local response_time="$3"
    local method="$4"
    local description="$5"
    
    if [[ $status -eq 200 || $status -eq 201 || $status -eq 204 || $status -eq 302 ]]; then
        color=$GREEN
        result="✅ PASS"
    elif [[ $status -eq 401 || $status -eq 403 ]]; then
        color=$YELLOW
        result="🔒 AUTH REQUIRED"
    else
        color=$RED
        result="❌ FAIL"
    fi
    
    printf "${color}%-10s${NC} | %-6s | %-50s | Status: %3s | Time: %6ss\n" \
        "$result" "$method" "$endpoint" "$status" "$response_time"
    
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
    
    local curl_cmd="curl -s -w '%{http_code}|%{time_total}' -X $method"
    
    if [[ -n "$headers" ]]; then
        curl_cmd="$curl_cmd $headers"
    fi
    
    if [[ -n "$data" && "$method" != "GET" ]]; then
        curl_cmd="$curl_cmd -d '$data'"
    fi
    
    curl_cmd="$curl_cmd ${BASE_URL}${API_VERSION}${endpoint}"
    
    local response=$(eval $curl_cmd)
    local status=$(echo "$response" | tail -c 14 | cut -d'|' -f1)
    local time=$(echo "$response" | tail -c 14 | cut -d'|' -f2)
    local body=$(echo "$response" | sed 's/|[^|]*$//')
    
    log_result "$endpoint" "$status" "$time" "$method" "$description"
    
    # Show response body for interesting endpoints
    if [[ $status -eq 200 && ${#body} -lt 500 ]]; then
        echo "Response: $body" | head -c 200
        echo "..."
    fi
    
    echo ""
}

# Initialize test results file
echo "Production API Test Results - $(date)" > "$TEST_RESULTS_FILE"
echo "Testing Base URL: ${BASE_URL}${API_VERSION}" >> "$TEST_RESULTS_FILE"
echo "============================================" >> "$TEST_RESULTS_FILE"

echo -e "${BLUE}🚀 Starting Production API Tests${NC}"
echo -e "${BLUE}Base URL: ${BASE_URL}${API_VERSION}${NC}"
echo ""

# System Endpoints (Public)
echo -e "${YELLOW}=== SYSTEM ENDPOINTS (Public) ===${NC}"
test_endpoint "GET" "/health" "Health check endpoint"
test_endpoint "GET" "/config" "Application configuration"

# Content Standards (Public)
echo -e "${YELLOW}=== CONTENT STANDARDS (Public) ===${NC}"
test_endpoint "GET" "/content-standards" "Content quality standards"

# Licenses (Public)
echo -e "${YELLOW}=== LICENSES (Public) ===${NC}"
test_endpoint "GET" "/licenses" "List all licenses"
test_endpoint "GET" "/licenses/cc0" "Get CC0 license details"
test_endpoint "GET" "/licenses/cc-by-4.0" "Get CC BY 4.0 license details"

# Assets (Public)
echo -e "${YELLOW}=== ASSETS (Public) ===${NC}"
test_endpoint "GET" "/assets" "List all assets"
test_endpoint "GET" "/assets?category=mushaf" "Filter assets by mushaf category"
test_endpoint "GET" "/assets?category=tafsir" "Filter assets by tafsir category"
test_endpoint "GET" "/assets?category=recitation" "Filter assets by recitation category"
test_endpoint "GET" "/assets?license_code=cc0" "Filter assets by CC0 license"
test_endpoint "GET" "/assets/1" "Get asset details for ID 1"
test_endpoint "GET" "/assets/2" "Get asset details for ID 2"
test_endpoint "GET" "/assets/999" "Test non-existent asset"

# Publishers (Public)
echo -e "${YELLOW}=== PUBLISHERS (Public) ===${NC}"
test_endpoint "GET" "/publishers/1" "Get publisher details for ID 1"
test_endpoint "GET" "/publishers/999" "Test non-existent publisher"

# Authentication Endpoints (No auth required for these)
echo -e "${YELLOW}=== AUTHENTICATION ENDPOINTS ===${NC}"
test_endpoint "POST" "/auth/register" "User registration" \
    '{"email":"test@example.com","password":"testpass123","first_name":"Test","last_name":"User"}' \
    '-H "Content-Type: application/json"'

test_endpoint "POST" "/auth/login" "User login" \
    '{"email":"invalid@example.com","password":"wrongpass"}' \
    '-H "Content-Type: application/json"'

test_endpoint "GET" "/auth/oauth/google/start" "Google OAuth start"
test_endpoint "GET" "/auth/oauth/github/start" "GitHub OAuth start"

test_endpoint "POST" "/auth/token/refresh" "Token refresh" \
    '{"refresh_token":"invalid_token"}' \
    '-H "Content-Type: application/json"'

# Protected Endpoints (These should return 401 without auth)
echo -e "${YELLOW}=== PROTECTED ENDPOINTS (Should require auth) ===${NC}"
test_endpoint "GET" "/auth/profile" "Get user profile (protected)"
test_endpoint "PUT" "/auth/profile" "Update user profile (protected)" \
    '{"name":"Updated Name"}' \
    '-H "Content-Type: application/json"'
test_endpoint "POST" "/auth/logout" "User logout (protected)"

test_endpoint "POST" "/assets/1/request-access" "Request asset access (protected)" \
    '{"purpose":"Testing","intended_use":"non-commercial"}' \
    '-H "Content-Type: application/json"'
test_endpoint "GET" "/assets/1/download" "Download asset (protected)"
test_endpoint "GET" "/resources/1/download" "Download resource (protected)"

# Test with invalid endpoints
echo -e "${YELLOW}=== INVALID ENDPOINTS ===${NC}"
test_endpoint "GET" "/invalid" "Non-existent endpoint"
test_endpoint "GET" "/assets/abc" "Invalid asset ID format"
test_endpoint "POST" "/assets" "Unsupported method on assets"

echo -e "${GREEN}🏁 Testing Complete!${NC}"
echo -e "${BLUE}Results saved to: $TEST_RESULTS_FILE${NC}"
echo ""
echo -e "${YELLOW}Summary:${NC}"
grep -c "✅ PASS" "$TEST_RESULTS_FILE" || echo "0" | xargs echo "✅ Passed:"
grep -c "🔒 AUTH REQUIRED" "$TEST_RESULTS_FILE" || echo "0" | xargs echo "🔒 Auth Required:"
grep -c "❌ FAIL" "$TEST_RESULTS_FILE" || echo "0" | xargs echo "❌ Failed:"
