# ==============================================================================
# Thoth API Server - Docker Configuration
# Multi-stage build for API server microservice
# ==============================================================================

# Build stage - Install dependencies and build application
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim as builder

# Set environment variables for build optimization
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Set working directory
WORKDIR /app

# Install dependencies first (better caching)
# API service: core + api + discovery (~200MB, NO heavy ML/vectordb/memory)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --extra service-api

# Copy source code
COPY . /app

# Install the project with service-api extras
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --extra service-api

# ==============================================================================
# Production stage - Minimal production image
FROM python:3.11-slim as production

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    THOTH_DOCKER=1 \
    THOTH_SERVICE=api \
    THOTH_LOG_LEVEL=INFO

# Install runtime system dependencies including Playwright browser dependencies
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
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd -r thoth && useradd -r -g thoth thoth

# Create application directories with proper permissions
RUN mkdir -p /app /workspace /data/logs /data/cache \
    && chown -R thoth:thoth /app /workspace /data

# Copy the application and virtual environment from builder stage
COPY --from=builder --chown=thoth:thoth /app /app

# Create cache directories for CacheService (as root before switching users)
RUN mkdir -p /app/cache/ocr /app/cache/analysis /app/cache/citations /app/cache/api_responses /app/cache/embeddings && \
    chown -R thoth:thoth /app/cache && \
    chmod -R 755 /app/cache

# Make sure we can run uv in the runtime
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy entrypoint script with execute permissions
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod 755 /entrypoint.sh && chown root:root /entrypoint.sh

# Ensure all Python files are readable by all users (docker-compose runs as UID 1000)
RUN chmod -R a+r /app/src && \
    find /app/src -type d -exec chmod a+rx {} \;

# Switch to non-root user temporarily for Playwright install
USER thoth

# Set working directory
WORKDIR /app

# Create Playwright cache directory with correct permissions
RUN mkdir -p /app/.cache/ms-playwright

# Switch back to root for Playwright browser installation (needs system deps)
USER root

# Install Playwright browsers as root (required for system dependencies)
RUN /app/.venv/bin/playwright install chromium && \
    /app/.venv/bin/playwright install-deps chromium && \
    chown -R thoth:thoth /root/.cache/ms-playwright 2>/dev/null || true

# Create default workspace structure with Letta directories
RUN mkdir -p /workspace/{pdfs,notes,data,queries,discovery,knowledge,logs,cache} \
    && mkdir -p /workspace/data/letta/config \
    && mkdir -p /workspace/data/cache/letta \
    && mkdir -p /workspace/logs/letta \
    && chown -R thoth:thoth /workspace

# Switch back to thoth user for runtime
USER thoth

# Health check for container orchestration
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose API port
EXPOSE 8000

# Set PATH to include the virtual environment
ENV PATH="/app/.venv/bin:$PATH" \
    THOTH_WORKSPACE_DIR=/workspace \
    THOTH_PDF_DIR=/workspace/pdfs \
    THOTH_NOTES_DIR=/workspace/notes \
    THOTH_DATA_DIR=/workspace/data \
    THOTH_LOGS_DIR=/workspace/logs \
    THOTH_API_HOST=0.0.0.0 \
    THOTH_API_PORT=8000

# Set entrypoint to handle migrations
ENTRYPOINT ["/entrypoint.sh"]

# Production command - start the API server only
CMD ["python", "-m", "thoth", "server", "start", \
     "--api-host", "0.0.0.0", \
     "--api-port", "8000", \
     "--no-discovery", \
     "--no-mcp"]

# ==============================================================================
# Development stage - extends production with development tools
FROM production as development

# Switch back to root for installing development dependencies
USER root

# Install development dependencies
RUN apt-get update && apt-get install -y \
    git \
    vim \
    htop \
    tree \
    procps \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

# Switch back to thoth user
USER thoth

# Development environment variables
ENV THOTH_LOG_LEVEL=DEBUG \
    THOTH_DEV_MODE=1

# Development command with auto-reload
CMD ["python", "-m", "thoth", "server", "start", \
     "--api-host", "0.0.0.0", \
     "--api-port", "8000", \
     "--no-discovery", \
     "--no-mcp", \
     "--api-reload"]
