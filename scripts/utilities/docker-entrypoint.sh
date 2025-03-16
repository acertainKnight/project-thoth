#!/bin/bash
set -e

# Function to check if pre-commit is installed
check_precommit() {
    if ! command -v pre-commit &> /dev/null; then
        echo "Installing pre-commit..."
        pip install pre-commit
    fi
    echo "Installing pre-commit hooks..."
    git init .
    pre-commit install-hooks
}

# Function to setup Jupyter config if needed
setup_jupyter() {
    if [[ "$1" == "jupyter" ]] || [[ "$1" == "lab" ]]; then
        jupyter lab --generate-config
        echo "c.NotebookApp.token = ''" >> ~/.jupyter/jupyter_lab_config.py
        echo "c.NotebookApp.password = ''" >> ~/.jupyter/jupyter_lab_config.py
    fi
}

# Ensure scripts are executable (in case of mounted volumes)
ensure_scripts_executable() {
    find ./scripts -type f -name "*.sh" -exec chmod +x {} \;
}

# Main entrypoint logic
main() {
    echo "Running entrypoint"
    # Ensure scripts are executable
    ensure_scripts_executable

    check_precommit

    # Setup Jupyter if needed
    setup_jupyter "$@"

    # Execute the passed command
    exec "$@"
}

main "$@"
