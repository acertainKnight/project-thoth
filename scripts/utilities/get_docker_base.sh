#!/bin/bash

# Get the base image configuration from pyproject.toml
get_base_image() {
    local use_cuda=$1
    local image_type="default"
    
    if [ "$use_cuda" = "true" ]; then
        image_type="cuda"
    fi
    
    # Extract base image from pyproject.toml using grep
    local image=$(grep "^\[tool.docker.base_images.$image_type\]" -A 1 pyproject.toml | tail -n 1 | sed -E 's/image = .*"(.+)".*$/\1/')
    
    echo "$image"

}

# If script is called directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    get_base_image "$1"
fi