/** @type {import('next').NextConfig} */
const nextConfig = {
  env: {
    NEXT_PUBLIC_STRAPI_URL: process.env.NEXT_PUBLIC_STRAPI_URL,
    NEXT_PUBLIC_STRAPI_API_URL: process.env.NEXT_PUBLIC_STRAPI_API_URL,
  },
  images: {
    remotePatterns: [
      {
        protocol: 'http',
        hostname: 'localhost',
        port: '1337',
        pathname: '/uploads/**',
      },
      {
        protocol: 'http',
        hostname: 'minio',
        port: '9000',
        pathname: '/**',
      },
    ],
  },
  i18n: {
    locales: ['en', 'ar'],
    defaultLocale: 'en',
    localeDetection: false,
  },
};

module.exports = nextConfig;
