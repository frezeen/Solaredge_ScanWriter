# Multi-platform SolarEdge Data Collector
# Supports: Windows, Linux (AMD64), Raspberry Pi (ARM64/ARMv7)
FROM python:3.11-slim

# Build arguments for multi-architecture support
ARG TARGETPLATFORM
ARG BUILDPLATFORM
ARG TARGETARCH

# Metadata
LABEL maintainer="SolarEdge Data Collector"
LABEL description="Multi-platform SolarEdge data collection system"
LABEL version="3.0"
LABEL platforms="linux/amd64,linux/arm64,linux/arm/v7"

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    DOCKER_MODE=true \
    PYTHONPATH=/app \
    PLATFORM=${TARGETPLATFORM:-linux/amd64}

# Install system dependencies based on architecture
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    netcat-openbsd \
    procps \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash --uid 1000 solaredge

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories and set permissions
RUN mkdir -p logs cache cookies config/sources data backups && \
    chown -R solaredge:solaredge /app && \
    chmod +x docker/entrypoint.sh

# Switch to non-root user
USER solaredge

# Expose GUI port
EXPOSE 8092

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8092/health || exit 1

# Persistent volumes
VOLUME ["/app/logs", "/app/cache", "/app/cookies", "/app/config", "/app/data"]

# Use entrypoint for initialization
ENTRYPOINT ["./docker/entrypoint.sh"]
CMD ["python", "main.py"]