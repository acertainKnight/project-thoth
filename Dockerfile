# Thoth Research Assistant Dockerfile
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:$PATH"

# Create app user and directories
RUN useradd --create-home --shell /bin/bash app && \
    mkdir -p /app && \
    chown -R app:app /app

# Set working directory
WORKDIR /app

# Copy project files
COPY --chown=app:app pyproject.toml uv.lock* ./
COPY --chown=app:app src/ ./src/
COPY --chown=app:app templates/ ./templates/
COPY --chown=app:app README.md ./

# Install dependencies
RUN uv sync --frozen

# Create data directories
RUN mkdir -p \
    /app/data/pdfs \
    /app/knowledge \
    /app/logs \
    /app/obsidian-vault && \
    chown -R app:app /app/data /app/knowledge /app/logs /app/obsidian-vault

# Switch to app user
USER app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Default command
CMD ["uv", "run", "python", "-m", "thoth", "api", "--host", "0.0.0.0", "--port", "8000"]
