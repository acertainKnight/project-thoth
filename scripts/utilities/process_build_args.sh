#!/bin/bash

# Define build-specific flags that should be ignored
BUILD_FLAGS=("build" "no-cache")

# Validate an extra
validate_extra() {
    local extra=$1
    # Skip build-specific flags
    for flag in "${BUILD_FLAGS[@]}"; do
        if [[ "$extra" == "$flag" ]]; then
            return 1
        fi
    done
    return 0
}

extras=()

# Process all arguments
while [[ $# -gt 0 ]]; do
    # Remove leading '--' from argument
    extra="${1#--}"
    if validate_extra "$extra"; then
        extras+=("$extra")
    fi
    shift
done

# Join extras with commas
if [ ${#extras[@]} -gt 0 ]; then
    printf "%s" "${extras[*]}" | tr ' ' ','
fi 