"""tscan.py - Ternary file scanner micro-tool
Usage: python tscan.py <path> <max_depth>
Returns JSON array of {FullName, Length, Extension} to stdout
"""
import os, json, sys

path = sys.argv[1] if len(sys.argv) > 1 else "C:/NovaX"
max_depth = int(sys.argv[2]) if len(sys.argv) > 2 else 2
results = []
base_depth = path.rstrip("/\\").count(os.sep)

for root, dirs, files in os.walk(path):
    current_depth = root.count(os.sep) - base_depth
    if current_depth > max_depth:
        dirs.clear()
        continue
    for f in files:
        fp = os.path.join(root, f)
        try:
            sz = os.path.getsize(fp)
        except OSError:
            sz = 0
        _, ext = os.path.splitext(f)
        results.append({"FullName": fp, "Length": sz, "Extension": ext})

print(json.dumps(results))
