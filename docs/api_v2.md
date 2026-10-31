# SolarEdge Monitoring API V2 — riferimento operativo

> Documento di riferimento per lo sviluppo (Solaredge_ScanWriter). Redatto il 2026-10-22 dalle
> pagine ufficiali https://api-docs.solaredge.com/ (sezioni elencate in fondo). I valori di
> chiave/token NON vanno scritti qui: solo nomi delle variabili d'ambiente.

## 1. Scadenze (fermo tutto)

| Data | Cosa |
| --- | --- |
| **2026-11-01** | V1 ritirata secondo l'errore restituito dal gateway (`Scheduled V1 deprecation window`); l'abbonamento ai tier a pagamento inizia a fatturare |
| **2026-11-03** | V1 "smette di rispondere" secondo la pagina di migrazione (finestra 1–3 nov 2026, le due fonti discordano di 2 giorni) |
| Fino al 2026-11-01 | tutti i tier Business Starter/Pro/Growth sono gratuiti (checkout tramite SolarEdge Store, carta di credito, poi le quote compaiono nel developer console) |

⚠️ Dalla migrazione il collector parla solo V2: nel codice non è rimasta traccia della V1 e la
sua chiave (`?api_key=…`) non funziona su V2. Le date qui sopra restano la ragione della migrazione.

## 2. Base URL e autenticazione

- Base: `https://monitoringapi.solaredge.com/v2/` — percorsi **plurali** come `/sites/{id}/…`
- Due modalità di accesso, un header ciascuna:

| Access type | Header | Valore |
| --- | --- | --- |
| Fleet Access | `X-API-Key` | App API Key (chiave statica dell'app, nessun token) |
| Site Access | `Authorization` | `Bearer {access_token}` (OAuth 2.0) |

- Scopes OAuth: `SITE_DATA` (metadati sito + misure aggregate), `DEVICE_DATA` (dati di
  dispositivo). Le chiavi Fleet portano implicitamente entrambi gli scope.
- L'Advanced Monitoring API (Live Power Flow, Weather Guard, Battery Backup Reserve) è gated
  per-destination ai soli tier Business Pro/Enterprise.
- Il portale self-serve (client id/secret per OAuth) è https://developer.solaredge.com/.

### Path A — OAuth 2.0 Authorization Code (Site Access)

1. Autorizzazione: `https://connect.solaredge.com/authorize?client_id=…` (+ opzionale
   `external_id`); il callback riceve `code`, `site_id`, `external_id`.
2. Token: `POST https://monitoringapi.solaredge.com/v2/oauth2/token` con body JSON
   `{"grant_type":"authorization_code", …}` → `expires_in` **7200 s**.
3. Refresh: ogni refresh restituisce access_token **e** refresh_token **nuovi**, il vecchio
   refresh_token diventa invalido (rotation obbligatoria: persistere sempre la coppia nuova).
4. Revoca: `POST /v2/oauth2/revoke-token` con `{"token": …}`.
5. Richiede consenso esplicito del proprietario del sito, per sito (via SolarEdge Connect).

### Path B — Fleet API Key via account association

Per siti di proprietà dell'installer: l'account viene associato all'app e si usa una chiave Fleet
(`X-API-Key`), senza consenso del homeowner. È la via praticabile per flotte gestite.

### Scegliere

- Proprietario homeowner che autorizza l'app → OAuth (Path A).
- Siti dell'installer / account aziendale condiviso → Fleet key (Path B).
- Chiave "Account" V1 → nuova V2 Fleet key.

## 3. Tier, crediti e rate limit

| Tier | Prezzo/mese | Crediti/mese | CPM | Max app |
| --- | --- | --- | --- | --- |
| Free | $0 | 2.000 | 10 | 1 |
| Business Starter | $100 | 20.000 | 25 | 1 |
| Business Growth | $400 | 100.000 | 50 | 3 |
| Business Pro | $1.000 | 400.000 | 100 | 5 |
| Enterprise | custom | custom | custom | custom |

- 1 credito per chiamata (al momento), reset mensile, nessun rollover.
- Crediti esauriti → 429 con body `{"message":"API rate limit…"/"Monthly credit limit reached."}`;
  la pagina migrazione documenta anche `402` credit-limit.
- Overage opt-in fino a 1.5× al costo di $0.01/credito (non disponibile sul Free).
- CPM è **per account**, condiviso tra tutte le Application. Budget: ~70% steady-state, ~30% burst,
  mai al 100%.
- Header di risposta: `x-ratelimit-limit-minute`, `x-ratelimit-remaining-minute` — leggerli e
  tenere un contatore locale per-minuto come throttle preventivo.

## 4. Mapping endpoint V1 → V2

| V1 | V2 |
| --- | --- |
| `GET /sites/list` | `GET /v2/sites` |
| `/site/{id}/details` | `/v2/sites/{id}` |
| `/site/{id}/dataPeriod` | `/v2/sites/{id}/energy` con `from`/`to` |
| `/site/{id}/energy` | `/v2/sites/{id}/energy` |
| `/site/{id}/currentPowerFlow` (overview) | `GET /v2/sites/{id}/power` con `from`/`to` recenti |
| `/equipment/{siteId}/list` | `/v2/sites/{id}/devices?type=INVERTER` |
| inventory | `/v2/sites/{id}/devices?type=INVERTER\|METER\|BATTERY\|GATEWAY` (senza type: tutti) |
| `/equipment/{siteId}/{sn}/data` | `/v2/sites/{id}/inverters/{sn}/telemetry` (più inverter: `serialNumbers` separati da virgola) oppure `…/inverters/status` |
| lifetime energy | `GET /v2/sites/{id}/inverters/lifetime-energy` (contatori on-board) |
| meter lifetime | `GET /v2/sites/{id}/meters/lifetime-energy` (tutti i meter o per meter) |

- I percorsi multi-sito "bulk" della V1 non esistono più; l'equipment è ripiegato dentro
  `/sites/{id}/devices/…`.
- `…/inverters/status`: bucket a quarto d'ora con **ultimo valore noto, non medie**; per finestra
  per chiamata: `QUARTER_OF_AN_HOUR` ≤ 1 settimana, `HOUR` ≤ 24 ore.

## 5. Parametri temporali e risposta

- `from`/`to`: ISO-8601 **completi con fuso** (`Z` o offset, es. `+02:00`); senza fuso → 404.
- I timestamp restituiti sono nell'**ora locale del sito** (non UTC).
- `timeUnit=DAY` (V1) → `resolution=DAY` (V2). Enum: quarto d'ora, HOUR, DAY, WEEK, MONTH, YEAR,
  TOTAL (la doc usa sia `QUARTER_OF_AN_HOUR` sia `QUARTER_HOUR` secondo la pagina).
- Envelope di risposta: `{"period", "unit", "resolution", "values":[…]}`.

## 6. Rinomina di campi V1 → V2

| V1 | V2 |
| --- | --- |
| `id` (string) | `siteId` (int) |
| `systemSize` | `peakPower` (kWp) |
| `status` | `activationStatus` ("Active") |
| `currentPower` / `power` (Site Overview) | rimosso → `GET /v2/sites/{id}/power` |
| `lastUpdateData.energy` | `production.total` con from/to |
| `lifeTimeData.energy` | contatori on-board via `/v2/sites/{id}/inverters/lifetime-energy` (può divergere) |
| `benefitsPerYear.envBenefits` | rimosso; resta `co2Reduction` (e equivalente alberi) |
| `systemUnit` (METRIC/IMPERIAL) | `unit` |

Campi V1 inverters **senza equivalente in V2**: `dcVoltage`, potenze apparente/reattiva
(`powerKVA`), `L1Data`/`L2Data`/`L3Data` — in V2 arrivano medie di tensione ecc. al loro posto.

## 7. Paginazione

- `GET /v2/sites` e `GET /v2/alerts` sono paginati.
- Parametri `page` + `sites-in-page` (default 50, **max 1000**) oppure `alerts-in-page`
  (default 50, **max 100**). Iterare page=1,2,… fino a quando restituisce meno di pageSize.

## 8. Formati di errore

- 400/403/404 → RFC 7807 Problem Details, `application/problem+json`.
- 401/405 → JSON "piatto" del gateway: `{"message":…,"request_id":…}` oppure
  `{"error":…,"error_description":…}` (chiave mancante).
- Richieste senza token → `{"error":"invalid_request","error_description":"The access token is missing"}`.
- 429 rate/crediti, 402 credit-limit (vedi §3).

## 9. Aggregazione e polling (credit-efficiency)

Quattro tecniche della pagina ufficiale:

1. **Telemetria bulk** invece di loop di endpoint singoli: `…/inverters/telemetry`,
   `…/meters/telemetry`, `…/storage/telemetry` (con o senza `serialNumbers`) ritornano multi-metrica
   × multi-device × multi-intervalo in una sola chiamata (1 credito). Parametri `from`, `to`,
   `resolution`; risoluzione minima 15 minuti. Per backfill e serie storiche decisamente meglio;
   per alert veri e propri con latenza <15 min usare letture puntuali.
2. **Staggering**: spargere le chiamate nell'ora (sleep = 3600/N + jitter) invece del burst sullo
   zero; tenere subset stabili per worker con hash(site_id) % N_WORKERS.
3. **Cache con invalidazione a evento**: site list TTL 1h, metadati sito 24h, device list 6h,
   site overview ~15 min (il backend si aggiorna ~ogni 15 min), power flow live 15 s; senza
   webhook, rinfrescare la site list quando un telemetry restituisce un siteId sconosciuto.
4. **Prioritizzazione dei siti**: baseline ogni 4 h, siti critici ogni 15 min, burst 15-min per
   1 h dopo un alert → ordine di grandezza di crediti risparmiati rispetto al polling uniforme.

### Esempio "dashboard casa, 1 utente" (nostro caso)

- 15-min polling solo diurno: 1 sito × 4/h × 12 h × 30 gg × 2 endpoint ≈ **2.880 crediti/mese** →
  NON entra nel Free (2.000).
- Workaround realistico: **polling orario solo diurno ≈ 720 crediti/mese** → entra nel Free.
- Alternativa: una sola chiamata telemetry/ora aggregata riduce ulteriormente le chiamate.

### Calcolo per il collector attuale

- Precisazione: il collector `web` è scraping del portale e non consuma crediti; il costo V2
  dipende solo da `collector_api`, che ha abilitati `site_details` e `site_energy_details`
  (`energyDetails`, QUARTER_OF_AN_HOUR). Riproponendo la cadenza attuale su V2 sono ~2
  crediti/15 min (~5.800/mese); ma una sola chiamata a `…/sites/{id}/energy` al giorno con
  tutta la finestra a `resolution=QUARTER_OF_AN_HOUR` (96 bucket) scende a ~30 crediti/mese:
  entra nel Free con ampio margine. Progettare la migrazione su questo, non sulla cadenza attuale.
- Nota: `GET /v2/` senza token risponde `401 invalid_request` "access token missing" già senza
  alcun parametro — lo si può usare come smoke test di raggiungibilità dell'endpoint V2.

## 10. Esempio curl (dalla guida di migrazione, sito di esempio 1148616)

```bash
# V1
curl "https://monitoringapi.solaredge.com/site/1148616/energy?api_key=$V1_KEY&startDate=2026-10-21&endDate=2026-10-22&timeUnit=DAY"
# V2
curl -H "X-API-Key: $V2_FLEET_KEY" \
  "https://monitoringapi.solaredge.com/v2/sites/1148616/energy?from=2026-10-21T00:00:00%2B02:00&to=2026-10-22T00:00:00%2B02:00&resolution=DAY"
# oppure con OAuth Site Access
curl -H "Authorization: Bearer $V2_ACCESS_TOKEN" \
  "https://monitoringapi.solaredge.com/v2/sites/1234567/energy?from=…&to=…&resolution=QUARTER_OF_AN_HOUR"
```

## 11. Note specifiche Solaredge_ScanWriter

- Sito di riferimento: **1234567**; la chiave V1 attiva resta in `.env` (non qui).
- Perimetro migrazione: **solo il `collector_api`** (chiave V1). Il realtime legge l'inverter
  via Modbus locale (<ip-inverter>:1502, nessun costo); il collector `web` è scraping del
  portale (login `/solaredge-apigw/api/login` risponde 410 dal 21/10/2026, sopravvive finché
  il server accetta il vecchio cookie — non migrabile, va sostituito o disattivato).
- Migrazione da pianificare entro il 2026-10-31 per non subire la finestra di deprecazione.
  Primo passo consigliato: creare l'app sul developer console, richiedere la chiave Fleet
  (siti di proprietà installer), provarla su `/v2/sites/1234567` e poi adattare le frequenze
  secondo il §9.
- I bucket InfluxDB realtime storici restano validi: solo la fonte dei dati cambia.

## 12. Fonti

- https://api-docs.solaredge.com/docs/developer-platform/mxj41549n0nxk-migrating-from-v1-to-v2
- https://api-docs.solaredge.com/docs/developer-platform/g09jmvp5t2cok-authentication
- https://api-docs.solaredge.com/docs/developer-platform/pwh8p4k2wtajh-tiers-and-rate-limits
- https://api-docs.solaredge.com/docs/developer-platform/pif9q8f76oz2d-aggregation-and-polling-strategy
- Console: https://developer.solaredge.com/
