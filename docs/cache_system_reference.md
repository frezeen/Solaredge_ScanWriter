# Sistema Cache - Riferimento Tecnico

## Scopo

Questo documento descrive **come funziona il sistema di cache** per ridurre le chiamate API e ottimizzare le performance del sistema. La cache è gestita dal `CacheManager` e supporta TTL configurabili, compressione, e validazione tramite hash.

---

## Architettura Cache

### Struttura Directory

```
cache/
├── api_ufficiali/
│   ├── site_details/
│   │   ├── 2025-11_19-51_a1b2c3d4.json.gz
│   │   └── 2025-12_20-14_e5f6g7h8.json.gz
│   └── site_energy_details/
│       └── 2025-11_19-51_9i0j1k2l.json.gz
├── web/
│   ├── SITE/
│   │   ├── 2025-11_19-51_m3n4o5p6.json.gz
│   │   └── 2025-12_20-14_q7r8s9t0.json.gz  (PARTIAL)
│   ├── OPTIMIZER/
│   │   └── 2025-11-25_19-52_u1v2w3x4.json.gz
│   └── WEATHER/
│       └── 2025-11-25_19-52_y5z6a7b8.json.gz
└── gme/
    ├── 2025-11-01_19-51_c9d0e1f2.json.gz
    └── 2025-11-02_19-51_g3h4i5j6.json.gz
```

### Convenzioni Naming

**Formato**: `{date}_{time}_{hash}.json.gz`

- **date**: `YYYY-MM-DD` (giornaliero) o `YYYY-MM` (mensile)
- **time**: `HH-MM` (orario creazione cache)
- **hash**: 8 caratteri MD5 del contenuto dati
- **estensione**: `.json.gz` (sempre compresso)

**Esempi**:
- `2025-11-25_19-52_a1b2c3d4.json.gz` - Cache giornaliera
- `2025-12_20-14.json.gz` - Cache mensile PARTIAL (senza hash)
- `2025-12_20-14_e5f6g7h8.json.gz` - Cache mensile SEALED (con hash)

---

## Stati Cache

### SEALED (Sigillato)

Cache completa e immutabile per periodi conclusi.

**Caratteristiche**:
- Nome file include hash MD5 del contenuto
- TTL ignorato (cache infinita)
- Non viene mai riscritta
- Usata per mesi/giorni completi

**Esempio**: `2025-11_19-51_a1b2c3d4.json.gz`

### PARTIAL (Parziale)

Cache temporanea per periodi in corso.

**Caratteristiche**:
- Nome file senza hash (suffisso `.json.gz`)
- Rispetta TTL configurato
- Può essere aggiornata
- Usata per mese/giorno corrente

**Esempio**: `2025-12_20-14.json.gz`

---

## TTL Configuration

Tempo di validità cache per sorgente (minuti):

```python
TTL_CONFIG = {
    'api_ufficiali': 15,    # API ufficiali: 15 minuti
    'web': 15,              # Web scraping: 15 minuti
    'gme': 1440             # GME: 24 ore (dati giornalieri)
}
```

**Comportamento**:
- Cache SEALED: TTL ignorato (infinito)
- Cache PARTIAL: dopo TTL, verifica hash per rilevare modifiche
- Se hash identico: cache hit (no API call)
- Se hash diverso: aggiorna cache

---

## Formato Dati Cache

### Struttura JSON

```json
{
  "data": {
    "list": [
      {
        "device": {
          "itemType": "SITE",
          "id": "2489781"
        },
        "measurementType": "PRODUCTION_ENERGY",
        "unitType": "WH",
        "measurements": [
          {
            "time": "2025-12-01T00:00:00+01:00",
            "measurement": 11054.0
          },
          {
            "time": "2025-12-02T00:00:00+01:00",
            "measurement": 2962.0
          }
        ]
      }
    ]
  },
  "source": "web",
  "endpoint": "SITE",
  "date": "2025-12",
  "data_hash": "a1b2c3d4"
}
```

### Campi Metadata

- **source**: Sorgente dati (`api_ufficiali`, `web`, `gme`)
- **endpoint**: Tipo endpoint/device
- **date**: Data riferimento (YYYY-MM-DD o YYYY-MM)
- **data_hash**: Hash MD5 del contenuto `data`

---

## Flusso Operativo

### 1. Lettura Cache (get_or_fetch)

```python
def get_or_fetch(
    source: str,
    endpoint: str,
    date: str,
    fetch_func: Callable,
    is_metadata: bool = False
) -> Dict[str, Any]:
```

**Processo**:

1. **Cerca file cache** per `source/endpoint/date`
2. **Verifica stato**:
   - SEALED → cache hit immediato
   - PARTIAL → verifica TTL
3. **Se TTL valido** → cache hit
4. **Se TTL scaduto**:
   - Chiama `fetch_func()` per ottenere nuovi dati
   - Calcola hash nuovo vs vecchio
   - Se identico → cache hit (aggiorna timestamp)
   - Se diverso → cache miss (salva nuovi dati)
5. **Se cache non esiste** → cache miss (fetch + save)

### 2. Scrittura Cache (save_cached_data)

```python
def save_cached_data(
    source: str,
    endpoint: str,
    date: str,
    data: Dict[str, Any],
    is_metadata: bool = False
) -> None:
```

**Processo**:

1. **Determina stato**:
   - Mese/giorno completo → SEALED
   - Mese/giorno corrente → PARTIAL
2. **Genera nome file**:
   - SEALED: include hash MD5
   - PARTIAL: senza hash
3. **Comprimi e salva**:
   - Serializza JSON
   - Comprimi con gzip
   - Scrivi file atomicamente
4. **Log operazione**:
   - `💾 CACHE SAVED [source] 🔒 SEALED: hash (date)`
   - `💾 CACHE SAVED [source] 📝 PARTIAL: hash (date)`

### 3. Validazione Hash

```python
def get_data_hash(data: Dict[str, Any]) -> str:
    return hashlib.md5(
        json.dumps(data, sort_keys=True).encode()
    ).hexdigest()[:8]
```

**Scopo**: Rilevare modifiche nei dati senza riscaricare completamente.

---

## Casi d'Uso Specifici

### API Ufficiali

**Granularità**: Mensile (`YYYY-MM`)

**Comportamento**:
- Mesi passati → SEALED (cache infinita)
- Mese corrente → PARTIAL (TTL 15 min)
- Hash check per rilevare nuovi dati del mese

**Esempio**:
```
cache/api_ufficiali/site_energy_details/
├── 2025-11_19-51_a1b2c3d4.json.gz  (SEALED - novembre completo)
└── 2025-12_20-14.json.gz           (PARTIAL - dicembre in corso)
```

### Web Scraping

**Granularità**: Variabile per device type

**SITE Device**:
- Granularità: Mensile (`YYYY-MM`)
- Aggregazione: Dati orari → giornalieri
- Merge: Accumula giorni nel mese corrente

**Altri Device** (OPTIMIZER, WEATHER):
- Granularità: Giornaliera (`YYYY-MM-DD`)
- No aggregazione

**Esempio SITE**:
```
cache/web/SITE/
├── 2025-11_19-51_m3n4o5p6.json.gz  (SEALED - 30 giorni)
└── 2025-12_20-14.json.gz           (PARTIAL - 2 giorni finora)
```

### GME (Mercato Elettrico)

**Granularità**: Giornaliera (`YYYY-MM-DD`)

**Comportamento**:
- Giorni passati → SEALED (cache infinita)
- Giorno corrente → PARTIAL (TTL 24h)
- Dati orari (24 valori PUN per giorno)

**Esempio**:
```
cache/gme/
├── 2025-11-01_19-51_c9d0e1f2.json.gz  (SEALED)
├── 2025-11-02_19-51_g3h4i5j6.json.gz  (SEALED)
└── 2025-12-02_20-14.json.gz           (PARTIAL - oggi)
```

---

## Aggregazione SITE (Web)

### Problema

L'API SolarEdge restituisce risoluzione variabile per device SITE:
- **Mesi completi**: Dati giornalieri (1 punto/giorno)
- **Mese corrente**: Dati orari (24 punti/giorno)

### Soluzione

Il `CollectorWeb` aggrega automaticamente dati orari in giornalieri:

```python
def _check_if_needs_aggregation(raw_data, date_range) -> bool:
    # Controlla intervallo tra primi 2 timestamp
    # Se < 24h → aggregazione necessaria
```

**Processo**:
1. Rileva risoluzione controllando delta timestamp
2. Se sub-giornaliera → aggrega per giorno
3. Merge con cache esistente (preserva giorni precedenti)
4. Normalizza timestamp a mezzanotte (`T00:00:00+01:00`)

**Risultato**: Cache mensile SITE contiene sempre dati giornalieri aggregati.

---

## Statistiche Cache

### Contatori

```python
stats = {
    'cache_hits': 0,      # Letture da cache
    'cache_misses': 0,    # Chiamate API
    'sealed_saves': 0,    # Salvataggi SEALED
    'partial_saves': 0    # Salvataggi PARTIAL
}
```

### Metodi

```python
# Ottieni statistiche
stats = cache.get_statistics()

# Reset contatori
cache.reset_statistics()
```

---

## Performance

### Riduzione API Calls

**Target**: ~90% riduzione chiamate API

**Meccanismi**:
1. Cache SEALED infinita per periodi completi
2. Hash check per PARTIAL (evita re-fetch se dati identici)
3. TTL ottimizzati per tipo sorgente

**Esempio History Mode**:
- 12 mesi da scaricare
- 11 mesi completi → SEALED (1 API call ciascuno)
- 1 mese corrente → PARTIAL (1 API call)
- Totale: 12 API calls
- Re-run: 1 API call (solo mese corrente)
- Riduzione: 91.7%

### Compressione

**Formato**: gzip (livello default)

**Benefici**:
- Riduzione spazio disco: ~70-80%
- I/O più veloce (meno byte da leggere)
- Trasparente (decompressione automatica)

**Esempio**:
```
Raw JSON:  245 KB
Gzipped:    48 KB  (80% riduzione)
```

---

## Manutenzione Cache

### Pulizia Manuale

```bash
# Cancella cache specifica
rm -rf cache/web/SITE/2025-12*.json.gz

# Cancella tutta la cache web
rm -rf cache/web/

# Cancella cache completa
rm -rf cache/
```

### Invalidazione Automatica

Non implementata. La cache si auto-gestisce tramite:
- TTL per PARTIAL
- Hash check per rilevare modifiche
- SEALED immutabile

---

## Troubleshooting

### Cache non aggiornata

**Sintomo**: Dati vecchi anche dopo TTL scaduto

**Causa**: Hash identico (dati API non cambiati)

**Soluzione**: Normale, significa che l'API non ha nuovi dati

### Cache PARTIAL non diventa SEALED

**Sintomo**: Mese passato ancora PARTIAL

**Causa**: Logica sealing basata su data corrente

**Verifica**:
```python
# In cache_manager.py
def _is_complete_period(date: str) -> bool:
    # Controlla se periodo è completo
```

### Spazio disco

**Sintomo**: Cache occupa troppo spazio

**Soluzione**:
1. Verifica compressione attiva (`.json.gz`)
2. Cancella cache vecchia se necessario
3. Considera retention policy per cache antica

---

## Integrazione con Flows

### API Flow

```python
# Usa cache mensile per endpoint
data = cache.get_or_fetch(
    source="api_ufficiali",
    endpoint="site_energy_details",
    date="2025-12",
    fetch_func=lambda: collector.fetch_endpoint(...)
)
```

### Web Flow

```python
# SITE: cache mensile con aggregazione
data = cache.get_or_fetch(
    source="web",
    endpoint="SITE",
    date="2025-12",
    fetch_func=lambda: collector.fetch_measurements(...)
)

# Altri device: cache giornaliera
data = cache.get_or_fetch(
    source="web",
    endpoint="OPTIMIZER",
    date="2025-12-02",
    fetch_func=lambda: collector.fetch_measurements(...)
)
```

### GME Flow

```python
# Cache giornaliera per prezzi energia
data = cache.get_or_fetch(
    source="gme",
    endpoint="",
    date="2025-12-02",
    fetch_func=lambda: collector.fetch_prices(...)
)
```

---

## Best Practices

1. **Non bypassare la cache**: Usa sempre `get_or_fetch()` invece di chiamare direttamente l'API
2. **Rispetta la granularità**: Usa date mensili per SITE, giornaliere per altri
3. **Non modificare file cache manualmente**: Usa i metodi del CacheManager
4. **Monitora statistiche**: Verifica cache hit rate per ottimizzare TTL
5. **Backup cache importante**: SEALED files sono preziosi (dati storici completi)

---

## Riferimenti

- **Implementazione**: `cache/cache_manager.py`
- **Configurazione TTL**: `cache/cache_manager.py` (TTL_CONFIG)
- **Aggregazione SITE**: `collector/collector_web.py` (_aggregate_site_to_daily)
- **Query Grafana**: `docs/query_grafana_reference.md`
