#!/usr/bin/env python3
"""Resolve a verifiable QBZ stable tag or explicitly approved immutable source SHA.
Never chooses the main branch implicitly. Python 3.12+ standard library only.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

URL = 'https://github.com/ifauzeee/QBZ-Downloader.git'
API = 'https://api.github.com/repos/ifauzeee/QBZ-Downloader/releases?per_page=100&page={}'
VERSION = re.compile(r'^v?(\d+)\.(\d+)\.(\d+)$')
FULL_SHA = re.compile(r'^[0-9a-fA-F]{40}$')

def run(*args, cwd=None):
    p = subprocess.run(list(args), cwd=cwd, text=True, encoding='utf-8', errors='replace', capture_output=True)
    if p.returncode:
        raise RuntimeError(f'Command failed ({p.returncode}): {args[0]} {args[1:3]}\n{p.stderr}')
    return p.stdout.strip()

def gh_releases():
    token = os.getenv('GITHUB_TOKEN') or os.getenv('GH_TOKEN', '')
    headers = {'Accept':'application/vnd.github+json','User-Agent':'QBZ-PortableApps-Builder-b1r4', 'X-GitHub-Api-Version':'2022-11-28'}
    if token: headers['Authorization'] = 'Bearer ' + token
    results = []
    for page in range(1, 4):
        req = urllib.request.Request(API.format(page), headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                rows = json.load(response)
        except urllib.error.HTTPError as exc:
            # An empty list is normal, but API authorization, throttling and server errors are not.
            raise RuntimeError(f'GitHub releases API HTTP {exc.code}; cannot verify stable releases') from exc
        if not isinstance(rows, list): raise RuntimeError('Unexpected GitHub releases API response')
        results.extend(x['tag_name'] for x in rows if isinstance(x, dict) and not x.get('draft')
                       and not x.get('prerelease') and VERSION.fullmatch(x.get('tag_name','')))
        if len(rows) < 100: return results
    raise RuntimeError('Release pagination exceeded audit limit; do not guess latest')

def git_tags():
    raw = run('git','ls-remote','--tags',URL)
    records = {}
    for line in raw.splitlines():
        sha, ref = line.split('\t', 1)
        if not ref.startswith('refs/tags/'): continue
        name = ref[len('refs/tags/'):]
        peeled = name.endswith('^{}')
        if peeled: name = name[:-3]
        if VERSION.fullmatch(name) and (name not in records or peeled): records[name] = sha.lower()
    return records

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--version', default='latest', help='latest or stable vX.Y.Z tag')
    ap.add_argument('--commit', default='', help='Explicit full 40-char upstream SHA, for repos without stable tags')
    ap.add_argument('--allow-untagged-head', action='store_true', help='Explicit opt-in to untagged HEAD snapshot; never enabled by default')
    ap.add_argument('--out', default='work')
    args = ap.parse_args()
    dest = Path(args.out).resolve(); dest.mkdir(parents=True, exist_ok=True)
    upstream = dest / 'upstream'
    if upstream.exists(): raise RuntimeError('Refusing to reuse an existing source directory')
    releases = gh_releases()
    tags = git_tags()
    if args.commit:
        if not FULL_SHA.fullmatch(args.commit): raise RuntimeError('commit must be a full 40-character SHA')
        if args.version == 'latest': raise RuntimeError('Explicit commit requires an explicit version (e.g., 5.6.3)')
        if not VERSION.fullmatch(args.version): raise RuntimeError('Explicit version must be stable X.Y.Z')
        selected = args.commit.lower()
        git_ref = selected
        provenance = 'explicit-commit-unreleased'
        tag = ''
        if selected not in tags.values(): print('NOTICE: An untagged commit is used ONLY because it was explicitly selected.')
    else:
        if not tags and not args.allow_untagged_head:
            raise RuntimeError('NO STABLE UPSTREAM TAGS FOUND. Refusing automatic main. Opt into untagged HEAD snapshot explicitly or supply a full SHA + version.')
        if not tags and args.allow_untagged_head:
            lines = run('git','ls-remote',URL,'HEAD').splitlines()
            if len(lines) != 1: raise RuntimeError('Cannot uniquely verify remote HEAD')
            selected, name = lines[0].split('\t')
            if name != 'HEAD' or not FULL_SHA.fullmatch(selected): raise RuntimeError('Invalid remote HEAD identity')
            tag = ''
            git_ref = selected.lower()
            provenance = 'user-opted-in-untagged-HEAD-snapshot-NOT-stable-release'
            print('WARNING: Explicitly opted into source HEAD snapshot, not a published stable release')
        elif args.version.lower() == 'latest':
            candidates = sorted((x for x in releases if x in tags), key=lambda x: tuple(map(int, VERSION.fullmatch(x).groups())))
            if candidates:
                tag = candidates[-1]
                provenance = 'published-stable-release-tag'
            else:
                tag = max(tags, key=lambda x: tuple(map(int, VERSION.fullmatch(x).groups())))
                provenance = 'stable-git-tag-no-published-release'
        else:
            if not VERSION.fullmatch(args.version): raise RuntimeError('Expected stable X.Y.Z or latest')
            matches = [k for k in tags if k.lstrip('v') == args.version.lstrip('v')]
            if len(matches) != 1: raise RuntimeError(f'Version {args.version} not present as unique stable tag')
            tag = matches[0]
            provenance = 'specified-stable-tag'
        if tag:
            git_ref = tag
            selected = tags[tag]
    run('git','clone','--no-checkout','--filter=blob:none',URL,str(upstream))
    run('git','-C',str(upstream),'fetch','--no-tags','--depth=1','origin',git_ref)
    run('git','-C',str(upstream),'checkout','--detach','FETCH_HEAD')
    commit = run('git','-C',str(upstream),'rev-parse','HEAD').lower()
    if commit != selected: raise RuntimeError(f'Fetched SHA {commit} differs from verified expected {selected}')
    pkg = json.loads((upstream/'package.json').read_text(encoding='utf-8'))
    version = pkg['version']
    if not VERSION.fullmatch(version): raise RuntimeError('Source package version is prerelease or invalid')
    if tag and version != tag.lstrip('v'):
        raise RuntimeError(f'Untrusted tag/version mismatch: {tag} vs package.json {version}')
    if args.allow_untagged_head and not args.commit and args.version != 'latest' and version != args.version.lstrip('v'):
        raise RuntimeError('Opted-in HEAD version mismatch with requested version')
    if args.commit and version != args.version.lstrip('v'):
        raise RuntimeError(f'Commit version mismatch: requested {args.version}, contains {version}')
    required = ['package-lock.json', 'client/package-lock.json','electron/main.cjs','electron/preload.cjs', 'LICENSE']
    for name in required:
        if not (upstream/name).is_file(): raise RuntimeError('Missing required upstream source file: '+name)
    locks = {x:hashlib.sha256((upstream/x).read_bytes()).hexdigest() for x in ('package-lock.json','client/package-lock.json')}
    identity = {'project':'QBZ-Downloader','upstream_url':URL,'version':version,'source_ref':git_ref,
                'upstream_tag':tag,'upstream_commit':commit,'source_provenance':provenance,
                'lockfile_sha256':locks,'builder_revision':'b1r4','package_revision':'r4','mode':'PORTABLEAPPS'}
    (dest/'identity.json').write_text(json.dumps(identity,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(identity,indent=2))
    output = os.getenv('GITHUB_OUTPUT')
    if output:
        with open(output,'a',encoding='utf-8') as f:
            f.write(f'version={version}\ncommit={commit}\nsource_tag={tag}\n')
            # Source SHA ensures a different release for changed source under the same version.
            f.write(f'release_tag=portable-qbz-v{version}-{commit[:12]}-b1r4\n')

if __name__=='__main__': main()
