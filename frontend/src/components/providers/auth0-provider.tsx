"use client";

import { Auth0Provider } from '@auth0/auth0-react';
import { env } from '@/lib/env';

interface Auth0ProviderWrapperProps {
  children: React.ReactNode;
}

export function Auth0ProviderWrapper({ children }: Auth0ProviderWrapperProps) {
  // Get the callback URL based on current locale
  const getCallbackUrl = () => {
    if (typeof window !== 'undefined') {
      const currentPath = window.location.pathname;
      const locale = currentPath.startsWith('/ar') ? 'ar' : 'en';
      return `${window.location.origin}/${locale}/auth/callback`;
    }
    return `${env.NEXT_PUBLIC_APP_URL}/en/auth/callback`;
  };

  return (
    <Auth0Provider
      domain={env.NEXT_PUBLIC_AUTH0_DOMAIN}
      clientId={env.NEXT_PUBLIC_AUTH0_CLIENT_ID}
      authorizationParams={{
        redirect_uri: getCallbackUrl(),
        scope: 'openid profile email offline_access',
        audience: env.NEXT_PUBLIC_AUTH0_AUDIENCE,
      }}
      useRefreshTokens={true}
      cacheLocation="localstorage"
    >
      {children}
    </Auth0Provider>
  );
}
