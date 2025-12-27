# ==============================================================================
# Thoth AI Research Assistant - Production Dockerfile
# Multi-stage build for optimal image size and security
# ==============================================================================

# Build stage - Install dependencies and build application
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim as builder

# Build arg to specify which service extras to install (defaults to all)
ARG SERVICE_EXTRAS="all"

# Set environment variables for build optimization
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Set working directory
WORKDIR /app

# Install dependencies first (better caching)
# Use SERVICE_EXTRAS to install only what this service needs
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    if [ "$SERVICE_EXTRAS" = "all" ]; then \
        uv sync --locked --no-install-project; \
    else \
        uv sync --locked --no-install-project --extra "$SERVICE_EXTRAS"; \
    fi

# Copy source code
COPY . /app

# Install the project with the same extras
RUN --mount=type=cache,target=/root/.cache/uv \
    if [ "$SERVICE_EXTRAS" = "all" ]; then \
        uv sync --locked; \
    else \
        uv sync --locked --extra "$SERVICE_EXTRAS"; \
    fi

# ==============================================================================
# Runtime stage - Minimal production image
FROM python:3.11-slim as runtime

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    THOTH_DOCKER=1 \
    THOTH_LOG_LEVEL=INFO

# Install runtime system dependencies including Node.js for MCP plugins and browser automation
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    ca-certificates \
    # Playwright browser dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libatspi2.0-0 \
    libxshmfence1 \
    # Install Node.js
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
# Use GID 1000 to match typical host user group for proper permissions when docker-compose overrides user
RUN groupadd -g 1000 thoth && useradd -r -u 999 -g thoth thoth

# Create application directories with proper permissions
RUN mkdir -p /app /workspace /data/logs /data/cache \
    && chown -R thoth:thoth /app /workspace /data

# Copy the application and virtual environment from builder stage
COPY --from=builder --chown=thoth:thoth /app /app

# Make sure we can run uv in the runtime (for any runtime needs)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy entrypoint script
COPY --chown=thoth:thoth docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Ensure all Python files have group read permissions (docker-compose runs as UID 1000, GID 1000)
# Both user thoth (999) and docker-compose user (1000) share group 1000
RUN chmod -R g+r /app/src

# Switch to non-root user temporarily for Playwright install
USER thoth

# Set working directory
WORKDIR /app

# Install Playwright browsers (run as thoth user to store in user home)
RUN /app/.venv/bin/playwright install --with-deps chromium || echo "Playwright install skipped"

# Switch back to root for remaining setup
USER root

# Create cache, logs, and data directories in app with proper permissions
# Use group-writable permissions instead of world-writable for security
# Docker-compose will run as user 1000 which we add to the thoth group
RUN mkdir -p /app/cache /app/logs /app/migrations /app/data/output /app/exports \
    && chown -R thoth:thoth /app/cache /app/logs /app/migrations /app/data /app/exports \
    && chmod -R 775 /app/cache /app/logs /app/migrations /app/data /app/exports \
    && chmod g+s /app/cache /app/logs /app/migrations /app/data /app/exports

# Create default workspace structure
RUN mkdir -p /workspace/{pdfs,notes,data,queries,discovery,knowledge,logs,cache}

# Switch back to thoth user for runtime
USER thoth

# Health check for container orchestration
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health', timeout=5)" || exit 1

# Expose ports
EXPOSE 8000 8001

# Set PATH to include the virtual environment and default environment variables
ENV PATH="/app/.venv/bin:$PATH" \
    THOTH_WORKSPACE_DIR=/workspace \
    THOTH_PDF_DIR=/workspace/pdfs \
    THOTH_NOTES_DIR=/workspace/notes \
    THOTH_DATA_DIR=/workspace/data \
    THOTH_QUERIES_DIR=/workspace/queries \
    THOTH_DISCOVERY_SOURCES_DIR=/workspace/discovery \
    THOTH_KNOWLEDGE_BASE_DIR=/workspace/knowledge \
    THOTH_LOGS_DIR=/workspace/logs \
    THOTH_CACHE_DIR=/workspace/cache \
    THOTH_API_HOST=0.0.0.0 \
    THOTH_API_PORT=8000 \
    THOTH_MCP_HOST=0.0.0.0 \
    THOTH_MCP_PORT=8001

# Set entrypoint to handle migrations
ENTRYPOINT ["/entrypoint.sh"]

# Default command - can be overridden in docker-compose.yml
# For multi-container setup, each service specifies its own command
# This default starts the API server for backward compatibility
CMD ["python", "-m", "thoth", "server", "start", "--api-host", "0.0.0.0", "--api-port", "8000"]

# ==============================================================================
# Development stage - extends runtime with development tools
FROM runtime as development

# Switch back to root for installing development dependencies
USER root

# Install development dependencies
RUN apt-get update && apt-get install -y \
    git \
    vim \
    htop \
    tree \
    && rm -rf /var/lib/apt/lists/*

# Switch back to thoth user
USER thoth

# Development environment variables
ENV THOTH_LOG_LEVEL=DEBUG \
    THOTH_DEV_MODE=1

# Development command with auto-reload
CMD ["python", "-m", "thoth", "server", "start", "--api-host", "0.0.0.0", "--api-port", "8000", "--no-discovery", "--no-mcp", "--api-reload"]
