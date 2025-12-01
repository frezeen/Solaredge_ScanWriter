# Sistema Web Scan - Riferimento Tecnico

## Panoramica

Questo documento descrive **come funziona tecnicamente il sistema di scansione web** quando si usa `python main.py --scan`. Si concentra esclusivamente sul processo di scansione e generazione della configurazione.

---

## Architettura del Sistema

### Componenti

1. **`WebTreeScanner`** (`tools/web_tree_scanner.py`)
   - Recupera il JSON "tree" dall'API SolarEdge
   - Salva lo snapshot grezzo in `cache/snapshots/web_tree/latest.json`
   - NON modifica alcun file di configurazione

2. **`YawlManager`** (`tools/yawl_manager.py`)
   - Legge lo snapshot da `cache/snapshots/web_tree/latest.json`
   - Estrae le informazioni sui dispositivi in modo ricorsivo
   - Genera `config/sources/web_endpoints.yaml`
   - Preserva gli stati `enabled` esistenti durante la rigenerazione

3. **`scan_flow`** (`flows/scan_flow.py`)
   - Orchestra il processo di scansione
   - Chiama prima `WebTreeScanner.scan()`
   - Poi chiama `YawlManager.generate_web_endpoints_only()`

---

## Comando: `python main.py --scan`

### Cosa Fa

1. **Autentica** al portale di monitoraggio SolarEdge
2. **Recupera** l'endpoint `/services/charts/site/{site_id}/tree`
3. **Salva** lo snapshot JSON grezzo in `cache/snapshots/web_tree/latest.json`
4. **Analizza** lo snapshot per estrarre tutti i dispositivi
5. **Genera** `config/sources/web_endpoints.yaml` con tutti i dispositivi scoperti

### Struttura dello Snapshot

Il JSON `tree` contiene:
- `siteStructure`: Gerarchia principale dei dispositivi (inverter, ottimizzatori, stringhe)
- `meters`: Dispositivi meter
- `storage`: Dispositivi di accumulo batteria
- `evChargers`: Caricatori per veicoli elettrici
- `smartHome`: Dispositivi smart home
- `gateways`: Dispositivi gateway
- `environmental.meteorologicalData`: Stazione meteo

---

## Processo di Generazione YAML

### Estrazione Dispositivi (`YawlManager._extract_devices_recursive`)

Per ogni elemento nell'albero:
1. Verifica se ha `itemId` (indica che è un dispositivo)
2. Estrae:
   - `itemType`: Tipo dispositivo (INVERTER, OPTIMIZER, METER, SITE, STRING, WEATHER)
   - `id`: ID dispositivo
   - `name`: Nome dispositivo
   - `parameters`: Misurazioni disponibili

3. Crea una voce endpoint con questa struttura:
   ```yaml
   {device_type}_{device_id}:
     device_id: "{id}"
     device_name: "{name}"
     device_type: {itemType}
     enabled: {true/false}  # Default: true per OPTIMIZER e WEATHER, false per altri
     category: "{category}"  # Derivato da device_type
     date_range: "{range}"   # Vedi sotto per i range supportati
     measurements:
       {MEASUREMENT_NAME}:
         enabled: {true/false}  # Corrisponde allo stato enabled del dispositivo
   ```

### Mappatura Categorie (`_get_category_for_device`)

| Tipo Dispositivo | Categoria |
|------------------|-----------|
| INVERTER | Inverter |
| METER | Meter |
| SITE | Site |
| STRING | String |
| WEATHER | Weather |
| OPTIMIZER | Optimizer group |

### Gestione Speciale

#### Dispositivi OPTIMIZER e STRING
- Estrae il campo `connectedToInverter`
- Aggiunge `inverter: {inverter_id}` alla configurazione endpoint

#### Dispositivi STRING
- Estrae il campo `identifier` se disponibile e diverso da "0"
- Aggiunge `identifier: {value}` alla configurazione endpoint

#### Dispositivi WEATHER
- Usa sempre `device_id: "weather_default"` indipendentemente dall'ID reale

---

## Preservazione della Configurazione

### Logica di Merge (`_merge_with_existing_config`)

Quando si rigenera `web_endpoints.yaml`:

1. **Carica la configurazione esistente** da `config/sources/web_endpoints.yaml`
2. **Per ogni dispositivo**:
   - Se il dispositivo esiste nella vecchia config: **preserva** il suo stato `enabled`
   - Se il dispositivo esiste nella vecchia config: **preserva** tutti gli stati `enabled` delle misurazioni
   - Se il dispositivo è nuovo: usa lo stato `enabled` **di default** (true per OPTIMIZER/WEATHER, false per altri)

3. **Risultato**: I nuovi dispositivi vengono aggiunti, quelli rimossi vengono eliminati, ma le scelte enabled/disabled dell'utente vengono preservate

---

## Stati Enabled di Default

### Livello Dispositivo

| Tipo Dispositivo | Default Enabled |
|------------------|-----------------|
| OPTIMIZER | ✅ true |
| WEATHER | ✅ true |
| SITE | ✅ true |
| INVERTER | ❌ false |
| METER | ❌ false |
| STRING | ❌ false |

### Livello Misurazione

Tutte le misurazioni ereditano di default lo stato enabled del dispositivo.

---

## Smart Range Mode

Il sistema utilizza una modalità "Smart Range" per ottimizzare le richieste API:

*   **History Mode** (date esplicite):
    *   **Dispositivi Daily/7days** (es. Ottimizzatori, Meteo): Itera giorno per giorno. **Nota**: Lo strumento `HistoryManager` limita di default agli ultimi 7 giorni per evitare un carico API eccessivo.
    *   **Dispositivi Monthly** (es. Site): Itera mese per mese. `HistoryManager` recupera la storia COMPLETA per questi dispositivi in base alla loro configurazione `date_range`.
*   **Loop Mode** (senza date): Usa il campo `date_range` definito in `web_endpoints.yaml`:
    *   `7days`: Richiede gli ultimi 7 giorni (es. per Ottimizzatori).
    *   `monthly`: Richiede dal 1° del mese corrente a oggi (es. per Site).
    *   `daily`: Richiede solo oggi.

Questo garantisce che i dispositivi ad alta risoluzione (Ottimizzatori) abbiano una storia breve ma dettagliata, mentre i dispositivi aggregati (Site) mantengano la coerenza mensile.

---

## Posizioni dei File

### Input
- **Snapshot**: `cache/snapshots/web_tree/latest.json`
  - JSON grezzo dall'API SolarEdge
  - Sovrascritto ad ogni scansione
  - File singolo (senza versioning)

### Output
- **Configurazione**: `config/sources/web_endpoints.yaml`
  - Generato dallo snapshot
  - Preserva gli stati enabled dell'utente
  - Usato da `CollectorWeb` per costruire le richieste API

---

## Dettagli Endpoint API

### Endpoint Tree
```
GET https://monitoring.solaredge.com/services/charts/site/{site_id}/tree
```

**Autenticazione**: Richiede cookie di sessione valido

**Risposta**: Oggetto JSON contenente la gerarchia completa dei dispositivi

**Header Richiesti**:
- `Cookie`: Cookie di sessione dal login
- `X-CSRF-TOKEN`: Token CSRF (se disponibile)
- `Accept`: `application/json`

---

## Come CollectorWeb Usa web_endpoints.yaml

### Costruzione Richieste (`_build_request`)

Per ogni dispositivo abilitato in `web_endpoints.yaml`:

1. **Legge la configurazione del dispositivo**:
   - `device_type`: Usato come `itemType` nella richiesta API
   - `device_id`: Usato come `id`, `originalSerial`, `identifier`
   - Misurazioni abilitate: Aggiunte all'array `measurementTypes`

2. **Costruisce la richiesta API**:
   ```json
   {
     "device": {
       "itemType": "{device_type}",
       "id": "{device_id}",
       "originalSerial": "{device_id}",
       "identifier": "{device_id}"
     },
     "deviceName": "{device_name}",
     "measurementTypes": ["{MEASUREMENT_1}", "{MEASUREMENT_2}", ...]
   }
   ```

3. **Casi speciali**:
   - **STRING**: Aggiunge il campo `connectedToInverter`
   - **WEATHER**: Omette i campi `id`, `originalSerial`, `identifier`

### Parametri Date Range

Attualmente, `CollectorWeb._get_date_params()` restituisce:
```python
{
    "start-date": "{date}",  # Singolo giorno
    "end-date": "{date}"     # Stesso giorno
}
```

**IMPORTANTE**: Questa è un'impostazione **globale** - tutti i dispositivi usano lo stesso intervallo di date.

---

## Estendere il Sistema

### Aggiungere Parametri Personalizzati ai Dispositivi

Per aggiungere parametri personalizzati (come `date_range`) ai dispositivi:

1. **Modifica `YawlManager._create_device_endpoint()`**:
   - Aggiungi il nuovo campo al dizionario endpoint
   - Imposta il valore di default in base al tipo di dispositivo o altri criteri

2. **Modifica `CollectorWeb`**:
   - Leggi il parametro personalizzato dalla configurazione del dispositivo
   - Usalo quando costruisci le richieste API

3. **Aggiorna questa documentazione**:
   - Documenta lo scopo del nuovo parametro
   - Spiega come influisce sulle chiamate API
   - Fornisci esempi

### Esempio: Aggiungere il Parametro `date_range`

**Step 1**: Modifica `YawlManager._create_device_endpoint()` (riga ~60):
```python
# Dopo aver impostato 'category'
if device_type == 'SITE':
    endpoint['date_range'] = 'monthly'  # Range personalizzato per SITE
else:
    endpoint['date_range'] = 'daily'    # Default per gli altri
```

**Step 2**: Modifica `CollectorWeb._fetch_batch()` per leggerlo e usarlo:
```python
def _fetch_batch(self, device_type: str, batch: List[Dict[str, Any]]) -> List:
    # Leggi date_range dal primo dispositivo nel batch
    date_range = batch[0].get('date_range', 'daily') if batch else 'daily'
    
    # Modifica _get_date_params per accettare e usare date_range
    params = self._get_date_params(
        getattr(self, '_target_date', None),
        date_range=date_range
    )
    # ... resto del codice
```

**Step 3**: Aggiorna la firma e logica di `_get_date_params()`:
```python
def _get_date_params(self, target_date: str = None, date_range: str = 'daily') -> Dict[str, str]:
    # ... calcola le date in base al parametro date_range
```

---

## Note Importanti

### Ciclo di Vita dello Snapshot
- **Singolo snapshot**: Viene mantenuto solo `latest.json`
- **Nessun versioning**: Ogni scansione sovrascrive lo snapshot precedente
- **Nessuna cronologia**: Le vecchie configurazioni dei dispositivi vengono perse se non presenti nella nuova scansione

### Preservazione della Configurazione
- **Stati enabled**: Sempre preservati tra le scansioni
- **Nuovi dispositivi**: Aggiunti con stato enabled di default
- **Dispositivi rimossi**: Eliminati dalla configurazione
- **Modifiche alle misurazioni**: Nuove misurazioni aggiunte, quelle rimosse eliminate

### Frequenza di Scansione
- **Solo manuale**: La scansione viene attivata dal comando `--scan`
- **Nessuna scansione automatica**: Il sistema non rileva automaticamente nuovi dispositivi
- **Responsabilità dell'utente**: Deve eseguire la scansione dopo aver aggiunto/rimosso dispositivi fisici

---

## Risoluzione Problemi

### Scansione Fallisce con HTTP 401/403
- **Causa**: Cookie di sessione scaduto o non valido
- **Soluzione**: Il Collector tenterà il re-login automatico

### web_endpoints.yaml Generato Vuoto
- **Causa**: File snapshot mancante o vuoto
- **Soluzione**: Esegui `python main.py --scan` per creare un nuovo snapshot

### Dispositivo Non Appare nel YAML
- **Causa**: Il dispositivo non ha `parameters` nel JSON tree
- **Soluzione**: Verifica se il dispositivo è configurato correttamente nel portale SolarEdge

### Stati Enabled Ripristinati al Default
- **Causa**: ID dispositivo cambiato (es. dispositivo sostituito)
- **Soluzione**: Riabilita manualmente in `web_endpoints.yaml`

---

## Riepilogo

Il sistema di scansione web è un **processo a due fasi**:

1. **Fase di Scansione** (`WebTreeScanner`):
   - Recupera l'albero dei dispositivi grezzo dall'API
   - Salva nel file snapshot
   - Nessuna modifica alla configurazione

2. **Fase di Generazione** (`YawlManager`):
   - Analizza lo snapshot
   - Estrae dispositivi e misurazioni
   - Genera la configurazione YAML
   - Preserva gli stati enabled dell'utente

**Principio Chiave**: Il sistema **scopre** i dispositivi automaticamente ma **rispetta** le scelte di configurazione manuale dell'utente.