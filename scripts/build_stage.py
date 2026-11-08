#!/usr/bin/env python3
"""Application-specific official portable ZIP -> PortableApps staging layout."""
from __future__ import annotations
import hashlib, json, os, shutil, stat, struct, sys, zipfile
from pathlib import Path


def pe_arch(path: Path) -> int:
    with path.open('rb') as f:
        data = f.read(64)
        if data[:2] != b'MZ' or len(data) < 64: raise ValueError(f'Not a PE: {path}')
        offset = struct.unpack_from('<I', data, 0x3c)[0]
        f.seek(offset)
        header = f.read(6)
        if header[:4] != b'PE\0\0': raise ValueError(f'Invalid PE signature: {path}')
        return struct.unpack_from('<H', header, 4)[0]


def extract_safe(src: Path, dest: Path):
    dest.mkdir(parents=True, exist_ok=False)
    seen = set()
    count = 0
    with zipfile.ZipFile(src) as z:
        for e in z.infolist():
            name = e.filename.replace('\\', '/')
            parts = name.strip('/').split('/')
            if (not name or name.startswith('/') or any(p in ('..', '', '.') for p in parts)
                    or ':' in name or '\0' in name):
                raise ValueError(f'Unsafe ZIP entry: {e.filename!r}')
            key = '/'.join(parts).casefold()
            if key in seen: raise ValueError(f'Case-insensitive duplicate ZIP entry: {name}')
            seen.add(key)
            mode = (e.external_attr >> 16) & 0o170000
            if mode == stat.S_IFLNK: raise ValueError('ZIP symlinks are not permitted')
            target = dest.joinpath(*parts)
            if e.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            count += e.file_size
            if count > 3 * 1024 ** 3: raise ValueError('Uncompressed ZIP exceeds safety limit')
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(e, 'r') as r, target.open('xb') as w:
                shutil.copyfileobj(r, w, 1024 * 1024)
    return count


def main():
    work = Path('work')
    meta = json.loads((work / 'identity.json').read_text(encoding='utf-8'))
    staging = work / 'staging' / 'ShareXPortable'
    original = work / 'upstream'
    if staging.exists() or original.exists(): raise ValueError('Clean staging required; refusing to overwrite existing data')
    binary = work / 'downloads' / meta['asset']
    src_zip = work / 'downloads' / meta['source_archive_filename']
    extract_safe(binary, original)
    matches = [p for p in original.rglob('ShareX.exe') if p.is_file() and len(p.relative_to(original).parts) <= 2]
    if len(matches) != 1:
        raise ValueError(f'Expected one upstream ShareX.exe at archive root/single wrapper, found {len(matches)}')
    app_source = matches[0].parent
    if pe_arch(matches[0]) != 0x8664: raise ValueError('Upstream ShareX.exe is not an AMD64 PE')
    source_archive_root = work / 'sources'
    extract_safe(src_zip, source_archive_root)
    # Confirm exact source archive is the expected ShareX repository tree.
    roots = [p for p in source_archive_root.iterdir() if p.is_dir()]
    if len(roots) != 1 or not (roots[0] / 'ShareX' / 'Program.cs').exists():
        raise ValueError('Expected ShareX source Program.cs absent from exact-commit archive')
    target_app = staging / 'App' / 'ShareX'
    shutil.copytree(app_source, target_app)
    if (target_app / 'ShareX').exists():
        raise ValueError('Official archive unexpectedly contains an existing ShareX profile; do not package host data')
    (target_app / 'Portable').touch(exist_ok=True)
    if (target_app / 'PersonalPath.cfg').exists():
        raise ValueError('Unexpected PersonalPath.cfg in official archive')
    launcher = work / 'launcher' / 'ShareXPortable.exe'
    if not launcher.is_file() or pe_arch(launcher) != 0x8664:
        raise ValueError('Missing real native AOT x64 launcher EXE')
    shutil.copy2(launcher, staging / 'ShareXPortable.exe')
    info = staging / 'App' / 'AppInfo'
    info.mkdir(parents=True)
    (staging / 'Data' / 'ShareX').mkdir(parents=True)
    guard = staging / 'Data' / 'TraceGuard'
    guard.mkdir(parents=True)
    (guard / 'README.txt').write_text('Crash-safe in-package profile transfer only; never host AppData harvesting.\n', encoding='utf-8')
    src_dir = staging / 'Other' / 'Source'
    src_dir.mkdir(parents=True)
    shutil.copy2(src_zip, src_dir / src_zip.name)
    shutil.copy2('launcher/Program.cs', src_dir / 'ShareXPortable-launcher.cs')
    shutil.copy2('launcher/ShareXPortable.csproj', src_dir / 'ShareXPortable.csproj')
    shutil.copy2('launcher/LICENSE-LAUNCHER.txt', src_dir / 'LICENSE-LAUNCHER.txt')
    if (roots[0] / 'LICENSE.txt').exists():
        shutil.copy2(roots[0] / 'LICENSE.txt', src_dir / 'ShareX-LICENSE.txt')
    else:
        raise ValueError('ShareX upstream LICENSE.txt missing from source archive')
    # Explicitly preserve relevant dependency-lock/build metadata provenance.
    lock_names = {'global.json','nuget.config','packages.lock.json','directory.packages.props',
                  'directory.build.props','directory.build.targets','paket.lock'}
    locked = {}
    for file in roots[0].rglob('*'):
        if file.is_file() and file.name.casefold() in lock_names:
            locked[file.relative_to(roots[0]).as_posix()] = hashlib.sha256(file.read_bytes()).hexdigest()
    meta['dependency_lockfile_sha256'] = locked
    (src_dir / 'dependency-lockfiles.json').write_text(json.dumps(locked, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    (src_dir / 'build-identity.json').write_text(json.dumps(meta, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    (src_dir / 'README.txt').write_text('Unofficial community package, not endorsed by ShareX or PortableApps.com.\nUpstream source: '+meta['source_url']+'\nPortable developer binary: '+meta['asset_url']+'\nSource and launcher code included. ShareX is GPL-licensed.\n', encoding='utf-8')
    nums = meta['version'].split('.')
    version_4 = '.'.join((nums + ['0'])[:4])
    ini = f'''[Format]
Type=PortableApps.comFormat
Version=3.8

[Details]
Name=ShareX Portable (Independent)
AppID=ShareXPortableIndependent
Publisher=ShareX Team (upstream); independent packaging
Homepage=https://github.com/ShareX/ShareX
Category=Graphics & Pictures
Description=ShareX screen capture, independent portable package
Language=Multilingual

[License]
Shareable=true
OpenSource=true
Freeware=true
CommercialUse=true
EULAVersion=1

[Version]
PackageVersion={version_4}
DisplayVersion={meta['version']} independent b1r1

[Control]
Icons=1
Start=ShareXPortable.exe
BaseAppID=ShareXPortableIndependent
'''
    (info / 'appinfo.ini').write_text(ini, encoding='utf-8', newline='\n')
    (staging / 'README.txt').write_text('Launch ShareXPortable.exe, NOT App\\ShareX\\ShareX.exe.\nData\\ShareX is moved atomically into the app folder while ShareX runs and returned after full exit.\nExit ShareX via the tray menu BEFORE moving/upgrading this folder.\nIf interrupted, launch the wrapper again BEFORE updating.\nDo not use ShareX integration settings unless you want permanent host integration.\nDO NOT delete Data or Data\\TraceGuard on upgrade.\n', encoding='utf-8')
    print('Staged:', staging)

if __name__ == '__main__':
    try: main()
    except Exception as e:
        print('ERROR:', e, file=sys.stderr)
        sys.exit(1)
