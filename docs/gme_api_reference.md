# GME API Integration – Technical Reference

## Overview

This document describes **how the GME (Gestore dei Mercati Energetici) data collection subsystem works**. It details the technical implementation of authentication, data retrieval, parsing, and storage of Italian electricity market prices (PUN).

---

## 1. Architecture Overview

```
GME Flow
└─ collector/collector_gme.py      →  Authentication & Data Download
   └─ requests (HTTP Session)      →  API calls
   └─ zipfile/base64               →  Response decoding
└─ parser/gme_parser.py            →  Data extraction & Point creation
└─ storage/writer_influx.py        →  InfluxDB storage
```

---

## 2. Authentication System

The GME API uses JWT (JSON Web Token) authentication.

### 2.1 Credentials
- **Source**: Environment variables `GME_USERNAME` and `GME_PASSWORD`.
- **Validation**: Checks for presence on initialization; logs warning if missing.

### 2.2 Token Retrieval (`_get_token`)
1. **Check Cache**: Returns existing token if valid (expiry set to 23 hours).
2. **Request**: POST to `/api/v1/Auth` with JSON payload `{"Login": "...", "Password": "..."}`.
3. **Response Parsing**:
   - Expects JSON with `token` field.
   - Fallback: Treats raw response text as token if JSON parsing fails.
4. **Caching**: Stores token and sets local expiry.

Code location: `collector/collector_gme.py` → `_get_token` (line 38-85)

---

## 3. Data Collection (`CollectorGME`)

### 3.1 Request Structure
- **Endpoint**: `/api/v1/RequestData`
- **Method**: POST
- **Headers**:
  - `Authorization`: `Bearer {token}`
  - `Content-Type`: `application/json`
- **Payload**:
  ```json
  {
    "Platform": "PublicMarketResults",
    "Segment": "MGP",
    "DataName": "ME_ZonalPrices",
    "IntervalStart": "YYYYMMDD",
    "IntervalEnd": "YYYYMMDD",
    "Attributes": {}
  }
  ```

### 3.2 Response Handling
1. **Base64 Decoding**: API returns a JSON with `contentResponse` containing a Base64 string.
2. **ZIP Extraction**: The decoded Base64 string is a ZIP file.
3. **File Traversal**: Iterates through files in the ZIP to find `.json` files.
4. **JSON Parsing**:
   - Extracts `ME_ZonalPrices` or `data` array.
   - Filters for `Zone == "PUN"`.
   - Normalizes fields (`Price`/`PunPrice` → `pun_mwh`).

### 3.3 Rate Limiting & Scheduler
- **Integration**: Uses `SchedulerLoop` with `SourceType.GME`.
- **Delay**: Configurable delay (default 15s) to respect GME limits (100 req/hour).
- **Optimization**: Skips delay on cache hits (though GME is typically live fetch).

Code location: `collector/collector_gme.py` → `collect` (line 100-213)

---

## 4. Parsing Logic (`GMEParser`)

### 4.1 Hourly Price Points (`gme_prices`)
Converts raw price data into InfluxDB points.

- **Measurement**: `gme_prices`
- **Tags**:
  - `source`: "GME"
  - `market`: "MGP"
  - `hour`: 1-24
  - `year`: YYYY
  - `month`: Full English name (e.g., "January")
  - `day`: Day of month
- **Fields**:
  - `pun_mwh`: Price in €/MWh (float)
- **Timestamp**:
  - Calculated from date and hour (Hour 1 = 00:00).
  - Localized to `Europe/Rome` then converted to UTC.

Code location: `parser/gme_parser.py` → `_create_gme_point` (line 75-134)

### 4.2 Monthly Average Points (`gme_monthly_avg`)
Calculates and stores the average PUN for the month.

- **Measurement**: `gme_monthly_avg`
- **Tags**:
  - `source`: "GME"
  - `market`: "MGP"
  - `year`: YYYY
  - `month`: Full English name
- **Fields**:
  - `pun_kwh_avg`: Average price in €/kWh (float)
- **Timestamp**: First day of the month at 00:00:00 UTC.

Code location: `parser/gme_parser.py` → `create_monthly_avg_point` (line 135-170)

---

## 5. InfluxDB Storage Schema

### Measurement: `gme_prices`
| Component | Name | Type | Description |
|-----------|------|------|-------------|
| Tag | `source` | string | Always "GME" |
| Tag | `market` | string | Always "MGP" |
| Tag | `hour` | string | Hour of day (1-24) |
| Tag | `year` | string | Year (e.g., "2024") |
| Tag | `month` | string | Month name (e.g., "March") |
| Tag | `day` | string | Day number |
| Field | `pun_mwh` | float | Price in €/MWh |

### Measurement: `gme_monthly_avg`
| Component | Name | Type | Description |
|-----------|------|------|-------------|
| Tag | `source` | string | Always "GME" |
| Tag | `market` | string | Always "MGP" |
| Tag | `year` | string | Year |
| Tag | `month` | string | Month name |
| Field | `pun_kwh_avg` | float | Average price in €/kWh |

---

## 6. Error Handling

- **Authentication Failure**: Logs error, returns empty dict.
- **Download Failure**: Logs error, returns empty dict.
- **ZIP/Base64 Errors**: Logs error, attempts to preview content for debugging.
- **Parsing Errors**: Skips individual malformed points, logs warning.
- **Missing Data**: Checks for empty `prices` list.

---

## 7. Configuration Parameters

| Parameter | Env Var | Description |
|-----------|---------|-------------|
| Username | `GME_USERNAME` | GME account login |
| Password | `GME_PASSWORD` | GME account password |
| Delay | `SCHEDULER_GME_DELAY_SECONDS` | Delay between API calls (default 15s) |

---

## 8. Summary of Data Flow

1. **Authenticate**: Obtain JWT token from GME.
2. **Download**: Request data for date range → Receive Base64 ZIP.
3. **Extract**: Decode Base64 → Unzip → Find JSON.
4. **Parse**: Extract PUN prices → Normalize to list of dicts.
5. **Convert**: Create `gme_prices` points (hourly) and `gme_monthly_avg` point (monthly).
6. **Store**: Write points to InfluxDB.

This document provides a complete technical description of the GME data collection subsystem.
