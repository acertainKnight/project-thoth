# ==============================================================================
# Thoth MCP Server - Docker Configuration
# Multi-stage build for MCP (Model Context Protocol) server microservice
# ==============================================================================

# Build stage - Install dependencies and build application
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim as builder

# Set environment variables for build optimization
ENV UV_COMPILE_BYTECODE=0 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Set working directory
WORKDIR /app

# Install dependencies first (better caching)
# MCP service: mcp + langchain + vectordb + embeddings (~2.5GB)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --extra service-mcp

# Copy source code
COPY . /app

# Install the project with service-mcp extras (non-editable for production)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-editable --extra service-mcp

# ==============================================================================
# Production stage - Minimal production image
FROM python:3.12-slim as production

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    THOTH_DOCKER=1 \
    THOTH_SERVICE=mcp \
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
RUN mkdir -p /app /workspace /data/logs \
    && chown -R thoth:thoth /app /workspace /data

# Copy the application and virtual environment from builder stage
COPY --from=builder --chown=thoth:thoth /app /app

# Make sure we can run uv in the runtime
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy entrypoint script with execute permissions
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod 755 /entrypoint.sh && chown root:root /entrypoint.sh

# Ensure all Python files are readable by all users (docker-compose runs as UID 1000)
RUN chmod -R a+r /app/src && \
    find /app/src -type d -exec chmod a+rx {} \;

# Create cache directories for CacheService (as root before switching users)
RUN mkdir -p /app/cache/ocr /app/cache/analysis /app/cache/citations /app/cache/api_responses /app/cache/embeddings && \
    chown -R thoth:thoth /app/cache && \
    chmod -R 755 /app/cache

# Set working directory
WORKDIR /app

# Install Playwright Chromium browsers as root (requires root for system deps)
ENV PLAYWRIGHT_BROWSERS_PATH=/app/.cache/ms-playwright
RUN mkdir -p /app/.cache/ms-playwright && \
    /app/.venv/bin/playwright install chromium && \
    /app/.venv/bin/playwright install-deps chromium && \
    chown -R thoth:thoth /app/.cache

# Create default workspace structure with Letta directories
RUN mkdir -p /workspace/{data,cache} \
    && mkdir -p /workspace/data/letta/config \
    && mkdir -p /workspace/data/cache/letta \
    && mkdir -p /workspace/logs/letta \
    && chown -R thoth:thoth /workspace

# Create cache directories for CacheService
RUN mkdir -p /app/cache/{ocr,analysis,citations,api_responses,embeddings} \
    && chown -R thoth:thoth /app/cache

# Switch back to thoth user for runtime
USER thoth

# Health check for container orchestration
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose MCP port
EXPOSE 8001

# Set PATH to include the virtual environment
ENV PATH="/app/.venv/bin:$PATH" \
    THOTH_WORKSPACE_DIR=/workspace \
    THOTH_DATA_DIR=/workspace/data \
    THOTH_MCP_HOST=0.0.0.0 \
    THOTH_MCP_PORT=8001

# Set entrypoint to handle migrations
ENTRYPOINT ["/entrypoint.sh"]

# Production command - start the MCP server with HTTP transport
CMD ["python", "-m", "thoth", "mcp", "http", "--host", "0.0.0.0", "--port", "8001"]

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

# Development command - HTTP transport for Docker
CMD ["python", "-m", "thoth", "mcp", "http", "--host", "0.0.0.0", "--port", "8001", "--log-level", "DEBUG"]
