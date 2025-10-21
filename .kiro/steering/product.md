---
inclusion: always
---

# SolarEdge Data Collector - Development Guidelines

## Architecture (MANDATORY)

**Pipeline Pattern**: `Collector → Parser → Filter → Writer → InfluxDB`
- Never bypass stages - data must flow through all four components
- Use `@dataclass(frozen=True)` for immutable data between stages
- Dependency injection: `Component(cache_manager, config_manager, logger)`

**Python 3.10+ Required**: Use async/await for ALL I/O operations

## Data Sources (NEVER MIX)

- **API** (`collector_api.py`): Official SolarEdge API, 15min intervals
- **Web** (`collector_web.py`): Portal scraping, 15min intervals  
- **Modbus** (`collector_realtime.py`): Real-time inverter data, 5sec intervals

**Critical Rule**: Process ONE data source type per execution. Never combine sources in same measurement.

## Code Standards

### Required Patterns
```python
# HTTP - ALWAYS use aiohttp, never requests
async with aiohttp.ClientSession() as session:
    async with session.get(url) as response:
        data = await response.json()

# Configuration - use ConfigManager, never hardcode
config = ConfigManager()
api_key = config.get_api_key()

# Error handling - graceful degradation, never crash main loop
try:
    result = await api_call()
except Exception as e:
    logger.error(f"API failed for site {site_id}: {e}")
    continue
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

### Logging
```python
logger = get_logger(__name__)
logger.info(f"Processing {len(data)} measurements for site {site_id}")
logger.error(f"Validation failed: {error}")
```

## Module Responsibilities

- **`collector/`**: Data acquisition only (API, web, Modbus)
- **`parser/`**: Transform to InfluxDB point format
- **`filtro/`**: Data validation and filtering
- **`storage/`**: Batch InfluxDB writes with error handling
- **`config/`**: Configuration management via `ConfigManager`
- **`app_logging/`**: Centralized logging via `get_logger()`

## Testing Commands

```bash
# Single execution tests
python main.py --api        # Test API collection
python main.py --web        # Test web scraping  
python main.py --realtime   # Test Modbus collection

# Production mode
python main.py              # 24/7 scheduled loop

# Configuration tools
python main.py --gui scan   # Update config from web scan
python main.py --gui        # Web interface
```

## AI Assistant Rules

1. **Test first**: Use single-run modes (`--api`, `--web`, `--realtime`) before modifying loop logic
2. **Preserve async**: Never introduce blocking operations
3. **Maintain separation**: Don't mix data sources in same execution
4. **Use existing patterns**: Follow established error handling and dependency injection
5. **Validate data**: All external data must pass through `filtro/regole_filtraggio.py`
6. **Respect limits**: Especially for web scraping rate limits
7. **Configuration changes**: Validate with `--gui scan` mode
