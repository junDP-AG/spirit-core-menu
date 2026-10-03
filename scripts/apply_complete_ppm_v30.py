#!/usr/bin/env python3
from pathlib import Path
import json, re

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / 'index.html'
DATA = ROOT / 'data' / 'peat_ppm_reference_v30.json'

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
fixes = data.get('category_fixes', {})

# Objective category correction: current 44% LARK Chinotto Citrus Cask official page
# does not describe peat; the separate Chinotto Cask Strength III is the peated release.
for row in raw:
    if row[1] in fixes:
        row[8] = fixes[row[1]]

peated_names = []
for row in raw:
    name = row[1]
    peat_class = row[8]
    d = details.get(name, {})
    if peat_class != 'None':
        peated_names.append(name)
        if name not in ppm_text:
            raise RuntimeError(f'Missing PPM/status coverage for peated whisky: {name}')
        d['ppmText'] = ppm_text[name]
        details[name] = d
    elif 'ppmText' in d:
        d.pop('ppmText', None)
        details[name] = d

# Prevent accidental stale/unused reference rows from silently drifting.
extra = sorted(set(ppm_text) - set(peated_names))
if extra:
    raise RuntimeError('PPM map contains non-peated/unmatched products: ' + ', '.join(extra))

text = replace_json_const('RAW', text, raw)
text = replace_json_const('PRODUCT_DETAILS', text, details)

# Refresh browser data while preserving prior admin/user settings via migration.
m = re.search(r"const STORAGE_KEY='([^']+)';", text)
if not m:
    raise RuntimeError('STORAGE_KEY not found')
old_key = m.group(1)
new_key = 'sc_ws_v28_local_stock_178_ppmcomplete'
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
print(f'PPM/status coverage applied to all {len(peated_names)} peated entries; 178 total whiskies remain.')
print('Category correction: LARK Chinotto Citrus Cask -> None (current 44% official release).')
