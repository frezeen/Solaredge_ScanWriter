#!/bin/bash
# Script per verificare configurazione bucket InfluxDB

source .env 2>/dev/null || { echo "❌ File .env non trovato"; exit 1; }

echo "🗄️ Verifica Configurazione Bucket InfluxDB"
echo "=========================================="
echo ""
echo "📋 Configurazione:"
echo "  URL: $INFLUXDB_URL"
echo "  Org: $INFLUXDB_ORG"
echo "  Bucket principale: $INFLUXDB_BUCKET"
echo "  Bucket realtime: $INFLUXDB_BUCKET_REALTIME"
echo ""

if command -v curl &> /dev/null; then
    echo "🔍 Verifica connessione InfluxDB..."
    if curl -s "$INFLUXDB_URL/health" >/dev/null 2>&1; then
        echo "✅ InfluxDB raggiungibile"
        
        if command -v jq &> /dev/null; then
            echo ""
            echo "📦 Bucket esistenti:"
            BUCKETS=$(curl -s -H "Authorization: Token $INFLUXDB_TOKEN" "$INFLUXDB_URL/api/v2/buckets" 2>/dev/null)
            
            if echo "$BUCKETS" | jq -e '.buckets' >/dev/null 2>&1; then
                echo "$BUCKETS" | jq -r '.buckets[] | "  • \(.name) (retention: \(if .retentionRules[0].everySeconds then "\(.retentionRules[0].everySeconds)s" else "infinite" end))"' 2>/dev/null || echo "  Errore parsing bucket"
            else
                echo "  ❌ Errore recupero bucket (verifica token)"
            fi
        else
            echo "  ⚠️  jq non installato - installa per dettagli bucket"
        fi
    else
        echo "❌ InfluxDB non raggiungibile"
    fi
else
    echo "⚠️  curl non disponibile - verifica manuale necessaria"
fi

echo ""
echo "💡 I bucket vengono creati automaticamente durante l'installazione"
