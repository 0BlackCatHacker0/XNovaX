#Requires -RunAsAdministrator
<#
.SYNOPSIS
    NovaX Process Priority & Affinity Manager (Process Lasso-style)

.DESCRIPTION
    Automatically sets CPU priorities and core affinity for NovaX AI workloads.
    Demotes Windows bloat processes. Uses WMI events to catch new process starts.

    CPU: AMD Ryzen 9 8845HS — 8 cores / 16 threads, single NUMA node, Zen 4
    Strategy:
      - Cores 0-7  (physical) → Ollama inference (cache-hot, no SMT contention)
      - Cores 8-15 (SMT)      → Python NovaX services (I/O bound, SMT is fine)
      - Cores 0-15 (all)      → nova*.exe / bitnet*.exe (use everything)

.NOTES
    DO NOT register as a startup entry. User runs manually or via Task Scheduler
    with "Run only when user is logged on" (no persistent autostart).

    Run: powershell -ExecutionPolicy Bypass -File novax-process-priority.ps1
    Run once (no monitor): powershell -File novax-process-priority.ps1 -OneShot

    v1.0.0 — 2026-03-15
#>

param(
    [switch]$OneShot,       # Apply once and exit (no WMI monitor)
    [switch]$Verbose_,      # Extra logging (avoid collision with built-in -Verbose)
    [switch]$DryRun         # Show what would happen without changing anything
)

# ============================================================================
# CONFIGURATION
# ============================================================================

# Affinity masks for 16-thread system (cores 0-15)
# Core 0 = bit 0 (0x0001), Core 15 = bit 15 (0x8000)
$AFFINITY_PHYSICAL   = 0x00FF   # Cores 0-7   (physical cores)
$AFFINITY_SMT        = 0xFF00   # Cores 8-15  (SMT threads)
$AFFINITY_ALL        = 0xFFFF   # Cores 0-15  (all threads)

# High priority processes — NovaX AI workloads
$HighPriorityRules = @(
    @{ Pattern = "ollama";    Priority = "High";        Affinity = $AFFINITY_PHYSICAL; Description = "AI inference engine" }
    @{ Pattern = "python";    Priority = "AboveNormal"; Affinity = $AFFINITY_SMT;      Description = "NovaX Python services" }
    @{ Pattern = "pythonw";   Priority = "AboveNormal"; Affinity = $AFFINITY_SMT;      Description = "NovaX Python services (windowless)" }
    @{ Pattern = "bitnet";    Priority = "High";        Affinity = $AFFINITY_ALL;       Description = "Ternary inference engine" }
)

# Nova executables get wildcard matching separately
$NovaExePattern = "nova"  # matches nova*.exe

# Below Normal priority processes — Windows bloat
$LowPriorityProcesses = @(
    "msedge",
    "SearchApp",
    "ShellExperienceHost",
    "StartMenuExperienceHost",
    "RuntimeBroker",
    "TextInputHost",
    "WidgetService",
    "Widgets",
    "PhoneExperienceHost",
    "GameBarPresenceWriter"
)

# svchost instances to demote (by command line pattern)
$SvchostDemotePatterns = @(
    "DiagTrack",
    "WSearch",
    "SysMain",
    "Themes",
    "TabletInputService",
    "CDPUserSvc",
    "WpnUserService"
)

# Protected processes we must never touch
$ProtectedProcesses = @(
    "System", "smss", "csrss", "wininit", "services", "lsass",
    "winlogon", "dwm", "fontdrvhost", "Memory Compression"
)

# ============================================================================
# LOGGING
# ============================================================================

$LogFile = "C:\NovaX\logs\process-priority.log"
$LogDir = Split-Path $LogFile
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] [$Level] $Message"
    Add-Content -Path $LogFile -Value $line -ErrorAction SilentlyContinue
    switch ($Level) {
        "ERROR" { Write-Host $line -ForegroundColor Red }
        "WARN"  { Write-Host $line -ForegroundColor Yellow }
        "OK"    { Write-Host $line -ForegroundColor Green }
        default {
            if ($Verbose_ -or $Level -eq "INFO") { Write-Host $line -ForegroundColor Cyan }
        }
    }
}

# ============================================================================
# CORE FUNCTIONS
# ============================================================================

function Set-ProcessPriorityAndAffinity {
    param(
        [System.Diagnostics.Process]$Proc,
        [string]$DesiredPriority,
        [nullable[long]]$DesiredAffinity,
        [string]$Reason
    )

    $name = $Proc.ProcessName
    $pid_ = $Proc.Id

    # Skip protected
    if ($ProtectedProcesses -contains $name) { return }

    # Skip our own process
    if ($pid_ -eq $PID) { return }

    try {
        # Refresh to get current state
        $Proc.Refresh()
        if ($Proc.HasExited) { return }

        $changed = $false
        $changes = @()

        # Set priority
        $priorityMap = @{
            "Idle"        = [System.Diagnostics.ProcessPriorityClass]::Idle
            "BelowNormal" = [System.Diagnostics.ProcessPriorityClass]::BelowNormal
            "Normal"      = [System.Diagnostics.ProcessPriorityClass]::Normal
            "AboveNormal" = [System.Diagnostics.ProcessPriorityClass]::AboveNormal
            "High"        = [System.Diagnostics.ProcessPriorityClass]::High
        }

        $targetPriority = $priorityMap[$DesiredPriority]
        if ($null -ne $targetPriority -and $Proc.PriorityClass -ne $targetPriority) {
            if (-not $DryRun) {
                $Proc.PriorityClass = $targetPriority
            }
            $changes += "priority=$DesiredPriority"
            $changed = $true
        }

        # Set affinity
        if ($null -ne $DesiredAffinity -and $Proc.ProcessorAffinity -ne [IntPtr]$DesiredAffinity) {
            if (-not $DryRun) {
                $Proc.ProcessorAffinity = [IntPtr]$DesiredAffinity
            }
            $affinityHex = "0x{0:X4}" -f $DesiredAffinity
            $changes += "affinity=$affinityHex"
            $changed = $true
        }

        if ($changed) {
            $prefix = if ($DryRun) { "[DRY RUN] Would set" } else { "Set" }
            Write-Log "$prefix $name (PID $pid_): $($changes -join ', ') — $Reason" "OK"
        }
    }
    catch [System.ComponentModel.Win32Exception] {
        # Access denied — system process or protected
        if ($Verbose_) {
            Write-Log "Access denied: $name (PID $pid_) — skipping" "WARN"
        }
    }
    catch {
        if (-not $Proc.HasExited) {
            Write-Log "Error setting $name (PID $pid_): $($_.Exception.Message)" "ERROR"
        }
    }
}

function Test-ProcessMatchesPattern {
    param([string]$ProcessName, [string]$Pattern)
    return $ProcessName -like "$Pattern*"
}

function Apply-AllRules {
    <#
    .SYNOPSIS
        Scan all running processes and apply priority/affinity rules.
    #>

    Write-Log "=== Applying process priority rules ===" "INFO"
    $applied = 0
    $demoted = 0

    $allProcs = Get-Process -ErrorAction SilentlyContinue

    foreach ($proc in $allProcs) {
        $name = $proc.ProcessName
        $matched = $false

        # Check high-priority rules
        foreach ($rule in $HighPriorityRules) {
            if (Test-ProcessMatchesPattern $name $rule.Pattern) {
                Set-ProcessPriorityAndAffinity -Proc $proc `
                    -DesiredPriority $rule.Priority `
                    -DesiredAffinity $rule.Affinity `
                    -Reason $rule.Description
                $applied++
                $matched = $true
                break
            }
        }

        # Check nova*.exe wildcard
        if (-not $matched -and (Test-ProcessMatchesPattern $name $NovaExePattern)) {
            # Exclude known non-NovaX: "Notepad" etc won't match "nova*"
            Set-ProcessPriorityAndAffinity -Proc $proc `
                -DesiredPriority "AboveNormal" `
                -DesiredAffinity $AFFINITY_ALL `
                -Reason "NovaX executable"
            $applied++
            $matched = $true
        }

        if ($matched) { continue }

        # Check low-priority (demote) list
        if ($LowPriorityProcesses -contains $name) {
            Set-ProcessPriorityAndAffinity -Proc $proc `
                -DesiredPriority "BelowNormal" `
                -DesiredAffinity $null `
                -Reason "Windows bloat demoted"
            $demoted++
            continue
        }

        # Special handling for svchost — demote specific service hosts
        if ($name -eq "svchost") {
            try {
                $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($proc.Id)" -ErrorAction SilentlyContinue).CommandLine
                if ($null -ne $cmdLine) {
                    foreach ($pattern in $SvchostDemotePatterns) {
                        if ($cmdLine -match $pattern) {
                            Set-ProcessPriorityAndAffinity -Proc $proc `
                                -DesiredPriority "BelowNormal" `
                                -DesiredAffinity $null `
                                -Reason "svchost ($pattern) demoted"
                            $demoted++
                            break
                        }
                    }
                }
            }
            catch {
                # CIM query failed — skip this svchost
            }
        }
    }

    Write-Log "Applied rules: $applied boosted, $demoted demoted" "INFO"
}

function Apply-SingleProcess {
    <#
    .SYNOPSIS
        Apply rules to a single newly-started process by name.
    #>
    param([string]$ProcessName, [int]$ProcessId)

    try {
        $proc = Get-Process -Id $ProcessId -ErrorAction Stop
    }
    catch {
        return  # Process already gone
    }

    $name = $proc.ProcessName

    # High priority rules
    foreach ($rule in $HighPriorityRules) {
        if (Test-ProcessMatchesPattern $name $rule.Pattern) {
            Set-ProcessPriorityAndAffinity -Proc $proc `
                -DesiredPriority $rule.Priority `
                -DesiredAffinity $rule.Affinity `
                -Reason "$($rule.Description) (auto-detected)"
            return
        }
    }

    # Nova wildcard
    if (Test-ProcessMatchesPattern $name $NovaExePattern) {
        Set-ProcessPriorityAndAffinity -Proc $proc `
            -DesiredPriority "AboveNormal" `
            -DesiredAffinity $AFFINITY_ALL `
            -Reason "NovaX executable (auto-detected)"
        return
    }

    # Demote list
    if ($LowPriorityProcesses -contains $name) {
        Set-ProcessPriorityAndAffinity -Proc $proc `
            -DesiredPriority "BelowNormal" `
            -DesiredAffinity $null `
            -Reason "Windows bloat demoted (auto-detected)"
        return
    }
}

# ============================================================================
# WMI EVENT MONITOR (Process Lasso-style)
# ============================================================================

function Start-ProcessMonitor {
    <#
    .SYNOPSIS
        Register a WMI event subscription that fires on every new process start.
        This runs in the current PowerShell session (not as a permanent WMI subscription).
    #>

    Write-Log "Registering WMI process creation monitor..." "INFO"

    # Build the list of process names we care about
    $watchNames = @()
    foreach ($rule in $HighPriorityRules) {
        $watchNames += $rule.Pattern
    }
    $watchNames += $NovaExePattern
    $watchNames += $LowPriorityProcesses
    $watchNames += "svchost"

    # WMI query for new process creation events
    # InstanceCreationEvent polls every 2 seconds (good balance of responsiveness vs CPU)
    $wmiQuery = "SELECT * FROM __InstanceCreationEvent WITHIN 2 WHERE TargetInstance ISA 'Win32_Process'"

    # Clean up any existing subscription from a previous run
    Get-EventSubscriber -SourceIdentifier "NovaXProcessMonitor" -ErrorAction SilentlyContinue |
        Unregister-Event -ErrorAction SilentlyContinue

    # Register the event
    $job = Register-WmiEvent -Query $wmiQuery -SourceIdentifier "NovaXProcessMonitor" -Action {
        $newProc = $Event.SourceEventArgs.NewEvent.TargetInstance
        $procName = $newProc.Name -replace '\.exe$', ''
        $procId = [int]$newProc.ProcessId

        # Quick check: is this a process we care about?
        $dominated = $false

        # High priority patterns
        $patterns = @("ollama", "python", "pythonw", "bitnet", "nova")
        foreach ($p in $patterns) {
            if ($procName -like "$p*") { $dominated = $true; break }
        }

        # Low priority exact matches
        $lowNames = @("msedge", "SearchApp", "ShellExperienceHost",
                       "StartMenuExperienceHost", "RuntimeBroker",
                       "TextInputHost", "WidgetService", "Widgets",
                       "PhoneExperienceHost", "GameBarPresenceWriter", "svchost")
        if ($lowNames -contains $procName) { $dominated = $true }

        if ($dominated) {
            # Small delay to let process initialize
            Start-Sleep -Milliseconds 500

            # Invoke rule application (we're in a script block so we call the function directly)
            try {
                $p = Get-Process -Id $procId -ErrorAction Stop

                # Inline rule application (can't easily call outer functions from event scriptblock)
                $highRules = @(
                    @{ Pattern = "ollama";  Priority = "High";        AffinityVal = 0x00FF }
                    @{ Pattern = "python";  Priority = "AboveNormal"; AffinityVal = 0xFF00 }
                    @{ Pattern = "pythonw"; Priority = "AboveNormal"; AffinityVal = 0xFF00 }
                    @{ Pattern = "bitnet";  Priority = "High";        AffinityVal = 0xFFFF }
                )

                $applied = $false
                foreach ($rule in $highRules) {
                    if ($procName -like "$($rule.Pattern)*") {
                        $priorityMap = @{
                            "High"        = [System.Diagnostics.ProcessPriorityClass]::High
                            "AboveNormal" = [System.Diagnostics.ProcessPriorityClass]::AboveNormal
                        }
                        try {
                            $p.PriorityClass = $priorityMap[$rule.Priority]
                            $p.ProcessorAffinity = [IntPtr]$rule.AffinityVal
                            $ts = Get-Date -Format "HH:mm:ss"
                            Write-Host "[$ts] [AUTO] $procName (PID $procId) -> $($rule.Priority), affinity 0x$($rule.AffinityVal.ToString('X4'))" -ForegroundColor Green
                        } catch {}
                        $applied = $true
                        break
                    }
                }

                # Nova wildcard
                if (-not $applied -and $procName -like "nova*") {
                    try {
                        $p.PriorityClass = [System.Diagnostics.ProcessPriorityClass]::AboveNormal
                        $p.ProcessorAffinity = [IntPtr]0xFFFF
                        $ts = Get-Date -Format "HH:mm:ss"
                        Write-Host "[$ts] [AUTO] $procName (PID $procId) -> AboveNormal, affinity 0xFFFF" -ForegroundColor Green
                    } catch {}
                    $applied = $true
                }

                # Demote
                if (-not $applied -and $lowNames -contains $procName) {
                    try {
                        $p.PriorityClass = [System.Diagnostics.ProcessPriorityClass]::BelowNormal
                        $ts = Get-Date -Format "HH:mm:ss"
                        Write-Host "[$ts] [AUTO] $procName (PID $procId) -> BelowNormal (demoted)" -ForegroundColor Yellow
                    } catch {}
                }
            }
            catch {
                # Process gone already
            }
        }
    }

    Write-Log "WMI monitor active. Watching for new processes every 2 seconds." "OK"
    Write-Log "Press Ctrl+C to stop monitoring." "INFO"

    # Keep the script alive
    try {
        while ($true) {
            Start-Sleep -Seconds 30

            # Periodic re-scan every 30 seconds to catch anything WMI missed
            # (WMI event polling has a 2-second window, very fast processes can slip through)
            $quickProcs = @("ollama", "python", "bitnet")
            foreach ($qp in $quickProcs) {
                Get-Process -Name "$qp*" -ErrorAction SilentlyContinue | ForEach-Object {
                    $target = $_
                    foreach ($rule in $HighPriorityRules) {
                        if ($target.ProcessName -like "$($rule.Pattern)*") {
                            $priorityMap = @{
                                "High"        = [System.Diagnostics.ProcessPriorityClass]::High
                                "AboveNormal" = [System.Diagnostics.ProcessPriorityClass]::AboveNormal
                            }
                            try {
                                $currentPri = $target.PriorityClass
                                $wantedPri = $priorityMap[$rule.Priority]
                                if ($currentPri -ne $wantedPri) {
                                    $target.PriorityClass = $wantedPri
                                    $target.ProcessorAffinity = [IntPtr]$rule.Affinity
                                    $ts = Get-Date -Format "HH:mm:ss"
                                    Write-Host "[$ts] [RESCAN] $($target.ProcessName) (PID $($target.Id)) corrected" -ForegroundColor Magenta
                                }
                            } catch {}
                            break
                        }
                    }
                }
            }
        }
    }
    finally {
        Write-Log "Shutting down process monitor..." "WARN"
        Get-EventSubscriber -SourceIdentifier "NovaXProcessMonitor" -ErrorAction SilentlyContinue |
            Unregister-Event -ErrorAction SilentlyContinue
        Write-Log "Monitor stopped. Process priorities will revert on next process restart." "INFO"
    }
}

# ============================================================================
# NUMA / TOPOLOGY INFO
# ============================================================================

function Show-TopologyInfo {
    Write-Log "=== CPU Topology ===" "INFO"

    $cpu = Get-CimInstance Win32_Processor -ErrorAction SilentlyContinue
    if ($cpu) {
        Write-Log "CPU: $($cpu.Name)" "INFO"
        Write-Log "Cores: $($cpu.NumberOfCores) physical, $($cpu.NumberOfLogicalProcessors) logical" "INFO"
        Write-Log "L2 Cache: $($cpu.L2CacheSize) KB, L3 Cache: $($cpu.L3CacheSize) KB" "INFO"
    }

    # NUMA topology
    $numa = Get-CimInstance Win32_NumaNode -ErrorAction SilentlyContinue
    $numaCount = ($numa | Measure-Object).Count
    Write-Log "NUMA nodes: $numaCount (8845HS is single-node — all cores share L3)" "INFO"

    if ($numaCount -eq 1) {
        Write-Log "Strategy: Physical cores (0-7) for inference, SMT threads (8-15) for services" "INFO"
        Write-Log "Rationale: Inference is compute-bound (benefits from full core), services are I/O-bound (SMT is fine)" "INFO"
    }
    else {
        Write-Log "Multi-NUMA detected! Consider pinning inference to node 0 and services to node 1" "WARN"
    }

    Write-Host ""
}

# ============================================================================
# STATUS REPORT
# ============================================================================

function Show-CurrentStatus {
    Write-Host ""
    Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║           NovaX Process Priority Manager v1.0.0            ║" -ForegroundColor Cyan
    Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""

    # Show managed processes
    $header = "{0,-25} {1,-8} {2,-15} {3,-12}" -f "PROCESS", "PID", "PRIORITY", "AFFINITY"
    Write-Host $header -ForegroundColor White
    Write-Host ("-" * 65) -ForegroundColor DarkGray

    $allPatterns = @("ollama", "python", "pythonw", "bitnet", "nova")
    $seen = @{}

    foreach ($pattern in $allPatterns) {
        Get-Process -Name "$pattern*" -ErrorAction SilentlyContinue | ForEach-Object {
            if (-not $seen.ContainsKey($_.Id)) {
                $seen[$_.Id] = $true
                $affinityHex = try { "0x{0:X4}" -f [long]$_.ProcessorAffinity } catch { "N/A" }
                $line = "{0,-25} {1,-8} {2,-15} {3,-12}" -f $_.ProcessName, $_.Id, $_.PriorityClass, $affinityHex
                Write-Host $line -ForegroundColor Green
            }
        }
    }

    foreach ($name in $LowPriorityProcesses) {
        Get-Process -Name $name -ErrorAction SilentlyContinue | ForEach-Object {
            if (-not $seen.ContainsKey($_.Id)) {
                $seen[$_.Id] = $true
                $line = "{0,-25} {1,-8} {2,-15} {3,-12}" -f $_.ProcessName, $_.Id, $_.PriorityClass, "default"
                Write-Host $line -ForegroundColor Yellow
            }
        }
    }

    Write-Host ""
}

# ============================================================================
# MAIN
# ============================================================================

Write-Host ""
Write-Host "  NovaX Process Priority Manager" -ForegroundColor Cyan
Write-Host "  AMD Ryzen 9 8845HS — 8C/16T Zen 4" -ForegroundColor DarkCyan
if ($DryRun) { Write-Host "  *** DRY RUN MODE — no changes will be made ***" -ForegroundColor Yellow }
Write-Host ""

# Check admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Log "ERROR: This script requires Administrator privileges." "ERROR"
    Write-Log "Right-click PowerShell -> 'Run as Administrator', then run this script." "ERROR"
    exit 1
}

# Show topology
Show-TopologyInfo

# Apply rules to all running processes
Apply-AllRules

# Show status
Show-CurrentStatus

if ($OneShot) {
    Write-Log "OneShot mode — rules applied, exiting." "INFO"
    exit 0
}

# Start continuous monitoring
Start-ProcessMonitor
