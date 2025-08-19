# 🤖 Auth0 Automated Setup Options

## **Option 1: Management API Script (Recommended)**

### **Step 1: Create M2M Application First**
1. **Go to**: https://manage.auth0.com/dashboard
2. **Click**: "Applications" → "Create Application"  
3. **Name**: `Itqan CMS Management`
4. **Type**: `Machine to Machine Applications`
5. **Authorize**: Select "Auth0 Management API"
6. **Scopes**: Select ALL scopes (or minimum: `create:clients`, `read:clients`, `create:connections`, `create:resource_servers`)
7. **Copy**: Domain, Client ID, Client Secret

### **Step 2: Run Automated Setup**
```bash
# Set your Auth0 M2M credentials
export AUTH0_DOMAIN=your-domain.auth0.com
export AUTH0_M2M_CLIENT_ID=your_m2m_client_id  
export AUTH0_M2M_CLIENT_SECRET=your_m2m_client_secret

# Optional: Add GitHub OAuth credentials
export GITHUB_CLIENT_ID=your_github_client_id
export GITHUB_CLIENT_SECRET=your_github_client_secret

# Run the automated setup
node setup-auth0-automated.js
```

### **What It Does Automatically:**
- ✅ Creates SPA Application
- ✅ Creates API Resource (https://api.itqan.com)
- ✅ Sets up GitHub Social Connection (if credentials provided)
- ✅ Configures Universal Login Branding
- ✅ Generates `.env.local` file with all credentials
- ✅ Creates test script for immediate testing

---

## **Option 2: Auth0 Deploy CLI**

### **Step 1: Initialize Deploy CLI**
```bash
# Login to Auth0
auth0-deploy-cli login

# Initialize configuration  
auth0-deploy-cli init
```

### **Step 2: Deploy Configuration**
```bash
# Deploy the predefined configuration
auth0-deploy-cli deploy --input auth0-config.json
```

---

## **Option 3: Quick Manual Setup (2 Minutes)**

If you prefer manual setup, just follow these 3 essential steps:

### **1. Create SPA Application**
- **URL**: https://manage.auth0.com/dashboard/applications
- **Type**: Single Page Application
- **Callbacks**: `http://localhost:3000/api/auth/callback`

### **2. Create API**  
- **URL**: https://manage.auth0.com/dashboard/apis
- **Identifier**: `https://api.itqan.com`
- **Algorithm**: RS256

### **3. Set Environment Variables**
```bash
cd web
cat > .env.local << EOF
AUTH0_SECRET=$(node -e "console.log(require('crypto').randomBytes(64).toString('hex'))")
AUTH0_BASE_URL=http://localhost:3000
AUTH0_ISSUER_BASE_URL=https://your-domain.auth0.com
AUTH0_CLIENT_ID=your_spa_client_id
AUTH0_CLIENT_SECRET=your_spa_client_secret
AUTH0_AUDIENCE=https://api.itqan.com
EOF
```

---

## **🧪 Testing After Setup**

Regardless of which option you choose, test with:

```bash
# Start the app with Auth0 configured
cd web && npm run dev

# Test endpoints
curl -i http://localhost:3000/register
curl -i http://localhost:3000/api/auth/login
curl -i http://localhost:3000/api/auth/login?connection=github
```

**Visit**: http://localhost:3000/register and click GitHub login!

---

## **🔑 Why Use Automation?**

### **Manual Setup Pain Points:**
- ❌ 15+ clicks through Auth0 dashboard
- ❌ Easy to miss configurations
- ❌ Manual copy/paste of credentials  
- ❌ Prone to typos and errors
- ❌ Need to repeat for different environments

### **Automated Setup Benefits:**
- ✅ **2-minute setup** vs 15+ minutes manual
- ✅ **Zero configuration errors** - everything consistent
- ✅ **Repeatable** across environments (dev/staging/prod)
- ✅ **Version controlled** configuration
- ✅ **Instant testing** with generated scripts
- ✅ **No missed settings** - comprehensive setup

---

## **📋 What You Need to Provide**

### **For Full Automation (Option 1):**
```bash
AUTH0_DOMAIN=your-domain.auth0.com          # From Auth0 tenant
AUTH0_M2M_CLIENT_ID=xxx                     # From M2M app  
AUTH0_M2M_CLIENT_SECRET=xxx                 # From M2M app
GITHUB_CLIENT_ID=xxx                        # From GitHub OAuth app (optional)
GITHUB_CLIENT_SECRET=xxx                    # From GitHub OAuth app (optional)
```

### **For Manual Setup (Option 3):**
```bash
AUTH0_DOMAIN=your-domain.auth0.com          # From Auth0 tenant
AUTH0_CLIENT_ID=xxx                         # From SPA app
AUTH0_CLIENT_SECRET=xxx                     # From SPA app (if any)
```

---

## **🚀 Recommended Flow**

1. **Create Auth0 account** (if needed): https://auth0.com
2. **Choose Option 1** (Management API) for full automation
3. **Create M2M app** with Management API access
4. **Set environment variables** and run `node setup-auth0-automated.js`
5. **Test immediately** with generated script
6. **Deploy to production** by updating environment variables

**Total Time**: ~5 minutes for complete Auth0 setup vs ~20 minutes manual!
