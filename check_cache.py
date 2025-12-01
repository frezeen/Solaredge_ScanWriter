import gzip
import json

with gzip.open('cache/web/SITE/2021-09_23-19.json.gz', 'rt') as f:
    cache_data = json.load(f)

data = cache_data['data']
items = data['list']

print(f"Total items: {len(items)}")
for i, item in enumerate(items):
    print(f"\nItem {i}:")
    print(f"  Keys: {item.keys()}")
    measurements = item.get('measurements', [])
    print(f"  Measurements count: {len(measurements)}")
    if measurements:
        print(f"  First measurement keys: {measurements[0].keys()}")
        print(f"  First measurement sample: {json.dumps(measurements[0], indent=2)}")
        break
