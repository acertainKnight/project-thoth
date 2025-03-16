#!/bin/bash

# Extract version constraints from requires-python line
get_constraints() {
    # Extract everything between the quotes and split on comma
    grep "requires-python" pyproject.toml | sed -E 's/.*"([^"]+)".*/\1/' | tr ',' '\n' | tr -d ' '
}

# Convert version string to comparable number (e.g., 3.9 -> 3009)
version_to_num() {
    echo "$1" | awk -F. '{ printf "%d%03d", $1, $2 }'
}

# Get available Python versions - customize this list as needed
get_available_versions() {
    echo "3.12
3.11
3.10
3.9"
}

# Find best matching version
find_best_version() {
    local best_version=""
    local min_version=3009
    local max_version=3012

    # Process each constraint
    while read -r constraint; do
        if [[ $constraint =~ ^">="([0-9]+\.[0-9]+) ]]; then
            min_version=$(version_to_num "${BASH_REMATCH[1]}")
        elif [[ $constraint =~ ^"<="([0-9]+\.[0-9]+) ]]; then
            max_version=$(version_to_num "${BASH_REMATCH[1]}")
        elif [[ $constraint =~ ^">"([0-9]+\.[0-9]+) ]]; then
            min_version=$(($(version_to_num "${BASH_REMATCH[1]}") + 1))
        elif [[ $constraint =~ ^"<"([0-9]+\.[0-9]+) ]]; then
            max_version=$(($(version_to_num "${BASH_REMATCH[1]}") - 1))
        elif [[ $constraint =~ ^"=="([0-9]+\.[0-9]+) ]]; then
            min_version=$(version_to_num "${BASH_REMATCH[1]}")
            max_version=$min_version
        fi
    done < <(get_constraints)
    # Find the first version that satisfies all constraints
    while read -r version; do
        local ver_num=$(version_to_num "$version")
        if (( ver_num >= min_version && ver_num <= max_version )); then
            echo "$version"
            return 0
        fi
    done < <(get_available_versions)

    echo "No suitable Python version found"
    return 1
}

find_best_version