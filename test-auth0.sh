#!/bin/bash

# Auth0 Test Script for Itqan CMS
# Replace the placeholder values with your actual Auth0 credentials

echo "🔐 Testing Auth0 Setup for Itqan CMS"
echo "====================================="

# Stop any running Next.js process
echo "1. Stopping any running Next.js processes..."
pkill -f "npm run dev" || echo "No running processes found"

# Navigate to web directory
cd web

# Start Next.js with Auth0 configuration
echo "2. Starting Next.js with Auth0 configuration..."
echo "📝 Make sure to replace the placeholder values below with your actual Auth0 credentials!"

AUTH0_SECRET=24b2490ffd98b4ceda49d75db5bc7adab4b70e133286de86c36fd719dfdaf25efcee4931a45a18d44f6dc6a746859508ffcb19bb9013b5a55d6fbced9a2daa6d \
AUTH0_BASE_URL=http://localhost:3000 \
AUTH0_ISSUER_BASE_URL=https://your-domain.auth0.com \
AUTH0_CLIENT_ID=your_client_id_here \
AUTH0_CLIENT_SECRET=your_client_secret_here \
AUTH0_AUDIENCE=https://api.itqan.com \
npm run dev

echo "3. After starting, test these URLs:"
echo "   - Registration: http://localhost:3000/register"
echo "   - Login: http://localhost:3000/api/auth/login"
echo "   - GitHub SSO: http://localhost:3000/api/auth/login?connection=github"
