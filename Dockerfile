# Auto-adaptive SolarEdge Data Collector
# Automatically adapts to: AMD64, ARM64, ARMv7
FROM python:3.11-slim

# Build arguments for architecture detection
ARG TARGETPLATFORM
ARG BUILDPLATFORM
ARG TARGETARCH
ARG TARGETVARIANT

# Metadata
LABEL maintainer="SolarEdge Data Collector"
LABEL description="Auto-adaptive SolarEdge data collection system"
LABEL version="3.1-auto"

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    DOCKER_MODE=true \
    PYTHONPATH=/app \
    PLATFORM=${TARGETPLATFORM:-linux/amd64} \
    ARCH=${TARGETARCH:-amd64}

# Architecture-specific optimizations
RUN echo "Building for platform: ${TARGETPLATFORM:-linux/amd64}" && \
    echo "Target architecture: ${TARGETARCH:-amd64}" && \
    apt-get update && \
    # Base packages for all architectures
    apt-get install -y \
        curl \
        wget \
        netcat-openbsd \
        procps \
        python3-dev \
        jq \
    # Architecture-specific packages
    && if [ "${TARGETARCH}" = "amd64" ]; then \
        apt-get install -y build-essential; \
    elif [ "${TARGETARCH}" = "arm64" ]; then \
        apt-get install -y build-essential gcc-aarch64-linux-gnu; \
    elif [ "${TARGETARCH}" = "arm" ]; then \
        apt-get install -y build-essential gcc-arm-linux-gnueabihf; \
    else \
        apt-get install -y build-essential; \
    fi \
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