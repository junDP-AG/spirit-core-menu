#!/usr/bin/env python3
from pathlib import Path
import json, re

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / 'index.html'
DATA = ROOT / 'data' / 'menu_patch_data.json'

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

# 1) PPM: producer-published numeric values only; other peated entries => 미상.
raw, _, _ = parse_json_const('RAW', text)
details, _, _ = parse_json_const('PRODUCT_DETAILS', text)
official_ppm = data['official_ppm']
for row in raw:
    name = row[1]
    peat_class = row[8]
    d = details.get(name, {})
    if peat_class != 'None':
        d['ppmText'] = official_ppm.get(name, '미상')
        details[name] = d
    elif 'ppmText' in d:
        d.pop('ppmText', None)
text = replace_json_const('PRODUCT_DETAILS', text, details)

if 'function ppmDisplay(w)' not in text:
    anchor = "function abvDisplay(w){const d=productDetail(w);if(d.abvText)return d.abvText;const n=normalizeAbv(w&&w.abv);return n?`${formatAbv(n)}%`:'—';}\n"
    if anchor not in text:
        raise RuntimeError('abvDisplay anchor not found')
    text = text.replace(anchor, anchor + "function ppmDisplay(w){const d=productDetail(w);if(d&&d.ppmText)return d.ppmText;return w&&w.peat&&w.peat!=='None'?'미상':'논피트';}\n", 1)

if 'PEAT PPM' not in text:
    old = '''          <div class="detail-spec-grid">
            <div class="detail-spec"><div class="detail-spec-label">ALCOHOL BY VOLUME</div><div class="detail-spec-value">${esc(abvDisplay(w))}</div></div>
            <div class="detail-spec"><div class="detail-spec-label">CASK COMPOSITION</div><div class="detail-spec-copy">${esc(d.caskDetail||subMeta('cask',w.cask)?.desc||'캐스크 정보 없음')}</div></div>
          </div>'''
    new = '''          <div class="detail-spec-grid">
            <div class="detail-spec"><div class="detail-spec-label">ALCOHOL BY VOLUME</div><div class="detail-spec-value">${esc(abvDisplay(w))}</div></div>
            <div class="detail-spec"><div class="detail-spec-label">PEAT PPM</div><div class="detail-spec-value">${esc(ppmDisplay(w))}</div></div>
            <div class="detail-spec"><div class="detail-spec-label">CASK COMPOSITION</div><div class="detail-spec-copy">${esc(d.caskDetail||subMeta('cask',w.cask)?.desc||'캐스크 정보 없음')}</div></div>
          </div>'''
    if old not in text:
        raise RuntimeError('detail spec grid anchor not found')
    text = text.replace(old, new, 1)

# 2) P1 official bottle assets.
image_map = data['official_image_urls']
if 'const OFFICIAL_IMAGE_URLS=' not in text:
    marker = 'function bottleSlug(name){'
    pos = text.find(marker)
    if pos < 0:
        raise RuntimeError('bottleSlug anchor not found')
    block = (
        'const OFFICIAL_IMAGE_URLS=' + json.dumps(image_map, ensure_ascii=False, separators=(',', ':')) + ';\n'
        "const LOCAL_IMAGE_FALLBACK='./images/placeholder.svg';\n"
        "function officialBottleImageUrl(w){const key=String(w&&w.sc_original_name||w&&w.name||'').trim();return OFFICIAL_IMAGE_URLS[key]||'';}\n"
    )
    text = text[:pos] + block + text[pos:]

old_bottle = '''function bottleImgUrl(w){
  return w.img&&String(w.img).trim()?String(w.img).trim():webBottleImageUrl(w);
}'''
new_bottle = '''function bottleImgUrl(w){
  const own=w&&w.img&&String(w.img).trim()?String(w.img).trim():'';
  if(own&&!isLegacySearchThumb(own))return own;
  const official=officialBottleImageUrl(w);
  return official||webBottleImageUrl(w);
}'''
if old_bottle in text:
    text = text.replace(old_bottle, new_bottle, 1)
elif 'officialBottleImageUrl(w)' not in text[text.find('function bottleImgUrl'):text.find('function bottleImageHtml')]:
    raise RuntimeError('bottleImgUrl anchor not found')

old_err = 'onerror="this.onerror=null;this.src=IMAGE_FALLBACK_SVG;" />'
new_err = 'onerror="this.onerror=null;this.src=LOCAL_IMAGE_FALLBACK;" />'
if old_err in text:
    text = text.replace(old_err, new_err, 1)

# 3) Storage migration version; preserve admin/user saved fields.
m = re.search(r"const STORAGE_KEY='([^']+)';", text)
if not m:
    raise RuntimeError('STORAGE_KEY not found')
old_key = m.group(1)
new_key = 'sc_ws_v26_local_stock_178_officialppm'
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
print(f'Patched {INDEX}: PPM={len(official_ppm)} official values, images={len(image_map)} official assets')
