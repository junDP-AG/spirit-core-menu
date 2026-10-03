#!/usr/bin/env python3
from pathlib import Path
import json, re

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / 'index.html'
DATA = ROOT / 'data' / 'ppm_ranges_v29.json'

text = INDEX.read_text(encoding='utf-8')
data = json.loads(DATA.read_text(encoding='utf-8'))


def parse_json_const(name, s):
    marker = f'const {name}='
    start = s.find(marker)
    if start < 0:
        raise RuntimeError(f'{name} const not found')
    jstart = start + len(marker)
    value, endrel = json.JSONDecoder().raw_decode(s[jstart:])
    return value, jstart, jstart + endrel


def replace_json_const(name, s, value):
    _, start, end = parse_json_const(name, s)
    return s[:start] + json.dumps(value, ensure_ascii=False, separators=(',', ':')) + s[end:]

raw, _, _ = parse_json_const('RAW', text)
details, _, _ = parse_json_const('PRODUCT_DETAILS', text)
ppm_text = data['ppm_text']

# PPM is primarily a malt phenol specification. For products without a defensible
# numeric range, retain '미상' rather than inventing a value.
for row in raw:
    name = row[1]
    peat_class = row[8]
    d = details.get(name, {})
    if peat_class != 'None':
        d['ppmText'] = ppm_text.get(name, '미상')
        details[name] = d
    elif 'ppmText' in d:
        d.pop('ppmText', None)

text = replace_json_const('PRODUCT_DETAILS', text, details)

# Version localStorage so existing user/admin data migrates while classifications refresh.
m = re.search(r"const STORAGE_KEY='([^']+)';", text)
if not m:
    raise RuntimeError('STORAGE_KEY not found')
old_key = m.group(1)
new_key = 'sc_ws_v27_local_stock_178_ppmranges'
if old_key != new_key:
    text = text[:m.start()] + f"const STORAGE_KEY='{new_key}';" + text[m.end():]

lm = re.search(r"const LEGACY_STORAGE_KEYS=\[([^\]]*)\];", text)
if not lm:
    raise RuntimeError('LEGACY_STORAGE_KEYS not found')
items = re.findall(r"'([^']+)'", lm.group(1))
if old_key != new_key and old_key not in items:
    items.insert(0, old_key)
legacy = 'const LEGACY_STORAGE_KEYS=[' + ','.join(repr(x) for x in items) + '];'
text = text[:lm.start()] + legacy + text[lm.end():]

INDEX.write_text(text, encoding='utf-8')
print(f'Applied numeric PPM ranges to {len(ppm_text)} products; other peated products remain 미상.')
