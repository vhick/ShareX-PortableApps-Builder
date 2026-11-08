#!/usr/bin/env python3
"""Guard against mutable/mismatched upstream shared-action interfaces at pinned SHAs."""
from __future__ import annotations
import os, sys, urllib.request

ACTIONS = [
  ('vhick/Portable-Package-Builder', '0112c35580e83b37eb8757ebcb949274e1631a04',
   ['source-dir:', 'output-dir:', 'engine:', 'running-exe:', 'timeout-seconds:',
    'package-revision:', 'official-tool-url:', 'official-tool-sha256:',
    'installer-file:', 'installer-sha256:', 'app-id:', 'app-version:', 'using: composite']),
  ('vhick/portable-release-publisher', 'cb64f86ac2d8c67506db5832de07f9ff58cbeaeb',
   ['files:', 'tag:', 'release-title:', 'tag-prefix:', 'keep-releases:',
    'prune:', 'dry-run:', 'using: composite']),
]

def main():
    for repo, sha, tokens in ACTIONS:
        url = f'https://raw.githubusercontent.com/{repo}/{sha}/action.yml'
        req = urllib.request.Request(url, headers={'User-Agent':'sharex-portable-builder-r1'})
        with urllib.request.urlopen(req, timeout=45) as f:
            contents = f.read().decode('utf-8-sig')
        for token in tokens:
            if token not in contents: raise ValueError(f'Missing action interface {repo}: {token}')
        print('Verified pinned action.yml interface', repo, sha)

if __name__ == '__main__':
    try: main()
    except Exception as e: print('ERROR:',e,file=sys.stderr); sys.exit(1)
