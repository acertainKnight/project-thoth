# ==============================================================================
# Thoth PDF Monitor Service - Docker Configuration
# Multi-stage build for PDF monitoring microservice
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
# Monitor service: pdf + langchain + vectordb + embeddings (~2.5GB)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --extra service-monitor

# Copy source code
COPY . /app

# Install the project with service-monitor extras (non-editable for production)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-editable --extra service-monitor

# ==============================================================================
# Production stage - Minimal production image
FROM python:3.11-slim as production

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    THOTH_DOCKER=1 \
    THOTH_SERVICE=pdf-monitor \
    THOTH_LOG_LEVEL=INFO

# Install runtime system dependencies including PDF processing tools
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    ca-certificates \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-eng \
    libreoffice \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd -r thoth && useradd -r -g thoth thoth

# Create application directories with proper permissions
RUN mkdir -p /app /workspace /data/logs \
    && chown -R thoth:thoth /app /workspace /data

# Copy the application and virtual environment from builder stage
COPY --from=builder /app /app

# Copy entrypoint script with execute permissions (for migrations)
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod 755 /entrypoint.sh && chown root:root /entrypoint.sh

# Ensure all Python files are readable by all users (docker-compose runs as UID 1000)
# MUST run AFTER copying files, not before
RUN chmod -R a+r /app/src && \
    find /app/src -type d -exec chmod a+rx {} \; && \
    chown -R thoth:thoth /app

# Make sure we can run uv in the runtime
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Switch to non-root user
USER thoth

# Set working directory
WORKDIR /app

# Create default workspace structure
RUN mkdir -p /workspace/{pdfs,notes,data,logs,cache} \
    && mkdir -p /workspace/data/letta/config \
    && mkdir -p /workspace/data/cache/letta \
    && mkdir -p /workspace/logs/letta \
    && chown -R thoth:thoth /workspace

# Set PATH to include the virtual environment
ENV PATH="/app/.venv/bin:$PATH" \
    THOTH_WORKSPACE_DIR=/workspace \
    THOTH_PDF_DIR=/workspace/data/pdfs \
    THOTH_NOTES_DIR=/workspace/data/notes \
    THOTH_DATA_DIR=/workspace/data \
    THOTH_LOGS_DIR=/workspace/logs \
    THOTH_MARKDOWN_DIR=/workspace/data/markdown \
    THOTH_PDF_MONITOR_INTERVAL=60

# Production command - start the PDF monitor service
# NOTE: --watch-dir omitted to use config value from settings.json
# Config resolves: vault_root + paths.pdf = /vault/thoth/papers/pdfs
CMD ["python", "-m", "thoth", "monitor", \
     "--polling-interval", "60", \
     "--recursive", \
     "--optimized"]

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
    THOTH_PDF_MONITOR_INTERVAL=30

# Development command with more frequent monitoring
# NOTE: --watch-dir omitted to use config value from settings.json
# Config resolves: vault_root + paths.pdf = /vault/thoth/papers/pdfs
CMD ["python", "-m", "thoth", "monitor", \
     "--polling-interval", "30", \
     "--recursive", \
     "--optimized"]
