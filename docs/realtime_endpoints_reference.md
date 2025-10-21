# SolarEdge Realtime Endpoints - Riferimento Completo per Query Grafana

## Panoramica

Questo documento analizza tutti gli endpoint realtime disponibili nel sistema SolarEdge Data Collector per la costruzione di query Grafana precise. I dati vengono salvati in InfluxDB nella measurement `realtime` con diversi field types.

## Struttura Dati InfluxDB

### Measurement: `realtime`
- **Field Types**:
  - `Inverter` (float): Valori numerici dall'inverter
  - `Inverter_Text` (string): Valori testuali dall'inverter
  - `Meter` (float): Valori numerici dai meter
  - `Meter_Text` (string): Valori testuali dai meter
  - `Battery` (float): Valori numerici dalle batterie
  - `Battery_Text` (string): Valori testuali dalle batterie

### Tags Comuni
- `device_id`: Identificativo dispositivo (es: "SE6000H", "Meter 1")
- `endpoint`: Nome metrica (es: "Power", "Import Energy")
- `unit`: Unità di misura (es: "W", "V", "A", "Wh", "°C")

---

## INVERTER ENDPOINTS

### Informazioni Dispositivo
| Endpoint | Field Type | Unità | Tipo Dato | Descrizione |
|----------|------------|-------|-----------|-------------|
| `Manufacturer` | `Inverter_Text` | - | String | Produttore inverter (es: "SolarEdge") |
| `Model` | `Inverter_Text` | - | String | Modello inverter (es: "SE6000H") |
| `Type` | `Inverter_Text` | - | String | Tipo inverter dal SunSpec DID |
| `Version` | `Inverter_Text` | - | String | Versione firmware |
| `Serial` | `Inverter_Text` | - | String | Numero seriale |
| `Status` | `Inverter_Text` | - | String | Stato inverter (es: "I_STATUS_MPPT") |

### Misure Elettriche AC
| Endpoint | Field Type | Unità | Tipo Dato | Descrizione |
|----------|------------|-------|-----------|-------------|
| `Current` | `Inverter` | A | Float | Corrente AC totale |
| `Phase 1 Current` | `Inverter` | A | Float | Corrente fase 1 (solo trifase) |
| `Phase 2 Current` | `Inverter` | A | Float | Corrente fase 2 (solo trifase) |
| `Phase 3 Current` | `Inverter` | A | Float | Corrente fase 3 (solo trifase) |
| `Voltage` | `Inverter` | V | Float | Tensione AC (monofase) |
| `Phase 1 voltage` | `Inverter` | V | Float | Tensione fase 1 (trifase) |
| `Phase 2 voltage` | `Inverter` | V | Float | Tensione fase 2 (trifase) |
| `Phase 3 voltage` | `Inverter` | V | Float | Tensione fase 3 (trifase) |
| `Phase 1-N voltage` | `Inverter` | V | Float | Tensione fase 1-neutro |
| `Phase 2-N voltage` | `Inverter` | V | Float | Tensione fase 2-neutro |
| `Phase 3-N voltage` | `Inverter` | V | Float | Tensione fase 3-neutro |
| `Frequency` | `Inverter` | Hz | Float | Frequenza rete |

### Potenze AC
| Endpoint | Field Type | Unità | Tipo Dato | Descrizione |
|----------|------------|-------|-----------|-------------|
| `Power` | `Inverter` | W | Float | **Potenza AC istantanea** - Principale per produzione |
| `Power (Apparent)` | `Inverter` | VA | Float | Potenza apparente |
| `Power (Reactive)` | `Inverter` | VAr | Float | Potenza reattiva |
| `Power Factor` | `Inverter` | % | Float | Fattore di potenza |

### Energia Totale
| Endpoint | Field Type | Unità | Tipo Dato | Descrizione |
|----------|------------|-------|-----------|-------------|
| `Total Energy` | `Inverter` | Wh | Float | **Energia totale prodotta** - Contatore crescente |

### Misure DC (Pannelli)
| Endpoint | Field Type | Unità | Tipo Dato | Descrizione |
|----------|------------|-------|-----------|-------------|
| `DC Current` | `Inverter` | A | Float | Corrente DC dai pannelli |
| `DC Voltage` | `Inverter` | V | Float | Tensione DC dai pannelli |
| `DC Power` | `Inverter` | W | Float | Potenza DC dai pannelli |

### Temperatura e Diagnostica
| Endpoint | Field Type | Unità | Tipo Dato | Descrizione |
|----------|------------|-------|-----------|-------------|
| `Temperature` | `Inverter` | °C | Float | Temperatura inverter |

---

## METER ENDPOINTS (Contatori Rete)

### Informazioni Dispositivo
| Endpoint | Field Type | Unità | Tipo Dato | Descrizione |
|----------|------------|-------|-----------|-------------|
| `Manufacturer` | `Meter_Text` | - | String | Produttore meter |
| `Model` | `Meter_Text` | - | String | Modello meter |
| `Version` | `Meter_Text` | - | String | Versione firmware |
| `Serial` | `Meter_Text` | - | String | Numero seriale |
| `Option` | `Meter_Text` | - | String | Opzioni configurazione |

### Correnti
| Endpoint | Field Type | Unità | Tipo Dato | Descrizione |
|----------|------------|-------|-----------|-------------|
| `Current` | `Meter` | A | Float | Corrente totale |
| `L1 Current` | `Meter` | A | Float | Corrente fase L1 |
| `L2 Current` | `Meter` | A | Float | Corrente fase L2 |
| `L3 Current` | `Meter` | A | Float | Corrente fase L3 |

### Tensioni
| Endpoint | Field Type | Unità | Tipo Dato | Descrizione |
|----------|------------|-------|-----------|-------------|
| `Voltage L-N` | `Meter` | V | Float | Tensione linea-neutro |
| `L1-N Voltage` | `Meter` | V | Float | Tensione L1-neutro |
| `L2-N Voltage` | `Meter` | V | Float | Tensione L2-neutro |
| `L3-N Voltage` | `Meter` | V | Float | Tensione L3-neutro |
| `Voltage L-L` | `Meter` | V | Float | Tensione linea-linea |
| `L1-L2 Voltage` | `Meter` | V | Float | Tensione L1-L2 |
| `L2-L3 Voltage` | `Meter` | V | Float | Tensione L2-L3 |
| `L3-L1 Voltage` | `Meter` | V | Float | Tensione L3-L1 |

### Frequenza
| Endpoint | Field Type | Unità | Tipo Dato | Descrizione |
|----------|------------|-------|-----------|-------------|
| `Frequency` | `Meter` | Hz | Float | Frequenza rete |

### Potenze Istantanee
| Endpoint | Field Type | Unità | Tipo Dato | Descrizione |
|----------|------------|-------|-----------|-------------|
| `Power` | `Meter` | W | Float | **Potenza netta verso/dalla rete** - Positiva=immissione, Negativa=prelievo |
| `L1 Power` | `Meter` | W | Float | Potenza fase L1 |
| `L2 Power` | `Meter` | W | Float | Potenza fase L2 |
| `L3 Power` | `Meter` | W | Float | Potenza fase L3 |
| `Apparent Power` | `Meter` | VA | Float | Potenza apparente totale |
| `L1 Apparent Power` | `Meter` | VA | Float | Potenza apparente L1 |
| `L2 Apparent Power` | `Meter` | VA | Float | Potenza apparente L2 |
| `L3 Apparent Power` | `Meter` | VA | Float | Potenza apparente L3 |
| `Reactive Power` | `Meter` | VAr | Float | Potenza reattiva totale |
| `L1 Reactive Power` | `Meter` | VAr | Float | Potenza reattiva L1 |
| `L2 Reactive Power` | `Meter` | VAr | Float | Potenza reattiva L2 |
| `L3 Reactive Power` | `Meter` | VAr | Float | Potenza reattiva L3 |

### Fattori di Potenza
| Endpoint | Field Type | Unità | Tipo Dato | Descrizione |
|----------|------------|-------|-----------|-------------|
| `Power Factor` | `Meter` | % | Float | Fattore di potenza totale |
| `L1 Power Factor` | `Meter` | % | Float | Fattore di potenza L1 |
| `L2 Power Factor` | `Meter` | % | Float | Fattore di potenza L2 |
| `L3 Power Factor` | `Meter` | % | Float | Fattore di potenza L3 |

### Energie Attive (PRINCIPALI PER BILANCI)
| Endpoint | Field Type | Unità | Tipo Dato | Descrizione |
|----------|------------|-------|-----------|-------------|
| `Import Energy` | `Meter` | Wh | Float | **Energia importata dalla rete** - Contatore crescente |
| `L1 Import Energy` | `Meter` | Wh | Float | Energia importata L1 |
| `L2 Import Energy` | `Meter` | Wh | Float | Energia importata L2 |
| `L3 Import Energy` | `Meter` | Wh | Float | Energia importata L3 |
| `Export Energy` | `Meter` | Wh | Float | **Energia esportata alla rete** - Contatore crescente |
| `L1 Export Energy` | `Meter` | Wh | Float | Energia esportata L1 |
| `L2 Export Energy` | `Meter` | Wh | Float | Energia esportata L2 |
| `L3 Export Energy` | `Meter` | Wh | Float | Energia esportata L3 |

---

## BATTERY ENDPOINTS

### Informazioni Dispositivo
| Endpoint | Field Type | Unità | Tipo Dato | Descrizione |
|----------|------------|-------|-----------|-------------|
| `Manufacturer` | `Battery_Text` | - | String | Produttore batteria |
| `Model` | `Battery_Text` | - | String | Modello batteria |
| `Version` | `Battery_Text` | - | String | Versione firmware |
| `Serial` | `Battery_Text` | - | String | Numero seriale |

### Metriche Dinamiche
Le batterie hanno metriche variabili che dipendono dal modello. Esempi comuni:
- State of Charge (%)
- Voltage (V)
- Current (A)
- Power (W)
- Temperature (°C)

---

## QUERY PATTERNS PER GRAFANA

### Pattern Base per Contatori Crescenti
```flux
// Per energie cumulative (Import/Export Energy, Total Energy)
from(bucket: "Solaredge")
  |> range(start: today_start)
  |> filter(fn: (r) => r["_measurement"] == "realtime")
  |> filter(fn: (r) => r["_field"] == "Meter" or r["_field"] == "Inverter")
  |> filter(fn: (r) => r["endpoint"] == "NOME_ENDPOINT")
  |> reduce(fn: (r, accumulator) => ({
      first: if accumulator.count == 0 then r._value else accumulator.first,
      last: r._value,
      count: accumulator.count + 1
    }))
  |> map(fn: (r) => ({ _value: (r.last - r.first) / 1000.0 }))
```

### Pattern per Valori Istantanei
```flux
// Per potenze istantanee (Power)
from(bucket: "Solaredge")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "realtime")
  |> filter(fn: (r) => r["_field"] == "Meter" or r["_field"] == "Inverter")
  |> filter(fn: (r) => r["endpoint"] == "Power")
  |> aggregateWindow(every: 5m, fn: mean)
```

### Pattern per Combinare Inverter + Meter (CRITICO)
```flux
// Per calcoli che richiedono sia produzione che flusso rete
inverter_data = from(bucket: "Solaredge")
  |> range(start: today_start)
  |> filter(fn: (r) => r["_measurement"] == "realtime")
  |> filter(fn: (r) => r["_field"] == "Inverter")
  |> filter(fn: (r) => r["endpoint"] == "Power")
  |> filter(fn: (r) => exists r._value)
  |> aggregateWindow(every: 30s, fn: mean, createEmpty: false)

meter_data = from(bucket: "Solaredge")
  |> range(start: today_start)
  |> filter(fn: (r) => r["_measurement"] == "realtime")
  |> filter(fn: (r) => r["_field"] == "Meter")
  |> filter(fn: (r) => r["endpoint"] == "Power")
  |> filter(fn: (r) => exists r._value)
  |> aggregateWindow(every: 30s, fn: mean, createEmpty: false)

// USARE JOIN invece di PIVOT per maggiore affidabilità
join(tables: {inverter: inverter_data, meter: meter_data}, on: ["_time"])
  |> map(fn: (r) => ({
    _time: r._time,
    consumo_reale: if r._value_meter >= 0.0 then r._value_inverter - r._value_meter else r._value_inverter + (r._value_meter * -1.0)
  }))
```

### Pattern per Somme Trifase
```flux
// Per sommare L1 + L2 + L3
from(bucket: "Solaredge")
  |> range(start: -1h)
  |> filter(fn: (r) => r["endpoint"] =~ /L[123] Power/)
  |> aggregateWindow(every: 5m, fn: mean)
  |> group(columns: ["_time"])
  |> sum()
```

---

## METRICHE CHIAVE PER DASHBOARD

### Produzione Fotovoltaica
- **Istantanea**: `Inverter.Power` (W)
- **Giornaliera**: `Inverter.Total Energy` (differenza primo/ultimo)
- **Efficienza**: `Inverter.DC Power` vs `Inverter.Power`

### Consumi e Bilanci
- **Prelievo rete**: `Meter.Import Energy` (differenza primo/ultimo)
- **Immissione rete**: `Meter.Export Energy` (differenza primo/ultimo)
- **Immissione netta**: `Meter.Power` (positivo) = Produzione > Consumo
- **Prelievo netto**: `Meter.Power` (negativo) = Consumo > Produzione
- **Consumo reale**: `Inverter.Power + |Meter.Power|` (quando Meter.Power < 0)
- **Consumo reale**: `Inverter.Power - Meter.Power` (quando Meter.Power > 0)

### Calcoli Derivati Fondamentali

#### Consumo Reale Istantaneo
```
Se Meter.Power >= 0 (immissione):
  Consumo_Reale = Inverter.Power - Meter.Power

Se Meter.Power < 0 (prelievo):
  Consumo_Reale = Inverter.Power + |Meter.Power|
```

#### Logica del Bilancio Energetico
- **Meter.Power**: Misura solo il flusso netto verso/dalla rete
- **Inverter.Power**: Produzione fotovoltaica istantanea
- **Consumo casa**: Non misurato direttamente, va calcolato

#### Esempi Pratici
```
Esempio 1: Produzione 2000W, Consumo casa 1000W
→ Meter.Power = +1000W (immissione)
→ Consumo_Reale = 2000W - 1000W = 1000W

Esempio 2: Produzione 500W, Consumo casa 1500W  
→ Meter.Power = -1000W (prelievo)
→ Consumo_Reale = 500W + 1000W = 1500W
```

### Percentuali Chiave (FORMULE CORRETTE)

#### Definizioni Fondamentali
- **Consumo Totale** = Import Energy + Autoconsumo = Import Energy + (Production - Export)
- **Autoconsumo** = Production - Export Energy (energia autoprodotta e consumata)

#### Formule Percentuali
- **% Prelievo**: `Import Energy / Consumo Totale × 100`
- **% Autoconsumo (del consumo)**: `Autoconsumo / Consumo Totale × 100`
- **% Autoconsumo (della produzione)**: `(Production - Export) / Production × 100`
- **% Autosufficienza**: `Autoconsumo / Consumo Totale × 100` (uguale a % Autoconsumo del consumo)

#### IMPORTANTE: Due Definizioni di % Autoconsumo
1. **% Autoconsumo del CONSUMO**: Quanto del mio consumo è autoprodotto (più utile per l'utente)
2. **% Autoconsumo della PRODUZIONE**: Quanto della mia produzione consumo (utile per ottimizzazione impianto)

**Raccomandazione**: Usare sempre "% Autoconsumo del consumo" per dashboard utente

#### Pattern Union + Pivot per Percentuali
```flux
// Per combinare 3+ contatori di energia
union(tables: [importata, prodotta, esportata])
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> map(fn: (r) => ({
    _time: now(),
    consumo_totale: r.importata + (r.prodotta - r.esportata),
    autoconsumo: r.prodotta - r.esportata,
    "Perc_Prelievo": (r.importata / (r.importata + (r.prodotta - r.esportata))) * 100.0,
    "Perc_Autoconsumo_del_Consumo": ((r.prodotta - r.esportata) / (r.importata + (r.prodotta - r.esportata))) * 100.0,
    "Perc_Autoconsumo_della_Produzione": ((r.prodotta - r.esportata) / r.prodotta) * 100.0
  }))
```

#### Esempi Pratici
```
Scenario: Import=2.45kWh, Production=12.7kWh, Export=9.46kWh
- Autoconsumo = 12.7 - 9.46 = 3.24 kWh
- Consumo Totale = 2.45 + 3.24 = 5.69 kWh
- % Prelievo = 2.45 / 5.69 × 100 = 43.1%
- % Autoconsumo (del consumo) = 3.24 / 5.69 × 100 = 56.9%
- % Autoconsumo (della produzione) = 3.24 / 12.7 × 100 = 25.5%
```

### Qualità Rete
- **Tensioni**: `Meter.L1-N Voltage`, `L2-N Voltage`, `L3-N Voltage`
- **Frequenza**: `Meter.Frequency`
- **Fattore di potenza**: `Meter.Power Factor`

---

## CONVENZIONI NAMING PER QUERY

### Rinominazione Campi Obbligatoria
**IMPORTANTE**: Tutti i risultati delle query devono essere rinominati con nomi descrittivi e comprensibili.

#### Pattern di Naming Raccomandati:
- **Metriche giornaliere**: `METRICA_OGGI` (es: `Prelievo_OGGI`, `Produzione_OGGI`)
- **Picchi/Massimi**: `Picco_Massimo_PERIODO` (es: `Picco_Massimo_OGGI`)
- **Percentuali**: `Percentuale_TIPO` (es: `Percentuale_Autoconsumo`)
- **Valori istantanei**: `METRICA_Istantanea` (es: `Potenza_Istantanea`)

#### Esempi di Rinominazione:
```flux
// CORRETTO - Con rinominazione descrittiva
|> map(fn: (r) => ({
    _time: now(),
    "Picco_Massimo_OGGI": r._value,
    _field: "picco_immissione"
}))

// SBAGLIATO - Campo generico
|> map(fn: (r) => ({
    _time: now(),
    _value: r._value,
    _field: "value"
}))
```

#### Convenzioni Specifiche:
- **Energia**: `Energia_TIPO_PERIODO` (es: `Energia_Importata_OGGI`)
- **Potenza**: `Potenza_TIPO_PERIODO` (es: `Potenza_Massima_OGGI`)
- **Percentuali**: `Perc_TIPO` (es: `Perc_Autoconsumo`, `Perc_Prelievo`)
- **Contatori**: `Contatore_TIPO` (es: `Contatore_Produzione`)

---

## NOTE TECNICHE

### Timezone
Tutti i timestamp sono in UTC. Usare sempre:
```flux
import "timezone"
option location = timezone.location(name: "Europe/Rome")
```

### Contatori Crescenti
I contatori di energia sono sempre crescenti. Per calcoli giornalieri usare sempre differenza primo/ultimo valore.

### Gestione Errori
Alcuni valori possono essere `N/A` o `invalid`. Usare sempre:
```flux
|> filter(fn: (r) => exists r._value)
```

### Frequenza Dati
I dati realtime arrivano ogni 5 secondi. Per performance usare `aggregateWindow()` per ridurre la granularità.

### Problemi Comuni e Soluzioni

#### Problema: "No Data" con PIVOT
**Causa**: Timestamp non perfettamente allineati tra Inverter e Meter
**Soluzione**: Usare `join()` invece di `pivot()` + `aggregateWindow(every: 30s)`

#### Problema: JOIN con più di 2 tabelle
**Causa**: Flux `join()` supporta solo 2 tabelle alla volta
**Errore**: "joins currently must only have two parents"
**Soluzione**: Usare `union()` + `pivot()` per combinare 3+ datasets

#### Problema: Inverter Power = 0 di notte
**Causa**: Normale, nessuna produzione fotovoltaica notturna
**Soluzione**: Per calcoli consumo, filtrare `r._value > 0` dopo il calcolo finale

#### Problema: Calcoli consumo errati
**Causa**: Non considerare la direzione del flusso meter
**Soluzione**: Sempre usare la formula condizionale:
```flux
consumo_reale = if meter >= 0.0 then produzione - meter else produzione + |meter|
```

#### Problema: % Autoconsumo confusa
**Causa**: Esistono due definizioni diverse di "% autoconsumo"
**Soluzione**: Specificare sempre se è "del consumo" o "della produzione"
- **Del consumo**: `Autoconsumo / Consumo Totale × 100` (più utile per utente)
- **Della produzione**: `Autoconsumo / Produzione × 100` (più utile per tecnici)

### Unità di Misura
Mantenere sempre le unità originali senza conversioni:
- **Potenze**: W (Watt)
- **Energie**: Wh (Watt-ora)
- **Tensioni**: V (Volt)
- **Correnti**: A (Ampere)

### Best Practices Operative
1. **Sempre usare `exists r._value`** per evitare valori null
2. **Per 2 datasets**: Preferire `join()` a `pivot()`
3. **Per 3+ datasets**: Usare `union()` + `pivot()` invece di join multipli
4. **Usare `aggregateWindow(every: 30s)`** per sincronizzare timestamp
5. **Filtrare risultati finali** con `> 0` per valori sensati
6. **Testare sempre con range estesi** (-3d) se oggi non ha dati sufficienti
7. **Evitare parole riservate** (`import`, `export`) come nomi di tabelle nel join