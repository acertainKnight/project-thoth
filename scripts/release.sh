#!/usr/bin/env bash
# release.sh - Generate changelog and release commands from conventional commits
#
# Parses commits since the last git tag, groups them by type (feat, fix, refactor, etc.),
# bumps the version in pyproject.toml, and prints the git commands to finalize the release.
#
# Usage:
#   ./scripts/release.sh [new_version]
#   make release                       # interactive prompt
#   make release VERSION=0.4.0-alpha   # explicit version

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# --- Resolve current version and last tag ---

CURRENT_VERSION=$(grep -oP "^version\s*=\s*['\"]?\K[^'\"]*" pyproject.toml)
LAST_TAG=$(git describe --tags --abbrev=0 --match 'v*' 2>/dev/null || echo "")

if [ -z "$LAST_TAG" ]; then
    echo -e "${RED}No tags found. Cannot generate changelog without a starting tag.${NC}"
    echo "Create an initial tag first: git tag v0.0.0"
    exit 1
fi

echo -e "${BOLD}Release Preparation${NC}"
echo "===================="
echo ""
echo -e "  Current version:  ${CYAN}${CURRENT_VERSION}${NC}"
echo -e "  Last tag:         ${CYAN}${LAST_TAG}${NC}"

# --- Count commits since last tag ---

COMMIT_COUNT=$(git rev-list "${LAST_TAG}..HEAD" --count)

if [ "$COMMIT_COUNT" -eq 0 ]; then
    echo ""
    echo -e "${YELLOW}No commits since ${LAST_TAG}. Nothing to release.${NC}"
    exit 0
fi

echo -e "  Commits since:    ${CYAN}${COMMIT_COUNT}${NC}"
echo ""

# --- Collect and categorize commits ---

declare -a FEATURES=()
declare -a FIXES=()
declare -a REFACTORS=()
declare -a TESTS=()
declare -a DOCS=()
declare -a STYLES=()
declare -a CHORES=()
declare -a OTHER=()

while IFS= read -r line; do
    hash=$(echo "$line" | cut -d' ' -f1)
    msg=$(echo "$line" | cut -d' ' -f2-)
    short="${hash:0:7}"
    entry="${msg} (${short})"

    # skip merge commits and version bumps
    if echo "$msg" | grep -qiE '^merge |^chore:.*bump version'; then
        continue
    fi

    if echo "$msg" | grep -qiE '^feat(\(|:)'; then
        FEATURES+=("$entry")
    elif echo "$msg" | grep -qiE '^fix(\(|:)'; then
        FIXES+=("$entry")
    elif echo "$msg" | grep -qiE '^refactor(\(|:)'; then
        REFACTORS+=("$entry")
    elif echo "$msg" | grep -qiE '^test(\(|:)'; then
        TESTS+=("$entry")
    elif echo "$msg" | grep -qiE '^docs(\(|:)'; then
        DOCS+=("$entry")
    elif echo "$msg" | grep -qiE '^style(\(|:)'; then
        STYLES+=("$entry")
    elif echo "$msg" | grep -qiE '^chore(\(|:)'; then
        CHORES+=("$entry")
    else
        OTHER+=("$entry")
    fi
done < <(git log "${LAST_TAG}..HEAD" --format="%H %s" --no-merges)

# --- Print changelog ---

echo -e "${BOLD}Changelog (${LAST_TAG} -> HEAD)${NC}"
echo "-------------------------------------------"

print_section() {
    local title="$1"
    shift
    local items=("$@")
    if [ ${#items[@]} -gt 0 ]; then
        echo ""
        echo -e "${BOLD}${title}${NC}"
        for item in "${items[@]}"; do
            echo "  - ${item}"
        done
    fi
}

print_section "Features" "${FEATURES[@]+"${FEATURES[@]}"}"
print_section "Bug Fixes" "${FIXES[@]+"${FIXES[@]}"}"
print_section "Refactors" "${REFACTORS[@]+"${REFACTORS[@]}"}"
print_section "Tests" "${TESTS[@]+"${TESTS[@]}"}"
print_section "Documentation" "${DOCS[@]+"${DOCS[@]}"}"
print_section "Styles" "${STYLES[@]+"${STYLES[@]}"}"
print_section "Chores" "${CHORES[@]+"${CHORES[@]}"}"
print_section "Other" "${OTHER[@]+"${OTHER[@]}"}"

echo ""
echo "-------------------------------------------"

# --- Determine new version ---

NEW_VERSION="${1:-}"

if [ -z "$NEW_VERSION" ]; then
    # Suggest a version bump based on commit types
    if [ ${#FEATURES[@]} -gt 0 ]; then
        SUGGESTION="minor bump (has features)"
    elif [ ${#FIXES[@]} -gt 0 ]; then
        SUGGESTION="patch bump (bug fixes only)"
    else
        SUGGESTION="patch bump (maintenance)"
    fi

    echo ""
    echo -e "${YELLOW}Suggestion: ${SUGGESTION}${NC}"
    echo -e "${YELLOW}Enter new version (current: ${CURRENT_VERSION}):${NC}"
    read -r -p "> " NEW_VERSION

    if [ -z "$NEW_VERSION" ]; then
        echo -e "${RED}No version provided. Aborting.${NC}"
        exit 1
    fi
fi

TAG_NAME="v${NEW_VERSION}"

# --- Check if tag already exists ---

if git rev-parse "$TAG_NAME" >/dev/null 2>&1; then
    echo -e "${RED}Tag ${TAG_NAME} already exists. Pick a different version.${NC}"
    exit 1
fi

# --- Build commit message body from changelog ---

COMMIT_BODY=""

build_body_section() {
    local title="$1"
    shift
    local items=("$@")
    if [ ${#items[@]} -gt 0 ]; then
        COMMIT_BODY+=$'\n'"${title}:"
        for item in "${items[@]}"; do
            COMMIT_BODY+=$'\n'"- ${item}"
        done
    fi
}

build_body_section "Features" "${FEATURES[@]+"${FEATURES[@]}"}"
build_body_section "Bug Fixes" "${FIXES[@]+"${FIXES[@]}"}"
build_body_section "Refactors" "${REFACTORS[@]+"${REFACTORS[@]}"}"
build_body_section "Tests" "${TESTS[@]+"${TESTS[@]}"}"
build_body_section "Documentation" "${DOCS[@]+"${DOCS[@]}"}"
build_body_section "Styles" "${STYLES[@]+"${STYLES[@]}"}"
build_body_section "Chores" "${CHORES[@]+"${CHORES[@]}"}"
build_body_section "Other" "${OTHER[@]+"${OTHER[@]}"}"

# --- Update pyproject.toml ---

echo ""
echo -e "${CYAN}Updating pyproject.toml version: ${CURRENT_VERSION} -> ${NEW_VERSION}${NC}"
sed -i "s/^version\s*=\s*['\"].*['\"]$/version = '${NEW_VERSION}'/" pyproject.toml

echo -e "${GREEN}Done.${NC}"

# --- Print the release commands ---

echo ""
echo -e "${BOLD}Run these commands to finalize the release:${NC}"
echo "============================================="
echo ""
echo -e "${CYAN}# 1. Stage and commit the version bump${NC}"
echo "git add pyproject.toml"
echo "git commit -m \"chore: bump version to ${NEW_VERSION}"
echo "${COMMIT_BODY}"
echo "\""
echo ""
echo -e "${CYAN}# 2. Tag the release${NC}"
echo "git tag -a ${TAG_NAME} -m \"Release ${TAG_NAME}"
echo "${COMMIT_BODY}"
echo "\""
echo ""
echo -e "${CYAN}# 3. Push commit and tag${NC}"
echo "git push origin main"
echo "git push origin ${TAG_NAME}"
echo ""
echo -e "${CYAN}# 4. (Optional) Create a GitHub release${NC}"
echo "gh release create ${TAG_NAME} --title \"${TAG_NAME}\" --notes-file - <<'EOF'"
echo "## ${TAG_NAME}"
echo "${COMMIT_BODY}"
echo "EOF"
echo ""
echo "============================================="
echo -e "${GREEN}Version bumped in pyproject.toml. Commands above are ready to copy-paste.${NC}"
