"""log-rotate -- Rotates and compresses NovaX log files"""
import os, json, time, gzip, shutil

_config = {}


def setup():
    global _config
    manifest_path = os.path.join(os.path.dirname(__file__), "manifest.json")
    with open(manifest_path) as f:
        _config = json.load(f).get("config", {})
    print(f"[log-rotate] Watching {len(_config.get('log_dirs', []))} directories")


def teardown():
    print("[log-rotate] Stopped.")


def run(params=None):
    rotated = []
    max_bytes = _config.get("max_size_mb", 10) * 1024 * 1024
    max_age = _config.get("max_age_days", 7) * 86400
    extensions = _config.get("extensions", [".log"])
    now = time.time()

    for log_dir in _config.get("log_dirs", []):
        if not os.path.isdir(log_dir):
            continue
        for fname in os.listdir(log_dir):
            if not any(fname.endswith(ext) for ext in extensions):
                continue
            fpath = os.path.join(log_dir, fname)
            if not os.path.isfile(fpath):
                continue
            size = os.path.getsize(fpath)
            age = now - os.path.getmtime(fpath)

            if size > max_bytes or age > max_age:
                if _config.get("compress", True):
                    gz_path = fpath + ".gz"
                    with open(fpath, "rb") as f_in:
                        with gzip.open(gz_path, "wb") as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    os.remove(fpath)
                    rotated.append({"file": fname, "action": "compressed", "size_mb": round(size / 1048576, 2)})
                else:
                    os.remove(fpath)
                    rotated.append({"file": fname, "action": "deleted", "size_mb": round(size / 1048576, 2)})

    print(f"[log-rotate] Rotated {len(rotated)} files")
    return {"rotated": rotated, "count": len(rotated)}
