#!/usr/bin/env node

/**
 * 🔗 Add GitHub Social Connection to Existing Auth0 Setup
 */

const { ManagementClient } = require('auth0');

// ANSI Colors
const colors = {
  green: '\x1b[32m',
  blue: '\x1b[34m',
  yellow: '\x1b[33m',
  red: '\x1b[31m',
  cyan: '\x1b[36m',
  reset: '\x1b[0m'
};

const log = (color, message) => console.log(`${colors[color]}${message}${colors.reset}`);

async function addGitHubConnection() {
  log('cyan', '🔗 Adding GitHub Social Connection to Auth0');
  log('yellow', '=' .repeat(45));

  const AUTH0_DOMAIN = process.env.AUTH0_DOMAIN;
  const AUTH0_M2M_CLIENT_ID = process.env.AUTH0_M2M_CLIENT_ID;
  const AUTH0_M2M_CLIENT_SECRET = process.env.AUTH0_M2M_CLIENT_SECRET;
  const GITHUB_CLIENT_ID = process.env.GITHUB_CLIENT_ID;
  const GITHUB_CLIENT_SECRET = process.env.GITHUB_CLIENT_SECRET;

  if (!AUTH0_DOMAIN || !AUTH0_M2M_CLIENT_ID || !AUTH0_M2M_CLIENT_SECRET || !GITHUB_CLIENT_ID || !GITHUB_CLIENT_SECRET) {
    log('red', '❌ Missing required credentials!');
    log('cyan', 'Required: AUTH0_DOMAIN, AUTH0_M2M_CLIENT_ID, AUTH0_M2M_CLIENT_SECRET, GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET');
    process.exit(1);
  }

  const management = new ManagementClient({
    domain: AUTH0_DOMAIN,
    clientId: AUTH0_M2M_CLIENT_ID,
    clientSecret: AUTH0_M2M_CLIENT_SECRET,
    scope: 'read:clients read:connections create:connections update:connections'
  });

  try {
    // Get existing Itqan CMS app
    log('blue', '📋 Finding Itqan CMS application...');
    const clients = await management.clients.getAll({ name: 'Itqan CMS Web App' });
    
    if (clients.data.length === 0) {
      log('red', '❌ Itqan CMS Web App not found');
      process.exit(1);
    }

    const appClientId = clients.data[0].client_id;
    log('green', `✅ Found app: ${appClientId}`);

    // Check if GitHub connection already exists
    log('blue', '📋 Checking for existing GitHub connection...');
    try {
      const connections = await management.connections.getAll({ strategy: 'github' });
      
      if (connections.data.length > 0) {
        log('yellow', '⚠️  GitHub connection already exists, updating...');
        
        // Update existing connection
        await management.connections.update(
          { id: connections.data[0].id },
          {
            options: {
              client_id: GITHUB_CLIENT_ID,
              client_secret: GITHUB_CLIENT_SECRET,
              scope: ['user:email'],
              set_user_root_attributes: 'on_each_login'
            },
            enabled_clients: [appClientId]
          }
        );
        
        log('green', '✅ GitHub connection updated');
      } else {
        // Create new GitHub connection
        log('blue', '📋 Creating new GitHub connection...');
        
        const githubConnection = await management.connections.create({
          name: 'github',
          strategy: 'github',
          options: {
            client_id: GITHUB_CLIENT_ID,
            client_secret: GITHUB_CLIENT_SECRET,
            scope: ['user:email'],
            set_user_root_attributes: 'on_each_login'
          },
          enabled_clients: [appClientId]
        });

        log('green', '✅ GitHub connection created');
      }
    } catch (connectionError) {
      log('red', `❌ Connection error: ${connectionError.message}`);
      process.exit(1);
    }

    // Update environment file to enable GitHub connection
    log('blue', '📋 Updating environment configuration...');
    
    const fs = require('fs');
    const path = require('path');
    const envPath = path.join(__dirname, 'web', '.env.local');
    
    if (fs.existsSync(envPath)) {
      let envContent = fs.readFileSync(envPath, 'utf8');
      
      // Uncomment GitHub connection line
      envContent = envContent.replace(
        '# AUTH0_LOGIN_CONNECTION=github',
        'AUTH0_LOGIN_CONNECTION=github'
      );
      
      fs.writeFileSync(envPath, envContent);
      log('green', '✅ Environment updated to use GitHub as default login');
    }

    log('green', '\n🎉 GitHub Social Connection Setup Complete!');
    log('yellow', '=' .repeat(45));
    log('cyan', '📋 Summary:');
    log('cyan', `   • Domain: ${AUTH0_DOMAIN}`);
    log('cyan', `   • Application: ${appClientId}`);
    log('cyan', `   • GitHub Connection: ✅ Configured`);
    log('cyan', `   • Default Login: GitHub SSO`);
    
    log('cyan', '\n🧪 Test GitHub Authentication:');
    log('cyan', '1. Visit: http://localhost:3000/register');
    log('cyan', '2. Click "GitHub" button');
    log('cyan', '3. Should redirect to GitHub OAuth');
    log('cyan', '4. After GitHub auth → redirect back to your app');
    
  } catch (error) {
    log('red', `❌ Error: ${error.message}`);
    if (error.statusCode) {
      log('red', `   Status: ${error.statusCode}`);
    }
    process.exit(1);
  }
}

// Run if called directly
if (require.main === module) {
  addGitHubConnection();
}

module.exports = { addGitHubConnection };
