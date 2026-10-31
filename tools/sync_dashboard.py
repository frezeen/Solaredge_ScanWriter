#!/usr/bin/env python3
"""Allinea grafana/dashboard-solaredge.json alla dashboard viva di Grafana.

Nessun git, nessun commit: scrive il file (o dice se e' diverso).
Lo chiama l'hook .git/hooks/pre-commit, cosi' ogni nostro commit porta la
dashboard aggiornata; il push resta una decisione umana.

    python3 tools/sync_dashboard.py --check   # dice se il file e' indietro
    python3 tools/sync_dashboard.py           # riscrive il file da Grafana
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DASH_FILE = ROOT / 'grafana' / 'dashboard-solaredge.json'


def load_env():
    env = ROOT / '.env'
    if not env.exists():
        return
    for line in env.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        os.environ.setdefault(k.strip(), v)


def normalise(resource):
    """Scarta i metadati volatili: uid, resourceVersion e generazione cambiano a ogni
    salvataggio e farebbero rumore nel diff senza dire niente."""
    md = resource.get('metadata', {}) or {}
    return {
        'kind': resource.get('kind', 'Dashboard'),
        'apiVersion': resource.get('apiVersion'),
        'metadata': {
            'name': md.get('name'),
            'namespace': md.get('namespace', 'default'),
            'labels': md.get('labels', {}),
        },
        'spec': resource.get('spec', {}),
    }


def main():
    check_only = '--check' in sys.argv
    dash_file = DASH_FILE
    if '--file' in sys.argv:
        dash_file = Path(sys.argv[sys.argv.index('--file') + 1])
    load_env()

    import requests

    url = os.environ.get('GRAFANA_URL', 'http://localhost:3000')
    auth = (os.environ.get('GRAFANA_USER', 'admin'), os.environ.get('GRAFANA_PASSWORD', ''))

    if not dash_file.exists():
        print('dashboard: file mancante:', dash_file)
        return 2

    disk = json.loads(dash_file.read_text(encoding='utf-8'))
    uid = (disk.get('metadata') or {}).get('name')
    api = f"{url}/apis/dashboard.grafana.app/v2/namespaces/default/dashboards/{uid}"

    try:
        r = requests.get(api, auth=auth, timeout=10)
    except Exception as e:
        print('dashboard: Grafana non raggiungibile:', e)
        return 2
    if r.status_code != 200:
        print('dashboard: Grafana ha risposto', r.status_code)
        return 2

    live = normalise(r.json())
    same = live == normalise(disk)

    if check_only:
        print('dashboard: allineata' if same else 'dashboard: il file e\' indietro rispetto a Grafana')
        return 0 if same else 1

    if same:
        return 0

    dash_file.write_text(json.dumps(live, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print('dashboard: file riscritto da Grafana')
    return 0


if __name__ == '__main__':
    sys.exit(main())
