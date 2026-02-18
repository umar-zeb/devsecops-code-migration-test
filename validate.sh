#!/bin/bash

# Usage: validate.sh <original_repo_url> <client_repo_url> <branch>

set -euo pipefail

if [ $# -lt 3 ]; then
  echo "Usage: $0 <original_repo_url> <client_repo_url> <branch>"
  exit 1
fi

ORIGINAL_REPO=$1
CLIENT_REPO=$2
BRANCH=$3

# Get the original commit SHA from environment (set by GitHub Actions)
if [ -z "${GITHUB_SHA:-}" ]; then
  echo "ERROR: GITHUB_SHA environment variable is not set."
  exit 1
fi

ORIGINAL_COMMIT=$GITHUB_SHA
CLIENT_USERNAME="${CLIENT_USERNAME:-superdesk_support@superdesk.solutions}"

# Paths to exclude from patch comparison (code-only validation)
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

# Extract host from CLIENT_REPO URL (e.g., https://gitlab.com/org/repo → gitlab.com)
CLIENT_HOST=$(echo "$CLIENT_REPO" | awk -F/ '{print $3}')
echo "https://${CLIENT_USERNAME}:${CLIENT_PAT}@${CLIENT_HOST}" > ~/.git-credentials
chmod 600 ~/.git-credentials

# ── Helper: compute a stable diff-only hash for a commit ──────────────────────
# git patch-id --stable strips commit metadata so cherry-picks match.
# We pipe through `git diff-tree` instead of `git show` to get a clean patch.
get_patch_id() {
  local repo_dir=$1
  local commit=$2

  # diff-tree -p produces a pure diff without commit message headers,
  # which is exactly what git patch-id expects.
  git -C "$repo_dir" diff-tree -p "$commit" -- . "${EXCLUDE_PATHS[@]}" \
    | git patch-id --stable \
    | awk '{print $1}'
}

# ── Cleanup trap ──────────────────────────────────────────────────────────────
WORKDIR=$(mktemp -d)
trap 'rm -rf "$WORKDIR"' EXIT

# ── Clone original repo and get the patch-id of the target commit ─────────────
echo "==> Cloning original repo..."
git clone --quiet --no-tags --branch "$BRANCH" "$ORIGINAL_REPO" "$WORKDIR/original"

# Fetch the specific commit (works even if it's not the branch tip)
git -C "$WORKDIR/original" fetch --quiet --depth=1 origin "$ORIGINAL_COMMIT"
git -C "$WORKDIR/original" checkout --quiet FETCH_HEAD

ORIGINAL_PATCH_ID=$(get_patch_id "$WORKDIR/original" "$ORIGINAL_COMMIT")

if [ -z "$ORIGINAL_PATCH_ID" ]; then
  echo "ERROR: Could not compute patch-id for commit $ORIGINAL_COMMIT."
  echo "The commit may be empty after applying path exclusions."
  exit 1
fi

echo "==> Target patch-id: $ORIGINAL_PATCH_ID"

# ── Clone client repo and get latest commit ───────────────────────────────────
echo "==> Cloning client repo..."
git clone --quiet --no-tags --branch main "$CLIENT_REPO" "$WORKDIR/client"

# Get the latest commit ID
CLIENT_COMMIT=$(git -C "$WORKDIR/client" rev-parse HEAD)
CLIENT_PATCH_ID=$(get_patch_id "$WORKDIR/client" "$CLIENT_COMMIT")

# ── Report ─────────────────────────────────────────────────────────────────────
if [ "$CLIENT_PATCH_ID" = "$ORIGINAL_PATCH_ID" ]; then
  echo ""
  echo "✅ Validation PASSED."
  echo "   Original commit : $ORIGINAL_COMMIT"
  echo "   Client commit   : $CLIENT_COMMIT"
  echo "   Patch-id        : $ORIGINAL_PATCH_ID"
  exit 0
else
  echo ""
  echo "❌ Validation FAILED — change not found in client repo."
  echo "   Original commit : $ORIGINAL_COMMIT"
  echo "   Client commit   : $CLIENT_COMMIT"
  echo "   Original patch-id: $ORIGINAL_PATCH_ID"
  echo "   Client patch-id  : $CLIENT_PATCH_ID"
  echo ""
  echo "==> Diff of the missing change (code only, configs excluded):"
  git -C "$WORKDIR/original" diff-tree -p --stat "$ORIGINAL_COMMIT" -- . "${EXCLUDE_PATHS[@]}"
  exit 1
fi