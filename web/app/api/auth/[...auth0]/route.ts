import { handleAuth, handleLogin, handleCallback } from '@auth0/nextjs-auth0';

const afterCallback = async (req: any, session: any, state: any) => {
  // Extract user info from session
  const user = session.user;
  
  try {
    // Call Strapi to create/update user record
    const response = await fetch(`${process.env.NEXT_PUBLIC_STRAPI_API_URL}/auth/callback`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        accessToken: session.accessToken,
        idToken: session.idToken,
        auth0_id: user.sub,
        email: user.email,
        username: user.nickname || user.email?.split('@')[0],
      }),
    });

    if (response.ok) {
      const strapiData = await response.json();
      // Store Strapi JWT in session for API calls
      session.strapiJwt = strapiData.jwt;
      session.strapiUser = strapiData.user;
    } else {
      console.error('Failed to create Strapi user:', await response.text());
    }
  } catch (error) {
    console.error('Error calling Strapi auth callback:', error);
  }

  return session;
};

export const GET = handleAuth({
  login: handleLogin({
    authorizationParams: {
      audience: process.env.AUTH0_AUDIENCE,
      scope: 'openid profile email',
    },
  }),
  callback: handleCallback({ afterCallback }),
});

export const POST = GET;
