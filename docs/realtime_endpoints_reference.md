# Realtime Modbus Endpoints – Technical Reference

## Overview

This document describes **how the realtime data collection subsystem works** in the SolarEdge ScanWriter project. It focuses on the internal mechanisms, data structures, and processing pipeline that transform raw Modbus TCP registers into InfluxDB points. No usage examples or operational instructions are included – the goal is to provide a clear technical manual for developers.

---

## 1. Architecture Overview

```
Realtime Flow
└─ collector/collector_realtime.py   →  Modbus TCP read
   └─ solaredge_modbus (third‑party library) – low‑level register access
└─ parser/parser_realtime.py        →  Normalisation, scaling, unit handling
└─ filtro/regole_filtraggio.py      →  Structured point validation
└─ storage/writer_influx.py          →  InfluxDB point write (measurement = "realtime")
```

All components are driven by configuration stored in `config/sources/modbus_endpoints.yaml` (accessed via `ConfigManager`).

---

## 2. Configuration (`modbus_endpoints.yaml`)

The YAML file defines three logical device groups:

| Group | Key in YAML | Enabled Flag | Device Type |
|-------|-------------|--------------|-------------|
| Inverter | `inverter_realtime` | `enabled: true/false` | `inverter` |
| Meters   | `meters`            | `enabled: true/false` | `meter` |
| Batteries| `batteries`        | `enabled: true/false` | `battery` |

Each group contains a `measurements` mapping where individual register fields are described:

```yaml
measurements:
  voltage: {enabled: true, unit: V}
  current: {enabled: true, unit: A}
  temperature: {enabled: true, unit: C}
  # ... other registers ...
```

Only measurements with `enabled: true` are parsed and written to InfluxDB.

---

## 3. Collector – `RealtimeCollector`

### 3.1 Initialization
* Loads logger (`app_logging.get_logger`).
* Retrieves the realtime connection config (`host`, `port`, `timeout`, `unit`).
* Loads the full Modbus endpoint configuration via `ConfigManager.get_modbus_endpoints()`.
* Verifies that Modbus collection is globally enabled; otherwise raises `ValueError`.

### 3.2 Data Collection (`collect_raw_data`)
* Wrapped in `timed_operation` context manager to log duration.
* Calls `_fetch_raw_data(host, port)` which:
  1. Instantiates `solaredge_modbus.Inverter` with the configured host/port.
  2. Calls `read_all()` → dictionary of all inverter registers.
  3. Calls `meters()` and `batteries()` → dictionaries of per‑device objects.
  4. Builds a **raw data structure**:
     ```python
     raw_data = {
         "inverter": inverter_values,
         "meters": {},
         "batteries": {}
     }
     ```
  5. If the corresponding group is enabled in the YAML, iterates over each meter/battery object and stores the result of `read_all()` under its name.
* Returns the nested raw dictionary.

---

## 4. Parser – `RealtimeParser`

The parser is responsible for **normalising units, applying scaling factors, and converting raw values into InfluxDB `Point` objects**.

### 4.1 Configuration Loading
* On construction it loads the Modbus endpoint configuration (`self._modbus_endpoints`).
* Pre‑populates caches for dynamic device IDs:
  * `inverter` – cached from `c_model` field.
  * `meters` – cached per meter name from `c_serialnumber` or `c_model`.
  * `batteries` – cached from `c_model`.
* Defines a unit normalisation map (`C → °C`, `F → °F`).

### 4.2 Enabled Measurements Helper
```python
def _get_enabled_measurements(self, endpoint_config: dict) -> dict:
    measurements = endpoint_config.get('measurements', {})
    return {name: cfg for name, cfg in measurements.items() if cfg.get('enabled', False)}
```
Only enabled measurements are processed.

### 4.3 Parsing Entry Point (`parse_raw_data`)
* Validates that `raw_data` is not empty.
* Delegates to three private methods:
  * `_parse_inverter_raw`
  * `_parse_meters_raw`
  * `_parse_batteries_raw`
* Aggregates all returned `Point` objects into a single list.
* Logs the total point count and duration.

### 4.4 Inverter Parsing (`_parse_inverter_raw`)
* Retrieves the inverter endpoint configuration.
* Determines the device identifier:
  * Uses cached `device_id` if present.
  * Falls back to `c_model` from the raw payload.
* Iterates over each key/value pair:
  * Strips the `c_` prefix.
  * Skips keys not present in the enabled measurement set.
  * Constructs a **human‑readable endpoint name** by title‑casing the key (`voltage_ac → Voltage Ac`).
  * Retrieves the scale factor from a sibling key (`{key}_scale`).
  * Applies special handling for `energy_total` where a scale of `1` indicates a firmware bug – the value is divided by `10`.
  * Applies generic scaling: `final_value = value * (10 ** scale)` unless `scale == -32768` (invalid), in which case the entry is ignored.
  * Normalises the unit using the configuration map.
  * Creates an InfluxDB `Point` with:
    * Measurement: `realtime`
    * Tags: `device_id`, `endpoint` (human name), `unit`
    * Field: `Inverter` (numeric) or `Inverter_Text` (string) depending on the final value type.
    * Timestamp: `datetime.now(timezone.utc)`.
* Returns the list of points.

### 4.5 Meters Parsing (`_parse_meters_raw`)
* Similar flow to inverter parsing but operates per‑meter name.
* Device ID resolution hierarchy:
  1. Cached ID for the meter name.
  2. `c_serialnumber` → `meter_{serial}`
  3. `c_model`
* Uses a **special‑scale‑key map** for registers that do not follow the `{key}_scale` convention (e.g., `import_energy_active` → `energy_active_scale`).
* Applies scaling, unit normalisation, and point creation analogous to the inverter parser, but the field name is `Meter` (numeric) or `Meter_Text`.

### 4.6 Batteries Parsing (`_parse_batteries_raw`)
* Mirrors the meter parser with device‑type‑specific tags.
* Device ID derived from cached value or `c_model`.
* Uses generic `{key}_scale` scaling.
* Points are created with field name `Battery` or `Battery_Text`.

---

## 5. Filtering – `filter_structured_points`

The realtime flow re‑uses the generic structured‑point filter located in `filtro/regole_filtraggio.py`. It validates:
* Presence of required tags (`device_id`, `endpoint`).
* Numeric field values are within reasonable bounds (configured in the filter rules).
* Discards points that fail validation, logging the reason.

---

## 6. InfluxDB Storage

All realtime points are written to the **`realtime` measurement** in the configured InfluxDB bucket.

### 6.1 Tag Schema
| Tag | Description |
|-----|-------------|
| `device_id` | Cached identifier for the physical device (inverter, meter, battery). |
| `endpoint`  | Human‑readable name derived from the register key (e.g., `Voltage Ac`). |
| `unit`      | Normalised unit string (`V`, `A`, `°C`, etc.). |

### 6.2 Field Schema
* Numeric values are stored under a type‑specific field name (`Inverter`, `Meter`, `Battery`).
* Non‑numeric values (e.g., status strings) are stored under `<Type>_Text`.

### 6.3 Timestamp
* Generated at point creation time using `datetime.now(timezone.utc)`. The writer does **not** modify timestamps; they reflect the moment of collection.

---

## 7. Error Handling & Logging

* **Configuration errors** (missing or disabled Modbus) raise `ValueError` during collector initialization.
* **Connection errors** (TCP timeout, socket failure) propagate as exceptions and are logged by the collector before being re‑raised.
* **Parsing errors** are caught per‑device group; the parser logs the exception and returns an empty list for that group, allowing the pipeline to continue with other data.
* **Scaling errors** (invalid scale values) are silently skipped (`continue`).
* All major steps emit structured log entries with `extra` fields for easy downstream analysis.

---

## 8. Extensibility

To add a new realtime register:
1. Add the register under the appropriate group in `modbus_endpoints.yaml` with `enabled: true` and a `unit`.
2. Ensure the Modbus device exposes a `{register}_scale` register (or add an entry to the **special‑scale‑key map** in `parser_realtime.py`).
3. No code changes are required – the parser automatically discovers enabled measurements and applies scaling.

---

## 9. Technical Appendices

### Appendix A: Hardcoded Scale Mappings
The parser contains a hardcoded dictionary (`special_scale_keys`) to map registers to their scale factors when they deviate from the standard `{name}_scale` pattern. This is critical for correct value interpretation.

| Register Pattern | Mapped Scale Key |
|------------------|------------------|
| `*import_energy_active` | `energy_active_scale` |
| `*export_energy_active` | `energy_active_scale` |
| `*import_energy_apparent` | `energy_apparent_scale` |
| `*export_energy_apparent` | `energy_apparent_scale` |
| `*import_energy_reactive_*` | `energy_reactive_scale` |
| `*export_energy_reactive_*` | `energy_reactive_scale` |
| `*voltage_ln`, `*l*n_voltage` | `voltage_scale` |
| `*voltage_ll`, `*l*voltage` | `voltage_scale` |
| `frequency` | `frequency_scale` |
| `*power` | `power_scale` |
| `*power_apparent` | `power_apparent_scale` |
| `*power_reactive` | `power_reactive_scale` |
| `*power_factor` | `power_factor_scale` |
| `*current` | `current_scale` |

### Appendix B: Unit Normalization
The parser normalizes specific unit strings to ensure consistency in InfluxDB.

| Configured Unit | Stored Unit |
|-----------------|-------------|
| `C` | `°C` |
| `F` | `°F` |
| *All others* | *As configured* |

### Appendix C: Firmware Bug Workarounds
**Energy Total Scaling Bug**:
- **Condition**: `endpoint == 'energy_total'` AND `scale == 1`
- **Action**: Divide value by 10 (instead of multiplying by 10^1)
- **Reason**: Corrects known firmware reporting error where scale 1 is incorrectly reported for what should be scale -1 or 0.

## 10. Summary of Data Flow

1. **Collector** reads raw registers via Modbus TCP → nested dictionary.
2. **Parser** loads endpoint config, resolves device IDs, applies scaling (standard + special maps), normalises units, creates InfluxDB `Point` objects.
3. **Filter** validates points against rule set.
4. **Writer** writes validated points to InfluxDB measurement `realtime`.
5. **Logging** records duration and any errors at each stage.

This document provides a complete technical description of the realtime data collection subsystem, suitable for developers needing to understand, extend, or debug the implementation.
