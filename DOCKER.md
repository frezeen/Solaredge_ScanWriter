# 🐳 SolarEdge Data Collector - Multi-Platform Docker

## 🌍 Platform Support

✅ **Windows** (Docker Desktop)  
✅ **Linux** (Ubuntu, Debian, CentOS, RHEL, Alpine)  
✅ **macOS** (Intel + Apple Silicon)  
✅ **Raspberry Pi** (ARM64/ARMv7)  
✅ **WSL** (Windows Subsystem for Linux)

## 🚀 Quick Start

### 1. Prerequisites

- **Docker 20.10+** installed
- **Docker Compose v2+**
- **2GB RAM** minimum (4GB recommended)
- **Internet connection** for image downloads

### 2. Setup Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit with your SolarEdge credentials
nano .env  # Linux/macOS
notepad .env  # Windows
```

**Required configuration in `.env`:**
```bash
SOLAREDGE_SITE_ID=123456
SOLAREDGE_API_KEY=your_api_key_here
SOLAREDGE_USERNAME=your.email@example.com
SOLAREDGE_PASSWORD=your_password_here
```

### 3. Platform-Specific Setup

#### Windows (PowerShell)
```powershell
# Make script executable and run
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\docker-setup.ps1

# Or with specific actions
.\docker-setup.ps1 -Start
.\docker-setup.ps1 -Start -Grafana  # Include Grafana dashboard
```

#### Linux/macOS/Raspberry Pi
```bash
# Make script executable and run
chmod +x docker-setup.sh
./docker-setup.sh

# Or with specific actions
./docker-setup.sh start
./docker-setup.sh start --grafana  # Include Grafana dashboard
```

#### Manual Docker Compose
```bash
# Basic setup (SolarEdge + InfluxDB)
docker compose up -d

# With Grafana dashboard
docker compose --profile grafana up -d
```

## 📊 Service Access

After startup, services are available at:

- **SolarEdge GUI**: http://localhost:8092
- **InfluxDB**: http://localhost:8086 (admin/solaredge123)
- **Grafana**: http://localhost:3000 (admin/admin) - *if enabled*

## 🛠️ Management Commands

### PowerShell (Windows)
```powershell
.\docker-setup.ps1 -Status    # Show service status
.\docker-setup.ps1 -Logs      # View logs
.\docker-setup.ps1 -Stop      # Stop services
.\docker-setup.ps1 -Clean     # Full cleanup
.\docker-setup.ps1 -Build     # Rebuild images
```

### Shell (Linux/macOS/Pi)
```bash
./docker-setup.sh status      # Show service status
./docker-setup.sh logs        # View logs
./docker-setup.sh stop        # Stop services
./docker-setup.sh clean       # Full cleanup
./docker-setup.sh build       # Rebuild images
```

### Direct Docker Compose
```bash
docker compose ps              # Service status
docker compose logs -f         # View logs
docker compose down            # Stop services
docker compose down -v         # Stop and remove volumes
```

## 🔧 Configuration

### Environment Variables

The Docker setup uses the same `.env` configuration as the standalone version:

```bash
# SolarEdge API
SOLAREDGE_SITE_ID=123456
SOLAREDGE_API_KEY=your_api_key
SOLAREDGE_USERNAME=your.email@example.com
SOLAREDGE_PASSWORD=your_password

# Database (auto-configured for Docker)
INFLUXDB_URL=http://influxdb:8086
INFLUXDB_TOKEN=solaredge-token-2024
INFLUXDB_ORG=fotovoltaico
INFLUXDB_BUCKET=Solaredge

# Optional: Modbus/TCP for real-time data
REALTIME_MODBUS_HOST=192.168.1.100
REALTIME_MODBUS_PORT=1502
MODBUS_ENABLED=true

# Timezone
TZ=Europe/Rome
```

### Resource Limits

Default resource limits (adjustable in `docker-compose.yml`):

```yaml
deploy:
  resources:
    limits:
      memory: 512M
      cpus: '1.0'
    reservations:
      memory: 256M
      cpus: '0.5'
```

For Raspberry Pi or low-resource systems, reduce limits:
```yaml
limits:
  memory: 256M
  cpus: '0.5'
```

## 🏗️ Multi-Architecture Build

The Docker setup automatically builds for multiple architectures:

- **linux/amd64** - Standard x86_64 systems
- **linux/arm64** - ARM64 systems (Apple Silicon, modern Pi)
- **linux/arm/v7** - ARMv7 systems (older Raspberry Pi)

### Manual Multi-Arch Build
```bash
# Enable buildx
docker buildx create --name solaredge-builder --use

# Build for all platforms
docker buildx build \
  --platform linux/amd64,linux/arm64,linux/arm/v7 \
  --tag solaredge-collector:latest \
  --load .
```

## 📁 Data Persistence

Docker volumes ensure data persistence across container restarts:

- **solaredge-logs** - Application logs
- **solaredge-cache** - Request cache
- **solaredge-cookies** - Web session cookies
- **solaredge-config** - Configuration files
- **solaredge-data** - Application data
- **influxdb-data** - InfluxDB database
- **grafana-data** - Grafana dashboards

### Backup Data
```bash
# Backup all volumes
docker run --rm -v solaredge-data:/data -v $(pwd):/backup alpine tar czf /backup/solaredge-backup.tar.gz /data

# Restore from backup
docker run --rm -v solaredge-data:/data -v $(pwd):/backup alpine tar xzf /backup/solaredge-backup.tar.gz -C /
```

## 🔍 Troubleshooting

### Common Issues

**1. Container won't start**
```bash
# Check logs
docker logs solaredge-collector

# Check configuration
docker exec solaredge-collector env | grep SOLAREDGE
```

**2. InfluxDB connection issues**
```bash
# Check InfluxDB status
docker logs solaredge-influxdb

# Test connection
docker exec solaredge-collector python -c "
from storage.writer_influx import InfluxWriter
try:
    with InfluxWriter() as w:
        print('✅ InfluxDB OK')
except Exception as e:
    print(f'❌ Error: {e}')
"
```

**3. Permission issues (Linux)**
```bash
# Fix Docker permissions
sudo usermod -aG docker $USER
newgrp docker

# Fix file permissions
sudo chown -R $USER:$USER .
```

**4. Port conflicts**
```bash
# Check what's using ports
netstat -tulpn | grep :8092
netstat -tulpn | grep :8086

# Change ports in docker-compose.yml if needed
ports:
  - "8093:8092"  # Use different external port
```

### Performance Optimization

**For Raspberry Pi:**
```yaml
# In docker-compose.yml
deploy:
  resources:
    limits:
      memory: 256M
      cpus: '0.5'

# Reduce cache size in .env
INFLUX_BATCH_SIZE=100
```

**For high-volume systems:**
```yaml
deploy:
  resources:
    limits:
      memory: 1G
      cpus: '2.0'

# Increase batch size in .env
INFLUX_BATCH_SIZE=1000
```

## 🔄 Updates

### Update to Latest Version
```bash
# Pull latest changes
git pull origin main

# Rebuild and restart
./docker-setup.sh clean
./docker-setup.sh build
./docker-setup.sh start
```

### Update Docker Images
```bash
# Update base images
docker compose pull

# Restart services
docker compose up -d
```

## 🧪 Testing

### Test Individual Components
```bash
# Test API collection
docker exec solaredge-collector python main.py --api

# Test web scraping
docker exec solaredge-collector python main.py --web

# Test Modbus (if configured)
docker exec solaredge-collector python main.py --realtime

# Scan for web endpoints
docker exec solaredge-collector python main.py --scan
```

### Health Checks
```bash
# Check container health
docker ps

# Test GUI health endpoint
curl http://localhost:8092/health

# Check InfluxDB
curl http://localhost:8086/health
```

## 📈 Monitoring

### View Real-time Logs
```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f solaredge

# With timestamps
docker compose logs -f -t solaredge
```

### Resource Usage
```bash
# Container stats
docker stats

# Detailed info
docker system df
docker system events
```

## 🔒 Security

### Best Practices

1. **Use non-root user** (already configured)
2. **Limit resources** (configured in compose)
3. **Secure credentials** (use `.env` file)
4. **Regular updates** (update base images)
5. **Network isolation** (uses custom network)

### Firewall Configuration
```bash
# Allow only necessary ports
sudo ufw allow 8092/tcp  # SolarEdge GUI
sudo ufw allow 8086/tcp  # InfluxDB (if external access needed)
sudo ufw allow 3000/tcp  # Grafana (if external access needed)
```

## 📞 Support

For issues specific to Docker deployment:

1. Check logs: `docker compose logs -f`
2. Verify configuration: `docker exec solaredge-collector env`
3. Test connectivity: `docker exec solaredge-collector ping influxdb`
4. Check resources: `docker stats`

For application-specific issues, refer to the main project documentation.