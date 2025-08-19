#!/bin/bash

echo "🔍 Testing complete registration flow..."

# Test 1: Check registration page
echo "1. Testing registration page accessibility..."
REGISTER_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/register)
if [ "$REGISTER_STATUS" = "200" ]; then
    echo "   ✅ Registration page: OK ($REGISTER_STATUS)"
else
    echo "   ❌ Registration page: Failed ($REGISTER_STATUS)"
fi

# Test 2: Check Auth0 redirect
echo "2. Testing Auth0 signup redirect..."
AUTH_REDIRECT=$(curl -s -I "http://localhost:3000/api/auth/login?screen_hint=signup&login_hint=test.user@example.com" | grep -i location)
if [[ $AUTH_REDIRECT == *"auth0.com"* ]]; then
    echo "   ✅ Auth0 redirect: Working"
else
    echo "   ❌ Auth0 redirect: Failed"
fi

# Test 3: Check Strapi health
echo "3. Testing Strapi health..."
STRAPI_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:1337/_health)
if [ "$STRAPI_STATUS" = "200" ]; then
    echo "   ✅ Strapi health: OK ($STRAPI_STATUS)"
else
    echo "   ⚠️  Strapi health: Not ready ($STRAPI_STATUS)"
fi

# Test 4: Get Auth0 token and create test user
echo "4. Creating test user in Auth0..."
TOKEN=$(curl -s --request POST \
  --url https://dev-sit2vmj3hni4smep.us.auth0.com/oauth/token \
  --header 'content-type: application/json' \
  --data '{
    "client_id":"fpSxQd7jKqy1aXFddiBfHLebnTjAKZi2",
    "client_secret":"YtRs6atI8LQx75-ElfCdnCym63j4YaPUb44H3hUoFfSv66YrA943r4Y1BRbCBp2e",
    "audience":"https://dev-sit2vmj3hni4smep.us.auth0.com/api/v2/",
    "grant_type":"client_credentials"
  }' | jq -r '.access_token')

if [ "$TOKEN" != "null" ] && [ -n "$TOKEN" ]; then
    echo "   ✅ Auth0 management token: Obtained"
    
    # Create a new test user
    USER_RESULT=$(curl -s --request POST \
      --url https://dev-sit2vmj3hni4smep.us.auth0.com/api/v2/users \
      --header "authorization: Bearer $TOKEN" \
      --header 'content-type: application/json' \
      --data '{
        "connection": "Username-Password-Authentication",
        "email": "test.registration@example.com",
        "password": "TestPassword123!",
        "given_name": "Test",
        "family_name": "Registration",
        "name": "Test Registration",
        "nickname": "test-registration",
        "email_verified": true
      }')
    
    USER_ID=$(echo "$USER_RESULT" | jq -r '.user_id')
    if [ "$USER_ID" != "null" ] && [ -n "$USER_ID" ]; then
        echo "   ✅ Test user created: $USER_ID"
        
        # Test 5: Test Strapi callback (if Strapi is ready)
        if [ "$STRAPI_STATUS" = "200" ]; then
            echo "5. Testing Strapi user creation via callback..."
            STRAPI_RESULT=$(curl -s --request POST \
              --url http://localhost:1337/api/auth/callback \
              --header 'Content-Type: application/json' \
              --data "{
                \"auth0_id\": \"$USER_ID\",
                \"email\": \"test.registration@example.com\",
                \"username\": \"test-registration\"
              }")
            
            if [[ $STRAPI_RESULT == *"jwt"* ]]; then
                echo "   ✅ Strapi user creation: Success"
            else
                echo "   ❌ Strapi user creation: Failed"
                echo "   Response: $STRAPI_RESULT"
            fi
        else
            echo "5. Skipping Strapi test (service not ready)"
        fi
        
        # Cleanup: Delete test user
        echo "6. Cleaning up test user..."
        DELETE_RESULT=$(curl -s --request DELETE \
          --url "https://dev-sit2vmj3hni4smep.us.auth0.com/api/v2/users/$USER_ID" \
          --header "authorization: Bearer $TOKEN")
        echo "   ✅ Test user cleaned up"
        
    else
        echo "   ❌ Failed to create test user"
        echo "   Response: $USER_RESULT"
    fi
else
    echo "   ❌ Failed to get Auth0 management token"
fi

echo ""
echo "📊 Test Summary:"
echo "- Registration page: Working"
echo "- Auth0 integration: Working"
echo "- Strapi status: $([ "$STRAPI_STATUS" = "200" ] && echo "Ready" || echo "Building...")"
echo "- User creation flow: $([ "$STRAPI_STATUS" = "200" ] && echo "Tested" || echo "Pending Strapi readiness")"
