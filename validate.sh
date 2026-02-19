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
if [ -z "${TARGET_PAT:-}" ]; then
  echo "ERROR: TARGET_PAT environment variable is not set."
  exit 1
fi

git config --global credential.helper store
TARGET_HOST=$(echo "$TARGET_REPO" | awk -F/ '{print $3}')
echo "https://${TARGET_USERNAME}:${TARGET_PAT}@${TARGET_HOST}" > ~/.git-credentials
chmod 600 ~/.git-credentials

# ── Helper: compute patch-id ──────────────────────────────────────────────────
get_patch_id() {
  local repo_dir=$1
  local commit=$2

  git -C "$repo_dir" diff-tree -p "$commit" -- . "${EXCLUDE_PATHS[@]}" \
    | git patch-id --stable \
    | awk '{print $1}'
}

# ── Cleanup trap ──────────────────────────────────────────────────────────────
WORKDIR=$(mktemp -d)
trap 'rm -rf "$WORKDIR"' EXIT

# ── Clone source repo and get the parent commit (before MR changes) ───────────
echo "==> Cloning source repo..."
git clone --quiet --no-tags --branch "$BRANCH" "$SOURCE_REPO" "$WORKDIR/source"

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

SOURCE_PATCH_ID=$(get_patch_id "$WORKDIR/source" "$SOURCE_BASE_COMMIT")

if [ -z "$SOURCE_PATCH_ID" ]; then
  echo "WARNING: Source base commit has no code changes (after excluding config files)."
  SOURCE_PATCH_ID="empty"
fi

echo "==> Source patch-id: $SOURCE_PATCH_ID"

# ── Clone target repo and get latest commit ───────────────────────────────────
echo "==> Cloning target (client) repo..."
git clone --quiet --no-tags --branch "$BRANCH" "$TARGET_REPO" "$WORKDIR/target"

# Get the latest commit hash from target repo
TARGET_LATEST_COMMIT=$(git -C "$WORKDIR/target" rev-parse HEAD)
echo "==> Target latest commit: $TARGET_LATEST_COMMIT"

TARGET_PATCH_ID=$(get_patch_id "$WORKDIR/target" "$TARGET_LATEST_COMMIT")

if [ -z "$TARGET_PATCH_ID" ]; then
  echo "WARNING: Target commit has no code changes (after excluding config files)."
  TARGET_PATCH_ID="empty"
fi

echo "==> Target patch-id: $TARGET_PATCH_ID"

# ── Compare patch-ids ──────────────────────────────────────────────────────────
if [ "$TARGET_PATCH_ID" = "$SOURCE_PATCH_ID" ]; then
  echo ""
  echo "✅ Validation PASSED - Repos are in sync."
  echo "   Source base commit : $SOURCE_BASE_COMMIT"
  echo "   Target latest commit: $TARGET_LATEST_COMMIT"
  echo "   Matching patch-id   : $SOURCE_PATCH_ID"
  echo ""
  echo "   ➜ Safe to merge changes to main."
  exit 0
else
  echo ""
  echo "❌ Validation FAILED - Target repo has diverged from source!"
  echo "   Source base commit  : $SOURCE_BASE_COMMIT (patch-id: $SOURCE_PATCH_ID)"
  echo "   Target latest commit: $TARGET_LATEST_COMMIT (patch-id: $TARGET_PATCH_ID)"
  echo ""
  echo "   ⚠️  The target (client) repo has changes that don't match the source repo."
  echo "   ⚠️  This MR cannot be merged until repos are synchronized."
  echo ""
  echo "==> Differences in source base commit (excluding configs):"
  git -C "$WORKDIR/source" diff-tree -p --stat "$SOURCE_BASE_COMMIT" -- . "${EXCLUDE_PATHS[@]}" || true
  echo ""
  echo "==> Differences in target latest commit (excluding configs):"
  git -C "$WORKDIR/target" diff-tree -p --stat "$TARGET_LATEST_COMMIT" -- . "${EXCLUDE_PATHS[@]}" || true
  exit 1
fi
