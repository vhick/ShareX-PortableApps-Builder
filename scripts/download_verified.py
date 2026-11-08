#!/usr/bin/env python3
"""Download upstream binary and exact upstream source; SHA check official asset."""
from __future__ import annotations
import hashlib, json, os, sys, urllib.request, urllib.error, zipfile
from pathlib import Path


def get(url, dest):
    if not (url.startswith('https://github.com/ShareX/ShareX/releases/download/') or
            url.startswith('https://codeload.github.com/ShareX/ShareX/zip/')):
        raise ValueError('Refusing non-official download URL')
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + '.part')
    if tmp.exists(): tmp.unlink()
    req = urllib.request.Request(url, headers={'User-Agent': 'sharex-portable-builder-r1'})
    digest = hashlib.sha256()
    total = 0
    with urllib.request.urlopen(req, timeout=120) as response, tmp.open('wb') as f:
        while True:
            block = response.read(2 * 1024 * 1024)
            if not block: break
            digest.update(block)
            f.write(block)
            total += len(block)
    tmp.replace(dest)
    if not zipfile.is_zipfile(dest): raise ValueError(f'Invalid ZIP: {dest}')
    return digest.hexdigest(), total


def main():
    meta_path = Path(sys.argv[1] if len(sys.argv) > 1 else 'work/identity.json')
    rec = json.loads(meta_path.read_text(encoding='utf-8'))
    out = Path('work/downloads')
    binary = out / rec['asset']
    sha, length = get(rec['asset_url'], binary)
    if sha.lower() != rec['asset_sha256']:
        binary.unlink(missing_ok=True)
        raise ValueError(f"Upstream ZIP checksum mismatch: expected {rec['asset_sha256']}, got {sha}")
    if length != rec['asset_size']:
        binary.unlink(missing_ok=True)
        raise ValueError(f'Upstream ZIP size mismatch: expected {rec["asset_size"]}, got {length}')
    print(f'Verified vendor SHA256 {sha} ({length:,} bytes)')
    source = out / ('ShareX-source-' + rec['commit'] + '.zip')
    source_hash, source_length = get(rec['source_url'], source)
    if source_length < 200_000: raise ValueError('Suspiciously small upstream source archive')
    rec['source_zip_sha256'] = source_hash
    rec['source_zip_size'] = source_length
    rec['source_archive_filename'] = source.name
    meta_path.write_text(json.dumps(rec, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    print(f'Exact commit source ZIP {source_hash} ({source_length:,} bytes)')

if __name__ == '__main__':
    try: main()
    except Exception as e:
        print(f'ERROR: {e}', file=sys.stderr)
        sys.exit(1)
