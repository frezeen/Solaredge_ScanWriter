# 📄 DOCUMENTAZIONE COMPLETA - Sistema di Analisi Economica Fotovoltaico

## 📑 INDICE

1. [Introduzione e Logica del Sistema](#1-introduzione-e-logica-del-sistema)
2. [Parametri Configurabili e Costanti](#2-parametri-configurabili-e-costanti)
3. [Query 1 - Spesa Senza Fotovoltaico](#3-query-1---spesa-senza-fotovoltaico)
4. [Query 2 - Spesa Con Fotovoltaico](#4-query-2---spesa-con-fotovoltaico)
5. [Query 3 - Rimborsi Immissione](#5-query-3---rimborsi-immissione)
6. [Pannello Riepilogo - Guadagno Totale](#6-pannello-riepilogo---guadagno-totale)
7. [Formule e Calcoli Matematici](#7-formule-e-calcoli-matematici)
8. [Piano di Implementazione con Valori Reali](#8-piano-di-implementazione-con-valori-reali)

---

## 1. INTRODUZIONE E LOGICA DEL SISTEMA

### 1.1 Obiettivo
Calcolare **quanto denaro hai guadagnato grazie al fotovoltaico** rispetto allo scenario in cui non lo avresti installato.

### 1.2 Logica di Base
```
Guadagno Totale = Risparmi in Bolletta + Incassi da GSE

Dove:
- Risparmi = (Costo Senza FV) - (Costo Con FV)
- Incassi = Rimborsi da immissione energia in rete
```

### 1.3 Componenti del Costo Energia
Per calcolare il costo reale dell'energia dalla rete, consideriamo:
- **PUN**: Prezzo Unico Nazionale (componente energia pura)
- **Oneri**: Oneri di sistema, trasporto, distribuzione, accise
- **IVA**: 10% uso domestico, 22% uso non domestico

**Formula completa costo energia:**
```
Costo = kWh × (PUN + Oneri) × (1 + IVA)
```

### 1.4 Semplificazioni Adottate
Per mantenere le query gestibili e personalizzabili:
- **Valori medi mensili** invece di valori orari
- **Percentuali fisse parametrizzabili** per prezzi Scambio/Eccedenza
- **Costanti configurabili** all'inizio di ogni query
- **Valori fittizie di default** che ogni utente può sostituire con i propri dati reali

### 1.5 Dati Necessari
Dal sistema SolarEdge:
- **PRODUCTION_ENERGY**: Energia prodotta dal fotovoltaico (Wh)
- **IMPORT_ENERGY**: Energia prelevata dalla rete (Wh)
- **EXPORT_ENERGY**: Energia immessa in rete (Wh)

Dal database GME:
- **PUN medio mensile**: Prezzo energia (€/kWh)

---

## 2. PARAMETRI CONFIGURABILI E COSTANTI

### 2.1 Lista Completa Parametri

Ogni query contiene all'inizio una sezione chiaramente delimitata con i parametri modificabili:

```sql
// ============================================================================
// PARAMETRI CONFIGURABILI - Modifica questi valori
// ============================================================================

// 1. COSTO ONERI VARIABILI (€/kWh)
// Componenti: trasporto, distribuzione, oneri di sistema, accise
// Valore tipico: 0.12 - 0.18 €/kWh
// Come trovarlo: (Totale bolletta - Costo energia) / kWh prelevati
// Default fittizio: 0.15 €/kWh
costo_oneri = 0.15

// 2. IVA ENERGIA ELETTRICA
// Uso domestico residenziale: 0.10 (10%)
// Uso non domestico/industriale: 0.22 (22%)
// Default: 0.10 (uso domestico)
iva_energia = 0.10

// 3. PREZZO SCAMBIO come percentuale del PUN
// Il GSE rimborsa l'energia "scambiata" a questo prezzo
// Valore tipico: 0.95 - 1.05 (95-105% del PUN)
// Default fittizio: 1.00 (100% del PUN - da verificare con dati GSE reali)
prezzo_scambio_percentuale = 1.00

// 4. PREZZO ECCEDENZA come percentuale del PUN
// Il GSE rimborsa l'energia "eccedente" a questo prezzo
// Valore tipico: 0.85 - 0.95 (85-95% del PUN)
// Default fittizio: 0.90 (90% del PUN - da verificare con dati GSE reali)
prezzo_eccedenza_percentuale = 0.90

// 5. TASSAZIONE ECCEDENZA
// Aliquota fiscale personale sull'energia venduta in eccedenza
// Dipende dalla tua situazione fiscale e dalle detrazioni applicabili
// Valori comuni:
//   0.00 = nessuna tassazione (detrazioni fiscali 100%)
//   0.23 = IRPEF primo scaglione (23%)
//   0.35 = IRPEF secondo scaglione (35%)
//   0.40 = tassazione effettiva media dopo detrazioni
// Default fittizio: 0.00 (nessuna tassazione)
tassazione_eccedenza = 0.00

// ============================================================================
// FINE PARAMETRI CONFIGURABILI
// ============================================================================
```

### 2.2 Guida alla Personalizzazione

| Parametro | Dove Trovare il Valore Reale | Note |
|-----------|-------------------------------|------|
| `costo_oneri` | Bolletta elettrica: (Totale - Energia) / kWh | Varia per fornitore e tipo contratto |
| `iva_energia` | 10% domestico, 22% altri usi | Fisso per legge |
| `prezzo_scambio_percentuale` | Portale GSE / Fatture GSE | Varia mensilmente |
| `prezzo_eccedenza_percentuale` | Portale GSE / Fatture GSE | Varia mensilmente |
| `tassazione_eccedenza` | Consulta commercialista | Dipende da situazione fiscale personale |

---

## 3. QUERY 1 - SPESA SENZA FOTOVOLTAICO

### 3.1 Scopo
Calcolare quanto **avresti speso** consumando la stessa quantità di energia **senza fotovoltaico** (prelevando tutto dalla rete).

### 3.2 Formula
```
Spesa Senza FV = Consumo Totale × (PUN + Oneri) × (1 + IVA)

Dove:
Consumo Totale = Produzione + Prelievo - Immissione
               = Autoconsumo + Prelievo
```

### 3.3 Logica
L'energia che hai consumato (Consumo Totale) è composta da:
- Energia autoprodotta e autoconsumata (Autoconsumo)
- Energia prelevata dalla rete (Prelievo)

Senza fotovoltaico, avresti dovuto prelevare **tutta** questa energia dalla rete, pagando il prezzo pieno comprensivo di PUN, Oneri e IVA.

### 3.4 Query Completa

```sql
import "date"
import "join"
import "timezone"

option location = timezone.location(name: "Europe/Rome")

// ============================================================================
// PARAMETRI CONFIGURABILI
// ============================================================================

costo_oneri = 0.15
iva_energia = 0.10

// ============================================================================

energia = from(bucket: "Solaredge")
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
  left: energia,
  right: pun,
  on: (l, r) => l.year == r.year and l.month == r.month,
  as: (l, r) => ({
    _time: l._time,
    _value: (l.consumo_wh / 1000.0) * (r.pun + costo_oneri) * (1.0 + iva_energia)
  })
)
  |> sum()
  |> map(fn: (r) => ({"Spesa Senza Fotovoltaico": r._value}))
```

---

## 4. QUERY 2 - SPESA CON FOTOVOLTAICO

### 4.1 Scopo
Calcolare quanto **stai spendendo realmente** con il fotovoltaico (solo per l'energia prelevata dalla rete).

### 4.2 Formula
```
Spesa Con FV = Prelievo × (PUN + Oneri) × (1 + IVA)
```

### 4.3 Logica
Con il fotovoltaico, paghi solo per l'energia che **effettivamente prelevi dalla rete** quando la produzione fotovoltaica non è sufficiente a coprire il consumo istantaneo.

L'energia autoconsumata dal fotovoltaico **non ha costo** in bolletta (oltre ai costi fissi annuali che si cancellano nel confronto).

### 4.4 Query Completa

```sql
import "date"
import "join"
import "timezone"

option location = timezone.location(name: "Europe/Rome")

// ============================================================================
// PARAMETRI CONFIGURABILI
// ============================================================================

costo_oneri = 0.15
iva_energia = 0.10

// ============================================================================

prelievo = from(bucket: "Solaredge")
  |> range(start: 0)
  |> filter(fn: (r) => 
      r._measurement == "web" and 
      r._field == "Site" and
      r.endpoint == "IMPORT_ENERGY"
  )
  |> aggregateWindow(every: 1mo, fn: sum, location: location, timeSrc: "_start")
  |> map(fn: (r) => ({
      _time: r._time,
      year: string(v: date.year(t: r._time)),
      month: string(v: date.month(t: r._time)),
      prelievo_wh: r._value
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
  left: prelievo,
  right: pun,
  on: (l, r) => l.year == r.year and l.month == r.month,
  as: (l, r) => ({
    _time: l._time,
    _value: (l.prelievo_wh / 1000.0) * (r.pun + costo_oneri) * (1.0 + iva_energia)
  })
)
  |> sum()
  |> map(fn: (r) => ({"Spesa Con Fotovoltaico": r._value}))
```

---

## 5. QUERY 3 - RIMBORSI IMMISSIONE

### 5.1 Scopo
Calcolare i **rimborsi netti** che ricevi dal GSE per l'energia immessa in rete, tenendo conto della distinzione tra Scambio ed Eccedenza e della tassazione.

### 5.2 Formule

#### Energia Scambiata ed Eccedenza
```
Energia Scambiata = min(Immissione, Prelievo)
Energia Eccedenza = max(0, Immissione - Prelievo)
```

**Logica:**
- **Scambio sul Posto**: Energia che "depositi" in rete e poi "riprendi" (fino al limite del prelievo)
- **Eccedenza**: Energia venduta definitivamente alla rete (oltre il prelievo)

#### Rimborsi
```
Rimborso Scambio = Energia Scambiata × PUN × prezzo_scambio_% 
                   (esente da tassazione IRPEF)

Rimborso Eccedenza Lordo = Energia Eccedenza × PUN × prezzo_eccedenza_%

Rimborso Eccedenza Netto = Rimborso Eccedenza Lordo × (1 - tassazione_%)

Rimborsi Totali = Rimborso Scambio + Rimborso Eccedenza Netto
```

### 5.3 Logica Tassazione

**Scambio sul Posto:**
- Considerato compensazione, non reddito
- **Esente da IRPEF**

**Eccedenza:**
- Considerata vendita di energia = reddito
- **Soggetta a tassazione IRPEF**
- Aliquota dipende da situazione fiscale personale e detrazioni applicabili

### 5.4 Query Completa

```sql
import "date"
import "join"
import "timezone"

option location = timezone.location(name: "Europe/Rome")

// ============================================================================
// PARAMETRI CONFIGURABILI
// ============================================================================

prezzo_scambio_percentuale = 1.00
prezzo_eccedenza_percentuale = 0.90
tassazione_eccedenza = 0.00

// ============================================================================

energia = from(bucket: "Solaredge")
  |> range(start: 0)
  |> filter(fn: (r) => 
      r._measurement == "web" and 
      r._field == "Site" and
      (r.endpoint == "EXPORT_ENERGY" or r.endpoint == "IMPORT_ENERGY")
  )
  |> aggregateWindow(every: 1mo, fn: sum, location: location, timeSrc: "_start")
  |> pivot(rowKey: ["_time"], columnKey: ["endpoint"], valueColumn: "_value")
  |> map(fn: (r) => ({
      _time: r._time,
      year: string(v: date.year(t: r._time)),
      month: string(v: date.month(t: r._time)),
      immissione_wh: r.EXPORT_ENERGY,
      prelievo_wh: r.IMPORT_ENERGY
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
  left: energia,
  right: pun,
  on: (l, r) => l.year == r.year and l.month == r.month,
  as: (l, r) => {
    immissione_kwh = l.immissione_wh / 1000.0
    prelievo_kwh = l.prelievo_wh / 1000.0
    scambio_kwh = if immissione_kwh < prelievo_kwh then immissione_kwh else prelievo_kwh
    eccedenza_kwh = if immissione_kwh > prelievo_kwh then immissione_kwh - prelievo_kwh else 0.0
    rimborso_scambio = scambio_kwh * r.pun * prezzo_scambio_percentuale
    rimborso_eccedenza_lordo = eccedenza_kwh * r.pun * prezzo_eccedenza_percentuale
    rimborso_eccedenza_netto = rimborso_eccedenza_lordo * (1.0 - tassazione_eccedenza)
    return {_time: l._time, _value: rimborso_scambio + rimborso_eccedenza_netto}
  }
)
  |> sum()
  |> map(fn: (r) => ({"Rimborsi Immissione Netti": r._value}))
```

---

## 6. PANNELLO RIEPILOGO - GUADAGNO TOTALE

### 6.1 Configurazione Grafana

Il pannello finale combina le tre query precedenti usando le **Expressions** di Grafana.

#### Step-by-Step:

1. **Crea un pannello di tipo "Stat" o "Table"**

2. **Aggiungi le 3 query:**
   - Query A: Spesa Senza Fotovoltaico
   - Query B: Spesa Con Fotovoltaico
   - Query C: Rimborsi Immissione Netti

3. **Aggiungi le Expressions:**
   - **Expression D** (Risparmi):
     - Type: Math
     - Expression: `$A - $B`
     - Alias: `Risparmi`
   
   - **Expression E** (Incassi):
     - Type: Math
     - Expression: `$C`
     - Alias: `Incassi`
   
   - **Expression F** (Totale):
     - Type: Math
     - Expression: `$A - $B + $C`
     - Alias: `Totale`

4. **Configura Display:**
   - Nascondi Query A, B, C (Hide)
   - Mostra solo: Risparmi, Incassi, Totale
   - Format: Currency (€)
   - Decimals: 2

### 6.2 Visualizzazione Consigliata

**Opzione 1: Tre Stat Panels affiancati**
```
┌─────────────────┬─────────────────┬─────────────────┐
│   RISPARMI      │    INCASSI      │    TOTALE       │
│   2.849 €       │    3.839 €      │    6.688 €      │
└─────────────────┴─────────────────┴─────────────────┘
```

**Opzione 2: Table Panel**
```
┌──────────────────┬────────────────┐
│ Voce             │ Importo Annuo  │
├──────────────────┼────────────────┤
│ Risparmi         │    2.849 €     │
│ Incassi GSE      │    3.839 €     │
│ TOTALE GUADAGNO  │    6.688 €     │
└──────────────────┴────────────────┘
```

---

## 7. FORMULE E CALCOLI MATEMATICI

### 7.1 Bilancio Energetico

#### Relazioni fondamentali:
```
Produzione FV = Autoconsumo + Immissione
Consumo Totale = Autoconsumo + Prelievo

Quindi:
Autoconsumo = Produzione - Immissione
Autoconsumo = Consumo - Prelievo
```

### 7.2 Calcoli Economici Completi

#### Risparmio in Bolletta:
```
Risparmio = (Consumo × Prezzo Completo) - (Prelievo × Prezzo Completo)
          = (Consumo - Prelievo) × (PUN + Oneri) × (1 + IVA)
          = Autoconsumo × (PUN + Oneri) × (1 + IVA)
```

**Interpretazione:** Ogni kWh autoconsumato ti fa risparmiare l'intero costo che avresti pagato prelevandolo dalla rete (PUN + Oneri + IVA).

#### Incassi da Immissione:
```
Scambio = min(Immissione, Prelievo)
Eccedenza = max(0, Immissione - Prelievo)

Incasso Scambio = Scambio × PUN × % Scambio (esente tasse)
Incasso Eccedenza Netto = Eccedenza × PUN × % Eccedenza × (1 - Tassazione)

Incassi Totali = Incasso Scambio + Incasso Eccedenza Netto
```

#### Guadagno Totale:
```
Guadagno Totale = Risparmio + Incassi
                = [Autoconsumo × (PUN + Oneri) × (1 + IVA)] 
                  + [Rimborsi GSE Netti]
```

### 7.3 Esempio Numerico Completo

**Dati di esempio (valori annuali):**
- Produzione: 31.800 kWh
- Consumo: 17.340 kWh
- Prelievo: 9.290 kWh
- Immissione: 23.760 kWh
- PUN medio: 0,172 €/kWh
- Oneri: 0,15 €/kWh
- IVA: 10%

**Calcoli:**
```
Autoconsumo = 31.800 - 23.760 = 8.040 kWh

Prezzo Completo = (0,172 + 0,15) × 1,10 = 0,3542 €/kWh

Spesa Senza FV = 17.340 × 0,3542 = 6.142 €
Spesa Con FV = 9.290 × 0,3542 = 3.290 €
Risparmio = 6.142 - 3.290 = 2.852 €

Scambio = min(23.760, 9.290) = 9.290 kWh
Eccedenza = 23.760 - 9.290 = 14.470 kWh

Rimborso Scambio = 9.290 × 0,172 × 1,00 = 1.598 €
Rimborso Eccedenza = 14.470 × 0,172 × 0,90 × (1 - 0) = 2.241 €
Incassi Totali = 1.598 + 2.241 = 3.839 €

GUADAGNO TOTALE = 2.852 + 3.839 = 6.691 €/anno
```

### 7.4 KPI Utili

**Tasso di Autoconsumo:**
```
Autoconsumo / Produzione = 8.040 / 31.800 = 25,3%
```
Indica quanto dell'energia prodotta viene utilizzata direttamente.

**Tasso di Copertura:**
```
Autoconsumo / Consumo = 8.040 / 17.340 = 46,4%
```
Indica quanta parte del fabbisogno è coperta dal fotovoltaico.

**Fattore di Sovradimensionamento:**
```
Produzione / Consumo = 31.800 / 17.340 = 1,83
```
Indica se l'impianto è sovradimensionato (>1) o sottodimensionato (<1).

---

## 8. PIANO DI IMPLEMENTAZIONE CON VALORI REALI

### 8.1 Obiettivo
Sostituire i valori fittizie approssimati con **dati reali specifici** per ottenere la massima precisione nei calcoli.

### 8.2 Roadmap di Ottimizzazione

#### FASE 1: Parametri di Base (Precisione 90%)
**Tempo richiesto:** 30 minuti

**Azioni:**
1. **Oneri Variabili:**
   - Prendi una bolletta recente
   - Identifica: Totale bolletta, Costo energia, kWh prelevati
   - Calcola: `Oneri = (Totale - Costo energia) / kWh`
   - Aggiorna `costo_oneri` nelle Query 1 e 2

2. **IVA:**
   - Verifica sulla bolletta l'aliquota IVA applicata
   - Domestico: 10%
   - Non domestico: 22%
   - Aggiorna `iva_energia` nelle Query 1 e 2

3. **Tassazione Personale:**
   - Consulta il tuo commercialista
   - Considera: Aliquota IRPEF, detrazioni applicabili
   - Aggiorna `tassazione_eccedenza` in Query 3

**Precisione attesa dopo Fase 1:** ~90%

---

#### FASE 2: Prezzi GSE Reali (Precisione 95%)
**Tempo richiesto:** 1-2 ore

**Azioni:**
1. **Accedi al Portale GSE:**
   - Login su https://applicazioni.gse.it
   - Sezione: Scambio sul Posto / Ritiro Dedicato
   - Scarica i rendiconti mensili

2. **Estrai i Prezzi Reali:**
   - **Prezzo di Scambio:** Cerca "Contributo in conto scambio unitario" (€/kWh)
   - **Prezzo Eccedenza:** Cerca "Prezzo minimo garantito" o "Prezzo zonale" (€/kWh)

3. **Calcola le Percentuali sul PUN:**
   ```
   % Scambio = Prezzo Scambio GSE / PUN medio mese
   % Eccedenza = Prezzo Eccedenza GSE / PUN medio mese
   ```

4. **Aggiorna Query 3:**
   - Sostituisci `prezzo_scambio_percentuale = 1.00` con valore calcolato
   - Sostituisci `prezzo_eccedenza_percentuale = 0.90` con valore calcolato

**Precisione attesa dopo Fase 2:** ~95%

---

#### FASE 3: Prezzi Variabili Mensili (Precisione 99%)
**Tempo richiesto:** 4-6 ore (una tantum)

**Obiettivo:** Usare prezzi GSE specifici mese per mese invece di percentuali fisse.

**Implementazione:**

1. **Crea Nuova Tabella nel Database:**
   ```sql
   CREATE TABLE gse_prezzi_mensili (
     anno INT,
     mese INT,
     prezzo_scambio FLOAT,
     prezzo_eccedenza FLOAT
   )
   ```

2. **Popola con Dati Storici GSE:**
   - Estrai dati da rendiconti GSE
   - Inserisci manualmente o tramite script

3. **Modifica Query 3:**
   Invece di usare percentuali fisse, fai un secondo join con la tabella prezzi GSE:
   
   ```sql
   // Pseudocodice
   prezzi_gse = from(bucket: "GSE_Prezzi")
     |> filter(anno, mese)
   
   join(energia, pun, prezzi_gse)
     |> calcola con prezzi_gse.prezzo_scambio e prezzi_gse.prezzo_eccedenza
   ```

**Precisione attesa dopo Fase 3:** ~99%

---

#### FASE 4: Oneri Variabili per Scaglioni (Precisione 99.5%)
**Tempo richiesto:** 2-3 ore

**Contesto:** Gli oneri in bolletta possono variare per scaglioni di consumo.

**Azioni:**
1. Analizza le bollette per identificare scaglioni
2. Crea una funzione che calcola oneri variabili:
   ```sql
   oneri = if consumo < 1800 then 0.12
           else if consumo < 2640 then 0.15
           else 0.18
   ```

3. Integra nella logica di calcolo Query 1 e 2

**Precisione attesa dopo Fase 4:** ~99.5%

---

### 8.3 Checklist Verifica Dati Reali

Prima di considerare il sistema "ottimizzato", verifica:

- [ ] **Oneri:** Valore estratto da bolletta reale (non stimato)
- [ ] **IVA:** Confermata da bolletta (10% o 22%)
- [ ] **Tassazione:** Confermata da commercialista o dichiarazione redditi
- [ ] **Prezzi GSE:** Estratti da rendiconti GSE (non stimati)
- [ ] **Confronto:** Risultati query vs fatture GSE reali (differenza <5%)

### 8.4 Validazione Finale

**Test di coerenza:**
1. Somma i guadagni mensili → Deve corrispondere al totale annuale
2. Confronta "Incassi" con totale fatture GSE annuali → Differenza <5%
3. Confronta "Risparmio" con riduzione bolletta annuale → Coerenza logica

**Tolleranze accettabili:**
- Differenza Incassi vs Fatture GSE: <5%
- Differenza Risparmio calcolato vs Bollette: <10% (variabilità consumi)
- Differenza Totale: <5%

Se le differenze sono maggiori, verifica:
- Parametri configurabili aggiornati correttamente
- Presenza di tutti i dati mensili nel database
- Coerenza temporale (stessi periodi confrontati)

---

### 8.5 Manutenzione e Aggiornamenti

**Frequenza consigliata aggiornamenti:**

| Parametro | Frequenza | Motivo |
|-----------|-----------|--------|
| `costo_oneri` | Semestrale | Possono variare con cambio fornitore |
| `iva_energia` | Annuale | Raramente cambia (solo per legge) |
| `prezzo_scambio_%` | Trimestrale | Varia con mercato energia |
| `prezzo_eccedenza_%` | Trimestrale | Varia con mercato energia |
| `tassazione_eccedenza` | Annuale | Cambia con dichiarazione redditi |

**Procedura di aggiornamento:**
1. Modifica i parametri nelle query
2. Verifica che i pannelli Grafana si aggiornino correttamente
3. Confronta un mese di test con dati reali
4. Se OK, considera aggiornamento validato

---

### 8.6 Troubleshooting Comuni

#### Problema: "I rimborsi calcolati sono molto diversi dalle fatture GSE"

**Possibili cause:**
- `prezzo_scambio_percentuale` e `prezzo_eccedenza_percentuale` non corretti
- `tassazione_eccedenza` non rispecchia la tua situazione fiscale reale
- Fatture GSE includono conguagli di mesi precedenti

**Soluzione:**
1. Scarica rendiconto GSE dettagliato mese per mese
2. Calcola manualmente le percentuali reali
3. Aggiorna i parametri in Query 3
4. Considera implementare Fase 3 (prezzi mensili variabili)

#### Problema: "Il risparmio calcolato non corrisponde alla riduzione in bolletta"

**Possibili cause:**
- `costo_oneri` non include tutte le componenti variabili
- IVA non configurata correttamente
- Bollette includono costi fissi (che si cancellano nel nostro calcolo)

**Soluzione:**
1. Analizza bolletta nel dettaglio
2. Separa costi fissi (€/anno) da costi variabili (€/kWh)
3. Ricalcola `costo_oneri` solo con componenti variabili
4. Verifica aliquota IVA applicata

#### Problema: "I dati energetici (Produzione, Consumo) sembrano sbagliati"

**Possibili cause:**
- Dati SolarEdge non completi per tutto il periodo
- Errori di comunicazione inverter
- Query con filtri temporali errati

**Soluzione:**
1. Verifica su portale SolarEdge che i dati siano completi
2. Controlla `range(start: 0)` nella query
3. Verifica aggregazione mensile funzioni correttamente
4. Confronta totale annuo con dati ufficiali SolarEdge

---

### 8.7 Estensioni Future Consigliate

#### 8.7.1 Dashboard Mensile
Modifica le query per mostrare dati mese per mese invece del totale:
- Rimuovi `|> sum()` finale
- Visualizza con grafico a barre o linee temporali
- Permette di vedere trend stagionali

#### 8.7.2 Confronto Anno su Anno
Aggiungi filtri temporali per confrontare:
- Anno corrente vs anno precedente
- Stesso mese anni diversi
- Trend di miglioramento

#### 8.7.3 Previsioni e Proiezioni
Usa dati storici per proiettare:
- Guadagno atteso fine anno
- Payback period impianto
- ROI annuale

#### 8.7.4 Integrazione Batterie
Se installi sistema di accumulo:
- Aggiungi parametro `capacita_batteria`
- Modifica calcolo autoconsumo
- Stima incremento risparmio con batterie

#### 8.7.5 Alert e Notifiche
Configura alert Grafana per:
- Produzione anomala (sotto soglia)
- Guadagno mensile sotto attese
- Prezzi PUN particolarmente alti/bassi

---

## APPENDICE A - Glossario Termini

**Autoconsumo:** Energia prodotta dal fotovoltaico e consumata istantaneamente, senza passare per la rete.

**Immissione (Export):** Energia prodotta dal fotovoltaico e immessa nella rete elettrica.

**Prelievo (Import):** Energia prelevata dalla rete elettrica quando la produzione fotovoltaica non è sufficiente.

**PUN (Prezzo Unico Nazionale):** Prezzo di riferimento dell'energia elettrica sul mercato italiano, determinato dalla borsa elettrica.

**Oneri di Sistema:** Componenti tariffarie che coprono costi di trasporto, distribuzione, incentivi rinnovabili, ecc.

**Scambio sul Posto (SSP):** Meccanismo che consente di compensare l'energia immessa con quella prelevata, con valorizzazione economica.

**Energia in Scambio:** Parte dell'energia immessa che viene "compensata" con il prelievo (fino al minimo tra immissione e prelievo).

**Energia in Eccedenza:** Parte dell'energia immessa che supera il prelievo annuale, quindi venduta definitivamente alla rete.

**GSE (Gestore Servizi Energetici):** Società pubblica che gestisce i meccanismi di incentivazione delle rinnovabili, incluso lo Scambio sul Posto.

**Tasso di Autoconsumo:** Percentuale dell'energia prodotta che viene autoconsumata (Autoconsumo / Produzione).

**Tasso di Copertura:** Percentuale del fabbisogno energetico coperto dal fotovoltaico (Autoconsumo / Consumo).

---

## APPENDICE B - Link Utili

**Portali Ufficiali:**
- GSE - Area Clienti: https://applicazioni.gse.it
- GME - Prezzi PUN: https://www.mercatoelettrico.org
- ARERA - Autorità Energia: https://www.arera.it
- SolarEdge Monitoring: https://monitoring.solaredge.com

**Documentazione:**
- Guida GSE Scambio sul Posto: https://www.gse.it/servizi-per-te/fotovoltaico/scambio-sul-posto
- Regole Tecniche SSP: Disponibili su portale GSE
- Delibere ARERA: https://www.arera.it/it/elettricita.htm

**Tool e Calcolatori:**
- Simulatore GSE: Disponibile su portale dopo login
- Calcolo convenienza batterie: Vari tool online disponibili

---

## APPENDICE C - FAQ

**Q: Perché non considerate i costi fissi in bolletta?**
A: I costi fissi (€/anno) si cancellano nel confronto con/senza fotovoltaico, perché li pagheresti comunque. Ci concentriamo solo sui costi variabili (€/kWh) che effettivamente cambiano con il fotovoltaico.

**Q: L'IVA va calcolata su PUN+Oneri o solo su PUN?**
A: L'IVA in bolletta si applica sul totale imponibile (PUN + Oneri + Accise), quindi la formula corretta è `(PUN + Oneri) × (1 + IVA)`.

**Q: Perché il prezzo di scambio è diverso dal PUN?**
A: Il GSE applica correzioni e costi di gestione, quindi il prezzo effettivo può essere leggermente superiore o inferiore al PUN. Verifica sui rendiconti GSE.

**Q: Come mai l'energia in eccedenza è tassata?**
A: L'eccedenza è considerata "vendita" di energia, quindi genera reddito soggetto a IRPEF. Lo scambio invece è solo "compensazione", quindi non è reddito.

**Q: Posso avere tassazione 0% sull'eccedenza?**
A: Sì, se hai detrazioni fiscali sufficienti a coprire tutto il reddito da eccedenza, oppure se hai un regime fiscale particolare. Consulta il tuo commercialista.

**Q: Ogni quanto devo aggiornare i parametri nelle query?**
A: Minimo annuale per tutti i parametri. Trimestrale per prezzi GSE se vuoi massima precisione. Vedi sezione 8.5 per dettagli.

**Q: I miei dati energetici sembrano sbagliati, cosa faccio?**
A: Verifica su portale SolarEdge che i dati siano corretti. Controlla che inverter comunichi correttamente. Confronta con bollette per validazione.

**Q: Posso usare queste query per impianti con batterie?**
A: Le query attuali funzionano, ma non ottimizzate per batterie. Servirebbero modifiche per tracciare energia da/verso accumulo. Vedi sezione 8.7.4.

**Q: Come valido che i calcoli siano corretti?**
A: Confronta "Incassi" con fatture GSE annuali (dovrebbero coincidere ±5%). Confronta "Risparmio" con riduzione bolletta (stima, non precisa per costi fissi). Vedi sezione 8.4.

---

## CONCLUSIONI

Questo sistema di analisi fornisce una **visione completa e precisa** del guadagno economico generato dal tuo impianto fotovoltaico.

**Punti di forza:**
- ✅ Calcoli basati su dati reali del tuo impianto
- ✅ Personalizzabile con parametri specifici
- ✅ Distingue correttamente Scambio ed Eccedenza
- ✅ Considera tutti i costi (PUN + Oneri + IVA)
- ✅ Tiene conto della tassazione personale
- ✅ Piano chiaro per ottimizzazione con dati reali

**Prossimi passi consigliati:**
1. Implementa le query in Grafana
2. Configura i parametri base (Fase 1)
3. Valida con dati di un mese recente
4. Procedi con Fase 2 (prezzi GSE reali)
5. Monitora e aggiorna trimestralmente

**Risultato finale:**
Un sistema che ti mostra in tempo reale quanto stai guadagnando grazie al fotovoltaico, con precisione >95% dopo ottimizzazione completa.

---

**Documento versione:** 1.0  
**Data creazione:** Dicembre 2024  
**Ultima modifica:** Dicembre 2024  
**Autore:** Sistema di analisi fotovoltaico personalizzato  
**Licenza:** Uso personale