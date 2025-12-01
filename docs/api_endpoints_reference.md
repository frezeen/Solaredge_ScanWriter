# Sistema Storage API SolarEdge - Riferimento Tecnico

## Scopo

Questo documento descrive **come il sistema raccoglie, processa e memorizza i dati dalle API ufficiali SolarEdge** in InfluxDB. Per come interrogare i dati, vedi altri documenti di riferimento.

---

## Struttura Storage InfluxDB

### Nome Measurement
Tutti i dati API sono memorizzati in un singolo measurement: **`api`**

### Struttura Data Point

**Tag** (indicizzati):
- `endpoint`: Nome endpoint API (es. "site_energy_details", "equipment_data")
- `metric`: Tipo meter o metrica specifica (es. "Production", "temperature", "L1Data_acCurrent")
- `unit`: Unità di misura (es. "W", "Wh", "V", "A", "°C") - opzionale

**Field**:
- Nome determinato dalla **category** in `api_endpoints.yaml`
- Valore: float per dati strutturati, string JSON per metadata

**Timestamp**:
- Precisione nanosecondi
- Convertito da datetime: `timestamp_seconds * 1_000_000_000`

---

## Sistema Category

### Come Funziona

1. Parser legge configurazione endpoint da `api_endpoints.yaml`
2. Estrae campo `category`
3. Usa `category` come nome field InfluxDB
4. Errore se category mancante

Posizione codice: `parser/api_parser.py` → `_create_raw_point()` (riga 69-90)

### Mappatura Category

| Category | Field InfluxDB | Tipo Dato | Endpoint Tipici |
|----------|----------------|-----------|-----------------|
| `Inverter` | `Inverter` | float | site_energy_*, equipment_data |
| `Meter` | `Meter` | float | site_energy_details, site_power_details |
| `Flusso` | `Flusso` | string (JSON) | site_power_flow |
| `Info` | `Info` | string (JSON) | site_details, site_overview, equipment_list |

---

## Pipeline Flusso Dati

### Step 1: Richiesta API

CollectorAPI costruisce ed esegue richieste HTTP:

```python
# Costruzione URL
url = f"{base_url}/site/{site_id}/energyDetails"

# Parametri
params = {
    'api_key': api_key,
    'startTime': '2025-11-29 00:00:00',
    'endTime': '2025-11-29 23:59:59',
    'meters': 'PRODUCTION,CONSUMPTION'
}

# Chiamata HTTP
response = session.get(url, params=params, timeout=30)
data = response.json()
```

Posizione codice: `collector/collector_api.py` → `_call_api()` (riga 106-125)

### Step 2: Parsing Dati

Parser processa risposta API in base a `data_format`:

**Formato Strutturato** (dati numerici):
- Estrae valori da JSON annidato
- Crea dizionari strutturati con tag e field
- Converte timestamp a UTC

**Formato Raw JSON** (metadata):
- Memorizza intera risposta JSON come string
- Processamento minimo

Posizione codice: `parser/api_parser.py` → `parse()` (riga 458-517)

### Step 3: Filtraggio

I raw point passano attraverso regole di filtraggio:

```python
# Filtra point strutturati
filtered_structured = filter_structured_points(all_structured_dicts)

# Filtra raw point
filtered_raw = filter_raw_points(all_raw_points)
```

Posizione codice: `parser/api_parser.py` → `parse()` (riga 488-493)

### Step 4: Conversione Point

Dati filtrati convertiti a oggetti InfluxDB Point:

```python
point = Point("api")
point.tag("endpoint", "site_energy_details")
point.tag("metric", "Production")
point.tag("unit", "Wh")
point.field("Meter", 15420.0)  # category come nome field
point.time(1732875600000000000, WritePrecision.NS)
```

Posizione codice: `parser/api_parser.py` → `_convert_dict_to_point()` (riga 131-165)

### Step 5: Scrittura

InfluxWriter scrive i point nel bucket InfluxDB.

Posizione codice: `storage/writer_influx.py` → `write_points()`

---

## Tipi di Endpoint

### Endpoint Dati Strutturati

**site_energy_details**:
- URL: `/site/{siteId}/energyDetails`
- Formato: Meter annidati con serie temporali
- Category: `Meter`
- Parsing: Estrae tipo meter, timestamp, valore, unità

**site_power_details**:
- URL: `/site/{siteId}/powerDetails`
- Formato: Meter annidati con serie temporali
- Category: `Meter`
- Parsing: Uguale a energy_details

**equipment_data**:
- URL: `/equipment/{siteId}/{serialNumber}/data`
- Formato: Array di telemetrie
- Category: `Inverter`
- Parsing: Estrae multipli field per telemetria

**site_timeframe_energy**:
- URL: `/site/{siteId}/timeFrameEnergy`
- Formato: Singolo valore energia con metadata
- Category: `Inverter`
- Parsing: Estrae valore energia e data inizio

### Endpoint Metadata

**site_details**:
- URL: `/site/{siteId}/details`
- Category: `Info`
- Storage: Appiattito in multipli point (uno per field)

**site_overview**:
- URL: `/site/{siteId}/overview`
- Category: `Info`
- Storage: Singolo point con stringa JSON

**equipment_list**:
- URL: `/equipment/{siteId}/list`
- Category: `Info`
- Storage: Singolo point con stringa JSON

---

## Gestione Timestamp

### Formati Input

API fornisce timestamp in vari formati:
- `"2025-11-29 10:00:00"` (ora locale, senza timezone)
- `"2025-11-29T10:00:00+01:00"` (ISO 8601 con timezone)

### Processo Conversione

1. **Parse** stringa a oggetto datetime
2. **Localizza** a timezone configurato (default: Europe/Rome)
3. **Converti** a UTC
4. **Estrai** Unix timestamp in secondi
5. **Moltiplica** per 1.000.000.000 per ottenere nanosecondi
6. **Scrivi** in InfluxDB con precisione nanosecondo

Posizione codice: `parser/api_parser.py` → `_parse_timestamp()` (riga 92-98)

---

## Costruzione Parametri

### Sostituzione Automatica Date

Collector sostituisce automaticamente placeholder nei parametri endpoint:

| Placeholder | Sostituito Con | Esempio |
|-------------|----------------|---------|
| `${API_START_DATE}` | Data corrente | `2025-11-29` |
| `${API_END_DATE}` | Data corrente | `2025-11-29` |
| `${API_START_TIME}` | Data corrente + 00:00:00 | `2025-11-29 00:00:00` |
| `${API_END_TIME}` | Data corrente + 23:59:59 | `2025-11-29 23:59:59` |
| `${CURRENT_YEAR_START}` | Inizio anno | `2025-01-01` |
| `${CURRENT_YEAR_END}` | Fine anno | `2025-12-31` |

Posizione codice: `collector/collector_api.py` → `_build_params()` (riga 71-104)

### Aggiunta Automatica Date

Per endpoint che richiedono date ma non le hanno in configurazione:
- Aggiunge automaticamente `startTime` e `endTime` per giorno corrente
- Si applica a: energyDetails, powerDetails, meters endpoint

---

## Sistema Caching

### Struttura Chiave Cache

```
source: "api_ufficiali"
endpoint: "{endpoint_name}"
date: "YYYY-MM-DD"
```

### Comportamento Cache

**Modalità Giornaliera** (`collect()`):
- Ogni endpoint cachato per giorno
- TTL: 15 minuti (configurabile)
- Chiave cache: nome endpoint + data odierna

**Modalità Storico** (`collect_with_dates()`):
- Dati mensili suddivisi in voci cache giornaliere
- Ogni giorno cachato separatamente
- Chiave cache: nome endpoint + data specifica

Posizione codice: `collector/collector_api.py` → `collect()` (riga 163-188), `collect_with_dates()` (riga 220-362)

### Suddivisione Dati

Risposte API mensili suddivise in chunk giornalieri per caching:

**site_energy_details / site_power_details**:
- Raggruppa valori per campo data
- Crea voce cache separata per giorno
- Preserva struttura meter

**equipment_data**:
- Raggruppa telemetrie per campo data
- Crea voce cache separata per giorno
- Preserva struttura telemetria

Posizione codice: `collector/collector_api.py` → `_split_data_by_day()` (riga 586-670)

---

## Gestione Speciale Endpoint

### Equipment Endpoints

Richiedono serial number da equipment_list:

1. **Recupera** endpoint equipment_list
2. **Estrae** primo serial number da reporters.list
3. **Usa** serial number in URL: `/equipment/{siteId}/{serialNumber}/data`

Posizione codice: `collector/collector_api.py` → `_collect_equipment_endpoint()` (riga 127-161)

### Equipment Data - Limite Temporale

Limitazione API: Massimo 7 giorni per richiesta

**Soluzione**: Suddivisione automatica settimanale per periodi lunghi
- Divide periodo in chunk da 6 giorni (con overlap)
- Effettua multiple chiamate API
- Aggrega telemetrie in singola risposta

Posizione codice: `collector/collector_api.py` → `_collect_equipment_by_weeks()` (riga 445-492)

### Site Energy Day

Limitazione API: Massimo 1 anno per richiesta (timeUnit=DAY)

**Soluzione**: Suddivisione automatica annuale
- Divide periodo in chunk annuali
- Una chiamata API per anno
- Aggrega valori in singola risposta

Posizione codice: `collector/collector_api.py` → `_collect_site_energy_day_with_dates()` (riga 676-745)

### Site Timeframe Energy

**Smart caching** per anno:
- Controlla cache per ogni anno individualmente
- Recupera solo anni mancanti dall'API
- Col tempo, solo nuovo anno richiede chiamata API

Posizione codice: `collector/collector_api.py` → `_collect_site_timeframe_energy_smart_cache()` (riga 747-847)

---

## Tipi Meter

### Meter Disponibili

| Tipo Meter | Descrizione | Disponibile In |
|------------|-------------|----------------|
| `Production` | Energia/Potenza prodotta | energy_details, power_details |
| `Consumption` | Energia/Potenza consumata | energy_details, power_details |
| `SelfConsumption` | Energia/Potenza autoconsumata (virtuale) | energy_details, power_details |
| `FeedIn` | Energia/Potenza esportata in rete | energy_details, power_details |
| `Purchased` | Energia/Potenza importata da rete | energy_details, power_details |

### Storage Tipo Meter

Ogni tipo meter memorizzato con proprio tag:

```
measurement: api
tags:
  endpoint: site_energy_details
  metric: Production  ← tipo meter
  unit: Wh
fields:
  Meter: 15420.0
```

---

## Field Equipment Data

### Field Telemetria Principali

| Field | Unità | Descrizione |
|-------|-------|-------------|
| `totalActivePower` | W | Potenza attiva totale |
| `dcVoltage` | V | Tensione DC dai pannelli |
| `powerLimit` | % | Limite potenza applicato |
| `totalEnergy` | Wh | Energia lifetime |
| `temperature` | °C | Temperatura inverter |

### Field Dati Fase (L1Data, L2Data, L3Data)

| Field | Unità | Descrizione |
|-------|-------|-------------|
| `acCurrent` | A | Corrente AC |
| `acVoltage` | V | Tensione AC |
| `acFrequency` | Hz | Frequenza AC |
| `apparentPower` | VA | Potenza apparente |
| `activePower` | W | Potenza attiva |
| `reactivePower` | VAr | Potenza reattiva |
| `cosPhi` | - | Fattore di potenza |

### Formato Storage

Ogni field memorizzato come point separato con tag metric:

```
measurement: api
tags:
  endpoint: equipment_data
  metric: L1Data_acCurrent  ← nome field
  unit: A
fields:
  Inverter: 5.2
```

Posizione codice: `parser/api_parser.py` → `_process_equipment_data()` (riga 351-408)

---

## Normalizzazione Unità

| Unità API | Normalizzata | Note |
|-----------|--------------|------|
| `w`, `W` | `W` | Watt |
| `wh`, `Wh` | `Wh` | Watt-ora |
| `kw`, `kW` | `kW` | Kilowatt |
| `kwh`, `kWh` | `kWh` | Kilowatt-ora |
| Altre | Invariate | Passate così come sono |

Posizione codice: `parser/api_parser.py` → `_normalize_unit()` (riga 100-105)

---

## Esempi Storage

### Esempio 1: Energy Details

**Risposta API**:
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

**Point InfluxDB**:
```
measurement: api
tags: endpoint=site_energy_details, metric=Production, unit=Wh
fields: Meter=1250.5
timestamp: 1732875600000000000
```

### Esempio 2: Equipment Data

**Risposta API**:
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

**Point InfluxDB** (2 point, uno per field):
```
1. measurement: api
   tags: endpoint=equipment_data, metric=totalActivePower, unit=W
   fields: Inverter=3500.0

2. measurement: api
   tags: endpoint=equipment_data, metric=temperature, unit=C
   fields: Inverter=45.2
```

### Esempio 3: Site Details (Metadata)

**Risposta API**:
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

**Point InfluxDB** (multipli point, appiattiti):
```
1. tags: endpoint=site_details, metric=name, unit=raw
   fields: Info="My Solar Site"

2. tags: endpoint=site_details, metric=peakPower, unit=raw
   fields: Info="5000"

3. tags: endpoint=site_details, metric=location_country, unit=raw
   fields: Info="Italy"

4. tags: endpoint=site_details, metric=location_city, unit=raw
   fields: Info="Rome"
```

Posizione codice: `parser/api_parser.py` → `_convert_site_details_to_points()` (riga 183-213)

---

## Gestione Errori

### Category Mancante
- **Trigger**: Config endpoint manca campo `category`
- **Azione**: Solleva ValueError
- **Log**: Messaggio errore con nome endpoint

### Errori HTTP
- **Trigger**: API restituisce codice status non-200
- **Azione**: Log errore e salta endpoint
- **Log**: Codice status HTTP e nome endpoint

### Errori Parsing
- **Trigger**: Struttura dati inaspettata
- **Azione**: Log errore e salta endpoint
- **Log**: Dettagli eccezione

Posizione codice: `collector/collector_api.py` → `_call_api()` (riga 106-125), `collect()` (riga 184-186)

---

## Ottimizzazioni Performance

### HTTP Session Pooling

Singola sessione riusata per tutte le richieste:
```python
self._session = requests.Session()
self._session.headers.update({
    'User-Agent': 'SolarEdge-Collector/1.0',
    'Accept': 'application/json'
})
```

Benefici:
- Riuso connessione (TCP keep-alive)
- Latenza ridotta
- Minor uso risorse

Posizione codice: `collector/collector_api.py` → `__init__()` (riga 36-41)

### Integrazione Scheduler

Scheduler opzionale per rate limiting:
```python
if self.scheduler:
    return self.scheduler.execute_with_timing(SourceType.API, _http_call, cache_hit=False)
else:
    return _http_call()
```

Posizione codice: `collector/collector_api.py` → `_call_api()` (riga 122-125)

### Smart Caching

- Cache giornaliera per modalità normale
- Cache per-anno per timeframe_energy
- Suddivisione cache automatica per modalità storico

---

## Limitazioni API

### Rate Limit

- **Quota giornaliera**: 300 richieste per account/sito
- **Concorrenza**: Max 3 richieste simultanee da stesso IP

### Limiti Range Temporale

| Endpoint | Range Max | Risoluzione |
|----------|-----------|-------------|
| site_energy_details (DAY) | 1 anno | Giornaliera |
| site_energy_details (HOUR/QUARTER) | 1 mese | Oraria/15min |
| site_power_details | 1 mese | 15 minuti |
| equipment_data | 1 settimana | Variabile |

### Soluzioni

Sistema gestisce automaticamente limitazioni:
- **Suddivisione annuale** per site_energy_day
- **Suddivisione settimanale** per equipment_data
- **Smart caching** per minimizzare chiamate API

---

## Riepilogo

Il sistema storage API:

1. **Costruisce** richieste HTTP con sostituzione automatica parametri
2. **Recupera** dati da API SolarEdge con caching
3. **Processa** risposte in base a configurazione endpoint
4. **Filtra** data point usando regole filtraggio
5. **Converte** a point InfluxDB con:
   - Measurement: `api`
   - Tag: `endpoint`, `metric`, `unit`
   - Field: Nome da category, valore da API
   - Timestamp: Precisione nanosecondo
6. **Scrive** in InfluxDB in batch

**Design Chiave**: Sistema configuration-driven dove comportamento endpoint è definito in YAML, permettendo raccolta dati flessibile senza modifiche codice.