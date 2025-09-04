# Branch Protection Rules Configuration

This document outlines the branch protection rules that should be configured in GitHub repository settings to enforce proper deployment flow.

## Required GitHub Repository Settings

### 1. Main Branch (Production)
- **Branch name pattern**: `main`
- **Restrict pushes that create files**: ✅ Enabled
- **Restrict force pushes**: ✅ Enabled  
- **Allow deletions**: ❌ Disabled
- **Require pull request reviews before merging**: ✅ Enabled
  - **Required number of reviewers**: 1
  - **Dismiss stale reviews when new commits are pushed**: ✅ Enabled
  - **Require review from code owners**: ✅ Enabled (if CODEOWNERS file exists)
- **Require status checks to pass before merging**: ✅ Enabled
  - **Require branches to be up to date before merging**: ✅ Enabled
- **Require conversation resolution before merging**: ✅ Enabled
- **Require signed commits**: ❌ Disabled (optional)
- **Require linear history**: ✅ Enabled
- **Include administrators**: ✅ Enabled
- **Allow specified actors to bypass required pull requests**: ❌ Disabled

### 2. Staging Branch (Pre-production)
- **Branch name pattern**: `staging`
- **Restrict pushes that create files**: ✅ Enabled
- **Restrict force pushes**: ✅ Enabled
- **Allow deletions**: ❌ Disabled
- **Require pull request reviews before merging**: ✅ Enabled
  - **Required number of reviewers**: 1
  - **Dismiss stale reviews when new commits are pushed**: ✅ Enabled
- **Require status checks to pass before merging**: ✅ Enabled
  - **Require branches to be up to date before merging**: ✅ Enabled
- **Require conversation resolution before merging**: ✅ Enabled
- **Require linear history**: ✅ Enabled
- **Include administrators**: ✅ Enabled

### 3. Develop Branch (Development)
- **Branch name pattern**: `develop`
- **Restrict pushes that create files**: ❌ Disabled (allow direct commits for development)
- **Restrict force pushes**: ✅ Enabled
- **Allow deletions**: ❌ Disabled
- **Require pull request reviews before merging**: ❌ Disabled (optional for feature branches)
- **Include administrators**: ❌ Disabled (allow admin override for hotfixes)

## Deployment Flow Enforcement

The above rules combined with the GitHub Actions workflow ensure:

1. **develop → staging**: Only through pull requests with review
2. **staging → main**: Only through pull requests with review  
3. **Direct pushes**: Only allowed to develop branch
4. **Deployment triggers**: Only on successful PR merges or manual dispatch (develop only)

## Setup Instructions

### For GitHub Organization/Enterprise Accounts:
1. Go to GitHub repository → Settings → Branches
2. Click "Add rule" for each branch above
3. Configure each rule according to the specifications
4. Ensure the Deploy workflow is properly configured
5. Test the flow with a sample PR

### For Personal/Team Accounts (Alternative):
1. **Use GitHub Actions enforcement** (already configured in `deploy.yml`)
2. **Install pre-push hook** for local validation:
   ```bash
   cp .github/pre-push-hook.sh .git/hooks/pre-push
   chmod +x .git/hooks/pre-push
   ```
3. **Follow manual process discipline**:
   - Always create PRs for staging/main updates
   - Never push directly to staging/main branches
   - Use the workflow validation as safety net

## Branch Flow Validation

The GitHub Actions workflow (`deploy.yml`) includes automatic validation:
- ✅ Prevents staging updates from any branch except develop  
- ✅ Prevents main updates from any branch except staging
- ✅ Allows manual deployment only for develop branch
- ✅ Validates PR merge events before deployment

## Emergency Procedures

In case of critical production issues:
1. **Hotfix to develop**: Push directly to develop, deploy via manual trigger
2. **Bypass protection**: Administrators can temporarily disable protection rules
3. **Rollback**: Use manual deployment trigger with previous commit hash

## Monitoring

Monitor deployment compliance through:
- GitHub Actions workflow logs
- Pull request merge history  
- Branch protection rule violations (if any)
