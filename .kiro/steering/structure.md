---
inclusion: always
---

# SolarEdge Data Collector - Architecture & Code Guidelines

## Mandatory Architecture

### Pipeline Pattern (NEVER BYPASS)
Data MUST flow: `Collector → Parser → Filter → Writer → InfluxDB`
- Each stage receives immutable data structures
- Never mix data sources in single execution
- Use dependency injection: `Component(cache_manager, config_manager, logger)`

### Module Structure
- **`collector/`**: Data acquisition (API/web/Modbus) - one source per execution
- **`parser/`**: Transform raw data to InfluxDB point format
- **`filtro/`**: Data validation and filtering rules
- **`storage/`**: Batch InfluxDB writes with error handling
- **`config/`**: Configuration via `ConfigManager` only
- **`app_logging/`**: Centralized logging via `get_logger()`

## Code Requirements

### Async Pattern (MANDATORY)
```python
# HTTP - ALWAYS use aiohttp, never requests
async with aiohttp.ClientSession() as session:
    async with session.get(url) as response:
        data = await response.json()

# Error handling - graceful degradation
try:
    result = await api_call()
except Exception as e:
    logger.error(f"API failed for site {site_id}: {e}")
    continue  # Never crash main loop
```

### Data Structures
- `@dataclass(frozen=True)` for configuration objects
- Type hints required on all functions
- Pass immutable data between pipeline stages

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

## Configuration Rules
- Use `ConfigManager` for all config access - never hardcode
- Environment variables: `${VAR_NAME}` syntax in `config/main.yaml`
- Changes require application restart

## Testing Commands
```bash
python main.py --api        # Test API collection once
python main.py --web        # Test web scraping once
python main.py --realtime   # Test Modbus collection once
python main.py              # Production 24/7 loop
```

## AI Assistant Rules
1. **Test first**: Use single-run modes before modifying loop logic
2. **Preserve async**: Never introduce blocking operations
3. **Maintain separation**: Don't mix data sources
4. **Follow pipeline**: Never bypass stages
5. **Graceful errors**: Continue processing on single source failure
