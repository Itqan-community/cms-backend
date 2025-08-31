# Auth0 GitHub Social Connection Configuration

## Step 1: Add GitHub Social Connection in Auth0

1. Go to: https://manage.auth0.com
2. Navigate to: Authentication → Social
3. Click: "Create Connection"
4. Select: "GitHub"

## Step 2: Enter GitHub OAuth App Credentials

Client ID: 0v23liemrfSQLjWQeZZo
Client Secret: ce6c555e9c78ce86f8f5ebd3dd336cf930ea6433

## Step 3: Enable Connection
- Make sure to enable this connection for your application
- The connection should be named "github"

## Step 4: Verify Auth0 Application Settings

Go to Applications → Your Application → Settings and ensure:

Allowed Callback URLs:
http://localhost:3000/ar/auth/callback,http://localhost:3000/en/auth/callback

Allowed Logout URLs:
http://localhost:3000/ar,http://localhost:3000/en,http://localhost:3000

Allowed Web Origins:
http://localhost:3000

Allowed Origins (CORS):
http://localhost:3000

## Step 5: Test Configuration
After saving, test at: http://localhost:3000/ar/auth/login
