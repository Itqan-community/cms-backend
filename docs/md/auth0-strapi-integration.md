# Auth0-Strapi CMS Integration Flow

## 📋 Task Overview
- **Task Number**: Auth0-Strapi Integration
- **Title**: Implement seamless user registration flow between Auth0 and Strapi CMS
- **Status**: In Progress
- **Date**: 2025-08-19

### Integration Objectives
- Users register via http://localhost:3000/register page
- Authentication handled by Auth0 (including GitHub/Google SSO)
- User records created in Strapi CMS backend
- Seamless synchronization between Auth0 and Strapi

## ✅ Current Implementation Status

### 1. Registration Form (Frontend)
**Location**: `web/app/register/page.tsx`
**Status**: ✅ WORKING

**Features**:
- Clean Bootstrap-styled registration form
- Fields: First Name, Last Name, Phone, Title, Email, Password
- Social login buttons (GitHub, Google)
- Redirects to Auth0 Universal Login on submission

**Form Flow**:
```javascript
// Form submission triggers Auth0 redirect
window.location.href = `/api/auth/login?${params.toString()}`;
// Where params include screen_hint=signup and login_hint=email
```

### 2. Auth0 Integration (Authentication)
**Location**: `web/app/api/auth/[...auth0]/route.ts`
**Status**: ✅ WORKING

**Features**:
- Next.js 14 App Router compatible
- Handles Auth0 Universal Login flow
- Implements `afterCallback` hook for Strapi integration
- Supports GitHub and Google social connections

**Auth0 Configuration**:
```typescript
export const GET = handleAuth({
  login: handleLogin({
    authorizationParams: {
      audience: process.env.AUTH0_AUDIENCE,
      scope: 'openid profile email',
    },
  }),
  callback: handleCallback({ afterCallback }),
});
```

**After Callback Hook**:
```typescript
const afterCallback = async (req: any, session: any, state: any) => {
  const user = session.user;
  
  try {
    // Call Strapi to create/update user record
    const response = await fetch(`${process.env.NEXT_PUBLIC_STRAPI_API_URL}/auth/callback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
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
    }
  } catch (error) {
    console.error('Error calling Strapi auth callback:', error);
  }

  return session;
};
```

### 3. Strapi Backend Integration
**Location**: `cms/src/api/auth/controllers/auth.ts`
**Status**: ✅ IMPLEMENTED (Pending Strapi startup)

**Features**:
- Auth0 callback endpoint: `POST /api/auth/callback`
- User registration endpoint: `POST /api/auth/register`
- Automatic user creation in Strapi database
- JWT token generation for Strapi sessions
- Extended user model with Auth0 fields

**User Model Extensions**:
```json
{
  "auth0_id": { "type": "string", "unique": true },
  "first_name": { "type": "string" },
  "last_name": { "type": "string" },
  "phone": { "type": "string" },
  "title": { "type": "string" }
}
```

**Callback Controller Logic**:
```typescript
async callback(ctx) {
  // 1. Verify Auth0 token
  const auth0Response = await axios.get(`https://${process.env.AUTH0_DOMAIN}/userinfo`, {
    headers: { Authorization: `Bearer ${accessToken}` }
  });

  // 2. Find or create user in Strapi
  let user = await strapi.db.query('plugin::users-permissions.user').findOne({
    where: { auth0_id: auth0User.sub }
  });

  if (!user) {
    // Create new user with Auth0 data
    user = await strapi.db.query('plugin::users-permissions.user').create({
      data: {
        username: auth0User.nickname || auth0User.email.split('@')[0],
        email: auth0User.email,
        auth0_id: auth0User.sub,
        confirmed: auth0User.email_verified || false,
        role: defaultRole.id,
        provider: 'auth0',
      }
    });
  }

  // 3. Generate Strapi JWT
  const jwt = strapi.plugins['users-permissions'].services.jwt.issue({
    id: user.id,
    email: user.email,
  });

  // 4. Return user and JWT
  ctx.send({ jwt, user });
}
```

## 🧪 Testing Results

### Registration Flow Test
```bash
./test-registration-flow.sh
```

**Results**:
- ✅ Registration page: Working (200 OK)
- ✅ Auth0 redirect: Working (302 to auth0.com)
- ⚠️ Strapi health: Building (waiting for startup)
- ✅ Auth0 user creation: Working
- ⚠️ Strapi integration: Pending service readiness

### Individual Component Tests

**1. Registration Page**:
```bash
curl -I http://localhost:3000/register
# Result: HTTP/1.1 200 OK ✅
```

**2. Auth0 Signup Redirect**:
```bash
curl -I "http://localhost:3000/api/auth/login?screen_hint=signup&login_hint=test@example.com"
# Result: HTTP/1.1 302 Found (Location: auth0.com/authorize...) ✅
```

**3. Auth0 User Creation**:
```bash
# Management API user creation working ✅
# User ID: auth0|68a450a248f1f9c0723014ae
```

**4. Database Integration**:
```bash
# PostgreSQL users table exists ✅
# Previous test user verified in database ✅
```

## 🔄 Complete Registration Flow

### For Regular Email Signup:
1. **User visits** `http://localhost:3000/register`
2. **Fills form** with personal details (First Name, Last Name, Phone, Title, Email, Password)
3. **Clicks "Sign Up"** → Redirects to Auth0 Universal Login
4. **Auth0 handles** email verification and account creation
5. **Successful login** triggers `afterCallback` in Next.js
6. **Next.js calls** Strapi `/api/auth/callback` endpoint
7. **Strapi creates** user record with Auth0 ID mapping
8. **User redirected** to dashboard with both Auth0 and Strapi sessions

### For Social Signup (GitHub/Google):
1. **User visits** `http://localhost:3000/register`
2. **Clicks GitHub/Google** button
3. **Auth0 handles** social authentication
4. **Same callback flow** as email signup (steps 5-8)

## 🏗️ Infrastructure Status

### Services Status
| Service | Status | Port | Notes |
|---------|--------|------|-------|
| Next.js | ✅ Running | 3000 | Registration page accessible |
| Auth0 | ✅ Working | - | Redirects and user creation working |
| PostgreSQL | ✅ Running | 5432 | Database tables ready |
| MinIO | ✅ Running | 9000-9001 | File storage ready |
| Meilisearch | ✅ Running | 7700 | Search service ready |
| Strapi | ⚠️ Building | 1337 | Admin dependencies installing |

### Environment Variables
```bash
# Auth0 Configuration
AUTH0_SECRET=19affe0d8d26ad09d3d7ad6e114c4016f1a081fed6f15963b515a698cb24e852e9e1abb9f1fd86d611471cb199423a0a6e332b5dcba3db1d93d8c980ada1c3ec
AUTH0_BASE_URL=http://localhost:3000
AUTH0_ISSUER_BASE_URL=https://dev-sit2vmj3hni4smep.us.auth0.com
AUTH0_CLIENT_ID=eal0fzibkFLUT89WK0C5g2BFuBaGqMfA
AUTH0_AUDIENCE=https://api.itqan.com

# Strapi Integration
NEXT_PUBLIC_STRAPI_API_URL=http://localhost:1337/api
```

## 🎯 Next Steps

### Immediate Tasks
1. **Complete Strapi startup** - Admin dependencies are still installing
2. **Test full integration** - Run complete Auth0 → Strapi flow
3. **Verify user data mapping** - Ensure all form fields sync to Strapi
4. **Test social login** - Verify GitHub/Google signup creates Strapi users

### Integration Testing
```bash
# Once Strapi is ready:
curl -X POST http://localhost:1337/api/auth/callback \
  -H "Content-Type: application/json" \
  -d '{
    "auth0_id": "auth0|test123",
    "email": "test@example.com",
    "username": "test-user"
  }'
```

### User Experience Flow
1. **Registration Form** → **Auth0 Universal Login** → **Dashboard**
2. **All user data** synchronized between Auth0 and Strapi
3. **Single session** for both authentication and CMS access
4. **Social logins** work seamlessly with same flow

## 📊 Integration Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   User Browser  │    │   Next.js App   │    │   Auth0 Tenant  │
│                 │    │                 │    │                 │
│ /register form  │───▶│ Auth0 redirect  │───▶│ Universal Login │
│                 │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │ afterCallback   │    │ User Created    │
                       │ Hook            │    │ in Auth0        │
                       └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │ Strapi API      │    │ PostgreSQL DB   │
                       │ /auth/callback  │───▶│ User Record     │
                       │                 │    │ Created         │
                       └─────────────────┘    └─────────────────┘
```

## 🔧 Key Implementation Features

### Security
- **Auth0 token verification** before Strapi user creation
- **Unique Auth0 ID mapping** prevents duplicate accounts
- **JWT tokens** for Strapi session management
- **Role-based access** with default 'authenticated' role

### Data Synchronization
- **Automatic user creation** on first Auth0 login
- **User profile updates** sync between systems
- **Email verification status** passed from Auth0 to Strapi
- **Additional user fields** (phone, title) stored in Strapi

### Error Handling
- **Graceful fallbacks** if Strapi is unavailable
- **Logging** for debugging integration issues
- **User feedback** for authentication failures

---

**Implementation Status**: Auth0 integration complete, Strapi integration implemented (pending service startup)  
**Date**: 2025-08-19  
**Next Phase**: Complete end-to-end testing once Strapi is running
