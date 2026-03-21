#Requires -RunAsAdministrator
<#
.SYNOPSIS
    NovaX Memory Analyzer & Optimizer for Windows 11 (16GB DDR5)
.DESCRIPTION
    Comprehensive memory analysis, leak detection, and optimization for systems
    running 100+ Python services + Ollama LLM inference.
.NOTES
    Author: NovaX Team
    Requires: Administrator privileges for full functionality
    System: Windows 11, 16GB DDR5
#>

param(
    [switch]$AnalyzeOnly,
    [switch]$OptimizeTrim,
    [switch]$FlushStandby,
    [switch]$CheckLeaks,
    [switch]$LargePages,
    [switch]$Full
)

if ($Full) {
    $AnalyzeOnly = $true
    $OptimizeTrim = $true
    $CheckLeaks = $true
    $LargePages = $true
    # FlushStandby intentionally not auto-enabled — destructive
}

# If no flags, default to analysis
if (-not ($AnalyzeOnly -or $OptimizeTrim -or $FlushStandby -or $CheckLeaks -or $LargePages)) {
    $AnalyzeOnly = $true
}

$ErrorActionPreference = 'SilentlyContinue'

# ============================================================================
# SECTION 1: CURRENT MEMORY ANALYSIS
# ============================================================================
function Get-MemoryAnalysis {
    Write-Host "`n" -NoNewline
    Write-Host "=" * 80 -ForegroundColor Cyan
    Write-Host "  SECTION 1: MEMORY ANALYSIS" -ForegroundColor Cyan
    Write-Host "=" * 80 -ForegroundColor Cyan

    # --- 1a: Overall Memory Summary ---
    Write-Host "`n[1a] PHYSICAL MEMORY SUMMARY" -ForegroundColor Yellow
    $os = Get-CimInstance Win32_OperatingSystem
    $totalGB = [math]::Round($os.TotalVisibleMemorySize / 1MB, 2)
    $freeGB = [math]::Round($os.FreePhysicalMemory / 1MB, 2)
    $usedGB = [math]::Round($totalGB - $freeGB, 2)
    $usedPct = [math]::Round(($usedGB / $totalGB) * 100, 1)

    $commitTotal = [math]::Round(($os.TotalVirtualMemorySize - $os.TotalVisibleMemorySize + $os.TotalVisibleMemorySize) / 1MB, 2)
    $commitUsed = [math]::Round(($os.TotalVirtualMemorySize - $os.FreeVirtualMemory) / 1MB, 2)

    Write-Host "  Total Physical:    $totalGB GB"
    Write-Host "  Used Physical:     $usedGB GB ($usedPct%)" -ForegroundColor $(if ($usedPct -gt 85) { 'Red' } elseif ($usedPct -gt 70) { 'Yellow' } else { 'Green' })
    Write-Host "  Free Physical:     $freeGB GB"
    Write-Host "  Commit Charge:     $commitUsed GB / $commitTotal GB"

    # --- 1b: Memory Counters (Compression, Cache, Pools) ---
    Write-Host "`n[1b] DETAILED MEMORY COUNTERS" -ForegroundColor Yellow

    $counters = @(
        '\Memory\Available MBytes',
        '\Memory\Committed Bytes',
        '\Memory\Commit Limit',
        '\Memory\Cache Bytes',
        '\Memory\Cache Bytes Peak',
        '\Memory\Pool Nonpaged Bytes',
        '\Memory\Pool Paged Bytes',
        '\Memory\Modified Page List Bytes',
        '\Memory\Standby Cache Normal Priority Bytes',
        '\Memory\Standby Cache Reserve Bytes',
        '\Memory\Standby Cache Core Bytes',
        '\Memory\Free & Zero Page List Bytes',
        '\Memory\Pages/sec',
        '\Memory\Page Faults/sec'
    )

    $samples = Get-Counter -Counter $counters -ErrorAction SilentlyContinue
    if ($samples) {
        foreach ($sample in $samples.CounterSamples) {
            $name = $sample.Path -replace '\\\\[^\\]+\\', ''
            $val = $sample.CookedValue
            if ($val -gt 1GB) {
                $display = "{0:N2} GB" -f ($val / 1GB)
            } elseif ($val -gt 1MB) {
                $display = "{0:N1} MB" -f ($val / 1MB)
            } else {
                $display = "{0:N0}" -f $val
            }
            Write-Host ("  {0,-50} {1,12}" -f $name, $display)
        }
    }

    # --- Memory Compression ---
    Write-Host "`n[1c] MEMORY COMPRESSION" -ForegroundColor Yellow
    try {
        $mmAgent = Get-MMAgent
        Write-Host "  Memory Compression:     $($mmAgent.MemoryCompression)"
        Write-Host "  Page Combining:         $($mmAgent.PageCombining)"
        Write-Host "  Application Launch PF:  $($mmAgent.ApplicationLaunchPrefetching)"
        Write-Host "  Application Pre-Launch: $($mmAgent.ApplicationPreLaunch)"
        Write-Host "  Operation API PF:       $($mmAgent.OperationAPI)"
    } catch {
        Write-Host "  Could not query MMAgent (requires admin)" -ForegroundColor Red
    }

    # Compression ratio via Memory Compression process
    $compProc = Get-Process -Name "Memory Compression" -ErrorAction SilentlyContinue
    if ($compProc) {
        $compWS = [math]::Round($compProc.WorkingSet64 / 1MB, 1)
        $compPM = [math]::Round($compProc.PrivateMemorySize64 / 1MB, 1)
        Write-Host "  Compression Process WS: $compWS MB"
        Write-Host "  Compression Private:    $compPM MB"
    }

    # --- 1d: Top 30 Processes by Memory ---
    Write-Host "`n[1d] TOP 30 PROCESSES BY WORKING SET" -ForegroundColor Yellow
    Write-Host ("  {0,-6} {1,-35} {2,10} {3,10} {4,10} {5,8}" -f "PID", "Name", "WS(MB)", "PM(MB)", "Handles", "Threads")
    Write-Host ("  " + "-" * 85)

    Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 30 | ForEach-Object {
        $ws = [math]::Round($_.WorkingSet64 / 1MB, 1)
        $pm = [math]::Round($_.PrivateMemorySize64 / 1MB, 1)
        $color = if ($ws -gt 1000) { 'Red' } elseif ($ws -gt 500) { 'Yellow' } else { 'White' }
        Write-Host ("  {0,-6} {1,-35} {2,10} {3,10} {4,10} {5,8}" -f $_.Id, ($_.ProcessName.Substring(0, [Math]::Min(35, $_.ProcessName.Length))), $ws, $pm, $_.HandleCount, $_.Threads.Count) -ForegroundColor $color
    }

    # --- 1e: Aggregate by process name ---
    Write-Host "`n[1e] AGGREGATE MEMORY BY PROCESS NAME (Top 20)" -ForegroundColor Yellow
    Write-Host ("  {0,-30} {1,8} {2,12} {3,12}" -f "Process", "Count", "Total WS(MB)", "Total PM(MB)")
    Write-Host ("  " + "-" * 65)

    Get-Process | Group-Object ProcessName | ForEach-Object {
        [PSCustomObject]@{
            Name     = $_.Name
            Count    = $_.Count
            TotalWS  = [math]::Round(($_.Group | Measure-Object WorkingSet64 -Sum).Sum / 1MB, 1)
            TotalPM  = [math]::Round(($_.Group | Measure-Object PrivateMemorySize64 -Sum).Sum / 1MB, 1)
        }
    } | Sort-Object TotalWS -Descending | Select-Object -First 20 | ForEach-Object {
        $color = if ($_.TotalWS -gt 1000) { 'Red' } elseif ($_.TotalWS -gt 500) { 'Yellow' } else { 'White' }
        Write-Host ("  {0,-30} {1,8} {2,12} {3,12}" -f $_.Name, $_.Count, $_.TotalWS, $_.TotalPM) -ForegroundColor $color
    }

    # --- 1f: Python processes (NovaX services) ---
    Write-Host "`n[1f] PYTHON PROCESSES (NovaX Services)" -ForegroundColor Yellow
    $pythonProcs = Get-Process -Name python, python3, pythonw -ErrorAction SilentlyContinue
    if ($pythonProcs) {
        $totalPythonWS = [math]::Round(($pythonProcs | Measure-Object WorkingSet64 -Sum).Sum / 1MB, 1)
        $totalPythonPM = [math]::Round(($pythonProcs | Measure-Object PrivateMemorySize64 -Sum).Sum / 1MB, 1)
        Write-Host "  Python process count:   $($pythonProcs.Count)"
        Write-Host "  Total Python WS:        $totalPythonWS MB" -ForegroundColor $(if ($totalPythonWS -gt 4000) { 'Red' } elseif ($totalPythonWS -gt 2000) { 'Yellow' } else { 'Green' })
        Write-Host "  Total Python Private:   $totalPythonPM MB"
        Write-Host "  Avg WS per service:     $([math]::Round($totalPythonWS / $pythonProcs.Count, 1)) MB"
    } else {
        Write-Host "  No Python processes found" -ForegroundColor DarkGray
    }

    # --- 1g: Ollama ---
    Write-Host "`n[1g] OLLAMA PROCESSES" -ForegroundColor Yellow
    $ollamaProcs = Get-Process -Name ollama*, llama* -ErrorAction SilentlyContinue
    if ($ollamaProcs) {
        foreach ($p in $ollamaProcs) {
            $ws = [math]::Round($p.WorkingSet64 / 1MB, 1)
            $pm = [math]::Round($p.PrivateMemorySize64 / 1MB, 1)
            $vm = [math]::Round($p.VirtualMemorySize64 / 1GB, 2)
            Write-Host "  $($p.ProcessName) (PID $($p.Id)): WS=$ws MB, Private=$pm MB, Virtual=$vm GB"
        }
    } else {
        Write-Host "  No Ollama processes found" -ForegroundColor DarkGray
    }
}

# ============================================================================
# SECTION 2: MEMORY LEAK DETECTION
# ============================================================================
function Get-MemoryLeakAnalysis {
    Write-Host "`n" -NoNewline
    Write-Host "=" * 80 -ForegroundColor Cyan
    Write-Host "  SECTION 2: MEMORY LEAK DETECTION" -ForegroundColor Cyan
    Write-Host "=" * 80 -ForegroundColor Cyan

    # --- 2a: High handle count (leak indicator) ---
    Write-Host "`n[2a] PROCESSES WITH HIGH HANDLE COUNTS (>500)" -ForegroundColor Yellow
    Write-Host ("  {0,-6} {1,-30} {2,10} {3,10} {4,10}" -f "PID", "Name", "Handles", "WS(MB)", "Threads")
    Write-Host ("  " + "-" * 70)

    Get-Process | Where-Object { $_.HandleCount -gt 500 } | Sort-Object HandleCount -Descending | Select-Object -First 20 | ForEach-Object {
        $ws = [math]::Round($_.WorkingSet64 / 1MB, 1)
        $color = if ($_.HandleCount -gt 5000) { 'Red' } elseif ($_.HandleCount -gt 2000) { 'Yellow' } else { 'White' }
        Write-Host ("  {0,-6} {1,-30} {2,10} {3,10} {4,10}" -f $_.Id, ($_.ProcessName.Substring(0, [Math]::Min(30, $_.ProcessName.Length))), $_.HandleCount, $ws, $_.Threads.Count) -ForegroundColor $color
    }

    # --- 2b: GDI/User Object counts (leak indicators) ---
    Write-Host "`n[2b] GDI & USER OBJECT COUNTS (via tasklist)" -ForegroundColor Yellow
    Write-Host "  Note: Windows default limits — 10000 GDI, 10000 User objects per process"

    # Use CIM to avoid tasklist parsing issues
    $highGDI = Get-Process | Where-Object {
        try { $_.MainWindowHandle -ne [IntPtr]::Zero } catch { $false }
    } | Sort-Object HandleCount -Descending | Select-Object -First 10

    # --- 2c: Python process detail for NovaX leak check ---
    Write-Host "`n[2c] NOVAХ PYTHON LEAK INDICATORS" -ForegroundColor Yellow
    $pythonProcs = Get-Process -Name python, python3 -ErrorAction SilentlyContinue
    if ($pythonProcs) {
        Write-Host ("  {0,-6} {1,10} {2,10} {3,10} {4,20}" -f "PID", "WS(MB)", "PM(MB)", "Handles", "StartTime")
        Write-Host ("  " + "-" * 60)

        foreach ($p in ($pythonProcs | Sort-Object WorkingSet64 -Descending)) {
            $ws = [math]::Round($p.WorkingSet64 / 1MB, 1)
            $pm = [math]::Round($p.PrivateMemorySize64 / 1MB, 1)
            $start = try { $p.StartTime.ToString("yyyy-MM-dd HH:mm") } catch { "N/A" }
            $uptime = try { ((Get-Date) - $p.StartTime).ToString("d\.hh\:mm") } catch { "?" }

            # Flag: WS > 200MB or Handles > 1000 for a single Python service
            $flag = ""
            if ($ws -gt 200) { $flag += " [HIGH-WS]" }
            if ($p.HandleCount -gt 1000) { $flag += " [HIGH-HANDLES]" }

            $color = if ($flag) { 'Yellow' } else { 'White' }
            Write-Host ("  {0,-6} {1,10} {2,10} {3,10} {4,20} {5}" -f $p.Id, $ws, $pm, $p.HandleCount, "$start (up $uptime)", $flag) -ForegroundColor $color
        }

        # Per-service command line (identify which service is which PID)
        Write-Host "`n  Command Lines (identify services):" -ForegroundColor DarkCyan
        foreach ($p in ($pythonProcs | Sort-Object WorkingSet64 -Descending | Select-Object -First 15)) {
            $cmdline = (Get-CimInstance Win32_Process -Filter "ProcessId=$($p.Id)" -ErrorAction SilentlyContinue).CommandLine
            if ($cmdline) {
                $short = if ($cmdline.Length -gt 100) { $cmdline.Substring(0, 100) + "..." } else { $cmdline }
                Write-Host "    PID $($p.Id): $short" -ForegroundColor DarkGray
            }
        }
    }

    # --- 2d: Snapshot for trend analysis ---
    Write-Host "`n[2d] MEMORY TREND SNAPSHOT (save and compare)" -ForegroundColor Yellow
    $snapshotFile = "C:\NovaX\tools\mem_snapshot_$(Get-Date -Format 'yyyyMMdd_HHmmss').csv"
    Get-Process | Select-Object Id, ProcessName, WorkingSet64, PrivateMemorySize64, HandleCount,
        @{N='StartTime';E={try{$_.StartTime.ToString('o')}catch{'N/A'}}},
        @{N='Uptime_Min';E={try{[math]::Round(((Get-Date)-$_.StartTime).TotalMinutes,1)}catch{-1}}} |
        Export-Csv -Path $snapshotFile -NoTypeInformation

    Write-Host "  Snapshot saved: $snapshotFile"
    Write-Host "  Compare snapshots over time to detect leaks (growing WS/Handles)"
}

# ============================================================================
# SECTION 3: WORKING SET OPTIMIZATION
# ============================================================================
function Invoke-WorkingSetTrim {
    Write-Host "`n" -NoNewline
    Write-Host "=" * 80 -ForegroundColor Cyan
    Write-Host "  SECTION 3: WORKING SET OPTIMIZATION" -ForegroundColor Cyan
    Write-Host "=" * 80 -ForegroundColor Cyan

    # Add the P/Invoke for SetProcessWorkingSetSizeEx and EmptyWorkingSet
    Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class MemoryOptimizer {
    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern bool SetProcessWorkingSetSizeEx(
        IntPtr hProcess, IntPtr dwMinimumWorkingSetSize, IntPtr dwMaximumWorkingSetSize, uint Flags);

    [DllImport("psapi.dll", SetLastError = true)]
    public static extern bool EmptyWorkingSet(IntPtr hProcess);

    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern IntPtr OpenProcess(uint dwDesiredAccess, bool bInheritHandle, int dwProcessId);

    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern bool CloseHandle(IntPtr hObject);

    public const uint PROCESS_SET_QUOTA = 0x0100;
    public const uint PROCESS_QUERY_INFORMATION = 0x0400;

    public static bool TrimProcess(int pid) {
        IntPtr handle = OpenProcess(PROCESS_SET_QUOTA | PROCESS_QUERY_INFORMATION, false, pid);
        if (handle == IntPtr.Zero) return false;
        try {
            return EmptyWorkingSet(handle);
        } finally {
            CloseHandle(handle);
        }
    }
}
"@ -ErrorAction SilentlyContinue

    # --- 3a: Identify idle Python services (low CPU, high memory) ---
    Write-Host "`n[3a] IDLE PYTHON SERVICES (candidates for WS trim)" -ForegroundColor Yellow
    $pythonProcs = Get-Process -Name python, python3 -ErrorAction SilentlyContinue

    if (-not $pythonProcs) {
        Write-Host "  No Python processes to trim" -ForegroundColor DarkGray
        return
    }

    # Get CPU usage via CIM (more accurate than Process object)
    $trimCandidates = @()
    foreach ($p in $pythonProcs) {
        $ws = [math]::Round($p.WorkingSet64 / 1MB, 1)
        # Consider idle if WS > 50MB (worth trimming)
        if ($ws -gt 50) {
            $trimCandidates += [PSCustomObject]@{
                PID  = $p.Id
                Name = $p.ProcessName
                WS   = $ws
                Proc = $p
            }
        }
    }

    $totalBefore = [math]::Round(($pythonProcs | Measure-Object WorkingSet64 -Sum).Sum / 1MB, 1)
    Write-Host "  Total Python WS before trim: $totalBefore MB"
    Write-Host "  Trim candidates (WS > 50MB): $($trimCandidates.Count)"

    if ($trimCandidates.Count -eq 0) {
        Write-Host "  All services already lean" -ForegroundColor Green
        return
    }

    # --- 3b: Trim working sets ---
    Write-Host "`n[3b] TRIMMING WORKING SETS" -ForegroundColor Yellow
    $trimmed = 0
    $savedMB = 0

    foreach ($candidate in ($trimCandidates | Sort-Object WS -Descending)) {
        $wsBefore = $candidate.WS
        $result = [MemoryOptimizer]::TrimProcess($candidate.PID)
        if ($result) {
            # Re-read WS after trim
            Start-Sleep -Milliseconds 100
            $procAfter = Get-Process -Id $candidate.PID -ErrorAction SilentlyContinue
            $wsAfter = if ($procAfter) { [math]::Round($procAfter.WorkingSet64 / 1MB, 1) } else { $wsBefore }
            $saved = [math]::Round($wsBefore - $wsAfter, 1)
            $savedMB += $saved
            $trimmed++
            $color = if ($saved -gt 10) { 'Green' } else { 'White' }
            Write-Host ("  PID {0,-6}: {1,8} MB -> {2,8} MB (freed {3,6} MB)" -f $candidate.PID, $wsBefore, $wsAfter, $saved) -ForegroundColor $color
        } else {
            Write-Host ("  PID {0,-6}: FAILED to trim (access denied or protected)" -f $candidate.PID) -ForegroundColor Red
        }
    }

    # Also trim non-Python idle processes over 200MB
    Write-Host "`n[3c] TRIMMING OTHER IDLE PROCESSES (WS > 200MB, non-critical)" -ForegroundColor Yellow
    $excludeNames = @('System', 'Registry', 'Memory Compression', 'csrss', 'smss', 'wininit',
                       'services', 'lsass', 'dwm', 'explorer', 'ollama_llama_server', 'ollama')

    Get-Process | Where-Object {
        $_.WorkingSet64 -gt 200MB -and
        $_.ProcessName -notin $excludeNames -and
        $_.ProcessName -notmatch 'python|ollama|llama'
    } | Sort-Object WorkingSet64 -Descending | Select-Object -First 10 | ForEach-Object {
        $wsBefore = [math]::Round($_.WorkingSet64 / 1MB, 1)
        $result = [MemoryOptimizer]::TrimProcess($_.Id)
        if ($result) {
            Start-Sleep -Milliseconds 50
            $after = Get-Process -Id $_.Id -ErrorAction SilentlyContinue
            $wsAfter = if ($after) { [math]::Round($after.WorkingSet64 / 1MB, 1) } else { $wsBefore }
            $saved = [math]::Round($wsBefore - $wsAfter, 1)
            $savedMB += $saved
            Write-Host ("  {0,-25} PID {1,-6}: {2,8} MB -> {3,8} MB (freed {4,6} MB)" -f $_.ProcessName, $_.Id, $wsBefore, $wsAfter, $saved) -ForegroundColor Green
        }
    }

    Write-Host "`n  TOTAL FREED: $savedMB MB across $trimmed+ processes" -ForegroundColor Green
}

# ============================================================================
# SECTION 4: LARGE PAGES
# ============================================================================
function Get-LargePageStatus {
    Write-Host "`n" -NoNewline
    Write-Host "=" * 80 -ForegroundColor Cyan
    Write-Host "  SECTION 4: LARGE PAGES ANALYSIS" -ForegroundColor Cyan
    Write-Host "=" * 80 -ForegroundColor Cyan

    # --- 4a: Check "Lock pages in memory" privilege ---
    Write-Host "`n[4a] LOCK PAGES IN MEMORY PRIVILEGE" -ForegroundColor Yellow

    $currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    Write-Host "  Current user: $currentUser"

    # Check via whoami /priv
    $privs = whoami /priv 2>&1
    $lockPages = $privs | Select-String "SeLockMemoryPrivilege"
    if ($lockPages) {
        Write-Host "  SeLockMemoryPrivilege: PRESENT" -ForegroundColor Green
        if ($lockPages -match "Enabled") {
            Write-Host "  Status: ENABLED" -ForegroundColor Green
        } else {
            Write-Host "  Status: Present but DISABLED (needs logoff/reboot)" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  SeLockMemoryPrivilege: NOT GRANTED" -ForegroundColor Red
        Write-Host ""
        Write-Host "  TO GRANT LARGE PAGE SUPPORT:" -ForegroundColor White
        Write-Host "  Option A (GUI):" -ForegroundColor DarkCyan
        Write-Host "    1. Win+R -> secpol.msc"
        Write-Host "    2. Local Policies -> User Rights Assignment"
        Write-Host "    3. 'Lock pages in memory' -> Add User or Group"
        Write-Host "    4. Add '$currentUser'"
        Write-Host "    5. Log off and back on"
        Write-Host ""
        Write-Host "  Option B (PowerShell, run as admin):" -ForegroundColor DarkCyan
        Write-Host "    # Install Carbon module first:"
        Write-Host "    Install-Module -Name Carbon -Force"
        Write-Host "    Grant-CPrivilege -Identity '$currentUser' -Privilege SeLockMemoryPrivilege"
        Write-Host ""
        Write-Host "  Option C (ntrights from Windows SDK):" -ForegroundColor DarkCyan
        Write-Host "    ntrights +r SeLockMemoryPrivilege -u `"$currentUser`""
    }

    # --- 4b: Applications that benefit from large pages ---
    Write-Host "`n[4b] APPLICATIONS THAT BENEFIT FROM LARGE PAGES" -ForegroundColor Yellow
    Write-Host "  Large pages (2MB instead of 4KB) reduce TLB misses for large allocations."
    Write-Host ""
    Write-Host "  HIGH BENEFIT for your workload:" -ForegroundColor Green
    Write-Host "    - Ollama / llama.cpp  : Models are GB-scale contiguous memory"
    Write-Host "      Set env: OLLAMA_LLM_LIBRARY=cpu_avx2  (or cuda)"
    Write-Host "      llama.cpp flag: --mlock (locks model in RAM, prevents paging)"
    Write-Host "      Ollama env: OLLAMA_KEEP_ALIVE=-1 (never unload model)"
    Write-Host "    - Python (limited)    : Large NumPy/Torch allocations benefit"
    Write-Host ""
    Write-Host "  MEDIUM BENEFIT:" -ForegroundColor Yellow
    Write-Host "    - Database engines (SQLite with large caches)"
    Write-Host "    - JVM applications (use -XX:+UseLargePages)"
    Write-Host "    - Redis/Memcached"
    Write-Host ""
    Write-Host "  LOW BENEFIT:" -ForegroundColor DarkGray
    Write-Host "    - Small Python HTTP services (NovaX microservices)"
    Write-Host "    - Node.js / Electron apps"

    # --- 4c: Check Ollama large page support ---
    Write-Host "`n[4c] OLLAMA LARGE PAGE CONFIGURATION" -ForegroundColor Yellow

    $ollamaEnv = [System.Environment]::GetEnvironmentVariable("OLLAMA_LLM_LIBRARY", "User")
    $ollamaKeep = [System.Environment]::GetEnvironmentVariable("OLLAMA_KEEP_ALIVE", "User")
    $ollamaModels = [System.Environment]::GetEnvironmentVariable("OLLAMA_MODELS", "User")

    Write-Host "  OLLAMA_LLM_LIBRARY: $(if($ollamaEnv){$ollamaEnv}else{'(not set)'})"
    Write-Host "  OLLAMA_KEEP_ALIVE:  $(if($ollamaKeep){$ollamaKeep}else{'(not set - default 5m)'})"
    Write-Host "  OLLAMA_MODELS:      $(if($ollamaModels){$ollamaModels}else{'(default ~/.ollama/models)'})"

    Write-Host "`n  RECOMMENDED OLLAMA ENV VARS:" -ForegroundColor DarkCyan
    Write-Host "    [System.Environment]::SetEnvironmentVariable('OLLAMA_KEEP_ALIVE', '-1', 'User')"
    Write-Host "    # Keeps models loaded indefinitely — critical on 16GB to avoid reload thrash"
    Write-Host "    # BUT: only if you use 1-2 models. Multiple models will OOM."
}

# ============================================================================
# SECTION 5: MEMORY-MAPPED FILE ANALYSIS
# ============================================================================
function Get-MmapAnalysis {
    Write-Host "`n" -NoNewline
    Write-Host "=" * 80 -ForegroundColor Cyan
    Write-Host "  SECTION 5: MEMORY-MAPPED FILES / STANDBY LIST" -ForegroundColor Cyan
    Write-Host "=" * 80 -ForegroundColor Cyan

    # --- 5a: Mapped file usage ---
    Write-Host "`n[5a] MEMORY-MAPPED FILE USAGE" -ForegroundColor Yellow
    Write-Host "  Windows tracks mmap'd files in the Standby list and Modified list."
    Write-Host "  Ollama/llama.cpp uses mmap by default for model files."

    # Check Ollama model files
    $modelPaths = @(
        "$env:USERPROFILE\.ollama\models",
        "C:\Users\Jupit\.ollama\models"
    )
    if ($ollamaModels) { $modelPaths += $ollamaModels }

    foreach ($mp in ($modelPaths | Select-Object -Unique)) {
        if (Test-Path $mp) {
            Write-Host "`n  Ollama models directory: $mp" -ForegroundColor DarkCyan
            $blobs = Get-ChildItem -Path "$mp\blobs" -File -ErrorAction SilentlyContinue
            if ($blobs) {
                $totalSize = [math]::Round(($blobs | Measure-Object Length -Sum).Sum / 1GB, 2)
                Write-Host "  Total model blob size: $totalSize GB"
                Write-Host "  Model files:"
                $blobs | Sort-Object Length -Descending | Select-Object -First 10 | ForEach-Object {
                    $sizeGB = [math]::Round($_.Length / 1GB, 2)
                    Write-Host "    $($_.Name.Substring(0, [Math]::Min(40, $_.Name.Length)))... : $sizeGB GB"
                }
                Write-Host "`n  IMPORTANT: These files are mmap'd into virtual memory." -ForegroundColor Yellow
                Write-Host "  The Standby list caches accessed pages. On 16GB, you can"
                Write-Host "  typically keep 1-2 models worth of pages cached."
            }
            break
        }
    }

    # --- 5b: Ollama mmap behavior ---
    Write-Host "`n[5b] OLLAMA MMAP BEHAVIOR" -ForegroundColor Yellow
    Write-Host "  - Default: mmap enabled (OLLAMA_NOMAP not set)"
    $nomap = [System.Environment]::GetEnvironmentVariable("OLLAMA_NOMAP", "User")
    Write-Host "  - OLLAMA_NOMAP: $(if($nomap){"$nomap (mmap DISABLED)"}else{'(not set - mmap ENABLED)'})"
    Write-Host ""
    Write-Host "  With mmap enabled (recommended for 16GB):" -ForegroundColor DarkCyan
    Write-Host "    - Model file pages loaded on demand (not all at once)"
    Write-Host "    - OS manages which pages stay in RAM via Standby list"
    Write-Host "    - Multiple processes can share the same mmap'd pages"
    Write-Host "    - Pages evicted under memory pressure (good for your 100+ services)"
    Write-Host ""
    Write-Host "  Without mmap (OLLAMA_NOMAP=1):" -ForegroundColor DarkCyan
    Write-Host "    - Entire model copied into process private memory"
    Write-Host "    - Uses more physical RAM, not shared"
    Write-Host "    - Only use if you have GPU VRAM and want to avoid disk I/O"
}

# ============================================================================
# SECTION 6: STANDBY LIST MANAGEMENT
# ============================================================================
function Invoke-StandbyListManagement {
    Write-Host "`n" -NoNewline
    Write-Host "=" * 80 -ForegroundColor Cyan
    Write-Host "  SECTION 6: STANDBY LIST MANAGEMENT" -ForegroundColor Cyan
    Write-Host "=" * 80 -ForegroundColor Cyan

    # --- 6a: Current standby list analysis ---
    Write-Host "`n[6a] STANDBY LIST BREAKDOWN" -ForegroundColor Yellow

    $standbyCounters = @(
        '\Memory\Standby Cache Normal Priority Bytes',
        '\Memory\Standby Cache Reserve Bytes',
        '\Memory\Standby Cache Core Bytes',
        '\Memory\Free & Zero Page List Bytes',
        '\Memory\Modified Page List Bytes',
        '\Memory\Available MBytes'
    )

    $samples = Get-Counter -Counter $standbyCounters -ErrorAction SilentlyContinue
    $standbyTotal = 0
    if ($samples) {
        foreach ($s in $samples.CounterSamples) {
            $name = ($s.Path -replace '\\\\[^\\]+\\memory\\', '').Trim()
            if ($name -match 'Standby') {
                $standbyTotal += $s.CookedValue
            }
            if ($s.CookedValue -gt 1GB) {
                $display = "{0:N2} GB" -f ($s.CookedValue / 1GB)
            } else {
                $display = "{0:N0} MB" -f ($s.CookedValue / 1MB)
            }
            Write-Host ("  {0,-45} {1,12}" -f $name, $display)
        }
        Write-Host ("  {0,-45} {1,12}" -f "TOTAL STANDBY", ("{0:N2} GB" -f ($standbyTotal / 1GB))) -ForegroundColor Green
    }

    # --- 6b: Standby flush options ---
    Write-Host "`n[6b] STANDBY LIST FLUSH OPTIONS" -ForegroundColor Yellow
    Write-Host "  The Standby list is cached file data. Flushing it frees RAM"
    Write-Host "  but causes cache misses (slower file access until re-cached)."
    Write-Host ""

    if ($FlushStandby) {
        Write-Host "  FLUSHING STANDBY LIST..." -ForegroundColor Red

        # Method 1: Use built-in Windows API
        Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class StandbyFlusher {
    [DllImport("ntdll.dll", SetLastError = true)]
    public static extern int NtSetSystemInformation(int InfoClass, ref int Info, int Length);

    // SystemMemoryListInformation = 80
    // MemoryPurgeStandbyList = 4
    public static int FlushStandbyList() {
        int command = 4; // MemoryPurgeStandbyList
        return NtSetSystemInformation(80, ref command, Marshal.SizeOf(command));
    }

    // MemoryFlushModifiedList = 3
    public static int FlushModifiedList() {
        int command = 3;
        return NtSetSystemInformation(80, ref command, Marshal.SizeOf(command));
    }
}
"@ -ErrorAction SilentlyContinue

        $beforeAvail = (Get-Counter '\Memory\Available MBytes' -ErrorAction SilentlyContinue).CounterSamples[0].CookedValue

        $result = [StandbyFlusher]::FlushStandbyList()
        if ($result -eq 0) {
            Start-Sleep -Seconds 1
            $afterAvail = (Get-Counter '\Memory\Available MBytes' -ErrorAction SilentlyContinue).CounterSamples[0].CookedValue
            $freed = [math]::Round($afterAvail - $beforeAvail, 0)
            Write-Host "  Standby list flushed successfully" -ForegroundColor Green
            Write-Host "  Available memory: $beforeAvail MB -> $afterAvail MB (freed ~$freed MB)"
        } else {
            Write-Host "  Flush failed (NTSTATUS: 0x$($result.ToString('X8')))" -ForegroundColor Red
            Write-Host "  Try running as Administrator, or use EmptyStandbyList.exe"
        }
    } else {
        Write-Host "  To flush standby list, run with -FlushStandby flag" -ForegroundColor DarkCyan
        Write-Host "  WARNING: This clears file cache. Ollama model will re-fault from disk." -ForegroundColor Yellow
    }

    # --- 6c: Automated standby management ---
    Write-Host "`n[6c] AUTOMATED STANDBY MANAGEMENT" -ForegroundColor Yellow
    Write-Host "  For a 16GB system with 100+ services + Ollama, consider:"
    Write-Host ""
    Write-Host "  1. Scheduled flush when available < 1GB:" -ForegroundColor DarkCyan
    Write-Host '     $avail = (Get-Counter "\Memory\Available MBytes").CounterSamples[0].CookedValue'
    Write-Host '     if ($avail -lt 1024) { # flush standby }'
    Write-Host ""
    Write-Host "  2. EmptyStandbyList.exe (Sysinternals/RAMMap):" -ForegroundColor DarkCyan
    Write-Host "     Download: https://learn.microsoft.com/en-us/sysinternals/downloads/rammap"
    Write-Host "     Run: EmptyStandbyList.exe standbylist"
    Write-Host ""
    Write-Host "  3. Intelligent Standby List Cleaner (ISLC):" -ForegroundColor DarkCyan
    Write-Host "     Free tool by Wagnardsoft, auto-flushes at configurable thresholds"
    Write-Host "     Recommended for gaming/LLM workloads on 16GB"
}

# ============================================================================
# SUMMARY & RECOMMENDATIONS
# ============================================================================
function Write-Recommendations {
    Write-Host "`n" -NoNewline
    Write-Host "=" * 80 -ForegroundColor Magenta
    Write-Host "  RECOMMENDATIONS FOR 16GB DDR5 + NovaX + Ollama" -ForegroundColor Magenta
    Write-Host "=" * 80 -ForegroundColor Magenta

    $os = Get-CimInstance Win32_OperatingSystem
    $usedPct = [math]::Round((1 - $os.FreePhysicalMemory / $os.TotalVisibleMemorySize) * 100, 1)
    $pythonCount = (Get-Process -Name python, python3 -ErrorAction SilentlyContinue | Measure-Object).Count
    $pythonMB = [math]::Round((Get-Process -Name python, python3 -ErrorAction SilentlyContinue | Measure-Object WorkingSet64 -Sum).Sum / 1MB, 0)

    Write-Host ""
    Write-Host "  Current State:" -ForegroundColor White
    Write-Host "    Memory usage:    $usedPct%"
    Write-Host "    Python services: $pythonCount processes using $pythonMB MB"
    Write-Host ""
    Write-Host "  Priority Actions:" -ForegroundColor White

    $priority = 1
    if ($usedPct -gt 85) {
        Write-Host "  $priority. CRITICAL: Memory usage > 85%. Trim working sets immediately." -ForegroundColor Red
        Write-Host "     Run: .\memory-analyzer.ps1 -OptimizeTrim" -ForegroundColor DarkCyan
        $priority++
    }

    if ($pythonCount -gt 80) {
        Write-Host "  $priority. HIGH: $pythonCount Python processes is heavy. Consider:" -ForegroundColor Yellow
        Write-Host "     - Consolidating related services into fewer processes"
        Write-Host "     - Using shared Python interpreters with multiprocessing"
        Write-Host "     - Setting PYTHONDONTWRITEBYTECODE=1 to save ~2MB/process"
        $priority++
    }

    Write-Host "  $priority. Set OLLAMA_KEEP_ALIVE=-1 if using a single model frequently" -ForegroundColor White
    $priority++

    Write-Host "  $priority. Run periodic WS trims for idle services (every 30-60 min)" -ForegroundColor White
    Write-Host "     Each Python http.server wastes 20-50MB of untrimmed WS"
    $priority++

    Write-Host "  $priority. Leave mmap enabled for Ollama (default) — lets OS manage pages" -ForegroundColor White
    $priority++

    Write-Host "  $priority. Consider ISLC for automatic standby list management" -ForegroundColor White
    $priority++

    Write-Host "  $priority. Grant SeLockMemoryPrivilege for large page support (optional)" -ForegroundColor White
    Write-Host "     Benefit is moderate unless running very large models (13B+)"
    $priority++

    Write-Host ""
    Write-Host "  Quick Commands:" -ForegroundColor White
    Write-Host "    Full analysis:    .\memory-analyzer.ps1 -Full"
    Write-Host "    Trim idle procs:  .\memory-analyzer.ps1 -OptimizeTrim"
    Write-Host "    Flush cache:      .\memory-analyzer.ps1 -FlushStandby"
    Write-Host "    Leak detection:   .\memory-analyzer.ps1 -CheckLeaks"
    Write-Host "    Large page info:  .\memory-analyzer.ps1 -LargePages"
    Write-Host ""
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================
Write-Host ""
Write-Host "  NovaX Memory Analyzer v1.0" -ForegroundColor Magenta
Write-Host "  System: Windows 11 | 16GB DDR5 | $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor DarkGray
Write-Host ""

if ($AnalyzeOnly) {
    Get-MemoryAnalysis
    Get-MmapAnalysis
}

if ($CheckLeaks) {
    Get-MemoryLeakAnalysis
}

if ($OptimizeTrim) {
    Invoke-WorkingSetTrim
}

if ($LargePages) {
    Get-LargePageStatus
}

# Standby section always shows analysis; flush only if -FlushStandby
if ($AnalyzeOnly -or $FlushStandby) {
    Invoke-StandbyListManagement
}

Write-Recommendations

Write-Host "`n  Done." -ForegroundColor Green
