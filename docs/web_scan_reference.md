# Web Scan System - Technical Reference

## Overview

This document describes **how the web scan system works** technically. It does NOT describe what we want to do with it, but rather how the system functions internally.

---

## System Architecture

### Components

1. **`WebTreeScanner`** (`tools/web_tree_scanner.py`)
   - Fetches the "tree" JSON from SolarEdge API
   - Saves raw snapshot to `cache/snapshots/web_tree/latest.json`
   - Does NOT modify any configuration files

2. **`YawlManager`** (`tools/yawl_manager.py`)
   - Reads the snapshot from `cache/snapshots/web_tree/latest.json`
   - Extracts device information recursively
   - Generates `config/sources/web_endpoints.yaml`
   - Preserves existing `enabled` states during regeneration

3. **`scan_flow`** (`flows/scan_flow.py`)
   - Orchestrates the scan process
   - Calls `WebTreeScanner.scan()` first
   - Then calls `YawlManager.generate_web_endpoints_only()`

---

## Command: `python main.py --scan`

### What It Does

1. **Authenticates** to SolarEdge monitoring portal
2. **Fetches** the `/services/charts/site/{site_id}/tree` endpoint
3. **Saves** raw JSON snapshot to `cache/snapshots/web_tree/latest.json`
4. **Parses** the snapshot to extract all devices
5. **Generates** `config/sources/web_endpoints.yaml` with all discovered devices

### Snapshot Structure

The `tree` JSON contains:
- `siteStructure`: Main device hierarchy (inverters, optimizers, strings)
- `meters`: Meter devices
- `storage`: Battery storage devices
- `evChargers`: EV charger devices
- `smartHome`: Smart home devices
- `gateways`: Gateway devices
- `environmental.meteorologicalData`: Weather station

---

## YAML Generation Process

### Device Extraction (`YawlManager._extract_devices_recursive`)

For each item in the tree:
1. Check if it has `itemId` (indicates it's a device)
2. Extract:
   - `itemType`: Device type (INVERTER, OPTIMIZER, METER, SITE, STRING, WEATHER)
   - `id`: Device ID
   - `name`: Device name
   - `parameters`: Available measurements

3. Create endpoint entry with structure:
   ```yaml
   {device_type}_{device_id}:
     device_id: "{id}"
     device_name: "{name}"
     device_type: {itemType}
     enabled: {true/false}  # Default: true for OPTIMIZER and WEATHER, false for others
     category: "{category}"  # Derived from device_type
     date_range: "{range}"   # See web_endpoints_reference.md "Supported Date Ranges"
     measurements:
       {MEASUREMENT_NAME}:
         enabled: {true/false}  # Matches device enabled state
   ```

### Category Mapping (`_get_category_for_device`)

| Device Type | Category |
|-------------|----------|
| INVERTER | Inverter |
| METER | Meter |
| SITE | Site |
| STRING | String |
| WEATHER | Weather |
| OPTIMIZER | Optimizer group |

### Special Handling

#### OPTIMIZER and STRING Devices
- Extract `connectedToInverter` field
- Add `inverter: {inverter_id}` to endpoint config

#### STRING Devices
- Extract `identifier` field if available and not "0"
- Add `identifier: {value}` to endpoint config

#### WEATHER Devices
- Always use `device_id: "weather_default"` regardless of actual ID

---

## Configuration Preservation

### Merge Logic (`_merge_with_existing_config`)

When regenerating `web_endpoints.yaml`:

1. **Load existing configuration** from `config/sources/web_endpoints.yaml`
2. **For each device**:
   - If device exists in old config: **preserve** its `enabled` state
   - If device exists in old config: **preserve** all measurement `enabled` states
   - If device is new: use **default** enabled state (true for OPTIMIZER/WEATHER, false for others)

3. **Result**: New devices are added, removed devices are deleted, but user's enabled/disabled choices are preserved

---

## Default Enabled States

### Device Level

| Device Type | Default Enabled |
|-------------|-----------------|
| OPTIMIZER | ✅ true |
| WEATHER | ✅ true |
| SITE | ✅ true |
| INVERTER | ❌ false |
| METER | ❌ false |
| STRING | ❌ false |

### Measurement Level

All measurements inherit the device's enabled state by default.

---

## Smart Range Mode

The system uses a "Smart Range" mode to optimize API requests:

*   **History Mode** (explicit dates):
    *   **Daily/7days Devices**: Iterates day-by-day to ensure maximum precision and avoid overlaps.
    *   **Monthly Devices** (e.g. Site): Iterates month-by-month to optimize requests and ensure cache consistency with Loop Mode.
*   **Loop Mode** (no dates): Uses the `date_range` field defined in `web_endpoints.yaml`:
    *   `7days`: Requests last 7 days (e.g., for Optimizers).
    *   `monthly`: Requests from 1st of current month to today (e.g., for Site).
    *   `daily`: Requests only today.

This ensures high-resolution devices (Optimizers) have a short but detailed history, while aggregated devices (Site) maintain monthly consistency.

---

## File Locations

### Input
- **Snapshot**: `cache/snapshots/web_tree/latest.json`
  - Raw JSON from SolarEdge API
  - Overwritten on each scan
  - Single file (no versioning)

### Output
- **Configuration**: `config/sources/web_endpoints.yaml`
  - Generated from snapshot
  - Preserves user's enabled states
  - Used by `CollectorWeb` to build API requests

---

## API Endpoint Details

### Tree Endpoint
```
GET https://monitoring.solaredge.com/services/charts/site/{site_id}/tree
```

**Authentication**: Requires valid session cookie

**Response**: JSON object containing complete device hierarchy

**Headers Required**:
- `Cookie`: Session cookie from login
- `X-CSRF-TOKEN`: CSRF token (if available)
- `Accept`: `application/json`

---

## How CollectorWeb Uses web_endpoints.yaml

### Request Building (`_build_request`)

For each enabled device in `web_endpoints.yaml`:

1. **Read device configuration**:
   - `device_type`: Used as `itemType` in API request
   - `device_id`: Used as `id`, `originalSerial`, `identifier`
   - Enabled measurements: Added to `measurementTypes` array

2. **Build API request**:
   ```json
   {
     "device": {
       "itemType": "{device_type}",
       "id": "{device_id}",
       "originalSerial": "{device_id}",
       "identifier": "{device_id}"
     },
     "deviceName": "{device_name}",
     "measurementTypes": ["{MEASUREMENT_1}", "{MEASUREMENT_2}", ...]
   }
   ```

3. **Special cases**:
   - **STRING**: Add `connectedToInverter` field
   - **WEATHER**: Omit `id`, `originalSerial`, `identifier` fields

### Date Range Parameters

Currently, `CollectorWeb._get_date_params()` returns:
```python
{
    "start-date": "{date}",  # Single day
    "end-date": "{date}"     # Same day
}
```

**IMPORTANT**: This is a **global setting** - all devices use the same date range.

---

## Extending the System

### Adding Custom Parameters to Devices

To add custom parameters (like `date_range`) to devices:

1. **Modify `YawlManager._create_device_endpoint()`**:
   - Add the new field to the endpoint dictionary
   - Set default value based on device type or other criteria

2. **Modify `CollectorWeb`**:
   - Read the custom parameter from device config
   - Use it when building API requests

3. **Update this documentation**:
   - Document the new parameter's purpose
   - Explain how it affects API calls
   - Provide examples

### Example: Adding `date_range` Parameter

**Step 1**: Modify `YawlManager._create_device_endpoint()` (line ~60):
```python
# After setting 'category'
if device_type == 'SITE':
    endpoint['date_range'] = 'monthly'  # Custom range for SITE
else:
    endpoint['date_range'] = 'daily'    # Default for others
```

**Step 2**: Modify `CollectorWeb._fetch_batch()` to read and use it:
```python
def _fetch_batch(self, device_type: str, batch: List[Dict[str, Any]]) -> List:
    # Read date_range from first device in batch
    date_range = batch[0].get('date_range', 'daily') if batch else 'daily'
    
    # Modify _get_date_params to accept and use date_range
    params = self._get_date_params(
        getattr(self, '_target_date', None),
        date_range=date_range
    )
    # ... rest of the code
```

**Step 3**: Update `_get_date_params()` signature and logic:
```python
def _get_date_params(self, target_date: str = None, date_range: str = 'daily') -> Dict[str, str]:
    # ... calculate dates based on date_range parameter
```

---

## Important Notes

### Snapshot Lifecycle
- **Single snapshot**: Only `latest.json` is kept
- **No versioning**: Each scan overwrites the previous snapshot
- **No history**: Old device configurations are lost if not in new scan

### Configuration Preservation
- **Enabled states**: Always preserved across scans
- **New devices**: Added with default enabled state
- **Removed devices**: Deleted from configuration
- **Measurement changes**: New measurements added, removed ones deleted

### Scan Frequency
- **Manual only**: Scan is triggered by `--scan` command
- **No automatic scanning**: System does not auto-detect new devices
- **User responsibility**: Must run scan after adding/removing physical devices

---

## Troubleshooting

### Scan Fails with HTTP 401/403
- **Cause**: Session cookie expired or invalid
- **Solution**: Collector will attempt automatic re-login

### Empty web_endpoints.yaml Generated
- **Cause**: Snapshot file missing or empty
- **Solution**: Run `python main.py --scan` to create fresh snapshot

### Device Not Appearing in YAML
- **Cause**: Device has no `parameters` in tree JSON
- **Solution**: Check if device is properly configured in SolarEdge portal

### Enabled States Reset to Default
- **Cause**: Device ID changed (e.g., device replaced)
- **Solution**: Manually re-enable in `web_endpoints.yaml`

---

## Summary

The web scan system is a **two-phase process**:

1. **Scan Phase** (`WebTreeScanner`):
   - Fetch raw device tree from API
   - Save to snapshot file
   - No configuration changes

2. **Generation Phase** (`YawlManager`):
   - Parse snapshot
   - Extract devices and measurements
   - Generate YAML configuration
   - Preserve user's enabled states

**Key Principle**: The system **discovers** devices automatically but **respects** user's manual configuration choices.
