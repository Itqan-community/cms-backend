export const environment = {
  production: true,
  apiUrl: 'https://api.itqan.com/api/v1',
  auth0: {
    domain: 'your-auth0-domain.auth0.com', // TODO: Set your Auth0 domain
    clientId: 'your-client-id', // TODO: Set your Auth0 client ID
    audience: 'https://api.itqan.com',
    redirectUri: 'https://cms.itqan.com/callback',
    scope: 'openid profile email'
  }
};
