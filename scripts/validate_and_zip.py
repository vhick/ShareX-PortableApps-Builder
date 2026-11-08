#!/usr/bin/env python3
"""Validate real staged binaries/layout and create ZIP independently of NSIS."""
from __future__ import annotations
import configparser, hashlib, json, os, re, stat, struct, sys, zipfile
from pathlib import Path
from build_stage import pe_arch


def hash_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(2 * 1024 * 1024), b''): h.update(b)
    return h.hexdigest()


def check():
    meta = json.loads(Path('work/identity.json').read_text(encoding='utf-8'))
    stage = Path('work/staging/ShareXPortable')
    must = ['ShareXPortable.exe','App/ShareX/ShareX.exe', 'App/ShareX/Portable',
            'App/AppInfo/appinfo.ini','App/AppInfo/appicon.ico', 'App/AppInfo/appicon_16.png',
            'App/AppInfo/appicon_32.png','Data/TraceGuard/README.txt',
            'Other/Source/ShareX-LICENSE.txt','Other/Source/ShareXPortable-launcher.cs',
            'Other/Source/' + meta['source_archive_filename']]
    for rel in must:
        if not (stage / rel).is_file(): raise ValueError('Missing package file: ' + rel)
    if not (stage / 'Data/ShareX').is_dir(): raise ValueError('Missing initial empty profile Data/ShareX')
    if (stage / 'App/ShareX/ShareX').exists(): raise ValueError('Live profile accidentally included under App')
    for relative in ('ShareXPortable.exe', 'App/ShareX/ShareX.exe'):
        if pe_arch(stage / relative) != 0x8664: raise ValueError('Non-x64 Windows PE: ' + relative)
    conf = configparser.ConfigParser(interpolation=None)
    conf.read(stage / 'App/AppInfo/appinfo.ini', encoding='utf-8')
    expect = {'Format': {'Type': 'PortableApps.comFormat'},
              'Details': {'AppID': 'ShareXPortableIndependent'},
              'Control': {'Start': 'ShareXPortable.exe'}}
    for group, names in expect.items():
        for name, val in names.items():
            if conf[group][name] != val: raise ValueError(f'Wrong appinfo.{group}.{name}')
    if conf['Version']['PackageVersion'] != meta['version'] + '.0': raise ValueError('Package version incorrect')
    icon_data = (stage / 'App/AppInfo/appicon.ico').read_bytes()
    if len(icon_data) < 500 or icon_data[:4] != b'\x00\x00\x01\x00' or int.from_bytes(icon_data[4:6], 'little') < 1:
        raise ValueError('Invalid icon ICO header or icon payload')
    for size in (16, 32):
        data = (stage / 'App/AppInfo' / f'appicon_{size}.png').read_bytes()
        if data[:8] != b'\x89PNG\r\n\x1a\n' or len(data) < 24:
            raise ValueError('Invalid icon PNG signature')
        dimensions = struct.unpack('>II', data[16:24])
        if dimensions != (size, size): raise ValueError(f'Invalid PNG dimensions: {dimensions}')
    for path in stage.rglob('*'):
        if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
            raise ValueError('Reparse links/symlinks not allowed in packaged input: ' + str(path))
    dist = Path('dist')
    dist.mkdir(exist_ok=True)
    filename = meta['zip_name']
    destination = dist / filename
    if destination.exists(): raise ValueError('Refusing overwrite of existing ZIP')
    with zipfile.ZipFile(destination, mode='x', compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as z:
        for item in sorted(stage.rglob('*')):
            rel = item.relative_to(stage).as_posix()
            archive_name = 'ShareXPortable/' + rel
            if item.is_dir():
                # Explicit empty directory ZIP entries, so empty user-data trees survive extraction.
                if not any(item.iterdir()): z.writestr(archive_name + '/', b'')
            elif item.is_file(): z.write(item, archive_name)
    with zipfile.ZipFile(destination) as z:
        if z.testzip() is not None: raise ValueError('Failed ZIP CRC validation')
        if 'ShareXPortable/ShareXPortable.exe' not in z.namelist(): raise ValueError('Root executable absent')
        if 'ShareXPortable/Data/ShareX/' not in z.namelist(): raise ValueError('Empty Data/ShareX not embedded')
    zip_hash = hash_file(destination)
    (dist / (filename + '.sha256')).write_text(f'{zip_hash}  {filename}\n', encoding='ascii')
    result = {'zip': filename, 'sha256': zip_hash, 'upstream_sha256': meta['asset_sha256'],
              'upstream_tag': meta['tag'], 'upstream_commit': meta['commit'],
              'source_sha256': meta['source_zip_sha256'], 'validation': 'STATIC-VALIDATED'}
    (dist / 'verification.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print('STATIC-VALIDATED ZIP:', destination, 'SHA256:', zip_hash)
    return result

if __name__ == '__main__':
    try: check()
    except Exception as e: print('ERROR:', e, file=sys.stderr); sys.exit(1)
