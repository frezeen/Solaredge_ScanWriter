# SolarEdge Data Collector - Docker Container
FROM python:3.11-slim-bullseye

# Metadata
LABEL maintainer="SolarEdge Data Collector"
LABEL description="SolarEdge data collection system for InfluxDB"
LABEL version="1.0"

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create application user
RUN useradd --create-home --shell /bin/bash solaredge

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p logs cache cookies && \
    chown -R solaredge:solaredge /app

# Switch to application user
USER solaredge

# Expose GUI port
EXPOSE 8092

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8092/health', timeout=5)" || exit 1

# Default command
CMD ["python", "main.py"]