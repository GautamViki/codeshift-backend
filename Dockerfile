# Use official Python 3.14 slim image
FROM python:3.14-slim AS base

# Install Go compiler tools required for Go validation
RUN apt-get update && apt-get install -y --no-install-recommends \
    golang-go \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Prevent Python from writing pyc files and buffer stdout/stderr
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency definition
COPY requirements.txt .

# Install dependencies system-wide inside container using uv
RUN uv pip install --system --no-cache -r requirements.txt

# Option A: Copy the app folder into /app/app
COPY app ./app

# Expose port for FastAPI
EXPOSE 8000

# Run FastAPI app with Uvicorn (module app.main, instance app)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]