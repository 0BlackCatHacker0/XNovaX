"""NovaX Orchestrator Bootstrap — loads from .pyc cache without .py source files."""
import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import sys
import os

CORE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(CORE_DIR, "__pycache__")
PY_VERSION = f"cpython-{sys.version_info.major}{sys.version_info.minor}"


class PycFinder(importlib.abc.MetaPathFinder):
    """Import hook: finds modules from __pycache__/*.pyc when .py is missing."""

    def find_spec(self, name, path, target=None):
        # Only handle top-level imports from core/
        if "." in name:
            return None
        pyc_file = os.path.join(CACHE_DIR, f"{name}.{PY_VERSION}.pyc")
        if os.path.exists(pyc_file):
            # Check if .py already exists (let normal import handle it)
            py_file = os.path.join(CORE_DIR, f"{name}.py")
            if os.path.exists(py_file):
                return None
            loader = importlib.machinery.SourcelessFileLoader(name, pyc_file)
            return importlib.util.spec_from_loader(name, loader, origin=pyc_file)
        return None


# Install the custom finder BEFORE any imports
sys.meta_path.insert(0, PycFinder())

# Ensure core/ is on sys.path
if CORE_DIR not in sys.path:
    sys.path.insert(0, CORE_DIR)

# NovaX root on path too
novax_root = os.path.dirname(CORE_DIR)
if novax_root not in sys.path:
    sys.path.insert(0, novax_root)

# Now load and run the orchestrator
spec = importlib.util.spec_from_file_location(
    "__main__",
    os.path.join(CACHE_DIR, f"orchestrator.{PY_VERSION}.pyc"),
    loader=importlib.machinery.SourcelessFileLoader("__main__",
        os.path.join(CACHE_DIR, f"orchestrator.{PY_VERSION}.pyc"))
)
module = importlib.util.module_from_spec(spec)
sys.modules["__main__"] = module

# Schedule health check patch to apply after orchestrator initializes
import threading
def _apply_health_patch():
    """Apply health check fix as soon as orchestrator module is importable.

    Preserves the old ~3s maximum wait but applies the patch the moment
    `health_patch` becomes importable, instead of always sleeping 3 seconds.
    """
    import time
    last_err = None
    for _ in range(10):  # up to 10 * 0.5s = 5s maximum
        time.sleep(0.5)
        try:
            import health_patch  # noqa: F401
            print("[boot] Health check patch applied successfully")
            return
        except Exception as e:
            last_err = e
    print(f"[boot] Health patch failed: {last_err}")
threading.Thread(target=_apply_health_patch, daemon=True, name="health-patcher").start()

spec.loader.exec_module(module)
