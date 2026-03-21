#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Disable non-essential Windows 11 scheduled tasks for performance.
.DESCRIPTION
    Analyzes and disables telemetry, diagnostic, and bloat scheduled tasks.
    Logs every action with task description and estimated impact.
    Safe tasks (Defrag/TRIM, Windows Update, CryptSvc, TaskScheduler) are preserved.
.NOTES
    Run as Administrator. Creates a log and a restore script.
    Date: 2026-03-15
#>

$LogFile = "C:\NovaX\tools\disabled-tasks-log_$(Get-Date -Format 'yyyyMMdd_HHmmss').txt"
$RestoreScript = "C:\NovaX\tools\restore-tasks_$(Get-Date -Format 'yyyyMMdd_HHmmss').ps1"

# --- Task definitions: Name, Path, Description, Impact ---
$TasksToDisable = @(
    # === Application Experience ===
    @{
        Name        = "Microsoft Compatibility Appraiser"
        Path        = "\Microsoft\Windows\Application Experience\"
        Description = "Collects program telemetry for Microsoft Compatibility program. Runs deep system scans."
        Impact      = "HIGH - CPU spikes 10-30min, heavy disk I/O, runs daily"
    },
    @{
        Name        = "ProgramDataUpdater"
        Path        = "\Microsoft\Windows\Application Experience\"
        Description = "Collects program telemetry if opted-in to the CEIP."
        Impact      = "MEDIUM - periodic CPU/disk usage for telemetry collection"
    },
    @{
        Name        = "StartupAppTask"
        Path        = "\Microsoft\Windows\Application Experience\"
        Description = "Scans startup entries for compatibility data."
        Impact      = "LOW-MEDIUM - runs at boot, adds to startup delay"
    },

    # === Customer Experience Improvement Program ===
    @{
        Name        = "Consolidator"
        Path        = "\Microsoft\Windows\Customer Experience Improvement Program\"
        Description = "Consolidates and uploads CEIP data to Microsoft."
        Impact      = "MEDIUM - network + disk I/O for telemetry upload"
    },
    @{
        Name        = "UsbCeip"
        Path        = "\Microsoft\Windows\Customer Experience Improvement Program\"
        Description = "Collects USB device usage telemetry for CEIP."
        Impact      = "LOW - periodic background data collection"
    },
    @{
        Name        = "KernelCeipTask"
        Path        = "\Microsoft\Windows\Customer Experience Improvement Program\"
        Description = "Collects kernel-level telemetry data for CEIP."
        Impact      = "MEDIUM - kernel-level data collection, can cause micro-stutters"
    },

    # === Diagnosis ===
    @{
        Name        = "Scheduled"
        Path        = "\Microsoft\Windows\DiskDiagnostic\"
        Description = "Runs Windows Disk Diagnostic scheduled data collection."
        Impact      = "MEDIUM - disk scanning and telemetry reporting"
    },

    # === Maps ===
    @{
        Name        = "MapsUpdateTask"
        Path        = "\Microsoft\Windows\Maps\"
        Description = "Downloads and updates offline map data."
        Impact      = "MEDIUM - large downloads, disk writes, network bandwidth"
    },
    @{
        Name        = "MapsToastTask"
        Path        = "\Microsoft\Windows\Maps\"
        Description = "Shows notifications to update offline maps."
        Impact      = "LOW - toast notification spam"
    },

    # === Mobile Broadband ===
    @{
        Name        = "MNO Metadata Parser"
        Path        = "\Microsoft\Windows\Mobile Broadband Accounts\"
        Description = "Parses mobile network operator metadata. Useless on desktops."
        Impact      = "LOW - unnecessary background parsing on non-mobile devices"
    },

    # === Maintenance ===
    @{
        Name        = "WinSAT"
        Path        = "\Microsoft\Windows\Maintenance\"
        Description = "Windows System Assessment Tool - benchmarks system hardware."
        Impact      = "HIGH - runs full CPU/disk/memory benchmarks, causes major slowdowns"
    },

    # === Power Efficiency ===
    @{
        Name        = "AnalyzeSystem"
        Path        = "\Microsoft\Windows\Power Efficiency Diagnostics\"
        Description = "Analyzes system for power efficiency problems."
        Impact      = "MEDIUM - runs diagnostic scans that consume CPU and disk"
    },

    # === Windows Error Reporting ===
    @{
        Name        = "QueueReporting"
        Path        = "\Microsoft\Windows\Windows Error Reporting\"
        Description = "Queues and uploads Windows error reports to Microsoft."
        Impact      = "LOW-MEDIUM - network uploads, disk reads of crash dumps"
    },

    # === Cloud Experience Host ===
    @{
        Name        = "CreateObjectTask"
        Path        = "\Microsoft\Windows\CloudExperienceHost\"
        Description = "Cloud Experience Host object creation for Microsoft account sync."
        Impact      = "LOW - background cloud sync operations"
    },

    # === Flighting (Windows Insider / Feature Config) ===
    @{
        Name        = "ReconcileFeatures"
        Path        = "\Microsoft\Windows\Flighting\FeatureConfig\"
        Description = "Reconciles feature configuration for Windows Insider/flighting."
        Impact      = "LOW-MEDIUM - background feature flag evaluation"
    },
    @{
        Name        = "UsageDataFlushing"
        Path        = "\Microsoft\Windows\Flighting\FeatureConfig\"
        Description = "Flushes feature usage data for flighting telemetry."
        Impact      = "LOW - periodic telemetry flush"
    },
    @{
        Name        = "UsageDataReporting"
        Path        = "\Microsoft\Windows\Flighting\FeatureConfig\"
        Description = "Reports feature usage data for flighting telemetry."
        Impact      = "LOW - periodic telemetry upload"
    },
    @{
        Name        = "OneSettings"
        Path        = "\Microsoft\Windows\Flighting\OneSettings\"
        Description = "Downloads OneSettings configuration from Microsoft."
        Impact      = "LOW - background config download"
    },

    # === Speech ===
    @{
        Name        = "SpeechModelDownloadTask"
        Path        = "\Microsoft\Windows\Speech\"
        Description = "Downloads updated speech recognition models."
        Impact      = "MEDIUM - large downloads consuming bandwidth and disk"
    },

    # === Additional bloat tasks commonly found on Win11 ===
    @{
        Name        = "Proxy"
        Path        = "\Microsoft\Windows\Autochk\"
        Description = "Autochk proxy task - collects and uploads autochk data."
        Impact      = "LOW - telemetry collection"
    },
    @{
        Name        = "BgTaskRegistrationMaintenanceTask"
        Path        = "\Microsoft\Windows\BrokerInfrastructure\"
        Description = "Background task registration maintenance."
        Impact      = "LOW - periodic background maintenance"
    },
    @{
        Name        = "XblGameSaveTask"
        Path        = "\Microsoft\XblGameSave\"
        Description = "Xbox Live game save sync. Useless if you don't use Xbox."
        Impact      = "LOW - background Xbox cloud sync"
    },
    @{
        Name        = "XblGameSaveTaskLogon"
        Path        = "\Microsoft\XblGameSave\"
        Description = "Xbox Live game save sync at logon."
        Impact      = "LOW - logon delay for Xbox sync"
    },
    @{
        Name        = "Sqm-Tasks"
        Path        = "\Microsoft\Windows\PI\"
        Description = "Software Quality Metrics data collection."
        Impact      = "LOW-MEDIUM - telemetry collection and upload"
    },
    @{
        Name        = "DmClient"
        Path        = "\Microsoft\Windows\Feedback\Siuf\"
        Description = "Device management client feedback task."
        Impact      = "LOW - feedback/telemetry collection"
    },
    @{
        Name        = "DmClientOnScenarioDownload"
        Path        = "\Microsoft\Windows\Feedback\Siuf\"
        Description = "Downloads feedback scenarios from Microsoft."
        Impact      = "LOW - background download"
    }
)

# === Safe tasks that must NOT be disabled ===
$SafeTasks = @(
    "ScheduledDefrag",       # SSD TRIM - critical for SSD health
    "SilentCleanup",         # Disk cleanup
    "CryptSvc",              # Cryptographic services
    "TaskScheduler",         # Task scheduler self-maintenance
    "SynchronizeTime",       # Time sync
    "SystemSoundsService",   # Audio
    "Plug and Play Cleanup", # Device management
    "RegIdleBackup"          # Registry backup
    # Windows Update tasks are in \Microsoft\Windows\WindowsUpdate\ - left alone entirely
)

# ============================================================
# PHASE 1: Pre-scan - show current state of all Ready tasks
# ============================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  WINDOWS 11 TASK OPTIMIZER - NovaX" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "[PHASE 1] Scanning all Ready scheduled tasks...`n" -ForegroundColor Yellow

$AllReady = Get-ScheduledTask | Where-Object { $_.State -eq 'Ready' } |
    Select-Object TaskName, TaskPath, State, @{
        Name = 'NextRun'
        Expression = {
            try {
                (Get-ScheduledTaskInfo -TaskName $_.TaskName -TaskPath $_.TaskPath -ErrorAction SilentlyContinue).NextRunTime
            } catch { "N/A" }
        }
    }

Write-Host "Total Ready tasks found: $($AllReady.Count)`n" -ForegroundColor White
$AllReady | Format-Table -AutoSize | Out-String | Write-Host

# ============================================================
# PHASE 2: Disable non-essential tasks
# ============================================================
Write-Host "`n[PHASE 2] Disabling non-essential tasks...`n" -ForegroundColor Yellow

$LogEntries = @()
$RestoreCommands = @()
$DisabledCount = 0
$SkippedCount = 0
$NotFoundCount = 0

# Add header to restore script
$RestoreCommands += "#Requires -RunAsAdministrator"
$RestoreCommands += "# Restore script - re-enables tasks disabled by NovaX optimizer"
$RestoreCommands += "# Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
$RestoreCommands += ""

foreach ($task in $TasksToDisable) {
    $taskName = $task.Name
    $taskPath = $task.Path

    # Safety check - skip if in safe list
    if ($SafeTasks -contains $taskName) {
        Write-Host "  [SAFE] $taskName - Protected task, skipping" -ForegroundColor Green
        $SkippedCount++
        continue
    }

    # Check if task exists
    $existing = $null
    try {
        $existing = Get-ScheduledTask -TaskName $taskName -TaskPath $taskPath -ErrorAction SilentlyContinue
    } catch {}

    # If not found at exact path, try by name only
    if (-not $existing) {
        try {
            $existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        } catch {}
    }

    if (-not $existing) {
        Write-Host "  [SKIP] $taskName - Not found on this system" -ForegroundColor DarkGray
        $NotFoundCount++
        $LogEntries += "NOT FOUND | $taskName | $taskPath | $($task.Description)"
        continue
    }

    # Check if already disabled
    if ($existing.State -eq 'Disabled') {
        Write-Host "  [DONE] $taskName - Already disabled" -ForegroundColor DarkYellow
        $SkippedCount++
        $LogEntries += "ALREADY DISABLED | $taskName | $($existing.TaskPath) | $($task.Description)"
        continue
    }

    # Disable the task
    try {
        $existing | Disable-ScheduledTask -ErrorAction Stop | Out-Null
        Write-Host "  [OFF]  $taskName - DISABLED ($($task.Impact))" -ForegroundColor Red
        $DisabledCount++

        $LogEntries += "DISABLED | $taskName | $($existing.TaskPath) | $($task.Description) | Impact: $($task.Impact)"
        $RestoreCommands += "Enable-ScheduledTask -TaskName '$taskName' -TaskPath '$($existing.TaskPath)' -ErrorAction SilentlyContinue"
    } catch {
        Write-Host "  [ERR]  $taskName - Failed: $($_.Exception.Message)" -ForegroundColor Magenta
        $LogEntries += "FAILED | $taskName | $($existing.TaskPath) | Error: $($_.Exception.Message)"
    }
}

# ============================================================
# PHASE 3: Write log and restore script
# ============================================================
Write-Host "`n[PHASE 3] Writing logs...`n" -ForegroundColor Yellow

# Write detailed log
$LogHeader = @"
================================================================
NovaX Windows 11 Task Optimizer - Execution Log
Date: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
Computer: $env:COMPUTERNAME
User: $env:USERNAME
================================================================

SUMMARY:
  Tasks disabled:    $DisabledCount
  Tasks skipped:     $SkippedCount
  Tasks not found:   $NotFoundCount
  Total processed:   $($TasksToDisable.Count)

PROTECTED TASKS (not touched):
  $($SafeTasks -join "`n  ")

================================================================
DETAILED LOG:
================================================================

"@

$LogContent = $LogHeader + ($LogEntries -join "`n")
$LogContent | Out-File -FilePath $LogFile -Encoding UTF8

# Write restore script
$RestoreCommands -join "`n" | Out-File -FilePath $RestoreScript -Encoding UTF8

Write-Host "  Log file:     $LogFile" -ForegroundColor White
Write-Host "  Restore file: $RestoreScript" -ForegroundColor White

# ============================================================
# PHASE 4: Summary
# ============================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  RESULTS" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Disabled:   $DisabledCount tasks" -ForegroundColor Red
Write-Host "  Skipped:    $SkippedCount tasks" -ForegroundColor Yellow
Write-Host "  Not found:  $NotFoundCount tasks" -ForegroundColor DarkGray
Write-Host "  Protected:  $($SafeTasks.Count) tasks (untouched)" -ForegroundColor Green
Write-Host "========================================`n" -ForegroundColor Cyan

# ============================================================
# PHASE 5: Show remaining Ready tasks
# ============================================================
Write-Host "[PHASE 5] Remaining Ready tasks after optimization:`n" -ForegroundColor Yellow

$Remaining = Get-ScheduledTask | Where-Object { $_.State -eq 'Ready' } |
    Select-Object TaskName, TaskPath, State
Write-Host "Remaining Ready tasks: $($Remaining.Count)`n" -ForegroundColor White
$Remaining | Format-Table -AutoSize | Out-String | Write-Host

Write-Host "Done. To undo all changes, run:" -ForegroundColor Green
Write-Host "  powershell -ExecutionPolicy Bypass -File `"$RestoreScript`"`n" -ForegroundColor White
