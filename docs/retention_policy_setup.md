# InfluxDB Retention Policy – Technical Reference

## Overview

This document describes **how retention policies work** in the SolarEdge ScanWriter InfluxDB setup. It details the automatic bucket configuration, retention rules, and the technical rationale behind the design.

---

## 1. Bucket Architecture

The system uses **three separate buckets** with different retention policies:

| Bucket Name | Data Type | Retention | Purpose |
|-------------|-----------|-----------|---------|
| `Solaredge` (default) | API + Web | **Infinite** | Long-term historical data |
| `Solaredge_Realtime` | Modbus TCP | **2 days** | High-frequency telemetry |
| `GME` | Energy Prices | **Infinite** | Market price history |

---

## 2. Automatic Bucket Creation

Buckets are created automatically on first run by `InfluxWriter` if they don't exist.

### 2.1 Implementation Location

**File**: `storage/writer_influx.py` → `_ensure_bucket_exists()` (lines 87-124)

### 2.2 Creation Logic

```python
# Main bucket (API/Web) - Infinite retention
buckets_api.create_bucket(
    bucket_name=self._influx_config.bucket,
    org=self._influx_config.org,
    retention_rules=[]  # Empty = infinite
)

# Realtime bucket - 2-day retention
retention_rules = BucketRetentionRules(type="expire", every_seconds=172800)
buckets_api.create_bucket(
    bucket_name=self._influx_config.bucket_realtime,
    org=self._influx_config.org,
    retention_rules=[retention_rules]
)

# GME bucket - Infinite retention
buckets_api.create_bucket(
    bucket_name=self._influx_config.bucket_gme,
    org=self._influx_config.org,
    retention_rules=[]
)
```

---

## 3. Retention Policy Rationale

### 3.1 Realtime Data (2 Days)

**Why 2 days?**
- Modbus data is collected every **5 seconds** (17,280 points/day per metric).
- With ~20 metrics per device, this generates **~350,000 points/day**.
- 2-day retention = **~700,000 points** (manageable size).
- Realtime data is used for **live monitoring**, not historical analysis.

**Storage Impact**:
- Older realtime data is automatically deleted after 48 hours.
- Prevents unbounded growth of high-frequency data.

### 3.2 API/Web Data (Infinite)

**Why infinite?**
- API data is collected **hourly** or **daily** (low frequency).
- Web data is collected **every 15 minutes** (moderate frequency).
- Total volume is **manageable** even over years.
- Historical data is **essential** for long-term analysis (ROI, trends, etc.).

### 3.3 GME Data (Infinite)

**Why infinite?**
- Price data is collected **daily** (24 points/day).
- Extremely low volume.
- Historical price data is **critical** for financial analysis.

---

## 4. Configuration

### 4.1 Environment Variables

Bucket names are configured via `.env`:

```bash
# Main bucket (API/Web)
INFLUXDB_BUCKET=Solaredge

# Realtime bucket (Modbus)
INFLUXDB_BUCKET_REALTIME=Solaredge_Realtime

# GME bucket (Energy prices)
INFLUXDB_BUCKET_GME=GME
```

### 4.2 Automatic Routing

The `InfluxWriter` automatically routes data to the correct bucket based on measurement type:

| Measurement | Bucket |
|-------------|--------|
| `realtime` | `Solaredge_Realtime` (2-day retention) |
| `gme_prices`, `gme_monthly_avg` | `GME` (infinite) |
| `api`, `web` | `Solaredge` (infinite) |

**Code location**: `storage/writer_influx.py` → `_get_bucket_for_measurement()` (lines 141-156)

---

## 5. Manual Retention Policy Changes

### 5.1 Via InfluxDB UI

1. Open InfluxDB UI: `http://localhost:8086`
2. Navigate to **Load Data** → **Buckets**
3. Click on bucket name → **Settings**
4. Modify **Retention Period**
5. Save changes

### 5.2 Via InfluxDB CLI

```bash
# Change realtime retention to 7 days
influx bucket update \
  --name Solaredge_Realtime \
  --retention 604800s \
  --org <your-org>

# Set infinite retention
influx bucket update \
  --name Solaredge_Realtime \
  --retention 0 \
  --org <your-org>
```

### 5.3 Via API

```bash
curl -X PATCH "http://localhost:8086/api/v2/buckets/<bucket-id>" \
  -H "Authorization: Token <your-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "retentionRules": [{
      "type": "expire",
      "everySeconds": 604800
    }]
  }'
```

---

## 6. Downsampling Strategy (Optional)

For advanced users who want to keep realtime data longer while reducing storage:

### 6.1 Concept

Instead of deleting realtime data after 2 days, **downsample** it to lower resolution:
- **Raw data** (5s): Keep for 2 days
- **1-minute averages**: Keep for 30 days
- **5-minute averages**: Keep for 1 year

### 6.2 Implementation (InfluxDB Tasks)

Create an InfluxDB Task to automatically downsample:

```flux
option task = {
  name: "Downsample Realtime to 1min",
  every: 1h,
}

from(bucket: "Solaredge_Realtime")
  |> range(start: -3d, stop: -2d)
  |> filter(fn: (r) => r._measurement == "realtime")
  |> aggregateWindow(every: 1m, fn: mean)
  |> to(bucket: "Solaredge_Realtime_1min", org: "your-org")
```

**Note**: This requires creating additional buckets (`Solaredge_Realtime_1min`, etc.) with appropriate retention policies.

---

## 7. Storage Estimation

### 7.1 Typical Storage Usage

| Data Type | Frequency | Points/Day | Storage/Day | 1 Year |
|-----------|-----------|------------|-------------|--------|
| **Realtime** | 5s | ~350,000 | ~50 MB | N/A (2-day retention) |
| **Web** | 15min | ~1,500 | ~200 KB | ~73 MB |
| **API** | 1h-1d | ~500 | ~50 KB | ~18 MB |
| **GME** | 1d | 24 | ~5 KB | ~2 MB |

**Total for 1 year**: ~100 MB (excluding realtime)

### 7.2 With Realtime (2-day retention)

- Realtime: ~100 MB (constant, auto-deleted after 2 days)
- Historical: ~100 MB/year
- **Total**: ~200 MB after 1 year

---

## 8. Monitoring Retention

### 8.1 Check Current Retention

```bash
influx bucket list --org <your-org>
```

### 8.2 Check Bucket Size

```bash
# Via InfluxDB UI
# Navigate to Load Data → Buckets → View bucket size

# Via CLI (requires InfluxDB 2.7+)
influx bucket list --org <your-org> --json | jq '.[] | {name, retentionRules}'
```

---

## 9. Summary

The retention policy design balances:
- **Storage efficiency**: High-frequency data (realtime) is automatically pruned.
- **Historical value**: Low-frequency data (API/Web/GME) is kept indefinitely.
- **Automatic management**: No manual intervention required.

**Key Design**: The system automatically routes data to the appropriate bucket based on measurement type, ensuring optimal retention without user configuration.
