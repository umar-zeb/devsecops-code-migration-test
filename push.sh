#!/bin/bash

# Usage: push.sh <original_repo_url> <client_repo_url> <branch> <original_commit> <new_branch>

if [ $# -lt 5 ]; then
  echo "Usage: $0 <original_repo_url> <client_repo_url> <branch> <original_commit> <new_branch>"
  exit 1
fi

ORIGINAL_REPO=$1
CLIENT_REPO=$2
BRANCH=$3
ORIGINAL_COMMIT=$4
NEW_BRANCH=$5

# Clone original
git clone $ORIGINAL_REPO original-temp
cd original-temp
git fetch origin

# Switch to the commit
git checkout $ORIGINAL_COMMIT

# Remove configs using git filter-repo (rewrites history to remove them)
git filter-repo --invert-paths --path-glob '.github/*' --path CODEOWNERS --path .gitattributes --force

# Add client remote with auth (assuming GitHub or git-compatible SCM)
CLIENT_URL=$(echo $CLIENT_REPO | sed 's/https:\/\//https:\/\/x:${CLIENT_PAT}@/')
git remote add client $CLIENT_URL
git fetch client

# Create new branch from client's current branch
git checkout -b $NEW_BRANCH client/$BRANCH

# Cherry-pick the commit, but discard any config changes (since filtered, should be clean)
git cherry-pick --no-commit $ORIGINAL_COMMIT
git checkout HEAD -- .github/ CODEOWNERS .gitattributes  # Safety revert if any slipped through
git commit -m "Pushed code changes from original PR commit: $ORIGINAL_COMMIT (configs removed)"

# Push the new branch
git push client $NEW_BRANCH

# Create PR in client repo (GitHub-specific; adapt for other SCM)
CLIENT_OWNER_REPO=${CLIENT_REPO#https://github.com/}
CLIENT_OWNER_REPO=${CLIENT_OWNER_REPO%.git}
gh pr create --repo $CLIENT_OWNER_REPO --head $NEW_BRANCH --base $BRANCH --title "Automated code update from original PR" --body "Pushing code changes (excluding configs) from original commit $ORIGINAL_COMMIT"

cd ..
rm -rf original-temp

echo "Push complete: New branch pushed and PR created in target repo."
