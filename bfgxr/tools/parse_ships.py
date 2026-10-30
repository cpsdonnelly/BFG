#!/usr/bin/env python3
"""
parse_ships.py - read every ship roster table in the BFG:XR companion .docx and write
structured data (ships.json, ships.csv, weapons.csv) plus a parse report.

Each weapon is parsed from the Armament cell into fields. Every parsed weapon is rendered
back to text and compared with the original; any mismatch is listed in parse_report.md
and that weapon keeps parsed=false, so nothing is silently misread.

Usage: python3 parse_ships.py BFGXR_XR_Companion.docx OUT_DIR
"""
import csv, html, json, re, sys, zipfile, os

# ---------------------------------------------------------------- docx reading
T = re.compile(r'<w:t(?:\s[^>]*)?>(.*?)</w:t>', re.S)

def para_text(p):
    return html.unescape(re.sub(r'\s+', ' ', ''.join(T.findall(p)))).strip()

def load_blocks(path):
    doc = zipfile.ZipFile(path).read('word/document.xml').decode('utf-8')
    body = re.search(r'<w:body>(.*)</w:body>', doc, re.S).group(1)
    out = []
    for m in re.finditer(r'<w:tbl>.*?</w:tbl>|<w:p\b.*?</w:p>', body, re.S):
        frag = m.group(0)
        if frag.startswith('<w:tbl'):
            rows = []
            for tr in re.findall(r'<w:tr\b.*?</w:tr>', frag, re.S):
                cells = []
                for tc in re.findall(r'<w:tc>.*?</w:tc>', tr, re.S):
                    paras = [para_text(p) for p in re.findall(r'<w:p\b.*?</w:p>', tc, re.S)]
                    cells.append([p for p in paras if p])
                rows.append(cells)
            out.append(('t', rows))
        else:
            st = re.search(r'<w:pStyle w:val="Heading(\d)"', frag)
            txt = para_text(frag)
            if txt:
                out.append(('h', int(st.group(1)), txt) if st else ('p', txt))
    return out

# ---------------------------------------------------------------- weapon grammar
ARC = re.compile(r'\(([^)]*)\)')
WEAPON = re.compile(
    r'^(?P<loc>(?:Prow|Dorsal|Keel|Port|Starboard)\s+)?'
    r'(?P<name>[A-Z][\w\'\- ]*?)'
    r'(?P<qual>\s+\([^)]*\))?'
    r'\s+(?P<range>\d+(?:-\d+)?cm)'
    r'\s+(?P<val>FP Special|FP ?[0-9D+()]+\+?|S ?[0-9D+()]+\+?|Template|Special)'
    r'(?P<per>\s+per face)?'
    r'(?P<perq>\s+\(per quadrant\))?'
    r'(?P<arcs>(?:,?\s*\([^)]*\))*)$')
BAYS = re.compile(
    r'^(?P<loc>(?:Prow|Dorsal)\s+)?Launch Bays\s+'
    r'(?P<mounts>(?:(?:prow|port|stbd|dorsal)\s+)?S ?[0-9D+]+(?:\s\+\s(?:(?:prow|port|stbd|dorsal)\s+)?S ?[0-9D+]+)*)'
    r'\s+\((?P<craft>[^)]*)\)$')
HOOKS = re.compile(r'^(?P<loc>Dorsal\s+)?Gravitic Hooks(?P<sides> port \+ stbd)? \((?P<cap>[^)]*)\)$')

def split_value(v):
    if v in ('Template', 'Special'): return v, None
    if v == 'FP Special': return 'FP', 'Special'
    m = re.match(r'^(FP|S) ?(.*)$', v)
    return m.group(1), m.group(2)

def fmt_value(stat, value):
    if value is None: return stat
    if value == 'Special' or 'D' in value: return f'{stat} {value}'
    return f'{stat}{value}'

def category(stat):
    return {'FP': 'direct', 'S': 'ordnance', 'Template': 'direct'}.get(stat, 'special')

def parse_range(r):
    a = re.findall(r'\d+', r)
    return (int(a[0]), int(a[1])) if len(a) == 2 else (None, int(a[0]))

def parse_weapon(seg, group=None):
    w = {'raw': seg, 'group': group}
    m = BAYS.match(seg)
    if m:
        mounts = []
        for part in m.group('mounts').split(' + '):
            mm = re.match(r'^(?:(prow|port|stbd|dorsal)\s+)?S ?([0-9D+]+)$', part)
            mounts.append({'side': mm.group(1), 'strength': mm.group(2), 'raw': part})
        craft = []
        for c in m.group('craft').split(', '):
            cm = re.match(r'^(.*?)\s+(\d+)cm$', c)
            craft.append({'type': cm.group(1), 'speed_cm': int(cm.group(2))} if cm else {'type': c, 'speed_cm': None})
        w.update(kind='launch_bays', location=(m.group('loc') or '').strip() or None, name='Launch Bays',
                 stat='S', category='ordnance', bays=mounts, craft=craft)
        back = (f"{w['location'] + ' ' if w['location'] else ''}Launch Bays "
                + ' + '.join(x['raw'] for x in mounts) + f" ({m.group('craft')})")
        w['parsed'] = back == seg
        return w
    m = HOOKS.match(seg)
    if m:
        w.update(kind='gravitic_hooks', location=(m.group('loc') or '').strip() or None, name='Gravitic Hooks',
                 stat=None, category='special', sides=['port', 'stbd'] if m.group('sides') else None,
                 capacity=m.group('cap'), parsed=True)
        return w
    m = WEAPON.match(seg)
    if not m:
        w.update(kind='unparsed', parsed=False)
        return w
    stat, value = split_value(m.group('val'))
    rmin, rmax = parse_range(m.group('range'))
    arcs = [[a.strip() for a in grp.split('/')] for grp in ARC.findall(m.group('arcs'))]
    w.update(kind='weapon', location=(m.group('loc') or '').strip() or None, name=m.group('name'),
             qualifier=(m.group('qual') or '').strip()[1:-1] or None,
             range_min_cm=rmin, range_max_cm=rmax, stat=stat, value=value,
             value_int=int(value) if value and value.isdigit() else None,
             per_face=bool(m.group('per')), per_quadrant=bool(m.group('perq')), category=category(stat),
             mounts=[{'arcs': a} for a in arcs])
    back = (f"{w['location'] + ' ' if w['location'] else ''}{w['name']}"
            f"{' (' + w['qualifier'] + ')' if w['qualifier'] else ''} {m.group('range')} "
            f"{fmt_value(stat, value)}{' per face' if w['per_face'] else ''}{' (per quadrant)' if w['per_quadrant'] else ''}"
            + (' ' + ', '.join('(' + '/'.join(a) + ')' for a in arcs) if arcs else ''))
    w['parsed'] = back == seg
    if not w['parsed']: w['roundtrip'] = back
    return w

def split_armament(cell):
    """Split on ';' outside brackets, then split star-fort 'Quadrant: / Basilica:' groups."""
    parts, depth, cur = [], 0, ''
    for ch in cell:
        depth += (ch == '(') - (ch == ')')
        if ch == ';' and depth == 0:
            parts.append(cur); cur = ''
        else:
            cur += ch
    parts.append(cur)
    out, group = [], None
    for p in parts:
        for piece in re.split(r'\.\s+(?=(?:Quadrant|Basilica):)', p.strip()):
            g = re.match(r'^(Quadrant|Basilica):\s*(.*)$', piece)
            if g: group, piece = g.group(1), g.group(2)
            if piece.strip(): out.append((piece.strip(), group))
    return out

# ---------------------------------------------------------------- stat fields
def to_int(s, unit=''):
    m = re.fullmatch(r'(\d+)' + re.escape(unit), s or '')
    return int(m.group(1)) if m else None

def parse_armour(s):
    m = re.fullmatch(r'(\d)\+(\w*) / (\d)\+', s or '')
    if m: return {'front': int(m.group(1)), 'front_note': m.group(2) or None, 'other': int(m.group(3))}
    m = re.fullmatch(r'(\d)\+', s or '')
    if m: return {'front': int(m.group(1)), 'front_note': None, 'other': int(m.group(1))}
    return None

def main(docx, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    blocks = load_blocks(docx)
    faction = source = None; label = None; ships = []
    for i, b in enumerate(blocks):
        if b[0] == 'h' and b[1] == 1:
            m = re.match(r'^(.*?)\s+((?:Imperium|Xenos|Rulebook) p\.[\d\-, ]+)$', b[2])
            faction, source = (m.group(1), m.group(2)) if m else (b[2], None)
        if b[0] == 'p': label = b[1]
        if b[0] == 't' and b[1] and b[1][0] and [c[0] if c else '' for c in b[1][0]][:1] == ['Class'] \
                and any(c and c[0] == 'Armament' for c in b[1][0]):
            hdr = [c[0] if c else '' for c in b[1][0]]
            for r in b[1][1:]:
                cell = {h: r[j] if j < len(r) else [] for j, h in enumerate(hdr)}
                name_paras = cell['Class']
                arm = ' '.join(cell['Armament'])
                weapons = [parse_weapon(s, g) for s, g in split_armament(arm)]
                if weapons and all(w['kind'] == 'unparsed' for w in weapons):
                    weapons = []          # not a weapon list (e.g. 'Built to order', 'Deployed mine')
                j = lambda k: ' '.join(cell.get(k, []))
                ships.append({
                    'faction': faction, 'source': source, 'roster_group': label,
                    'name': name_paras[0] if name_paras else '',
                    'hull_type': name_paras[1] if len(name_paras) > 1 else None,
                    'points': to_int(j('Pts')), 'points_raw': j('Pts'),
                    'hits': to_int(j('Hits')), 'hits_raw': j('Hits'),
                    'base': j('Base') or None,
                    'speed_cm': to_int(j('Spd'), 'cm'), 'speed_raw': j('Spd'),
                    'turn_deg': to_int(j('Turn'), '°'), 'turn_raw': j('Turn'),
                    'shields': to_int(j('Sh')), 'shields_raw': j('Sh'),
                    'armour': parse_armour(j('Armr')), 'armour_raw': j('Armr'),
                    'turrets': to_int(j('Tur')), 'turrets_raw': j('Tur'),
                    'armament_raw': arm, 'weapons': weapons,
                    'notes': j('Notes') or None,
                })
    json.dump({'source_document': os.path.basename(docx), 'ship_count': len(ships), 'ships': ships},
              open(os.path.join(out_dir, 'ships.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    flat = ['faction', 'roster_group', 'name', 'hull_type', 'points_raw', 'hits_raw', 'base', 'speed_raw',
            'turn_raw', 'shields_raw', 'armour_raw', 'turrets_raw', 'armament_raw', 'notes']
    with open(os.path.join(out_dir, 'ships.csv'), 'w', newline='', encoding='utf-8') as f:
        wr = csv.writer(f); wr.writerow(flat)
        for s in ships: wr.writerow([s[k] for k in flat])
    wcols = ['faction', 'ship', 'group', 'kind', 'location', 'name', 'qualifier', 'range_min_cm', 'range_max_cm',
             'stat', 'value', 'category', 'arcs', 'parsed', 'raw']
    with open(os.path.join(out_dir, 'weapons.csv'), 'w', newline='', encoding='utf-8') as f:
        wr = csv.writer(f); wr.writerow(wcols)
        for s in ships:
            for w in s['weapons']:
                arcs = ' | '.join('/'.join(m['arcs']) for m in w.get('mounts', []))
                if w['kind'] == 'launch_bays':
                    arcs = ''; value = ' + '.join(f"{x['side'] or ''} {x['strength']}".strip() for x in w['bays'])
                else:
                    value = w.get('value') or w.get('capacity')
                wr.writerow([s['faction'], s['name'], w['group'], w['kind'], w.get('location'), w.get('name'),
                             w.get('qualifier'), w.get('range_min_cm'), w.get('range_max_cm'), w.get('stat'),
                             value, w.get('category'), arcs, w['parsed'], w['raw']])
    # report
    allw = [(s, w) for s in ships for w in s['weapons']]
    bad = [(s, w) for s, w in allw if not w['parsed']]
    nolist = [s for s in ships if not s['weapons']]
    rep = [f"# Parse report\n", f"Source: `{os.path.basename(docx)}`\n",
           f"- Ships: {len(ships)}", f"- Weapon entries: {len(allw)}",
           f"- Parsed and round-tripped exactly: {len(allw) - len(bad)}",
           f"- Not parsed (kept as raw text only): {len(bad)}",
           f"- Ships whose Armament cell is not a weapon list: {len(nolist)}\n"]
    if bad:
        rep.append("## Weapons kept as raw text\n")
        rep += [f"- {s['faction']} / {s['name']}: `{w['raw']}`" for s, w in bad]
        rep.append("")
    oddf = [(s['faction'], s['name'], k, s[k]) for s in ships for k in
            ('points_raw', 'hits_raw', 'speed_raw', 'turn_raw', 'shields_raw', 'turrets_raw')
            if s[k] not in ('', '-') and s[k.replace('_raw', '') if k in ('points_raw','hits_raw','shields_raw','turrets_raw')
                else {'speed_raw': 'speed_cm', 'turn_raw': 'turn_deg'}[k]] is None]
    oddf += [(s['faction'], s['name'], 'armour_raw', s['armour_raw']) for s in ships
             if s['armour'] is None and s['armour_raw'] not in ('', '-')]
    if oddf:
        rep.append("## Stat cells kept as raw text only (not plain numbers)\n")
        rep += [f"- {f} / {n}: `{k}` = `{v}`" for f, n, k, v in oddf]
        rep.append("")
    if nolist:
        rep.append("## Ships with no weapon list (Armament cell kept in `armament_raw`)\n")
        rep += [f"- {s['faction']} / {s['name']}: `{s['armament_raw']}`" for s in nolist]
    open(os.path.join(out_dir, 'parse_report.md'), 'w', encoding='utf-8').write('\n'.join(rep) + '\n')
    print('\n'.join(rep[2:7]))
    return ships

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
