export const environment = {
  production: false,
  apiUrl: 'http://localhost:8000/api/v1',
  auth0: {
    domain: 'your-auth0-domain.auth0.com', // TODO: Set your Auth0 domain
    clientId: 'your-client-id', // TODO: Set your Auth0 client ID
    audience: 'https://api.itqan.com',
    redirectUri: 'http://localhost:4200/callback',
    scope: 'openid profile email'
  }
};
