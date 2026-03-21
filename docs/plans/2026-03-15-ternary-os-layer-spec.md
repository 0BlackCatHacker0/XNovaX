# NovaX Ternary Operating System Layer Specification
**Date:** 2026-03-15
**Version:** 1.0.0
**Author:** NovaX Architecture (Opus 4.6 + Harmonic Constants)
**Status:** Design Specification

---

## 0. DESIGN PHILOSOPHY

Binary operating systems encode all state as 0/1. This forces every nuance into
boolean logic: a process is either running or not. A permission is either granted
or denied. A page is either present or absent.

Reality has three states. A process can be **actively running (+1)**, **ready but
waiting (0)**, or **blocked and unable to proceed (-1)**. A permission can be
**explicitly allowed (+1)**, **inherited from parent (0)**, or **explicitly denied (-1)**.

NovaX OS builds on this insight. Every subsystem uses balanced ternary
{-1, 0, +1} as its fundamental unit. The 3-5-7-13 harmonic constants govern
all sizing, scheduling, and structural decisions.

```
Harmonic Constants (from NovaX core):
  H3  = 3     Ternary base (-1, 0, +1)
  H5  = 5     TZip packing (3^5 = 243 fits in 1 byte)
  H7  = 7     Composition unit (tryte + dimension)
  H13 = 13    Carrier/frame envelope

  BLOCK_SIZE = 3^7 = 2187 bytes
  PAGE_SIZE  = 3^7 = 2187 bytes (ternary-native page)
  Re_LAMINAR = 27, Re_TRANS = 125, Re_TURB = 343
```

---

## 1. TERNARY PROCESS STATES

### 1.1 The Three States

| Trit | State     | Meaning                                           |
|------|-----------|---------------------------------------------------|
| +1   | RUNNING   | Process is executing on a CPU core                 |
| 0    | READY     | Process can run, waiting for scheduler             |
| -1   | BLOCKED   | Process cannot proceed (I/O, lock, sleep, signal)  |

### 1.2 State Transition Diagram

```
         schedule(+1)
    +----- READY(0) <------+
    |         ^             |
    |         | preempt(0)  | unblock(0)
    v         |             |
 RUNNING(+1) -+        BLOCKED(-1)
    |                       ^
    |    block(-1)          |
    +-----------------------+
    |
    | exit(terminate)
    v
  [DEAD] (process removed from table)
```

### 1.3 Transition Matrix (Ternary)

Each transition produces a trit value indicating the direction of state change:

```
From\To    RUNNING(+1)   READY(0)    BLOCKED(-1)
RUNNING       --          preempt      block
              --          delta=(-1)   delta=(-2)
READY       schedule        --          --
            delta=(+1)      --          --
BLOCKED       --          unblock       --
              --          delta=(+1)    --
```

Transition delta: `new_state - old_state`
- schedule: 0 -> +1 = +1 (positive movement)
- preempt:  +1 -> 0 = -1 (negative movement)
- block:    +1 -> -1 = -2 (strong negative, logged as Reynolds event)
- unblock:  -1 -> 0 = +1 (positive recovery)

### 1.4 Process Control Block (Ternary PCB)

```
struct TernaryPCB {
    pid:          int           // Process ID (unique)
    state:        trit          // +1=running, 0=ready, -1=blocked
    priority:     trit          // +1=high, 0=normal, -1=low
    reynolds:     float         // Current Re number (complexity metric)
    regime:       string        // laminar/transitional/turbulent/chaotic
    parent_pid:   int           // Parent process ID
    tryte_id:     [trit; 7]     // 7-trit unique identifier (H7)
    cpu_trits:    int           // CPU time consumed (in trit-cycles)
    block_reason: trit          // +1=I/O wait, 0=lock wait, -1=signal wait
    permissions:  TritMask      // See section 4
    memory_map:   PageTable     // See section 3
    ipc_channels: [Channel; N]  // See section 5
    created_at:   timestamp
    last_tick:    timestamp
}
```

### 1.5 Comparison with Unix

| Aspect            | Unix (binary)              | NovaX (ternary)                     |
|-------------------|----------------------------|-------------------------------------|
| States            | 5+ (R, S, D, Z, T, etc.)  | 3 fundamental (+1, 0, -1)           |
| State encoding    | Single char                | Single trit                         |
| Zombie state      | Separate state (Z)         | Eliminated: parent always reaps     |
| Stopped state     | SIGSTOP -> T               | BLOCKED(-1) with block_reason=(-1)  |
| Uninterruptible   | D (dangerous, can hang)    | No equivalent: all blocks timeout   |
| State transitions | Complex FSM                | 4 transitions, all produce trits    |

**Key improvement:** Unix has the "uninterruptible sleep" (D) state that can
hang a system. NovaX eliminates this. Every BLOCKED(-1) state has a
Reynolds-derived timeout: `timeout = BLOCK_SIZE / Re`. High-complexity
(turbulent) processes get shorter timeouts. If timeout expires, the process
is forcibly moved to READY(0) and the blocked resource is marked failed.

---

## 2. TERNARY SCHEDULER

### 2.1 3-Level Priority Queue

The scheduler maintains three queues, one per priority trit:

```
QUEUE[+1] = High Priority    (system services, IPC handlers)
QUEUE[0]  = Normal Priority  (user processes, background tasks)
QUEUE[-1] = Low Priority     (batch jobs, maintenance, sweepers)
```

### 2.2 Time Quantum (Harmonically Derived)

```
quantum[+1] = H13 trit-cycles  = 13 trit-cycles  (short burst, responsive)
quantum[0]  = H7 * H3 cycles   = 21 trit-cycles  (balanced)
quantum[-1] = H7 * H5 cycles   = 35 trit-cycles  (long batch, efficient)
```

Rationale: High-priority processes get SHORT quanta so they respond quickly
and don't monopolize. Low-priority processes get LONG quanta so they do
meaningful work per context switch (batch efficiency).

### 2.3 Scheduling Algorithm: Ternary Round-Robin with N-S Flow

```
fn schedule_next():
    // Phase 1: Check high-priority queue
    if3 len(QUEUE[+1]) > 0 {
        return dequeue(QUEUE[+1])
    }

    // Phase 2: Reynolds-weighted selection from normal queue
    if3 len(QUEUE[0]) > 0 {
        // Calculate pressure gradient across normal queue
        let candidates = QUEUE[0]
        let best = candidates[0]
        let best_score = 0
        for3 proc in candidates {
            // N-S: lower Reynolds = more laminar = smoother execution
            // Favor laminar processes (they complete faster)
            let wait_time = now() - proc.last_tick
            let score = wait_time / (proc.reynolds + 1)
            if3 score > best_score {
                best = proc
                best_score = score
            }
        }
        return best
    }

    // Phase 3: Low-priority fallback
    if3 len(QUEUE[-1]) > 0 {
        return dequeue(QUEUE[-1])
    }

    // Phase 4: Idle (return idle process with trit=0)
    return IDLE_PROCESS
```

### 2.4 Priority Promotion and Demotion

Processes can move between queues based on behavior:

```
Promotion (+1 direction):
  - Process has been in READY(0) for > H13 * quantum[0] trit-cycles
  - Process is handling IPC from a +1 priority process
  - Block reason resolved (I/O completed)

Demotion (-1 direction):
  - Process exceeds quantum 3 consecutive times (CPU hog)
  - Reynolds number enters turbulent/chaotic regime
  - Process triggers more than H7 page faults per quantum

Stasis (0, unchanged):
  - Normal behavior within quantum
  - Reynolds stays in laminar/transitional
```

### 2.5 Multi-Core Scheduling

For N cores, the scheduler maintains N RUNNING slots:

```
RUNNING_SLOTS = [trit; N]   // +1=occupied, 0=available, -1=draining

fn assign_cores():
    for3 slot in RUNNING_SLOTS {
        if3 slot == 0 {  // available
            let proc = schedule_next()
            if3 proc != IDLE_PROCESS {
                slot = +1
                proc.state = +1  // RUNNING
            }
        }
    }
```

Core draining (-1): A core enters draining state when its process is being
preempted but context save hasn't completed. This prevents double-scheduling.

### 2.6 Comparison with Unix Schedulers

| Aspect              | Linux CFS              | NovaX Ternary Scheduler       |
|---------------------|------------------------|--------------------------------|
| Priority levels     | 140 (nice -20 to +19)  | 3 (-1, 0, +1)                 |
| Time accounting     | Virtual runtime (vruntime) | Trit-cycles + Reynolds      |
| Fairness model      | Red-black tree          | 3 queues + N-S flow score      |
| Real-time support   | FIFO/RR classes         | +1 queue with H13 quantum      |
| Complexity          | O(log n) per decision   | O(1) for +1/-1, O(n) for 0    |
| Starvation guard    | vruntime catches up     | Promotion after H13 quanta     |
| CPU hog detection   | None (relies on nice)   | Auto-demotion after 3 overruns |

**Key insight:** 140 priority levels are overkill. Most processes cluster
around nice=0. Three levels capture the real categories: "urgent," "normal,"
and "background." The N-S Reynolds score provides continuous fine-grained
ordering within each category without needing 140 discrete buckets.

---

## 3. TERNARY VIRTUAL MEMORY

### 3.1 Page Size

```
PAGE_SIZE = 3^7 = 2187 bytes (ternary-native)
```

This is NOT a power of 2. Ternary pages align to ternary block boundaries.
Address translation uses balanced ternary arithmetic, not bit shifting.

### 3.2 Page Table Entry (Ternary PTE)

Each PTE uses trits for permission and state fields:

```
struct TernaryPTE {
    // --- Permission Trits (3 trits = 1 per access type) ---
    read:      trit    // +1=allowed, 0=inherit, -1=denied
    write:     trit    // +1=allowed, 0=inherit, -1=denied
    execute:   trit    // +1=allowed, 0=inherit, -1=denied

    // --- State Trits ---
    present:   trit    // +1=in RAM, 0=in swap, -1=unmapped
    dirty:     trit    // +1=modified, 0=clean, -1=read-only-clean
    accessed:  trit    // +1=recently accessed, 0=not recent, -1=cold

    // --- Frame Reference ---
    frame:     int     // Physical frame number
    swap_id:   int     // Swap location (if present=0)

    // --- Ternary Metadata ---
    reynolds:  float   // Page access Reynolds number
    tier:      trit    // +1=hot, 0=warm, -1=cold (matches TResource)
}
```

### 3.3 Permission Resolution with Inheritance

The `0` (inherit) state is the key innovation. In Unix, every page explicitly
sets rwx bits. In NovaX, a page can inherit permissions from its parent region:

```
fn resolve_permission(page_perm, region_perm, global_perm):
    // -1 (deny) always wins — explicit deny overrides everything
    if3 page_perm == -1 {
        return -1  // DENIED
    }

    // +1 (allow) is explicit grant at this level
    if3 page_perm == +1 {
        return +1  // ALLOWED
    }

    // 0 (inherit) — walk up the hierarchy
    if3 region_perm == -1 {
        return -1
    }
    if3 region_perm == +1 {
        return +1
    }

    // Both page and region inherit — check global
    return global_perm  // Final fallback (default: -1 deny)
```

### 3.4 Permission Encoding

Three trits encode all permissions for one page:

```
rwx encoding (3 trits):
  [+1, +1, +1] = read/write/execute    (full access)
  [+1, +1, -1] = read/write/no-exec    (data segment)
  [+1, -1, +1] = read/no-write/exec    (code segment, immutable)
  [+1, -1, -1] = read-only             (constants)
  [-1, -1, -1] = no access             (guard page)
  [0,  0,  0]  = inherit all           (use parent region perms)
  [+1, 0,  -1] = read/inherit-write/no-exec  (partial inheritance)
```

Total states: 3^3 = 27 permission combinations per page.
Unix has 2^3 = 8 combinations (rwx bits). NovaX has 27, with inheritance
providing hierarchical security without redundant per-page configuration.

### 3.5 Page Replacement: Ternary TResource Algorithm

Page replacement mirrors the TResource hot/warm/cold tier system already
running in nova_ternary_server_service.nova:

```
Page lifecycle:
  +1 (hot)  → Recently accessed, kept in RAM
   0 (warm) → Not recent, candidate for swap
  -1 (cold) → Eviction target, will be swapped out

Sweep algorithm (runs every HEARTBEAT=5s):
  for3 page in all_pages {
      if3 page.accessed == +1 {
          page.tier = +1           // Promote to hot
          page.accessed = 0        // Reset accessed flag
      } else3 page.tier == +1 {
          page.tier = 0            // Hot -> warm (not accessed this cycle)
      } else3 page.tier == 0 {
          page.tier = -1           // Warm -> cold
      } else3 {
          // Already cold: eviction candidate
          if3 need_frame() {
              evict(page)          // Write to swap if dirty
          }
      }
  }
```

This is the EXACT same logic as `handle_tresource_sweep` in the ternary
server, applied to memory pages instead of service slots.

### 3.6 Comparison with Unix Virtual Memory

| Aspect              | Unix                        | NovaX Ternary                     |
|---------------------|-----------------------------|-----------------------------------|
| Page size           | 4096 (2^12)                 | 2187 (3^7)                        |
| Permission bits     | 3 binary (rwx = 8 combos)  | 3 trits (rwx = 27 combos)         |
| Inheritance         | None (every page explicit)  | 0=inherit from region/global       |
| Page states         | 2 (present/not present)     | 3 (+1=RAM, 0=swap, -1=unmapped)   |
| Replacement algo    | LRU/Clock                   | 3-tier TResource (hot/warm/cold)   |
| Dirty tracking      | 1 bit                       | 1 trit (+1=dirty, 0=clean, -1=RO) |
| Address translation | Bit shift + mask            | Balanced ternary division          |
| Guard pages         | Separate mechanism          | [-1,-1,-1] = natural guard         |

### 3.7 Address Translation

```
Virtual Address (balanced ternary):
  [region_trits | page_trits | offset_trits]

  region_trits:  H7 trits  (3^7 = 2187 regions)
  page_trits:    H7 trits  (3^7 = 2187 pages per region)
  offset_trits:  H7 trits  (3^7 = 2187 bytes per page = PAGE_SIZE)

Total addressable: 3^21 = 10,460,353,203 bytes (~10 GB per process)
  (Expandable by adding trit width: 3^28 = ~22 TB)

Translation:
  region = trits[0:7]       // Extract region
  page   = trits[7:14]      // Extract page within region
  offset = trits[14:21]     // Extract byte offset

  frame = page_table[region][page].frame
  physical = frame * PAGE_SIZE + offset
```

---

## 4. TERNARY FILE PERMISSIONS

### 4.1 Permission Model

Unix uses 9 binary bits: owner(rwx) + group(rwx) + other(rwx).
NovaX uses 9 trits with three possible values each:

```
-1 = DENY     Explicitly forbidden (cannot be overridden by parent)
 0 = INHERIT  Use parent directory's permission
+1 = ALLOW    Explicitly permitted
```

### 4.2 Permission Structure

```
struct TernaryFilePerms {
    // Owner permissions (3 trits)
    owner_read:    trit
    owner_write:   trit
    owner_exec:    trit

    // Group permissions (3 trits)
    group_read:    trit
    group_write:   trit
    group_exec:    trit

    // Other permissions (3 trits)
    other_read:    trit
    other_write:   trit
    other_exec:    trit
}
```

### 4.3 Permission Resolution Chain

```
fn check_access(user, file, access_type):
    let perm = get_perm(file, user_category(user), access_type)

    if3 perm == +1 { return ALLOW }
    if3 perm == -1 { return DENY  }

    // perm == 0: INHERIT — walk up directory tree
    let parent = parent_dir(file)
    while3 parent != ROOT {
        let parent_perm = get_perm(parent, user_category(user), access_type)
        if3 parent_perm == +1 { return ALLOW }
        if3 parent_perm == -1 { return DENY  }
        parent = parent_dir(parent)
    }

    // Reached root with all inherits: default DENY
    return DENY
```

### 4.4 Examples

```
Ternary notation: [owner_rwx | group_rwx | other_rwx]

[+1,+1,-1 | +1,-1,-1 | -1,-1,-1]
  Owner: read, write, no-exec
  Group: read-only
  Other: no access
  Unix equivalent: rw-r-----

[+1,-1,+1 | 0,0,0 | -1,-1,-1]
  Owner: read, no-write, exec (immutable executable)
  Group: inherit from parent directory
  Other: no access
  Unix equivalent: r-x???--- (??? depends on parent)

[0,0,0 | 0,0,0 | 0,0,0]
  Everything inherits. File has no explicit permissions.
  Permissions determined entirely by directory hierarchy.
  Unix equivalent: NO EQUIVALENT (Unix cannot express "inherit")
```

### 4.5 Permission Arithmetic

Combining permissions uses ternary min-with-deny-dominance:

```
fn combine(perm_a, perm_b):
    if3 perm_a == -1 || perm_b == -1 {
        return -1    // Deny dominates
    }
    if3 perm_a == +1 && perm_b == +1 {
        return +1    // Both allow
    }
    return 0         // Mixed: inherit/uncertain
```

### 4.6 Comparison with Unix File Permissions

| Aspect               | Unix                      | NovaX Ternary                        |
|-----------------------|---------------------------|--------------------------------------|
| Values per bit        | 2 (0 or 1)               | 3 (-1, 0, +1)                        |
| Total combinations    | 2^9 = 512                | 3^9 = 19,683                          |
| Inheritance           | None                      | 0 = inherit from parent directory     |
| Explicit deny         | Absence of bit = deny     | -1 = explicit deny (cannot override)  |
| ACL needed?           | Yes (for complex rules)   | Rarely (inheritance handles most)     |
| Default new file      | umask subtracted          | All-0 (full inherit from directory)   |
| Setuid/setgid/sticky  | 3 extra bits              | 3 extra trits (with inherit option)   |
| Security strength     | Deny = no bit set         | Deny = explicit, propagates down      |

**Key improvement:** Unix `chmod 755` sets explicit permissions on every file.
Changing a directory's policy requires `chmod -R`. In NovaX, files default to
`[0,0,0|0,0,0|0,0,0]` (all-inherit). Change the directory permission once and
all inheriting children update automatically. Only files needing exceptions get
explicit +1/-1 overrides.

**Explicit deny propagation:** In Unix, removing read from a parent directory
prevents listing, but if you know the filename, you might still access a
file with its own read permission. In NovaX, if a parent directory has `-1`
for read, ALL children are denied regardless of their own permissions —
deny propagates downward and cannot be overridden by children.

---

## 5. TERNARY IPC (Inter-Process Communication)

### 5.1 3-State Semaphores

Unix semaphores are binary (locked/unlocked) or counting integers.
NovaX semaphores have three states:

```
+1 = AVAILABLE    Resource is free, next acquirer gets it
 0 = CONTESTED    Resource is held but shareable (readers allowed)
-1 = EXCLUSIVE    Resource is exclusively locked (all others block)
```

### 5.2 Semaphore Operations

```
fn tsem_acquire(sem, mode):
    // mode: +1=shared, -1=exclusive

    if3 sem.state == +1 {
        // Available: grant immediately
        if3 mode == -1 {
            sem.state = -1       // Exclusive lock
            sem.owner = current_pid()
        } else3 {
            sem.state = 0        // Shared/contested
            sem.readers = sem.readers + 1
        }
        return +1  // Acquired
    }

    if3 sem.state == 0 {
        // Contested (shared readers present)
        if3 mode == +1 {
            sem.readers = sem.readers + 1
            return +1  // Another reader, allowed
        } else3 {
            // Exclusive requested but readers present
            return -1  // Must wait (BLOCKED)
        }
    }

    if3 sem.state == -1 {
        // Exclusively locked
        return -1  // Must wait regardless of mode
    }

fn tsem_release(sem):
    if3 sem.state == -1 {
        // Exclusive release
        sem.state = +1
        sem.owner = 0
        wake_waiters(sem)
    } else3 sem.state == 0 {
        // Shared release
        sem.readers = sem.readers - 1
        if3 sem.readers == 0 {
            sem.state = +1       // Last reader, now available
            wake_waiters(sem)
        }
    }
    return +1
```

### 5.3 Ternary Message Passing

Messages between processes carry ternary metadata:

```
struct TernaryMessage {
    sender_pid:   int
    receiver_pid: int
    priority:     trit       // +1=urgent, 0=normal, -1=bulk
    trit_payload: trit       // Summary trit (+1=positive, 0=neutral, -1=negative)
    data:         bytes      // Actual message content
    reynolds:     float      // Complexity of the message content
    timestamp:    int
}
```

### 5.4 Channel Types (3 Types)

```
+1 = SYNCHRONOUS     Sender blocks until receiver reads
 0 = BUFFERED        Messages queue up to BLOCK_SIZE entries
-1 = FIRE_AND_FORGET Sender never blocks, messages may be dropped
```

### 5.5 Ternary Pipe (TPipe)

Extends Unix pipes with 3-state flow control:

```
struct TPipe {
    buffer:     [byte; BLOCK_SIZE]   // 2187-byte buffer
    flow_state: trit                 // +1=flowing, 0=paused, -1=closed
    pressure:   float                // N-S pressure (buffer fullness ratio)
    viscosity:  float                // N-S viscosity (throughput resistance)
}

Flow control via N-S:
  pressure = buffer_used / BLOCK_SIZE

  if3 pressure > 0.85 {
      flow_state = 0       // Pause: back-pressure (buffer nearly full)
      // Sender blocks until reader drains
  } else3 pressure < 0.15 {
      flow_state = +1      // Flowing: plenty of room
  } else3 {
      // Transitional: check Reynolds
      let Re = pressure * throughput / viscosity
      if3 Re > RE_TURBULENT {
          flow_state = 0   // Turbulent: pause to stabilize
      } else3 {
          flow_state = +1  // Laminar/transitional: keep flowing
      }
  }
```

### 5.6 Ternary Signals

Unix has 31+ signals (SIGTERM, SIGKILL, etc.). NovaX reduces to 3 signal
categories, each with a trit modifier:

```
Signal Categories:
  TSIG_CONTROL  (process lifecycle)
    +1 = resume
     0 = pause
    -1 = terminate

  TSIG_IO       (I/O events)
    +1 = data ready
     0 = timeout
    -1 = error

  TSIG_IPC      (inter-process)
    +1 = message available
     0 = channel status change
    -1 = channel closed
```

Total: 3 categories x 3 modifiers = 9 signals (vs Unix's 31+).
All 9 cover the same functional space as Unix signals with less complexity.

### 5.7 Comparison with Unix IPC

| Aspect            | Unix                          | NovaX Ternary                      |
|-------------------|-------------------------------|-------------------------------------|
| Semaphores        | Binary or counting integer    | 3-state (+1=free, 0=shared, -1=excl)|
| Reader/writer     | Separate rwlock primitive      | Built into semaphore (0=shared)      |
| Pipes             | Byte stream, binary open/close| TPipe with N-S flow control          |
| Back-pressure     | Writer blocks when full       | Gradual: N-S pressure gradient       |
| Signals           | 31+ discrete signals          | 3 categories x 3 modifiers = 9      |
| Message queues    | POSIX mq with priority int    | Trit priority + Reynolds complexity  |
| Shared memory     | mmap + manual sync            | Shared pages with ternary perms      |

---

## 6. UNIFIED SYSTEM ARCHITECTURE

### 6.1 How Components Connect

```
+-------------------------------------------------------------------+
|                     NovaX Ternary OS Layer                         |
|                                                                   |
|  SCHEDULER                    MEMORY                              |
|  +--------+--------+-------+ +-----------+-----------+            |
|  |QUEUE+1 |QUEUE 0 |QUEUE-1| |Region+1   |Region 0   |Region-1   |
|  |        |        |       | |(code, r-x) |(data, rw-)|(stack,rw-)|
|  |svc A   |app B   |batch C| |PTE[rwx]   |PTE[rwx]   |PTE[rwx]  |
|  +--------+--------+-------+ |present    |present    |present   |
|       |                      |tier       |tier       |tier      |
|       v                      +-----------+-----------+           |
|  N-S Reynolds Router                                              |
|  (schedule by Re score)       PAGE REPLACEMENT                    |
|       |                      +---+---+---+                        |
|       v                      |+1 | 0 |-1 | (hot/warm/cold)       |
|  CPU Core Assignment         |hot|wrm|cld|                        |
|  [+1, +1, 0, -1]            +---+---+---+                        |
|  (occupied, occupied,                                             |
|   available, draining)        FILE SYSTEM                         |
|                              [own|grp|oth] x [rwx]                |
|  IPC LAYER                   = 9 trits per file                   |
|  +----------+                0 = inherit from parent              |
|  |Semaphores|                                                     |
|  |+1=free   |  TPipes          SIGNALS                            |
|  | 0=shared |  +1=flowing      3 categories x 3 modifiers        |
|  |-1=excl   |   0=paused       = 9 total signals                  |
|  +----------+  -1=closed                                          |
+-------------------------------------------------------------------+
```

### 6.2 Reynolds Number as Universal Metric

Every subsystem uses Reynolds number for flow control:

```
Scheduler:   Re(process) = complexity * demand / available_cycles
Memory:      Re(page)    = access_freq * working_set / page_size
IPC:         Re(pipe)    = pressure * throughput / viscosity
Filesystem:  Re(file)    = access_count * file_size / cache_size

Reynolds boundaries (universal):
  Re < 27  (laminar)       = simple, predictable, single-path
  Re < 125 (transitional)  = moderate, may need buffering
  Re < 343 (turbulent)     = complex, needs multiple paths/cores
  Re >= 343 (chaotic)      = emergency, all resources engaged
```

### 6.3 Ternary System Calls

```
Process:
  tsys_spawn(code, priority)       -> pid
  tsys_exit(trit_code)             -> void
  tsys_yield()                     -> void    // +1 -> 0 (voluntary preempt)
  tsys_getstate(pid)               -> trit    // +1/0/-1

Memory:
  tsys_mmap(region, size, rwx)     -> addr
  tsys_munmap(addr)                -> trit
  tsys_mprotect(addr, rwx)         -> trit
  tsys_mquery(addr)                -> PTE     // Returns full ternary PTE

Filesystem:
  tsys_open(path, mode_trit)       -> fd      // +1=write, 0=read, -1=append
  tsys_chmod(path, 9_trits)        -> trit
  tsys_chown(path, owner, group)   -> trit

IPC:
  tsys_sem_create(initial_state)   -> sem_id
  tsys_sem_acquire(sem_id, mode)   -> trit
  tsys_sem_release(sem_id)         -> trit
  tsys_pipe_create(type_trit)      -> [read_fd, write_fd]
  tsys_send(pid, category, mod)    -> trit    // Ternary signal
  tsys_msg_send(pid, msg)          -> trit
  tsys_msg_recv(timeout)           -> TernaryMessage
```

Total: 18 system calls (vs Unix ~300+). Every syscall returns a trit
where applicable: +1=success, 0=partial/retry, -1=error.

---

## 7. IMPLEMENTATION MAPPING TO NovaX

### 7.1 Existing Components That Map Directly

| OS Concept              | NovaX Component Already Built        |
|-------------------------|--------------------------------------|
| Process hot/warm/cold   | TResource (nova_ternary_server)       |
| Reynolds routing        | calc_reynolds + classify_regime        |
| 3-tier eviction         | handle_tresource_sweep                 |
| Harmonic sizing         | H3/H5/H7/H13 constants                |
| Ternary consensus       | handle_ternary_vote (majority vote)    |
| Flow classification     | handle_ternary_classify                |
| Service states          | health endpoints (+1/0/-1 trit)        |
| Modulation/encoding     | modulation engine (bpsk/qpsk/tqam)     |
| N-S pressure routing    | Hivemind Reynolds scatter              |

### 7.2 New Components Needed

```
Phase 1 (Immediate):
  - ternary_pcb.nova          Process Control Block structures
  - ternary_scheduler.nova    3-queue scheduler with N-S flow
  - ternary_semaphore.nova    3-state semaphores

Phase 2 (Short-term):
  - ternary_vmm.nova          Virtual memory manager
  - ternary_page_table.nova   Page table with trit permissions
  - ternary_pager.nova        TResource-based page replacement

Phase 3 (Medium-term):
  - ternary_fs_perms.nova     File permission system with inheritance
  - ternary_ipc.nova          Full IPC layer (TPipe, signals, messages)
  - ternary_syscall.nova      System call dispatcher

Phase 4 (Integration):
  - Wire into orchestrator as OS-level service (port TBD)
  - Desktop UI panel: "NovaX OS" with process/memory/IPC views
  - Self-hosting: NovaX OS manages NovaX services
```

### 7.3 Ternary vs Binary: Summary of Advantages

| Dimension        | Binary (Unix)            | Ternary (NovaX)                    | Improvement        |
|------------------|--------------------------|-------------------------------------|--------------------|
| Process states   | 5-7 states               | 3 states                            | Simpler FSM        |
| Permissions      | 512 combos, no inherit   | 19,683 combos, with inherit         | Hierarchical       |
| Scheduling       | 140 priority levels      | 3 levels + Reynolds                 | Simpler + smarter  |
| Page replacement | LRU (binary recent bit)  | 3-tier hot/warm/cold                | Graduated eviction |
| Semaphores       | Binary lock or int count | 3-state (free/shared/exclusive)     | Native rwlock      |
| Signals          | 31+ discrete             | 9 (3 categories x 3 modifiers)      | Orthogonal design  |
| System calls     | 300+                     | 18                                  | Minimal surface    |
| Default security | Explicit everywhere      | Inherit + explicit deny propagates  | Safer defaults     |
| Flow control     | Binary (block or not)    | N-S gradual (pressure/viscosity)    | No hard stalls     |
| Zombie processes | Special state, can leak  | Eliminated (forced reap)            | No zombies         |
| Uninterruptible  | D state (can hang OS)    | Eliminated (Reynolds timeout)       | No hangs           |

---

## 8. THEORETICAL FOUNDATIONS

### 8.1 Information Density

A single trit carries log2(3) = 1.585 bits of information.
Three trits carry 3 * 1.585 = 4.755 bits (vs 3 binary bits = 3 bits).

For permission encoding:
- Unix rwx = 3 bits = 8 states
- NovaX rwx = 3 trits = 27 states = 4.755 bits equivalent

We encode 58.5% more information per position. The "inherit" state alone
eliminates the need for ACLs in most cases.

### 8.2 Kolmogorov Complexity

The ternary OS has lower Kolmogorov complexity than Unix:
- Fewer states to enumerate (3 vs 5-7 for processes)
- Fewer system calls (18 vs 300+)
- Fewer signals (9 vs 31+)
- Fewer priority levels (3 vs 140)
- Single unifying metric (Reynolds) vs ad-hoc heuristics

Lower complexity = fewer bugs, easier verification, faster implementation.

### 8.3 N-S as Universal Scheduler

The Navier-Stokes equations describe fluid flow. Computation IS flow:
data flows through pipes, processes flow through CPU time, pages flow
between RAM and disk.

By using the SAME N-S equations for ALL flow decisions (scheduling,
paging, IPC, routing), the OS achieves mathematical consistency that
binary operating systems lack. Every component speaks the same language:
pressure, viscosity, Reynolds number, laminar vs turbulent flow.

---

*This specification defines the ternary OS layer for NovaX. All designs
use balanced ternary {-1, 0, +1}, respect the 3-5-7-13 harmonic constants,
and integrate with existing NovaX infrastructure (TResource, Reynolds
routing, Hivemind N-S scatter).*

*The ternary OS does not replace Windows — it runs ABOVE it as a
virtualized layer managing NovaX services, just as the orchestrator
already manages 26+ services today.*
