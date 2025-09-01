# 1 – User Registration (Auth0 Setup Guide)

**Date:** 2024-12-15  
**Author:** Itqan CMS Team  

## Overview
Comprehensive manual setup instructions for Auth0 tenant configuration including SPA application creation, API resource setup, and social connection configuration for the Itqan CMS authentication system.

## Objectives
- Create and configure Auth0 tenant
- Set up SPA application with proper callbacks
- Configure API resources and scopes
- Enable GitHub and Google social connections
- Generate environment configuration

## Implementation Details

### 1. Create Auth0 Tenant
1. Go to [Auth0 Dashboard](https://manage.auth0.com/)
2. Create a new tenant named `itqan-cms-dev`

### 2. Configure Application (SPA)
1. Create new application: "Itqan CMS Web"
2. Type: Single Page Application
3. **Allowed Callback URLs**: `http://localhost:3000/api/auth/callback`
4. **Allowed Logout URLs**: `http://localhost:3000`
5. **Allowed Web Origins**: `http://localhost:3000`

### 3. Configure GitHub SSO
1. Go to Connections → Social
2. Enable GitHub connection
3. Configure GitHub OAuth App:
   - Homepage URL: `http://localhost:3000`
   - Authorization callback URL: `https://YOUR_AUTH0_DOMAIN/login/callback`
4. Add GitHub Client ID and Secret to Auth0

### 4. Configure Google OAuth (Secondary)
1. Go to Connections → Social  
2. Enable Google connection
3. Configure Google OAuth 2.0:
   - Authorized redirect URIs: `https://YOUR_AUTH0_DOMAIN/login/callback`

### 5. Create M2M Application
1. Create new application: "Itqan CMS Backend"
2. Type: Machine to Machine
3. Authorize for Auth0 Management API
4. Grant scopes: `read:users`, `create:users`, `update:users`

### 6. Customize Universal Login
1. Go to Branding → Universal Login
2. Customize colors:
   - Primary: `#669B80`
   - Page Background: `#22433D`
3. Upload Itqan logo

### 7. Environment Variables
Copy these values to your `.env.dev` file:

```bash
# Auth0 Configuration
AUTH0_DOMAIN=your-tenant.auth0.com
AUTH0_CLIENT_ID=your-spa-client-id
AUTH0_CLIENT_SECRET=your-spa-client-secret
AUTH0_AUDIENCE=https://api.itqan.com
AUTH0_SCOPE=openid profile email

# Machine-to-Machine for Strapi
AUTH0_M2M_CLIENT_ID=your-m2m-client-id
AUTH0_M2M_CLIENT_SECRET=your-m2m-client-secret

# Next.js Auth0
AUTH0_SECRET=a-32-character-secret-for-sessions
AUTH0_BASE_URL=http://localhost:3000
```

## Testing Checklist

- [ ] GitHub SSO redirects to Auth0 Universal Login
- [ ] Login with GitHub creates user in Strapi database  
- [ ] User is redirected to dashboard after registration
- [ ] New user has 'authenticated' role in Strapi
- [ ] Auth0 user_id is stored in Strapi user record
- [ ] Strapi JWT is issued for API access

## Implementation Files Created

### Strapi Backend:
- `cms/config/database.ts` - PostgreSQL connection
- `cms/config/plugins.ts` - Upload, i18n, Meilisearch, Users & Permissions
- `cms/src/api/auth/controllers/auth.ts` - Auth0 integration controller
- `cms/src/api/auth/routes/auth.ts` - Auth callback routes

### Next.js Frontend:
- `web/app/register/page.tsx` - Registration page (REG-001)
- `web/app/dashboard/page.tsx` - Dashboard after login (DASH-001)
- `web/app/api/auth/[...auth0]/route.ts` - Auth0 NextJS integration
- `web/app/layout.tsx` - Auth0 UserProvider wrapper

### Styling:
- `web/app/globals.css` - Itqan brand colors and Auth0 customization
- Bootstrap 5.3 integration with Itqan color scheme

## Next Steps
1. Set up Auth0 tenant with above configuration
2. Update `.env.dev` with actual Auth0 credentials  
3. Run `docker compose up --build` to test integration
4. Test GitHub SSO registration flow end-to-end
