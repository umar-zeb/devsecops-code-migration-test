#!/bin/bash

# Usage: validate.sh <source_repo_url> <target_repo_url> <branch>
# Requires: GITHUB_SHA environment variable (the MR/PR commit being merged)

set -euo pipefail

if [ $# -lt 3 ]; then
  echo "Usage: $0 <source_repo_url> <target_repo_url> <branch>"
  echo "Requires: GITHUB_SHA environment variable (current PR/MR commit)"
  exit 1
fi

SOURCE_REPO=$1
TARGET_REPO=$2
BRANCH=$3
TARGET_USERNAME="${TARGET_USERNAME:-superdesk_support@superdesk.solutions}"

# Get current MR/PR commit from environment (GitHub Actions sets this automatically)
if [ -z "${GITHUB_SHA:-}" ]; then
  echo "ERROR: GITHUB_SHA environment variable is not set."
  exit 1
fi

# Paths to exclude from patch comparison (config files only)
EXCLUDE_PATHS=(
  ":(exclude).github/"
  ":(exclude)CODEOWNERS"
  ":(exclude).gitattributes"
  ":(exclude).gitignore"
  ":(exclude)validate.sh"
  ":(exclude)push.sh"
)

# ── Credentials ────────────────────────────────────────────────────────────────
if [ -z "${CLIENT_PAT:-}" ]; then
  echo "ERROR: CLIENT_PAT environment variable is not set."
  exit 1
fi

git config --global credential.helper store
TARGET_HOST=$(echo "$TARGET_REPO" | awk -F/ '{print $3}')
echo "https://${TARGET_USERNAME}:${CLIENT_PAT}@${TARGET_HOST}" > ~/.git-credentials
chmod 600 ~/.git-credentials

# ── Helper: compute hash of entire codebase at a commit ──────────────────────
get_tree_hash() {
  local repo_dir=$1
  local commit=$2

  # Generate a diff of the entire tree against empty tree (shows all files)
  # Then hash it to get a stable identifier for the codebase state
  git -C "$repo_dir" diff-tree -p "$commit" 4b825dc642cb6eb9a060e54bf8d69288fbee4904 -- . "${EXCLUDE_PATHS[@]}" \
    | git hash-object --stdin
}

# ── Cleanup trap ──────────────────────────────────────────────────────────────
WORKDIR=$(mktemp -d)
trap 'rm -rf "$WORKDIR"' EXIT

# ── Clone source repo and get the parent commit (before MR changes) ───────────
# This removes "https://" from the start of SOURCE_REPO and adds credentials
AUTH_SOURCE_REPO="https://${TARGET_USERNAME}:${CLIENT_PAT}@${SOURCE_REPO#https://}"

echo "==> Cloning source repo..."
git clone --quiet --no-tags --branch "$BRANCH" "$AUTH_SOURCE_REPO" "$WORKDIR/source"

# Fetch the MR commit
git -C "$WORKDIR/source" fetch --quiet --depth=2 origin "$GITHUB_SHA"
git -C "$WORKDIR/source" checkout --quiet FETCH_HEAD

# Get the parent commit (the commit before this MR's changes)
SOURCE_BASE_COMMIT=$(git -C "$WORKDIR/source" rev-parse HEAD^)

if [ -z "$SOURCE_BASE_COMMIT" ]; then
  echo "ERROR: Could not determine parent commit of $GITHUB_SHA."
  exit 1
fi

echo "==> Source base commit (before MR): $SOURCE_BASE_COMMIT"

SOURCE_TREE_HASH=$(get_tree_hash "$WORKDIR/source" "$SOURCE_BASE_COMMIT")

if [ -z "$SOURCE_TREE_HASH" ]; then
  echo "ERROR: Could not compute tree hash for source base commit."
  exit 1
fi

echo "==> Source codebase hash: $SOURCE_TREE_HASH"

# ── Clone target repo and get latest commit ───────────────────────────────────
echo "==> Cloning target (client) repo..."
git clone --quiet --no-tags --branch "$BRANCH" "$TARGET_REPO" "$WORKDIR/target"

# Get the latest commit hash from target repo
TARGET_LATEST_COMMIT=$(git -C "$WORKDIR/target" rev-parse HEAD)
echo "==> Target latest commit: $TARGET_LATEST_COMMIT"

TARGET_TREE_HASH=$(get_tree_hash "$WORKDIR/target" "$TARGET_LATEST_COMMIT")

if [ -z "$TARGET_TREE_HASH" ]; then
  echo "ERROR: Could not compute tree hash for target commit."
  exit 1
fi

echo "==> Target codebase hash: $TARGET_TREE_HASH"

# ── Compare codebase hashes ───────────────────────────────────────────────────
if [ "$TARGET_TREE_HASH" = "$SOURCE_TREE_HASH" ]; then
  echo ""
  echo "✅ Validation PASSED - Entire codebases are identical."
  echo "   Source base commit : $SOURCE_BASE_COMMIT"
  echo "   Target latest commit: $TARGET_LATEST_COMMIT"
  echo "   Matching tree hash  : $SOURCE_TREE_HASH"
  echo ""
  echo "   ➜ Safe to merge changes to main."
  exit 0
else
  echo ""
  echo "❌ Validation FAILED - Codebases do not match!"
  echo "   Source base commit  : $SOURCE_BASE_COMMIT (hash: $SOURCE_TREE_HASH)"
  echo "   Target latest commit: $TARGET_LATEST_COMMIT (hash: $TARGET_TREE_HASH)"
  echo ""
  echo "   ⚠️  The target (client) repo codebase differs from source repo."
  echo "   ⚠️  This MR cannot be merged until repos are synchronized."
  echo ""
  echo "==> Source codebase state (excluding configs):"
  git -C "$WORKDIR/source" ls-tree -r --name-only "$SOURCE_BASE_COMMIT" | grep -v -E '^\.github/|^CODEOWNERS$|^\.gitattributes$|^\.gitignore$|^validate\.sh$|^push\.sh$' | head -20
  echo "   ... (showing first 20 files)"
  echo ""
  echo "==> Target codebase state (excluding configs):"
  git -C "$WORKDIR/target" ls-tree -r --name-only "$TARGET_LATEST_COMMIT" | grep -v -E '^\.github/|^CODEOWNERS$|^\.gitattributes$|^\.gitignore$|^validate\.sh$|^push\.sh$' | head -20
  echo "   ... (showing first 20 files)"
  exit 1
fi
