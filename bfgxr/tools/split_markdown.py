"""Split pandoc's single GFM file into one Markdown file per top-level (H1) section,
clean heading markup, and rename images to descriptive filenames."""
import re, sys, os, shutil
src_md, media_dir, out_dir = sys.argv[1], sys.argv[2], sys.argv[3]
text = open(src_md, encoding='utf-8').read()
lines = text.split('\n')

def slug(s):
    s = re.sub(r"[’']", '', s.lower())
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')

# 1. drop the Word table of contents (page numbers are meaningless here); keep intro line
first_h1 = next(i for i, l in enumerate(lines) if l.startswith('# '))
intro = next((l for l in lines[:first_h1] if l.strip() and 'Contents' not in l), '').strip('* ')
lines = lines[first_h1:]

# 2. clean headings: '# **Imperial Navy** *Imperium p.63-88*' -> '# Imperial Navy (Imperium p.63-88)'
def clean_heading(l):
    m = re.match(r'^(#+) (.*)$', l)
    if not m: return l
    hashes, body = m.groups()
    src = re.search(r'\s\*([^*]+ p\.[\d\-–, ]+)\*\s*$', body)
    if src: body = body[:src.start()]
    body = re.sub(r'\*+', '', body).strip()
    if src: body += f' ({src.group(1).strip()})'
    return f'{hashes} {body}'
lines = [clean_heading(l) for l in lines]

# 3. rename images by context (scenario name / special order), point links at media/
h = {1: '', 2: '', 3: ''}; names = {}; used = set()
order_names = {}
for i, l in enumerate(lines):
    m = re.match(r'^(#{1,3}) (.*)', l)
    if m:
        lvl = len(m.group(1)); h[lvl] = m.group(2)
        for k in h:
            if k > lvl: h[k] = ''
    def repl(mm):
        src = mm.group(1); base = os.path.basename(src)
        if base not in names:
            if h[1].startswith('Appendix 6'):
                order = re.search(r'\*\*([^*]+)\*\*', l[:mm.start()][::-1][::-1].split('|')[-2] if '|' in l[:mm.start()] else l[:mm.start()])
                cell = l[:mm.start()].split('|')[-1]
                on = re.search(r'\*\*([^*]+)\*\*', cell)
                stem = 'special-order_' + slug(on.group(1) if on else 'icon')
            else:
                stem = slug(h[1]) + '_' + slug(h[2] or h[1])
            n, cand = 1, stem
            while cand in used:
                n += 1; cand = f'{stem}-{n}'
            used.add(cand); names[base] = cand + os.path.splitext(base)[1]
        alt = h[2] or h[1]
        if h[1].startswith('Appendix 6'): alt = 'Special order icon'
        return f'![{alt}](media/{names[base]})'
    lines[i] = re.sub(r'<img src="([^"]+)"[^>]*/>', repl, l)

# 3b. compact pipe tables (pandoc pads cells to align columns) and unbold header cells
def compact(l):
    if not l.startswith('|'): return l
    cells = re.split(r'(?<!\\)\|', l.strip())[1:-1]
    cells = [c.strip() for c in cells]
    if all(re.fullmatch(r':?-+:?', c) for c in cells):
        return '|' + '|'.join('---' for _ in cells) + '|'
    return '| ' + ' | '.join(cells) + ' |'
lines = [compact(l) for l in lines]
for i in range(1, len(lines)):
    if lines[i].startswith('|---') and lines[i-1].startswith('|'):
        lines[i-1] = re.sub(r'\*\*([^*|]+)\*\*', r'\1', lines[i-1])

# 4. split by H1
os.makedirs(os.path.join(out_dir, 'media'), exist_ok=True)
for base, new in names.items():
    shutil.copy(os.path.join(media_dir, base), os.path.join(out_dir, 'media', new))
sections = []; cur = None
for l in lines:
    if l.startswith('# '):
        cur = [l]; sections.append(cur)
    else:
        cur.append(l)
files = []
for idx, sec in enumerate(sections):
    title = sec[0][2:]
    fname = f'{idx:02d}_' + slug(re.sub(r'\s*\(.*\)$', '', title)) + '.md'
    body = '\n'.join(sec).rstrip() + '\n'
    body = re.sub(r'\n{3,}', '\n\n', body)
    open(os.path.join(out_dir, fname), 'w', encoding='utf-8').write(body)
    files.append((fname, title))
open(os.path.join(out_dir, '_index.txt'), 'w').write(intro + '\n' + '\n'.join(f'{f}\t{t}' for f, t in files))
print(f'{len(files)} section files, {len(names)} images')
for f, t in files: print(f'  {f}  <-  {t}')
