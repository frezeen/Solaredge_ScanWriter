---
inclusion: always
---

# SolarEdge Data Collector - AI Assistant Guidelines

## Architecture (NON-NEGOTIABLE)

### Pipeline Pattern

Data MUST flow: `Collector → Parser → Filter → Writer → InfluxDB`

- Never bypass stages or mix data sources in single execution
- Use `@dataclass(frozen=True)` for immutable data between stages
- Dependency injection: `Component(cache_manager, config_manager, logger)`

### Data Sources (NEVER MIX)

- **API** (`collector_api.py`): Official SolarEdge API, 15min intervals
- **Web** (`collector_web.py`): Portal scraping, 15min intervals
- **Modbus** (`collector_realtime.py`): Real-time inverter data, 5sec intervals

## Technology Requirements

### Python 3.10+ with Async/Await

- ALL I/O operations must be asynchronous
- Use `aiohttp.ClientSession` for HTTP (NEVER `requests`)
- Use async InfluxDB client methods
- Type hints required on all function parameters and returns

### Core Dependencies (DO NOT SUBSTITUTE)

- `aiohttp`: HTTP client/server operations
- `influxdb-client-python`: InfluxDB 2.x API only
- `solaredge_modbus`: Modbus TCP communication
- `PyYAML`: Configuration management
- `python-dotenv`: Environment variables

## Code Standards

### Required Patterns

```python
# HTTP requests
async with aiohttp.ClientSession() as session:
    async with session.get(url) as response:
        data = await response.json()

# Configuration access
config = ConfigManager()
api_key = config.get_api_key()  # Never hardcode

# Error handling - graceful degradation
try:
    result = await api_call()
except Exception as e:
    logger.error(f"API failed for site {site_id}: {e}")
    continue  # Never crash main loop

# Logging
logger = get_logger(__name__)
logger.info(f"Processing {len(data)} measurements")
```

### Import Order

```python
# Standard library (alphabetical)
import asyncio
from datetime import datetime

# Third-party (alphabetical)
import aiohttp
from influxdb_client import InfluxDBClient

# Local modules (alphabetical)
from config.config_manager import ConfigManager
from app_logging.universal_logger import get_logger
```

## Testing Commands (USE THESE)

```bash
# Single execution tests (use for development)
python main.py --api        # Test API collection once
python main.py --web        # Test web scraping once
python main.py --realtime   # Test Modbus collection once

# Production mode
python main.py              # 24/7 scheduled loop

# Configuration tools
python main.py --gui scan   # Update config from web scan
python main.py --gui        # Web interface
```

## AI Assistant Rules

1. **Test first**: Always use single-run modes (`--api`, `--web`, `--realtime`) before modifying loop logic
2. **Preserve async**: Never introduce blocking operations
3. **Maintain separation**: Process ONE data source type per execution
4. **Follow pipeline**: Never bypass `Collector → Parser → Filter → Writer` stages
5. **Graceful errors**: Continue processing on single source failure, never crash main loop
6. **Use ConfigManager**: Never hardcode credentials or URLs
7. **Validate data**: All external data must pass through `filtro/regole_filtraggio.py`
8. **Respect limits**: Especially for web scraping rate limits

## Module Structure

- `collector/`: Data acquisition (API/web/Modbus) - one source per execution
- `parser/`: Transform raw data to InfluxDB point format
- `filtro/`: Data validation and filtering rules
- `storage/`: Batch InfluxDB writes with error handling
- `config/`: Configuration via `ConfigManager` only
- `app_logging/`: Centralized logging via `get_logger()`
