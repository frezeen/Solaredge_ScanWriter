# SolarEdge API Endpoints - Riferimento Completo per Query Grafana

## Panoramica

Questo documento analizza tutti gli endpoint API ufficiali SolarEdge abilitati nel nostro sistema per la costruzione di query Grafana precise. Tutte le informazioni sono basate sulla documentazione ufficiale SolarEdge API.

## Struttura Dati InfluxDB

### Measurement: `api`

- **Field Types** (basati su categoria endpoint):
  - `Inverter` (float): Dati inverter - produzione energia/potenza, telemetria equipment
  - `Meter` (float): Dati meter - energia/potenza dettagliata per produzione, consumo, import/export
  - `Flusso` (string): Power flow - JSON con flussi energetici correnti
  - `Info` (string): Metadati - JSON con informazioni sito, equipment, sensori

### Tags Comuni

- `endpoint`: Nome endpoint API
- `metric`: Tipo di meter o metrica specifica
- `unit`: Unità di misura

### Note Importanti

- **Unità salvate**: Valori nelle unità originali API (Wh per energie, W per potenze)
- **Valori per intervallo**: Energy/Power details sono valori per intervallo temporale, NON contatori crescenti
- **Conversioni**: Per kWh, dividere Wh per 1000

---

## ENDPOINT METER (Energie e Potenze Dettagliate)

### site_energy_details

**URL**: `/site/{siteId}/energyDetails`  
**Descrizione**: Misurazioni energia dettagliate da meters (produzione, consumo, autoconsumo, export, import)  
**Category**: `Meter`  
**Unit**: `Wh`  
**Risoluzione**: Configurabile (QUARTER_OF_AN_HOUR, HOUR, DAY, WEEK, MONTH, YEAR)  
**Limitazioni API**:

- 1 anno max con risoluzione DAY
- 1 mese max con risoluzione QUARTER_OF_AN_HOUR o HOUR
- Nessun limite per WEEK, MONTH, YEAR

**IMPORTANTE**: I valori sono energia per intervallo temporale, NON contatori crescenti.

**Meters disponibili** (valori metric nel database):

- `Production`: Energia prodotta
- `Consumption`: Energia consumata
- `SelfConsumption`: Energia autoconsumata (meter virtuale calcolato)
- `FeedIn`: Energia esportata alla rete
- `Purchased`: Energia importata dalla rete

**Nota**: Nella richiesta API si usano nomi maiuscoli (PRODUCTION, CONSUMPTION), ma nella risposta e nel database sono salvati con prima lettera maiuscola.

**Query Grafana**:

```flux
// Produzione giornaliera (somma intervalli del giorno)
import "timezone"
option location = timezone.location(name: "Europe/Rome")

from(bucket: "Solaredge")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "api")
  |> filter(fn: (r) => r["_field"] == "Meter")
  |> filter(fn: (r) => r["endpoint"] == "site_energy_details")
  |> filter(fn: (r) => r["metric"] == "Production")
  |> filter(fn: (r) => exists r._value)
  |> aggregateWindow(every: 1d, fn: sum, createEmpty: false)
  |> map(fn: (r) => ({ r with _field: "Produzione_Wh" }))
  |> keep(columns: ["_time", "_value", "_field"])
```

---

### site_power_details

**URL**: `/site/{siteId}/powerDetails`  
**Descrizione**: Misurazioni potenza dettagliate da meters con risoluzione 15 minuti  
**Category**: `Meter`  
**Unit**: `W`  
**Risoluzione**: Fissa a QUARTER_OF_AN_HOUR (15 minuti)  
**Limitazioni API**: 1 mese max

**Meters disponibili** (valori metric nel database):

- `Production`: Potenza prodotta (AC production power meter/inverter)
- `Consumption`: Potenza consumata
- `SelfConsumption`: Potenza autoconsumata (meter virtuale calcolato)
- `FeedIn`: Potenza esportata alla rete
- `Purchased`: Potenza importata dalla rete

**Query Grafana**:

```flux
// Potenza produzione media ultima ora
from(bucket: "Solaredge")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "api")
  |> filter(fn: (r) => r["_field"] == "Meter")
  |> filter(fn: (r) => r["endpoint"] == "site_power_details")
  |> filter(fn: (r) => r["metric"] == "Production")
  |> aggregateWindow(every: 5m, fn: mean)
```

---

## ENDPOINT INVERTER (Produzione ed Equipment)

### site_energy_day / site_energy_hour / site_energy_quarter

**URL**: `/site/{siteId}/energy`  
**Descrizione**: Energia prodotta con diverse risoluzioni temporali (come mostrato nel Site Dashboard)  
**Category**: `Inverter`  
**Unit**: `Wh`  
**Parametro timeUnit**: DAY, HOUR, QUARTER_OF_AN_HOUR  
**Limitazioni API**:

- DAY: max 1 anno
- HOUR o QUARTER_OF_AN_HOUR: max 1 mese

**Nota**: Questi endpoint forniscono solo produzione aggregata, senza distinzione tra meter types.

---

### site_timeframe_energy

**URL**: `/site/{siteId}/timeFrameEnergy`  
**Descrizione**: Energia totale prodotta per l'anno corrente (lifetime energy)  
**Category**: `Inverter`  
**Unit**: `Wh`  
**Parametri**: startDate e endDate (tipicamente anno corrente)

**Risposta**: Singolo valore aggregato di energia prodotta dal sistema fotovoltaico.

---

### equipment_data

**URL**: `/equipment/{siteId}/{serialNumber}/data`  
**Descrizione**: Dati telemetrici dettagliati dall'inverter per un periodo specifico  
**Category**: `Inverter`  
**Limitazioni API**: Max 1 settimana (7 giorni)

**Dati inclusi**: Parametri tecnici di performance (tensione AC/DC, corrente, frequenza, potenza attiva/reattiva/apparente, fattore di potenza, temperatura, modalità operative). Include versione software e tipo inverter (1ph/3ph). Dati divisi per fase dove applicabile.

**Metriche principali**:

- `totalActivePower` (W): Potenza attiva totale
- `dcVoltage` (V): Tensione DC dai pannelli
- `groundFaultResistance` (Ω): Resistenza guasto a terra
- `powerLimit` (%): Limite potenza applicato
- `totalEnergy` (Wh): Energia lifetime
- `temperature` (°C): Temperatura inverter
- `inverterMode`: Modalità operativa (MPPT, OFF, SLEEPING, FAULT, etc.)
- `operationMode`: 0=On-grid, 1=Off-grid PV/battery, 2=Off-grid con generator

**Metriche per fase (L1Data, L2Data, L3Data)**:

- `acCurrent` (A): Corrente AC
- `acVoltage` (V): Tensione AC
- `acFrequency` (Hz): Frequenza
- `apparentPower` (VA): Potenza apparente (comm board v2.474+)
- `activePower` (W): Potenza attiva (comm board v2.474+)
- `reactivePower` (VAr): Potenza reattiva (comm board v2.474+)
- `cosPhi`: Fattore di potenza

**Tensioni trifase (solo 3ph)**:

- `vL1To2`, `vL2To3`, `vL3To1` (V): Tensioni linea-linea

**Tensioni monofase (solo 1ph)**:

- `vL1ToN`, `vL2ToN` (V): Tensioni linea-neutro

**Query Grafana**:

```flux
// Temperatura inverter
from(bucket: "Solaredge")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "api")
  |> filter(fn: (r) => r["_field"] == "Inverter")
  |> filter(fn: (r) => r["endpoint"] == "equipment_data")
  |> filter(fn: (r) => r["metric"] == "temperature")
  |> aggregateWindow(every: 15m, fn: mean)
```

---

## ENDPOINT FLUSSO (Power Flow)

### site_power_flow

**URL**: `/site/{siteId}/currentPowerFlow`  
**Descrizione**: Flusso energetico corrente del sito (snapshot istantaneo)  
**Category**: `Flusso`  
**Data Format**: JSON string

**Contiene**: Snapshot corrente dei flussi energetici tra PV, GRID, LOAD, STORAGE con informazioni su connessioni ed elementi.

---

## ENDPOINT INFO (Metadati)

### site_details

**URL**: `/site/{siteId}/details`  
**Descrizione**: Dettagli completi del sito fotovoltaico  
**Category**: `Info`  
**Data Format**: JSON string

**Contiene**: Nome, posizione, stato, configurazione, dati installazione, specifiche tecniche, peak power, valuta, date installazione/PTO, note, tipo sito.

---

### site_overview

**URL**: `/site/{siteId}/overview`  
**Descrizione**: Panoramica corrente del sito con metriche chiave  
**Category**: `Info`  
**Data Format**: JSON string

**Contiene**:

- `currentPower`: Potenza istantanea corrente
- `lastDayData`: Energia e revenue giornalieri
- `lastMonthData`: Energia e revenue mensili
- `lastYearData`: Energia e revenue annuali
- `lifeTimeData`: Energia e revenue lifetime
- `lastUpdateTime`: Timestamp ultimo aggiornamento

---

### site_data_period

**URL**: `/site/{siteId}/dataPeriod`  
**Descrizione**: Periodo temporale di produzione energetica del sito  
**Category**: `Info`  
**Data Format**: JSON string

**Contiene**: Date di inizio e fine della raccolta dati (startDate, endDate).

---

### equipment_list

**URL**: `/equipment/{siteId}/list`  
**Descrizione**: Lista inverter e SMI installati  
**Category**: `Info`  
**Data Format**: JSON string

**Contiene**: Nomi, modelli, produttori, numeri seriali di tutti i dispositivi di conversione energia.

---

### site_inventory

**URL**: `/site/{siteId}/inventory`  
**Descrizione**: Inventario completo equipment SolarEdge  
**Category**: `Info`  
**Data Format**: JSON string

**Contiene**: Dettagli su inverter/SMI, batterie, meters, gateways, sensori con serial numbers, modelli, versioni firmware, connessioni.

---

### equipment_change_log

**URL**: `/equipment/{siteId}/{serialNumber}/changeLog`  
**Descrizione**: Registro storico sostituzioni e cambi equipment  
**Category**: `Info`  
**Data Format**: JSON string

**Contiene**: Tutte le modifiche hardware ordinate per data.

---

### site_env_benefits

**URL**: `/site/{siteId}/envBenefits`  
**Descrizione**: Benefici ambientali derivanti dalla produzione energetica  
**Category**: `Info`  
**Data Format**: JSON string

**Contiene**: Emissioni CO2 evitate, alberi equivalenti piantati, impatto ambientale positivo.

---

### site_meters

**URL**: `/site/{siteId}/meters`  
**Descrizione**: Metadati completi dei contatori installati  
**Category**: `Info`  
**Data Format**: JSON string

**Contiene**: Numero seriale, modello, dispositivo connesso, tipo contatore, valori energia lifetime.

---

### site_sensors_list

**URL**: `/equipment/{siteId}/sensors`  
**Descrizione**: Lista sensori installati nel sito  
**Category**: `Info`  
**Data Format**: JSON string

**Contiene**: Sensori di irradianza, temperatura, vento con dettagli su posizione, tipo, dispositivi collegati.

---

### site_storage_data

**URL**: `/site/{siteId}/storageData`  
**Descrizione**: Informazioni dettagliate batterie storage  
**Category**: `Inverter`  
**Data Format**: Structured

**Contiene**: Stato energia, potenza, energia lifetime per batteria. Include serial number, capacità nominale, modello, stato batteria, energia caricata/scaricata lifetime, telemetrie potenza (positiva=carica, negativa=scarica).

**Applicabile solo**: Sistemi con batterie.

---

### sites_list

**URL**: `/sites/list`  
**Descrizione**: Lista completa siti associati all'account API  
**Category**: `Info`  
**Data Format**: JSON string

**Contiene**: Nome, posizione, stato, configurazione, dettagli tecnici di ogni sito. Supporta ricerca, ordinamento, paginazione.

---

### api_version_current / api_versions

**URL**: `/version/current` e `/version/supported`  
**Descrizione**: Informazioni versioni API SolarEdge  
**Category**: `Info`  
**Data Format**: JSON string

**Contiene**: Versione corrente e versioni supportate dell'API.

---

## METRICHE CHIAVE PER DASHBOARD

### Produzione Fotovoltaica

- **Istantanea**: `site_power_details` → field=`Meter`, metric=`Production` (W)
- **Giornaliera**: `site_energy_details` → field=`Meter`, metric=`Production` (somma intervalli)
- **Lifetime**: `site_timeframe_energy` → field=`Inverter` (Wh totali)
- **Overview**: `site_overview` → field=`Info` (JSON con lastDayData, lastMonthData, lifeTimeData)

### Consumi e Bilanci

- **Consumo istantaneo**: `site_power_details` → field=`Meter`, metric=`Consumption` (W)
- **Consumo giornaliero**: `site_energy_details` → field=`Meter`, metric=`Consumption` (somma)
- **Prelievo rete**: `site_energy_details` → field=`Meter`, metric=`Purchased`
- **Immissione rete**: `site_energy_details` → field=`Meter`, metric=`FeedIn`
- **Autoconsumo**: `site_energy_details` → field=`Meter`, metric=`SelfConsumption`

### Performance Inverter

- **Potenza attiva**: `equipment_data` → field=`Inverter`, metric=`totalActivePower`
- **Temperatura**: `equipment_data` → field=`Inverter`, metric=`temperature`
- **Tensione DC**: `equipment_data` → field=`Inverter`, metric=`dcVoltage`
- **Modalità**: `equipment_data` → field=`Inverter`, metric=`inverterMode`

---

## CALCOLI DERIVATI

### Percentuali Energetiche

```flux
import "timezone"
option location = timezone.location(name: "Europe/Rome")

// Recupera energie giornaliere
import_energy = from(bucket: "Solaredge")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "api")
  |> filter(fn: (r) => r["_field"] == "Meter")
  |> filter(fn: (r) => r["endpoint"] == "site_energy_details")
  |> filter(fn: (r) => r["metric"] == "Purchased")
  |> aggregateWindow(every: 1d, fn: sum)
  |> map(fn: (r) => ({ _time: r._time, _value: r._value, _field: "imported" }))

production_energy = from(bucket: "Solaredge")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "api")
  |> filter(fn: (r) => r["_field"] == "Meter")
  |> filter(fn: (r) => r["endpoint"] == "site_energy_details")
  |> filter(fn: (r) => r["metric"] == "Production")
  |> aggregateWindow(every: 1d, fn: sum)
  |> map(fn: (r) => ({ _time: r._time, _value: r._value, _field: "produced" }))

export_energy = from(bucket: "Solaredge")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "api")
  |> filter(fn: (r) => r["_field"] == "Meter")
  |> filter(fn: (r) => r["endpoint"] == "site_energy_details")
  |> filter(fn: (r) => r["metric"] == "FeedIn")
  |> aggregateWindow(every: 1d, fn: sum)
  |> map(fn: (r) => ({ _time: r._time, _value: r._value, _field: "exported" }))

// Calcola percentuali
union(tables: [import_energy, production_energy, export_energy])
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> map(fn: (r) => ({
    _time: r._time,
    autoconsumo: r.produced - r.exported,
    consumo_totale: r.imported + (r.produced - r.exported),
    "Perc_Autoconsumo": ((r.produced - r.exported) / (r.imported + (r.produced - r.exported))) * 100.0,
    "Perc_Prelievo": (r.imported / (r.imported + (r.produced - r.exported))) * 100.0
  }))
```

---

## NOTE TECNICHE

### Timezone

Tutti i timestamp sono nel timezone del sito. Usare sempre:

```flux
import "timezone"
option location = timezone.location(name: "Europe/Rome")
```

### Valori per Intervallo Temporale

I valori di energia e potenza sono per ogni intervallo temporale, NON contatori crescenti. Per calcoli giornalieri usare `sum()`.

### Gestione Errori

Usare sempre `filter(fn: (r) => exists r._value)` per evitare valori null.

### Unità di Misura

- **Energie**: Wh (dividere per 1000 per kWh)
- **Potenze**: W (dividere per 1000 per kW)
- **Tensioni**: V
- **Correnti**: A
- **Temperature**: °C
- **Frequenze**: Hz
- **Potenza apparente**: VA
- **Potenza reattiva**: VAr

### Best Practices

1. Usare `exists r._value` per evitare valori null
2. Per energie giornaliere: `aggregateWindow(every: 1d, fn: sum)`
3. Per potenze medie: `aggregateWindow(every: 5m, fn: mean)`
4. Filtrare sempre per measurement, field, endpoint, metric
5. Per percentuali: usare `union()` + `pivot()`
6. Meters virtuali (SELFCONSUMPTION) sono calcolati, non misurati

### Limitazioni API

- **site_energy_details**: 1 anno (DAY), 1 mese (HOUR/QUARTER)
- **site_power_details**: 1 mese
- **equipment_data**: 1 settimana
- **Daily quota**: 300 richieste per account/site
- **Concurrency**: Max 3 chiamate concurrent dallo stesso IP
