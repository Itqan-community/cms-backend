# 34 – GitHub Actions Auto-Deployment Setup Guide

**Date:** 2025-09-01  
**Author:** AI Assistant  

## Overview
This guide explains how to manually add the GitHub Actions workflow for automatic deployment to your DigitalOcean environments.

## What the Auto-Deployment Does

### 🎯 **Automatic Triggers**
- **Push to `develop`** → Auto-deploys to `develop.api.cms.itqan.dev`
- **Push to `staging`** → Auto-deploys to `staging.api.cms.itqan.dev`  
- **Push to `main`** → Auto-deploys to `api.cms.itqan.dev`

### 🚀 **Deployment Process**
1. GitHub detects push to branch
2. Connects to correct DigitalOcean droplet via SSH
3. Pulls latest code (`git fetch` + `git reset --hard`)
4. Rebuilds Docker containers (`docker compose up -d --build`)
5. Performs health check
6. Cleans up old Docker images
7. Reports success/failure

## Manual Setup Instructions

### Step 1: Add the Workflow File

1. **Go to your GitHub repository**: https://github.com/Itqan-community/cms-backend
2. **Navigate to**: `.github/workflows/` directory
3. **Create new file**: Click "Add file" → "Create new file"
4. **Filename**: `deploy.yml`
5. **Copy the workflow content** from: `.github/workflows/deploy.yml` in this project

### Step 2: Verify GitHub Secrets

Ensure these secrets are configured in GitHub:
- Go to **Settings** → **Secrets and variables** → **Actions**
- Verify these secrets exist:

| Secret Name | Value | Description |
|-------------|-------|-------------|
| `DEVELOP_HOST` | `develop.api.cms.itqan.dev` | Development server |
| `STAGING_HOST` | `staging.api.cms.itqan.dev` | Staging server |
| `PROD_HOST` | `api.cms.itqan.dev` | Production server |
| `SSH_USER` | `root` | SSH username |
| `SSH_PRIVATE_KEY` | `[Your SSH private key]` | Private key for server access |

### Step 3: Test the Workflow

1. **Make a test change** to any branch (develop/staging/main)
2. **Push the change** to GitHub
3. **Watch the deployment** in GitHub → Actions tab
4. **Verify deployment** by visiting the corresponding URL

## Expected Workflow Behavior

### 🔄 **Development Workflow**
```bash
git checkout develop
git add .
git commit -m "Feature: Add new functionality"
git push origin develop
# ↓ GitHub Actions automatically deploys to develop.api.cms.itqan.dev
```

### 🚀 **Staging Workflow**  
```bash
git checkout staging
git merge develop
git push origin staging
# ↓ GitHub Actions automatically deploys to staging.api.cms.itqan.dev
```

### 🌟 **Production Workflow**
```bash
git checkout main
git merge staging
git push origin main
# ↓ GitHub Actions automatically deploys to api.cms.itqan.dev
```

## Troubleshooting

### ❌ **Common Issues**

1. **SSH Connection Failed**
   - Check `SSH_PRIVATE_KEY` is correct
   - Verify server hostnames in secrets

2. **Git Pull Failed**
   - Ensure GitHub token has repository access
   - Check if repository is accessible from droplets

3. **Docker Build Failed**
   - Check Docker service is running on droplets
   - Verify environment files exist

4. **Health Check Failed**
   - Normal if application takes time to start
   - Check container logs: `docker logs docker-web-1`

### 🔍 **Monitoring Deployments**

- **GitHub Actions**: Repository → Actions tab
- **Container Status**: `docker compose ps`
- **Application Logs**: `docker logs docker-web-1`
- **Caddy Logs**: `docker logs docker-caddy-1`

## Benefits of Auto-Deployment

✅ **Zero Manual Work**: Push code → Automatic deployment  
✅ **Consistent Process**: Same deployment steps every time  
✅ **Fast Feedback**: Know immediately if deployment fails  
✅ **Environment Parity**: Same process for all environments  
✅ **Audit Trail**: All deployments logged in GitHub Actions  

## Next Steps

1. Add the workflow file to GitHub
2. Test with a small change on staging
3. Once confirmed working, use for all deployments
4. Monitor Actions tab for deployment status

## Security Notes

- SSH private key is stored securely in GitHub Secrets
- Deployments only trigger from specific branches
- All deployment activity is logged and auditable
