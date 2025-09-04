#!/bin/bash
# Pre-push hook to validate branch flow rules locally
# Install: cp .github/pre-push-hook.sh .git/hooks/pre-push && chmod +x .git/hooks/pre-push

echo "🔍 Validating branch flow rules before push..."

# Get current branch and remote branch being pushed to
current_branch=$(git rev-parse --abbrev-ref HEAD)
remote_ref=$(echo $1 | cut -d'/' -f3)

echo "   Pushing: $current_branch → $remote_ref"

# Rule 1: Only staging can push to main
if [[ "$remote_ref" == "main" && "$current_branch" != "staging" ]]; then
    echo "❌ ERROR: Production (main) can only be updated from staging branch"
    echo "   Attempted: $current_branch → main"
    echo "   Required: staging → main"
    echo "   Use: git checkout staging && git merge $current_branch"
    exit 1
fi

# Rule 2: Only develop can push to staging  
if [[ "$remote_ref" == "staging" && "$current_branch" != "develop" ]]; then
    echo "❌ ERROR: Staging can only be updated from develop branch"
    echo "   Attempted: $current_branch → staging"
    echo "   Required: develop → staging"
    echo "   Use: git checkout develop && git merge $current_branch"
    exit 1
fi

echo "✅ Branch flow rules validated successfully"
exit 0
