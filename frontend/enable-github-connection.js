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

async function enableGitHubConnection(token) {
  return new Promise((resolve, reject) => {
    const connectionData = JSON.stringify({
      enabled: true,
      enabled_clients: ['h4NPegjClDuYxZefNBeXIhqXbu9SV6aC'],
      options: {
        client_id: '0v23liemrfSQLjWQeZZo',
        client_secret: 'ce6c555e9c78ce86f8f5ebd3dd336cf930ea6433',
        scope: ['user:email', 'read:user']
      }
    });

    const options = {
      hostname: AUTH0_DOMAIN,
      port: 443,
      path: '/api/v2/connections/con_TgRLMCMLxq4AhQNF',
      method: 'PATCH',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(connectionData)
      }
    };

    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', (chunk) => data += chunk);
      res.on('end', () => {
        console.log(`GitHub Connection Enable Status: ${res.statusCode}`);
        if (res.statusCode === 200) {
          console.log('✅ GitHub connection enabled successfully!');
          const result = JSON.parse(data);
          console.log(`   Enabled: ${result.enabled}`);
          console.log(`   Enabled Clients: ${result.enabled_clients.join(', ')}`);
          resolve(result);
        } else {
          console.log('Response:', data);
          reject(new Error(`Connection enable failed: ${res.statusCode}`));
        }
      });
    });

    req.on('error', reject);
    req.write(connectionData);
    req.end();
  });
}

async function main() {
  try {
    console.log('🔧 Enabling GitHub Connection...');
    console.log('================================');
    
    const token = await getManagementToken();
    await enableGitHubConnection(token);
    
    console.log('\n🎉 GitHub connection is now properly enabled!');
    console.log('\n🧪 Test the authentication:');
    console.log('1. Visit: http://localhost:3000/ar/auth/login');
    console.log('2. Click "Login with GitHub"');
    console.log('3. You should be redirected to GitHub for authorization');
    
  } catch (error) {
    console.error('❌ Enable failed:', error.message);
  }
}

main();
