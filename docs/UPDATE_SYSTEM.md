# Sistema di Update - SolarEdge Data Collector

## Utilizzo

### Aggiornamento Standard
```bash
./update.sh
```

Il sistema:
- Controlla aggiornamenti disponibili
- Preserva configurazioni locali durante l'aggiornamento
- Applica aggiornamenti Git in modo sicuro
- Corregge permessi automaticamente
- Riavvia il servizio se necessario

## File Preservati Automaticamente

- `.env` - Variabili d'ambiente
- `config/main.yaml` - Configurazione principale
- `config/sources/*.yaml` - Endpoint API/Web/Modbus

## Comandi

```bash
# Aggiornamento normale
./update.sh

# Solo controllo aggiornamenti (senza applicare)
python3 scripts/smart_update.py --check-only

# Aggiornamento forzato
python3 scripts/smart_update.py --force
```

## Note

Il sistema preserva automaticamente le configurazioni locali durante l'aggiornamento. Non è necessario fare backup manuali.