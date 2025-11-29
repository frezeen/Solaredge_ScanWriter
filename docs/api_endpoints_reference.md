# API Data Storage - Technical Reference

## Purpose

This document describes **how the SolarEdge API data storage system works** technically in InfluxDB. It does NOT describe how to query it or what to do with it, but rather the technical implementation of data collection, parsing, and storage.

---

## InfluxDB Storage Structure

### Measurement Name
All API data is stored in a single measurement: **`api`**

### Data Point Structure

Each data point written to InfluxDB has:

**Tags** (indexed, used for filtering):
- `endpoint`: The API endpoint name (e.g., "site_energy_details", "equipment_data")
- `metric`: The meter type or specific metric (e.g., "Production", "temperature", "L1Data_acCurrent")
- `unit`: The unit of measurement (e.g., "W", "Wh", "V", "A", "°C") - optional

**Fields** (actual values):
- Field name is determined by the **category** from `api_endpoints.yaml`
- Field value is either:
  - Numeric value (float) for structured data
  - JSON string for metadata endpoints

**Timestamp**:
- Nanosecond precision
- Converted from parsed datetime: `timestamp_seconds * 1_000_000_000`

---

## Category System

### What is Category?

Category is defined in `config/sources/api_endpoints.yaml` for each endpoint and determines the **field name** used in InfluxDB.

### Category Mapping

| Category | Field Name | Data Type | Typical Endpoints |
|----------|------------|-----------|-------------------|
| `Inverter` | `Inverter` | float | site_energy_*, site_timeframe_energy, equipment_data |
| `Meter` | `Meter` | float | site_energy_details, site_power_details |
| `Flusso` | `Flusso` | string (JSON) | site_power_flow |
| `Info` | `Info` | string (JSON) | site_details, site_overview, equipment_list, etc. |

### How Category is Determined

1. **Parser reads** endpoint configuration from `api_endpoints.yaml`
2. **Extracts** `category` field from endpoint config
3. **Uses** category as InfluxDB field name
4. **Error**: If category missing, raises ValueError

Code location: `parser/api_parser.py` → `_create_raw_point()` (line 69-90), `_create_structured_dicts()` (line 410-456)

---

## Data Flow Pipeline

### Step 1: API Request

CollectorAPI builds and executes HTTP requests:

```python
# URL construction
url = f"{base_url}/site/{site_id}/energyDetails"

# Parameters
params = {
    'api_key': api_key,
    'startTime': '2025-11-29 00:00:00',
    'endTime': '2025-11-29 23:59:59',
    'meters': 'PRODUCTION,CONSUMPTION'
}

# HTTP call
response = session.get(url, params=params, timeout=30)
data = response.json()
```

Code location: `collector/collector_api.py` → `_call_api()` (line 106-125)

### Step 2: Data Parsing

Parser processes API response based on `data_format`:

**Structured Format** (numeric data):
- Extracts values from nested JSON
- Creates structured dictionaries with tags and fields
- Parses timestamps to UTC

**Raw JSON Format** (metadata):
- Stores entire JSON response as string
- Minimal processing

Code location: `parser/api_parser.py` → `parse()` (line 458-517)

### Step 3: Filtering

Raw points pass through filtering rules:

```python
# Filter structured points
filtered_structured = filter_structured_points(all_structured_dicts)

# Filter raw points  
filtered_raw = filter_raw_points(all_raw_points)
```

Code location: `parser/api_parser.py` → `parse()` (line 488-493)

### Step 4: Point Conversion

Filtered data is converted to InfluxDB Point objects:

```python
point = Point("api")
point.tag("endpoint", "site_energy_details")
point.tag("metric", "Production")
point.tag("unit", "Wh")
point.field("Meter", 15420.0)  # category as field name
point.time(1732875600000000000, WritePrecision.NS)
```

Code location: `parser/api_parser.py` → `_convert_dict_to_point()` (line 131-165)

### Step 5: Storage

InfluxWriter writes points to InfluxDB bucket.

Code location: `storage/writer_influx.py` → `write_points()`

---

## Endpoint Types

### Structured Data Endpoints

These endpoints return numeric time-series data:

**site_energy_details**:
- URL: `/site/{siteId}/energyDetails`
- Data format: Nested meters with time-series values
- Category: `Meter`
- Parsing: Extracts meter type, timestamp, value, unit

**site_power_details**:
- URL: `/site/{siteId}/powerDetails`
- Data format: Nested meters with time-series values
- Category: `Meter`
- Parsing: Same as energy_details

**equipment_data**:
- URL: `/equipment/{siteId}/{serialNumber}/data`
- Data format: Array of telemetries
- Category: `Inverter`
- Parsing: Extracts multiple fields per telemetry (totalActivePower, dcVoltage, temperature, etc.)

**site_timeframe_energy**:
- URL: `/site/{siteId}/timeFrameEnergy`
- Data format: Single energy value with metadata
- Category: `Inverter`
- Parsing: Extracts energy value and start date

### Metadata Endpoints

These endpoints return JSON metadata:

**site_details**:
- URL: `/site/{siteId}/details`
- Data format: Nested JSON with site information
- Category: `Info`
- Storage: Flattened into multiple points (one per field)

**site_overview**:
- URL: `/site/{siteId}/overview`
- Data format: JSON with current metrics
- Category: `Info`
- Storage: Single point with JSON string

**equipment_list**:
- URL: `/equipment/{siteId}/list`
- Data format: JSON array of equipment
- Category: `Info`
- Storage: Single point with JSON string

---

## Timestamp Handling

### Input Formats

API provides timestamps in various formats:
- `"2025-11-29 10:00:00"` (local time, no timezone)
- `"2025-11-29T10:00:00+01:00"` (ISO 8601 with timezone)

### Conversion Process

1. **Parse** string to datetime object
2. **Localize** to configured timezone (default: Europe/Rome)
3. **Convert** to UTC
4. **Extract** Unix timestamp in seconds
5. **Multiply** by 1,000,000,000 to get nanoseconds
6. **Write** to InfluxDB with nanosecond precision

Code location: `parser/api_parser.py` → `_parse_timestamp()` (line 92-98)

---

## Parameter Building

### Automatic Date Substitution

Collector automatically replaces placeholders in endpoint parameters:

| Placeholder | Replaced With | Example |
|-------------|---------------|---------|
| `${API_START_DATE}` | Current date | `2025-11-29` |
| `${API_END_DATE}` | Current date | `2025-11-29` |
| `${API_START_TIME}` | Current date + 00:00:00 | `2025-11-29 00:00:00` |
| `${API_END_TIME}` | Current date + 23:59:59 | `2025-11-29 23:59:59` |
| `${CURRENT_YEAR_START}` | Year start | `2025-01-01` |
| `${CURRENT_YEAR_END}` | Year end | `2025-12-31` |

Code location: `collector/collector_api.py` → `_build_params()` (line 71-104)

### Automatic Date Addition

For endpoints that require dates but don't have them in config:
- Automatically adds `startTime` and `endTime` for current day
- Applies to: energyDetails, powerDetails, meters endpoints

---

## Caching System

### Cache Key Structure

```
source: "api_ufficiali"
endpoint: "{endpoint_name}"
date: "YYYY-MM-DD"
```

### Cache Behavior

**Daily Mode** (`collect()`):
- Each endpoint cached per day
- TTL: 15 minutes (configurable)
- Cache key: endpoint name + today's date

**History Mode** (`collect_with_dates()`):
- Monthly data split into daily cache entries
- Each day cached separately
- Cache key: endpoint name + specific date

Code location: `collector/collector_api.py` → `collect()` (line 163-188), `collect_with_dates()` (line 220-362)

### Data Splitting

Monthly API responses are split into daily chunks for caching:

**site_energy_details / site_power_details**:
- Groups values by date field
- Creates separate cache entry per day
- Preserves meter structure

**equipment_data**:
- Groups telemetries by date field
- Creates separate cache entry per day
- Preserves telemetry structure

Code location: `collector/collector_api.py` → `_split_data_by_day()` (line 586-670)

---

## Special Endpoint Handling

### Equipment Endpoints

Require serial number from equipment_list:

1. **Fetch** equipment_list endpoint
2. **Extract** first serial number from reporters.list
3. **Use** serial number in URL: `/equipment/{siteId}/{serialNumber}/data`

Code location: `collector/collector_api.py` → `_collect_equipment_endpoint()` (line 127-161)

### Equipment Data Time Limits

API limitation: Maximum 7 days per request

**Solution**: Automatic week splitting for longer periods
- Divides period into 6-day chunks (with overlap)
- Makes multiple API calls
- Aggregates telemetries into single response

Code location: `collector/collector_api.py` → `_collect_equipment_by_weeks()` (line 445-492)

### Site Energy Day

API limitation: Maximum 1 year per request (timeUnit=DAY)

**Solution**: Automatic year splitting
- Divides period into yearly chunks
- Makes one API call per year
- Aggregates values into single response

Code location: `collector/collector_api.py` → `_collect_site_energy_day_with_dates()` (line 676-745)

### Site Timeframe Energy

**Smart caching** per year:
- Checks cache for each year individually
- Only fetches missing years from API
- As system ages, only new year requires API call

Code location: `collector/collector_api.py` → `_collect_site_timeframe_energy_smart_cache()` (line 747-847)

---

## Meter Types

### Available Meters

API provides data for different meter types:

| Meter Type | Description | Available In |
|------------|-------------|--------------|
| `Production` | Energy/Power produced | energy_details, power_details |
| `Consumption` | Energy/Power consumed | energy_details, power_details |
| `SelfConsumption` | Energy/Power self-consumed (virtual) | energy_details, power_details |
| `FeedIn` | Energy/Power exported to grid | energy_details, power_details |
| `Purchased` | Energy/Power imported from grid | energy_details, power_details |

### Meter Type Storage

Each meter type is stored with its own tag:

```
measurement: api
tags:
  endpoint: site_energy_details
  metric: Production  ← meter type
  unit: Wh
fields:
  Meter: 15420.0
```

---

## Equipment Data Fields

### Main Telemetry Fields

| Field | Unit | Description |
|-------|------|-------------|
| `totalActivePower` | W | Total active power |
| `dcVoltage` | V | DC voltage from panels |
| `powerLimit` | % | Applied power limit |
| `totalEnergy` | Wh | Lifetime energy |
| `temperature` | °C | Inverter temperature |

### Phase Data Fields (L1Data, L2Data, L3Data)

| Field | Unit | Description |
|-------|------|-------------|
| `acCurrent` | A | AC current |
| `acVoltage` | V | AC voltage |
| `acFrequency` | Hz | AC frequency |
| `apparentPower` | VA | Apparent power |
| `activePower` | W | Active power |
| `reactivePower` | VAr | Reactive power |
| `cosPhi` | - | Power factor |

### Storage Format

Each field is stored as separate point with metric tag:

```
measurement: api
tags:
  endpoint: equipment_data
  metric: L1Data_acCurrent  ← field name
  unit: A
fields:
  Inverter: 5.2
```

Code location: `parser/api_parser.py` → `_process_equipment_data()` (line 351-408)

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

Code location: `parser/api_parser.py` → `_normalize_unit()` (line 100-105)

---

## Storage Examples

### Example 1: Energy Details

**API Response**:
```json
{
  "energyDetails": {
    "timeUnit": "QUARTER_OF_AN_HOUR",
    "unit": "Wh",
    "meters": [
      {
        "type": "Production",
        "values": [
          {"date": "2025-11-29 10:00:00", "value": 1250.5}
        ]
      }
    ]
  }
}
```

**InfluxDB Point**:
```
measurement: api
tags:
  endpoint=site_energy_details
  metric=Production
  unit=Wh
fields:
  Meter=1250.5
timestamp: 1732875600000000000 (nanoseconds)
```

### Example 2: Equipment Data

**API Response**:
```json
{
  "data": {
    "telemetries": [
      {
        "date": "2025-11-29 10:00:00",
        "totalActivePower": 3500,
        "temperature": 45.2
      }
    ]
  }
}
```

**InfluxDB Points** (2 points, one per field):
```
1. measurement: api
   tags: endpoint=equipment_data, metric=totalActivePower, unit=W
   fields: Inverter=3500.0
   timestamp: 1732875600000000000

2. measurement: api
   tags: endpoint=equipment_data, metric=temperature, unit=C
   fields: Inverter=45.2
   timestamp: 1732875600000000000
```

### Example 3: Site Details (Metadata)

**API Response**:
```json
{
  "details": {
    "name": "My Solar Site",
    "peakPower": 5000,
    "location": {
      "country": "Italy",
      "city": "Rome"
    }
  }
}
```

**InfluxDB Points** (multiple points, flattened):
```
1. measurement: api
   tags: endpoint=site_details, metric=name, unit=raw
   fields: Info="My Solar Site"

2. measurement: api
   tags: endpoint=site_details, metric=peakPower, unit=raw
   fields: Info="5000"

3. measurement: api
   tags: endpoint=site_details, metric=location_country, unit=raw
   fields: Info="Italy"

4. measurement: api
   tags: endpoint=site_details, metric=location_city, unit=raw
   fields: Info="Rome"
```

Code location: `parser/api_parser.py` → `_convert_site_details_to_points()` (line 183-213)

---

## Configuration Dependency

### api_endpoints.yaml Role

The collector and parser **require** `api_endpoints.yaml` to function:

**Collector uses**:
- `enabled`: Whether to collect this endpoint
- `endpoint`: API URL path
- `parameters`: Query parameters with placeholders

**Parser uses**:
- `category`: InfluxDB field name
- `data_format`: "structured" or "raw_json"
- `extraction`: How to extract values from response

### Config Structure Example

```yaml
sources:
  api_ufficiali:
    endpoints:
      site_energy_details:
        enabled: true
        endpoint: "/site/{siteId}/energyDetails"
        category: "Meter"  # ← Used as InfluxDB field name
        data_format: "structured"
        parameters:
          meters: "PRODUCTION,CONSUMPTION"
          timeUnit: "QUARTER_OF_AN_HOUR"
        extraction:
          values_path: "energyDetails.meters"
          time_field: "date"
          value_field: "value"
```

---

## Error Handling

### Missing Category
- **Trigger**: Endpoint config lacks `category` field
- **Action**: Raise ValueError
- **Log**: Error message with endpoint name

### HTTP Errors
- **Trigger**: API returns non-200 status code
- **Action**: Log error and skip endpoint
- **Log**: HTTP status code and endpoint name

### Parsing Errors
- **Trigger**: Unexpected data structure
- **Action**: Log error and skip that endpoint
- **Log**: Exception details

Code location: `collector/collector_api.py` → `_call_api()` (line 106-125), `collect()` (line 184-186)

---

## Performance Optimizations

### HTTP Session Pooling

Single session reused for all requests:
```python
self._session = requests.Session()
self._session.headers.update({
    'User-Agent': 'SolarEdge-Collector/1.0',
    'Accept': 'application/json'
})
```

Benefits:
- Connection reuse (TCP keep-alive)
- Reduced latency
- Lower resource usage

Code location: `collector/collector_api.py` → `__init__()` (line 36-41)

### Scheduler Integration

Optional scheduler for rate limiting:
```python
if self.scheduler:
    return self.scheduler.execute_with_timing(SourceType.API, _http_call, cache_hit=False)
else:
    return _http_call()
```

Code location: `collector/collector_api.py` → `_call_api()` (line 122-125)

### Smart Caching

- Daily cache for normal mode
- Per-year cache for timeframe_energy
- Automatic cache splitting for history mode

---

## API Limitations

### Rate Limits

- **Daily quota**: 300 requests per account/site
- **Concurrency**: Max 3 simultaneous requests from same IP

### Time Range Limits

| Endpoint | Max Range | Resolution |
|----------|-----------|------------|
| site_energy_details (DAY) | 1 year | Daily |
| site_energy_details (HOUR/QUARTER) | 1 month | Hourly/15min |
| site_power_details | 1 month | 15 minutes |
| equipment_data | 1 week | Variable |

### Workarounds

System automatically handles limitations:
- **Year splitting** for site_energy_day
- **Week splitting** for equipment_data
- **Smart caching** to minimize API calls

---

## Summary

The API data storage system:

1. **Builds** HTTP requests with automatic parameter substitution
2. **Fetches** data from SolarEdge API with caching
3. **Parses** responses based on endpoint configuration
4. **Filters** data points using filtering rules
5. **Converts** to InfluxDB points with:
   - Measurement: `api`
   - Tags: `endpoint`, `metric`, `unit`
   - Field: Named by category, value from API
   - Timestamp: Nanosecond precision
6. **Writes** to InfluxDB in batches

**Key Design**: Configuration-driven system where endpoint behavior is defined in YAML, allowing flexible data collection without code changes.
