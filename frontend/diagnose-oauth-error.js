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

async function getGitHubConnection(token) {
  return new Promise((resolve, reject) => {
    const options = {
      hostname: AUTH0_DOMAIN,
      port: 443,
      path: '/api/v2/connections?strategy=github',
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
          reject(new Error(`Get connections failed: ${res.statusCode}`));
        }
      });
    });

    req.on('error', reject);
    req.end();
  });
}

async function getApplication(token) {
  return new Promise((resolve, reject) => {
    const options = {
      hostname: AUTH0_DOMAIN,
      port: 443,
      path: '/api/v2/clients/h4NPegjClDuYxZefNBeXIhqXbu9SV6aC',
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
          reject(new Error(`Get application failed: ${res.statusCode}`));
        }
      });
    });

    req.on('error', reject);
    req.end();
  });
}

async function main() {
  try {
    console.log('🔍 Diagnosing OAuth Configuration...');
    console.log('====================================');
    
    const token = await getManagementToken();
    console.log('✅ Management token obtained');

    console.log('\n📋 GitHub Connection Details:');
    const connections = await getGitHubConnection(token);
    const githubConn = connections[0];
    if (githubConn) {
      console.log(`   ID: ${githubConn.id}`);
      console.log(`   Name: ${githubConn.name}`);
      console.log(`   Strategy: ${githubConn.strategy}`);
      console.log(`   Enabled: ${githubConn.enabled}`);
      console.log(`   Client ID: ${githubConn.options.client_id}`);
      console.log(`   Enabled Clients: ${githubConn.enabled_clients.join(', ')}`);
    } else {
      console.log('   ❌ No GitHub connection found');
    }

    console.log('\n📋 Application Details:');
    const app = await getApplication(token);
    console.log(`   Name: ${app.name}`);
    console.log(`   Client ID: ${app.client_id}`);
    console.log(`   Callbacks: ${app.callbacks ? app.callbacks.join(', ') : 'None'}`);
    console.log(`   Logout URLs: ${app.allowed_logout_urls ? app.allowed_logout_urls.join(', ') : 'None'}`);
    console.log(`   Web Origins: ${app.web_origins ? app.web_origins.join(', ') : 'None'}`);

    console.log('\n🔧 Potential Issues to Check:');
    console.log('1. GitHub OAuth App callback URL should be: https://dev-itqan.eu.auth0.com/login/callback');
    console.log('2. GitHub OAuth App should be active and not suspended');
    console.log('3. GitHub OAuth App Client ID/Secret should match Auth0 connection');
    console.log('4. Auth0 connection should be enabled for your application');

  } catch (error) {
    console.error('❌ Diagnosis failed:', error.message);
  }
}

main();
