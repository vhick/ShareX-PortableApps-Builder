#!/usr/bin/env python3
"""Resolve a real stable ShareX GitHub release and vendor SHA-256. Stdlib only."""
from __future__ import annotations
import argparse, json, os, re, sys, urllib.request, urllib.error
from pathlib import Path

API = 'https://api.github.com/repos/ShareX/ShareX'
SEMVER = re.compile(r'^v?(\d+)\.(\d+)\.(\d+)$')


def api(url: str):
    assert url.startswith(API + '/') or url == API, 'API URL not allowed'
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'sharex-portable-builder-r1',
               'X-GitHub-Api-Version': '2022-11-28'}
    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    if token: headers['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=40) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise ValueError(f'GitHub resource not found (404): {url}') from exc
        raise RuntimeError(f'GitHub API returned {exc.code}: {url}') from exc


def tag_commit(tag: str) -> str:
    obj = api(f'{API}/git/ref/tags/{tag}')['object']
    for _ in range(5):
        kind = obj['type']
        sha = obj['sha']
        if not re.fullmatch(r'[0-9a-f]{40}', sha):
            raise ValueError(f'Invalid git object hash: {sha}')
        if kind == 'commit': return sha
        if kind != 'tag': raise ValueError(f'Unexpected git object type: {kind}')
        obj = api(f'{API}/git/tags/{sha}')['object']
    raise ValueError('Too many annotated tag levels')


def resolve(version: str):
    if version != 'latest' and not SEMVER.fullmatch(version):
        raise ValueError('Requested version must be latest or numeric X.Y.Z')
    if version == 'latest':
        releases = []
        for page in range(1, 5):
            batch = api(f'{API}/releases?per_page=100&page={page}')
            if not isinstance(batch, list): raise ValueError('Invalid releases API response')
            releases.extend(batch)
            if len(batch) < 100: break
        valid = [r for r in releases if not r.get('prerelease') and not r.get('draft')
                 and SEMVER.fullmatch(r.get('tag_name', ''))]
        if not valid: raise ValueError('No suitable stable ShareX release found')
        release = max(valid, key=lambda r: tuple(map(int, SEMVER.fullmatch(r['tag_name']).groups())))
    else:
        tag = 'v' + version.lstrip('v')
        release = api(f'{API}/releases/tags/{tag}')
        if release.get('prerelease') or release.get('draft'):
            raise ValueError(f'{tag} is not a stable published release')
    tag = release['tag_name']
    match = SEMVER.fullmatch(tag)
    if not match: raise ValueError(f'Non-numeric release tag: {tag}')
    normalized = '.'.join(match.groups())
    asset_name = f'ShareX-{normalized}-portable-x64.zip'
    matches = [a for a in release.get('assets', []) if a['name'] == asset_name]
    if len(matches) != 1: raise ValueError(f'Expected official asset missing: {asset_name}')
    asset = matches[0]
    url = asset['browser_download_url']
    if url != f'https://github.com/ShareX/ShareX/releases/download/{tag}/{asset_name}':
        raise ValueError(f'Unexpected official asset download URL: {url}')
    # Vendor-published checksum in immutable release metadata; never accept a guessed hash.
    checksum = re.search(re.escape(asset_name) + r'\s*\|\s*`?([0-9A-Fa-f]{64})`?', release.get('body') or '')
    if not checksum:
        raise ValueError(f'Official release body lacks SHA-256 for {asset_name}; refusing download')
    commit = tag_commit(tag)
    if release.get('immutable') is False:
        print(f'NOTICE: Release {tag} API does not report immutable; asset checksum is still mandatory.', file=sys.stderr)
    suffix = f'{normalized}-{commit[:12]}-custom-nsis-b1r1'
    output = {
        'upstream_repository': 'ShareX/ShareX', 'version': normalized, 'tag': tag, 'commit': commit,
        'asset': asset_name, 'asset_url': url, 'asset_sha256': checksum.group(1).lower(),
        'asset_size': asset['size'], 'source_url': f'https://codeload.github.com/ShareX/ShareX/zip/{commit}',
        'builder_revision': 'b1', 'package_revision': 'r1', 'engine': 'custom-nsis',
        'shared_package_builder': '0112c35580e83b37eb8757ebcb949274e1631a04',
        'shared_publisher': 'cb64f86ac2d8c67506db5832de07f9ff58cbeaeb',
        'release_tag': 'sharex-portable-v' + suffix,
        'zip_name': f'ShareXPortable_{normalized}_custom-nsis-b1r1.zip',
    }
    return output


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--version', default='latest')
    p.add_argument('--out', default='work/identity.json')
    p.add_argument('--github-output', default='')
    args = p.parse_args()
    record = resolve(args.version)
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    if args.github_output:
        with open(args.github_output, 'a', encoding='utf-8', newline='\n') as f:
            for name, value in [('tag', record['release_tag']), ('version', record['version']),
                                ('asset', record['asset']), ('sha', record['commit'])]:
                f.write(name + '=' + value + '\n')
    print(f"Stable upstream {record['tag']} @ {record['commit']}\nOfficial {record['asset']} SHA256 {record['asset_sha256']}\nRelease {record['release_tag']}")


if __name__ == '__main__':
    try: main()
    except (ValueError, RuntimeError, OSError, KeyError, urllib.error.URLError) as e:
        print('ERROR:', e, file=sys.stderr)
        sys.exit(1)
