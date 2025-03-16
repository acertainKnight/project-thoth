#!/bin/bash

CONFIG_TYPE=$1

case $CONFIG_TYPE in
    "version")
        grep "^\[tool.docker.base_images.cuda\]" -A 1 pyproject.toml | tail -n 1 |
        sed -E 's/cuda_version = .*"(.+)".*$/\1/'
        ;;
    "cudnn")
        grep "^\[tool.docker.base_images.cuda\]" -A 1 pyproject.toml | tail -n 1 |
        sed -E 's/cudnn_version = .*"(.+)".*$/\1/'
        ;;
    "nccl")
        grep "^\[tool.docker.base_images.cuda\]" -A 1 pyproject.toml | tail -n 1 |
        sed -E 's/nccl_version = .*"(.+)".*$/\1/'
        ;;
    *)
        echo "Unknown configuration type"
        exit 1
        ;;
esac
