#!/usr/bin/env node

/**
 * 🔧 Fix GitHub Connection for Correct Auth0 Client
 */

const { ManagementClient } = require('auth0');
const fs = require('fs');

async function fixGitHubConnection() {
  console.log('🔧 Fixing GitHub Connection for Correct Client...');

  // Get current client ID from environment file
  const envContent = fs.readFileSync('web/.env.local', 'utf8');
  const currentClientId = envContent.match(/AUTH0_CLIENT_ID=(.+)/)[1];
  console.log(`📋 Current Client ID: ${currentClientId}`);

  // Initialize Management API client
  const management = new ManagementClient({
    domain: 'dev-sit2vmj3hni4smep.us.auth0.com',
    clientId: 'fpSxQd7jKqy1aXFddiBfHLebnTjAKZi2',
    clientSecret: 'YtRs6atI8LQx75-ElfCdnCym63j4YaPUb44H3hUoFfSv66YrA943r4Y1BRbCBp2e',
    scope: 'read:connections update:connections'
  });

  try {
    // Get GitHub connection
    const connections = await management.connections.getAll({ strategy: 'github' });
    const githubConnection = connections.data[0];
    
    if (!githubConnection) {
      console.log('❌ GitHub connection not found');
      return;
    }

    console.log(`📋 GitHub Connection ID: ${githubConnection.id}`);
    console.log(`📋 Current enabled clients: ${githubConnection.enabled_clients.join(', ')}`);

    // Update GitHub connection to enable it for the correct client
    console.log('🔄 Updating GitHub connection...');
    
    const updatedConnection = await management.connections.update(
      { id: githubConnection.id },
      {
        enabled_clients: [currentClientId],
        options: {
          client_id: 'Ov23liixinP8iNlVVdUd',
          client_secret: 'ce2ec58836aa5eef1afb3b1450fe9858a0906f92',
          scope: ['user:email'],
          set_user_root_attributes: 'on_each_login'
        }
      }
    );

    console.log('✅ GitHub connection updated successfully!');
    console.log(`📋 New enabled clients: ${updatedConnection.data.enabled_clients.join(', ')}`);
    
    console.log('\n🧪 Test the fix:');
    console.log('1. Visit: http://localhost:3000/register');
    console.log('2. Click any social login button');
    console.log('3. Should now see GitHub option in Auth0 Universal Login');

  } catch (error) {
    console.log(`❌ Error: ${error.message}`);
    if (error.statusCode) {
      console.log(`   Status: ${error.statusCode}`);
    }
  }
}

fixGitHubConnection();
