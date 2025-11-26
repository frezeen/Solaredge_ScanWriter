# GME API Documentation Summary

## Overview
GME (Gestore dei Mercati Energetici) provides an API service for downloading Italian electricity market results via HTTP requests using JSON data exchange.

## Key Information

### Base URL
```
https://api.mercatoelettrico.org/request/api/v1/
```

### Authentication

**Endpoint**: `/api/v1/Auth`  
**Method**: POST  
**Request Body**:
```json
{
  "Login": "your_username",
  "Password": "your_password"
}
```

**Response**:
```json
{
  "Success": true,
  "token": "JWT_TOKEN_HERE"
}
```

The JWT token must be included in subsequent requests as:
```
Authorization: Bearer JWT_TOKEN
```

### Data Retrieval

**Endpoint**: `/api/v1/RequestData` (NOT `RequestaData`)  
**Method**: POST  
**Headers**:
```
Authorization: Bearer JWT_TOKEN
Content-Type: application/json
```

**Request Body**:
```json
{
  "Platform": "PublicMarketResults",
  "Segment": "MGP",
  "DataName": "ME_ZonalPrices",
  "IntervalStart": "yyyyMMdd",
  "IntervalEnd": "yyyyMMdd",
  "Attributes": {}
}
```

**Response Format**:
- Content is base64 encoded
- Contains either `.json.zip` or `.xml.zip` file
- Must be decoded from base64 and unzipped

### Other Endpoints

### Quotas and Limits

The GME API enforces strict usage limits to prevent overload. Exceeding these limits results in a **500 Internal Server Error** with a message like `"The request exceedes quota MaxDataPerMinute"`.

**Exact Limits (Confirmed)**:
- **MaxConnectionsPerMinute**: 10
- **MaxConnectionsPerHour**: 100 (Critical for history mode)
- **MaxDataPerMinute**: 225,000 bytes (~220 KB)
- **MaxDataPerHour**: 1,100,000 bytes (~1.1 MB)

**Check Quota Endpoint**:
- **URL**: `/api/v1/GetMyQuotas`
- **Method**: GET
- **Headers**: `Authorization: Bearer JWT_TOKEN`
- **Response**: Returns current usage and remaining quota.

**Implementation Strategy**:
To balance speed and compliance with `MaxConnectionsPerHour` (100 req/h):
- **Granularity**: History mode downloads 1 full month per request.
- **Capacity**: 100 requests = 100 months ≈ 8.3 years of data.
- **Strategy**: Use a faster delay (**15s**) to download ~8 years of data in ~25 minutes.
- **Limit Handling**: If >8 years are needed, the system will hit the 100 req/h limit after 25 mins and must wait for the hour to reset. This is an acceptable trade-off for faster backfills.

**Configuration**:
- `SCHEDULER_GME_DELAY_SECONDS=15` in `.env`
- This applies to both loop mode and history mode.
- **Cache Optimization**: Delays are skipped for cache hits when `SCHEDULER_SKIP_DELAY_ON_CACHE_HIT=true`


### Support Contacts

- **Authorization/Procedure**: SupportoAPI@mercatoelettrico.org
- **Technical/IT Support**: Sistemi@mercatoelettrico.org

## Available Data

### ME_ZonalPrices
Hourly zonal electricity prices for the Italian market (MGP - Day-Ahead Market).

**Fields**:
- Date
- Hour (1-24)
- Zone (e.g., "PUN" for national single price)
- Price (€/MWh)

## Important Notes

1. **Endpoint Name**: The correct endpoint is `RequestData` not `RequestaData`
2. **Platform**: Must use `"PublicMarketResults"` for public market data
3. **Response Encoding**: All responses are base64 encoded ZIP files
4. **Date Format**: Use `yyyyMMdd` format (e.g., "20241125")
5. **Data Availability**: Market results are typically available D+1 (next day)

## References

- User Manual: Available at GME website → Media → Library → Manuals
- Technical Manual: Available at GME website → Media → Library → Manuals
- Updated: 01/10/2025

## Common Issues

### 404 Not Found
- Check endpoint spelling: `/RequestData` not `/RequestaData`
- Verify Platform name: `"PublicMarketResults"`
- Ensure date is in correct format and data is available

### 400 Bad Request
- Verify JSON payload structure
- Check field names: `"Login"` and `"Password"` (not `"username"` and `"password"`)
- Ensure all required fields are present

### No Data
- Market data is available D+1 (published the next day)
- Check if the requested date has published data
- Verify the date range is valid

## Grafana & InfluxDB Integration

This section provides technical details for building dashboards in Grafana using Flux queries.

### InfluxDB Schema

#### Measurement: `gme_prices`
Stores hourly raw price data.

**Tags:**
- `source`: Always `"GME"`
- `market`: Always `"MGP"`
- `hour`: Hour of the day (1-24)
- `year`: Year (e.g., "2024")
- `month`: Month (e.g., "11")
- `day`: Day of month (e.g., "25")

**Fields:**
- `pun_mwh`: Price in €/MWh (original raw value from API)

> [!IMPORTANT]
> The `year`, `month`, and `day` tags enable efficient InfluxDB queries for history mode and granular aggregations.

#### Measurement: `gme_monthly_avg`
Stores calculated monthly average prices.

**Tags:**
- `source`: Always `"GME"`
- `market`: Always `"MGP"`
- `year`: Year (e.g., "2024")
- `month`: Month (e.g., "11")

**Fields:**
- `pun_kwh_avg`: Average monthly price in €/kWh

### Example Flux Queries

#### 1. Hourly Trend (Last 7 Days)
Visualizes the hourly price trend in €/kWh.

```flux
from(bucket: "Solaredge")
  |> range(start: -7d)
  |> filter(fn: (r) => r["_measurement"] == "gme_prices")
  |> filter(fn: (r) => r["_field"] == "pun_kwh")
  |> filter(fn: (r) => r["source"] == "GME")
  |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
  |> yield(name: "hourly_price")
```

#### 2. Monthly Average Trend (Last Year)
Shows how the average monthly price has evolved over the last year.

```flux
from(bucket: "Solaredge")
  |> range(start: -1y)
  |> filter(fn: (r) => r["_measurement"] == "gme_monthly_avg")
  |> filter(fn: (r) => r["_field"] == "pun_kwh_avg")
  |> filter(fn: (r) => r["source"] == "GME")
  |> yield(name: "monthly_average")
```

#### 3. Daily Average Calculation from Hourly Data
Calculates the daily average price dynamically from hourly data.

```flux
from(bucket: "Solaredge")
  |> range(start: -30d)
  |> filter(fn: (r) => r["_measurement"] == "gme_prices")
  |> filter(fn: (r) => r["_field"] == "pun_kwh")
  |> filter(fn: (r) => r["source"] == "GME")
  |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)
  |> yield(name: "daily_average")
```

#### 4. Energy Cost Calculation (Example)
Estimates cost by multiplying consumption by GME price (requires `consumption` measurement).

```flux
// Fetch GME Prices
prices = from(bucket: "Solaredge")
  |> range(start: -1d)
  |> filter(fn: (r) => r["_measurement"] == "gme_prices")
  |> filter(fn: (r) => r["_field"] == "pun_kwh")
  |> aggregateWindow(every: 1h, fn: mean)

// Fetch Consumption
consumption = from(bucket: "Solaredge")
  |> range(start: -1d)
  |> filter(fn: (r) => r["_measurement"] == "consumption")
  |> filter(fn: (r) => r["_field"] == "value")
  |> aggregateWindow(every: 1h, fn: mean)

// Join and Calculate Cost
join(tables: {p: prices, c: consumption}, on: ["_time"])
  |> map(fn: (r) => ({
      _time: r._time,
      _value: r._value_p * r._value_c  // Price (€/kWh) * Consumption (kWh) = Cost (€)
    }))
  |> yield(name: "estimated_cost")
```
