export const environment = {
  production: false,
  environment: 'staging',
  apiUrl: 'https://staging.itqan.dev/api/v1',
  auth0: {
    domain: 'dev-itqan.eu.auth0.com',
    clientId: "h4NPegjClDuYxZefNBeXIhqXbu9SV6aC",
    audience: 'https://dev-itqan.eu.auth0.com/api/v2/',
    redirectUri: 'https://staging.itqan.dev/auth/callback',
    scope: 'openid profile email read:current_user update:current_user_metadata'
  },
  features: {
    enableAnalytics: true,
    enableNotifications: true,
    enableRealTimeUpdates: true,
    enableAdvancedSearch: true,
    enableDebugMode: false,
    enableBetaFeatures: true
  },
  islamic: {
    enableArabicRTL: true,
    defaultLanguage: 'en',
    enableIslamicCalendar: true,
    enableQuranicVerse: true,
    enableTafsir: true,
    enableTranslation: true
  },
  content: {
    enableContentVersioning: true,
    enableScholarlyReview: true,
    enableContentIntegrity: true,
    enableMultilingualContent: true
  }
};
