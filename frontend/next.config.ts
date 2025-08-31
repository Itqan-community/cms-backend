import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Enable experimental features for better i18n support
  experimental: {
    // Enable optimized package imports
    optimizePackageImports: ['lucide-react'],
  },
  
  // Configure redirects to default to Arabic
  async redirects() {
    return [
      {
        source: '/',
        destination: '/ar',
        permanent: false,
      },
    ];
  },
  
  // Configure rewrites for clean URLs
  async rewrites() {
    return [
      {
        source: '/sitemap.xml',
        destination: '/ar/sitemap.xml',
      },
    ];
  },
};

export default nextConfig;