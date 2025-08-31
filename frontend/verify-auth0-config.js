// Auth0 Configuration Verification Script
const config = {
  domain: process.env.NEXT_PUBLIC_AUTH0_DOMAIN || 'dev-itqan.eu.auth0.com',
  clientId: process.env.NEXT_PUBLIC_AUTH0_CLIENT_ID || 'h4NPegjClDuYxZefNBeXIhqXbu9SV6aC',
  audience: process.env.NEXT_PUBLIC_AUTH0_AUDIENCE || 'https://api.itqan-cms.com'
};

console.log('🔍 Auth0 Configuration Verification');
console.log('=====================================');
console.log(`Domain: ${config.domain}`);
console.log(`Client ID: ${config.clientId}`);
console.log(`Audience: ${config.audience}`);
console.log('');
console.log('✅ Next Steps:');
console.log('1. Create GitHub OAuth App at: https://github.com/settings/applications/new');
console.log('2. Use callback URL: https://dev-itqan.eu.auth0.com/login/callback');
console.log('3. Configure Auth0 Social Connection with GitHub credentials');
console.log('4. Update Auth0 Application URLs with localhost:3000 callbacks');
