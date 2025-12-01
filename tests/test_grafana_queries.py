"""
Test performance di tutte le query Grafana
Estrae le query dal JSON della dashboard e le esegue misurando i tempi
"""

import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime
from influxdb_client import InfluxDBClient
from dotenv import load_dotenv

# Carica .env
load_dotenv()

# Config InfluxDB
INFLUXDB_URL = os.getenv("INFLUXDB_URL")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG")

def load_dashboard_json(filepath):
    """Carica il JSON della dashboard"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def replace_grafana_variables(query):
    """Sostituisce le variabili Grafana con valori reali"""
    from datetime import datetime, timedelta
    
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    replacements = {
        '${__range_s}s': '86400s',
        '${__range_ms}ms': '86400000ms',
        '${__from}': str(int(today_start.timestamp() * 1000)),
        '${__to}': str(int(now.timestamp() * 1000)),
        '$__from': str(int(today_start.timestamp() * 1000)),
        '$__to': str(int(now.timestamp() * 1000)),
        '${__interval}': '1m',
        '${__interval_ms}': '60000',
        '$__interval': '1m',
        '$__interval_ms': '60000',
        'start: ${__from:date:iso}': f'start: {today_start.isoformat()}Z',
        'stop: ${__to:date:iso}': f'stop: {now.isoformat()}Z',
        'start: $__from': f'start: {today_start.isoformat()}Z',
        'stop: $__to': f'stop: {now.isoformat()}Z',
    }
    
    for var, value in replacements.items():
        query = query.replace(var, value)
    
    return query

def extract_flux_queries(dashboard):
    """Estrae tutte le query Flux dalla dashboard"""
    queries = []
    
    panels = dashboard.get('panels', [])
    
    for panel in panels:
        panel_title = panel.get('title', 'Untitled')
        panel_id = panel.get('id', 'unknown')
        panel_type = panel.get('type', 'unknown')
        
        if panel_type == 'row':
            continue
        
        targets = panel.get('targets', [])
        
        for idx, target in enumerate(targets):
            query_text = target.get('query', '')
            ref_id = target.get('refId', f'Query{idx}')
            
            if query_text and 'from(bucket:' in query_text:
                query_text = replace_grafana_variables(query_text)
                
                queries.append({
                    'panel_id': panel_id,
                    'panel_title': panel_title,
                    'panel_type': panel_type,
                    'query_index': idx,
                    'ref_id': ref_id,
                    'query': query_text
                })
    
    return queries

def execute_query_with_timing(client, query):
    """Esegue una query e misura il tempo"""
    query_api = client.query_api()
    
    start_time = time.time()
    
    try:
        result = query_api.query(query)
        
        end_time = time.time()
        execution_time = (end_time - start_time) * 1000  # ms
        
        record_count = 0
        table_count = 0
        
        for table in result:
            table_count += 1
            record_count += len(table.records)
        
        return {
            'success': True,
            'execution_time': execution_time,
            'record_count': record_count,
            'table_count': table_count,
            'error': None
        }
        
    except Exception as e:
        end_time = time.time()
        execution_time = (end_time - start_time) * 1000
        
        return {
            'success': False,
            'execution_time': execution_time,
            'record_count': 0,
            'table_count': 0,
            'error': str(e)[:100]
        }

def analyze_dashboard(dashboard_path):
    """Analizza tutte le query della dashboard"""
    print("=" * 80)
    print("GRAFANA QUERY PERFORMANCE TESTER")
    print("=" * 80)
    
    # Carica dashboard
    print("[>>>] Loading Grafana dashboard...")
    dashboard = load_dashboard_json(dashboard_path)
    dashboard_title = dashboard.get('title', 'Unknown')
    
    # Estrai query
    print("[>>>] Extracting Flux queries...")
    queries = extract_flux_queries(dashboard)
    print(f"[OK] Found {len(queries)} queries to test\n")
    
    if not queries:
        print("[!!!] No Flux queries found in dashboard!")
        return
    
    # Connetti a InfluxDB
    print("[>>>] Running performance tests...\n")
    client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
    
    results = []
    
    for i, query_info in enumerate(queries, 1):
        panel_title = query_info['panel_title']
        panel_id = query_info['panel_id']
        ref_id = query_info['ref_id']
        query = query_info['query']
        
        print(f"[{i}/{len(queries)}] [i] Testing Panel {panel_id}: {panel_title} (Ref: {ref_id})")
        
        result = execute_query_with_timing(client, query)
        
        if result['success']:
            print(f"    [OK] {result['execution_time']:.2f}ms - {result['record_count']} records\n")
        else:
            print(f"    [FAIL] {result['error']}\n")
        
        results.append({
            **query_info,
            **result
        })
    
    client.close()
    
    # Report finale
    print("\n" + "=" * 80)
    print("PERFORMANCE TEST SUMMARY")
    print("=" * 80)
    
    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]
    
    print(f"\nTotal Queries:     {len(results)}")
    print(f"Successful:        {len(successful)}")
    print(f"Failed:            {len(failed)}")
    
    if successful:
        times = [r['execution_time'] for r in successful]
        print(f"\nExecution Times:")
        print(f"  Min:             {min(times):.2f} ms")
        print(f"  Max:             {max(times):.2f} ms")
        print(f"  Average:         {sum(times)/len(times):.2f} ms")
        print(f"  Total:           {sum(times):.2f} ms")
        
        # Top 5 slowest
        sorted_results = sorted(successful, key=lambda x: x['execution_time'], reverse=True)
        print(f"\nTop 5 Slowest Queries:")
        for i, r in enumerate(sorted_results[:5], 1):
            print(f"  {i}. Panel {r['panel_id']}: {r['panel_title']}")
            print(f"     Query: {r['ref_id']}")
            print(f"     {r['execution_time']:.2f} ms - {r['record_count']} records")
    
    print("\n" + "=" * 80)
    
    # Salva report
    report_file = "query_performance_report.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n[OK] Detailed report saved to: {report_file}")

if __name__ == "__main__":
    dashboard_path = "grafana/dashboard-solaredge.json"
    
    if not os.path.exists(dashboard_path):
        print(f"[!!!] Dashboard file not found: {dashboard_path}")
        sys.exit(1)
    
    try:
        analyze_dashboard(dashboard_path)
    except KeyboardInterrupt:
        print("\n\n[!!!] Test interrupted by user")
    except Exception as e:
        print(f"\n[!!!] Error: {e}")
        import traceback
        traceback.print_exc()
