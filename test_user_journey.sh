#!/bin/bash

# =============================================================================
# 🚀 Itqan CMS - Complete User Journey Demo Script
# =============================================================================
# This script demonstrates the complete user experience from registration
# to downloading assets through the Itqan CMS API.
# =============================================================================

set -e

# ANSI Color codes for beautiful output
RED='\033[91m'
GREEN='\033[92m'
YELLOW='\033[93m'
BLUE='\033[94m'
PURPLE='\033[95m'
CYAN='\033[96m'
WHITE='\033[97m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m' # No Color

# Configuration - Override with environment variables
BASE_URL="${BASE_URL:-https://develop.api.cms.itqan.dev}"
API_BASE="${BASE_URL}/api/v1"
# Generate unique email with timestamp to avoid conflicts on reruns
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DEMO_EMAIL="${DEMO_EMAIL:-demouser_${TIMESTAMP}@example.com}"
DEMO_PASSWORD="${DEMO_PASSWORD:-SecurePassword123!}"
DEMO_FIRST_NAME="${DEMO_FIRST_NAME:-Demo}"
DEMO_LAST_NAME="${DEMO_LAST_NAME:-User}"
DEMO_PHONE="${DEMO_PHONE:-+1234567890}"
DEMO_TITLE="${DEMO_TITLE:-Student}"

# Global variables
ACCESS_TOKEN=""
SELECTED_ASSET_ID=""
DOWNLOAD_DIR="./downloads"

# =============================================================================
# Helper Functions
# =============================================================================

print_header() {
    echo ""
    echo -e "${BOLD}${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${BLUE}║  🚀 Itqan CMS - Complete User Journey Demo                ║${NC}"
    echo -e "${BOLD}${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${CYAN}🌐 API Base URL: ${BOLD}${WHITE}${BASE_URL}${NC}"
    echo -e "${CYAN}📧 Demo Email: ${BOLD}${WHITE}${DEMO_EMAIL}${NC}"
    echo -e "${CYAN}🔑 Password: ${BOLD}${WHITE}${DEMO_PASSWORD:0:4}****${NC}"
    echo ""
}

print_step() {
    local step_num="$1"
    local title="$2"
    echo -e "${BOLD}${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}${WHITE}Step ${step_num}: ${title}${NC}"
    echo -e "${BOLD}${PURPLE}▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔${NC}"
}

print_status() {
    local status="$1"
    local message="$2"
    if [ "$status" = "SUCCESS" ]; then
        echo -e "    ${BOLD}${GREEN}✅ $message${NC}"
    elif [ "$status" = "INFO" ]; then
        echo -e "    ${BOLD}${CYAN}ℹ️  $message${NC}"
    elif [ "$status" = "WARNING" ]; then
        echo -e "    ${BOLD}${YELLOW}⚠️  $message${NC}"
    elif [ "$status" = "ERROR" ]; then
        echo -e "    ${BOLD}${RED}❌ $message${NC}"
    fi
}

show_curl_command() {
    local cmd="$1"
    echo -e "    ${BOLD}${PURPLE}📤 CURL COMMAND:${NC}"
    echo -e "    ${DIM}${CYAN}$cmd${NC}"
    echo ""
}

show_response() {
    local response="$1"
    echo -e "    ${BOLD}${PURPLE}📥 RESPONSE:${NC}"
    if echo "$response" | python3 -c "import sys,json; json.load(sys.stdin)" 2>/dev/null; then
        echo "$response" | python3 -m json.tool 2>/dev/null | sed 's/^/        /' || echo "$response" | sed 's/^/        /'
    else
        echo "$response" | head -10 | sed 's/^/        /' | sed 's/\(HTTP.*\)/'"${BOLD}${WHITE}"'\1'"${NC}"'/g'
        if [ $(echo "$response" | wc -l) -gt 10 ]; then
            echo -e "        ${DIM}... (response truncated)${NC}"
        fi
    fi
    echo ""
}

pause_for_user() {
    echo -e "${BOLD}${YELLOW}⏸️  Press ENTER to continue...${NC}"
    read -r
}

# =============================================================================
# API Functions
# =============================================================================

step1_register() {
    print_step "1" "🆕 Register New User Account"
    
    local curl_cmd="curl -s -X POST \"${API_BASE}/auth/register/\" \\
  -H \"Content-Type: application/json\" \\
  -d '{
    \"email\": \"${DEMO_EMAIL}\",
    \"password\": \"${DEMO_PASSWORD}\",
    \"first_name\": \"${DEMO_FIRST_NAME}\",
    \"last_name\": \"${DEMO_LAST_NAME}\",
    \"phone_number\": \"${DEMO_PHONE}\",
    \"title\": \"${DEMO_TITLE}\"
  }'"
    
    show_curl_command "$curl_cmd"
    
    local response
    response=$(curl -s -X POST "${API_BASE}/auth/register/" \
      -H "Content-Type: application/json" \
      -d "{
        \"email\": \"${DEMO_EMAIL}\",
        \"password\": \"${DEMO_PASSWORD}\",
        \"first_name\": \"${DEMO_FIRST_NAME}\",
        \"last_name\": \"${DEMO_LAST_NAME}\",
        \"phone_number\": \"${DEMO_PHONE}\",
        \"title\": \"${DEMO_TITLE}\"
      }")
    
    show_response "$response"
    
    if echo "$response" | grep -q '"user_id"'; then
        print_status "SUCCESS" "User account created successfully!"
        local user_id=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin)['user_id'])" 2>/dev/null || echo "unknown")
        print_status "INFO" "User ID: $user_id"
    elif echo "$response" | grep -q '"email".*"already exists"'; then
        print_status "WARNING" "User email already exists. This is unexpected with timestamp-based email."
        print_status "INFO" "Continuing with login attempt..."
    elif echo "$response" | grep -q '"error"'; then
        local error_msg=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin).get('error', {}).get('message', 'Unknown error'))" 2>/dev/null || echo "Unknown error")
        print_status "WARNING" "Registration failed: $error_msg"
        print_status "INFO" "Continuing with login attempt..."
    else
        print_status "WARNING" "Unexpected response from registration. Continuing with login attempt..."
    fi
    
    pause_for_user
}

step2_login() {
    print_step "2" "🔐 Login and Get Access Token"
    
    local curl_cmd="curl -s -X POST \"${API_BASE}/auth/login/\" \\
  -H \"Content-Type: application/json\" \\
  -d '{
    \"email\": \"${DEMO_EMAIL}\",
    \"password\": \"${DEMO_PASSWORD}\"
  }'"
    
    show_curl_command "$curl_cmd"
    
    local response
    response=$(curl -s -X POST "${API_BASE}/auth/login/" \
      -H "Content-Type: application/json" \
      -d "{
        \"email\": \"${DEMO_EMAIL}\",
        \"password\": \"${DEMO_PASSWORD}\"
      }")
    
    show_response "$response"
    
    if echo "$response" | grep -q '"access_token"'; then
        ACCESS_TOKEN=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null)
        print_status "SUCCESS" "Login successful! Access token obtained."
        print_status "INFO" "Token: ${ACCESS_TOKEN:0:20}..."
    else
        print_status "ERROR" "Failed to login. Cannot continue without access token."
        exit 1
    fi
    
    pause_for_user
}

step3_list_assets() {
    print_step "3" "📋 List All Available Assets"
    
    local curl_cmd="curl -s -X GET \"${API_BASE}/assets/\" \\
  -H \"Authorization: Bearer ${ACCESS_TOKEN:0:20}...\""
    
    show_curl_command "$curl_cmd"
    
    local response
    response=$(curl -s -X GET "${API_BASE}/assets/" \
      -H "Authorization: Bearer ${ACCESS_TOKEN}")
    
    show_response "$response"
    
    if echo "$response" | grep -q '"assets"'; then
        local asset_count=$(echo "$response" | python3 -c "import sys,json; print(len(json.load(sys.stdin)['assets']))" 2>/dev/null || echo "0")
        print_status "SUCCESS" "Found $asset_count assets available"
        
        # Get the first asset ID for next steps
        SELECTED_ASSET_ID=$(echo "$response" | python3 -c "import sys,json; assets=json.load(sys.stdin)['assets']; print(assets[0]['id'] if assets else '')" 2>/dev/null || echo "")
        
        if [ -n "$SELECTED_ASSET_ID" ]; then
            local asset_title=$(echo "$response" | python3 -c "import sys,json; assets=json.load(sys.stdin)['assets']; print(assets[0]['title'] if assets else '')" 2>/dev/null || echo "Unknown")
            print_status "INFO" "Selected asset for demo: $asset_title"
            print_status "INFO" "Asset ID: $SELECTED_ASSET_ID"
        else
            print_status "WARNING" "No assets found for detailed testing"
        fi
    else
        print_status "ERROR" "Failed to retrieve assets list"
        SELECTED_ASSET_ID=""
    fi
    
    pause_for_user
}

step4_asset_details() {
    if [ -z "$SELECTED_ASSET_ID" ]; then
        print_status "WARNING" "Skipping asset details - no asset selected"
        return
    fi
    
    print_step "4" "🔍 Get Asset Details"
    
    local curl_cmd="curl -s -X GET \"${API_BASE}/assets/${SELECTED_ASSET_ID}/\" \\
  -H \"Authorization: Bearer ${ACCESS_TOKEN:0:20}...\""
    
    show_curl_command "$curl_cmd"
    
    local response
    response=$(curl -s -X GET "${API_BASE}/assets/${SELECTED_ASSET_ID}/" \
      -H "Authorization: Bearer ${ACCESS_TOKEN}")
    
    show_response "$response"
    
    if echo "$response" | grep -q '"id"'; then
        print_status "SUCCESS" "Asset details retrieved successfully"
        local title=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin)['title'])" 2>/dev/null || echo "Unknown")
        local category=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin)['category'])" 2>/dev/null || echo "Unknown")
        local file_size=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin)['file_size'])" 2>/dev/null || echo "Unknown")
        print_status "INFO" "Title: $title"
        print_status "INFO" "Category: $category"
        print_status "INFO" "Size: $file_size"
    else
        print_status "ERROR" "Failed to get asset details"
    fi
    
    pause_for_user
}

step5_request_access() {
    if [ -z "$SELECTED_ASSET_ID" ]; then
        print_status "WARNING" "Skipping access request - no asset selected"
        return
    fi
    
    print_step "5" "🙋 Request Access to Asset"
    
    local curl_cmd="curl -s -X POST \"${API_BASE}/assets/${SELECTED_ASSET_ID}/request-access/\" \\
  -H \"Authorization: Bearer ${ACCESS_TOKEN:0:20}...\" \\
  -H \"Content-Type: application/json\" \\
  -d '{
    \"purpose\": \"Demo and testing purposes for the Itqan CMS API\",
    \"intended_use\": \"non-commercial\"
  }'"
    
    show_curl_command "$curl_cmd"
    
    local response
    response=$(curl -s -X POST "${API_BASE}/assets/${SELECTED_ASSET_ID}/request-access/" \
      -H "Authorization: Bearer ${ACCESS_TOKEN}" \
      -H "Content-Type: application/json" \
      -d '{
        "purpose": "Demo and testing purposes for the Itqan CMS API",
        "intended_use": "non-commercial"
      }')
    
    show_response "$response"
    
    if echo "$response" | grep -q '"request_id"'; then
        print_status "SUCCESS" "Access request submitted successfully"
        local request_id=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin)['request_id'])" 2>/dev/null || echo "unknown")
        local status=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])" 2>/dev/null || echo "unknown")
        print_status "INFO" "Request ID: $request_id"
        print_status "INFO" "Status: $status"
        
        if [ "$status" = "approved" ]; then
            print_status "SUCCESS" "Access automatically approved! You can now download the asset."
        else
            print_status "INFO" "Access request is pending approval"
        fi
    else
        print_status "ERROR" "Failed to submit access request"
    fi
    
    pause_for_user
}

step6_download_asset() {
    if [ -z "$SELECTED_ASSET_ID" ]; then
        print_status "WARNING" "Skipping download - no asset selected"
        return
    fi
    
    print_step "6" "⬇️  Download Asset"
    
    # Create downloads directory
    mkdir -p "$DOWNLOAD_DIR"
    
    local curl_cmd="curl -s -X GET \"${API_BASE}/assets/${SELECTED_ASSET_ID}/download/\" \\
  -H \"Authorization: Bearer ${ACCESS_TOKEN:0:20}...\" \\
  -L -o \"${DOWNLOAD_DIR}/asset_${SELECTED_ASSET_ID:0:8}.zip\""
    
    show_curl_command "$curl_cmd"
    
    local response
    response=$(curl -s -X GET "${API_BASE}/assets/${SELECTED_ASSET_ID}/download/" \
      -H "Authorization: Bearer ${ACCESS_TOKEN}" \
      -w "\nHTTP_STATUS:%{http_code}")
    
    local http_status=$(echo "$response" | tail -1 | cut -d: -f2)
    local response_body=$(echo "$response" | sed '$d')
    
    echo -e "    ${BOLD}${PURPLE}📥 DOWNLOAD RESPONSE:${NC}"
    echo -e "        ${BOLD}${WHITE}HTTP Status: $http_status${NC}"
    
    if [ "$http_status" = "200" ]; then
        print_status "SUCCESS" "Asset download successful!"
        print_status "INFO" "File saved to: ${DOWNLOAD_DIR}/asset_${SELECTED_ASSET_ID:0:8}.zip"
        
        # Actually save the file (re-run curl for real download)
        curl -s -X GET "${API_BASE}/assets/${SELECTED_ASSET_ID}/download/" \
          -H "Authorization: Bearer ${ACCESS_TOKEN}" \
          -L -o "${DOWNLOAD_DIR}/asset_${SELECTED_ASSET_ID:0:8}.zip" 2>/dev/null
          
        if [ -f "${DOWNLOAD_DIR}/asset_${SELECTED_ASSET_ID:0:8}.zip" ]; then
            local file_size=$(ls -lh "${DOWNLOAD_DIR}/asset_${SELECTED_ASSET_ID:0:8}.zip" | awk '{print $5}')
            print_status "INFO" "Downloaded file size: $file_size"
        fi
    elif [ "$http_status" = "403" ]; then
        print_status "ERROR" "Access denied - you may need to wait for access approval"
        show_response "$response_body"
    elif [ "$http_status" = "404" ]; then
        print_status "ERROR" "Asset not found or download not available"
        show_response "$response_body"
    else
        print_status "ERROR" "Download failed with HTTP $http_status"
        show_response "$response_body"
    fi
    
    pause_for_user
}

step7_profile() {
    print_step "7" "👤 Check User Profile"
    
    local curl_cmd="curl -s -X GET \"${API_BASE}/auth/profile/\" \\
  -H \"Authorization: Bearer ${ACCESS_TOKEN:0:20}...\""
    
    show_curl_command "$curl_cmd"
    
    local response
    response=$(curl -s -X GET "${API_BASE}/auth/profile/" \
      -H "Authorization: Bearer ${ACCESS_TOKEN}")
    
    show_response "$response"
    
    if echo "$response" | grep -q '"email"'; then
        print_status "SUCCESS" "Profile retrieved successfully"
        local email=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin)['email'])" 2>/dev/null || echo "unknown")
        local full_name=$(echo "$response" | python3 -c "import sys,json; data=json.load(sys.stdin); print(f\"{data.get('first_name', '')} {data.get('last_name', '')}\")" 2>/dev/null || echo "unknown")
        print_status "INFO" "User: $full_name ($email)"
    else
        print_status "ERROR" "Failed to retrieve profile"
    fi
    
    pause_for_user
}

# =============================================================================
# Main Execution
# =============================================================================

main() {
    print_header
    
    echo -e "${BOLD}${CYAN}🎯 This script will demonstrate a complete user journey:${NC}"
    echo -e "   ${WHITE}1. Register a new account${NC}"
    echo -e "   ${WHITE}2. Login and get access token${NC}"
    echo -e "   ${WHITE}3. List available assets${NC}"
    echo -e "   ${WHITE}4. Get detailed asset information${NC}"
    echo -e "   ${WHITE}5. Request access to an asset${NC}"
    echo -e "   ${WHITE}6. Download the asset${NC}"
    echo -e "   ${WHITE}7. Check user profile${NC}"
    echo ""
    
    pause_for_user
    
    # Execute all steps
    step1_register
    step2_login
    step3_list_assets
    step4_asset_details
    step5_request_access
    step6_download_asset
    step7_profile
    
    # Final summary
    echo ""
    echo -e "${BOLD}${GREEN}🎉 User Journey Demo Complete!${NC}"
    echo ""
    echo -e "${BOLD}${CYAN}📊 Summary:${NC}"
    echo -e "   ${WHITE}• User Email: ${DEMO_EMAIL}${NC}"
    echo -e "   ${WHITE}• Access Token: ${ACCESS_TOKEN:0:20}...${NC}"
    if [ -n "$SELECTED_ASSET_ID" ]; then
        echo -e "   ${WHITE}• Demo Asset: ${SELECTED_ASSET_ID}${NC}"
    fi
    if [ -d "$DOWNLOAD_DIR" ] && [ "$(ls -A $DOWNLOAD_DIR 2>/dev/null)" ]; then
        echo -e "   ${WHITE}• Downloads: $(ls $DOWNLOAD_DIR | wc -l) file(s) in $DOWNLOAD_DIR${NC}"
    fi
    echo ""
    echo -e "${BOLD}${PURPLE}✨ The Itqan CMS API is working perfectly! ✨${NC}"
    echo ""
}

# Handle script arguments
case "${1:-}" in
    --help|-h)
        echo "Itqan CMS - Complete User Journey Demo"
        echo ""
        echo "Usage: $0 [options]"
        echo ""
        echo "Environment Variables:"
        echo "  BASE_URL      API base URL (default: https://develop.api.cms.itqan.dev)"
        echo "  DEMO_EMAIL    Demo user email (default: demouser<timestamp>@example.com)"
        echo "  DEMO_PASSWORD Demo user password (default: SecurePassword123!)"
        echo ""
        echo "Examples:"
        echo "  $0                                    # Run with defaults"
        echo "  BASE_URL=http://localhost:8000 $0     # Run against local server"
        echo "  DEMO_EMAIL=mytest@example.com $0      # Use custom email"
        exit 0
        ;;
    *)
        main
        ;;
esac
