FROM ghcr.io/astral-sh/uv:python3.13-alpine AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

ENV UV_PYTHON_DOWNLOADS=0

WORKDIR /app
COPY uv.lock uv.lock 
COPY pyproject.toml pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev
COPY app /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Then, use a final image without uv
FROM python:3.13-alpine

LABEL maintainer="loorisr"
LABEL repository="https://github.com/loorisr/crawlrouter"
LABEL description="Unified API for Searching and Crawling"
LABEL date="2025-03-10"

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Copy the application from the builder
COPY --from=builder --chown=app:app /app /app

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"

# Set the working directory in the container
WORKDIR /app

ARG PORT
ENV PORT=${PORT:-8000}

EXPOSE ${PORT}

# Command to run the application
CMD uvicorn app:app --host 0.0.0.0 --port $PORT