#!/usr/bin/env python3
from pathlib import Path
import json, re

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / 'index.html'
DATA = ROOT / 'data' / 'peat_classification_v31.json'

text = INDEX.read_text(encoding='utf-8')
data = json.loads(DATA.read_text(encoding='utf-8'))
classes = data['classes']


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
if len(raw) != 178:
    raise RuntimeError(f'Expected 178 whiskies, got {len(raw)}')

current_peated = {r[1] for r in raw if r[8] != 'None'}
if current_peated != set(classes):
    missing = sorted(current_peated - set(classes))
    extra = sorted(set(classes) - current_peated)
    raise RuntimeError(f'Peat class map mismatch. missing={missing}, extra={extra}')

changes = []
for row in raw:
    name = row[1]
    if name in classes:
        old = row[8]
        new = classes[name]
        if old != new:
            changes.append((name, old, new))
        row[8] = new

expected_changes = {
    'The Glenturret 10 Peat Smoked',
    'Ki One Unicorn',
    'Bowmore 12',
    'Bowmore 18',
    'Nikka Taketsuru Pure Malt',
    'Johnnie Walker Green Label 15',
}
if {n for n,_,_ in changes} != expected_changes:
    raise RuntimeError('Unexpected classification changes: ' + repr(changes))

text = replace_json_const('RAW', text, raw)

# Keep taxonomy authoritative even when older browser localStorage has stale peat values.
override_json = json.dumps(classes, ensure_ascii=False, separators=(',', ':'))
marker = 'const PRODUCT_KO_NAMES='
if 'const PEAT_CLASS_OVERRIDES=' in text:
    text = replace_json_const('PEAT_CLASS_OVERRIDES', text, classes)
else:
    idx = text.find(marker)
    if idx < 0:
        raise RuntimeError('PRODUCT_KO_NAMES marker not found')
    text = text[:idx] + 'const PEAT_CLASS_OVERRIDES=' + override_json + ';\n' + text[idx:]

migration_line = "  (PRODUCT_MIGRATIONS[originalName]||PRODUCT_MIGRATIONS[x.name]||[]).forEach(([field,from,to])=>{if(x[field]===from)x[field]=to;});"
override_line = migration_line + "\n  if(PEAT_CLASS_OVERRIDES[originalName])x.peat=PEAT_CLASS_OVERRIDES[originalName];"
if override_line not in text:
    if migration_line not in text:
        raise RuntimeError('migrateWhisky migration line not found')
    text = text.replace(migration_line, override_line, 1)

old_desc = 'desc:"이 축은 약품향·해풍향 같은 향의 종류가 아니라, 마실 때 체감되는 피트 훈연의 강도만 비교합니다. 메디시널·마리타임·재·장작 같은 세부 성격은 향미 설명에서 별도로 다룹니다."'
new_desc = 'desc:"SPIRIT CORE 하우스 기준으로 병입 제품에서 체감되는 피트·스모크 강도를 비교합니다. 원맥아 PPM은 1–15=약, 16–35=중, 36 이상=강을 기본선으로 쓰되, PPM은 병입 위스키의 체감 강도와 동일하지 않으므로 숙성·블렌딩·피티드 원액 비중과 공식 테이스팅 노트를 함께 봅니다. 그 결과 실제 체감이 뚜렷하게 다르면 한 단계 조정합니다."'
if old_desc not in text:
    raise RuntimeError('peat axis description not found')
text = text.replace(old_desc, new_desc, 1)

subs = {
    'id:"Light Peat",ko:"약한 피트",desc:"훈연감이 배경에서 은은하게 느껴지는 단계입니다. 주된 과일·곡물·오크 풍미를 가리지 않고 복합성을 보조합니다."':
    'id:"Light Peat",ko:"약한 피트",desc:"기본선은 원맥아 1–15 PPM입니다. 병입 제품에서 훈연감이 배경에 머물고 과일·곡물·오크 풍미를 가리지 않는 스타일을 포함합니다. PPM 미공개 제품도 공식 노트상 스모크가 보조적이면 이 단계로 분류합니다."',
    'id:"Medium Peat",ko:"중간 피트",desc:"피트 위스키임을 분명히 인지할 수 있는 단계입니다. 스모키함이 주요 캐릭터 중 하나로 나타나며 다른 숙성 풍미와 균형을 이룹니다."':
    'id:"Medium Peat",ko:"중간 피트",desc:"기본선은 원맥아 16–35 PPM입니다. 병입 제품에서 피트를 분명히 인지할 수 있고 스모키함이 주요 캐릭터 중 하나지만, 과실·셰리·몰트와 균형을 이루는 스타일입니다."',
    'id:"Heavy Peat",ko:"강한 피트",desc:"훈연·재·탄 장작·페놀릭 인상이 전면에 나서는 단계입니다. 강도 분류일 뿐, 약품향·해풍향 등 구체적인 향의 성격까지 동일하다는 뜻은 아닙니다."':
    'id:"Heavy Peat",ko:"강한 피트",desc:"기본선은 원맥아 36 PPM 이상입니다. 병입 제품에서 훈연·재·탄 장작·페놀릭 인상이 전면에 나서는 스타일을 포함합니다. 단, 피티드 원액을 논피티드 원액과 섞은 제품은 실제 체감에 따라 중간 단계로 조정할 수 있습니다."'
}
for old, new in subs.items():
    if old not in text:
        raise RuntimeError('peat sub-description not found: ' + old[:40])
    text = text.replace(old, new, 1)

# Refresh local browser seed while importing prior admin visibility/price/image settings.
m = re.search(r"const STORAGE_KEY='([^']+)';", text)
if not m:
    raise RuntimeError('STORAGE_KEY not found')
old_key = m.group(1)
new_key = 'sc_ws_v29_local_stock_178_peatreclass'
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

from collections import Counter
counts = Counter(classes.values())
print('Reclassified all 46 peated entries.')
print('Light:', counts['Light Peat'], 'Medium:', counts['Medium Peat'], 'Heavy:', counts['Heavy Peat'])
for name, old, new in changes:
    print(f'- {name}: {old} -> {new}')
