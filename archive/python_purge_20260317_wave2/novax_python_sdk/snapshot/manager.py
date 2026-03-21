"""Snapshot manager - capture and restore system state."""
import os, json, time, shutil
from ..objects import Snapshot
from ..events.bus import bus, SNAPSHOT_CREATED

SNAP_DIR = "C:/NovaX/snapshots"

class SnapshotManager:
    def __init__(self):
        os.makedirs(SNAP_DIR, exist_ok=True)
        self.snapshots = []

    def create(self, label="", paths=None) -> Snapshot:
        snap = Snapshot(label=label)
        snap_path = os.path.join(SNAP_DIR, snap.id)
        os.makedirs(snap_path, exist_ok=True)
        if paths:
            for p in paths:
                if os.path.isfile(p):
                    dest = os.path.join(snap_path, os.path.basename(p))
                    shutil.copy2(p, dest)
                    snap.files[p] = dest
        meta = os.path.join(snap_path, "meta.json")
        with open(meta, "w") as f:
            json.dump({"id": snap.id, "label": label, "created": snap.created,
                       "files": snap.files}, f, indent=2)
        self.snapshots.append(snap)
        bus.emit(SNAPSHOT_CREATED, {"id": snap.id, "label": label})
        return snap

    def list_snapshots(self):
        return [{"id": s.id, "label": s.label, "created": s.created} for s in self.snapshots]

    def restore(self, snap_id) -> bool:
        snap = next((s for s in self.snapshots if s.id == snap_id), None)
        if not snap: return False
        for original, backup in snap.files.items():
            if os.path.isfile(backup): shutil.copy2(backup, original)
        return True
