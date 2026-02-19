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

# ── Credentials ────────────────────────────────────────────────────────────────
if [ -z "${CLIENT_PAT:-}" ]; then
  echo "ERROR: CLIENT_PAT environment variable is not set."
  exit 1
fi

git config --global credential.helper store
TARGET_HOST=$(echo "$TARGET_REPO" | awk -F/ '{print $3}')
echo "https://${TARGET_USERNAME}:${CLIENT_PAT}@${TARGET_HOST}" > ~/.git-credentials
chmod 600 ~/.git-credentials

# ── Cleanup trap ──────────────────────────────────────────────────────────────
WORKDIR=$(mktemp -d)
trap 'rm -rf "$WORKDIR"' EXIT

# ── Use current repo (already checked out by GitHub Actions) ─────────────────
echo "==> Using current repository (already checked out)..."
echo ""
echo "==> BEFORE VALIDATION - Current directory contents:"
ls -la
echo ""

# Get the parent commit (the commit before this MR's changes)
SOURCE_BASE_COMMIT=$(git rev-parse HEAD^)

if [ -z "$SOURCE_BASE_COMMIT" ]; then
  echo "ERROR: Could not determine parent commit of $GITHUB_SHA."
  exit 1
fi

echo "==> Source base commit (before MR): $SOURCE_BASE_COMMIT"

# Export source tree to a clean directory (excluding configs)
echo "==> Exporting source codebase to temp directory..."
mkdir -p "$WORKDIR/source"
git archive "$SOURCE_BASE_COMMIT" | tar -x -C "$WORKDIR/source"

# Remove config files from source
rm -rf "$WORKDIR/source/.github" \
       "$WORKDIR/source/CODEOWNERS" \
       "$WORKDIR/source/.gitattributes" \
       "$WORKDIR/source/.gitignore" \
       "$WORKDIR/source/validate.sh" \
       "$WORKDIR/source/push.sh" 2>/dev/null || true

# List files in source after removing configs
echo "==> Source directory after removing configs:"
find "$WORKDIR/source" -type f | sort | tee "$WORKDIR/source_files.txt"
echo "==> Total files in source: $(wc -l < "$WORKDIR/source_files.txt")"
echo ""

# ── Clone target repo and get latest commit ───────────────────────────────────
# 1. URL-encode the @ in the email to %40 to prevent "Port number" errors
ENCODED_USER=${TARGET_USERNAME//@/%40}

# 2. Construct the GitLab URL using the token and the TARGET_REPO variable
AUTH_TARGET_REPO="https://${ENCODED_USER}:${CLIENT_PAT}@${TARGET_REPO#https://}"

echo "==> Cloning target (GitLab) repo..."
git clone --quiet --no-tags --branch "$BRANCH" "$AUTH_TARGET_REPO" "$WORKDIR/target_repo"

# Get the latest commit hash from target repo
TARGET_LATEST_COMMIT=$(git -C "$WORKDIR/target_repo" rev-parse HEAD)
echo "==> Target latest commit: $TARGET_LATEST_COMMIT"

# Export target tree to a clean directory (excluding configs)
echo "==> Exporting target codebase to temp directory..."
mkdir -p "$WORKDIR/target"
git -C "$WORKDIR/target_repo" archive "$TARGET_LATEST_COMMIT" | tar -x -C "$WORKDIR/target"

# Remove config files from target
rm -rf "$WORKDIR/target/.github" \
       "$WORKDIR/target/CODEOWNERS" \
       "$WORKDIR/target/.gitattributes" \
       "$WORKDIR/target/.gitignore" \
       "$WORKDIR/target/validate.sh" \
       "$WORKDIR/target/push.sh" 2>/dev/null || true

# List files in target after removing configs
echo "==> Target directory after removing configs:"
find "$WORKDIR/target" -type f | sort | tee "$WORKDIR/target_files.txt"
echo "==> Total files in target: $(wc -l < "$WORKDIR/target_files.txt")"
echo ""

# ── Compare codebases ──────────────────────────────────────────────────────────
echo "==> Comparing codebases..."
echo ""

# Normalize file lists (remove WORKDIR prefix for comparison)
sed "s|$WORKDIR/source/||" "$WORKDIR/source_files.txt" | sort > "$WORKDIR/source_list.txt"
sed "s|$WORKDIR/target/||" "$WORKDIR/target_files.txt" | sort > "$WORKDIR/target_list.txt"

# First compare file lists
if ! diff -q "$WORKDIR/source_list.txt" "$WORKDIR/target_list.txt" > /dev/null 2>&1; then
  echo "❌ Validation FAILED - Different files exist in the repos!"
  echo "   Source base commit  : $SOURCE_BASE_COMMIT"
  echo "   Target latest commit: $TARGET_LATEST_COMMIT"
  echo ""
  echo "==> Files only in source:"
  comm -23 "$WORKDIR/source_list.txt" "$WORKDIR/target_list.txt" | head -20
  echo ""
  echo "==> Files only in target:"
  comm -13 "$WORKDIR/source_list.txt" "$WORKDIR/target_list.txt" | head -20
  echo ""
  echo "==> AFTER VALIDATION - Directory listing:"
  ls -la
  exit 1
fi

echo "✓ File lists match ($(wc -l < "$WORKDIR/source_list.txt") files in each repo)"
echo ""

# Compare file contents using diff (ignoring whitespace)
echo "==> Comparing file contents (ignoring whitespace)..."
DIFF_FOUND=0
DIFF_COUNT=0

while IFS= read -r file; do
  SOURCE_FILE="$WORKDIR/source/$file"
  TARGET_FILE="$WORKDIR/target/$file"
  
  # Compare files ignoring all whitespace differences
  if ! diff -w -q "$SOURCE_FILE" "$TARGET_FILE" > /dev/null 2>&1; then
    if [ $DIFF_COUNT -eq 0 ]; then
      echo ""
      echo "❌ Validation FAILED - File contents differ!"
      echo "   Source base commit  : $SOURCE_BASE_COMMIT"
      echo "   Target latest commit: $TARGET_LATEST_COMMIT"
      echo ""
      echo "==> Files with differences:"
    fi
    echo "  - $file"
    DIFF_FOUND=1
    DIFF_COUNT=$((DIFF_COUNT + 1))
    
    # Show first 5 differing files in detail
    if [ $DIFF_COUNT -le 5 ]; then
      echo ""
      echo "    Diff for $file (first 20 lines):"
      diff -w -u "$SOURCE_FILE" "$TARGET_FILE" | head -20 || true
      echo ""
    fi
  fi
done < "$WORKDIR/source_list.txt"

if [ $DIFF_FOUND -eq 1 ]; then
  echo ""
  echo "   Total files with differences: $DIFF_COUNT"
  echo "   ⚠️  The target (client) repo codebase differs from source repo."
  echo "   ⚠️  This MR cannot be merged until repos are synchronized."
  echo ""
  echo "==> AFTER VALIDATION - Directory listing:"
  ls -la
  exit 1
fi

# ── Success ────────────────────────────────────────────────────────────────────
echo ""
echo "✅ Validation PASSED - Entire codebases are identical (ignoring whitespace)."
echo "   Source base commit : $SOURCE_BASE_COMMIT"
echo "   Target latest commit: $TARGET_LATEST_COMMIT"
echo "   Files validated    : $(wc -l < "$WORKDIR/source_list.txt")"
echo ""
echo "   ➜ Safe to merge changes to main."
echo ""
echo "==> AFTER VALIDATION - Directory listing:"
ls -la
exit 0
