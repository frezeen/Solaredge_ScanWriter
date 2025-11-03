# 🐳 SolarEdge Docker

Multi-platform Docker setup for SolarEdge Data Collector.

## 🌍 Supported Platforms

✅ **Windows** (AMD64, ARM64)  
✅ **Linux** (AMD64, ARM64, ARMv7)  
✅ **Raspberry Pi** (ARM64, ARMv7)  

## 🚀 Quick Start

### 1. Configuration

Copy and edit environment file:
```bash
cp .env.example .env
# Edit .env with your SolarEdge credentials
```

Required variables in `.env`:
```bash
SOLAREDGE_SITE_ID=123456
SOLAREDGE_API_KEY=your_api_key_here
SOLAREDGE_USERNAME=your.email@example.com
SOLAREDGE_PASSWORD=your_password_here
```

### 2. Build & Run

#### Linux/macOS/Raspberry Pi
```bash
chmod +x docker-build.sh
./docker-build.sh
docker compose up -d
```

#### Windows (PowerShell)
```powershell
.\docker-build.ps1
docker compose up -d
```

#### Manual Build
```bash
docker build -t solaredge-scanwriter:latest .
docker compose up -d
```

## 📊 Services

After startup, access:
- **SolarEdge GUI**: http://localhost:8092
- **InfluxDB**: http://localhost:8086 (admin/solaredge123)
- **Grafana**: http://localhost:3000 (admin/admin)

## 🔧 Management

```bash
# View logs
docker compose logs -f

# Check status
docker compose ps

# Stop services
docker compose down

# Restart services
docker compose restart

# Shell access
docker exec -it solaredge-scanwriter bash
```

## 🧪 Testing Components

```bash
# Test API collection
docker exec solaredge-scanwriter python main.py --api

# Test web scraping
docker exec solaredge-scanwriter python main.py --web

# Generate web endpoints
docker exec solaredge-scanwriter python main.py --scan

# Download historical data
docker exec solaredge-scanwriter python main.py --history

# Test Modbus (if configured)
docker exec solaredge-scanwriter python main.py --realtime
```

## 📁 Architecture

- **Dockerfile**: Multi-platform container definition
- **docker-compose.yml**: Complete stack (SolarEdge + InfluxDB + Grafana)
- **docker-build.sh**: Linux/macOS build script
- **docker-build.ps1**: Windows PowerShell build script
- **grafana/**: Grafana configuration and dashboards

## 🔄 Updates

### Universal Update Method
```bash
# Pull latest changes and update
git pull origin dev
./docker-build.sh  # Linux/macOS/Pi
# or
.\docker-build.ps1  # Windows
```

This single command handles all updates:
- Code changes
- New features
- Dashboard updates
- Configuration updates
- Dependency updates

**Your configuration files (.env, custom configs) are preserved.**

## 🛠️ Troubleshooting

### Container won't start
```bash
docker logs solaredge-scanwriter
```

### Check configuration
```bash
docker exec solaredge-scanwriter env | grep SOLAREDGE
```

### Test InfluxDB connection
```bash
docker exec solaredge-scanwriter python -c "
from storage.writer_influx import InfluxWriter
try:
    with InfluxWriter() as w:
        print('✅ InfluxDB OK')
except Exception as e:
    print(f'❌ Error: {e}')
"
```

### Port conflicts
Change ports in `docker-compose.yml` if needed:
```yaml
ports:
  - "8093:8092"  # Use different external port
```

## 📋 Requirements

- Docker 20.10+
- Docker Compose v2+
- 2GB RAM minimum (4GB recommended)
- SolarEdge account with API access