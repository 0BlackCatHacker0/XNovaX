"""NovaX Script Vault Helper — called by nova_script_vault_service.nova
Usage: python vault_helper.py <command> [args...]
Commands:
  scan                    - Scan vault, return total + categories JSON
  list <category>         - List scripts in a category
  catalog                 - Full catalog of all categories + scripts
  search <query>          - Search filenames for query
  grep <query>            - Search file contents for query
  github <query>          - Search GitHub repos for scripts
  gists <query>           - Search GitHub gists for scripts
  download <url> <cat>    - Download script from URL into category
"""
import os, sys, json
from urllib.request import Request, urlopen
from urllib.parse import quote_plus
from urllib.error import URLError, HTTPError

VAULT = "C:/NovaX/scripts/vault"

def scan():
    cats = {}
    total = 0
    if os.path.isdir(VAULT):
        for d in os.listdir(VAULT):
            dp = os.path.join(VAULT, d)
            if os.path.isdir(dp):
                count = len([f for f in os.listdir(dp) if f.endswith(".nova")])
                cats[d] = count
                total += count
    print(json.dumps({"total": total, "categories": cats}))

def list_cat(category):
    d = os.path.join(VAULT, category)
    if os.path.isdir(d):
        files = [f for f in os.listdir(d) if f.endswith(".nova")]
    else:
        files = []
    print(json.dumps(files))

def catalog():
    cat = {}
    if os.path.isdir(VAULT):
        for d in sorted(os.listdir(VAULT)):
            dp = os.path.join(VAULT, d)
            if os.path.isdir(dp):
                cat[d] = [f for f in os.listdir(dp) if f.endswith(".nova")]
    print(json.dumps(cat))

def search(query):
    q = query.lower()
    results = []
    if os.path.isdir(VAULT):
        for d in os.listdir(VAULT):
            dp = os.path.join(VAULT, d)
            if os.path.isdir(dp):
                for f in os.listdir(dp):
                    if f.endswith(".nova") and q in f.lower():
                        results.append({"cat": d, "name": f, "path": os.path.join(dp, f)})
    print(json.dumps(results[:50]))

def grep(query):
    q = query.lower()
    results = []
    if os.path.isdir(VAULT):
        for d in os.listdir(VAULT):
            dp = os.path.join(VAULT, d)
            if os.path.isdir(dp):
                for f in os.listdir(dp):
                    if f.endswith(".nova"):
                        try:
                            with open(os.path.join(dp, f), "r", errors="ignore") as fh:
                                for i, line in enumerate(fh):
                                    if q in line.lower():
                                        results.append({"cat": d, "name": f, "line": i+1, "text": line.strip()})
                        except:
                            pass
    print(json.dumps(results[:100]))

GH_HEADERS = {"Accept": "application/vnd.github.v3+json", "User-Agent": "NovaX-ScriptVault/1.0"}

def _gh_get(url):
    """GET request to GitHub API with proper headers."""
    req = Request(url, headers=GH_HEADERS)
    try:
        with urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except (URLError, HTTPError) as e:
        return {"error": str(e)}

def github_search(query):
    """Search GitHub repos for scripts — broad search, sorted by stars."""
    q = quote_plus(query)
    url = f"https://api.github.com/search/repositories?q={q}&sort=stars&per_page=15"
    data = _gh_get(url)
    if "error" in data:
        print(json.dumps({"ok": False, "error": data["error"], "results": []}))
        return
    items = data.get("items", [])
    results = []
    for item in items:
        results.append({
            "name": item.get("full_name", ""),
            "description": (item.get("description") or "")[:200],
            "stars": item.get("stargazers_count", 0),
            "url": item.get("html_url", ""),
            "language": item.get("language", ""),
            "topics": item.get("topics", [])[:5],
            "updated": item.get("updated_at", "")[:10]
        })
    print(json.dumps({"ok": True, "total": data.get("total_count", 0), "results": results}))

def gists_search(query):
    """Search GitHub gists (public, by keyword in description)."""
    # GitHub doesn't have a gist search API, so we search code instead
    q = quote_plus(query + " in:description language:shell")
    url = f"https://api.github.com/search/code?q={q}&per_page=10"
    data = _gh_get(url)
    if "error" in data:
        # Fallback: list recent public gists (no search filter)
        url2 = "https://api.github.com/gists/public?per_page=10"
        data2 = _gh_get(url2)
        if isinstance(data2, list):
            results = []
            for g in data2:
                desc = (g.get("description") or "")[:200]
                if query.lower() in desc.lower() or any(query.lower() in f.lower() for f in g.get("files", {})):
                    results.append({
                        "id": g.get("id", ""),
                        "description": desc,
                        "url": g.get("html_url", ""),
                        "files": list(g.get("files", {}).keys())[:5],
                        "created": g.get("created_at", "")[:10]
                    })
            print(json.dumps({"ok": True, "total": len(results), "results": results}))
        else:
            print(json.dumps({"ok": False, "error": "Gist search unavailable", "results": []}))
        return
    items = data.get("items", [])
    results = []
    for item in items:
        results.append({
            "name": item.get("name", ""),
            "path": item.get("path", ""),
            "repo": item.get("repository", {}).get("full_name", ""),
            "url": item.get("html_url", ""),
            "score": item.get("score", 0)
        })
    print(json.dumps({"ok": True, "total": data.get("total_count", 0), "results": results}))

def download_script(url, category):
    """Download a raw script from URL and save to vault category."""
    cat_dir = os.path.join(VAULT, category)
    os.makedirs(cat_dir, exist_ok=True)
    # Extract filename from URL
    fname = url.split("/")[-1]
    if not fname.endswith(".nova"):
        fname = fname.replace(".sh", ".nova").replace(".py", ".nova")
        if not fname.endswith(".nova"):
            fname = fname + ".nova"
    dest = os.path.join(cat_dir, fname)
    try:
        req = Request(url, headers={"User-Agent": "NovaX-ScriptVault/1.0"})
        with urlopen(req, timeout=15) as resp:
            content = resp.read().decode(errors="ignore")
        # Add NovaLang header comment
        header = f"// Downloaded from: {url}\n// Category: {category}\n// Auto-imported by NovaX Script Vault\n\n"
        with open(dest, "w") as f:
            f.write(header + content)
        print(json.dumps({"ok": True, "path": dest, "size": len(content), "name": fname}))
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}))

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "scan"
    if cmd == "scan":
        scan()
    elif cmd == "list" and len(sys.argv) > 2:
        list_cat(sys.argv[2])
    elif cmd == "catalog":
        catalog()
    elif cmd == "search" and len(sys.argv) > 2:
        search(sys.argv[2])
    elif cmd == "grep" and len(sys.argv) > 2:
        grep(sys.argv[2])
    elif cmd == "github" and len(sys.argv) > 2:
        github_search(sys.argv[2])
    elif cmd == "gists" and len(sys.argv) > 2:
        gists_search(sys.argv[2])
    elif cmd == "download" and len(sys.argv) > 3:
        download_script(sys.argv[2], sys.argv[3])
    else:
        print(json.dumps({"error": "Unknown command: " + cmd}))
