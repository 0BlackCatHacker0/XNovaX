"""Extract HTTP routes from NovaX service files."""
import re, sys

def extract_routes(filepath):
    with open(filepath) as f:
        content = f.read()
    routes = set()
    # Match: path == "/something"
    for m in re.finditer(r'path\s*==\s*["\'](/[^"\'\s]+)["\']', content):
        routes.add(m.group(1))
    # Match: path.startswith("/something")
    for m in re.finditer(r'path\.startswith\(["\'](/[^"\'\s]+)["\']\)', content):
        routes.add(m.group(1))
    routes.discard("/")
    return sorted(routes)

files = {
    "TMapper (9994)": r"C:\NovaX\nova_tmapper.py",
    "TTimeout (9995)": r"C:\NovaX\nova_ttimeout.py",
}

for label, fpath in files.items():
    print(f"=== {label} ===")
    for r in extract_routes(fpath):
        print(f"  {r}")
    print()
