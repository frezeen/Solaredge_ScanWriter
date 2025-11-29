# Web Data Storage - Technical Reference

## Purpose

This document describes **how the web data storage system works** technically in InfluxDB. It does NOT describe how to query it or what to do with it, but rather the technical implementation of data storage.

---

## InfluxDB Storage Structure

### Measurement Name
All web scraping data is stored in a single measurement: **`web`**

### Data Point Structure

Each data point written to InfluxDB has:

**Tags** (indexed, used for filtering):
- `endpoint`: The measurement type from API (e.g., "PRODUCTION_POWER", "PRODUCTION_ENERGY")
- `device_id`: The device identifier (e.g., "7403D7C5-13", "606483640", "weather_default")
- `unit`: The unit of measurement (e.g., "W", "Wh", "V", "A", "°C") - optional

**Fields** (actual values):
- Field name is determined by the **category** from `web_endpoints.yaml`
- Field value is the numeric measurement value
- If value cannot be converted to float, it's stored as string

**Timestamp**:
- Nanosecond precision
- Converted from API milliseconds: `timestamp_ms * 1_000_000`

---

## Category System

### What is Category?

Category is defined in `config/sources/web_endpoints.yaml` for each device and determines the **field name** used in InfluxDB.

### Category Mapping

| Category | Field Name | Data Type | Typical Values |
|----------|------------|-----------|----------------|
| `Inverter` | `Inverter` | float | Power, Energy, Voltage, Current |
| `Meter` | `Meter` | float | Power, Energy, Voltage, Current |
| `Site` | `Site` | float | Production/Import/Export Power/Energy |
| `Optimizer group` | `Optimizer group` | float | Power, Energy, Voltage, Current |
| `String` | `String` | float | Power, Energy |
| `Weather` | `Weather` | float | Temperature, Wind Speed, Humidity |
| `Info` (default) | `Info` | float/string | Generic data |

### How Category is Determined

1. **Parser reads** `web_endpoints.yaml` configuration
2. **Matches** `device_id` from API response to config entry
3. **Extracts** `category` field from matched config
4. **Uses** category as InfluxDB field name
5. **Fallback**: If no match found, uses `"Info"` as default

Code location: `parser/web_parser.py` → `_get_category_from_config()` (line 138-156)

---

## Data Flow Pipeline

### Step 1: API Response

CollectorWeb receives JSON from SolarEdge API:
```json
{
  "list": [
    {
      "device": {
        "itemType": "OPTIMIZER",
        "id": "21830A42-F0"
      },
      "measurementType": "PRODUCTION_POWER",
      "unitType": "W",
      "measurements": [
        {
          "time": "2025-11-29T10:00:00+01:00",
          "measurement": 245.5
        }
      ]
    }
  ]
}
```

### Step 2: Raw Point Creation

Parser extracts data and creates raw point:
```python
{
    "source": "web",
    "device_id": "21830A42-F0",
    "device_type": "OPTIMIZER",
    "metric": "PRODUCTION_POWER",
    "value": 245.5,
    "timestamp": 1732875600000,  # milliseconds
    "unit": "W",
    "category": "Optimizer group"  # from config
}
```

Code location: `parser/web_parser.py` → `_create_raw_point()` (line 78-97)

### Step 3: InfluxDB Point Conversion

Raw point is converted to InfluxDB Point object:
```python
Point("web")
    .tag("endpoint", "PRODUCTION_POWER")
    .tag("device_id", "21830A42-F0")
    .tag("unit", "W")
    .field("Optimizer group", 245.5)  # category as field name
    .time(1732875600000000000, WritePrecision.NS)
```

Code location: `parser/web_parser.py` → `_convert_raw_point_to_influx_point()` (line 106-136)

### Step 4: Storage

InfluxWriter writes the point to InfluxDB bucket.

Code location: `storage/writer_influx.py` → `write_points()` (line 158)

---

## Device ID Patterns

### How Device IDs are Determined

Device IDs come from the API response `device.id` field, with special handling:

| Device Type | ID Source | Example | Notes |
|-------------|-----------|---------|-------|
| INVERTER | API `id` | `7403D7C5-13` | Serial number with suffix |
| METER | API `id` | `606483640` | Numeric ID |
| OPTIMIZER | API `id` | `21830A42-F0` | Serial number with suffix |
| STRING | API `id` | `0`, `1`, `2` | Numeric index |
| SITE | API `id` | `2489781` | Site ID number |
| WEATHER | Hardcoded | `weather_default` | Always same ID |

Code location: `parser/web_parser.py` → `_extract_device_info()` (line 38-55)

---

## Unit Normalization

Units from API are normalized to standard format:

| API Unit | Normalized | Notes |
|----------|------------|-------|
| `w`, `W` | `W` | Watts |
| `wh`, `Wh` | `Wh` | Watt-hours |
| `kw`, `kW` | `kW` | Kilowatts |
| `kwh`, `kWh` | `kWh` | Kilowatt-hours |
| Others | Unchanged | Passed through as-is |

Code location: `parser/web_parser.py` → `_normalize_unit()` (line 99-104)

---

## Timestamp Handling

### Input Format

API provides timestamps in ISO 8601 format:
- `"2025-11-29T10:00:00+01:00"` (with timezone)
- `"2025-11-29T10:00:00Z"` (UTC)

### Conversion Process

1. **Parse** ISO 8601 string to datetime object
2. **Convert** to UTC if timezone-aware
3. **Extract** Unix timestamp in milliseconds
4. **Multiply** by 1,000,000 to get nanoseconds
5. **Write** to InfluxDB with nanosecond precision

Code location: `parser/web_parser.py` → `_convert_timestamp()` (line 57-76)

---

## Data Filtering

Before writing to InfluxDB, raw points pass through filtering:

### Filter Rules

1. **Null values**: Points with `value = None` are discarded
2. **Invalid timestamps**: Points with `timestamp <= 0` are discarded
3. **Duplicate detection**: Implemented in `filtro/regole_filtraggio.py`

Code location: `parser/web_parser.py` → `parse_web()` (line 194)

---

## Measurement Types by Device

### INVERTER
- `AC_PRODUCTION_POWER` (W)
- `AC_PRODUCTION_ENERGY` (Wh)
- `AC_CONSUMPTION_POWER` (W)
- `AC_CONSUMPTION_ENERGY` (Wh)
- `AC_VOLTAGE` (V)
- `AC_CURRENT` (A)
- `AC_FREQUENCY` (Hz)
- `DC_VOLTAGE` (V)
- `KWH_KWP_RATIO` (ratio)

### METER
- `IMPORT_POWER` (W)
- `IMPORT_ENERGY` (Wh)
- `EXPORT_POWER` (W)
- `EXPORT_ENERGY` (Wh)

### OPTIMIZER
- `PRODUCTION_POWER` (W)
- `PRODUCTION_ENERGY` (Wh)
- `MODULE_CURRENT` (A)
- `MODULE_OUTPUT_VOLTAGE` (V)
- `OPTIMIZER_OUTPUT_VOLTAGE` (V)

### SITE
- `PRODUCTION_POWER` (W)
- `PRODUCTION_ENERGY` (Wh)
- `IMPORT_POWER` (W)
- `IMPORT_ENERGY` (Wh)
- `EXPORT_POWER` (W)
- `EXPORT_ENERGY` (Wh)
- `KWH_KWP_RATIO` (ratio)

### STRING
- `PRODUCTION_POWER` (W)
- `PRODUCTION_ENERGY` (Wh)

### WEATHER
- `TEMPERATURE` (°C)
- `WIND_SPEED` (m/s)
- `HUMIDITY` (%)
- `IRRADIANCE` (W/m²)

---

## Storage Example

### Input (API Response)
```json
{
  "device": {"itemType": "SITE", "id": "2489781"},
  "measurementType": "PRODUCTION_ENERGY",
  "unitType": "Wh",
  "measurements": [
    {"time": "2025-11-29T10:00:00Z", "measurement": 15420}
  ]
}
```

### Output (InfluxDB Point)
```
Measurement: web
Tags:
  endpoint=PRODUCTION_ENERGY
  device_id=2489781
  unit=Wh
Fields:
  Site=15420.0
Timestamp: 1732875600000000000 (nanoseconds)
```

### InfluxDB Line Protocol
```
web,endpoint=PRODUCTION_ENERGY,device_id=2489781,unit=Wh Site=15420.0 1732875600000000000
```

---

## Configuration Dependency

### web_endpoints.yaml Role

The parser **requires** `web_endpoints.yaml` to determine categories:

1. **Without config**: All data stored with field name `"Info"`
2. **With config**: Data stored with proper category field names

### Config Structure Used
```yaml
web_scraping:
  endpoints:
    site_2489781:
      device_id: "2489781"
      category: "Site"  # ← Used as InfluxDB field name
```

---

## Error Handling

### Missing Category
- **Trigger**: `device_id` not found in `web_endpoints.yaml`
- **Action**: Use `"Info"` as default category
- **Log**: Warning message with available device IDs

### Invalid Value
- **Trigger**: Value cannot be converted to float
- **Action**: Store as string in InfluxDB
- **Log**: Debug message

### Missing Timestamp
- **Trigger**: Timestamp is None or <= 0
- **Action**: Discard the data point
- **Log**: No log (silent discard)

---

## Supported Date Ranges

Based on technical testing, the SolarEdge API has specific limitations on date ranges for different device types:

| Device Type | 1 Day | 3 Days | 7 Days | 1 Month | Notes |
|-------------|-------|--------|--------|---------|-------|
| **OPTIMIZER** | ✅ | ✅ | ✅ | ❌ | Fails with HTTP 400 for ranges > 7 days |
| **SITE** | ✅ | ✅ | ✅ | ✅ | Supports full monthly range |
| **WEATHER** | ✅ | ✅ | ✅ | ✅ | Supports full monthly range |
| **INVERTER** | ✅ | ✅ | ✅ | ✅ | Generally supports monthly range |
| **METER** | ✅ | ✅ | ✅ | ✅ | Generally supports monthly range |

**Technical Implication**:
- For **Optimizers**, the collector must split monthly requests into smaller chunks (e.g., daily or weekly) to avoid errors.
- For **Site/Weather**, bulk monthly collection is efficient and supported.

---

## Performance Considerations

### Batch Writing
- Points are collected in memory
- Written in batches to InfluxDB
- Batch size: 500 points (configurable)

### Tag Cardinality
- `endpoint`: ~10-20 unique values per device type
- `device_id`: Number of physical devices (typically 1-50)
- `unit`: ~10 unique values total

**Total cardinality**: Low (< 1000 unique tag combinations)

---

## Summary

The web data storage system:

1. **Receives** JSON from SolarEdge API
2. **Parses** device info and measurements
3. **Looks up** category from configuration
4. **Creates** InfluxDB points with:
   - Measurement: `web`
   - Tags: `endpoint`, `device_id`, `unit`
   - Field: Named by category, value from API
   - Timestamp: Nanosecond precision
5. **Writes** to InfluxDB in batches

**Key Design**: Category system allows flexible field naming while maintaining consistent measurement structure.
