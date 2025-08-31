const https = require('https');

// Auth0 Management API credentials
const AUTH0_DOMAIN = 'dev-itqan.eu.auth0.com';
const CLIENT_ID = 'RYjndDR2mlvnWKAqFNi5bqGh1J9ig00L';
const CLIENT_SECRET = 'CDuYPjJkckJpktrQkccH7iYAu_WQJCVzhnxk_8NWlgkwN3WslrH7FQtF4OZZCPsf';
const AUDIENCE = 'https://dev-itqan.eu.auth0.com/api/v2/';

// GitHub OAuth App credentials
const GITHUB_CLIENT_ID = '0v23liemrfSQLjWQeZZo';
const GITHUB_CLIENT_SECRET = 'ce6c555e9c78ce86f8f5ebd3dd336cf930ea6433';

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
          const response = JSON.parse(data);
          resolve(response.access_token);
        } else {
          reject(new Error(`Token request failed: ${res.statusCode} - ${data}`));
        }
      });
    });

    req.on('error', reject);
    req.write(postData);
    req.end();
  });
}

async function createGitHubConnection(token) {
  return new Promise((resolve, reject) => {
    const connectionData = JSON.stringify({
      name: 'github',
      strategy: 'github',
      options: {
        client_id: GITHUB_CLIENT_ID,
        client_secret: GITHUB_CLIENT_SECRET,
        scope: ['user:email', 'read:user']
      },
      enabled_clients: ['h4NPegjClDuYxZefNBeXIhqXbu9SV6aC'] // Your frontend app client ID
    });

    const options = {
      hostname: AUTH0_DOMAIN,
      port: 443,
      path: '/api/v2/connections',
      method: 'POST',
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
        console.log(`GitHub Connection Status: ${res.statusCode}`);
        if (res.statusCode === 201) {
          console.log('✅ GitHub connection created successfully!');
          resolve(JSON.parse(data));
        } else if (res.statusCode === 409) {
          console.log('ℹ️  GitHub connection already exists');
          resolve({ message: 'Connection already exists' });
        } else {
          console.log('Response:', data);
          reject(new Error(`Connection creation failed: ${res.statusCode} - ${data}`));
        }
      });
    });

    req.on('error', reject);
    req.write(connectionData);
    req.end();
  });
}

async function updateApplicationSettings(token) {
  return new Promise((resolve, reject) => {
    const appData = JSON.stringify({
      callbacks: [
        'http://localhost:3000/ar/auth/callback',
        'http://localhost:3000/en/auth/callback'
      ],
      allowed_logout_urls: [
        'http://localhost:3000/ar',
        'http://localhost:3000/en',
        'http://localhost:3000'
      ],
      web_origins: [
        'http://localhost:3000'
      ],
      allowed_origins: [
        'http://localhost:3000'
      ]
    });

    const options = {
      hostname: AUTH0_DOMAIN,
      port: 443,
      path: '/api/v2/clients/h4NPegjClDuYxZefNBeXIhqXbu9SV6aC',
      method: 'PATCH',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(appData)
      }
    };

    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', (chunk) => data += chunk);
      res.on('end', () => {
        console.log(`Application Update Status: ${res.statusCode}`);
        if (res.statusCode === 200) {
          console.log('✅ Application settings updated successfully!');
          resolve(JSON.parse(data));
        } else {
          console.log('Response:', data);
          reject(new Error(`Application update failed: ${res.statusCode} - ${data}`));
        }
      });
    });

    req.on('error', reject);
    req.write(appData);
    req.end();
  });
}

async function main() {
  try {
    console.log('🔧 Configuring Auth0 with GitHub OAuth...');
    console.log('==========================================');
    
    console.log('1. Getting Management API token...');
    const token = await getManagementToken();
    console.log('✅ Management token obtained');

    console.log('\n2. Creating GitHub social connection...');
    await createGitHubConnection(token);

    console.log('\n3. Updating application settings...');
    await updateApplicationSettings(token);

    console.log('\n🎉 Auth0 configuration completed successfully!');
    console.log('\n🧪 Test your authentication:');
    console.log('   1. Start dev server: npm run dev');
    console.log('   2. Visit: http://localhost:3000/ar/auth/login');
    console.log('   3. Click "Login with GitHub"');
    console.log('   4. Enjoy your new assets dashboard!');

  } catch (error) {
    console.error('❌ Configuration failed:', error.message);
  }
}

main();
