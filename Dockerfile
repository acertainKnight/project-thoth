# ==============================================================================
# Thoth AI Research Assistant - Production Dockerfile
# Multi-stage build for optimal image size and security
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
# Runtime stage - Minimal production image
FROM python:3.11-slim as runtime

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    THOTH_DOCKER=1 \
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

# Make sure we can run uv in the runtime (for any runtime needs)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Switch to non-root user
USER thoth

# Set working directory
WORKDIR /app

# Create default workspace structure
RUN mkdir -p /workspace/{pdfs,notes,data,queries,discovery,knowledge,logs,cache}

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

# Default command - start the API server using server subcommand
CMD ["python", "-m", "thoth", "server", "start", "--api-host", "0.0.0.0", "--api-port", "8000", "--no-discovery", "--no-mcp"]

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
