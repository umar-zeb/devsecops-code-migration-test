#!/bin/bash

# Usage: validate.sh <original_repo_url> <client_repo_url> <branch> <original_commit>

set -euo pipefail

if [ $# -lt 4 ]; then
  echo "Usage: $0 <original_repo_url> <client_repo_url> <branch> <original_commit>"
  exit 1
fi

ORIGINAL_REPO=$1
CLIENT_REPO=$2
BRANCH=$3
ORIGINAL_COMMIT=$4
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

# ── Clone client repo and search recent commits for a matching patch-id ────────
echo "==> Cloning client repo..."
git clone --quiet --no-tags --branch "$BRANCH" "$CLIENT_REPO" "$WORKDIR/client"

# Deepen the clone to cover enough history (increase if needed)
git -C "$WORKDIR/client" fetch --quiet --depth=100 origin "$BRANCH"

MATCH_FOUND=false
MATCH_COMMIT=""

echo "==> Scanning last 100 commits in client repo..."
while IFS= read -r commit; do
  CLIENT_PATCH_ID=$(get_patch_id "$WORKDIR/client" "$commit")
  if [ "$CLIENT_PATCH_ID" = "$ORIGINAL_PATCH_ID" ]; then
    MATCH_FOUND=true
    MATCH_COMMIT="$commit"
    break
  fi
done < <(git -C "$WORKDIR/client" rev-list --max-count=100 "origin/$BRANCH")

# ── Report ─────────────────────────────────────────────────────────────────────
if $MATCH_FOUND; then
  echo ""
  echo "✅ Validation PASSED."
  echo "   Original commit : $ORIGINAL_COMMIT"
  echo "   Matched commit  : $MATCH_COMMIT"
  echo "   Patch-id        : $ORIGINAL_PATCH_ID"
  exit 0
else
  echo ""
  echo "❌ Validation FAILED — change not found in client repo."
  echo "   Original commit : $ORIGINAL_COMMIT"
  echo "   Patch-id        : $ORIGINAL_PATCH_ID"
  echo ""
  echo "==> Diff of the missing change (code only, configs excluded):"
  git -C "$WORKDIR/original" diff-tree -p --stat "$ORIGINAL_COMMIT" -- . "${EXCLUDE_PATHS[@]}"
  exit 1
fi