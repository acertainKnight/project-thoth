#!/usr/bin/env bash
# release.sh - Generate changelog, bump version, and optionally run release commands
#
# Parses commits since the last git tag, groups them by type (feat, fix, refactor, etc.),
# bumps the version in pyproject.toml, then walks through each release step interactively.
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
    echo -e "${RED}No semver tags found. Cannot generate changelog without a starting tag.${NC}"
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

# --- Build changelog body for commit/tag messages ---

CHANGELOG_BODY=""

build_body_section() {
    local title="$1"
    shift
    local items=("$@")
    if [ ${#items[@]} -gt 0 ]; then
        CHANGELOG_BODY+="${title}:"$'\n'
        for item in "${items[@]}"; do
            CHANGELOG_BODY+="- ${item}"$'\n'
        done
        CHANGELOG_BODY+=$'\n'
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

# --- Step runner ---
# Presents each step, asks the user, and runs it if approved.

AUTORUN=""  # tracks "all" mode

ask_and_run() {
    local step_num="$1"
    local description="$2"
    shift 2
    # remaining args are the command(s) to run

    echo ""
    echo -e "${BOLD}Step ${step_num}: ${description}${NC}"
    echo -e "${CYAN}  > $*${NC}"

    if [ "$AUTORUN" = "all" ]; then
        echo -e "  ${YELLOW}(auto-running)${NC}"
    else
        read -r -p "  Run this step? [y]es / [n]o / [a]ll remaining / [q]uit: " choice
        case "$choice" in
            a|A|all)
                AUTORUN="all"
                ;;
            n|N|no)
                echo -e "  ${YELLOW}Skipped.${NC}"
                return 0
                ;;
            q|Q|quit)
                echo -e "  ${RED}Aborted. Remaining steps skipped.${NC}"
                exit 0
                ;;
            *)
                # default: yes
                ;;
        esac
    fi

    if eval "$@"; then
        echo -e "  ${GREEN}Done.${NC}"
    else
        echo -e "  ${RED}Command failed (exit $?). Stopping.${NC}"
        exit 1
    fi
}

# --- Update pyproject.toml (always runs, not optional) ---

echo ""
echo -e "${CYAN}Updating pyproject.toml version: ${CURRENT_VERSION} -> ${NEW_VERSION}${NC}"
sed -i "s/^version\s*=\s*['\"].*['\"]$/version = '${NEW_VERSION}'/" pyproject.toml
echo -e "${GREEN}Done.${NC}"

# --- Present release steps ---

echo ""
echo -e "${BOLD}Release steps for ${TAG_NAME}${NC}"
echo "============================================="
echo ""
echo "  1. Stage and commit the version bump"
echo "  2. Tag the release"
echo "  3. Push commit to origin"
echo "  4. Push tag to origin"
echo "  5. Create GitHub release (requires gh CLI)"
echo ""
echo -e "${YELLOW}For each step you can choose: [y]es, [n]o, [a]ll remaining, [q]uit${NC}"

# Step 1: commit
COMMIT_MSG="chore: bump version to ${NEW_VERSION}

${CHANGELOG_BODY}"

ask_and_run 1 "Stage and commit version bump" \
    "git add pyproject.toml && git commit -m \"\$(cat <<'COMMITMSG'
${COMMIT_MSG}
COMMITMSG
)\""

# Step 2: tag
TAG_MSG="Release ${TAG_NAME}

${CHANGELOG_BODY}"

ask_and_run 2 "Tag the release as ${TAG_NAME}" \
    "git tag -a '${TAG_NAME}' -m \"\$(cat <<'TAGMSG'
${TAG_MSG}
TAGMSG
)\""

# Step 3: push commit
BRANCH=$(git branch --show-current)
ask_and_run 3 "Push commit to origin/${BRANCH}" \
    "git push origin '${BRANCH}'"

# Step 4: push tag
ask_and_run 4 "Push tag ${TAG_NAME} to origin" \
    "git push origin '${TAG_NAME}'"

# Step 5: GitHub release
GH_NOTES="## ${TAG_NAME}

${CHANGELOG_BODY}"

ask_and_run 5 "Create GitHub release for ${TAG_NAME}" \
    "gh release create '${TAG_NAME}' --title '${TAG_NAME}' --notes \"\$(cat <<'GHNOTES'
${GH_NOTES}
GHNOTES
)\""

echo ""
echo "============================================="
echo -e "${GREEN}Release ${TAG_NAME} complete.${NC}"
