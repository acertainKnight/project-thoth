# ==============================================================================
# Thoth Research Agent Service - Docker Configuration
# Multi-stage build for research agent microservice
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
# Agent service: FULL STACK with memory (~4GB)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --extra service-agent

# Copy source code
COPY . /app

# Install the project with service-agent extras (includes Letta + nvidia libs)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --extra service-agent

# ==============================================================================
# Production stage - Minimal production image
FROM python:3.12-slim as production

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    THOTH_DOCKER=1 \
    THOTH_SERVICE=agent \
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
RUN mkdir -p /app /workspace /data/logs \
    && chown -R thoth:thoth /app /workspace /data

# Copy the application and virtual environment from builder stage
COPY --from=builder --chown=thoth:thoth /app /app

# Make sure we can run uv in the runtime
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Switch to non-root user
USER thoth

# Set working directory
WORKDIR /app

# Create default workspace structure
RUN mkdir -p /workspace/{data,logs,cache,sessions} \
    && mkdir -p /workspace/data/letta/config \
    && mkdir -p /workspace/data/cache/letta \
    && mkdir -p /workspace/logs/letta \
    && chown -R thoth:thoth /workspace

# Health check for container orchestration
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8005/health || exit 1

# Expose agent service port
EXPOSE 8005

# Set PATH to include the virtual environment
ENV PATH="/app/.venv/bin:$PATH" \
    THOTH_WORKSPACE_DIR=/workspace \
    THOTH_DATA_DIR=/workspace/data \
    THOTH_LOGS_DIR=/workspace/logs \
    THOTH_AGENT_HOST=0.0.0.0 \
    THOTH_AGENT_PORT=8005 \
    THOTH_RESEARCH_AGENT_MEMORY_ENABLED=true \
    THOTH_AGENT_MAX_TOOL_CALLS=20 \
    THOTH_AGENT_TIMEOUT_SECONDS=300 \
    THOTH_AGENT_CONCURRENT_SESSIONS=5

# Production command - start the research agent service
CMD ["python", "-m", "thoth", "agent", "serve", \
     "--host", "0.0.0.0", \
     "--port", "8005", \
     "--memory"]

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
    THOTH_DEV_MODE=1 \
    THOTH_AGENT_CONCURRENT_SESSIONS=2

# Development command with debug mode
CMD ["python", "-m", "thoth", "agent", "serve", \
     "--host", "0.0.0.0", \
     "--port", "8005", \
     "--memory", \
     "--debug"]
