const https = require('https');

const AUTH0_DOMAIN = 'dev-itqan.eu.auth0.com';
const CLIENT_ID = 'RYjndDR2mlvnWKAqFNi5bqGh1J9ig00L';
const CLIENT_SECRET = 'CDuYPjJkckJpktrQkccH7iYAu_WQJCVzhnxk_8NWlgkwN3WslrH7FQtF4OZZCPsf';
const AUDIENCE = 'https://dev-itqan.eu.auth0.com/api/v2/';

// New GitHub OAuth App credentials
const NEW_GITHUB_CLIENT_ID = 'Ov23lizjfvLj3yehPx8M';
const NEW_GITHUB_CLIENT_SECRET = 'faef2bffb4e2b79d65f9b0a61ff52f94c6bcc686';

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

async function updateGitHubConnection(token) {
  return new Promise((resolve, reject) => {
    const connectionData = JSON.stringify({
      options: {
        client_id: NEW_GITHUB_CLIENT_ID,
        client_secret: NEW_GITHUB_CLIENT_SECRET,
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
        console.log(`GitHub Connection Update Status: ${res.statusCode}`);
        if (res.statusCode === 200) {
          const result = JSON.parse(data);
          console.log('✅ GitHub connection updated successfully!');
          console.log(`   New Client ID: ${result.options.client_id}`);
          console.log(`   Connection ID: ${result.id}`);
          resolve(result);
        } else {
          console.log('Response:', data);
          reject(new Error(`Connection update failed: ${res.statusCode}`));
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
    console.log('🔧 Updating GitHub OAuth Connection...');
    console.log('=====================================');
    console.log(`   Old Client ID: 0v23liemrfSQLjWQeZZo (suspended/deleted)`);
    console.log(`   New Client ID: ${NEW_GITHUB_CLIENT_ID}`);
    console.log('');
    
    const token = await getManagementToken();
    await updateGitHubConnection(token);
    
    console.log('\n🎉 GitHub OAuth App Updated Successfully!');
    console.log('\n🧪 Ready to Test:');
    console.log('1. Visit: http://localhost:3000/ar/auth/login');
    console.log('2. Click "Login with GitHub"');
    console.log('3. You should now see GitHub authorization page (no more 404!)');
    console.log('4. Authorize and you\'ll be redirected to your dashboard');
    
  } catch (error) {
    console.error('❌ Update failed:', error.message);
  }
}

main();
