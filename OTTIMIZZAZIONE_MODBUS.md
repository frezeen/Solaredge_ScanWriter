# 🔧 Ottimizzazione Modbus per Ridurre CPU

## Problema Identificato
- Polling Modbus ogni 5 secondi con 130+ metriche
- Causa: 1560 letture Modbus/minuto
- Risultato: 8% CPU costante

## Soluzioni (in ordine di efficacia)

### ✅ Soluzione 1: Aumenta Intervallo (FACILE)

**Nel file `.env`:**
```bash
LOOP_REALTIME_INTERVAL_SECONDS=30  # Da 5 a 30 secondi
```

**Impatto:**
- Letture: da 1560/min a 260/min (-83%)
- CPU attesa: da 8% a ~2-3%
- Dati: ancora molto frequenti (ogni 30s)

---

### ✅ Soluzione 2: Disabilita Metriche Inutili (OTTIMALE)

**Nel file `config/sources/modbus_endpoints.yaml`:**

Disabilita metriche che probabilmente non ti servono:

```yaml
meters:
  enabled: true
  measurements:
    # DISABILITA tutte le energie reattive (inutili per uso domestico)
    import_energy_reactive_q1:
      enabled: false  # Da true a false
    import_energy_reactive_q2:
      enabled: false
    export_energy_reactive_q3:
      enabled: false
    export_energy_reactive_q4:
      enabled: false
    
    # DISABILITA energie reattive per fase (L1, L2, L3)
    l1_import_energy_reactive_q1:
      enabled: false
    l1_import_energy_reactive_q2:
      enabled: false
    l1_export_energy_reactive_q3:
      enabled: false
    l1_export_energy_reactive_q4:
      enabled: false
    # ... ripeti per L2 e L3
    
    # DISABILITA energie apparenti se non ti servono
    export_energy_apparent:
      enabled: false
    import_energy_apparent:
      enabled: false
    l1_export_energy_apparent:
      enabled: false
    l1_import_energy_apparent:
      enabled: false
    # ... ripeti per L2 e L3
    
    # DISABILITA tensioni L-L se hai solo L-N
    voltage_ll:
      enabled: false
    l12_voltage:
      enabled: false
    l23_voltage:
      enabled: false
    l31_voltage:
      enabled: false
```

**Impatto:**
- Metriche: da 130+ a ~50 (-60%)
- CPU attesa: da 8% a ~3-4%
- Dati: mantieni solo quelli utili

---

### ✅ Soluzione 3: Disabilita Meters (SE NON TI SERVONO)

Se ti bastano i dati dell'inverter:

```yaml
meters:
  enabled: false  # Disabilita completamente i meters
```

**Impatto:**
- Metriche: da 130+ a ~50 (solo inverter)
- CPU attesa: da 8% a ~4%

---

### ✅ Soluzione 4: Combinazione (MIGLIORE)

Combina le soluzioni per risultato ottimale:

1. **Aumenta intervallo a 15 secondi** (compromesso tra 5 e 30)
2. **Disabilita metriche inutili** (energie reattive, apparenti)
3. **Mantieni solo metriche essenziali**:
   - Potenze (W, VA, VAr)
   - Tensioni L-N
   - Correnti
   - Energie attive (import/export)

**Impatto totale:**
- CPU attesa: ~2-3%
- Dati: ancora molto dettagliati e frequenti
- Riduzione: -70% CPU

---

## 🎯 Metriche Essenziali Consigliate

### Inverter (mantieni):
- ✅ Potenze (power_ac, power_dc, power_apparent, power_reactive)
- ✅ Tensioni (voltage_dc, l1_voltage, l1n_voltage)
- ✅ Correnti (current, current_dc, l1_current)
- ✅ Energia totale (energy_total)
- ✅ Temperatura (temperature)
- ✅ Status (status)
- ✅ Frequenza (frequency)

### Inverter (disabilita se non servono):
- ❌ Tutti i campi "advanced_power_control"
- ❌ Tutti i campi "export_control"
- ❌ vendor_status, rrcr_state
- ❌ commit_power_control_settings

### Meters (mantieni):
- ✅ Potenze per fase (l1_power, l2_power, l3_power)
- ✅ Tensioni L-N (l1n_voltage, l2n_voltage, l3n_voltage)
- ✅ Correnti per fase (l1_current, l2_current, l3_current)
- ✅ Energie attive (import_energy_active, export_energy_active)
- ✅ Energie attive per fase (l1_import_energy_active, etc.)

### Meters (disabilita):
- ❌ Tutte le energie reattive Q1-Q4
- ❌ Tutte le energie apparenti
- ❌ Tensioni L-L (se hai L-N)
- ❌ Fattori di potenza per fase (se non ti servono)

---

## 📝 Script Automatico per Disabilitare Metriche

Crea questo script per disabilitare automaticamente le metriche inutili:

```python
#!/usr/bin/env python3
import yaml

config_file = 'config/sources/modbus_endpoints.yaml'

with open(config_file, 'r') as f:
    config = yaml.safe_load(f)

# Metriche da disabilitare
disable_patterns = [
    'reactive_q1', 'reactive_q2', 'reactive_q3', 'reactive_q4',
    'apparent_energy', 'voltage_ll', 'l12_voltage', 'l23_voltage', 'l31_voltage',
    'advanced_power_control', 'export_control', 'vendor_status', 'rrcr_state'
]

# Disabilita metriche che matchano i pattern
for endpoint in ['inverter_realtime', 'meters']:
    if endpoint in config['modbus']['endpoints']:
        measurements = config['modbus']['endpoints'][endpoint].get('measurements', {})
        for metric_name, metric_config in measurements.items():
            if any(pattern in metric_name for pattern in disable_patterns):
                metric_config['enabled'] = False
                print(f"Disabilitato: {endpoint}.{metric_name}")

# Salva configurazione
with open(config_file, 'w') as f:
    yaml.dump(config, f, default_flow_style=False, allow_unicode=True, indent=2)

print("\n✅ Configurazione ottimizzata salvata!")
```

---

## 🚀 Raccomandazione Finale

**Configurazione ottimale per LXC Debian:**

```bash
# .env
LOOP_REALTIME_INTERVAL_SECONDS=15  # Ogni 15 secondi (compromesso)
```

```yaml
# modbus_endpoints.yaml
modbus:
  enabled: true
  endpoints:
    inverter_realtime:
      enabled: true
      # Disabilita solo metriche avanzate non essenziali
    
    meters:
      enabled: true
      # Disabilita energie reattive e apparenti
```

**Risultato atteso:**
- CPU: ~2-3% (da 8%)
- Dati: ogni 15 secondi (da 5)
- Metriche: ~60 essenziali (da 130+)
- Riduzione: -70% CPU, -50% metriche

Perfetto equilibrio tra dettaglio e performance! 🎯
