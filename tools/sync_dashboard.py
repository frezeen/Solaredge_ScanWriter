#!/usr/bin/env python3
"""Tiene grafana/dashboard-solaredge.json allineato alla dashboard viva.

Gira dal timer solaredge-dashboard-sync: legge la dashboard v2 dal Grafana
locale, la confronta con il file del repo, e solo se e' diversa riscrive il
file, fa un commit di quel solo file e lo pusha.

    python3 tools/sync_dashboard.py --check   # dice se e' allineata, non scrive
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DASH_FILE = ROOT / 'grafana' / 'dashboard-solaredge.json'
VOLATILE = ('resourceVersion', 'generation', 'creationTimestamp', 'managedFields', 'uid')


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
        print('file mancante:', dash_file)
        return 2

    disk = json.loads(dash_file.read_text(encoding='utf-8'))
    uid = (disk.get('metadata') or {}).get('name')
    api = f"{url}/apis/dashboard.grafana.app/v2/namespaces/default/dashboards/{uid}"

    try:
        r = requests.get(api, auth=auth, timeout=10)
    except Exception as e:
        print('Grafana non raggiungibile:', e)
        return 2
    if r.status_code != 200:
        print('Grafana ha risposto', r.status_code)
        return 2

    live = normalise(r.json())
    same = live == normalise(disk)

    if check_only:
        print('allineata' if same else 'DIVERSO: il file e\' indietro rispetto a Grafana')
        return 0 if same else 1

    if same:
        print('allineata, niente da fare')
        return 0

    text = json.dumps(live, indent=2, ensure_ascii=False) + '\n'
    dash_file.write_text(text, encoding='utf-8')
    print('file riscritto da Grafana')

    subprocess.run(['git', 'add', 'grafana/dashboard-solaredge.json'], cwd=ROOT, check=True)
    dirty = subprocess.run(['git', 'diff', '--cached', '--quiet'], cwd=ROOT).returncode != 0
    if not dirty:
        print('nessuna differenza da committare')
        return 0

    subprocess.run(['git', 'commit', '-m', 'chore(dashboard): sync from grafana',
                    '--only', 'grafana/dashboard-solaredge.json'], cwd=ROOT, check=True)
    push = subprocess.run(['git', 'push', 'origin', 'main'], cwd=ROOT, capture_output=True, text=True)
    print('push:', (push.stdout or push.stderr).strip().splitlines()[-1] if (push.stdout or push.stderr) else 'ok')
    return 0 if push.returncode == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
