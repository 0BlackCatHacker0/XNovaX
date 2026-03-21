"""
NovaX LLM -- Memory Manager for Paged Trit KV Cache
=====================================================
Monitors GPU/RAM usage and automatically manages cache tier eviction:
  HOT  (VRAM) -> WARM (RAM) -> COLD (Disk)

Uses torch.cuda.mem_get_info() for GPU memory, psutil for RAM (with
os-based fallback), and triggers eviction when budgets are exceeded.

N-S Mapping:
    memory_pressure = fluid pressure (high pressure triggers flow/eviction)
    eviction        = viscous dissipation (energy lost to lower tiers)
    budget          = pipe capacity (fixed constraint)

3-5-7-13 Constants:
    Disk cache path = C:\\NovaX\\nova_llm\\cache\\
    Check interval driven by access patterns, not timers
"""

import os
import time
from pathlib import Path
from typing import Dict, Optional

try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


# Default disk cache path
DEFAULT_DISK_PATH = Path("C:/NovaX/nova_llm/cache")


class MemoryManager:
    """Monitors GPU/RAM usage and manages paged trit KV cache tier eviction.

    Budgets are soft limits: when exceeded, the manager triggers eviction
    of the coldest pages (lowest Reynolds number) from hot->warm->cold.

    Args:
        gpu_budget_mb:  Max MB of VRAM to use for KV cache pages (hot tier).
        ram_budget_mb:  Max MB of system RAM for KV cache pages (warm tier).
        disk_path:      Directory for cold-tier page files.
    """

    def __init__(self, gpu_budget_mb: float = 6000.0,
                 ram_budget_mb: float = 16000.0,
                 disk_path: str = None):
        self.gpu_budget_bytes = int(gpu_budget_mb * 1024 * 1024)
        self.ram_budget_bytes = int(ram_budget_mb * 1024 * 1024)
        self.disk_path = Path(disk_path) if disk_path else DEFAULT_DISK_PATH
        self.disk_path.mkdir(parents=True, exist_ok=True)

        self._last_check_time = 0.0
        self._eviction_count = 0
        self._cache_ref = None  # Will be set to PagedTritKVCache

    def attach_cache(self, paged_cache):
        """Attach a PagedTritKVCache instance for management.

        Args:
            paged_cache: PagedTritKVCache instance to manage.
        """
        self._cache_ref = paged_cache

    # ----------------------------------------------------------
    # GPU Memory
    # ----------------------------------------------------------
    def _gpu_info(self) -> Dict[str, int]:
        """Get GPU memory info in bytes. Returns free and total."""
        if HAS_TORCH and torch.cuda.is_available():
            try:
                free, total = torch.cuda.mem_get_info(0)
                allocated = torch.cuda.memory_allocated(0)
                reserved = torch.cuda.memory_reserved(0)
                return {
                    "free": free,
                    "total": total,
                    "allocated": allocated,
                    "reserved": reserved,
                    "used": total - free,
                }
            except Exception:
                pass
        return {"free": 0, "total": 0, "allocated": 0, "reserved": 0, "used": 0}

    # ----------------------------------------------------------
    # RAM Memory
    # ----------------------------------------------------------
    def _ram_info(self) -> Dict[str, int]:
        """Get system RAM info in bytes."""
        if HAS_PSUTIL:
            try:
                vm = psutil.virtual_memory()
                return {
                    "total": vm.total,
                    "available": vm.available,
                    "used": vm.used,
                    "percent": vm.percent,
                }
            except Exception:
                pass
        # Fallback: try os-based approach (Windows)
        try:
            import ctypes
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(stat)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            return {
                "total": stat.ullTotalPhys,
                "available": stat.ullAvailPhys,
                "used": stat.ullTotalPhys - stat.ullAvailPhys,
                "percent": stat.dwMemoryLoad,
            }
        except Exception:
            return {"total": 0, "available": 0, "used": 0, "percent": 0}

    # ----------------------------------------------------------
    # Disk Usage
    # ----------------------------------------------------------
    def _disk_info(self) -> Dict[str, int]:
        """Get disk cache usage."""
        total_bytes = 0
        file_count = 0
        if self.disk_path.exists():
            for f in self.disk_path.glob("*.kvpage"):
                total_bytes += f.stat().st_size
                file_count += 1
        return {"bytes": total_bytes, "files": file_count}

    # ----------------------------------------------------------
    # Cache Tier Sizes
    # ----------------------------------------------------------
    def _tier_bytes(self) -> Dict[str, int]:
        """Calculate bytes used per tier from attached cache."""
        hot_bytes = 0
        warm_bytes = 0
        cold_bytes = 0

        if self._cache_ref is None:
            return {"hot": 0, "warm": 0, "cold": 0}

        cache = self._cache_ref
        for page in cache.hot.values():
            for key in ("k", "v"):
                packed, scales, _ = page[key]
                hot_bytes += len(packed) + scales.nbytes

        for page in cache.warm.values():
            for key in ("k", "v"):
                packed, scales, _ = page[key]
                warm_bytes += len(packed) + scales.nbytes

        disk_info = self._disk_info()
        cold_bytes = disk_info["bytes"]

        return {"hot": hot_bytes, "warm": warm_bytes, "cold": cold_bytes}

    # ----------------------------------------------------------
    # Pressure Check
    # ----------------------------------------------------------
    def check_pressure(self) -> Dict:
        """Check current memory pressure across all tiers.

        Returns a dict with:
            - gpu_pressure: 0.0-1.0 (fraction of GPU budget used by hot tier)
            - ram_pressure: 0.0-1.0 (fraction of RAM budget used by warm tier)
            - evict_hot:    True if hot tier exceeds GPU budget
            - evict_warm:   True if warm tier exceeds RAM budget
            - gpu_info:     raw GPU memory info
            - ram_info:     raw RAM memory info
        """
        tier = self._tier_bytes()
        gpu_info = self._gpu_info()
        ram_info = self._ram_info()

        gpu_pressure = tier["hot"] / max(self.gpu_budget_bytes, 1)
        ram_pressure = tier["warm"] / max(self.ram_budget_bytes, 1)

        evict_hot = tier["hot"] > self.gpu_budget_bytes
        evict_warm = tier["warm"] > self.ram_budget_bytes

        self._last_check_time = time.time()

        return {
            "gpu_pressure": round(gpu_pressure, 4),
            "ram_pressure": round(ram_pressure, 4),
            "evict_hot": evict_hot,
            "evict_warm": evict_warm,
            "tier_bytes": tier,
            "gpu_info": gpu_info,
            "ram_info": ram_info,
        }

    # ----------------------------------------------------------
    # Eviction
    # ----------------------------------------------------------
    def evict_if_needed(self) -> int:
        """Check pressure and trigger eviction if any budget is exceeded.

        Returns:
            Number of pages evicted.
        """
        if self._cache_ref is None:
            return 0

        cache = self._cache_ref
        evicted = 0
        pressure = self.check_pressure()

        # Evict hot -> warm if GPU budget exceeded
        if pressure["evict_hot"]:
            hot_sorted = sorted(
                cache.hot.keys(),
                key=lambda pid: cache._reynolds(pid)
            )
            while pressure["tier_bytes"]["hot"] > self.gpu_budget_bytes and hot_sorted:
                coldest = hot_sorted.pop(0)
                page = cache.hot.pop(coldest)
                cache.warm[coldest] = page
                evicted += 1
                # Recalculate hot bytes
                hot_bytes = 0
                for p in cache.hot.values():
                    for key in ("k", "v"):
                        packed, scales, _ = p[key]
                        hot_bytes += len(packed) + scales.nbytes
                pressure["tier_bytes"]["hot"] = hot_bytes

        # Evict warm -> cold if RAM budget exceeded
        if pressure["evict_warm"]:
            warm_sorted = sorted(
                cache.warm.keys(),
                key=lambda pid: cache._reynolds(pid)
            )
            while pressure["tier_bytes"]["warm"] > self.ram_budget_bytes and warm_sorted:
                coldest = warm_sorted.pop(0)
                page = cache.warm.pop(coldest)
                cache._save_to_disk(coldest, page)
                evicted += 1
                # Recalculate warm bytes
                warm_bytes = 0
                for p in cache.warm.values():
                    for key in ("k", "v"):
                        packed, scales, _ = p[key]
                        warm_bytes += len(packed) + scales.nbytes
                pressure["tier_bytes"]["warm"] = warm_bytes

        self._eviction_count += evicted
        return evicted

    # ----------------------------------------------------------
    # Stats
    # ----------------------------------------------------------
    def stats(self) -> Dict:
        """Full memory statistics across all tiers.

        Returns dict with per-tier usage, budgets, pressure, and system info.
        """
        tier = self._tier_bytes()
        gpu_info = self._gpu_info()
        ram_info = self._ram_info()
        disk_info = self._disk_info()

        total_cache_bytes = tier["hot"] + tier["warm"] + tier["cold"]

        # Estimate tokens per tier (approximate: ~4680 bytes/token for 13L/13H/64D trit cache)
        # Per token: 2 * num_layers * (ceil(num_heads * head_dim / 5) + num_heads * 2)
        # For 13L/13H/64D: 2 * 13 * (ceil(832/5) + 26) = 2 * 13 * (167 + 26) = 2 * 13 * 193 = 5018
        # But actual depends on packing — use measured bytes / estimated per-token
        bytes_per_token_est = 5018  # approximate for 13L/13H/64D
        hot_tokens = int(tier["hot"] / max(bytes_per_token_est, 1))
        warm_tokens = int(tier["warm"] / max(bytes_per_token_est, 1))
        cold_tokens = int(tier["cold"] / max(bytes_per_token_est, 1))

        return {
            "tiers": {
                "hot": {
                    "bytes": tier["hot"],
                    "mb": round(tier["hot"] / (1024 * 1024), 2),
                    "budget_mb": round(self.gpu_budget_bytes / (1024 * 1024), 1),
                    "pressure": round(tier["hot"] / max(self.gpu_budget_bytes, 1), 4),
                    "est_tokens": hot_tokens,
                    "location": "VRAM",
                },
                "warm": {
                    "bytes": tier["warm"],
                    "mb": round(tier["warm"] / (1024 * 1024), 2),
                    "budget_mb": round(self.ram_budget_bytes / (1024 * 1024), 1),
                    "pressure": round(tier["warm"] / max(self.ram_budget_bytes, 1), 4),
                    "est_tokens": warm_tokens,
                    "location": "RAM",
                },
                "cold": {
                    "bytes": tier["cold"],
                    "mb": round(tier["cold"] / (1024 * 1024), 2),
                    "budget_mb": "unlimited",
                    "files": disk_info["files"],
                    "est_tokens": cold_tokens,
                    "location": "Disk",
                    "path": str(self.disk_path),
                },
            },
            "total": {
                "bytes": total_cache_bytes,
                "mb": round(total_cache_bytes / (1024 * 1024), 2),
                "est_tokens": hot_tokens + warm_tokens + cold_tokens,
            },
            "gpu": {
                "total_mb": round(gpu_info["total"] / (1024 * 1024), 1),
                "free_mb": round(gpu_info["free"] / (1024 * 1024), 1),
                "allocated_mb": round(gpu_info["allocated"] / (1024 * 1024), 1),
            },
            "ram": {
                "total_mb": round(ram_info.get("total", 0) / (1024 * 1024), 1),
                "available_mb": round(ram_info.get("available", 0) / (1024 * 1024), 1),
                "percent_used": ram_info.get("percent", 0),
            },
            "eviction_count": self._eviction_count,
            "bytes_per_token_est": bytes_per_token_est,
        }

    # ----------------------------------------------------------
    # Math Check (capacity calculation)
    # ----------------------------------------------------------
    @staticmethod
    def capacity_estimate(num_layers=13, num_heads=13, head_dim=64,
                          gpu_budget_mb=6000, ram_budget_mb=16000):
        """Estimate max tokens per tier for given model dimensions.

        Per-token trit-packed bytes (K+V):
            elements_per_kv = num_heads * head_dim = 832
            trit_bytes_per_kv = ceil(832 / 5) = 167 bytes (TZip)
            scale_bytes_per_kv = num_heads * 2 = 26 bytes (float16 per head)
            per_layer = (167 + 26) * 2 = 386 bytes (K + V)
            per_token = per_layer * num_layers = 386 * 13 = 5018 bytes

        Results for RTX 4060 (8GB total, 6GB usable):
            VRAM (6GB): 6,291,456,000 / 5018 = ~1,253,783 tokens
            RAM (16GB): 16,777,216,000 / 5018 = ~3,343,351 tokens
            Disk: unlimited
        """
        import math as _math
        elements = num_heads * head_dim
        trit_bytes = _math.ceil(elements / 5)  # TZip: 5 trits/byte
        scale_bytes = num_heads * 2  # float16 per head
        per_layer = (trit_bytes + scale_bytes) * 2  # K + V
        per_token = per_layer * num_layers

        gpu_bytes = int(gpu_budget_mb * 1024 * 1024)
        ram_bytes = int(ram_budget_mb * 1024 * 1024)

        return {
            "bytes_per_token": per_token,
            "vram_tokens": gpu_bytes // per_token,
            "ram_tokens": ram_bytes // per_token,
            "disk_tokens": "unlimited",
            "total_addressable": f"{(gpu_bytes + ram_bytes) // per_token:,}+",
            "model": f"{num_layers}L/{num_heads}H/{head_dim}D",
        }
