#Requires -RunAsAdministrator
<#
.SYNOPSIS
    NovaX AI Workstation Process Priority Watchdog
.DESCRIPTION
    Continuously monitors and sets process priorities, CPU affinity, and I/O priority
    for an AI workstation running NovaX services. Runs every 30 seconds.

    Priority tiers:
      TIER 1 (AI Critical):  ollama, python, nova_*, rustc, cargo  → High/AboveNormal
      TIER 2 (System Bloat): SearchUI, Defender, Widgets, etc.     → Idle/BelowNormal

    CPU Affinity (16-core layout):
      Cores 0-7   (perf):  Ollama
      Cores 0-15  (all):   Python/Nova services
      Cores 14-15 (last):  System bloat

    I/O Priority:
      AI processes:   High (3)
      Background:     Low (1)
.NOTES
    Author:  NovaX Toolchain
    Version: 1.0.0
    Run:     powershell -ExecutionPolicy Bypass -File Set-AIProcessPriorities.ps1
#>

# ─────────────────────────────────────────────────────────────────────
# P/Invoke for NtSetInformationProcess (I/O priority)
# ─────────────────────────────────────────────────────────────────────
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public static class NtDll
{
    // ProcessIoPriority = 33
    [DllImport("ntdll.dll", SetLastError = true)]
    public static extern int NtSetInformationProcess(
        IntPtr ProcessHandle,
        int ProcessInformationClass,
        ref int ProcessInformation,
        int ProcessInformationLength
    );

    public const int ProcessIoPriority = 33;
    public const int IoPriorityLow     = 1;
    public const int IoPriorityNormal  = 2;
    public const int IoPriorityHigh    = 3;
}
"@ -ErrorAction SilentlyContinue

# ─────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────
$WATCHDOG_INTERVAL = 30  # seconds between scans

# CPU affinity masks (for 16-core / 16-thread CPUs)
# Core 0 = bit 0, Core 15 = bit 15
$AFFINITY_PERF_CORES   = 0x00FF   # cores 0-7   (0b0000000011111111)
$AFFINITY_ALL_CORES    = 0xFFFF   # cores 0-15   (0b1111111111111111)
$AFFINITY_LAST_2_CORES = 0xC000   # cores 14-15  (0b1100000000000000)

# ── TIER 1: AI / High-Priority Processes ──
$AI_REALTIME = @(
    "ollama"               # LLM inference engine — maximum priority
    "ollama_llama_server"  # ollama spawned server
)

$AI_ABOVE_NORMAL = @(
    "python"
    "python3"
    "pythonw"
    "rustc"
    "cargo"
)

# Wildcard patterns matched separately
$AI_WILDCARD_PATTERNS = @(
    "nova_*"
)

# ── TIER 2: System Bloat / Low-Priority Processes ──
$BLOAT_IDLE = @(
    "SearchUI"
    "SearchHost"
    "SearchApp"
    "backgroundTaskHost"
    "WidgetService"
    "Widgets"
    "PhoneExperienceHost"
    "YourPhoneServer"
    "Microsoft.Photos"
    "GameBarPresenceWriter"
    "GameBar"
    "GameBarFTServer"
    "HxTsr"                     # Outlook background sync
    "MusNotification"           # Windows Update notification
    "TextInputHost"             # Touch keyboard (not needed on desktop)
    "LockApp"                   # Lock screen app
    "StartMenuExperienceHost"   # Start menu (low when not in use)
    "ShellExperienceHost"       # Shell chrome
    "CompatTelRunner"           # Telemetry
    "DeviceCensus"              # Telemetry
    "MoUsoCoreWorker"           # Update orchestrator
)

$BLOAT_BELOW_NORMAL = @(
    "MsMpEng"                   # Windows Defender antimalware
    "NisSrv"                    # Defender network inspection
    "SecurityHealthService"
    "RuntimeBroker"
    "SgrmBroker"                # System Guard runtime broker
    "ctfmon"                    # Text framework (keep running, just lower)
    "svchost"                   # NOTE: only specific ones, see filter below
)

# svchost instances to deprioritize (by command-line match)
$SVCHOST_DEPRIORITIZE_ARGS = @(
    "WSearch"
    "DiagTrack"
    "DusmSvc"
    "WpnService"
    "TokenBroker"
)

# ─────────────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────────────

function Set-IoPriority {
    param(
        [System.Diagnostics.Process]$Process,
        [int]$Priority  # 1=Low, 2=Normal, 3=High
    )
    try {
        $handle = $Process.Handle
        $prio = $Priority
        $result = [NtDll]::NtSetInformationProcess(
            $handle,
            [NtDll]::ProcessIoPriority,
            [ref]$prio,
            4
        )
        if ($result -ne 0) {
            # STATUS_ACCESS_DENIED or other NT status — silently skip
            return $false
        }
        return $true
    }
    catch {
        return $false
    }
}

function Set-ProcessConfig {
    param(
        [System.Diagnostics.Process]$Process,
        [System.Diagnostics.ProcessPriorityClass]$Priority,
        [Nullable[long]]$Affinity = $null,
        [int]$IoPrio = 2
    )

    $name = $Process.ProcessName
    $pid  = $Process.Id

    try {
        # Set CPU priority
        if ($Process.PriorityClass -ne $Priority) {
            $Process.PriorityClass = $Priority
            Write-Host "  [PRI] $name ($pid) → $Priority" -ForegroundColor Cyan
        }

        # Set CPU affinity
        if ($null -ne $Affinity) {
            $currentAffinity = $Process.ProcessorAffinity.ToInt64()
            if ($currentAffinity -ne $Affinity) {
                $Process.ProcessorAffinity = [IntPtr]$Affinity
                $coreList = Get-CoreListFromMask $Affinity
                Write-Host "  [AFF] $name ($pid) → cores $coreList" -ForegroundColor Yellow
            }
        }

        # Set I/O priority
        $ioResult = Set-IoPriority -Process $Process -Priority $IoPrio
        if ($ioResult) {
            $ioLabel = switch ($IoPrio) { 1 {"Low"} 2 {"Normal"} 3 {"High"} }
            # Only log on first set (avoid spam) — we log unconditionally for clarity
        }
    }
    catch [System.ComponentModel.Win32Exception] {
        # Access denied for protected processes (e.g., svchost, csrss)
        # Silently skip
    }
    catch {
        Write-Host "  [ERR] $name ($pid): $($_.Exception.Message)" -ForegroundColor Red
    }
}

function Get-CoreListFromMask {
    param([long]$Mask)
    $cores = @()
    for ($i = 0; $i -lt 64; $i++) {
        if ($Mask -band (1L -shl $i)) { $cores += $i }
    }
    if ($cores.Count -le 4) {
        return ($cores -join ",")
    }
    return "$($cores[0])-$($cores[-1])"
}

function Get-ProcessesByWildcard {
    param([string]$Pattern)
    Get-Process | Where-Object { $_.ProcessName -like $Pattern } 2>$null
}

# ─────────────────────────────────────────────────────────────────────
# MAIN WATCHDOG LOOP
# ─────────────────────────────────────────────────────────────────────

$iteration = 0

Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Magenta
Write-Host "  NovaX AI Process Priority Watchdog v1.0.0" -ForegroundColor White
Write-Host "  Scan interval: ${WATCHDOG_INTERVAL}s | Ctrl+C to stop" -ForegroundColor Gray
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Magenta
Write-Host ""

while ($true) {
    $iteration++
    $timestamp = Get-Date -Format "HH:mm:ss"
    $changes = 0

    Write-Host "[$timestamp] Scan #$iteration" -ForegroundColor DarkGray

    # ── TIER 1A: Ollama → Realtime + Perf Cores + High I/O ──
    foreach ($name in $AI_REALTIME) {
        $procs = Get-Process -Name $name -ErrorAction SilentlyContinue
        foreach ($p in $procs) {
            # Use High instead of Realtime to avoid system instability
            # Realtime can starve critical OS threads and cause hangs
            Set-ProcessConfig -Process $p `
                -Priority ([System.Diagnostics.ProcessPriorityClass]::High) `
                -Affinity $AFFINITY_PERF_CORES `
                -IoPrio 3
            $changes++
        }
    }

    # ── TIER 1B: Python / Rust / Nova → AboveNormal + All Cores + High I/O ──
    foreach ($name in $AI_ABOVE_NORMAL) {
        $procs = Get-Process -Name $name -ErrorAction SilentlyContinue
        foreach ($p in $procs) {
            Set-ProcessConfig -Process $p `
                -Priority ([System.Diagnostics.ProcessPriorityClass]::AboveNormal) `
                -Affinity $AFFINITY_ALL_CORES `
                -IoPrio 3
            $changes++
        }
    }

    # ── TIER 1C: Wildcard nova_* processes ──
    foreach ($pattern in $AI_WILDCARD_PATTERNS) {
        $procs = Get-ProcessesByWildcard -Pattern $pattern
        foreach ($p in $procs) {
            Set-ProcessConfig -Process $p `
                -Priority ([System.Diagnostics.ProcessPriorityClass]::AboveNormal) `
                -Affinity $AFFINITY_ALL_CORES `
                -IoPrio 3
            $changes++
        }
    }

    # ── TIER 2A: Bloat → Idle + Last 2 Cores + Low I/O ──
    foreach ($name in $BLOAT_IDLE) {
        $procs = Get-Process -Name $name -ErrorAction SilentlyContinue
        foreach ($p in $procs) {
            Set-ProcessConfig -Process $p `
                -Priority ([System.Diagnostics.ProcessPriorityClass]::Idle) `
                -Affinity $AFFINITY_LAST_2_CORES `
                -IoPrio 1
            $changes++
        }
    }

    # ── TIER 2B: Defender / RuntimeBroker → BelowNormal + Last 2 Cores + Low I/O ──
    foreach ($name in $BLOAT_BELOW_NORMAL) {
        # Special handling for svchost — only deprioritize specific service groups
        if ($name -eq "svchost") {
            foreach ($argMatch in $SVCHOST_DEPRIORITIZE_ARGS) {
                $procs = Get-CimInstance Win32_Process -Filter "Name='svchost.exe'" -ErrorAction SilentlyContinue |
                    Where-Object { $_.CommandLine -match $argMatch }
                foreach ($cimProc in $procs) {
                    try {
                        $p = Get-Process -Id $cimProc.ProcessId -ErrorAction SilentlyContinue
                        if ($p) {
                            Set-ProcessConfig -Process $p `
                                -Priority ([System.Diagnostics.ProcessPriorityClass]::BelowNormal) `
                                -Affinity $AFFINITY_LAST_2_CORES `
                                -IoPrio 1
                            $changes++
                        }
                    } catch {}
                }
            }
            continue
        }

        $procs = Get-Process -Name $name -ErrorAction SilentlyContinue
        foreach ($p in $procs) {
            Set-ProcessConfig -Process $p `
                -Priority ([System.Diagnostics.ProcessPriorityClass]::BelowNormal) `
                -Affinity $AFFINITY_LAST_2_CORES `
                -IoPrio 1
            $changes++
        }
    }

    # ── Summary ──
    if ($changes -eq 0) {
        Write-Host "  [OK] No changes needed" -ForegroundColor DarkGray
    }
    else {
        Write-Host "  [OK] $changes process(es) configured" -ForegroundColor Green
    }

    # ── Sleep until next scan ──
    Start-Sleep -Seconds $WATCHDOG_INTERVAL
}
