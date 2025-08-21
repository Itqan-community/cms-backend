export const environment = {
  production: true,
  apiUrl: 'https://cms.itqan.dev/api/v1', // Production API URL
  auth0: {
    domain: 'dev-itqan.eu.auth0.com', // Production Auth0 domain
    clientId: "h4NPegjClDuYxZefNBeXIhqXbu9SV6aC",
    audience: 'https://api.cms.itqan.dev',
    redirectUri: `${window.location.origin}/auth/callback`,
    scope: 'openid profile email read:current_user update:current_user_metadata'
  },
  features: {
    enableAnalytics: true,
    enableNotifications: true,
    enableRealTimeUpdates: true,
    enableAdvancedSearch: true
  },
  islamic: {
    defaultReciter: 'Abdul Rahman Al-Sudais',
    supportedLanguages: ['ar', 'en', 'ur', 'fr', 'id', 'tr', 'ms', 'bn'],
    quranicFonts: ['Amiri', 'Scheherazade New', 'Noto Sans Arabic', 'IBM Plex Sans Arabic'],
    enableHijriCalendar: true,
    enablePrayerTimes: true // Enable in production
  },
  cdn: {
    baseUrl: 'https://cdn.cms.itqan.dev', // Alibaba OSS CDN
    audioPath: '/audio',
    imagesPath: '/images',
    documentsPath: '/documents'
  }
};
