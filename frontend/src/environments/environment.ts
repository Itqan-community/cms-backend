export const environment = {
  production: false,
  apiUrl: 'http://localhost:8000/api/v1',
  auth0: {
    domain: 'dev-itqan.eu.auth0.com',
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
    supportedLanguages: ['ar', 'en', 'ur', 'fr', 'id', 'tr'],
    quranicFonts: ['Amiri', 'Scheherazade New', 'Noto Sans Arabic'],
    enableHijriCalendar: true,
    enablePrayerTimes: false // Future feature
  },
  cdn: {
    baseUrl: 'http://localhost:9000', // MinIO for development
    audioPath: '/audio',
    imagesPath: '/images',
    documentsPath: '/documents'
  }
};
