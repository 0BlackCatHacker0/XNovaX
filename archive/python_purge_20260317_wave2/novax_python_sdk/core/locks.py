"""Resource locks - prevent concurrent dangerous operations."""
import threading

class LockManager:
    def __init__(self):
        self._locks = {}
        self._global = threading.Lock()
    def acquire(self, resource, timeout=10):
        with self._global:
            if resource not in self._locks:
                self._locks[resource] = threading.Lock()
        return self._locks[resource].acquire(timeout=timeout)
    def release(self, resource):
        if resource in self._locks:
            try: self._locks[resource].release()
            except RuntimeError: pass
    def locked(self):
        return [r for r, l in self._locks.items() if l.locked()]
