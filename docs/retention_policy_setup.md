# Retention Policy per Measurement Realtime

## Panoramica

Il sistema SolarEdge Data Collector supporta retention policy diverse per i diversi tipi di dati:

- **API e Web**: Retention default del bucket principale (configurabile in InfluxDB)
- **Realtime**: Retention di 2 giorni per ottimizzare lo storage

## Architettura

### Bucket Separati

Il sistema utilizza due bucket InfluxDB:

1. **Bucket Principale** (`INFLUXDB_BUCKET`):

   - Contiene dati API e Web
   - Retention configurabile (default: infinita)
   - Measurements: `api`, `web`

2. **Bucket Realtime** (`INFLUXDB_BUCKET_REALTIME`):
   - Contiene solo dati realtime
   - Retention fissa: 2 giorni (172800 secondi)
   - Measurement: `realtime`

### Routing Automatico

Il `InfluxWriter` determina automaticamente il bucket corretto in base al measurement:

```python
def _get_bucket_for_measurement(self, measurement: str) -> str:
    if measurement == "realtime":
        return self._influx_config.bucket_realtime
    else:
        return self._influx_config.bucket  # API e Web
```

## Configurazione

### Variabili d'Ambiente

Aggiungi al file `.env`:

```bash
# Bucket principale (API/Web)
INFLUXDB_BUCKET=Solaredge

# Bucket realtime (2 giorni retention)
INFLUXDB_BUCKET_REALTIME=Solaredge_Realtime
```

### Installazione Automatica

Per nuove installazioni, lo script `install.sh` crea automaticamente entrambi i bucket.

### Installazioni Esistenti

Per installazioni esistenti, usa lo script di setup:

```bash
# I bucket vengono creati automaticamente durante l'installazione
# Non è necessario eseguire script aggiuntivi
```

Lo script:

1. Verifica la connessione InfluxDB
2. Controlla se il bucket realtime esiste
3. Crea il bucket con retention di 2 giorni
4. Aggiorna il file `.env`

## Utilizzo

### Scrittura Dati

Il sistema gestisce automaticamente il routing:

```python
# Dati realtime → bucket realtime (2 giorni)
writer.write_points(realtime_points, measurement_type="realtime")

# Dati API → bucket principale
writer.write_points(api_points, measurement_type="api")

# Dati Web → bucket principale
writer.write_points(web_points, measurement_type="web")
```

### Query Grafana

Per query che includono dati realtime, specifica il bucket corretto:

```flux
// Dati realtime (ultimi 2 giorni)
from(bucket: "Solaredge_Realtime")
  |> range(start: -2d)
  |> filter(fn: (r) => r._measurement == "realtime")

// Dati storici API/Web
from(bucket: "Solaredge")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "api" or r._measurement == "web")
```

## Vantaggi

### Ottimizzazione Storage

- **Dati realtime**: Eliminazione automatica dopo 2 giorni
- **Dati storici**: Conservazione a lungo termine per analisi
- **Performance**: Query più veloci su dataset ridotti

### Flessibilità

- Retention configurabile per bucket principale
- Possibilità di estendere con altri bucket specializzati
- Compatibilità con installazioni esistenti

## Troubleshooting

### Bucket Non Creato

Se il bucket realtime non viene creato automaticamente:

```bash
# Verifica token InfluxDB
curl -H "Authorization: Token $INFLUXDB_TOKEN" \
     "$INFLUXDB_URL/api/v2/buckets"

# I bucket vengono configurati automaticamente
# Non è necessario setup manuale
```

### Dati nel Bucket Sbagliato

Verifica il measurement type nei log:

```bash
journalctl -u solaredge-scanwriter | grep "bucket"
```

### Retention Non Applicata

Controlla la configurazione del bucket:

```bash
curl -H "Authorization: Token $INFLUXDB_TOKEN" \
     "$INFLUXDB_URL/api/v2/buckets?name=Solaredge_Realtime"
```

## Migrazione

### Da Bucket Singolo

Per migrare da configurazione con bucket singolo:

1. I bucket vengono configurati automaticamente dal sistema
2. Riavvia il servizio: `systemctl restart solaredge-scanwriter`
3. I nuovi dati realtime andranno nel bucket separato
4. I dati esistenti rimangono nel bucket principale

### Backup Dati

Prima della migrazione, considera un backup:

```bash
# Export dati realtime esistenti
influx query 'from(bucket:"Solaredge") |> range(start:-7d) |> filter(fn:(r) => r._measurement == "realtime")' \
  --org "$INFLUXDB_ORG" --token "$INFLUXDB_TOKEN" > realtime_backup.csv
```

## Monitoraggio

### Dimensioni Bucket

Monitora l'utilizzo storage:

```flux
// Dimensione bucket realtime
from(bucket: "_monitoring")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "boltdb_reads_total")
  |> filter(fn: (r) => r.bucket == "Solaredge_Realtime")
```

### Retention Efficace

Verifica che i dati vengano eliminati:

```flux
// Dati più vecchi di 2 giorni (dovrebbero essere vuoti)
from(bucket: "Solaredge_Realtime")
  |> range(start: -7d, stop: -2d)
  |> count()
```
