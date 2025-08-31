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

async function updateGitHubConnection(token) {
  return new Promise((resolve, reject) => {
    const connectionData = JSON.stringify({
      options: {
        client_id: '0v23liemrfSQLjWQeZZo',
        client_secret: 'ce6c555e9c78ce86f8f5ebd3dd336cf930ea6433',
        scope: ['user:email', 'read:user']
      }
    });

    const options = {
      hostname: AUTH0_DOMAIN,
      port: 443,
      path: '/api/v2/connections/github',
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
          console.log('✅ GitHub connection updated with new credentials!');
          resolve(JSON.parse(data));
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
    console.log('🔄 Updating GitHub connection with new credentials...');
    const token = await getManagementToken();
    await updateGitHubConnection(token);
    console.log('🎉 GitHub connection updated successfully!');
  } catch (error) {
    console.error('❌ Update failed:', error.message);
  }
}

main();
