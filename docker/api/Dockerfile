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
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

# Copy source code
COPY . /app

# Install the project
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

# ==============================================================================
# Production stage - Minimal production image
FROM python:3.11-slim as production

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    THOTH_DOCKER=1 \
    THOTH_SERVICE=api \
    THOTH_LOG_LEVEL=INFO

# Install runtime system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd -r thoth && useradd -r -g thoth thoth

# Create application directories with proper permissions
RUN mkdir -p /app /workspace /data/logs /data/cache \
    && chown -R thoth:thoth /app /workspace /data

# Copy the application and virtual environment from builder stage
COPY --from=builder --chown=thoth:thoth /app /app

# Make sure we can run uv in the runtime
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Switch to non-root user
USER thoth

# Set working directory
WORKDIR /app

# Create default workspace structure with Letta directories
RUN mkdir -p /workspace/{pdfs,notes,data,queries,discovery,knowledge,logs,cache} \
    && mkdir -p /workspace/data/letta/config \
    && mkdir -p /workspace/data/cache/letta \
    && mkdir -p /workspace/logs/letta \
    && chown -R thoth:thoth /workspace

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
