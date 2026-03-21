# Windows 11 Thread Pool & IOCP Optimization for 26+ Python Microservices

## Machine: 16 logical processors

---

## 1. WINDOWS THREAD POOL API

### CreateThreadpool + Configure (Python ctypes)

```python
import ctypes
from ctypes import wintypes

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

# --- Create custom thread pool ---
kernel32.CreateThreadpool.restype = ctypes.c_void_p
kernel32.CreateThreadpool.argtypes = [ctypes.c_void_p]
pool = kernel32.CreateThreadpool(None)

# --- Set min/max threads ---
# Min: keep warm threads ready (avoid cold-start latency)
# Max: cap to prevent context-switch thrashing
kernel32.SetThreadpoolThreadMinimum.restype = wintypes.BOOL
kernel32.SetThreadpoolThreadMinimum.argtypes = [ctypes.c_void_p, wintypes.DWORD]
kernel32.SetThreadpoolThreadMaximum.restype = None
kernel32.SetThreadpoolThreadMaximum.argtypes = [ctypes.c_void_p, wintypes.DWORD]

CPU_COUNT = 16
MIN_THREADS = CPU_COUNT          # 16 warm threads
MAX_THREADS = CPU_COUNT * 2      # 32 max (2x CPU for kernel-blocking coverage)

kernel32.SetThreadpoolThreadMaximum(pool, MAX_THREADS)  # SET MAX FIRST
success = kernel32.SetThreadpoolThreadMinimum(pool, MIN_THREADS)
# Note: SetMax returns void, SetMin returns BOOL (can fail on alloc)
```

### Callback Environment Setup (C reference)

```c
TP_CALLBACK_ENVIRON cbe;
InitializeThreadpoolEnvironment(&cbe);
SetThreadpoolCallbackPool(&cbe, pool);

// Cleanup group: auto-release all work items on shutdown
PTP_CLEANUP_GROUP cleanupGroup = CreateThreadpoolCleanupGroup();
SetThreadpoolCallbackCleanupGroup(&cbe, cleanupGroup, NULL);

// Submit work
PTP_WORK work = CreateThreadpoolWork(WorkCallback, context, &cbe);
SubmitThreadpoolWork(work);

// Shutdown: cancel pending, wait for running, release all
CloseThreadpoolCleanupGroupMembers(cleanupGroup, TRUE, NULL);
CloseThreadpoolCleanupGroup(cleanupGroup);
CloseThreadpool(pool);
```

### PowerShell: Query Current Thread Pool State

```powershell
# View process thread counts for all NovaX services
Get-Process python* | Select-Object Id, ProcessName, Threads,
    @{N='ThreadCount';E={$_.Threads.Count}},
    @{N='WorkingSetMB';E={[math]::Round($_.WorkingSet64/1MB,1)}} |
    Sort-Object ThreadCount -Descending | Format-Table -AutoSize

# Total thread count across all Python processes
(Get-Process python* | ForEach-Object { $_.Threads.Count } |
    Measure-Object -Sum).Sum
```

### Defaults (important)

```
Default min = 0, max = 500
Recommended for 26 services:
  Per-service pool: min=2, max=4  (IO-bound services)
  Orchestrator:     min=4, max=16 (high-traffic gateway)
  HiveMind:         min=4, max=32 (fan-out to AI providers)
```

---

## 2. I/O COMPLETION PORTS

### CreateIoCompletionPort (Python ctypes)

```python
import ctypes
from ctypes import wintypes

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

INVALID_HANDLE = ctypes.c_void_p(-1)

# Create IOCP with concurrency = CPU count
# NumberOfConcurrentThreads=0 means "use number of processors"
kernel32.CreateIoCompletionPort.restype = wintypes.HANDLE
kernel32.CreateIoCompletionPort.argtypes = [
    wintypes.HANDLE,   # FileHandle
    wintypes.HANDLE,   # ExistingCompletionPort
    ctypes.POINTER(ctypes.c_ulong),  # CompletionKey
    wintypes.DWORD     # NumberOfConcurrentThreads
]

CPU_COUNT = 16
iocp = kernel32.CreateIoCompletionPort(
    INVALID_HANDLE,    # no file handle (create new port)
    None,              # no existing port
    None,              # no completion key
    CPU_COUNT          # concurrency = 16 (one per logical CPU)
)

# Associate a socket/file handle with the IOCP
# kernel32.CreateIoCompletionPort(file_handle, iocp, completion_key, 0)
```

### GetQueuedCompletionStatusEx: Batched I/O (C reference)

```c
// Batch dequeue: reduce kernel transitions
#define BATCH_SIZE 32
OVERLAPPED_ENTRY entries[BATCH_SIZE];
ULONG numRemoved = 0;

BOOL ok = GetQueuedCompletionStatusEx(
    iocp,           // completion port
    entries,        // output array
    BATCH_SIZE,     // max entries to dequeue
    &numRemoved,    // actual count dequeued
    1000,           // timeout ms
    FALSE           // not alertable
);

for (ULONG i = 0; i < numRemoved; i++) {
    ULONG_PTR key = entries[i].lpCompletionKey;
    OVERLAPPED* ov = entries[i].lpOverlapped;
    DWORD bytes = entries[i].dwNumberOfBytesTransferred;
    // dispatch based on completion key
}
```

### PostQueuedCompletionStatus: Custom Notifications

```python
# Signal custom events through IOCP (service health change, etc.)
kernel32.PostQueuedCompletionStatus.restype = wintypes.BOOL
kernel32.PostQueuedCompletionStatus.argtypes = [
    wintypes.HANDLE, wintypes.DWORD,
    ctypes.POINTER(ctypes.c_ulong), ctypes.c_void_p
]

SERVICE_HEALTH_CHANGED = 0x1001
SERVICE_SHUTDOWN = 0x1002

# Post custom notification
kernel32.PostQueuedCompletionStatus(
    iocp,
    0,                                          # bytes transferred
    ctypes.pointer(ctypes.c_ulong(SERVICE_HEALTH_CHANGED)),  # key
    None                                        # no OVERLAPPED
)
```

### Thread Count Formula

```
IOCP concurrency value = CPU_COUNT (16)
Worker threads per IOCP = 2 * CPU_COUNT (32)
  - Extra threads cover kernel-mode blocking (page faults, locks)
  - IOCP uses LIFO wake: hot thread gets reused, cold threads sleep
  - LIFO = better cache locality, fewer context switches
```

---

## 3. PYTHON + IOCP (ProactorEventLoop)

### Default on Windows Since Python 3.8

```python
import asyncio
import sys

# ProactorEventLoop is default on Windows
# It wraps Windows IOCP internally via IocpProactor
loop = asyncio.new_event_loop()
print(type(loop))  # <class 'asyncio.windows_events.ProactorEventLoop'>
```

### How Python Maps to IOCP

```
asyncio.ProactorEventLoop
  └── IocpProactor (Lib/asyncio/windows_events.py)
       └── _overlapped.CreateIoCompletionPort()   # C extension
       └── _overlapped.GetQueuedCompletionStatus() # polls IOCP
       └── _overlapped.Overlapped()                # wraps OVERLAPPED struct

Each async I/O call:
  1. Python creates Overlapped object
  2. Starts async Windows I/O (ReadFile, WSARecv, ConnectEx, etc.)
  3. IocpProactor._poll() calls GetQueuedCompletionStatus in event loop
  4. Completion triggers Future.set_result() → coroutine resumes
```

### Tuning ProactorEventLoop for 26 Services

```python
import asyncio
import socket
from concurrent.futures import ThreadPoolExecutor

async def create_optimized_server():
    loop = asyncio.get_running_loop()

    # 1. Thread pool for blocking calls (run_in_executor)
    #    26 services, some do blocking I/O → size accordingly
    executor = ThreadPoolExecutor(
        max_workers=32,           # 2x CPU count
        thread_name_prefix="nova"
    )
    loop.set_default_executor(executor)

    # 2. Socket tuning for each service server
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)   # disable Nagle
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)  # 64KB send buf
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)  # 64KB recv buf

    # 3. GC tuning for reduced pause times
    import gc
    gc.set_threshold(50000, 20, 10)  # less frequent GC cycles

    # 4. For each service: use asyncio.start_server (uses IOCP under the hood)
    server = await asyncio.start_server(
        handle_client,
        '127.0.0.1', 9999,
        backlog=1024,             # connection queue depth
        reuse_address=True
    )
    return server

# 5. Per-service launcher pattern
async def run_service(name, port, handler):
    """Launch one microservice on its own asyncio server."""
    server = await asyncio.start_server(
        handler, '127.0.0.1', port, backlog=256
    )
    async with server:
        await server.serve_forever()
```

### Multi-Service Launcher (All 26 in One Process via IOCP)

```python
import asyncio

async def main():
    """Run all 26 services sharing one IOCP via ProactorEventLoop."""
    tasks = []
    for name, port, handler in SERVICE_REGISTRY:
        tasks.append(asyncio.create_task(
            run_service(name, port, handler)
        ))
    await asyncio.gather(*tasks)

# Single IOCP, single event loop, 26 servers
# All share the same IOCP completion port
asyncio.run(main())
```

### Python 3.12+ / 3.14+ Note

```python
# Policies deprecated in 3.12, removed in 3.16
# Use loop_factory instead:
asyncio.run(main(), loop_factory=asyncio.ProactorEventLoop)

# Or with Runner:
with asyncio.Runner(loop_factory=asyncio.ProactorEventLoop) as runner:
    runner.run(main())
```

---

## 4. THREAD STACK SIZE

### The Problem

```
26 services × ~10 threads each = 260 threads
260 threads × 1MB default stack = 260MB committed just for stacks
+ Python interpreter overhead per thread
= significant memory pressure on a desktop machine
```

### Reduce Stack Size in Python

```python
import threading
import ctypes
from ctypes import wintypes

# Python threading module: set stack size BEFORE creating threads
# Minimum on Windows = 64KB, recommended for IO-bound = 256KB
threading.stack_size(262144)  # 256KB = 256 * 1024

# Memory savings: 260 threads × (1MB - 256KB) = 195MB saved

# For very lightweight IO-only threads:
threading.stack_size(131072)  # 128KB = 128 * 1024
# Memory savings: 260 threads × (1MB - 128KB) = 227.5MB saved

# Create thread AFTER setting stack size
t = threading.Thread(target=io_worker, daemon=True)
t.start()
```

### Per-Thread Stack via Win32 API

```python
import ctypes

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

STACK_SIZE_256KB = 262144
STACK_SIZE_128KB = 131072

# CreateThread with custom stack size
LPTHREAD_START_ROUTINE = ctypes.WINFUNCTYPE(wintypes.DWORD, wintypes.LPVOID)

@LPTHREAD_START_ROUTINE
def worker(param):
    # IO-bound work here
    return 0

thread_id = wintypes.DWORD()
handle = kernel32.CreateThread(
    None,                   # security attributes
    STACK_SIZE_128KB,       # stack size (128KB)
    worker,                 # start routine
    None,                   # parameter
    0,                      # creation flags (0 = run immediately)
    ctypes.byref(thread_id)
)
```

### PowerShell: Check Current Thread Stack Usage

```powershell
# View committed stack sizes for Python processes
$procs = Get-Process python* -ErrorAction SilentlyContinue
foreach ($proc in $procs) {
    $threadCount = $proc.Threads.Count
    $estimatedStackMB = $threadCount * 1  # 1MB default assumption
    Write-Output "$($proc.Id) | $($proc.ProcessName) | Threads: $threadCount | Est. Stack: ${estimatedStackMB}MB"
}

# Total estimated stack memory
$total = ($procs | ForEach-Object { $_.Threads.Count } | Measure-Object -Sum).Sum
Write-Output "Total threads: $total | Default stack mem: ${total}MB | At 256KB: $([math]::Round($total * 0.25, 1))MB"
```

### Registry: SharedSection (Desktop Heap, NOT per-thread stack)

```powershell
# NOTE: This controls desktop HEAP, not thread stacks
# Thread stack size is set per-process via PE header or CreateThread API
# Shown for reference only - DO NOT MODIFY unless you understand desktop heap

$key = "HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\SubSystems"
$val = (Get-ItemProperty -Path $key -Name "Windows").Windows
# Format: SharedSection=1024,20480,768
# 1024  = system-wide shared section (KB)
# 20480 = per-interactive-window-station desktop heap (KB)
# 768   = per-non-interactive-window-station desktop heap (KB)

# To change default stack for a compiled EXE (not Python):
# editbin /STACK:262144 myservice.exe
```

### Recommended Stack Sizes by Service Type

```
Service Type              Stack Size    Rationale
─────────────────────────────────────────────────────────
IO-bound (health, proxy)  128KB         Minimal call depth
HTTP servers              256KB         Moderate call depth
NovaLang interpreter      512KB         Recursive eval, nested scopes
Orchestrator main         1MB (default) Deep call chains, routing
HiveMind fan-out          256KB         Mostly async waiting
```

---

## 5. THREAD AFFINITY

### Pin IO Threads to Specific Cores (Python)

```python
import ctypes
from ctypes import wintypes

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

def set_thread_affinity(core_mask):
    """Pin current thread to specific cores. mask is a bitmask."""
    handle = kernel32.GetCurrentThread()
    old_mask = kernel32.SetThreadAffinityMask(handle, core_mask)
    if old_mask == 0:
        raise ctypes.WinError(ctypes.get_last_error())
    return old_mask

def set_process_affinity(core_mask):
    """Pin entire process to specific cores."""
    handle = kernel32.GetCurrentProcess()
    kernel32.SetProcessAffinityMask.restype = wintypes.BOOL
    kernel32.SetProcessAffinityMask(handle, core_mask)

# --- NovaX Service Affinity Map (16 cores) ---
# Cores 0-3:   Orchestrator + critical path (mask = 0x000F)
# Cores 4-7:   HiveMind + Cloud Router     (mask = 0x00F0)
# Cores 8-11:  Tier 1 services             (mask = 0x0F00)
# Cores 12-15: Tier 2 services + background (mask = 0xF000)

AFFINITY_MAP = {
    'orchestrator':  0x000F,  # cores 0-3
    'hivemind':      0x00F0,  # cores 4-7
    'cloud_router':  0x00F0,  # cores 4-7
    'novaxcore':     0x000F,  # cores 0-3
    'novalang':      0x0F00,  # cores 8-11
    'nova_vault':    0x0F00,  # cores 8-11
    'nova_cortex':   0xF000,  # cores 12-15
    'default':       0xF000,  # cores 12-15
}

def apply_service_affinity(service_name):
    mask = AFFINITY_MAP.get(service_name, AFFINITY_MAP['default'])
    set_process_affinity(mask)
```

### NUMA-Aware Placement

```python
def get_numa_topology():
    """Query NUMA nodes and their processor masks."""
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

    highest_node = ctypes.c_ulong()
    kernel32.GetNumaHighestNodeNumber(ctypes.byref(highest_node))

    nodes = {}
    for node in range(highest_node.value + 1):
        proc_mask = ctypes.c_ulonglong()
        kernel32.GetNumaNodeProcessorMask(node, ctypes.byref(proc_mask))
        nodes[node] = proc_mask.value
    return nodes

# Pin service threads to same NUMA node as their allocated memory
# VirtualAllocExNuma for NUMA-local memory allocation
```

### PowerShell: Set Process Affinity

```powershell
# Pin a Python service to cores 0-3
$proc = Get-Process -Id (Get-NetTCPConnection -LocalPort 9999 -State Listen).OwningProcess
$proc.ProcessorAffinity = 0x000F

# Pin all NovaX Python processes to specific cores
$ports = @{9999=0x000F; 9881=0x00F0; 9878=0x00F0; 9890=0x000F}
foreach ($port in $ports.Keys) {
    $pid = (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue).OwningProcess
    if ($pid) {
        $p = Get-Process -Id $pid
        $p.ProcessorAffinity = $ports[$port]
        Write-Output "Port $port (PID $pid) → affinity 0x$($ports[$port].ToString('X4'))"
    }
}

# View current affinity for all Python processes
Get-Process python* | ForEach-Object {
    "$($_.Id) | $($_.ProcessName) | Affinity: 0x$($_.ProcessorAffinity.ToString('X'))"
}
```

---

## 6. WAITFORMULTIPLEOBJECTS OPTIMIZATION

### Problem: 64-Handle Limit

```python
# WaitForMultipleObjects max = MAXIMUM_WAIT_OBJECTS = 64
# 26 services × ~4 handles each = 104 handles
# CANNOT pass 104 handles to single WFMO call
```

### Strategy 1: Thread-Based Batching

```python
import ctypes
from ctypes import wintypes
import threading

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
MAXIMUM_WAIT_OBJECTS = 64
WAIT_OBJECT_0 = 0
INFINITE = 0xFFFFFFFF

def wait_for_handles(handles):
    """Wait for 100+ handles using hierarchical batching."""
    if len(handles) <= MAXIMUM_WAIT_OBJECTS:
        arr = (wintypes.HANDLE * len(handles))(*handles)
        result = kernel32.WaitForMultipleObjects(
            len(handles), arr, False, INFINITE
        )
        return result - WAIT_OBJECT_0

    # Split into chunks of 63 (leave 1 slot for batch event)
    CHUNK = MAXIMUM_WAIT_OBJECTS - 1  # 63
    batch_events = []
    results = {}

    def batch_waiter(chunk_handles, batch_event, chunk_id):
        arr = (wintypes.HANDLE * len(chunk_handles))(*chunk_handles)
        idx = kernel32.WaitForMultipleObjects(
            len(chunk_handles), arr, False, INFINITE
        )
        results[chunk_id] = idx
        kernel32.SetEvent(batch_event)

    for i in range(0, len(handles), CHUNK):
        chunk = handles[i:i+CHUNK]
        event = kernel32.CreateEventW(None, True, False, None)
        batch_events.append(event)
        t = threading.Thread(
            target=batch_waiter, args=(chunk, event, i)
        )
        t.daemon = True
        t.start()

    # Wait on batch events (one per chunk, max 64 chunks = 4032 handles)
    arr = (wintypes.HANDLE * len(batch_events))(*batch_events)
    kernel32.WaitForMultipleObjects(
        len(batch_events), arr, False, INFINITE
    )
    return results
```

### Strategy 2: RegisterWaitForSingleObject (Thread Pool)

```python
def register_wait_threadpool(handle, callback, timeout_ms=INFINITE):
    """Use Windows thread pool to wait on individual handles."""
    WAITORTIMERCALLBACK = ctypes.WINFUNCTYPE(
        None, ctypes.c_void_p, wintypes.BOOLEAN
    )

    cb = WAITORTIMERCALLBACK(callback)
    wait_handle = wintypes.HANDLE()

    kernel32.RegisterWaitForSingleObject(
        ctypes.byref(wait_handle),
        handle,
        cb,
        None,             # context
        timeout_ms,
        0x00000008        # WT_EXECUTEONLYONCE
    )
    return wait_handle

# Register all 104 handles — thread pool manages the waiting
for handle in service_handles:
    register_wait_threadpool(handle, on_service_event)
```

### Strategy 3: IOCP (Best for I/O Handles)

```python
# For sockets/pipes/files: associate with IOCP instead of WFMO
# See Section 2 above — IOCP has NO handle limit
# All 26 services' sockets on ONE completion port
```

### Comparison

```
Strategy                  Handle Limit  Latency    Complexity
──────────────────────────────────────────────────────────────
WFMO direct               64           Lowest     Simple
WFMO batch (threads)      4032         Low        Moderate
RegisterWaitForSingle     Unlimited    Low        Simple
IOCP                      Unlimited    Lowest     Moderate (I/O only)
MsgWaitForMultipleObjects 64           Low        Simple (GUI threads)
```

---

## 7. CRITICAL_SECTION vs SRWLock

### SRWLock: Read-Heavy (Health Checks, Status Queries)

```python
import ctypes
from ctypes import wintypes

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

class SRWLock:
    """Slim Reader/Writer Lock wrapper for Python."""
    def __init__(self):
        self._lock = ctypes.c_void_p(0)  # SRWLOCK = pointer-sized
        kernel32.InitializeSRWLock(ctypes.byref(self._lock))

    def acquire_shared(self):
        """Multiple readers can hold simultaneously."""
        kernel32.AcquireSRWLockShared(ctypes.byref(self._lock))

    def release_shared(self):
        kernel32.ReleaseSRWLockShared(ctypes.byref(self._lock))

    def acquire_exclusive(self):
        """Only one writer, blocks all readers."""
        kernel32.AcquireSRWLockExclusive(ctypes.byref(self._lock))

    def release_exclusive(self):
        kernel32.ReleaseSRWLockExclusive(ctypes.byref(self._lock))

    def try_acquire_shared(self):
        return bool(kernel32.TryAcquireSRWLockShared(ctypes.byref(self._lock)))

    def try_acquire_exclusive(self):
        return bool(kernel32.TryAcquireSRWLockExclusive(ctypes.byref(self._lock)))


# Usage: service health registry (read-heavy, write-rare)
health_lock = SRWLock()
service_health = {}

def get_health(service_name):
    health_lock.acquire_shared()      # multiple readers OK
    try:
        return service_health.get(service_name)
    finally:
        health_lock.release_shared()

def update_health(service_name, status):
    health_lock.acquire_exclusive()   # exclusive writer
    try:
        service_health[service_name] = status
    finally:
        health_lock.release_exclusive()
```

### CriticalSection: Write-Heavy (State Machine, Queues)

```python
class CriticalSection:
    """CRITICAL_SECTION wrapper for write-heavy workloads."""
    def __init__(self, spin_count=4000):
        # CRITICAL_SECTION is 40 bytes on x64
        self._cs = (ctypes.c_byte * 40)()
        # InitializeCriticalSectionAndSpinCount: spin before kernel wait
        kernel32.InitializeCriticalSectionAndSpinCount(
            ctypes.byref(self._cs),
            spin_count   # 4000 = recommended, spins in user-mode first
        )

    def enter(self):
        kernel32.EnterCriticalSection(ctypes.byref(self._cs))

    def leave(self):
        kernel32.LeaveCriticalSection(ctypes.byref(self._cs))

    def try_enter(self):
        return bool(kernel32.TryEnterCriticalSection(ctypes.byref(self._cs)))

    def __del__(self):
        kernel32.DeleteCriticalSection(ctypes.byref(self._cs))


# Usage: write-heavy state updates
state_lock = CriticalSection(spin_count=4000)

def update_state(key, value):
    state_lock.enter()
    try:
        state_machine[key] = value
    finally:
        state_lock.leave()
```

### Performance Comparison

```
Metric                  SRWLock             CRITICAL_SECTION
──────────────────────────────────────────────────────────────
Size                    8 bytes (pointer)   40 bytes (x64)
Shared read mode        YES                 NO
Recursive locking       NO                  YES
Uncontended enter/leave 5-15% faster        baseline
Write-only contention   ~50% faster         baseline
Read-heavy (4R/1W)      ~300% faster        baseline (serialized)
Spin count              N/A (built-in)      Configurable (4000)
Fair ordering           NO                  NO (FIFO-ish)
```

### When to Use What (NovaX Map)

```
Component                    Lock Type       Rationale
──────────────────────────────────────────────────────────
VCC health registry          SRWLock shared  95% reads, 5% writes
Service status map           SRWLock shared  Constant health polls
Route table                  SRWLock shared  Read on every request
HiveMind model slots         SRWLock shared  Read to check availability
State machine transitions    CriticalSection Frequent writes, recursive
Message queue push/pop       CriticalSection Write-heavy, need recursion
Cloud Router key rotation    CriticalSection Infrequent but exclusive
NovaLang variable scope      CriticalSection Recursive eval needs re-entry
```

---

## QUICK REFERENCE: OPTIMAL CONFIG FOR 26 NOVAX SERVICES

```
Thread Pool:        min=16 (CPU), max=32 (2×CPU)
IOCP concurrency:   16 (= CPU count) or 0 (let OS decide)
IOCP workers:       32 (2× concurrency)
Thread stack:       256KB for HTTP servers, 128KB for IO-only
ProactorEventLoop:  Default on Windows, tune executor to 32 workers
Socket buffers:     64KB send/recv, TCP_NODELAY=1
GC threshold:       (50000, 20, 10) for reduced pause
Affinity:           4-core groups per service tier
WaitForMultiple:    Use RegisterWaitForSingleObject or IOCP
Health checks:      SRWLock (shared reads)
State updates:      CriticalSection with spin_count=4000

Memory savings from stack reduction:
  Before: 260 threads × 1MB   = 260MB
  After:  260 threads × 256KB = 65MB   (195MB saved)
  Aggressive: 260 threads × 128KB = 32.5MB (227.5MB saved)
```

---

Sources:
- [Thread Pool API - Microsoft Learn](https://learn.microsoft.com/en-us/windows/win32/procthread/thread-pool-api)
- [CreateThreadpool - Microsoft Learn](https://learn.microsoft.com/en-us/windows/win32/api/threadpoolapiset/nf-threadpoolapiset-createthreadpool)
- [SetThreadpoolThreadMinimum - Microsoft Learn](https://learn.microsoft.com/en-us/windows/win32/api/threadpoolapiset/nf-threadpoolapiset-setthreadpoolthreadminimum)
- [SetThreadpoolThreadMaximum - Microsoft Learn](https://learn.microsoft.com/en-us/windows/win32/api/threadpoolapiset/nf-threadpoolapiset-setthreadpoolthreadmaximum)
- [I/O Completion Ports - Microsoft Learn](https://learn.microsoft.com/en-us/windows/win32/fileio/i-o-completion-ports)
- [CreateIoCompletionPort - Microsoft Learn](https://learn.microsoft.com/en-us/windows/win32/fileio/createiocompletionport)
- [Event Loop - Python 3.14 docs](https://docs.python.org/3/library/asyncio-eventloop.html)
- [CPython windows_events.py](https://github.com/python/cpython/blob/main/Lib/asyncio/windows_events.py)
- [Asyncio Windows ProactorEventLoop 2025](https://www.johal.in/asyncio-windows-python-proactor-loop-2025/)
- [Thread Stack Size - Microsoft Learn](https://learn.microsoft.com/en-us/windows/win32/procthread/thread-stack-size)
- [Pushing the Limits: Processes and Threads - Mark Russinovich](https://learn.microsoft.com/en-us/archive/blogs/markrussinovich/pushing-the-limits-of-windows-processes-and-threads)
- [SetThreadAffinityMask - Microsoft Learn](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-setthreadaffinitymask)
- [NUMA Support - Microsoft Learn](https://learn.microsoft.com/en-us/windows/win32/procthread/numa-support)
- [WaitForMultipleObjects - Microsoft Learn](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-waitformultipleobjects)
- [WFMO 64+ handles - Raymond Chen / Old New Thing](https://devblogs.microsoft.com/oldnewthing/?p=110169)
- [SRW Locks - Microsoft Learn](https://learn.microsoft.com/en-us/windows/win32/sync/slim-reader-writer--srw--locks)
- [Synchronization Primitives New to Vista - MSDN Magazine](https://learn.microsoft.com/en-us/archive/msdn-magazine/2007/june/concurrency-synchronization-primitives-new-to-windows-vista)
- [MutexShootout Benchmark](https://github.com/markwaterman/MutexShootout)
