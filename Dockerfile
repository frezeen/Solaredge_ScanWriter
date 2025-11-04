# SolarEdge Data Collector - Multi-Platform
FROM python:3.11-slim

# Metadata
LABEL maintainer="SolarEdge Data Collector"
LABEL description="SolarEdge data collection system"
LABEL version="1.0"

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    DOCKER_MODE=true \
    PYTHONPATH=/app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    netcat-openbsd \
    procps \
    python3-dev \
    build-essential \
    jq \
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
    sed -i 's/\r$//' docker/entrypoint.sh && \
    chmod +x docker/entrypoint.sh && \
    chown -R solaredge:solaredge /app

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