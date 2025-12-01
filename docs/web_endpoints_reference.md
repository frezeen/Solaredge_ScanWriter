# Sistema Storage Dati Web - Riferimento Tecnico

## Scopo

Questo documento descrive **come il sistema scrive i dati web in InfluxDB** dal punto di vista tecnico dell'implementazione. Per come interrogare i dati, vedi `query_grafana_reference.md`.

---

## Pipeline Flusso Dati

### Step 1: Risposta API

CollectorWeb riceve JSON dall'API SolarEdge:
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

### Step 2: Creazione Raw Point

Parser estrae i dati e crea un raw point:
```python
{
    "source": "web",
    "device_id": "21830A42-F0",
    "device_type": "OPTIMIZER",
    "metric": "PRODUCTION_POWER",
    "value": 245.5,
    "timestamp": 1732875600000,  # millisecondi
    "unit": "W",
    "category": "Optimizer group"  # da config
}
```

Posizione codice: `parser/web_parser.py` → `_create_raw_point()` (riga 78-97)

### Step 3: Conversione a InfluxDB Point

Raw point convertito a oggetto InfluxDB Point:
```python
Point("web")
    .tag("endpoint", "PRODUCTION_POWER")
    .tag("device_id", "21830A42-F0")
    .tag("unit", "W")
    .field("Optimizer group", 245.5)  # category come nome field
    .time(1732875600000000000, WritePrecision.NS)
```

Posizione codice: `parser/web_parser.py` → `_convert_raw_point_to_influx_point()` (riga 106-136)

### Step 4: Scrittura

InfluxWriter scrive il point nel bucket InfluxDB.

Posizione codice: `storage/writer_influx.py` → `write_points()` (riga 158)

---

## Sistema Category

### Come Funziona

La **category** determina il nome del field in InfluxDB:

1. Parser legge `web_endpoints.yaml`
2. Cerca il `device_id` dalla risposta API nella configurazione
3. Estrae il campo `category`
4. Usa `category` come nome del field InfluxDB
5. Se non trova corrispondenza → usa `"Info"` come default

Posizione codice: `parser/web_parser.py` → `_get_category_from_config()` (riga 138-156)

### Esempio Configurazione
```yaml
web_scraping:
  endpoints:
    site_2489781:
      device_id: "2489781"
      category: "Site"  # ← Diventa il nome field in InfluxDB
```

### Mappatura Category → Field

| Device Type | Category Config | Field InfluxDB |
|-------------|-----------------|----------------|
| INVERTER | `Inverter` | `Inverter` |
| METER | `Meter` | `Meter` |
| SITE | `Site` | `Site` |
| OPTIMIZER | `Optimizer group` | `Optimizer group` |
| STRING | `String` | `String` |
| WEATHER | `Weather` | `Weather` |
| Sconosciuto | `Info` (default) | `Info` |

---

## Gestione Timestamp

### Formato Input

API fornisce timestamp in formato ISO 8601:
- `"2025-11-29T10:00:00+01:00"` (con timezone)
- `"2025-11-29T10:00:00Z"` (UTC)

### Processo di Conversione

1. **Parse** stringa ISO 8601 a oggetto datetime
2. **Converti** a UTC se timezone-aware
3. **Estrai** Unix timestamp in millisecondi
4. **Moltiplica** per 1.000.000 per ottenere nanosecondi
5. **Scrivi** in InfluxDB con precisione nanosecondo

Posizione codice: `parser/web_parser.py` → `_convert_timestamp()` (riga 57-76)

---

## Normalizzazione Unità

Le unità dall'API vengono normalizzate a formato standard:

| Unità API | Normalizzata | Note |
|-----------|--------------|------|
| `w`, `W` | `W` | Watt |
| `wh`, `Wh` | `Wh` | Watt-ora |
| `kw`, `kW` | `kW` | Kilowatt |
| `kwh`, `kWh` | `kWh` | Kilowatt-ora |
| Altre | Invariate | Passate così come sono |

Posizione codice: `parser/web_parser.py` → `_normalize_unit()` (riga 99-104)

---

## Estrazione Device ID

I Device ID provengono dal campo `device.id` della risposta API, con gestione speciale:

| Device Type | Sorgente ID | Esempio | Note |
|-------------|-------------|---------|------|
| INVERTER | API `id` | `7403D7C5-13` | Numero seriale con suffisso |
| METER | API `id` | `606483640` | ID numerico |
| OPTIMIZER | API `id` | `21830A42-F0` | Numero seriale con suffisso |
| STRING | API `id` | `0`, `1`, `2` | Indice numerico |
| SITE | API `id` | `2489781` | Numero ID sito |
| WEATHER | Hardcoded | `weather_default` | Sempre stesso ID |

Posizione codice: `parser/web_parser.py` → `_extract_device_info()` (riga 38-55)

---

## Filtraggio Dati

Prima di scrivere in InfluxDB, i raw point passano attraverso filtraggio:

### Regole Filtro

1. **Valori null**: Point con `value = None` vengono scartati
2. **Timestamp non validi**: Point con `timestamp <= 0` vengono scartati
3. **Rilevamento duplicati**: Implementato in `filtro/regole_filtraggio.py`

Posizione codice: `parser/web_parser.py` → `parse_web()` (riga 194)

---

## Gestione Errori

### Category Mancante
- **Trigger**: `device_id` non trovato in `web_endpoints.yaml`
- **Azione**: Usa `"Info"` come category di default
- **Log**: Messaggio warning con device ID disponibili

### Valore Non Valido
- **Trigger**: Valore non convertibile a float
- **Azione**: Memorizza come string in InfluxDB
- **Log**: Messaggio debug

### Timestamp Mancante
- **Trigger**: Timestamp è None o <= 0
- **Azione**: Scarta il data point
- **Log**: Nessun log (scarto silenzioso)

---

## Esempio Storage Completo

### Input (Risposta API)
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

### Output (Point InfluxDB)
```
Measurement: web
Tags:
  endpoint=PRODUCTION_ENERGY
  device_id=2489781
  unit=Wh
Fields:
  Site=15420.0
Timestamp: 1732875600000000000 (nanosecondi)
```

### Line Protocol InfluxDB
```
web,endpoint=PRODUCTION_ENERGY,device_id=2489781,unit=Wh Site=15420.0 1732875600000000000
```

---

## Considerazioni Performance

### Scrittura Batch
- I point vengono raccolti in memoria
- Scritti in batch in InfluxDB
- Dimensione batch: 500 point (configurabile)

### Cardinalità Tag
- `endpoint`: ~10-20 valori unici per tipo dispositivo
- `device_id`: Numero di dispositivi fisici (tipicamente 1-50)
- `unit`: ~10 valori unici totali

**Cardinalità totale**: Bassa (< 1000 combinazioni tag uniche)

---

## Riepilogo

Il sistema di storage dati web:

1. **Riceve** JSON dall'API SolarEdge
2. **Estrae** info dispositivo e misurazioni
3. **Cerca** category dalla configurazione
4. **Crea** point InfluxDB con:
   - Measurement: `web`
   - Tag: `endpoint`, `device_id`, `unit`
   - Field: Nome dalla category, valore dall'API
   - Timestamp: Precisione nanosecondo
5. **Scrive** in InfluxDB in batch

**Design Chiave**: Il sistema category permette nomi field flessibili mantenendo struttura measurement consistente.