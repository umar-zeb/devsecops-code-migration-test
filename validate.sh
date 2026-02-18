#!/bin/bash

# Usage: validate.sh <original_repo_url> <client_repo_url> <branch>
# Requires: SOURCE_COMMIT_SHA environment variable

set -euo pipefail

if [ $# -lt 3 ]; then
  echo "Usage: $0 <original_repo_url> <client_repo_url> <branch>"
  echo "Requires: SOURCE_COMMIT_SHA environment variable"
  exit 1
fi

ORIGINAL_REPO=$1
CLIENT_REPO=$2
BRANCH=$3
CLIENT_USERNAME="${CLIENT_USERNAME:-superdesk_support@superdesk.solutions}"

# Get source commit from environment
if [ -z "${SOURCE_COMMIT_SHA:-}" ]; then
  echo "ERROR: SOURCE_COMMIT_SHA environment variable is not set."
  exit 1
fi

# Paths to exclude from patch comparison
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
CLIENT_HOST=$(echo "$CLIENT_REPO" | awk -F/ '{print $3}')
echo "https://${CLIENT_USERNAME}:${CLIENT_PAT}@${CLIENT_HOST}" > ~/.git-credentials
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

# ── Clone original repo and get patch-id of source commit ─────────────────────
echo "==> Cloning original repo..."
git clone --quiet --no-tags --branch "$BRANCH" "$ORIGINAL_REPO" "$WORKDIR/original"
git -C "$WORKDIR/original" fetch --quiet --depth=1 origin "$SOURCE_COMMIT_SHA"
git -C "$WORKDIR/original" checkout --quiet FETCH_HEAD

ORIGINAL_PATCH_ID=$(get_patch_id "$WORKDIR/original" "$SOURCE_COMMIT_SHA")

if [ -z "$ORIGINAL_PATCH_ID" ]; then
  echo "ERROR: Could not compute patch-id for commit $SOURCE_COMMIT_SHA."
  exit 1
fi

echo "==> Source patch-id: $ORIGINAL_PATCH_ID (from $SOURCE_COMMIT_SHA)"

# ── Clone client repo and get latest commit ───────────────────────────────────
echo "==> Cloning client repo..."
git clone --quiet --no-tags --branch "$BRANCH" "$CLIENT_REPO" "$WORKDIR/client"

# Get the latest commit hash
LATEST_CLIENT_COMMIT=$(git -C "$WORKDIR/client" rev-parse HEAD)
echo "==> Latest client commit: $LATEST_CLIENT_COMMIT"

CLIENT_PATCH_ID=$(get_patch_id "$WORKDIR/client" "$LATEST_CLIENT_COMMIT")

if [ -z "$CLIENT_PATCH_ID" ]; then
  echo "ERROR: Could not compute patch-id for client commit $LATEST_CLIENT_COMMIT."
  exit 1
fi

echo "==> Client patch-id: $CLIENT_PATCH_ID"

# ── Compare ────────────────────────────────────────────────────────────────────
if [ "$CLIENT_PATCH_ID" = "$ORIGINAL_PATCH_ID" ]; then
  echo ""
  echo "✅ Validation PASSED."
  echo "   Source commit : $SOURCE_COMMIT_SHA"
  echo "   Client commit : $LATEST_CLIENT_COMMIT"
  echo "   Patch-id      : $ORIGINAL_PATCH_ID"
  exit 0
else
  echo ""
  echo "❌ Validation FAILED — patch-ids do not match."
  echo "   Source commit : $SOURCE_COMMIT_SHA (patch-id: $ORIGINAL_PATCH_ID)"
  echo "   Client commit : $LATEST_CLIENT_COMMIT (patch-id: $CLIENT_PATCH_ID)"
  echo ""
  echo "==> Source change (code only, configs excluded):"
  git -C "$WORKDIR/original" diff-tree -p --stat "$SOURCE_COMMIT_SHA" -- . "${EXCLUDE_PATHS[@]}"
  exit 1
fi