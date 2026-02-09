# ==============================================================================
# Thoth All-in-One Container - Docker Configuration
# Multi-stage build for unified container running all Thoth services
# ==============================================================================

# Build stage - Install dependencies and build application
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim as builder

# Set environment variables for build optimization
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Set working directory
WORKDIR /app

# Install dependencies first (better caching)
# All-in-one service: all features (~2.5GB with embeddings)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --extra service-all

# Copy source code
COPY . /app

# Install the project with service-all extras (non-editable for production)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-editable --extra service-all

# ==============================================================================
# Production stage - Minimal production image
FROM python:3.12-slim as production

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    THOTH_DOCKER=1 \
    THOTH_SERVICE=all-in-one \
    THOTH_LOG_LEVEL=INFO

# Install runtime system dependencies including Supervisor
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    ca-certificates \
    supervisor \
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
RUN mkdir -p /app /workspace /data/logs /etc/supervisor/conf.d \
    && chown -R thoth:thoth /app /workspace /data

# Copy the application and virtual environment from builder stage
COPY --from=builder --chown=thoth:thoth /app /app

# Make sure we can run uv in the runtime
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy supervisor configuration
COPY --chown=root:root docker/supervisor/supervisord.conf /etc/supervisor/supervisord.conf

# Copy entrypoint script with execute permissions
COPY docker/all-in-one/entrypoint.sh /entrypoint.sh
RUN chmod 755 /entrypoint.sh && chown root:root /entrypoint.sh

# Ensure all Python files are readable by all users (docker-compose runs as UID 1000)
RUN chmod -R a+r /app/src && \
    find /app/src -type d -exec chmod a+rx {} \;

# Set working directory
WORKDIR /app

# Install Playwright Chromium browsers as root (requires root for system deps)
ENV PLAYWRIGHT_BROWSERS_PATH=/app/.cache/ms-playwright
RUN mkdir -p /app/.cache/ms-playwright && \
    /app/.venv/bin/playwright install chromium && \
    /app/.venv/bin/playwright install-deps chromium && \
    chown -R thoth:thoth /app/.cache

# Create default workspace structure
RUN mkdir -p /workspace/{data,cache} \
    && mkdir -p /workspace/data/letta/config \
    && mkdir -p /workspace/data/cache/letta \
    && mkdir -p /workspace/logs/letta \
    && chown -R thoth:thoth /workspace

# Switch back to thoth user for runtime
USER thoth

# Health check - check if supervisor is running and API is responding
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD supervisorctl status thoth-api | grep RUNNING && \
        curl -f http://localhost:8000/health || exit 1

# Expose all service ports
EXPOSE 8000 8001

# Set PATH to include the virtual environment
ENV PATH="/app/.venv/bin:$PATH" \
    THOTH_WORKSPACE_DIR=/workspace \
    THOTH_DATA_DIR=/workspace/data \
    PYTHONPATH="/app/src"

# Set entrypoint to handle initialization
ENTRYPOINT ["/entrypoint.sh"]

# No CMD needed - entrypoint starts supervisor

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

# Development still uses supervisor
