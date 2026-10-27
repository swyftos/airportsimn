"""Validate the dashboard team's area evidence without treating missing capacity as zero."""
from pathlib import Path
import csv
import hashlib
import json
import math

base = Path(__file__).resolve().parents[1]
data = json.loads((base/'data/processed/apron_area.json').read_text())
raw = base/'data/raw/fbo_apron'
sources = json.loads((raw/'source_manifest.json').read_text())
ids = {s['source_id'] for s in sources}
for source in sources:
    actual = hashlib.sha256((raw/source['file']).read_bytes()).hexdigest()
    assert actual == source['sha256'], source['file']
for name, rows, key in [('apron_area',data['records'],'record_id'), ('assumptions_apron',data['assumptions'],'assumption_id')]:
    assert len({r[key] for r in rows}) == len(rows)
    with (base/f'data/processed/{name}.csv').open(newline='') as f:
        saved = list(csv.DictReader(f))
    assert len(saved) == len(rows)
    for expected, actual in zip(rows,saved):
        for field, value in expected.items():
            if value is None: assert actual[field] == '', (name,field)
            elif isinstance(value,(int,float)): assert math.isclose(float(actual[field]),value)
            else: assert actual[field] == value, (name,field)
for record in data['records']:
    assert record['source_id'] in ids
    assert record['retrieved_date'] == '2026-10-23'
    assert record['classification'] in {'public data','benchmark estimate','assumption'}
    if record['status'] == 'not_established': assert record['value'] is None
assert math.isclose(13*43560, data['assumptions'][1]['value'])
assert data['records'][6]['value'] is None
print('Source checksums, CSV/JSON round trips, unit conversion and missing-value semantics passed.')
