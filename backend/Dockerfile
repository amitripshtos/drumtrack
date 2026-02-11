FROM python:3.12-slim

# System deps: ffmpeg for audio processing, libsndfile for soundfile
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Install dependencies (lockfile ensures reproducibility)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy application code and install the project
COPY app/ app/
RUN uv sync --frozen --no-dev

# Create directories for persistent data
RUN mkdir -p /app/storage/jobs /app/models

VOLUME ["/app/storage", "/app/models"]

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
