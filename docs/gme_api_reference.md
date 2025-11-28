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
- `month`: English month name (e.g., "January", "February", "March")
- `day`: Day of month (e.g., "25")

**Fields:**
- `pun_mwh`: Price in €/MWh (original raw value from API)

> [!IMPORTANT]
> - The `year`, `month`, and `day` tags enable efficient InfluxDB queries for history mode and granular aggregations.
> - The `month` tag uses **English month names** (e.g., "January", "March", "November") not numeric values.
> - Prices are stored in **€/MWh** (original GME format). To convert to €/kWh, divide by 1000.

#### Measurement: `gme_monthly_avg`
Stores calculated monthly average prices. This measurement is automatically computed by the GME flow and updated progressively as new daily data arrives.

**Tags:**
- `source`: Always `"GME"`
- `market`: Always `"MGP"`
- `year`: Year (e.g., "2024")
- `month`: English month name (e.g., "March", "May", "January")

**Fields:**
- `pun_kwh_avg`: Average monthly price in €/kWh (already converted from MWh)

**Timestamp:**
- Set to the first day of the month at 00:00:00 (e.g., 2024-11-01 00:00:00)

> [!NOTE]
> - The `month` tag uses **English month names** (e.g., "March", "May") not numeric values (e.g., "3", "5").
> - Monthly averages are **progressively updated** each day as new hourly data is collected.
> - The average is calculated from all available hourly `pun_kwh` values for that month.
> - Use `range(start: 0)` when querying monthly averages to ensure all historical data is included.

### Example Flux Queries

> [!IMPORTANT]
> GME data is stored in the **`GME` bucket**, not the `Solaredge` bucket.

#### 1. Hourly Trend (Last 7 Days)
Visualizes the hourly price trend in €/kWh.

```flux
from(bucket: "GME")
  |> range(start: -7d)
  |> filter(fn: (r) => r._measurement == "gme_prices")
  |> filter(fn: (r) => r._field == "pun_kwh")
  |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
```

#### 2. Monthly Average Trend (Last Year)
Shows how the average monthly price has evolved over the last year.

```flux
from(bucket: "GME")
  |> range(start: -1y)
  |> filter(fn: (r) => r._measurement == "gme_monthly_avg")
  |> filter(fn: (r) => r._field == "pun_kwh_avg")
```

#### 3. Current Month Average (Dynamic)
Retrieves the pre-calculated monthly average for the current month. This is useful for real-time cost calculations.

```flux
import "date"

month_start = date.truncate(t: now(), unit: 1mo)

from(bucket: "GME")
  |> range(start: month_start)
  |> filter(fn: (r) => r._measurement == "gme_monthly_avg")
  |> filter(fn: (r) => r._field == "pun_kwh_avg")
  |> last()
```

> [!TIP]
> - Use `range(start: month_start)` to get the current month's average.
> - The `last()` function returns the most recent value, which is the progressively updated average.
> - This query automatically adapts to the current month without hardcoding dates.

#### 4. Specific Month Average (e.g., March 2024)
Retrieves the pre-calculated monthly average for a specific month.

```flux
from(bucket: "GME")
  |> range(start: 0)
  |> filter(fn: (r) => r._measurement == "gme_monthly_avg")
  |> filter(fn: (r) => r._field == "pun_kwh_avg")
  |> filter(fn: (r) => r.month == "March")
  |> filter(fn: (r) => r.year == "2024")
```

> [!TIP]
> Use `range(start: 0)` for monthly averages instead of relative ranges like `-1y`. Monthly average data points have timestamps at the first day of each month, and using `start: 0` ensures all historical data is included.

#### 5. Daily Average Calculation from Hourly Data
Calculates the daily average price dynamically from hourly data.

```flux
from(bucket: "GME")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "gme_prices")
  |> filter(fn: (r) => r._field == "pun_kwh")
  |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)
```

#### 5. Daily Import Cost Calculation with Current Month PUN
Calculates the daily energy import cost using the current month's average PUN price.

```flux
import "timezone"
import "date"
import "array"

option location = timezone.location(name: "Europe/Rome")

start = date.truncate(t: now(), unit: 1d)
month_start = date.truncate(t: now(), unit: 1mo)

// Recupera prezzo PUN medio mensile (già pre-calcolato)
prezzo_pun = from(bucket: "GME")
  |> range(start: month_start)
  |> filter(fn: (r) => r._measurement == "gme_monthly_avg" and r._field == "pun_kwh_avg")
  |> last()
  |> findRecord(fn: (key) => true, idx: 0)

// Calcolo prelievo giornaliero
base = from(bucket: "Solaredge_Realtime")
  |> range(start: start)
  |> filter(fn: (r) => r._measurement == "realtime" and r._field == "Meter" and r.endpoint == "Import Energy Active" and r.unit == "Wh")

first = base |> filter(fn: (r) => exists r._value and r._value > 0.0) |> sort(columns: ["_time"]) |> limit(n: 1) |> findRecord(fn: (key) => true, idx: 0)
last = base |> last() |> findRecord(fn: (key) => true, idx: 0)

prelievo = if (last._value - first._value) < 0.0 then 0.0 else (last._value - first._value)
costo = (prelievo / 1000.0) * prezzo_pun._value

array.from(rows: [{PUN: prezzo_pun._value, Costo: costo}])
```

**Grafana Visualization Setup:**

This query is designed to be displayed as **two side-by-side stat panels** showing:
- **PUN**: Current month's average price (€/kWh)
- **Costo**: Today's import cost (€)

**Configuration:**
1. **Visualization**: Stat panel
2. **Panel Options**:
   - Title: "Costo Prelievo" or similar
   - Show: All values
3. **Standard Options**:
   - Unit: `currency(EUR)` or custom `€`
   - Decimals: 3 for PUN, 2-3 for Costo
4. **Value Mappings**: None needed
5. **Thresholds**: Optional (e.g., red for high costs)
6. **Layout**: Horizontal orientation to display both values side-by-side

**Result**: Two boxes displaying "PUN" and "Costo" with their respective values in euros, automatically updated as new data arrives.

> [!TIP]
> - The query uses pre-calculated monthly averages for efficiency
> - PUN value updates daily as new hourly data is collected
> - Cost is calculated from midnight to current time each day
> - Use Grafana's auto-refresh (e.g., 5m) to keep values current

#### 6. Monthly Energy Analysis with PUN and Hypothetical Cost
Comprehensive monthly analysis combining energy data from SolarEdge API with GME PUN prices to calculate hypothetical costs without photovoltaic system.

```flux
import "timezone"
import "date"
import "join"

option location = timezone.location(name: "Europe/Rome")

// 1. Dati energetici mensili (Produzione, Consumo, Autoconsumo, Prelievo, Immissione)
energia = from(bucket: "Solaredge")
  |> range(start: 0)
  |> filter(fn: (r) => r._measurement == "api" and r._field == "Meter" and r.endpoint == "site_energy_details")
  |> filter(fn: (r) => r.metric == "Production" or r.metric == "Consumption" or r.metric == "SelfConsumption" or r.metric == "Purchased" or r.metric == "FeedIn")
  |> aggregateWindow(every: 1mo, fn: sum, createEmpty: false)
  |> map(fn: (r) => ({
    r with _field: 
      if r.metric == "Production" then "Produzione"
      else if r.metric == "Consumption" then "Consumo"
      else if r.metric == "SelfConsumption" then "Autoconsumo"
      else if r.metric == "Purchased" then "Prelievo"
      else if r.metric == "FeedIn" then "Immissione"
      else r._field
  }))
  |> drop(columns: ["metric", "_start", "_stop", "endpoint", "unit", "_measurement"])
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")

// 2. PUN mensile
pun = from(bucket: "GME")
  |> range(start: 0)
  |> filter(fn: (r) => r._measurement == "gme_monthly_avg" and r._field == "pun_kwh_avg")
  |> group()
  |> map(fn: (r) => ({_time: r._time, year: r.year, month: r.month, PUN: r._value}))

// 3. Join energia con PUN e calcola costo ipotetico senza FV
join.time(
  left: energia,
  right: pun,
  as: (l, r) => ({
    _time: l._time,
    year: r.year,
    month: r.month,
    Produzione: l.Produzione,
    Consumo: l.Consumo,
    Autoconsumo: l.Autoconsumo,
    Prelievo: l.Prelievo,
    Immissione: l.Immissione,
    PUN: r.PUN,
    Costo_senza_FV: (l.Consumo / 1000.0) * r.PUN
  })
)
  |> sort(columns: ["_time"])
```

**What This Query Does:**

1. **Energy Data**: Retrieves monthly aggregated energy metrics from SolarEdge API:
   - **Produzione**: Total solar production (Wh)
   - **Consumo**: Total household consumption (Wh)
   - **Autoconsumo**: Self-consumed solar energy (Wh)
   - **Prelievo**: Energy imported from grid (Wh)
   - **Immissione**: Energy exported to grid (Wh)

2. **PUN Prices**: Retrieves pre-calculated monthly average PUN prices (€/kWh)

3. **Cost Calculation**: Calculates hypothetical cost if all consumption was purchased from grid at PUN price

**Output Columns:**
- `_time`: Month timestamp
- `year`, `month`: Year and month name
- `Produzione`, `Consumo`, `Autoconsumo`, `Prelievo`, `Immissione`: Energy values in Wh
- `PUN`: Monthly average price in €/kWh
- `Costo_senza_FV`: Hypothetical monthly cost without photovoltaic system (€)

**Use Cases:**
- Calculate total savings from photovoltaic installation
- Compare actual costs vs. hypothetical costs without solar
- Analyze ROI and payback period
- Generate monthly energy reports with cost analysis

**To Get Total Lifetime Cost:**
Add `|> sum(column: "Costo_senza_FV")` at the end to sum all monthly costs.

**Grafana Visualization:**
- Use **Table** panel to show all columns
- Use **Stat** panel with `sum()` to show total lifetime savings
- Use **Time series** to plot cost trends over time

> [!IMPORTANT]
> - This query uses **API data** from the `Solaredge` bucket, not realtime data
> - Energy values are in **Wh** (divide by 1000 for kWh)
> - The `site_energy_details` endpoint provides accurate monthly aggregations
> - PUN prices are matched by month using `join.time()` for precise alignment
> - Missing months (no PUN data) will be excluded from results

#### 7. Financial Analysis Queries

These queries calculate the financial impact of your photovoltaic system using historical PUN prices.

**7.1 Hypothetical Cost Without Photovoltaic System**

Calculates total cost if all consumption was purchased from grid at PUN prices.

```flux
import "timezone"
import "date"
import "join"

option location = timezone.location(name: "Europe/Rome")

// 1. Consumo mensile
consumo = from(bucket: "Solaredge")
  |> range(start: 0)
  |> filter(fn: (r) => r._measurement == "api" and r._field == "Meter" and r.endpoint == "site_energy_details" and r.metric == "Consumption")
  |> aggregateWindow(every: 1mo, fn: sum, createEmpty: false)
  |> group()
  |> map(fn: (r) => ({_time: r._time, year: string(v: date.year(t: r._time)), month: string(v: date.month(t: r._time)), consumo_wh: r._value}))

// 2. PUN mensile
pun = from(bucket: "GME")
  |> range(start: 0)
  |> filter(fn: (r) => r._measurement == "gme_monthly_avg" and r._field == "pun_kwh_avg")
  |> group()
  |> map(fn: (r) => ({_time: r._time, year: r.year, month: string(v: date.month(t: r._time)), pun: r._value}))

// 3. Join, calcola costo e somma totale
join.inner(
  left: consumo,
  right: pun,
  on: (l, r) => l.year == r.year and l.month == r.month,
  as: (l, r) => ({
    _time: l._time,
    "Costo Senza Fotovoltaico": (l.consumo_wh / 1000.0) * r.pun
  })
)
  |> sum(column: "Costo Senza Fotovoltaico")
```

**7.2 Actual Cost With Photovoltaic System**

Calculates total cost of energy actually purchased from grid (with solar covering part of consumption).

```flux
import "timezone"
import "date"
import "join"

option location = timezone.location(name: "Europe/Rome")

// 1. Prelievo mensile (energia acquistata dalla rete)
prelievo = from(bucket: "Solaredge")
  |> range(start: 0)
  |> filter(fn: (r) => r._measurement == "api" and r._field == "Meter" and r.endpoint == "site_energy_details" and r.metric == "Purchased")
  |> aggregateWindow(every: 1mo, fn: sum, createEmpty: false)
  |> group()
  |> map(fn: (r) => ({_time: r._time, year: string(v: date.year(t: r._time)), month: string(v: date.month(t: r._time)), prelievo_wh: r._value}))

// 2. PUN mensile
pun = from(bucket: "GME")
  |> range(start: 0)
  |> filter(fn: (r) => r._measurement == "gme_monthly_avg" and r._field == "pun_kwh_avg")
  |> group()
  |> map(fn: (r) => ({_time: r._time, year: r.year, month: string(v: date.month(t: r._time)), pun: r._value}))

// 3. Join, calcola costo e somma totale
join.inner(
  left: prelievo,
  right: pun,
  on: (l, r) => l.year == r.year and l.month == r.month,
  as: (l, r) => ({
    _time: l._time,
    "Costo Con Fotovoltaico": (l.prelievo_wh / 1000.0) * r.pun
  })
)
  |> sum(column: "Costo Con Fotovoltaico")
```

**7.3 Total Reimbursements from Grid Feed-In**

Calculates total revenue from energy exported to grid, valued at PUN prices.

```flux
import "timezone"
import "date"
import "join"

option location = timezone.location(name: "Europe/Rome")

// 1. Immissione mensile (energia venduta alla rete)
immissione = from(bucket: "Solaredge")
  |> range(start: 0)
  |> filter(fn: (r) => r._measurement == "api" and r._field == "Meter" and r.endpoint == "site_energy_details" and r.metric == "FeedIn")
  |> aggregateWindow(every: 1mo, fn: sum, createEmpty: false)
  |> group()
  |> map(fn: (r) => ({_time: r._time, year: string(v: date.year(t: r._time)), month: string(v: date.month(t: r._time)), immissione_wh: r._value}))

// 2. PUN mensile
pun = from(bucket: "GME")
  |> range(start: 0)
  |> filter(fn: (r) => r._measurement == "gme_monthly_avg" and r._field == "pun_kwh_avg")
  |> group()
  |> map(fn: (r) => ({_time: r._time, year: r.year, month: string(v: date.month(t: r._time)), pun: r._value}))

// 3. Join, calcola rimborso e somma totale
join.inner(
  left: immissione,
  right: pun,
  on: (l, r) => l.year == r.year and l.month == r.month,
  as: (l, r) => ({
    _time: l._time,
    "Rimborsi Immissione": (l.immissione_wh / 1000.0) * r.pun
  })
)
  |> sum(column: "Rimborsi Immissione")
```

**7.4 Historical Average PUN Price**

Calculates the average PUN price across all months.

```flux
from(bucket: "GME")
  |> range(start: 0)
  |> filter(fn: (r) => r._measurement == "gme_monthly_avg" and r._field == "pun_kwh_avg")
  |> mean()
```

**Total Savings Calculation:**

To calculate total savings from photovoltaic system, use these three values in Grafana:

```
Total Savings = ${Costo Senza Fotovoltaico} - ${Costo Con Fotovoltaico} + ${Rimborsi Immissione}
```

**Explanation:**
- **Costo Senza Fotovoltaico**: What you would have paid buying all energy from grid
- **Costo Con Fotovoltaico**: What you actually paid (only grid imports)
- **Difference**: Savings from NOT buying energy (covered by solar)
- **+ Rimborsi**: Money earned selling excess energy

**Example:**
- Without PV: €10,000
- With PV: €3,000 (less grid imports)
- Reimbursements: €1,500 (sold energy)
- **Total Savings = €10,000 - €3,000 + €1,500 = €8,500**

> [!TIP]
> - All queries use month-by-month PUN matching for accurate historical pricing
> - Each month's energy is valued at that specific month's average PUN price
> - Use Stat panels with `currency(EUR)` unit for visualization
> - Combine all three queries in a single dashboard for complete financial overview
