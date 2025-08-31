const https = require('https');

const AUTH0_DOMAIN = 'dev-itqan.eu.auth0.com';
const CLIENT_ID = 'RYjndDR2mlvnWKAqFNi5bqGh1J9ig00L';
const CLIENT_SECRET = 'CDuYPjJkckJpktrQkccH7iYAu_WQJCVzhnxk_8NWlgkwN3WslrH7FQtF4OZZCPsf';
const AUDIENCE = 'https://dev-itqan.eu.auth0.com/api/v2/';

async function getManagementToken() {
  return new Promise((resolve, reject) => {
    const postData = JSON.stringify({
      client_id: CLIENT_ID,
      client_secret: CLIENT_SECRET,
      audience: AUDIENCE,
      grant_type: 'client_credentials'
    });

    const options = {
      hostname: AUTH0_DOMAIN,
      port: 443,
      path: '/oauth/token',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(postData)
      }
    };

    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', (chunk) => data += chunk);
      res.on('end', () => {
        if (res.statusCode === 200) {
          resolve(JSON.parse(data).access_token);
        } else {
          reject(new Error(`Token request failed: ${res.statusCode}`));
        }
      });
    });

    req.on('error', reject);
    req.write(postData);
    req.end();
  });
}

async function testGitHubConnection(token) {
  return new Promise((resolve, reject) => {
    const options = {
      hostname: AUTH0_DOMAIN,
      port: 443,
      path: '/api/v2/connections/con_TgRLMCMLxq4AhQNF',
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    };

    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', (chunk) => data += chunk);
      res.on('end', () => {
        if (res.statusCode === 200) {
          resolve(JSON.parse(data));
        } else {
          reject(new Error(`Get connection failed: ${res.statusCode}`));
        }
      });
    });

    req.on('error', reject);
    req.end();
  });
}

async function main() {
  try {
    console.log('🔍 Debugging OAuth Flow...');
    console.log('===========================');
    
    const token = await getManagementToken();
    console.log('✅ Management token obtained');

    console.log('\n📋 GitHub Connection Status:');
    const connection = await testGitHubConnection(token);
    console.log(`   ID: ${connection.id}`);
    console.log(`   Name: ${connection.name}`);
    console.log(`   Strategy: ${connection.strategy}`);
    console.log(`   Client ID: ${connection.options.client_id}`);
    console.log(`   Enabled Clients: ${connection.enabled_clients ? connection.enabled_clients.join(', ') : 'None'}`);
    
    // Check if connection has our app enabled
    const isAppEnabled = connection.enabled_clients && connection.enabled_clients.includes('h4NPegjClDuYxZefNBeXIhqXbu9SV6aC');
    console.log(`   App Enabled: ${isAppEnabled ? '✅ Yes' : '❌ No'}`);

    console.log('\n🔧 Issues Found:');
    if (!isAppEnabled) {
      console.log('   ❌ GitHub connection is not enabled for your application');
      console.log('   This is likely the main issue!');
    }
    
    console.log('\n🎯 Possible Causes of 404:');
    console.log('   1. GitHub OAuth App suspended or deleted');
    console.log('   2. Client ID mismatch between GitHub and Auth0');
    console.log('   3. Organization OAuth app restrictions');
    console.log('   4. GitHub OAuth App not approved for organization use');
    
  } catch (error) {
    console.error('❌ Debug failed:', error.message);
  }
}

main();
