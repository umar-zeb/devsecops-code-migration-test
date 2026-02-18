#!/bin/bash

# Usage: push.sh <original_repo_url> <client_repo_url> <branch> <original_commit> <new_branch>

if [ $# -lt 5 ]; then
  echo "Usage: $0 <original_repo_url> <client_repo_url> <branch> <original_commit> <new_branch>"
  exit 1
fi

ORIGINAL_REPO=$1
CLIENT_REPO=$2  # e.g., https://gitlab.com/group/project.git (no auth in URL)
BRANCH=$3
ORIGINAL_COMMIT=$4
NEW_BRANCH=$5

# Set up global credential helper (use 'store' for persistent; 'cache' for temp with --timeout=3600)
git config --global credential.helper store

# Provide credentials once (username/email and PAT/password); Git will store them in ~/.git-credentials
# Format: https://username:password@host
# For GitLab PAT: username can be 'oauth2' or your email, password is PAT
echo "https://${CLIENT_USERNAME}:${CLIENT_PAT}@${CLIENT_REPO#https://}" > ~/.git-credentials  # CLIENT_USERNAME from env (e.g., your email or 'oauth2')

# Now Git will use these for any operations on $CLIENT_REPO

# Clone original
git clone $ORIGINAL_REPO original-temp
cd original-temp
git fetch origin

# Switch to the commit
git checkout $ORIGINAL_COMMIT

# Remove configs using git filter-repo (rewrites history to remove them)
git filter-repo --invert-paths --path-glob '.github/*' --path CODEOWNERS --path .gitattributes --force

# Add client remote (plain URL, no embedded auth—helper handles it)
git remote add client $CLIENT_REPO
git fetch client

# Create new branch from client's current branch
git checkout -b $NEW_BRANCH client/$BRANCH

# Cherry-pick the commit, but discard any config changes (since filtered, should be clean)
git cherry-pick --no-commit $ORIGINAL_COMMIT
git checkout HEAD -- .github/ CODEOWNERS .gitattributes  # Safety revert if any slipped through
git commit -m "Pushed code changes from original commit: $ORIGINAL_COMMIT (configs removed)"

# Push the new branch (auth handled by helper)
git push client $NEW_BRANCH

cd ..
rm -rf original-temp

echo "Push complete: New branch pushed."