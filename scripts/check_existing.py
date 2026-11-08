#!/usr/bin/env python3
"""Skip exact previously published releases. A 404 alone means missing."""
import json, os, sys, urllib.error, urllib.request
from pathlib import Path
rec = json.loads(Path('work/identity.json').read_text(encoding='utf-8'))
repo = os.environ['GITHUB_REPOSITORY']
url = f"https://api.github.com/repos/{repo}/releases/tags/{rec['release_tag']}"
headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'sharex-portable-builder-r1'}
token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
if token: headers['Authorization'] = 'Bearer ' + token
exists = False
try:
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
        release = json.load(r)
        if release.get('draft'): raise RuntimeError('Same release tag already exists as a draft; manual review required')
        if '<!-- portable-release-publisher:managed:v2 -->' not in release.get('body', ''):
            raise RuntimeError('Release tag collision with a non-publisher release')
        exists = True
except urllib.error.HTTPError as e:
    if e.code != 404: raise RuntimeError(f'Release API failed HTTP {e.code}') from e
with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8', newline='\n') as f:
    f.write(f"exists={str(exists).lower()}\n")
print('Matching release already exists; skip duplicate build.' if exists else 'New release; build required.')
