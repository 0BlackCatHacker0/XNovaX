#!/usr/bin/env python3
"""TBuild deps scanner — finds project dependencies from manifest files.
Scans: package.json, requirements.txt, Cargo.toml, go.mod, pyproject.toml
Returns JSON: {deps: {manifest: [dep_names]}, count: N, trit: +1/0/-1}
"""
import json, os, re, sys

p = sys.argv[1] if len(sys.argv) > 1 else "."
deps = {}

# package.json
pj = os.path.join(p, 'package.json')
if os.path.exists(pj):
    try:
        d = json.load(open(pj, 'r', encoding='utf-8'))
        deps['package.json'] = (
            list(d.get('dependencies', {}).keys()) +
            ['[dev]' + k for k in d.get('devDependencies', {}).keys()]
        )
    except Exception:
        pass

# requirements.txt
rq = os.path.join(p, 'requirements.txt')
if os.path.exists(rq):
    deps['requirements.txt'] = [
        l.strip() for l in open(rq, 'r', encoding='utf-8')
        if l.strip() and not l.strip().startswith('#')
    ]

# Cargo.toml
ct = os.path.join(p, 'Cargo.toml')
if os.path.exists(ct):
    in_deps = False
    cargo_deps = []
    for ln in open(ct, 'r', encoding='utf-8'):
        stripped = ln.strip()
        if stripped.startswith('['):
            in_deps = 'dependencies' in stripped.lower()
            continue
        if in_deps:
            m = re.match(r'^([A-Za-z0-9_-]+)\s*=', stripped)
            if m:
                cargo_deps.append(m.group(1))
    if cargo_deps:
        deps['Cargo.toml'] = cargo_deps

# go.mod
gm = os.path.join(p, 'go.mod')
if os.path.exists(gm):
    go_deps = []
    in_require = False
    for ln in open(gm, 'r', encoding='utf-8'):
        stripped = ln.strip()
        if stripped.startswith('require ('):
            in_require = True
            continue
        if in_require:
            if stripped == ')':
                in_require = False
                continue
            parts = stripped.split()
            if parts:
                go_deps.append(parts[0])
        elif stripped.startswith('require ') and not stripped.startswith('require ('):
            parts = stripped.split()
            if len(parts) >= 2:
                go_deps.append(parts[1])
    if go_deps:
        deps['go.mod'] = go_deps

# pyproject.toml
pt = os.path.join(p, 'pyproject.toml')
if os.path.exists(pt):
    try:
        src = open(pt, 'r', encoding='utf-8').read()
        m = re.findall(r'dependencies\s*=\s*\[([^\]]*?)\]', src, re.DOTALL)
        if m:
            deps['pyproject.toml'] = [
                re.sub(r'[>=<!].*', '', d.strip().strip('"').strip("'")).strip()
                for d in m[0].split(',') if d.strip()
            ]
    except Exception:
        pass

found = {k: v for k, v in deps.items() if v}
total = sum(len(v) for v in found.values())
trit = 1 if total > 0 else 0
print(json.dumps({'deps': found, 'count': total, 'trit': trit}))
