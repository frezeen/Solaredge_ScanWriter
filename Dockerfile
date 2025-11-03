# SolarEdge ScanWriter - Universal Multi-Architecture Container
# Compatibile con: Windows, Linux (AMD64), Raspberry Pi (ARM64/ARMv7)
FROM python:3.11-slim-bullseye

# Metadata
LABEL maintainer="SolarEdge ScanWriter"
LABEL description="Universal SolarEdge data collection system"
LABEL version="2.0-universal"

# Build arguments for multi-architecture support
ARG TARGETPLATFORM
ARG BUILDPLATFORM
ARG TARGETARCH
ARG TARGETVARIANT

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DEBIAN_FRONTEND=noninteractive
ENV DOCKER_MODE=true
ENV PYTHONPATH=/app
ENV PLATFORM=${TARGETPLATFORM}

# Install system dependencies (universal)
RUN apt-get update && apt-get install -y \
    # Network tools (cross-platform)
    curl \
    wget \
    netcat-openbsd \
    net-tools \
    procps \
    # Build tools
    build-essential \
    git \
    # Python development
    python3-dev \
    # Cleanup
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create application user (security best practice)
RUN useradd --create-home --shell /bin/bash --uid 1000 solaredge

# Set working directory
WORKDIR /app

# Copy requirements file (Docker layer caching optimization)
COPY requirements.txt ./

# Install Python dependencies with platform optimizations
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Apply cross-platform fixes and setup
RUN python docker/platform-fixes.py || echo "Platform fixes not available, continuing..." && \
    # Create necessary directories
    mkdir -p logs cache cookies config/sources data backups && \
    # Set proper permissions
    chown -R solaredge:solaredge /app && \
    # Make entrypoint executable
    chmod +x docker/entrypoint.sh

# Switch to non-root user for security
USER solaredge

# Expose GUI port
EXPOSE 8092

# Health check (universal)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8092/health', timeout=5)" || exit 1

# Persistent data volumes
VOLUME ["/app/logs", "/app/cache", "/app/cookies", "/app/config", "/app/data"]

# Use entrypoint for proper initialization
ENTRYPOINT ["./docker/entrypoint.sh"]
CMD ["python", "main.py"]