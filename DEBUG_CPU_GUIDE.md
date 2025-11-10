# 🔍 Guida Diagnosi Utilizzo CPU Alto (8%)

## Situazione Attuale
- CPU utilizzata: ~8% (ancora troppo alto per idle)
- Correzioni applicate: sleep intelligente in GUI e loop_orchestrator
- Problema: Qualcos'altro sta consumando CPU

## 🎯 Metodi di Diagnosi (in ordine di efficacia)

### Metodo 1: cProfile (PIÙ PRECISO) ⭐⭐⭐⭐⭐

**Cosa fa**: Profila esattamente dove viene speso il tempo CPU

**Come usare**:
```bash
# Nel container o sulla macchina
python debug_cpu_profile.py

# Lascia girare per 60 secondi, poi premi Ctrl+C
# Guarda il report in logs/cpu_profile_report.txt
```

**Cosa cercare nel report**:
- Funzioni con alto `cumtime` (tempo cumulativo)
- Funzioni chiamate molte volte (`ncalls`)
- Funzioni con alto `tottime` (tempo proprio)

---

### Metodo 2: py-spy (NON INVASIVO) ⭐⭐⭐⭐

**Cosa fa**: Sampling profiler che non rallenta il programma

**Come usare**:
```bash
# Trova il PID del processo
ps aux | grep "python.*main.py"

# Installa py-spy
pip install py-spy

# Profila per 60 secondi
py-spy record --pid <PID> --duration 60 --output logs/cpu_flamegraph.svg

# Apri logs/cpu_flamegraph.svg con un browser
```

**Cosa cercare**:
- Funzioni che occupano molto spazio nel flame graph
- Pattern ripetitivi (indicano loop)

---

### Metodo 3: Monitoring Thread/Tasks ⭐⭐⭐

**Cosa fa**: Mostra thread attivi e utilizzo risorse

**Come usare**:
```bash
# Snapshot singolo
python debug_threads_tasks.py

# Monitoraggio continuo
python debug_threads_tasks.py --continuous
```

**Cosa cercare**:
- Troppi thread attivi (>10 è sospetto)
- Thread che non dovrebbero esistere
- Connessioni di rete aperte inutilmente

---

### Metodo 4: Verifica Polling Modbus ⭐⭐

**Cosa fa**: Verifica se il polling realtime ogni 5s causa problemi

**Come usare**:
```bash
# Avvia main.py in un terminale
python main.py

# In un altro terminale, monitora
python debug_check_modbus.py
```

**Cosa cercare**:
- Picchi CPU ogni ~5 secondi → problema realtime
- CPU costante alta → problema busy-wait

---

## 🔧 Possibili Cause Rimanenti

### 1. **Logging Eccessivo**
```bash
# Verifica log level nel .env
grep LOG_LEVEL .env

# Dovrebbe essere INFO o WARNING, non DEBUG
```

**Fix**: Imposta `LOG_LEVEL=WARNING` nel .env

---

### 2. **Operazioni Modbus Troppo Frequenti**
Il realtime polling ogni 5 secondi potrebbe essere troppo aggressivo.

**Test**: Disabilita temporaneamente realtime:
```yaml
# In config/sources/modbus_endpoints.yaml
modbus:
  enabled: false  # Cambia da true a false
```

Riavvia e verifica se CPU scende. Se sì, il problema è il Modbus.

**Fix permanente**: Aumenta intervallo realtime:
```bash
# Nel .env
LOOP_REALTIME_INTERVAL_SECONDS=30  # Da 5 a 30 secondi
```

---

### 3. **aiohttp Server Overhead**
Il server web GUI potrebbe avere overhead.

**Test**: Avvia senza GUI:
```bash
python main.py --api  # Solo API, niente GUI
```

Se CPU scende, il problema è la GUI/aiohttp.

**Fix**: Verifica se ci sono richieste HTTP continue (polling dal browser)

---

### 4. **ThreadPoolExecutor con Troppi Thread**
Verifica se ci sono troppi thread in background.

**Check**:
```python
# Aggiungi temporaneamente in main.py dopo le import
import threading
print(f"Thread attivi: {threading.active_count()}")
```

**Fix**: Se >10 thread, c'è un leak. Cerca `ThreadPoolExecutor` senza `max_workers` limitato.

---

### 5. **Connessioni HTTP Non Chiuse**
Session HTTP potrebbero non essere chiuse correttamente.

**Check**: Usa `debug_threads_tasks.py` e guarda "Connessioni di rete"

**Fix**: Verifica che tutti i collector usino context manager:
```python
with CollectorAPI(cache=cache) as collector:
    data = collector.collect()
```

---

### 6. **Cache Manager con Troppi File I/O**
Cache potrebbe fare troppi accessi disco.

**Test**: Disabilita cache temporaneamente:
```python
# In main.py, commenta:
# cache = CacheManager()
cache = None
```

Se CPU scende, il problema è la cache.

---

## 📊 Interpretazione Risultati

### Se cProfile mostra:
- **`asyncio.sleep`** alto → Bug nel sleep intelligente
- **`requests.get/post`** alto → Troppe chiamate HTTP
- **`solaredge_modbus`** alto → Modbus troppo lento/frequente
- **`json.loads/dumps`** alto → Troppo parsing JSON
- **`logging`** alto → Log level troppo verboso

### Se py-spy mostra:
- **Flame graph largo in una funzione** → Quella funzione è il problema
- **Molte funzioni piccole ripetute** → Loop inefficiente

---

## 🎯 Azione Immediata Consigliata

**PASSO 1**: Esegui cProfile per 60 secondi
```bash
python debug_cpu_profile.py
```

**PASSO 2**: Guarda il report e identifica la funzione con più `cumtime`

**PASSO 3**: Condividi il report (prime 30 righe) per analisi

---

## 💡 Quick Fixes da Provare Subito

### Fix 1: Aumenta intervallo realtime
```bash
# Nel .env
LOOP_REALTIME_INTERVAL_SECONDS=15  # Da 5 a 15
```

### Fix 2: Riduci log level
```bash
# Nel .env
LOG_LEVEL=WARNING  # Da INFO a WARNING
```

### Fix 3: Disabilita file logging temporaneamente
```bash
# Nel .env
LOG_FILE_LOGGING=false
```

Riavvia dopo ogni fix e verifica CPU.

---

## 📞 Prossimi Passi

1. Esegui `python debug_cpu_profile.py` per 60 secondi
2. Condividi le prime 30 righe del report
3. Analizziamo insieme il bottleneck specifico
4. Applichiamo fix mirato

**Nota**: L'8% potrebbe anche essere normale se:
- Stai raccogliendo dati realtime ogni 5 secondi
- Hai molti dispositivi configurati
- Il sistema è su hardware limitato (Raspberry Pi, LXC con poche risorse)

Ma possiamo sicuramente ottimizzare ulteriormente! 🚀
