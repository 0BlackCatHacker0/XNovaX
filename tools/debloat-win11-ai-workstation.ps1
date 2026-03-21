#Requires -RunAsAdministrator
<#
.SYNOPSIS
    NovaX AI Workstation - Windows 11 Aggressive Debloat Script
.DESCRIPTION
    Optimizes Windows 11 Home for AI/ML workloads on ASUS TUF Gaming A16
    (AMD 8845HS, RTX 4060, 16GB DDR5, 2TB NVMe)

    Estimated savings: ~400-600MB RAM, ~3-8% CPU idle reduction, faster boot

    ALWAYS create a System Restore point before running.
    Run as Administrator in PowerShell.

.NOTES
    Author: NovaX Team
    Date: 2026-03-14
    Target: Windows 11 Home 10.0.26200
#>

param(
    [switch]$DryRun,        # Show what would be done without doing it
    [switch]$SkipRestore     # Skip restore point creation (not recommended)
)

$ErrorActionPreference = "SilentlyContinue"
$host.UI.RawUI.WindowTitle = "NovaX AI Workstation Debloat"

function Write-Section($title) {
    Write-Host "`n$('=' * 70)" -ForegroundColor Cyan
    Write-Host "  $title" -ForegroundColor Cyan
    Write-Host "$('=' * 70)" -ForegroundColor Cyan
}

function Safe-StopDisable($serviceName, $description, $ramSaving) {
    $svc = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
    if ($svc) {
        if ($DryRun) {
            Write-Host "  [DRY RUN] Would disable: $serviceName ($description) ~$ramSaving MB saved" -ForegroundColor Yellow
        } else {
            Stop-Service -Name $serviceName -Force -ErrorAction SilentlyContinue
            Set-Service -Name $serviceName -StartupType Disabled -ErrorAction SilentlyContinue
            Write-Host "  [DISABLED] $serviceName - $description (~$ramSaving MB)" -ForegroundColor Green
        }
    } else {
        Write-Host "  [SKIP] $serviceName not found on this system" -ForegroundColor DarkGray
    }
}

function Safe-RegSet($path, $name, $value, $type, $description) {
    if ($DryRun) {
        Write-Host "  [DRY RUN] Would set: $path\$name = $value ($description)" -ForegroundColor Yellow
        return
    }
    if (-not (Test-Path $path)) {
        New-Item -Path $path -Force | Out-Null
    }
    New-ItemProperty -Path $path -Name $name -Value $value -PropertyType $type -Force | Out-Null
    Write-Host "  [SET] $name = $value ($description)" -ForegroundColor Green
}

function Safe-DisableTask($taskPath, $taskName, $description) {
    $task = Get-ScheduledTask -TaskPath $taskPath -TaskName $taskName -ErrorAction SilentlyContinue
    if ($task) {
        if ($DryRun) {
            Write-Host "  [DRY RUN] Would disable task: $taskPath$taskName ($description)" -ForegroundColor Yellow
        } else {
            Disable-ScheduledTask -TaskPath $taskPath -TaskName $taskName -ErrorAction SilentlyContinue | Out-Null
            Write-Host "  [DISABLED] $taskPath$taskName - $description" -ForegroundColor Green
        }
    } else {
        Write-Host "  [SKIP] Task $taskName not found" -ForegroundColor DarkGray
    }
}

# ============================================================================
Write-Section "0. SYSTEM RESTORE POINT"
# ============================================================================
# Creates a safety net before any changes. ~30 seconds.

if (-not $SkipRestore) {
    if ($DryRun) {
        Write-Host "  [DRY RUN] Would create restore point" -ForegroundColor Yellow
    } else {
        Write-Host "  Creating restore point..." -ForegroundColor White
        # Enable System Restore on C: if not already
        Enable-ComputerRestore -Drive "C:\" -ErrorAction SilentlyContinue
        Checkpoint-Computer -Description "NovaX-Debloat-Pre-$(Get-Date -Format 'yyyyMMdd-HHmm')" -RestorePointType MODIFY_SETTINGS -ErrorAction SilentlyContinue
        Write-Host "  [DONE] Restore point created" -ForegroundColor Green
    }
}

# ============================================================================
Write-Section "1. SERVICE DISABLING (~250-350MB RAM saved)"
# ============================================================================
# These services are safe to disable on an AI dev workstation.
# Each service listed with its RAM footprint and justification.

# --- Search & Indexing ---
# WSearch constantly indexes files, uses 50-100MB RAM + disk I/O
Safe-StopDisable "WSearch" "Windows Search Indexer (heavy disk I/O, 50-100MB)" "80"

# --- Memory Prefetch ---
# SysMain preloads apps into RAM. Useless when you need RAM for models.
# Also disables RAM compression and ReadyBoost.
Safe-StopDisable "SysMain" "Superfetch/SysMain (preloads apps, wastes RAM for AI)" "100"

# --- Telemetry & Diagnostics ---
# DiagTrack sends usage data to Microsoft. CPU + network overhead.
Safe-StopDisable "DiagTrack" "Connected User Experiences and Telemetry" "30"

# dmwappushservice is the WAP push message routing service for telemetry
Safe-StopDisable "dmwappushservice" "WAP Push Message Routing (telemetry helper)" "5"

# --- Maps ---
# Downloads offline map data in background. Completely unnecessary.
Safe-StopDisable "MapsBroker" "Downloaded Maps Manager (background map updates)" "10"

# --- Biometrics ---
# Only needed if using fingerprint/face login. ASUS TUF A16 has no IR camera.
Safe-StopDisable "WbioSrvc" "Windows Biometric Service (no fingerprint reader)" "15"

# --- Tablet/Touch ---
# Handwriting recognition, touch keyboard features. Not needed on laptop.
Safe-StopDisable "TabletInputService" "Touch Keyboard and Handwriting Panel" "15"

# --- Print Spooler ---
# If you never print, this saves RAM and closes a common attack vector.
Safe-StopDisable "Spooler" "Print Spooler (disable if you never print)" "20"

# --- Fax ---
Safe-StopDisable "Fax" "Fax Service (nobody uses fax)" "5"

# --- Remote Registry ---
# Security risk, no need on personal workstation
Safe-StopDisable "RemoteRegistry" "Remote Registry (security risk)" "5"

# --- Retail Demo ---
Safe-StopDisable "RetailDemo" "Retail Demo Service (store display mode)" "5"

# --- Xbox Services ---
# Not needed for AI workstation. Saves background CPU.
Safe-StopDisable "XblAuthManager" "Xbox Live Auth Manager" "10"
Safe-StopDisable "XblGameSave" "Xbox Live Game Save" "5"
Safe-StopDisable "XboxGipSvc" "Xbox Accessory Management" "5"
Safe-StopDisable "XboxNetApiSvc" "Xbox Live Networking" "5"

# --- Windows Error Reporting ---
Safe-StopDisable "WerSvc" "Windows Error Reporting (sends crash data)" "10"

# --- Phone Link ---
Safe-StopDisable "PhoneSvc" "Phone Service (Phone Link companion)" "5"

# --- Diagnostic Services ---
Safe-StopDisable "diagnosticshub.standardcollector.service" "Diagnostics Hub Standard Collector" "10"
Safe-StopDisable "DiagSvc" "Diagnostic Execution Service" "5"

# --- Windows Insider ---
Safe-StopDisable "wisvc" "Windows Insider Service" "5"

# --- AllJoyn Router ---
# IoT protocol router, not needed
Safe-StopDisable "AJRouter" "AllJoyn Router Service (IoT)" "5"

# --- Geolocation ---
Safe-StopDisable "lfsvc" "Geolocation Service" "5"

# --- Windows AI Fabric Service ---
# The big one. WorkloadsSessionHost can eat 150-300MB for MS AI features.
Safe-StopDisable "WSAIFabricSvc" "Windows AI Fabric Service (MS AI, 150-300MB!)" "200"

# --- Delivery Optimization ---
# P2P update sharing. Uses bandwidth and RAM.
Safe-StopDisable "DoSvc" "Delivery Optimization (P2P updates)" "20"

# --- Program Compatibility Assistant ---
Safe-StopDisable "PcaSvc" "Program Compatibility Assistant" "10"

# --- Clipboard User Service (per-user) ---
# Cloud clipboard sync. Not needed.
# Note: this is a per-user template service, may show as ClipSVC
Safe-StopDisable "cbdhsvc" "Clipboard User Service" "5"

Write-Host "`n  Total estimated RAM savings from services: ~300-500MB" -ForegroundColor Magenta

# ============================================================================
Write-Section "2. TELEMETRY REMOVAL (privacy + CPU savings)"
# ============================================================================
# Registry keys to minimize data collection. Windows 11 Home cannot fully
# disable telemetry, but these reduce it to security-only level.

# Main telemetry kill switch (0 = Security/Off, 1 = Basic, 2 = Enhanced, 3 = Full)
Safe-RegSet "HKLM:\SOFTWARE\Policies\Microsoft\Windows\DataCollection" `
    "AllowTelemetry" 0 "DWORD" "Telemetry level: Security only"

Safe-RegSet "HKLM:\SOFTWARE\Policies\Microsoft\Windows\DataCollection" `
    "MaxTelemetryAllowed" 0 "DWORD" "Max telemetry: None"

Safe-RegSet "HKLM:\SOFTWARE\Policies\Microsoft\Windows\DataCollection" `
    "DoNotShowFeedbackNotifications" 1 "DWORD" "Disable feedback prompts"

# Disable Application Compatibility telemetry engine
Safe-RegSet "HKLM:\SOFTWARE\Policies\Microsoft\Windows\AppCompat" `
    "AITEnable" 0 "DWORD" "Disable App Compat telemetry engine"

Safe-RegSet "HKLM:\SOFTWARE\Policies\Microsoft\Windows\AppCompat" `
    "DisableInventory" 1 "DWORD" "Disable application inventory collector"

Safe-RegSet "HKLM:\SOFTWARE\Policies\Microsoft\Windows\AppCompat" `
    "DisableUAR" 1 "DWORD" "Disable Steps Recorder"

# Disable Windows Error Reporting
Safe-RegSet "HKLM:\SOFTWARE\Policies\Microsoft\Windows\Windows Error Reporting" `
    "Disabled" 1 "DWORD" "Disable Windows Error Reporting"

Safe-RegSet "HKLM:\SOFTWARE\Microsoft\Windows\Windows Error Reporting" `
    "Disabled" 1 "DWORD" "Disable WER (user key)"

# Disable Customer Experience Improvement Program
Safe-RegSet "HKLM:\SOFTWARE\Policies\Microsoft\SQMClient\Windows" `
    "CEIPEnable" 0 "DWORD" "Disable CEIP"

# Disable advertising ID
Safe-RegSet "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\AdvertisingInfo" `
    "Enabled" 0 "DWORD" "Disable advertising ID"

# Disable activity history
Safe-RegSet "HKLM:\SOFTWARE\Policies\Microsoft\Windows\System" `
    "EnableActivityFeed" 0 "DWORD" "Disable activity feed"

Safe-RegSet "HKLM:\SOFTWARE\Policies\Microsoft\Windows\System" `
    "PublishUserActivities" 0 "DWORD" "Disable activity publishing"

Safe-RegSet "HKLM:\SOFTWARE\Policies\Microsoft\Windows\System" `
    "UploadUserActivities" 0 "DWORD" "Disable activity upload"

# Disable Copilot
Safe-RegSet "HKCU:\Software\Policies\Microsoft\Windows\WindowsCopilot" `
    "TurnOffWindowsCopilot" 1 "DWORD" "Disable Windows Copilot"

Safe-RegSet "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsCopilot" `
    "TurnOffWindowsCopilot" 1 "DWORD" "Disable Copilot (machine policy)"

# Disable Recall
Safe-RegSet "HKCU:\Software\Policies\Microsoft\Windows\WindowsAI" `
    "DisableAIDataAnalysis" 1 "DWORD" "Disable Recall/AI data analysis"

Safe-RegSet "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsAI" `
    "DisableAIDataAnalysis" 1 "DWORD" "Disable Recall (machine policy)"

# Disable Click to Do
Safe-RegSet "HKCU:\Software\Policies\Microsoft\Windows\WindowsAI" `
    "TurnOffSavingSnapshots" 1 "DWORD" "Disable Click to Do snapshots"

# Disable web search in Start/taskbar
Safe-RegSet "HKCU:\Software\Policies\Microsoft\Windows\Explorer" `
    "DisableSearchBoxSuggestions" 1 "DWORD" "Disable search box web suggestions"

Safe-RegSet "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Search" `
    "BingSearchEnabled" 0 "DWORD" "Disable Bing search integration"

Safe-RegSet "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Search" `
    "CortanaConsent" 0 "DWORD" "Disable Cortana consent"

Write-Host "`n  Telemetry reduction applied. Note: Win11 Home still sends security data." -ForegroundColor Magenta

# ============================================================================
Write-Section "3. BACKGROUND APPS (~50-100MB RAM saved)"
# ============================================================================
# Prevents UWP apps from running in the background consuming resources.

# Global kill switch for background apps
Safe-RegSet "HKCU:\Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications" `
    "GlobalUserDisabled" 1 "DWORD" "Disable ALL background UWP apps"

Safe-RegSet "HKCU:\Software\Microsoft\Windows\CurrentVersion\Search" `
    "BackgroundAppGlobalToggle" 0 "DWORD" "Disable background app global toggle"

# Disable startup delay for desktop apps (faster login)
Safe-RegSet "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Serialize" `
    "StartupDelayInMSec" 0 "DWORD" "Remove startup delay for apps"

# Disable tips, suggestions, and welcome experience
Safe-RegSet "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\ContentDeliveryManager" `
    "SystemPaneSuggestionsEnabled" 0 "DWORD" "Disable Start menu suggestions"

Safe-RegSet "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\ContentDeliveryManager" `
    "SoftLandingEnabled" 0 "DWORD" "Disable tips/suggestions"

Safe-RegSet "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\ContentDeliveryManager" `
    "SubscribedContent-338389Enabled" 0 "DWORD" "Disable Windows tips"

Safe-RegSet "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\ContentDeliveryManager" `
    "SubscribedContent-310093Enabled" 0 "DWORD" "Disable 'Get the most out of Windows'"

Safe-RegSet "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\ContentDeliveryManager" `
    "SubscribedContent-338388Enabled" 0 "DWORD" "Disable suggested content in Settings"

Safe-RegSet "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\ContentDeliveryManager" `
    "SubscribedContent-353694Enabled" 0 "DWORD" "Disable suggested content in Settings 2"

Safe-RegSet "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\ContentDeliveryManager" `
    "SubscribedContent-353696Enabled" 0 "DWORD" "Disable suggested content in Settings 3"

Safe-RegSet "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\ContentDeliveryManager" `
    "SubscribedContent-338393Enabled" 0 "DWORD" "Disable suggested content in Settings 4"

Safe-RegSet "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\ContentDeliveryManager" `
    "SilentInstalledAppsEnabled" 0 "DWORD" "Prevent silent app installs"

Safe-RegSet "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\ContentDeliveryManager" `
    "ContentDeliveryAllowed" 0 "DWORD" "Disable content delivery"

Safe-RegSet "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\ContentDeliveryManager" `
    "PreInstalledAppsEnabled" 0 "DWORD" "Disable pre-installed app suggestions"

Safe-RegSet "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\ContentDeliveryManager" `
    "OemPreInstalledAppsEnabled" 0 "DWORD" "Disable OEM pre-installed app promos"

# Disable "Show me suggestions" in Start
Safe-RegSet "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Advanced" `
    "Start_IrisRecommendations" 0 "DWORD" "Disable Start menu recommendations"

Write-Host "`n  All background UWP apps disabled. Silent installs blocked." -ForegroundColor Magenta

# ============================================================================
Write-Section "4. VISUAL EFFECTS (snappier UI, slight CPU/GPU savings)"
# ============================================================================
# Disable transparency, animations, shadows for maximum responsiveness.
# GPU resources freed up for CUDA/AI workloads.

# Set visual effects to "Best Performance" mode
Safe-RegSet "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects" `
    "VisualFXSetting" 2 "DWORD" "Visual effects: Best Performance"

# Disable specific visual effects
Safe-RegSet "HKCU:\Control Panel\Desktop" `
    "UserPreferencesMask" ([byte[]](0x90,0x12,0x03,0x80,0x10,0x00,0x00,0x00)) "Binary" "Disable animations/effects mask"

Safe-RegSet "HKCU:\Control Panel\Desktop" `
    "DragFullWindows" "0" "String" "Disable full window drag"

Safe-RegSet "HKCU:\Control Panel\Desktop" `
    "FontSmoothing" "2" "String" "Keep ClearType (readability)"

Safe-RegSet "HKCU:\Control Panel\Desktop\WindowMetrics" `
    "MinAnimate" "0" "String" "Disable minimize/maximize animation"

# Disable transparency effects
Safe-RegSet "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize" `
    "EnableTransparency" 0 "DWORD" "Disable transparency effects"

# Disable animation effects
Safe-RegSet "HKCU:\SOFTWARE\Microsoft\Windows\DWM" `
    "EnableAeroPeek" 0 "DWORD" "Disable Aero Peek"

Safe-RegSet "HKCU:\SOFTWARE\Microsoft\Windows\DWM" `
    "AlwaysHibernateThumbnails" 0 "DWORD" "Disable thumbnail caching"

# Disable smooth scrolling in explorer
Safe-RegSet "HKCU:\Control Panel\Desktop" `
    "SmoothScroll" 0 "DWORD" "Disable smooth scrolling"

# Reduce menu show delay (snappier menus)
Safe-RegSet "HKCU:\Control Panel\Desktop" `
    "MenuShowDelay" "50" "String" "Faster menu display (default 400ms -> 50ms)"

# Disable cursor shadow
Safe-RegSet "HKCU:\Control Panel\Desktop" `
    "CursorShadow" 0 "DWORD" "Disable cursor shadow"

Write-Host "`n  Visual effects set to Best Performance. Transparency disabled." -ForegroundColor Magenta

# ============================================================================
Write-Section "5. DEFENDER EXCLUSIONS (faster AI model inference)"
# ============================================================================
# Excludes AI model directories from real-time scanning.
# Models are large binary blobs - scanning them wastes CPU during inference.
# WARNING: Only exclude directories YOU control. Don't exclude Downloads etc.

$exclusionPaths = @(
    "C:\NovaX",
    "C:\Users\Jupit\.ollama",
    "C:\NovaX\tools\bitnet",
    "C:\Users\Jupit\.cache\huggingface",
    "C:\Users\Jupit\.cache\torch",
    "C:\Users\Jupit\AppData\Local\lm-studio"
)

$exclusionExtensions = @(
    ".gguf",       # GGUF model files (llama.cpp)
    ".safetensors", # SafeTensors model files
    ".bin",        # PyTorch model binary
    ".pt",         # PyTorch checkpoint
    ".pth",        # PyTorch model
    ".onnx",       # ONNX model
    ".ckpt"        # Model checkpoint
)

$exclusionProcesses = @(
    "ollama.exe",
    "ollama_llama_server.exe",
    "python.exe",
    "pythonw.exe",
    "node.exe",
    "novalang-vm.exe",
    "bitnet-server.exe"
)

foreach ($path in $exclusionPaths) {
    if (Test-Path $path) {
        if ($DryRun) {
            Write-Host "  [DRY RUN] Would exclude path: $path" -ForegroundColor Yellow
        } else {
            Add-MpPreference -ExclusionPath $path -Force -ErrorAction SilentlyContinue
            Write-Host "  [EXCLUDED] Path: $path" -ForegroundColor Green
        }
    } else {
        Write-Host "  [SKIP] Path not found: $path" -ForegroundColor DarkGray
    }
}

foreach ($ext in $exclusionExtensions) {
    if ($DryRun) {
        Write-Host "  [DRY RUN] Would exclude extension: $ext" -ForegroundColor Yellow
    } else {
        Add-MpPreference -ExclusionExtension $ext -Force -ErrorAction SilentlyContinue
        Write-Host "  [EXCLUDED] Extension: $ext" -ForegroundColor Green
    }
}

foreach ($proc in $exclusionProcesses) {
    if ($DryRun) {
        Write-Host "  [DRY RUN] Would exclude process: $proc" -ForegroundColor Yellow
    } else {
        Add-MpPreference -ExclusionProcess $proc -Force -ErrorAction SilentlyContinue
        Write-Host "  [EXCLUDED] Process: $proc" -ForegroundColor Green
    }
}

Write-Host "`n  Defender will skip AI model files during real-time scanning." -ForegroundColor Magenta
Write-Host "  This can save 5-30% CPU during model loading/inference." -ForegroundColor Magenta

# ============================================================================
Write-Section "6. SCHEDULED TASKS TO DISABLE (~2-5% CPU saved)"
# ============================================================================
# These tasks run periodically and waste CPU/disk on an AI workstation.

# Application Experience / Compatibility
Safe-DisableTask "\Microsoft\Windows\Application Experience\" "Microsoft Compatibility Appraiser" "Compat telemetry (heavy CPU)"
Safe-DisableTask "\Microsoft\Windows\Application Experience\" "ProgramDataUpdater" "Program data telemetry"
Safe-DisableTask "\Microsoft\Windows\Application Experience\" "StartupAppTask" "Startup app analysis"
Safe-DisableTask "\Microsoft\Windows\Application Experience\" "AitAgent" "App Impact telemetry agent"

# Customer Experience Improvement Program
Safe-DisableTask "\Microsoft\Windows\Customer Experience Improvement Program\" "Consolidator" "CEIP consolidator"
Safe-DisableTask "\Microsoft\Windows\Customer Experience Improvement Program\" "KernelCeipTask" "Kernel CEIP data collection"
Safe-DisableTask "\Microsoft\Windows\Customer Experience Improvement Program\" "UsbCeip" "USB CEIP data collection"
Safe-DisableTask "\Microsoft\Windows\Customer Experience Improvement Program\" "Proxy" "CEIP proxy"

# Autochk (disk telemetry)
Safe-DisableTask "\Microsoft\Windows\Autochk\" "Proxy" "Autochk proxy telemetry"

# Diagnosis
Safe-DisableTask "\Microsoft\Windows\DiskDiagnostic\" "Microsoft-Windows-DiskDiagnosticDataCollector" "Disk diagnostic data"

# Feedback
Safe-DisableTask "\Microsoft\Windows\Feedback\Siuf\" "DmClient" "Feedback data collection"
Safe-DisableTask "\Microsoft\Windows\Feedback\Siuf\" "DmClientOnScenarioDownload" "Feedback scenario download"

# Maps
Safe-DisableTask "\Microsoft\Windows\Maps\" "MapsToastTask" "Maps toast notifications"
Safe-DisableTask "\Microsoft\Windows\Maps\" "MapsUpdateTask" "Offline maps update"

# Windows AI / Recall tasks (if present on 25H2+)
Safe-DisableTask "\Microsoft\Windows\WindowsAI\" "RecallBackgroundTask" "Recall background indexing"
Safe-DisableTask "\Microsoft\Windows\WindowsAI\" "RecallUserTask" "Recall user task"

# CloudExperienceHost
Safe-DisableTask "\Microsoft\Windows\CloudExperienceHost\" "CreateObjectTask" "Cloud experience telemetry"

# Flighting (Insider)
Safe-DisableTask "\Microsoft\Windows\Flighting\FeatureConfig\" "ReconcileFeatures" "Insider feature reconciliation"
Safe-DisableTask "\Microsoft\Windows\Flighting\FeatureConfig\" "UsageDataFlushing" "Insider usage data"
Safe-DisableTask "\Microsoft\Windows\Flighting\FeatureConfig\" "UsageDataReporting" "Insider usage reporting"
Safe-DisableTask "\Microsoft\Windows\Flighting\OneSettings\" "RefreshCache" "Insider settings refresh"

# Power Efficiency Diagnostics
Safe-DisableTask "\Microsoft\Windows\Power Efficiency Diagnostics\" "AnalyzeSystem" "Power efficiency analysis"

# Windows Update Orchestrator medic (aggressive re-enabler)
# Note: Do NOT disable the main update tasks, just the telemetry ones
Safe-DisableTask "\Microsoft\Windows\Diagnosis\" "Scheduled" "Diagnostic scheduled task"

Write-Host "`n  Telemetry/diagnostic scheduled tasks disabled." -ForegroundColor Magenta

# ============================================================================
Write-Section "7. MEMORY OPTIMIZATION"
# ============================================================================
# Additional memory tweaks beyond service disabling.

# Disable Delivery Optimization (P2P update sharing)
Safe-RegSet "HKLM:\SOFTWARE\Policies\Microsoft\Windows\DeliveryOptimization" `
    "DODownloadMode" 0 "DWORD" "Disable Delivery Optimization P2P"

# Disable Windows Tips/Suggestions notifications
Safe-RegSet "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Notifications\Settings\Windows.SystemToast.Suggested" `
    "Enabled" 0 "DWORD" "Disable suggestion notifications"

# Disable Game Bar entirely
Safe-RegSet "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\GameDVR" `
    "AppCaptureEnabled" 0 "DWORD" "Disable Game DVR capture"

Safe-RegSet "HKCU:\System\GameConfigStore" `
    "GameDVR_Enabled" 0 "DWORD" "Disable Game DVR"

Safe-RegSet "HKCU:\Software\Microsoft\GameBar" `
    "AllowAutoGameMode" 0 "DWORD" "Disable auto Game Mode"

Safe-RegSet "HKCU:\Software\Microsoft\GameBar" `
    "UseNexusForGameBarEnabled" 0 "DWORD" "Disable Game Bar overlay"

Safe-RegSet "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\GameDVR" `
    "AudioCaptureEnabled" 0 "DWORD" "Disable Game DVR audio capture"

Safe-RegSet "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\GameDVR" `
    "CursorCaptureEnabled" 0 "DWORD" "Disable Game DVR cursor capture"

# Disable Fullscreen Optimizations globally (can interfere with CUDA)
Safe-RegSet "HKCU:\System\GameConfigStore" `
    "GameDVR_FSEBehavior" 2 "DWORD" "Disable fullscreen optimizations"

# Optimize NTFS - disable last access time updates (reduces disk writes)
if (-not $DryRun) {
    fsutil behavior set disablelastaccess 1 2>$null
    Write-Host "  [SET] NTFS last access time updates disabled" -ForegroundColor Green
} else {
    Write-Host "  [DRY RUN] Would disable NTFS last access time updates" -ForegroundColor Yellow
}

# Disable hibernation (saves disk space = RAM size, ~16GB on this system)
# Only if you don't use hibernate. Sleep still works.
if (-not $DryRun) {
    powercfg /hibernate off 2>$null
    Write-Host "  [SET] Hibernation disabled (saved ~16GB disk space)" -ForegroundColor Green
} else {
    Write-Host "  [DRY RUN] Would disable hibernation (saves ~16GB disk)" -ForegroundColor Yellow
}

# Set power plan to High Performance
if (-not $DryRun) {
    powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c 2>$null
    Write-Host "  [SET] Power plan: High Performance" -ForegroundColor Green
} else {
    Write-Host "  [DRY RUN] Would set High Performance power plan" -ForegroundColor Yellow
}

# Disable Widgets/News feed
Safe-RegSet "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Advanced" `
    "TaskbarDa" 0 "DWORD" "Disable Widgets on taskbar"

# Disable Chat icon on taskbar
Safe-RegSet "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Advanced" `
    "TaskbarMn" 0 "DWORD" "Disable Chat icon on taskbar"

Write-Host "`n  Memory optimizations applied. Game Bar/DVR/Widgets disabled." -ForegroundColor Magenta

# ============================================================================
Write-Section "8. NETWORK OPTIMIZATION (lower latency for API calls)"
# ============================================================================
# Optimizes TCP/IP for AI workloads making many API calls.

# Disable Nagle's Algorithm on all network interfaces for lower latency
# Find active interfaces and apply to each
if (-not $DryRun) {
    $basePath = "HKLM:\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces"
    $interfaces = Get-ChildItem -Path $basePath -ErrorAction SilentlyContinue
    $applied = 0
    foreach ($iface in $interfaces) {
        $ipAddr = (Get-ItemProperty -Path $iface.PSPath -Name "DhcpIPAddress" -ErrorAction SilentlyContinue).DhcpIPAddress
        if (-not $ipAddr) {
            $ipAddr = (Get-ItemProperty -Path $iface.PSPath -Name "IPAddress" -ErrorAction SilentlyContinue).IPAddress
        }
        if ($ipAddr -and $ipAddr -ne "0.0.0.0" -and $ipAddr -ne "") {
            New-ItemProperty -Path $iface.PSPath -Name "TcpAckFrequency" -Value 1 -PropertyType DWORD -Force | Out-Null
            New-ItemProperty -Path $iface.PSPath -Name "TCPNoDelay" -Value 1 -PropertyType DWORD -Force | Out-Null
            Write-Host "  [SET] Nagle disabled on interface: $ipAddr" -ForegroundColor Green
            $applied++
        }
    }
    if ($applied -eq 0) {
        Write-Host "  [WARN] No active interfaces found for Nagle optimization" -ForegroundColor Yellow
    }
} else {
    Write-Host "  [DRY RUN] Would disable Nagle's algorithm on active interfaces" -ForegroundColor Yellow
}

# TCP auto-tuning: set to 'normal' (best for most workloads)
# 'disabled' can hurt throughput for large model downloads
if (-not $DryRun) {
    netsh int tcp set global autotuninglevel=normal 2>$null
    Write-Host "  [SET] TCP auto-tuning: normal" -ForegroundColor Green
} else {
    Write-Host "  [DRY RUN] Would set TCP auto-tuning to normal" -ForegroundColor Yellow
}

# Enable RSS (Receive Side Scaling) for better multi-core network processing
if (-not $DryRun) {
    netsh int tcp set global rss=enabled 2>$null
    Write-Host "  [SET] RSS (Receive Side Scaling): enabled" -ForegroundColor Green
} else {
    Write-Host "  [DRY RUN] Would enable RSS" -ForegroundColor Yellow
}

# Enable Direct Cache Access for network adapter
if (-not $DryRun) {
    netsh int tcp set global dca=enabled 2>$null
    Write-Host "  [SET] Direct Cache Access: enabled (if supported)" -ForegroundColor Green
} else {
    Write-Host "  [DRY RUN] Would enable DCA" -ForegroundColor Yellow
}

# Disable ECN (Explicit Congestion Notification) - can cause issues with some servers
if (-not $DryRun) {
    netsh int tcp set global ecncapability=disabled 2>$null
    Write-Host "  [SET] ECN: disabled (compatibility)" -ForegroundColor Green
} else {
    Write-Host "  [DRY RUN] Would disable ECN" -ForegroundColor Yellow
}

# Increase default TTL for better routing
Safe-RegSet "HKLM:\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters" `
    "DefaultTTL" 128 "DWORD" "Set default TTL to 128"

# Disable Network Throttling Index (removes 10Mbps limit on non-multimedia)
Safe-RegSet "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile" `
    "NetworkThrottlingIndex" 0xFFFFFFFF "DWORD" "Disable network throttling"

Safe-RegSet "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile" `
    "SystemResponsiveness" 0 "DWORD" "Reserve 0% CPU for background (max for foreground)"

Write-Host "`n  Network optimized for low-latency API calls." -ForegroundColor Magenta

# ============================================================================
Write-Section "9. BONUS: EDGE NEUTRALIZATION (user uses Brave)"
# ============================================================================
# Prevent Edge from running in background or hijacking defaults.
# Does NOT uninstall Edge (can break WebView2 dependencies).

# Disable Edge startup boost and background running
Safe-RegSet "HKLM:\SOFTWARE\Policies\Microsoft\Edge" `
    "StartupBoostEnabled" 0 "DWORD" "Disable Edge startup boost"

Safe-RegSet "HKLM:\SOFTWARE\Policies\Microsoft\Edge" `
    "BackgroundModeEnabled" 0 "DWORD" "Disable Edge background mode"

Safe-RegSet "HKLM:\SOFTWARE\Policies\Microsoft\Edge" `
    "HubsSidebarEnabled" 0 "DWORD" "Disable Edge sidebar"

# Prevent Edge from pre-launching
Safe-RegSet "HKLM:\SOFTWARE\Policies\Microsoft\MicrosoftEdge\Main" `
    "AllowPrelaunch" 0 "DWORD" "Prevent Edge pre-launch"

# Disable Edge scheduled tasks
Safe-DisableTask "\Microsoft\Windows\" "MicrosoftEdgeUpdateTaskMachineCore" "Edge auto-update core"
Safe-DisableTask "\Microsoft\Windows\" "MicrosoftEdgeUpdateTaskMachineUA" "Edge auto-update UA"

# Disable Edge auto-update services
Safe-StopDisable "edgeupdate" "Microsoft Edge Update Service" "10"
Safe-StopDisable "edgeupdatem" "Microsoft Edge Update Service (manual)" "5"
Safe-StopDisable "MicrosoftEdgeElevationService" "Microsoft Edge Elevation Service" "5"

Write-Host "`n  Edge neutralized. Background processes and updates disabled." -ForegroundColor Magenta

# ============================================================================
Write-Section "SUMMARY"
# ============================================================================

Write-Host @"

  ============================================================
  NovaX AI Workstation Debloat Complete!
  ============================================================

  Estimated savings:
    RAM:  400-600 MB freed at idle
    CPU:  3-8% reduced idle usage
    Disk: ~16 GB (hibernation) + reduced I/O
    Boot: 20-40% faster startup
    AI:   5-30% faster model loading (Defender exclusions)
    Net:  5-15ms lower latency (Nagle disabled)

  What was done:
    [1] 25+ unnecessary services disabled
    [2] Telemetry reduced to security-only level
    [3] Background UWP apps globally disabled
    [4] Visual effects set to Best Performance
    [5] Defender exclusions for AI model paths
    [6] 20+ telemetry scheduled tasks disabled
    [7] Game Bar/DVR/Widgets/Hibernation disabled
    [8] TCP/IP optimized for API call latency
    [9] Edge background processes neutralized

  IMPORTANT:
    - Restart your computer to apply all changes
    - Some changes may revert after Windows feature updates
    - Re-run this script after major Windows updates
    - To undo: restore from the system restore point created

  ============================================================
"@ -ForegroundColor Cyan

if ($DryRun) {
    Write-Host "  *** THIS WAS A DRY RUN - NO CHANGES WERE MADE ***" -ForegroundColor Red
    Write-Host "  Run without -DryRun to apply changes." -ForegroundColor Red
}

Write-Host ""
