# Query Grafana Flux - Guida di Riferimento e Ottimizzazione

## Indice
1. [Migrazione da API a Site](#migrazione-da-api-a-site)
2. [Gestione Timezone e Aggregazioni Mensili](#gestione-timezone-e-aggregazioni-mensili)
3. [Tecniche di Ottimizzazione Generali](#tecniche-di-ottimizzazione-generali)
4. [Pattern per Query con Delta (primo/ultimo)](#pattern-per-query-con-delta)
5. [Query con Join e PUN](#query-con-join-e-pun)
6. [Output e Naming](#output-e-naming)
7. [Errori Comuni da Evitare](#errori-comuni-da-evitare)
8. [Checklist Finale](#checklist-finale)

---

## Migrazione da API a Site

### Problema Originale
Le query utilizzavano dati da `_measurement == "api"` e `_field == "Meter"` con endpoint come `site_energy_details` e metriche come `Consumption`, `Production`, `FeedIn`, `Purchased`.

### Soluzione
Migrare a `_measurement == "web"` e `_field == "Site"` con nuovi endpoint:

| Vecchio | Nuovo |
|---------|-------|
| `metric == "Production"` | `endpoint == "PRODUCTION_ENERGY"` |
| `metric == "Purchased"` / `Import` | `endpoint == "IMPORT_ENERGY"` |
| `metric == "FeedIn"` / `Export` | `endpoint == "EXPORT_ENERGY"` |
| `metric == "Consumption"` | Calcolato: `PRODUCTION + IMPORT - EXPORT` |

**Formula Consumo**: `consumo = produzione + prelievo - immissione`

### Esempio Prima/Dopo

**PRIMA:**
```flux
from(bucket: "Solaredge")
  |> filter(fn: (r) => r._measurement == "api" and r._field == "Meter")
  |> filter(fn: (r) => r.endpoint == "site_energy_details")
  |> filter(fn: (r) => r.metric == "Consumption")
```

**DOPO:**
```flux
from(bucket: "Solaredge")
  |> filter(fn: (r) => 
      r._measurement == "web" and 
      r._field == "Site" and
      (r.endpoint == "PRODUCTION_ENERGY" or 
       r.endpoint == "IMPORT_ENERGY" or 
       r.endpoint == "EXPORT_ENERGY")
  )
  |> pivot(rowKey: ["_time"], columnKey: ["endpoint"], valueColumn: "_value")
  |> map(fn: (r) => ({
      consumo: r.PRODUCTION_ENERGY + r.IMPORT_ENERGY - r.EXPORT_ENERGY
  }))
```

---

## Gestione Timezone e Aggregazioni Mensili

### Problema Critico
Con `aggregateWindow(every: 1mo)` i dati si spostano di un mese se non gestito correttamente il timezone.

### Soluzione Verificata
```flux
import "timezone"

option location = timezone.location(name: "Europe/Rome")

from(bucket: "Solaredge")
  |> range(start: 0)
  |> aggregateWindow(
      every: 1mo, 
      fn: sum, 
      location: location,      // FONDAMENTALE
      timeSrc: "_start"         // FONDAMENTALE
  )
```

**IMPORTANTE:**
- `location: location` → usa fuso orario italiano per i confini dei mesi
- `timeSrc: "_start"` → usa l'inizio della finestra temporale
- Senza questi parametri i dati slittano di 1 mese

### Verifica Corretta
I timestamp devono essere: `01/12/2024`, `01/01/2025`, `01/02/2025`, ecc.
Se vedi date sbagliate → manca `location` o `timeSrc`

---

## Tecniche di Ottimizzazione Generali

### 1. Accorpamento Filter
**EVITA:**
```flux
|> filter(fn: (r) => r._measurement == "realtime")
|> filter(fn: (r) => r._field == "Meter")
|> filter(fn: (r) => r.endpoint == "Import Energy Active")
|> filter(fn: (r) => exists r._value)
```

**PREFERISCI:**
```flux
|> filter(fn: (r) =>
    r._measurement == "realtime" and
    r._field == "Meter" and
    r.endpoint == "Import Energy Active" and
    exists r._value)
```

### 2. Semplificazione sum()
**EVITA:**
```flux
|> sum(column: "_value")
```

**PREFERISCI:**
```flux
|> sum()
```

### 3. Rimozione Import Inutilizzati
Se `timezone` è dichiarato ma non usato → rimuovilo.
**ECCEZIONE:** Se `option location` è presente, timezone DEVE rimanere anche se sembra inutilizzato.

### 4. Eliminazione Variabili Intermedie
**EVITA:**
```flux
prod = r.PRODUCTION_ENERGY
imp = r.IMPORT_ENERGY
exp = r.EXPORT_ENERGY
consumo = prod + imp - exp

return {
    _value: consumo
}
```

**PREFERISCI:**
```flux
return {
    _value: r.PRODUCTION_ENERGY + r.IMPORT_ENERGY - r.EXPORT_ENERGY
}
```

### 5. Rimozione createEmpty: false

**⚠️ ATTENZIONE - REGOLA CRITICA:**

`createEmpty: false` può essere rimosso **SOLO** se `range()` non ha parametro `stop`.

**✅ SICURO (può essere rimosso):**
```flux
|> range(start: today_start)  // NO stop parameter
|> aggregateWindow(every: 1m, fn: mean)  // OK senza createEmpty: false
```

**❌ NECESSARIO (NON rimuovere):**
```flux
|> range(start: yesterday_start, stop: yesterday_end)  // HA stop parameter
|> aggregateWindow(every: 1m, fn: mean, createEmpty: false)  // OBBLIGATORIO
```

**Motivo:** Quando specifichi un range chiuso con `stop`, Grafana/InfluxDB richiede `createEmpty: false` esplicito per evitare record vuoti ai bordi del range temporale. Rimuoverlo causa il fallimento della query in Grafana.

**Testato e confermato:** 01/12/2025

---

## Pattern per Query con Delta (primo/ultimo)

### Caso d'Uso
Calcolare energia giornaliera come differenza tra ultimo e primo valore (contatori cumulativi).

### Pattern Ottimizzato
```flux
import "date"
import "array"
import "timezone"

option location = timezone.location(name: "Europe/Rome")

start = date.truncate(t: now(), unit: 1d)

data = from(bucket: "Solaredge_Realtime")
  |> range(start: start)
  |> filter(fn: (r) =>
      r._measurement == "realtime" and
      r._field == "Meter" and
      r.endpoint == "Import Energy Active" and
      exists r._value)

// Calcolo diretto senza variabili intermedie
prelievo_wh = (data |> last() |> findRecord(fn: (key) => true, idx: 0))._value - 
              (data |> first() |> findRecord(fn: (key) => true, idx: 0))._value

array.from(rows: [{
  _time: now(),
  "Prelievo Oggi (Wh)": prelievo_wh
}])
```

### IMPORTANTE - Filter exists
Il `filter(fn: (r) => exists r._value)` è **FONDAMENTALE** per first/last.
Senza questo filtro, first/last potrebbero prendere valori null e causare calcoli errati.

**Verificato:** Rimuoverlo cambia i risultati (da 100% a 41.3% nell'esempio % Prelievo).

### IMPORTANTE - option location
Anche se sembra non usato, `option location` influenza `date.truncate()` e definisce quando inizia "oggi" (mezzanotte italiana vs UTC).

**Verificato:** Rimuoverlo cambia i risultati da 100% a 41.3%.

---

## Query con Join e PUN

### Pattern Base
```flux
import "date"
import "join"
import "timezone"

option location = timezone.location(name: "Europe/Rome")

// 1. Consumo mensile
consumo = from(bucket: "Solaredge")
  |> range(start: 0)
  |> filter(fn: (r) => 
      r._measurement == "web" and 
      r._field == "Site" and
      (r.endpoint == "PRODUCTION_ENERGY" or 
       r.endpoint == "IMPORT_ENERGY" or 
       r.endpoint == "EXPORT_ENERGY")
  )
  |> aggregateWindow(every: 1mo, fn: sum, location: location, timeSrc: "_start")
  |> pivot(rowKey: ["_time"], columnKey: ["endpoint"], valueColumn: "_value")
  |> map(fn: (r) => ({
      _time: r._time,
      year: string(v: date.year(t: r._time)),
      month: string(v: date.month(t: r._time)),
      consumo_wh: r.PRODUCTION_ENERGY + r.IMPORT_ENERGY - r.EXPORT_ENERGY
  }))
  |> group()

// 2. PUN mensile
pun = from(bucket: "GME")
  |> range(start: 0)
  |> filter(fn: (r) => r._measurement == "gme_monthly_avg" and r._field == "pun_kwh_avg")
  |> map(fn: (r) => ({
      _time: r._time,
      year: r.year,
      month: string(v: date.month(t: r._time)),
      pun: r._value
  }))
  |> group()

// 3. Join
join.inner(
  left: consumo,
  right: pun,
  on: (l, r) => l.year == r.year and l.month == r.month,
  as: (l, r) => ({
    _time: l._time,
    _value: (l.consumo_wh / 1000.0) * r.pun
  })
)
  |> sum()
  |> map(fn: (r) => ({"Spesa Senza Fotovoltaico": r._value}))
```

### Punti Critici Join

1. **group() è NECESSARIO** prima del join
   - Rimuoverlo causa "no data"
   - Anche se sembra ridondante, va mantenuto

2. **Conversione Wh → kWh**
   - I dati Site sono in Wh
   - PUN è in €/kWh
   - Dividere per 1000: `(wh / 1000.0) * pun`

3. **Bug Consumo /1000**
   - Solo il campo Consumo calcolato necessita `/1000` extra
   - Produzione, Prelievo, Immissione → OK così
   - Consumo → dividere per 1000
   - **Motivo:** Bug di visualizzazione Grafana (17.29 GWh invece di MWh)

### Verifica Manuale Join
Prima di usare `sum()`, testare con dettagli:
```flux
join.inner(...)
  |> filter(fn: (r) => r.anno == "2025")  // Test anno specifico
```
Verificare che consumo_kwh × pun_eur = costo calcolato

---

## Output e Naming

### Naming Colonne
**EVITA `_field` se non necessario:**
```flux
// EVITA (ridondante)
array.from(rows: [{
  _time: now(),
  _field: "percentuale_prelievo",
  _value: perc
}])

// PREFERISCI (nome descrittivo)
array.from(rows: [{
  _time: now(),
  "% Prelievo OGGI": perc
}])
```

### Convenzioni Nomi
- Percentuali: `"% Nome OGGI"`
- Energie: `"Nome Oggi (Wh)"`
- Costi: `"Spesa/Costo Nome (€)"`
- PUN: `"PUN (€/kWh)"`

### Rimozione yield
`|> yield(name: "...")` non è necessario, rimuovilo:
```flux
// EVITA
array.from(...)
  |> yield(name: "risultato")

// PREFERISCI
array.from(...)
```

---

## Errori Comuni da Evitare

### 1. Pivot con rowKey Vuoto
**ERRORE:**
```flux
|> pivot(rowKey: [], columnKey: ["endpoint"], valueColumn: "_value")
```
Causa bug nel calcolo Consumo (moltiplicazione x1000 invece di somma).

**SOLUZIONE:**
```flux
// Usa _time o altra colonna esistente
|> pivot(rowKey: ["_time"], columnKey: ["endpoint"], valueColumn: "_value")

// O crea colonna dummy
|> map(fn: (r) => ({r with dummy: "total"}))
|> pivot(rowKey: ["dummy"], columnKey: ["endpoint"], valueColumn: "_value")
```

### 2. Tentare di Ottimizzare group()
Se `group()` appare dopo un join, **NON TOCCARLO**.
Rimuoverlo causa "no data".

### 3. Rimuovere option location
Anche se sembra inutilizzato, influenza `date.truncate()`.
Non rimuoverlo a meno di test specifici.

### 4. Range con Date Fisse
**EVITA:**
```flux
|> range(start: 2021-09-01T00:00:00Z)
```

**PREFERISCI:**
```flux
|> range(start: 0)  // Per dati storici completi
```

Usare date fisse solo per testing.

---

## Checklist Finale

### Query Mensili con Site
- [ ] Usa `_measurement == "web"` e `_field == "Site"`
- [ ] Endpoint corretti: `PRODUCTION_ENERGY`, `IMPORT_ENERGY`, `EXPORT_ENERGY`
- [ ] `aggregateWindow` con `location: location` e `timeSrc: "_start"`
- [ ] Import `timezone` presente
- [ ] `option location = timezone.location(name: "Europe/Rome")`
- [ ] Consumo calcolato: `prod + imp - exp`
- [ ] Se c'è join, verificare che `group()` sia presente
- [ ] Range: `start: 0` per dati completi

### Query Giornaliere Realtime
- [ ] `filter` accorpato con `and`
- [ ] `exists r._value` incluso nel filter
- [ ] `option location` presente (influenza date.truncate)
- [ ] Variabili `first_*` e `last_*` eliminate
- [ ] Calcolo delta diretto
- [ ] Output con nome descrittivo (senza `_field`)
- [ ] `array.from` senza `yield`

### Query con Join/PUN
- [ ] `group()` presente dopo map di consumo
- [ ] `group()` presente dopo map di PUN
- [ ] Join su `year` e `month` (stringhe)
- [ ] Conversione Wh → kWh: `/ 1000.0`
- [ ] Bug Consumo: se presente, diviso per 1000 extra
- [ ] Verifica manuale pre-sum con anno specifico
- [ ] Output con nome descrittivo

### Ottimizzazioni Applicate
- [ ] Filter accorpati
- [ ] `sum()` invece di `sum(column: "_value")`
- [ ] Variabili intermedie eliminate
- [ ] `createEmpty: false` rimosso (è default)
- [ ] Import inutilizzati rimossi (eccetto timezone con option location)
- [ ] `yield` rimosso
- [ ] `_field` rimosso se ridondante

---

## Note Finali

**Range Universale:**
Tutte le query devono usare `start: 0` per prendere tutto lo storico, non date fisse.

**Testing Incrementale:**
Quando ottimizzi, applica UNA modifica alla volta e testa.
Se rompe, ripristina immediatamente.

**Verifica Valori:**
Per query con calcoli complessi (join, percentuali), testare con subset di dati e verificare manualmente i calcoli prima di usare sum() o aggregazioni finali.

**option location è Critico:**
Non rimuoverlo mai senza test. Influenza sia timezone che date.truncate anche quando sembra inutilizzato.

---

## Esempi Query Complete Ottimizzate

### 1. Totali Storici
```flux
import "timezone"

option location = timezone.location(name: "Europe/Rome")

emission_factor_kg_per_kwh = 0.4

from(bucket: "Solaredge")
  |> range(start: 0)
  |> filter(fn: (r) => 
      r._measurement == "web" and 
      r._field == "Site" and
      (r.endpoint == "PRODUCTION_ENERGY" or 
       r.endpoint == "EXPORT_ENERGY" or 
       r.endpoint == "IMPORT_ENERGY")
  )
  |> aggregateWindow(every: 1d, fn: last, createEmpty: false)
  |> group(columns: ["endpoint"])
  |> sum()
  |> map(fn: (r) => ({r with dummy: "total"}))
  |> pivot(rowKey: ["dummy"], columnKey: ["endpoint"], valueColumn: "_value")
  |> map(fn: (r) => {
      prod = r.PRODUCTION_ENERGY
      imp = r.IMPORT_ENERGY
      exp = r.EXPORT_ENERGY
      
      return {
          Produzione: prod,
          Prelievo: imp,
          Immissione: exp,
          Consumo: (prod + imp - exp) / 1000.0,
          Autoconsumo: prod - exp,
          "Emissioni CO2 Evitate (kg)": (prod / 1000.0) * emission_factor_kg_per_kwh,
          "% Autoconsumo": ((prod - exp) / (prod + imp - exp)) * 100.0,
          "% Prelievo": (imp / (prod + imp - exp)) * 100.0
      }
  })
```

### 2. Costo Senza Fotovoltaico (Join PUN)
```flux
import "date"
import "join"
import "timezone"

option location = timezone.location(name: "Europe/Rome")

consumo = from(bucket: "Solaredge")
  |> range(start: 0)
  |> filter(fn: (r) => 
      r._measurement == "web" and 
      r._field == "Site" and
      (r.endpoint == "PRODUCTION_ENERGY" or 
       r.endpoint == "IMPORT_ENERGY" or 
       r.endpoint == "EXPORT_ENERGY")
  )
  |> aggregateWindow(every: 1mo, fn: sum, location: location, timeSrc: "_start")
  |> pivot(rowKey: ["_time"], columnKey: ["endpoint"], valueColumn: "_value")
  |> map(fn: (r) => ({
      _time: r._time,
      year: string(v: date.year(t: r._time)),
      month: string(v: date.month(t: r._time)),
      consumo_wh: r.PRODUCTION_ENERGY + r.IMPORT_ENERGY - r.EXPORT_ENERGY
  }))
  |> group()

pun = from(bucket: "GME")
  |> range(start: 0)
  |> filter(fn: (r) => r._measurement == "gme_monthly_avg" and r._field == "pun_kwh_avg")
  |> map(fn: (r) => ({
      _time: r._time,
      year: r.year,
      month: string(v: date.month(t: r._time)),
      pun: r._value
  }))
  |> group()

join.inner(
  left: consumo,
  right: pun,
  on: (l, r) => l.year == r.year and l.month == r.month,
  as: (l, r) => ({
    _time: l._time,
    _value: (l.consumo_wh / 1000.0) * r.pun
  })
)
  |> sum()
  |> map(fn: (r) => ({"Spesa Senza Fotovoltaico": r._value}))
```

### 3. Percentuale Prelievo Giornaliera
```flux
import "date"
import "array"
import "timezone"

option location = timezone.location(name: "Europe/Rome")

start = date.truncate(t: now(), unit: 1d)

data_prod = from(bucket: "Solaredge_Realtime")
  |> range(start: start)
  |> filter(fn: (r) =>
      r._measurement == "realtime" and
      r._field == "Inverter" and
      r.endpoint == "Energy Total" and
      exists r._value)

prod_value = (data_prod |> last() |> findRecord(fn: (key) => true, idx: 0))._value - 
             (data_prod |> first() |> findRecord(fn: (key) => true, idx: 0))._value

data_imp = from(bucket: "Solaredge_Realtime")
  |> range(start: start)
  |> filter(fn: (r) =>
      r._measurement == "realtime" and
      r._field == "Meter" and
      r.endpoint == "Import Energy Active" and
      exists r._value)

imp_value = (data_imp |> last() |> findRecord(fn: (key) => true, idx: 0))._value - 
            (data_imp |> first() |> findRecord(fn: (key) => true, idx: 0))._value

data_exp = from(bucket: "Solaredge_Realtime")
  |> range(start: start)
  |> filter(fn: (r) =>
      r._measurement == "realtime" and
      r._field == "Meter" and
      r.endpoint == "Export Energy Active" and
      exists r._value)

exp_value = (data_exp |> last() |> findRecord(fn: (key) => true, idx: 0))._value - 
            (data_exp |> first() |> findRecord(fn: (key) => true, idx: 0))._value

consumo_wh = imp_value + prod_value - exp_value

array.from(rows: [{
  _time: now(),
  "% Prelievo OGGI": if consumo_wh > 0.0 then (imp_value / consumo_wh) * 100.0 else 0.0
}])
```

---

**Documento compilato da conversazione del 01/12/2025**
**Obiettivo Completezza: 98%**

Possibili Gap:
- Dettagli specifici su performance timing (non misurati)
- Casistiche edge non testate (dati mancanti, bucket vuoti)
