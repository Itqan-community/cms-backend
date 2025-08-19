# 🔐 Auth0 Complete Setup Guide for Itqan CMS

## 📊 **Current Database Status**

### ✅ **Created Users in itqan-postgres Database:**

```sql
-- Users Table
 id |         email          | first_name | last_name |         created_at         
----+------------------------+------------+-----------+----------------------------
  1 | ahmed.test@example.com | Ahmed      | AlRajhy   | 2025-08-19 08:04:33.882891
```

**Test User Successfully Created:**
- **📧 Email**: ahmed.test@example.com
- **👤 Name**: Ahmed AlRajhy  
- **🗓️ Created**: 2025-08-19 via cURL testing
- **✅ Status**: Ready for Auth0 integration

---

## 🚀 **Auth0 Tenant Setup (Step-by-Step)**

### **Step 1: Create Auth0 Account & Tenant**

1. **Visit Auth0**: Go to [https://auth0.com](https://auth0.com)
2. **Sign Up**: Create a free account (if you don't have one)
3. **Create Tenant**: 
   - **Tenant Name**: `itqan-cms` (or your preferred name)
   - **Region**: Choose closest to your users
   - **Environment**: `Development` (for now)

### **Step 2: Create SPA Application**

1. **Dashboard** → **Applications** → **Create Application**
2. **Settings**:
   - **Name**: `Itqan CMS Web App`
   - **Type**: `Single Page Application` (SPA)
   - **Technology**: `React`

3. **Application Settings**:
   ```
   Domain: YOUR_DOMAIN.auth0.com
   Client ID: [Auto-generated]
   Client Secret: [Auto-generated for SPA]
   ```

4. **Application URIs**:
   ```
   Allowed Callback URLs: http://localhost:3000/api/auth/callback
   Allowed Logout URLs: http://localhost:3000
   Allowed Web Origins: http://localhost:3000
   Allowed Origins (CORS): http://localhost:3000
   ```

### **Step 3: Configure GitHub Social Connection**

1. **Authentication** → **Social** → **Create Connection**
2. **Select GitHub**
3. **GitHub OAuth App Setup**:
   
   #### **3a. Create GitHub OAuth App:**
   - Go to **GitHub** → **Settings** → **Developer settings** → **OAuth Apps**
   - **New OAuth App**:
     ```
     Application name: Itqan CMS Development
     Homepage URL: http://localhost:3000
     Authorization callback URL: https://YOUR_DOMAIN.auth0.com/login/callback
     ```
   
   #### **3b. Configure in Auth0:**
   ```
   Client ID: [From GitHub OAuth App]
   Client Secret: [From GitHub OAuth App]
   Attributes: email, name, login, avatar_url
   Sync user profile: ON
   ```

4. **Enable for Applications**: Select your `Itqan CMS Web App`

### **Step 4: Configure Universal Login**

1. **Branding** → **Universal Login**
2. **Custom Login Page**: Enable
3. **Logo**: Upload Itqan logo
4. **Colors**:
   ```
   Primary Color: #669B80
   Page Background: #FFFFFF
   ```

### **Step 5: Create Machine-to-Machine Application**

1. **Applications** → **Create Application**
2. **Settings**:
   - **Name**: `Itqan CMS Strapi Integration`
   - **Type**: `Machine to Machine Applications`
   - **Authorize**: Select default API

### **Step 6: Configure API & Audience**

1. **Applications** → **APIs** → **Create API**
2. **Settings**:
   ```
   Name: Itqan CMS API
   Identifier: https://api.itqan.com
   Signing Algorithm: RS256
   ```

---

## 🔧 **Environment Variables Configuration**

### **Step 7: Update Your Environment Variables**

Create a `.env.local` file in the `/web` directory:

```bash
# Auth0 Configuration (Replace with your actual values)
AUTH0_SECRET=use_a_long_random_value_64_characters_long_minimum_for_security
AUTH0_BASE_URL=http://localhost:3000
AUTH0_ISSUER_BASE_URL=https://YOUR_DOMAIN.auth0.com
AUTH0_CLIENT_ID=your_spa_client_id_from_auth0
AUTH0_CLIENT_SECRET=your_spa_client_secret_from_auth0
AUTH0_AUDIENCE=https://api.itqan.com

# Optional: Force GitHub as primary login
AUTH0_LOGIN_CONNECTION=github
```

### **Step 8: Generate AUTH0_SECRET**

Run this command to generate a secure secret:

```bash
node -e "console.log(require('crypto').randomBytes(64).toString('hex'))"
```

---

## 🧪 **Testing the Setup**

### **Step 9: Test Authentication Flow**

1. **Stop current Next.js if running**:
   ```bash
   # Stop the background process in web directory
   ps aux | grep "npm run dev" | grep -v grep
   ```

2. **Start with Auth0 configured**:
   ```bash
   cd web
   AUTH0_SECRET=your_generated_secret \
   AUTH0_BASE_URL=http://localhost:3000 \
   AUTH0_ISSUER_BASE_URL=https://YOUR_DOMAIN.auth0.com \
   AUTH0_CLIENT_ID=your_client_id \
   AUTH0_CLIENT_SECRET=your_client_secret \
   AUTH0_AUDIENCE=https://api.itqan.com \
   npm run dev
   ```

3. **Test Complete Flow**:
   ```bash
   # Test registration page
   curl -i http://localhost:3000/register
   
   # Test Auth0 login redirect (should now redirect to Auth0)
   curl -L http://localhost:3000/api/auth/login
   
   # Test GitHub SSO
   curl -L http://localhost:3000/api/auth/login?connection=github
   ```

---

## 🔄 **Complete User Registration Flow**

### **How It Works After Setup:**

1. **User visits** `/register` ✅ (Working)
2. **User fills form** with personal data ✅ (Working) 
3. **Form submits** and redirects to Auth0 ✅ (Ready)
4. **Auth0 shows** GitHub/Google login options 🔄 (After setup)
5. **User authenticates** via GitHub 🔄 (After setup)
6. **Auth0 redirects** to `/api/auth/callback` 🔄 (After setup)
7. **Callback creates** Strapi user record 🔄 (After setup)
8. **User redirected** to `/dashboard` 🔄 (After setup)

### **Current Status:**
- ✅ **Form Collection**: User data captured (Ahmed AlRajhy)
- ✅ **Database**: PostgreSQL ready with users table
- ⏳ **Auth0 Setup**: Requires configuration (this guide)
- ⏳ **Strapi Integration**: Will work after Auth0 + package fixes

---

## 🎯 **Next Steps After Auth0 Setup**

1. **Complete this Auth0 configuration**
2. **Test the full authentication flow**
3. **Fix Strapi package versions and integration**
4. **Connect Strapi to sync with Auth0 users**
5. **Implement the dashboard with user data**

---

## 🆘 **Quick Setup Command**

Once you have your Auth0 credentials, run this single command to test:

```bash
cd web && \
AUTH0_SECRET=$(node -e "console.log(require('crypto').randomBytes(64).toString('hex'))") \
AUTH0_BASE_URL=http://localhost:3000 \
AUTH0_ISSUER_BASE_URL=https://YOUR_DOMAIN.auth0.com \
AUTH0_CLIENT_ID=your_client_id \
AUTH0_CLIENT_SECRET=your_client_secret \
AUTH0_AUDIENCE=https://api.itqan.com \
npm run dev
```

Then visit: **http://localhost:3000/register** and click the GitHub login button!

---

**🔗 Need Help?** Check the detailed setup in `TASK1_AUTH0_SETUP.md` or refer to [Auth0 Documentation](https://auth0.com/docs/quickstart/spa/react)
