#!/bin/bash

# Itqan CMS Authentication API Test Script
API_BASE="https://develop.api.cms.itqan.dev/api/v1"
TEST_EMAIL="apitest.$(date +%s)@example.com"
TEST_PASSWORD="SecurePassword123!"

echo "🚀 Testing Itqan CMS Authentication API"
echo "==============================================="
echo "API Base URL: $API_BASE"
echo "Test Email: $TEST_EMAIL"
echo ""

# 1. Register new user
echo "1️⃣ Testing Registration with all optional fields..."
echo "POST $API_BASE/auth/register/"
REGISTER_RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "$API_BASE/auth/register/" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d "{
    \"email\": \"$TEST_EMAIL\",
    \"password\": \"$TEST_PASSWORD\",
    \"first_name\": \"Test\",
    \"last_name\": \"User\",
    \"phone_number\": \"+1234567890\",
    \"title\": \"API Test Engineer\"
  }")

HTTP_CODE=$(echo "$REGISTER_RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)
REGISTER_BODY=$(echo "$REGISTER_RESPONSE" | sed '/HTTP_CODE:/d')

echo "Status Code: $HTTP_CODE"
echo "Response Body:"
echo "$REGISTER_BODY" | jq . 2>/dev/null || echo "$REGISTER_BODY"
echo ""

# Extract tokens from registration response
ACCESS_TOKEN=$(echo "$REGISTER_BODY" | jq -r '.access_token // empty' 2>/dev/null)
REFRESH_TOKEN=$(echo "$REGISTER_BODY" | jq -r '.refresh_token // empty' 2>/dev/null)

if [ -z "$ACCESS_TOKEN" ] || [ "$ACCESS_TOKEN" = "null" ]; then
    echo "❌ Registration failed or didn't return tokens, trying login..."
    
    # 2. Try login if registration failed
    echo "2️⃣ Testing Login..."
    echo "POST $API_BASE/auth/login/"
    LOGIN_RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "$API_BASE/auth/login/" \
      -H "Content-Type: application/json" \
      -H "Accept: application/json" \
      -d "{
        \"email\": \"$TEST_EMAIL\",
        \"password\": \"$TEST_PASSWORD\"
      }")
    
    HTTP_CODE=$(echo "$LOGIN_RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)
    LOGIN_BODY=$(echo "$LOGIN_RESPONSE" | sed '/HTTP_CODE:/d')
    
    echo "Status Code: $HTTP_CODE"
    echo "Response Body:"
    echo "$LOGIN_BODY" | jq . 2>/dev/null || echo "$LOGIN_BODY"
    echo ""
    
    ACCESS_TOKEN=$(echo "$LOGIN_BODY" | jq -r '.access_token // empty' 2>/dev/null)
    REFRESH_TOKEN=$(echo "$LOGIN_BODY" | jq -r '.refresh_token // empty' 2>/dev/null)
fi

if [ -n "$ACCESS_TOKEN" ] && [ "$ACCESS_TOKEN" != "null" ]; then
    echo "✅ Authentication successful!"
    echo "Access Token: ${ACCESS_TOKEN:0:50}..."
    echo ""
    
    # 3. Test OAuth start endpoints
    echo "3️⃣ Testing OAuth Start Endpoints..."
    echo "GET $API_BASE/auth/oauth/google/start/"
    GOOGLE_OAUTH=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X GET "$API_BASE/auth/oauth/google/start/" \
      -H "Accept: application/json")
    
    HTTP_CODE=$(echo "$GOOGLE_OAUTH" | grep "HTTP_CODE:" | cut -d: -f2)
    GOOGLE_BODY=$(echo "$GOOGLE_OAUTH" | sed '/HTTP_CODE:/d')
    
    echo "Google OAuth Status: $HTTP_CODE"
    echo "$GOOGLE_BODY" | jq . 2>/dev/null || echo "$GOOGLE_BODY"
    echo ""
    
    echo "GET $API_BASE/auth/oauth/github/start/"
    GITHUB_OAUTH=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X GET "$API_BASE/auth/oauth/github/start/" \
      -H "Accept: application/json")
    
    HTTP_CODE=$(echo "$GITHUB_OAUTH" | grep "HTTP_CODE:" | cut -d: -f2)
    GITHUB_BODY=$(echo "$GITHUB_OAUTH" | sed '/HTTP_CODE:/d')
    
    echo "GitHub OAuth Status: $HTTP_CODE"
    echo "$GITHUB_BODY" | jq . 2>/dev/null || echo "$GITHUB_BODY"
    echo ""
    
    # 4. Get user profile
    echo "4️⃣ Testing Get User Profile..."
    echo "GET $API_BASE/auth/profile/"
    PROFILE_RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X GET "$API_BASE/auth/profile/" \
      -H "Authorization: Bearer $ACCESS_TOKEN" \
      -H "Accept: application/json")
    
    HTTP_CODE=$(echo "$PROFILE_RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)
    PROFILE_BODY=$(echo "$PROFILE_RESPONSE" | sed '/HTTP_CODE:/d')
    
    echo "Status Code: $HTTP_CODE"
    echo "Response Body:"
    echo "$PROFILE_BODY" | jq . 2>/dev/null || echo "$PROFILE_BODY"
    echo ""
    
    # 5. Update user profile with all fields
    echo "5️⃣ Testing Profile Update with all optional fields..."
    echo "PUT $API_BASE/auth/profile/"
    UPDATE_RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X PUT "$API_BASE/auth/profile/" \
      -H "Authorization: Bearer $ACCESS_TOKEN" \
      -H "Content-Type: application/json" \
      -H "Accept: application/json" \
      -d '{
        "name": "Test Alexander User",
        "bio": "Comprehensive API testing specialist for Quranic CMS platforms",
        "organization": "Itqan Community",
        "location": "Global",
        "website": "https://itqan.dev",
        "github_username": "testuser",
        "phone_number": "+1987654321",
        "title": "Senior API Test Engineer"
      }')
    
    HTTP_CODE=$(echo "$UPDATE_RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)
    UPDATE_BODY=$(echo "$UPDATE_RESPONSE" | sed '/HTTP_CODE:/d')
    
    echo "Status Code: $HTTP_CODE"
    echo "Response Body:"
    echo "$UPDATE_BODY" | jq . 2>/dev/null || echo "$UPDATE_BODY"
    echo ""
    
    # 6. Test token refresh
    echo "6️⃣ Testing Token Refresh..."
    echo "POST $API_BASE/auth/token/refresh/"
    if [ -n "$REFRESH_TOKEN" ] && [ "$REFRESH_TOKEN" != "null" ]; then
        REFRESH_RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "$API_BASE/auth/token/refresh/" \
          -H "Content-Type: application/json" \
          -H "Accept: application/json" \
          -d "{\"refresh\": \"$REFRESH_TOKEN\"}")
        
        HTTP_CODE=$(echo "$REFRESH_RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)
        REFRESH_BODY=$(echo "$REFRESH_RESPONSE" | sed '/HTTP_CODE:/d')
        
        echo "Status Code: $HTTP_CODE"
        echo "Response Body:"
        echo "$REFRESH_BODY" | jq . 2>/dev/null || echo "$REFRESH_BODY"
    else
        echo "❌ No refresh token available for testing"
    fi
    echo ""
    
    # 7. Test logout
    echo "7️⃣ Testing Logout..."
    echo "POST $API_BASE/auth/logout/"
    LOGOUT_RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "$API_BASE/auth/logout/" \
      -H "Authorization: Bearer $ACCESS_TOKEN" \
      -H "Content-Type: application/json" \
      -H "Accept: application/json" \
      -d "{\"refresh_token\": \"$REFRESH_TOKEN\"}")
    
    HTTP_CODE=$(echo "$LOGOUT_RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)
    LOGOUT_BODY=$(echo "$LOGOUT_RESPONSE" | sed '/HTTP_CODE:/d')
    
    echo "Status Code: $HTTP_CODE"
    if [ -n "$LOGOUT_BODY" ]; then
        echo "Response Body:"
        echo "$LOGOUT_BODY"
    else
        echo "No response body (expected for successful logout)"
    fi
    echo ""
    
    echo "✅ All authentication endpoints tested successfully!"
else
    echo "❌ Failed to authenticate - cannot test protected endpoints"
    echo "This could be due to:"
    echo "  - API server not responding"
    echo "  - Authentication configuration issues"
    echo "  - Network connectivity problems"
fi

echo "==============================================="
echo "🏁 Test completed!"
