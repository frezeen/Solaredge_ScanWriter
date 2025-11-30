# GUI Core Components – Technical Reference

## Overview

This document describes **how the GUI Core subsystem works**. It details the internal architecture, component responsibilities, and data flow mechanisms that power the frontend-backend interaction.

---

## 1. Architecture Overview

The GUI Core (`gui/core/`) follows the Single Responsibility Principle (SRP) and provides modular services for the web interface.

```
gui/core/
├── config_handler.py          →  Configuration Management (I/O, Caching)
├── state_manager.py           →  State Tracking & Log Buffering
├── unified_toggle_handler.py  →  Entity Toggle Logic (Device/Metric/Endpoint)
├── middleware.py              →  HTTP Request Processing Stack
└── loop_adapter.py            →  Orchestration Layer
```

---

## 2. Configuration Handler (`ConfigHandler`)

**File**: `gui/core/config_handler.py`

Responsible for all YAML file operations, providing a unified interface for loading, saving, and validating configuration.

### 2.1 Caching Mechanism
- Maintains an internal dictionary `_config_cache`.
- **Load**: Checks cache first; if miss, reads file and caches result.
- **Save**: Writes to file and updates cache immediately.
- **Invalidation**: `invalidate_cache(source_type)` clears specific or all entries.

### 2.2 Source Mapping
Uses a lookup table (`SOURCE_CONFIG_MAP`) to abstract file paths:

| Source Type | File Path | Root Key | Data Key |
|-------------|-----------|----------|----------|
| `web` | `config/sources/web_endpoints.yaml` | `web_scraping` | `endpoints` |
| `api` | `config/sources/api_endpoints.yaml` | `api_ufficiali` | `endpoints` |
| `modbus` | `config/sources/modbus_endpoints.yaml` | `modbus` | `endpoints` |

### 2.3 Async I/O
- Uses `aiofiles` for non-blocking file operations.
- Uses `utils.yaml_loader` for consistent YAML parsing and validation.

---

## 3. State Manager (`StateManager`)

**File**: `gui/core/state_manager.py`

Manages the application's runtime state, loop status, and log buffering.

### 3.1 Log Buffering
- **Structure**: Uses `collections.deque` with `maxlen` for auto-eviction (preventing memory leaks).
- **Flow Tracking**: Maintains separate deques for each flow type (`api`, `web`, `realtime`, `gme`).
- **Run Grouping**: Groups logs into "runs" based on start markers (e.g., "🚀 Avvio flusso...").
  - API/Web/GME: Keeps last 3 runs.
  - Realtime: Keeps last 5 runs.
- **General Logs**: Separate list for system messages (no run concept).

### 3.2 Loop Statistics
Tracks execution metrics in `loop_stats` dictionary:
- Execution counts (success/failed).
- Timestamps (start time, last update, next run).
- Status (`running`, `stopped`).

### 3.3 Serialization (`get_loop_status`)
Prepares state for JSON response:
- Calculates uptime.
- Formats `datetime` objects to strings (`HH:MM:SS`).
- Removes non-serializable objects before returning.

---

## 4. Unified Toggle Handler (`UnifiedToggleHandler`)

**File**: `gui/core/unified_toggle_handler.py`

Consolidates all toggle logic (enabling/disabling entities) into a single 7-step process.

### 4.1 Supported Entities
- `web_device` / `web_metric`
- `modbus_device` / `modbus_metric`
- `api_endpoint`

### 4.2 The 7-Step Toggle Process (`_toggle_entity`)
1. **Load Config**: Reads YAML based on entity type.
2. **Navigate**: Locates the specific entity in the config structure.
3. **Toggle**: Inverts the `enabled` boolean.
4. **Cascade (Device → Metrics)**:
   - If a device is toggled, applies the new state to all its metrics.
5. **Auto-Update Source**:
   - Checks if *any* entity in the source is enabled.
   - Updates the parent source's `enabled` flag accordingly.
   - Example: If all Modbus devices are disabled, `modbus.enabled` becomes `false`.
6. **Save**: Writes updated config to disk.
7. **Response**: Returns success status and updated state.

### 4.3 Smart Device Auto-Toggle
When toggling a **metric**:
- **Enable Metric**: Automatically enables the parent device if it was disabled.
- **Disable Metric**: Automatically disables the parent device if *no other metrics* remain enabled.

---

## 5. Middleware Stack (`middleware.py`)

**File**: `gui/core/middleware.py`

Centralized HTTP processing pipeline.

### 5.1 Stack Order
1. **ErrorHandler**: Catches unhandled exceptions, returns JSON 500.
2. **RequestLogging**: Logs method, path, and execution time (ms).
3. **CORS**: Adds Access-Control headers for cross-origin requests.
4. **SecurityHeaders**: Adds CSP, X-Frame-Options, X-Content-Type-Options.

### 5.2 Factory
`create_middleware_stack(logger)` returns the configured list of middleware for `aiohttp.web.Application`.

---

## 6. Summary of Data Flow

1. **Frontend Request** (e.g., Toggle Switch) → **Middleware** (Logging/Security).
2. **Route Handler** calls **UnifiedToggleHandler**.
3. **UnifiedToggleHandler** uses **ConfigHandler** to load YAML.
4. **Logic Applied** (Toggle + Cascade + Auto-Update).
5. **ConfigHandler** saves YAML.
6. **StateManager** logs the action.
7. **Response** sent back through Middleware.

This architecture ensures separation of concerns, consistent error handling, and robust state management.
