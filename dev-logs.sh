#!/bin/bash
# Script per visualizzare log in tempo reale
# Uso: ./dev-logs.sh [servizio]

SERVICE=${1:-solaredge}

echo "📋 Log in tempo reale per: $SERVICE"
echo "=================================="
echo "Premi Ctrl+C per uscire"
echo ""

case $SERVICE in
    "all"|"tutto")
        docker compose logs -f
        ;;
    "solaredge"|"app")
        docker compose logs -f solaredge
        ;;
    "influx"|"influxdb")
        docker compose logs -f influxdb
        ;;
    "grafana")
        docker compose logs -f grafana
        ;;
    *)
        echo "Servizi disponibili:"
        echo "  all/tutto  - Tutti i servizi"
        echo "  solaredge  - Solo SolarEdge (default)"
        echo "  influx     - Solo InfluxDB"
        echo "  grafana    - Solo Grafana"
        echo ""
        echo "Uso: ./dev-logs.sh [servizio]"
        exit 1
        ;;
esac