# SolarEdge Web Endpoints - Riferimento Completo per Query Grafana

## Panoramica

Questo documento analizza tutti gli endpoint web scraping disponibili nel sistema SolarEdge Data Collector per la costruzione di query Grafana precise. I dati vengono salvati in InfluxDB nella measurement `web` con diversi field types basati sulla categoria del dispositivo.

## Struttura Dati InfluxDB

### Measurement: `web`
- **Field Types** (basati su categoria):
  - `Energy` (float): Valori di energia (Wh, kWh)
  - `Power` (float): Valori di potenza (W, kW)
  - `Voltage` (float): Valori di tensione (V)
  - `Current` (float): Valori di corrente (A)
  - `Temperature` (float): Valori di temperatura (°C)
  - `Info` (string/float): Informazioni generiche e metriche varie

### Tags Comuni
- `endpoint`: Tipo di measurement (es: "Energy", "Power", "Voltage", "Temperature")
- `device_id`: ID dispositivo specifico (es: "7F123456", "400123456", "weather_default")
- `unit`: Unità di misura (es: "W", "Wh", "V", "A", "°C")

---

## INVERTER ENDPOINTS

### Device Type: `INVERTER`
**Device ID Pattern**: Numero seriale inverter (es: "7F123456")

#### Metriche Disponibili

| Endpoint (measurementType) | Field Type | Unit | Descrizione |
|----------------------------|------------|------|-------------|
| `Energy` | `Energy` | Wh | **Energia prodotta totale** - Contatore crescente |
| `Power` | `Power` | W | **Potenza istantanea** - Produzione corrente |
| `Voltage` | `Voltage` | V | Tensione AC inverter |
| `Current` | `Current` | A | Corrente AC inverter |
| `Temperature` | `Temperature` | °C | Temperatura interna inverter |

#### Query Pattern Inverter
```flux
// Potenza inverter istantanea
from(bucket: "Solaredge")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "web")
  |> filter(fn: (r) => r["_field"] == "Power")
  |> filter(fn: (r) => r["endpoint"] == "Power")
  |> filter(fn: (r) => r["device_id"] == "7F123456")  // Sostituire con serial inverter
  |> aggregateWindow(every: 5m, fn: mean)
```

```flux
// Energia prodotta oggi dall'inverter
from(bucket: "Solaredge")
  |> range(start: today_start)
  |> filter(fn: (r) => r["_measurement"] == "web")
  |> filter(fn: (r) => r["_field"] == "Energy")
  |> filter(fn: (r) => r["endpoint"] == "Energy")
  |> filter(fn: (r) => r["device_id"] == "7F123456")
  |> reduce(fn: (r, accumulator) => ({
      first: if accumulator.count == 0 then r._value else accumulator.first,
      last: r._value,
      count: accumulator.count + 1
    }))
  |> map(fn: (r) => ({ _value: (r.last - r.first) / 1000.0 }))  // Converti in kWh
```

---

## OPTIMIZER ENDPOINTS

### Device Type: `OPTIMIZER`
**Device ID Pattern**: Numero seriale optimizer (es: "0123456789AB")

#### Metriche Disponibili

| Endpoint (measurementType) | Field Type | Unit | Descrizione |
|----------------------------|------------|------|-------------|
| `Power` | `Power` | W | **Potenza DC optimizer** - Produzione singolo pannello |
| `Voltage` | `Voltage` | V | Tensione DC optimizer |
| `Current` | `Current` | A | Corrente DC optimizer |
| `Temperature` | `Temperature` | °C | Temperatura optimizer |

#### Query Pattern Optimizer
```flux
// Potenza di tutti gli optimizer
from(bucket: "Solaredge")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "web")
  |> filter(fn: (r) => r["_field"] == "Power")
  |> filter(fn: (r) => r["endpoint"] == "Power")
  |> filter(fn: (r) => r["device_id"] =~ /^[0-9A-F]{12}$/)  // Pattern optimizer
  |> aggregateWindow(every: 5m, fn: mean)
```

```flux
// Optimizer con potenza più bassa (possibile problema)
from(bucket: "Solaredge")
  |> range(start: -15m)
  |> filter(fn: (r) => r["_measurement"] == "web")
  |> filter(fn: (r) => r["_field"] == "Power")
  |> filter(fn: (r) => r["endpoint"] == "Power")
  |> filter(fn: (r) => r["device_id"] =~ /^[0-9A-F]{12}$/)
  |> group(columns: ["device_id"])
  |> mean()
  |> group()
  |> sort(columns: ["_value"], desc: false)
  |> limit(n: 5)
```

```flux
// Temperatura massima tra optimizer
from(bucket: "Solaredge")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "web")
  |> filter(fn: (r) => r["_field"] == "Temperature")
  |> filter(fn: (r) => r["endpoint"] == "Temperature")
  |> filter(fn: (r) => r["device_id"] =~ /^[0-9A-F]{12}$/)
  |> group(columns: ["device_id"])
  |> max()
  |> group()
  |> max()
```

---

## METER ENDPOINTS (Contatori)

### Device Type: `METER`
**Device ID Pattern**: Numero ID meter (es: "400123456")

#### Metriche Disponibili

| Endpoint (measurementType) | Field Type | Unit | Descrizione |
|----------------------------|------------|------|-------------|
| `Power` | `Power` | W | **Potenza netta verso/dalla rete** - Positiva=immissione, Negativa=prelievo |
| `Voltage` | `Voltage` | V | Tensione rete |
| `Current` | `Current` | A | Corrente rete |
| `Frequency` | `Info` | Hz | Frequenza rete |
| `PowerFactor` | `Info` | - | Fattore di potenza |

#### Query Pattern Meter
```flux
// Potenza netta rete (positiva=immissione, negativa=prelievo)
from(bucket: "Solaredge")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "web")
  |> filter(fn: (r) => r["_field"] == "Power")
  |> filter(fn: (r) => r["endpoint"] == "Power")
  |> filter(fn: (r) => r["device_id"] == "400123456")  // Sostituire con ID meter
  |> aggregateWindow(every: 5m, fn: mean)
```

```flux
// Tensione rete
from(bucket: "Solaredge")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "web")
  |> filter(fn: (r) => r["_field"] == "Voltage")
  |> filter(fn: (r) => r["endpoint"] == "Voltage")
  |> filter(fn: (r) => r["device_id"] == "400123456")
  |> aggregateWindow(every: 5m, fn: mean)
```

---

## BATTERY ENDPOINTS

### Device Type: `BATTERY`
**Device ID Pattern**: Numero seriale batteria

#### Metriche Disponibili

| Endpoint (measurementType) | Field Type | Unit | Descrizione |
|----------------------------|------------|------|-------------|
| `Power` | `Power` | W | **Potenza batteria** - Positiva=carica, Negativa=scarica |
| `StateOfCharge` | `Info` | % | Stato di carica batteria |
| `Voltage` | `Voltage` | V | Tensione batteria |
| `Current` | `Current` | A | Corrente batteria |
| `Temperature` | `Temperature` | °C | Temperatura batteria |

#### Query Pattern Battery
```flux
// Stato di carica batteria
from(bucket: "Solaredge")
  |> range(start: -24h)
  |> filter(fn: (r) => r["_measurement"] == "web")
  |> filter(fn: (r) => r["_field"] == "Info")
  |> filter(fn: (r) => r["endpoint"] == "StateOfCharge")
  |> aggregateWindow(every: 15m, fn: mean)
```

```flux
// Potenza batteria (positiva=carica, negativa=scarica)
from(bucket: "Solaredge")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "web")
  |> filter(fn: (r) => r["_field"] == "Power")
  |> filter(fn: (r) => r["endpoint"] == "Power")
  |> filter(fn: (r) => r["device_id"] =~ /BAT/)  // Pattern batteria
  |> aggregateWindow(every: 5m, fn: mean)
```

---

## STRING ENDPOINTS (Stringhe DC)

### Device Type: `STRING`
**Device ID Pattern**: ID stringa (es: "1", "2")

#### Metriche Disponibili

| Endpoint (measurementType) | Field Type | Unit | Descrizione |
|----------------------------|------------|------|-------------|
| `Power` | `Power` | W | Potenza DC stringa |
| `Voltage` | `Voltage` | V | Tensione DC stringa |
| `Current` | `Current` | A | Corrente DC stringa |

#### Query Pattern String
```flux
// Potenza tutte le stringhe
from(bucket: "Solaredge")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "web")
  |> filter(fn: (r) => r["_field"] == "Power")
  |> filter(fn: (r) => r["endpoint"] == "Power")
  |> filter(fn: (r) => r["device_id"] =~ /^[0-9]+$/)  // Pattern stringa
  |> aggregateWindow(every: 5m, fn: mean)
  |> group(columns: ["device_id"])
```

---

## WEATHER ENDPOINTS

### Device Type: `WEATHER`
**Device ID**: `weather_default`

#### Metriche Disponibili

| Endpoint (measurementType) | Field Type | Unit | Descrizione |
|----------------------------|------------|------|-------------|
| `Temperature` | `Temperature` | °C | Temperatura ambiente |
| `WindSpeed` | `Info` | m/s | Velocità vento |
| `Irradiance` | `Info` | W/m² | Irraggiamento solare |

#### Query Pattern Weather
```flux
// Temperatura ambiente
from(bucket: "Solaredge")
  |> range(start: -24h)
  |> filter(fn: (r) => r["_measurement"] == "web")
  |> filter(fn: (r) => r["_field"] == "Temperature")
  |> filter(fn: (r) => r["endpoint"] == "Temperature")
  |> filter(fn: (r) => r["device_id"] == "weather_default")
  |> aggregateWindow(every: 15m, fn: mean)
```

```flux
// Irraggiamento solare
from(bucket: "Solaredge")
  |> range(start: -24h)
  |> filter(fn: (r) => r["_measurement"] == "web")
  |> filter(fn: (r) => r["_field"] == "Info")
  |> filter(fn: (r) => r["endpoint"] == "Irradiance")
  |> filter(fn: (r) => r["device_id"] == "weather_default")
  |> aggregateWindow(every: 15m, fn: mean)
```

---

## METRICHE CHIAVE PER DASHBOARD

### Produzione Fotovoltaica
- **Istantanea inverter**: `web` → endpoint=`Power`, device_id=inverter_serial
- **Giornaliera inverter**: `web` → endpoint=`Energy`, device_id=inverter_serial (differenza primo/ultimo)
- **Per optimizer**: Somma di tutti gli optimizer con endpoint=`Power`

### Monitoraggio Optimizer
- **Potenza individuale**: Filtrare per `device_id` specifico
- **Optimizer problematici**: Ordinare per potenza crescente e prendere i primi 5
- **Temperatura massima**: Aggregare con `max()` su tutti gli optimizer
- **Distribuzione potenza**: Visualizzare tutti gli optimizer in un grafico

### Qualità Rete (da Meter)
- **Tensione rete**: endpoint=`Voltage`, device_id=meter_id
- **Frequenza**: endpoint=`Frequency`, device_id=meter_id
- **Fattore di potenza**: endpoint=`PowerFactor`, device_id=meter_id

### Batteria (se presente)
- **Stato di carica**: endpoint=`StateOfCharge`
- **Potenza carica/scarica**: endpoint=`Power` (positiva=carica, negativa=scarica)
- **Temperatura**: endpoint=`Temperature`

### Condizioni Ambientali
- **Temperatura ambiente**: device_id=`weather_default`, endpoint=`Temperature`
- **Irraggiamento**: device_id=`weather_default`, endpoint=`Irradiance`
- **Vento**: device_id=`weather_default`, endpoint=`WindSpeed`

---

## CALCOLI DERIVATI

### Efficienza Optimizer
```flux
// Confronto potenza optimizer vs media
avg_power = from(bucket: "Solaredge")
  |> range(start: -15m)
  |> filter(fn: (r) => r["_measurement"] == "web")
  |> filter(fn: (r) => r["_field"] == "Power")
  |> filter(fn: (r) => r["endpoint"] == "Power")
  |> filter(fn: (r) => r["device_id"] =~ /^[0-9A-F]{12}$/)
  |> mean()
  |> group()
  |> mean()

optimizer_power = from(bucket: "Solaredge")
  |> range(start: -15m)
  |> filter(fn: (r) => r["_measurement"] == "web")
  |> filter(fn: (r) => r["_field"] == "Power")
  |> filter(fn: (r) => r["endpoint"] == "Power")
  |> filter(fn: (r) => r["device_id"] =~ /^[0-9A-F]{12}$/)
  |> group(columns: ["device_id"])
  |> mean()

// Calcola deviazione dalla media
join(tables: {opt: optimizer_power, avg: avg_power}, on: ["_time"])
  |> map(fn: (r) => ({
    _time: r._time,
    device_id: r.device_id,
    power: r._value_opt,
    avg_power: r._value_avg,
    deviation_pct: ((r._value_opt - r._value_avg) / r._value_avg) * 100.0
  }))
  |> filter(fn: (r) => r.deviation_pct < -20.0)  // Optimizer con -20% rispetto alla media
```

### Bilancio Energetico con Web Data
```flux
// Produzione inverter
production = from(bucket: "Solaredge")
  |> range(start: -15m)
  |> filter(fn: (r) => r["_measurement"] == "web")
  |> filter(fn: (r) => r["_field"] == "Power")
  |> filter(fn: (r) => r["endpoint"] == "Power")
  |> filter(fn: (r) => r["device_id"] == "7F123456")  // Inverter
  |> mean()
  |> map(fn: (r) => ({ _time: r._time, _value: r._value, _field: "production" }))

// Flusso rete
grid = from(bucket: "Solaredge")
  |> range(start: -15m)
  |> filter(fn: (r) => r["_measurement"] == "web")
  |> filter(fn: (r) => r["_field"] == "Power")
  |> filter(fn: (r) => r["endpoint"] == "Power")
  |> filter(fn: (r) => r["device_id"] == "400123456")  // Meter
  |> mean()
  |> map(fn: (r) => ({ _time: r._time, _value: r._value, _field: "grid" }))

// Calcola consumo
union(tables: [production, grid])
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> map(fn: (r) => ({
    _time: r._time,
    consumo: if r.grid >= 0.0 then r.production - r.grid else r.production + (r.grid * -1.0)
  }))
```

---

## CONVENZIONI NAMING PER QUERY

### Rinominazione Campi Obbligatoria
Tutti i risultati delle query devono essere rinominati con nomi descrittivi.

#### Pattern di Naming:
- **Inverter**: `Inverter_METRICA` (es: `Inverter_Potenza`, `Inverter_Temperatura`)
- **Optimizer**: `Optimizer_SERIAL_METRICA` o `Optimizer_METRICA` per aggregati
- **Meter**: `Rete_METRICA` (es: `Rete_Potenza`, `Rete_Tensione`)
- **Battery**: `Batteria_METRICA` (es: `Batteria_SoC`, `Batteria_Potenza`)
- **Weather**: `Meteo_METRICA` (es: `Meteo_Temperatura`, `Meteo_Irraggiamento`)

---

## NOTE TECNICHE

### Timezone
Tutti i timestamp sono in UTC. Usare sempre:
```flux
import "timezone"
option location = timezone.location(name: "Europe/Rome")
```

### Intervallo Dati
- **Dati web**: Intervallo 15 minuti (sincronizzato con API)
- **Granularità**: Dipende dalla frequenza di scraping configurata

### Device ID
- **Inverter**: Serial number (es: "7F123456")
- **Optimizer**: Serial number 12 caratteri hex (es: "0123456789AB")
- **Meter**: ID numerico (es: "400123456")
- **Weather**: Sempre "weather_default"
- **Battery**: Contiene "BAT" nel serial
- **String**: ID numerico semplice (es: "1", "2")

### Gestione Errori
Alcuni valori possono essere `null`. Usare sempre:
```flux
|> filter(fn: (r) => exists r._value)
```

### Unità di Misura
- **Potenze**: W (convertire in kW dividendo per 1000)
- **Energie**: Wh (convertire in kWh dividendo per 1000)
- **Tensioni**: V
- **Correnti**: A
- **Temperature**: °C
- **Frequenze**: Hz
- **Irraggiamento**: W/m²

### Best Practices
1. **Usare `exists r._value`** per evitare valori null
2. **Filtrare per device_id** quando si lavora con dispositivi specifici
3. **Usare pattern regex** per filtrare gruppi di dispositivi (es: tutti gli optimizer)
4. **Aggregare con `aggregateWindow()`** per ridurre granularità
5. **Per contatori energia**: Usare `reduce()` per calcolare differenza primo/ultimo
6. **Monitorare optimizer**: Confrontare con media per identificare problemi
7. **Combinare con dati realtime**: Per analisi più dettagliate

### Problemi Comuni e Soluzioni

#### Problema: Troppi optimizer da visualizzare
**Soluzione**: Aggregare con `mean()` o `sum()`, oppure filtrare solo quelli problematici

#### Problema: Device ID non trovato
**Causa**: Device ID errato o dispositivo non configurato
**Soluzione**: Verificare configurazione in `config/main.yaml` sezione `web_scraping`

#### Problema: Dati mancanti per alcuni dispositivi
**Causa**: Dispositivo offline o non abilitato in configurazione
**Soluzione**: Verificare stato dispositivo nel portale SolarEdge

#### Problema: Valori negativi inaspettati
**Causa**: Normale per meter (prelievo rete) e battery (scarica)
**Soluzione**: Gestire segno nel calcolo: positivo=immissione/carica, negativo=prelievo/scarica

#### Problema: Differenza tra web e API
**Causa**: Fonti dati diverse, web può avere granularità diversa
**Soluzione**: Preferire API per dati ufficiali, web per dettagli optimizer e dispositivi specifici
