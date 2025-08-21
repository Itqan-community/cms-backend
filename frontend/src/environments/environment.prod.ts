export const environment = {
  production: true,
  apiUrl: 'https://api.itqan-cms.com/api/v1', // Production API URL
  auth0: {
    domain: 'itqan-cms.auth0.com', // Production Auth0 domain
    clientId: 'production-client-id', // Will be set via environment variables
    audience: 'https://itqan-cms-api',
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
    baseUrl: 'https://cdn.itqan-cms.com', // Alibaba OSS CDN
    audioPath: '/audio',
    imagesPath: '/images',
    documentsPath: '/documents'
  }
};
