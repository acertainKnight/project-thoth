# ==============================================================================
# Thoth AI Research Assistant - Production Dockerfile
# Following UV official best practices for Docker
# See: https://docs.astral.sh/uv/guides/integration/docker/
# ==============================================================================

# ==============================================================================
# Builder stage - Install dependencies and project
# ==============================================================================
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

# Build argument for service-specific extras
ARG SERVICE_EXTRAS="api,discovery,vectordb"

# UV best practices for Docker builds
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Install dependencies first (cached layer)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev --extra ${SERVICE_EXTRAS}

# Copy source code
COPY . /app

# Install the project (non-editable for production)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable --extra ${SERVICE_EXTRAS}

# ==============================================================================
# Production stage - Minimal runtime image
# ==============================================================================
FROM python:3.12-slim AS production

# Install runtime dependencies + Playwright browser system libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    git \
    # Playwright Chromium system dependencies
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
    libasound2t64 \
    libatspi2.0-0 \
    libxshmfence1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user
RUN useradd -m -u 1000 thoth && \
    mkdir -p /app /data && \
    chown -R thoth:thoth /app /data

WORKDIR /app

# Copy only the virtual environment from builder (includes installed project)
COPY --from=builder --chown=thoth:thoth /app/.venv /app/.venv

# Install Playwright Chromium browsers (as root, then chown to thoth)
ENV PLAYWRIGHT_BROWSERS_PATH=/app/.cache/ms-playwright
RUN mkdir -p /app/.cache/ms-playwright && \
    /app/.venv/bin/playwright install chromium && \
    chown -R thoth:thoth /app/.cache

# Switch to non-root user
USER thoth

# UV best practice: Set PATH to include venv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    THOTH_DATA_DIR=/data

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Default command
CMD ["uvicorn", "thoth.server.app:app", "--host", "0.0.0.0", "--port", "8000"]
