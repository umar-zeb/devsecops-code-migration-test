#!/bin/bash

# Usage: validate.sh <original_repo_url> <client_repo_url> <branch> <original_commit>

if [ $# -lt 4 ]; then
  echo "Usage: $0 <original_repo_url> <client_repo_url> <branch> <original_commit>"
  exit 1
fi

ORIGINAL_REPO=$1
CLIENT_REPO=$2
BRANCH=$3
ORIGINAL_COMMIT=$4

EXCLUDE_PATHS=":!.github/ :!CODEOWNERS :!.gitattributes"  # Add more excludes as needed

# Clone original shallow for the commit
git clone --depth=1 --branch $BRANCH $ORIGINAL_REPO original-temp
cd original-temp
git fetch origin $ORIGINAL_COMMIT
ORIGINAL_PATCH_ID=$(git show $ORIGINAL_COMMIT -- . $EXCLUDE_PATHS | git patch-id | awk '{print $1}')
cd ..
rm -rf original-temp

# Clone client shallow
git clone --depth=100 --branch $BRANCH $CLIENT_REPO client-temp
cd client-temp
git fetch origin --depth=100

MATCH_FOUND=false
for commit in $(git rev-list --max-count=100 $BRANCH); do
  CLIENT_PATCH_ID=$(git show $commit -- . $EXCLUDE_PATHS | git patch-id | awk '{print $1}')
  if [ "$CLIENT_PATCH_ID" = "$ORIGINAL_PATCH_ID" ]; then
    MATCH_FOUND=true
    break
  fi
done

cd ..
rm -rf client-temp

if $MATCH_FOUND; then
  echo "Validation passed. Code change from original commit $ORIGINAL_COMMIT already applied in client's repo (matching filtered patch-id: $ORIGINAL_PATCH_ID)."
  exit 0
else
  # Explain the changes (show the filtered diff of the missing change)
  git clone --depth=1 --branch $BRANCH $ORIGINAL_REPO original-temp
  cd original-temp
  git fetch origin $ORIGINAL_COMMIT
  echo "Validation failed. The target does not match the source (code change not found in client)."
  echo "Here are the changes in the code (filtered to ignore configs):"
  git show $ORIGINAL_COMMIT -- . $EXCLUDE_PATHS
  cd ..
  rm -rf original-temp
  exit 1
fi
