# Thoth Research Assistant Dockerfile for Background Agents
FROM python:3.11-slim

# Set environment variables to prevent buffering and bytecode generation
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Set the home for the new user and add cargo to path
    USER_HOME=/home/app \
    PATH="/home/app/.cargo/bin:$PATH"

# Install system dependencies required for development and project dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    build-essential \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# Install uv, a fast Python package manager
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Create a non-root user with a home directory and sudo privileges
RUN useradd --create-home --shell /bin/bash --uid 1001 app && \
    adduser app sudo && \
    echo "app ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers

# Switch to the new user
USER app

# Set the working directory to the user's home
WORKDIR /home/app

# Set a default command to keep the container running if needed, e.g., for interactive sessions
# Or leave it empty to be specified at runtime by the agent.
CMD ["/bin/bash"]
