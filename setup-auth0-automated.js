#!/usr/bin/env node

/**
 * 🚀 Automated Auth0 Setup for Itqan CMS
 * 
 * This script uses Auth0 Management API to automatically configure:
 * - SPA Application
 * - GitHub Social Connection  
 * - API & Audience
 * - Universal Login Branding
 */

const { ManagementClient } = require('auth0');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

// ANSI Colors for better output
const colors = {
  green: '\x1b[32m',
  blue: '\x1b[34m',
  yellow: '\x1b[33m',
  red: '\x1b[31m',
  cyan: '\x1b[36m',
  reset: '\x1b[0m',
  bold: '\x1b[1m'
};

const log = (color, message) => console.log(`${colors[color]}${message}${colors.reset}`);

async function setupAuth0() {
  log('cyan', '🚀 Starting Automated Auth0 Setup for Itqan CMS');
  log('yellow', '=' .repeat(50));

  // Step 1: Get Auth0 credentials
  const AUTH0_DOMAIN = process.env.AUTH0_DOMAIN;
  const AUTH0_M2M_CLIENT_ID = process.env.AUTH0_M2M_CLIENT_ID;
  const AUTH0_M2M_CLIENT_SECRET = process.env.AUTH0_M2M_CLIENT_SECRET;
  const GITHUB_CLIENT_ID = process.env.GITHUB_CLIENT_ID;
  const GITHUB_CLIENT_SECRET = process.env.GITHUB_CLIENT_SECRET;

  if (!AUTH0_DOMAIN || !AUTH0_M2M_CLIENT_ID || !AUTH0_M2M_CLIENT_SECRET) {
    log('red', '❌ Missing required Auth0 credentials!');
    log('yellow', 'Please set these environment variables:');
    log('cyan', '  AUTH0_DOMAIN=your-domain.auth0.com');
    log('cyan', '  AUTH0_M2M_CLIENT_ID=your_m2m_client_id');
    log('cyan', '  AUTH0_M2M_CLIENT_SECRET=your_m2m_client_secret');
    log('yellow', '\nTo get these credentials:');
    log('cyan', '1. Go to: https://manage.auth0.com/dashboard');
    log('cyan', '2. Create a Machine-to-Machine application');
    log('cyan', '3. Authorize it for the Auth0 Management API');
    log('cyan', '4. Copy the Domain, Client ID, and Client Secret');
    process.exit(1);
  }

  const management = new ManagementClient({
    domain: AUTH0_DOMAIN,
    clientId: AUTH0_M2M_CLIENT_ID,
    clientSecret: AUTH0_M2M_CLIENT_SECRET,
    scope: 'read:clients create:clients update:clients read:connections create:connections update:connections read:resource_servers create:resource_servers update:resource_servers read:branding update:branding'
  });

  try {
    log('blue', '📋 Step 1: Creating Itqan CMS SPA Application...');
    
    // Create SPA Application
    const app = await management.clients.create({
      name: 'Itqan CMS Web App',
      app_type: 'spa',
      description: 'Itqan Quranic Content Management System - Single Page Application',
      callbacks: ['http://localhost:3000/api/auth/callback', 'https://itqan.com/api/auth/callback'],
      allowed_logout_urls: ['http://localhost:3000', 'https://itqan.com'],
      web_origins: ['http://localhost:3000', 'https://itqan.com'],
      allowed_origins: ['http://localhost:3000', 'https://itqan.com'],
      grant_types: ['authorization_code', 'refresh_token'],
      token_endpoint_auth_method: 'none',
      oidc_conformant: true
    });

    log('green', `✅ SPA Application created: ${app.data.name}`);
    log('cyan', `   Client ID: ${app.data.client_id}`);

    // Create API Resource
    log('blue', '📋 Step 2: Creating Itqan CMS API...');
    
    const api = await management.resourceServers.create({
      name: 'Itqan CMS API',
      identifier: 'https://api.itqan.com',
      signing_alg: 'RS256',
      scopes: [
        { value: 'read:content', description: 'Read content' },
        { value: 'write:content', description: 'Write content' },
        { value: 'manage:users', description: 'Manage users' },
        { value: 'admin:all', description: 'Full admin access' }
      ],
      allow_offline_access: true,
      token_lifetime: 86400
    });

    log('green', `✅ API created: ${api.data.name}`);
    log('cyan', `   Identifier: ${api.data.identifier}`);

    // Create GitHub Connection (if credentials provided)
    if (GITHUB_CLIENT_ID && GITHUB_CLIENT_SECRET) {
      log('blue', '📋 Step 3: Creating GitHub Social Connection...');
      
      const githubConnection = await management.connections.create({
        name: 'github',
        strategy: 'github',
        options: {
          client_id: GITHUB_CLIENT_ID,
          client_secret: GITHUB_CLIENT_SECRET,
          scope: ['user:email'],
          set_user_root_attributes: 'on_each_login'
        },
        enabled_clients: [app.data.client_id]
      });

      log('green', '✅ GitHub Social Connection created');
    } else {
      log('yellow', '⚠️  Skipping GitHub connection (credentials not provided)');
      log('cyan', 'To add GitHub later, set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET');
    }

    // Update Branding
    log('blue', '📋 Step 4: Updating Universal Login Branding...');
    
    try {
      await management.branding.updateBranding({
        colors: {
          primary: '#669B80',
          page_background: '#FFFFFF'
        },
        logo_url: 'https://itqan.com/logo.png' // Update with actual logo URL
      });
      log('green', '✅ Branding updated with Itqan colors');
    } catch (brandingError) {
      log('yellow', '⚠️  Branding update skipped (requires higher plan)');
    }

    // Generate environment file
    log('blue', '📋 Step 5: Generating environment configuration...');
    
    const auth0Secret = crypto.randomBytes(64).toString('hex');
    const envContent = `# Auth0 Configuration for Itqan CMS
# Generated on ${new Date().toISOString()}

# Core Auth0 Settings
AUTH0_SECRET=${auth0Secret}
AUTH0_BASE_URL=http://localhost:3000
AUTH0_ISSUER_BASE_URL=https://${AUTH0_DOMAIN}
AUTH0_CLIENT_ID=${app.data.client_id}
AUTH0_CLIENT_SECRET=${app.data.client_secret || 'not_needed_for_spa'}
AUTH0_AUDIENCE=${api.data.identifier}

# Optional: Force GitHub login (if configured)
${GITHUB_CLIENT_ID ? 'AUTH0_LOGIN_CONNECTION=github' : '# AUTH0_LOGIN_CONNECTION=github'}

# Next.js Public Variables
NEXT_PUBLIC_AUTH0_DOMAIN=${AUTH0_DOMAIN}
NEXT_PUBLIC_AUTH0_CLIENT_ID=${app.data.client_id}
NEXT_PUBLIC_AUTH0_AUDIENCE=${api.data.identifier}
`;

    fs.writeFileSync(path.join(__dirname, 'web', '.env.local'), envContent);
    log('green', '✅ Environment file created: web/.env.local');

    // Generate test script
    const testScript = `#!/bin/bash
# Auto-generated Auth0 test script

echo "🧪 Testing Auth0 Configuration..."
cd web

# Start Next.js with Auth0 configuration
AUTH0_SECRET=${auth0Secret} \\
AUTH0_BASE_URL=http://localhost:3000 \\
AUTH0_ISSUER_BASE_URL=https://${AUTH0_DOMAIN} \\
AUTH0_CLIENT_ID=${app.data.client_id} \\
AUTH0_CLIENT_SECRET=${app.data.client_secret || ''} \\
AUTH0_AUDIENCE=${api.data.identifier} \\
npm run dev

echo "✅ Visit: http://localhost:3000/register"
echo "✅ Test login: http://localhost:3000/api/auth/login"
${GITHUB_CLIENT_ID ? 'echo "✅ GitHub SSO: http://localhost:3000/api/auth/login?connection=github"' : ''}
`;

    fs.writeFileSync(path.join(__dirname, 'test-auth0-auto.sh'), testScript);
    fs.chmodSync(path.join(__dirname, 'test-auth0-auto.sh'), 0o755);
    log('green', '✅ Test script created: test-auth0-auto.sh');

    // Summary
    log('green', '\n🎉 Auth0 Setup Complete!');
    log('yellow', '=' .repeat(50));
    log('cyan', '📋 Summary:');
    log('cyan', `   • Domain: ${AUTH0_DOMAIN}`);
    log('cyan', `   • Application: ${app.data.name}`);
    log('cyan', `   • Client ID: ${app.data.client_id}`);
    log('cyan', `   • API: ${api.data.identifier}`);
    log('cyan', `   • Environment: web/.env.local`);
    log('cyan', '\n🚀 Next Steps:');
    log('cyan', '1. Run: ./test-auth0-auto.sh');
    log('cyan', '2. Visit: http://localhost:3000/register');
    log('cyan', '3. Test the complete authentication flow!');

    if (!GITHUB_CLIENT_ID) {
      log('yellow', '\n💡 To add GitHub SSO:');
      log('cyan', '1. Create GitHub OAuth app at: https://github.com/settings/applications/new');
      log('cyan', `2. Set callback URL: https://${AUTH0_DOMAIN}/login/callback`);
      log('cyan', '3. Re-run this script with GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET');
    }

  } catch (error) {
    log('red', `❌ Error: ${error.message}`);
    if (error.statusCode) {
      log('red', `   Status: ${error.statusCode}`);
    }
    process.exit(1);
  }
}

// Check if running directly
if (require.main === module) {
  setupAuth0();
}

module.exports = { setupAuth0 };
