#!/usr/bin/env python3
"""
build_export.py - regenerate everything in this folder from the companion .docx.

    python3 tools/build_export.py path/to/BFGXR_XR_Companion.docx

Steps:
  1. premerge.py      merge multi-paragraph table cells so every table converts to Markdown
  2. pandoc           docx -> one GitHub-flavoured Markdown file + extracted images
  3. split_markdown   one .md per top-level section in rules/, tables compacted, images renamed
  4. parse_ships      ship rosters -> data/ships.json, ships.csv, weapons.csv, parse_report.md
Needs: python3, pandoc.
"""
import os, shutil, subprocess, sys, tempfile

here = os.path.dirname(os.path.abspath(__file__))
root = os.path.dirname(here)
docx = os.path.abspath(sys.argv[1])
tmp = tempfile.mkdtemp()
merged = os.path.join(tmp, 'merged.docx')
subprocess.run([sys.executable, os.path.join(here, 'premerge.py'), docx, merged], check=True)
subprocess.run(['pandoc', merged, '-t', 'gfm', '--wrap=none', f'--extract-media={tmp}',
                '-o', os.path.join(tmp, 'all.md')], check=True)
for d in ('rules', 'data'):
    shutil.rmtree(os.path.join(root, d), ignore_errors=True)
subprocess.run([sys.executable, os.path.join(here, 'split_markdown.py'), os.path.join(tmp, 'all.md'),
                os.path.join(tmp, 'media'), os.path.join(root, 'rules')], check=True)
subprocess.run([sys.executable, os.path.join(here, 'parse_ships.py'), docx, os.path.join(root, 'data')], check=True)
shutil.rmtree(tmp)
print('done')
