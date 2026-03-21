"""auto-backup -- Backs up critical NovaX files to timestamped archives"""
import os, json, time, zipfile, shutil

_config = {}


def setup():
    global _config
    manifest_path = os.path.join(os.path.dirname(__file__), "manifest.json")
    with open(manifest_path) as f:
        _config = json.load(f).get("config", {})
    backup_dir = _config.get("backup_dir", r"C:\NovaX\backups")
    os.makedirs(backup_dir, exist_ok=True)
    print(f"[auto-backup] Ready — {len(_config.get('targets', []))} targets → {backup_dir}")


def teardown():
    print("[auto-backup] Stopped.")


def run(params=None):
    backup_dir = _config.get("backup_dir", r"C:\NovaX\backups")
    os.makedirs(backup_dir, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    zip_path = os.path.join(backup_dir, f"novax_backup_{ts}.zip")

    file_count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for target in _config.get("targets", []):
            if os.path.isfile(target):
                arcname = os.path.relpath(target, r"C:\NovaX")
                zf.write(target, arcname)
                file_count += 1
            elif os.path.isdir(target):
                for root, dirs, files in os.walk(target):
                    for fname in files:
                        fpath = os.path.join(root, fname)
                        arcname = os.path.relpath(fpath, r"C:\NovaX")
                        zf.write(fpath, arcname)
                        file_count += 1

    size_mb = round(os.path.getsize(zip_path) / 1048576, 2)
    _cleanup_old(backup_dir)
    print(f"[auto-backup] Created {zip_path} ({file_count} files, {size_mb}MB)")
    return {"path": zip_path, "files": file_count, "size_mb": size_mb}


def _cleanup_old(backup_dir):
    max_backups = _config.get("max_backups", 10)
    backups = sorted(
        [f for f in os.listdir(backup_dir) if f.startswith("novax_backup_") and f.endswith(".zip")],
        reverse=True,
    )
    for old in backups[max_backups:]:
        os.remove(os.path.join(backup_dir, old))
