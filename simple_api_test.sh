#!/bin/bash

# Simple Production API Test for https://api.cms.itqan.dev
BASE_URL="https://api.cms.itqan.dev"

echo "=== Itqan CMS Production API Test Report ==="
echo "Date: $(date)"
echo "Base URL: $BASE_URL"
echo ""

# Function to test endpoint
test_endpoint() {
    local method="$1"
    local url="$2"
    local description="$3"
    local data="$4"
    
    printf "%-60s" "$description"
    
    if [[ -n "$data" ]]; then
        response=$(curl -s -w "%{http_code}" -X "$method" -H "Content-Type: application/json" -d "$data" "$url")
    else
        response=$(curl -s -w "%{http_code}" -X "$method" "$url")
    fi
    
    status_code="${response: -3}"
    body="${response%???}"
    
    case $status_code in
        200|201|204)
            echo "✅ $status_code"
            ;;
        302)
            echo "🔄 $status_code (Redirect)"
            ;;
        401|403)
            echo "🔒 $status_code (Auth Required)"
            ;;
        404)
            echo "❓ $status_code (Not Found)"
            ;;
        500)
            echo "💥 $status_code (Server Error)"
            ;;
        *)
            echo "❌ $status_code"
            ;;
    esac
}

echo "=== SYSTEM ENDPOINTS ==="
test_endpoint "GET" "$BASE_URL/health/" "Health check"
test_endpoint "GET" "$BASE_URL/openapi.yaml" "OpenAPI specification"

echo ""
echo "=== DOCUMENTATION ENDPOINTS ==="
test_endpoint "GET" "$BASE_URL/api/v1/docs/" "API documentation (Scalar)"
test_endpoint "GET" "$BASE_URL/api/v1/swagger/" "Swagger UI"
test_endpoint "GET" "$BASE_URL/api/v1/redoc/" "ReDoc UI"
test_endpoint "GET" "$BASE_URL/api/v1/schema/" "OpenAPI schema"

echo ""
echo "=== PUBLIC ENDPOINTS ==="
test_endpoint "GET" "$BASE_URL/api/v1/assets/" "List assets"
test_endpoint "GET" "$BASE_URL/api/v1/assets/1/" "Get asset #1"
test_endpoint "GET" "$BASE_URL/api/v1/publishers/" "List publishers"
test_endpoint "GET" "$BASE_URL/api/v1/publishers/1/" "Get publisher #1"
test_endpoint "GET" "$BASE_URL/api/v1/licenses/" "List licenses"
test_endpoint "GET" "$BASE_URL/api/v1/licenses/cc0/" "Get CC0 license"
test_endpoint "GET" "$BASE_URL/api/v1/content-standards/" "Content standards"
test_endpoint "GET" "$BASE_URL/api/v1/landing/statistics/" "Platform statistics"

echo ""
echo "=== AUTHENTICATION ENDPOINTS ==="
test_endpoint "POST" "$BASE_URL/api/v1/auth/token/" "JWT token obtain" '{"username":"test","password":"test"}'
test_endpoint "GET" "$BASE_URL/api/v1/auth/login/" "Django auth login"
test_endpoint "GET" "$BASE_URL/api/v1/auth/google/login/" "Google OAuth"
test_endpoint "GET" "$BASE_URL/api/v1/auth/github/login/" "GitHub OAuth"

echo ""
echo "=== PROTECTED ENDPOINTS ==="
test_endpoint "POST" "$BASE_URL/api/v1/assets/1/request-access/" "Request asset access" '{"purpose":"test","intended_use":"non-commercial"}'
test_endpoint "GET" "$BASE_URL/api/v1/assets/1/download/" "Download asset"
test_endpoint "GET" "$BASE_URL/api/v1/users/" "List users (admin)"
test_endpoint "GET" "$BASE_URL/api/v1/roles/" "List roles (admin)"

echo ""
echo "=== TEST SUMMARY ==="
echo "✅ = Working correctly"
echo "🔄 = Redirect (likely working)"
echo "🔒 = Authentication required (expected for protected endpoints)"
echo "❓ = Not found (may indicate endpoint doesn't exist)"
echo "💥 = Server error (needs investigation)"
echo "❌ = Other error"
echo ""
echo "For full interactive documentation, visit: $BASE_URL/api/v1/docs/"
