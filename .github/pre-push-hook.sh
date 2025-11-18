#!/bin/bash
# Pre-push hook to validate branch flow rules locally
# Install: cp .github/pre-push-hook.sh .git/hooks/pre-push && chmod +x .git/hooks/pre-push

echo "🔍 Validating branch flow rules before push..."

# Get current branch and parse push arguments
current_branch=$(git rev-parse --abbrev-ref HEAD)

# Parse git push arguments to get target branch
while read local_ref local_sha remote_ref remote_sha; do
    remote_branch=$(echo $remote_ref | sed 's/refs\/heads\///')
done

echo "   Pushing: $current_branch → $remote_branch"

# Rule 1: Only staging can push to main
if [[ "$remote_branch" == "main" && "$current_branch" != "staging" ]]; then
    echo "❌ ERROR: Production (main) can only be updated from staging branch"
    echo "   Attempted: $current_branch → main"
    echo "   Required: staging → main"
    echo "   Use: git checkout staging && git merge $current_branch"
    exit 1
fi

# Rule 2: Only develop can push to staging
if [[ "$remote_branch" == "staging" && "$current_branch" != "develop" ]]; then
    echo "❌ ERROR: Staging can only be updated from develop branch"
    echo "   Attempted: $current_branch → staging"
    echo "   Required: develop → staging"
    echo "   Use: git checkout develop && git merge $current_branch"
    exit 1
fi

echo "✅ Branch flow rules validated successfully"
exit 0
