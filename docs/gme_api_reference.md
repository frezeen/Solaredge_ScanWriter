# Guida Completa API GME - Recupero Dati PUN

## Panoramica
Questa guida descrive come utilizzare le API del GME (Gestore Mercati Energetici) per recuperare i dati del PUN (Prezzo Unico Nazionale) dell'energia elettrica in Italia.

**Base URL**: `https://api.mercatoelettrico.org/request`

---

## 1. Autenticazione

### Endpoint
`POST /api/v1/Auth`

### Request
```json
{
  "Login": "tuo_username",
  "Password": "tua_password"
}
```

### Response
```json
{
  "Success": true,
  "JWT": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "Reason": ""
}
```

### Note operative
- Il token JWT deve essere incluso in **tutte le chiamate successive**
- Header HTTP: `Authorization: Bearer <JWT_token>`
- Non ci sono informazioni sulla durata del token nel documento
- **Best practice**: Ri-autenticarsi se si riceve un errore 401

---

## 2. Recupero Dati PUN

### Endpoint
`POST /api/v1/RequestData`

### Headers
```
Authorization: Bearer <JWT_token>
Content-Type: application/json
```

### Request Body
```json
{
  "Platform": "PublicMarketResults",
  "Segment": "MGP",
  "DataName": "ME_ZonalPrices",
  "IntervalStart": "20240101",
  "IntervalEnd": "20240131",
  "Attributes": {}
}
```

### Parametri Obbligatori

| Parametro | Valore per PUN | Descrizione |
|-----------|----------------|-------------|
| `Platform` | `"PublicMarketResults"` | Piattaforma fissa per dati pubblici |
| `Segment` | `"MGP"` | Mercato del Giorno Prima |
| `DataName` | `"ME_ZonalPrices"` | Dataset prezzi zonali (include PUN) |
| `IntervalStart` | `"yyyyMMdd"` | Data inizio periodo (es: "20240101") |
| `IntervalEnd` | `"yyyyMMdd"` | Data fine periodo (es: "20240131") |
| `Attributes` | `{}` | Oggetto vuoto (o con granularità) |

### Attributi Opzionali (dal 1° Ottobre 2025)
```json
{
  "Attributes": {
    "GranularityTypes": "PT15"  // oppure "PT30" o "PT60"
  }
}
```

**Granularità disponibili**:
- `"PT15"` → dati ogni 15 minuti
- `"PT30"` → dati ogni 30 minuti  
- `"PT60"` → dati orari (default)

⚠️ **ATTENZIONE**: Granularità diverse da PT60 sono disponibili solo dal 1° Ottobre 2025 in poi.

---

## 3. Struttura Risposta

### Response Format
```json
{
  "RequestId": "abc123",
  "FormatType": ".json.zip",
  "ResultRequest": "Success",
  "ContentResponse": "UEsDBBQAAAAIA..."
}
```

### Campi Response

| Campo | Tipo | Descrizione |
|-------|------|-------------|
| `RequestId` | string | ID univoco della richiesta |
| `FormatType` | string | Formato risposta (`.json.zip` o `.xml.zip`) |
| `ResultRequest` | string | Esito richiesta o messaggio errore |
| `ContentResponse` | string | Contenuto codificato in **Base64** |

### Decodifica ContentResponse

1. **Decodifica Base64** → ottieni un file ZIP
2. **Decomprimi ZIP** → ottieni un file JSON/XML
3. **Parsa JSON/XML** → ottieni i dati

---

## 4. Struttura Dati PUN

### Campi nel JSON Decodificato

```json
[
  {
    "FlowDate": 20240101,
    "Hour": 1,
    "Period": null,
    "Market": "MGP",
    "Zone": "PUN",
    "Price": 115.50
  },
  {
    "FlowDate": 20240101,
    "Hour": 2,
    "Period": null,
    "Market": "MGP",
    "Zone": "PUN",
    "Price": 110.25
  }
]
```

### Descrizione Campi

| Campo | Tipo | Descrizione | Note |
|-------|------|-------------|------|
| `FlowDate` | int | Data in formato `yyyyMMdd` | Es: 20240101 = 1 gen 2024 |
| `Hour` | int | Ora del giorno (1-25) | Ora 25 = ora legale → solare |
| `Period` | string | Periodo sub-orario (1-100) | Valorizzato solo con granularità <60min |
| `Market` | string | Sempre `"MGP"` | Mercato del Giorno Prima |
| `Zone` | string | Zona di mercato | **Filtra su `"PUN"`** per il prezzo nazionale |
| `Price` | decimal | Prezzo in €/MWh | Prezzo orario del PUN |

### ⚠️ IMPORTANTE: Filtraggio Zone
La risposta contiene **tutte le zone di mercato** (Nord, Sud, Sicilia, Sardegna, ecc.).  
**Devi filtrare** i record con `Zone == "PUN"` per ottenere solo il Prezzo Unico Nazionale.

---

## 5. Gestione Rate Limiting

### Limiti API

Il sistema applica limiti di utilizzo calcolati come:

**Numero Dati = Numero Oggetti × Numero Campi**

Limiti disponibili:
- `MaxConcurrentConnections` - Connessioni simultanee
- `MaxConnectionsPerMinute` - Chiamate al minuto
- `MaxConnectionsPerHour` - Chiamate all'ora
- `MaxDataPerMinute` - Dati scaricabili al minuto
- `MaxDataPerHour` - Dati scaricabili all'ora

### Verifica Quote Utente

**Endpoint**: `GET /api/v1/GetMyQuotas`

**Headers**: 
```
Authorization: Bearer <JWT_token>
```

**Response**:
```json
{
  "LastModifiedTime": "2024-01-15T10:30:00",
  "LastModifiedHour": "2024-01-15T10:00:00",
  "ActiveConnections": 0,
  "ConnectionsPerMinute": 5,
  "ConnectionsPerHour": 45,
  "DataPerMinute": 1200,
  "DataPerHour": 15000,
  "Limits": {
    "MaxConcurrentConnections": 5,
    "MaxConnectionsPerMinute": 60,
    "MaxConnectionsPerHour": 500,
    "MaxDataPerMinute": 10000,
    "MaxDataPerHour": 100000
  }
}
```

### Calcolo Consumo Dati per PUN

**Esempio**: Richiesta di 1 mese (30 giorni)
- Record: 30 giorni × 24 ore = 720 oggetti
- Campi per record: 6 (FlowDate, Hour, Period, Market, Zone, Price)
- **Consumo dati**: 720 × 6 = **4.320 dati**

**Con MaxDataPerHour = 100.000**:
- Mesi richiedibili all'ora: 100.000 / 4.320 ≈ **23 mesi**

### Best Practices Rate Limiting

1. ✅ **Raggruppa le richieste**: Richiedi periodi lunghi (mensili/trimestrali) invece di giornalieri
2. ✅ **Monitora le quote**: Chiama `GetMyQuotas` prima di operazioni massive
3. ✅ **Gestisci errori 429**: Implementa retry con backoff esponenziale
4. ✅ **Calcola consumo previsto**: Valuta quanti dati consumerai prima di chiamare l'API

---

## 6. Strategie di Recupero Dati

### ❌ Approccio SCONSIGLIATO
```
180 chiamate giornaliere per 6 mesi
→ Supera MaxConnectionsPerHour
→ Blocco API
```

### ✅ Approccio OTTIMALE

**Opzione A - Chiamate Mensili**
```json
// Gennaio 2024
{"IntervalStart": "20240101", "IntervalEnd": "20240131"}
// Febbraio 2024
{"IntervalStart": "20240201", "IntervalEnd": "20240229"}
// ... ecc
```
→ 6 chiamate per 6 mesi (invece di 180)

**Opzione B - Chiamate Semestrali/Annuali**
```json
// Intero semestre
{"IntervalStart": "20240101", "IntervalEnd": "20240630"}
```
→ 1 sola chiamata per 6 mesi

**Opzione C - Multi-anno**
```json
// Ultimi 5 anni
{"IntervalStart": "20200101", "IntervalEnd": "20241231"}
```
→ 1 chiamata per 5 anni (se entro i limiti)

### Workflow Consigliato

```
1. Autenticazione → Ottieni JWT
2. GetMyQuotas → Verifica limiti disponibili
3. Calcola consumo → N_giorni × 24 × 6 campi
4. Verifica fattibilità → Consumo < MaxDataPerHour?
5. RequestData → Richiedi dati
6. Decodifica Base64 → Ottieni ZIP
7. Decomprimi → Ottieni JSON
8. Filtra Zone="PUN" → Estrai solo PUN
9. Aggrega → Calcola medie mensili/annuali
```

---

## 7. Gestione Errori

### Errori Comuni

| Errore | Causa | Soluzione |
|--------|-------|-----------|
| `Success: false` | Credenziali errate | Verifica Login/Password |
| `401 Unauthorized` | Token scaduto/invalido | Ri-autentica |
| `429 Too Many Requests` | Rate limit superato | Attendi reset limiti orari |
| `ResultRequest != "Success"` | Parametri errati | Verifica Segment/DataName |
| Dati vuoti | Intervallo date errato | Verifica formato yyyyMMdd |

### Error Handling Template

```python
# Esempio pseudo-codice
try:
    response = call_api(params)
    
    if response["ResultRequest"] != "Success":
        log_error(response["ResultRequest"])
        return None
    
    # Decodifica Base64
    zip_data = base64.decode(response["ContentResponse"])
    
    # Decomprimi
    json_data = unzip(zip_data)
    
    # Filtra PUN
    pun_data = filter(json_data, Zone="PUN")
    
    return pun_data
    
except RateLimitError:
    wait_until_reset()
    retry()
    
except AuthError:
    re_authenticate()
    retry()
```

---

## 8. Calcolo Medie Mensili

### Algoritmo

```
Per ogni mese:
  1. Filtra record del mese
  2. Somma tutti i Price
  3. Dividi per numero di ore
  4. Risultato = PUN medio mensile
```

### Esempio Calcolo

```python
# Pseudo-codice
monthly_averages = {}

for record in pun_data:
    month = extract_month(record["FlowDate"])  # es: "202401"
    
    if month not in monthly_averages:
        monthly_averages[month] = {"sum": 0, "count": 0}
    
    monthly_averages[month]["sum"] += record["Price"]
    monthly_averages[month]["count"] += 1

# Calcola medie
for month in monthly_averages:
    avg = monthly_averages[month]["sum"] / monthly_averages[month]["count"]
    print(f"{month}: {avg:.2f} €/MWh")
```

### Output Atteso
```
202401: 115.32 €/MWh
202402: 108.45 €/MWh
202403: 95.67 €/MWh
...
```

---

## 9. Checklist Implementazione

### Pre-implementazione
- [ ] Ottenute credenziali GME (Login/Password)
- [ ] Testato endpoint autenticazione
- [ ] Verificati limiti account con GetMyQuotas

### Implementazione
- [ ] Sistema di gestione token JWT
- [ ] Decodifica Base64 implementata
- [ ] Decompressione ZIP implementata
- [ ] Parser JSON implementato
- [ ] Filtro Zone="PUN" implementato

### Ottimizzazione
- [ ] Chiamate raggruppate (mensili/trimestrali)
- [ ] Rate limiting gestito
- [ ] Retry logic con backoff
- [ ] Logging errori
- [ ] Cache risultati (opzionale)

### Post-implementazione
- [ ] Test con periodo breve (1 settimana)
- [ ] Test con periodo lungo (1 anno)
- [ ] Validazione medie calcolate
- [ ] Monitoraggio consumo quote

---

## 10. FAQ

**Q: Posso richiedere più di 5 anni in una call?**  
A: Sì, se non superi MaxDataPerHour. Calcola: anni × 365 × 24 × 6 campi.

**Q: Il PUN include tutte le zone?**  
A: No, devi filtrare `Zone="PUN"`. La risposta include tutte le zone geografiche.

**Q: Come gestisco l'ora 25?**  
A: L'ora 25 appare nel passaggio da ora legale a solare. Rappresenta l'ora ripetuta.

**Q: Posso avere dati a 15 minuti storici?**  
A: No, la granularità <60min è disponibile solo dal 1° Ottobre 2025.

**Q: Quanto durano i token JWT?**  
A: Non specificato. Implementa re-autenticazione su errore 401.

**Q: Il ContentResponse è sempre Base64?**  
A: Sì, il documento specifica "sempre una stringa che codifica il contenuto in base64".

---

## 11. Riferimenti

- **Documentazione API**: https://www.mercatoelettrico.org/Portals/0/Documents/it-IT/20251015Manuale_tecnico_API.pdf
- **Pagina Prezzi Zonali MGP**: https://www.mercatoelettrico.org/it-it/Home/Esiti/Elettricita/MGP/Esiti/PrezziZonali
- **Endpoint Base**: https://api.mercatoelettrico.org/request

---

## 12. Esempio Completo

### Request Flow Completo

```json
// 1. AUTENTICAZIONE
POST /api/v1/Auth
{
  "Login": "user@example.com",
  "Password": "SecurePass123"
}

// Response
{
  "Success": true,
  "JWT": "eyJhbGc..."
}

// 2. VERIFICA QUOTE
GET /api/v1/GetMyQuotas
Header: Authorization: Bearer eyJhbGc...

// 3. RICHIESTA DATI PUN (Ultimi 12 mesi)
POST /api/v1/RequestData
Header: Authorization: Bearer eyJhbGc...
{
  "Platform": "PublicMarketResults",
  "Segment": "MGP",
  "DataName": "ME_ZonalPrices",
  "IntervalStart": "20230101",
  "IntervalEnd": "20231231",
  "Attributes": {}
}

// Response
{
  "RequestId": "req_001",
  "FormatType": ".json.zip",
  "ResultRequest": "Success",
  "ContentResponse": "UEsDBBQAAAAIAO..."
}

// 4. DECODE & PROCESS
// Base64 decode → ZIP extract → JSON parse → Filter Zone="PUN"

// 5. RISULTATO FINALE
[
  {"FlowDate": 20230101, "Hour": 1, "Zone": "PUN", "Price": 120.5},
  {"FlowDate": 20230101, "Hour": 2, "Zone": "PUN", "Price": 115.3},
  ...
]
```

---

## Note Finali

Questa guida copre **esclusivamente** il recupero dei dati PUN tramite l'API GME. Per altri mercati o dati (Gas, Ambiente, ecc.) consulta il manuale tecnico completo.

**Ultima revisione documento GME**: 15/10/2025