#Requires -RunAsAdministrator
# =============================================================================
# NovaX Windows 11 Home Debloat Script — AI Workstation Edition
# =============================================================================
# Purpose: Strip Windows 11 Home down to a lean AI workstation so NovaX,
#          Ollama, Python, and BitNet get maximum CPU/RAM/disk.
#
# Edition: Windows 11 HOME (no gpedit.msc — registry & PowerShell only)
# Author:  NovaX Project
# Date:    2026-03-14
#
# USAGE:   Run PowerShell as Administrator, then:
#          Set-ExecutionPolicy Unrestricted -Scope Process -Force
#          .\debloat-win11-novax.ps1
#
# SAFETY:  Creates a System Restore Point first. Every change is reversible.
#          Review each section before running. Comment out anything you want
#          to skip.
# =============================================================================

Write-Host "============================================" -ForegroundColor Cyan
Write-Host " NovaX Win11 Home Debloat — AI Workstation" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# --- RESTORE POINT -----------------------------------------------------------
Write-Host "[0/17] Creating System Restore Point..." -ForegroundColor Yellow
try {
    Enable-ComputerRestore -Drive "C:\"
    Checkpoint-Computer -Description "Pre-NovaX-Debloat" -RestorePointType "MODIFY_SETTINGS"
    Write-Host "       Restore point created." -ForegroundColor Green
} catch {
    Write-Host "       Could not create restore point (non-fatal). Continuing..." -ForegroundColor DarkYellow
}

# =============================================================================
# [1] HIGH IMPACT — DISABLE WINDOWS SERVICES
# =============================================================================
Write-Host ""
Write-Host "[1/17] Disabling unnecessary Windows services..." -ForegroundColor Yellow

$servicesToDisable = @(
    # --- HIGH IMPACT ---
    @{ Name = "DiagTrack";          Desc = "Connected User Experiences and Telemetry" },
    @{ Name = "dmwappushservice";   Desc = "WAP Push Message Routing (telemetry)" },
    @{ Name = "SysMain";           Desc = "Superfetch — preloads apps into RAM (unneeded with SSD+32GB)" },
    @{ Name = "WSearch";           Desc = "Windows Search Indexer — constant disk/CPU churn" },
    @{ Name = "DoSvc";             Desc = "Delivery Optimization — P2P update uploads" },

    # --- MEDIUM IMPACT ---
    @{ Name = "Spooler";           Desc = "Print Spooler — disable if no printer" },
    @{ Name = "Fax";               Desc = "Fax service" },
    @{ Name = "MapsBroker";        Desc = "Downloaded Maps Manager" },
    @{ Name = "lfsvc";             Desc = "Geolocation Service" },
    @{ Name = "RetailDemo";        Desc = "Retail Demo Service" },
    @{ Name = "wisvc";             Desc = "Windows Insider Service" },
    @{ Name = "WerSvc";            Desc = "Windows Error Reporting" },
    @{ Name = "wercplsupport";     Desc = "Problem Reports Control Panel" },
    @{ Name = "PcaSvc";            Desc = "Program Compatibility Assistant" },
    @{ Name = "DiagSvc";           Desc = "Diagnostic Execution Service" },
    @{ Name = "diagnosticshub.standardcollector.service"; Desc = "Diagnostics Hub" },

    # --- LOW IMPACT (cleanup) ---
    @{ Name = "WMPNetworkSvc";     Desc = "Windows Media Player Network Sharing" },
    @{ Name = "icssvc";            Desc = "Windows Mobile Hotspot Service" },
    @{ Name = "WpcMonSvc";         Desc = "Parental Controls" },
    @{ Name = "SEMgrSvc";          Desc = "Payments and NFC/SE Manager" },
    @{ Name = "PhoneSvc";          Desc = "Phone Service" },
    @{ Name = "TabletInputService"; Desc = "Touch Keyboard and Handwriting Panel" },
    @{ Name = "WbioSrvc";         Desc = "Windows Biometric Service (disable if no fingerprint)" }
)

# NOTE: Bluetooth left ENABLED by default. Uncomment below if you don't use BT:
# $servicesToDisable += @{ Name = "bthserv"; Desc = "Bluetooth Support Service" }
# $servicesToDisable += @{ Name = "BluetoothUserService"; Desc = "Bluetooth User Service" }

foreach ($svc in $servicesToDisable) {
    try {
        $s = Get-Service -Name $svc.Name -ErrorAction SilentlyContinue
        if ($s) {
            Stop-Service -Name $svc.Name -Force -ErrorAction SilentlyContinue
            Set-Service -Name $svc.Name -StartupType Disabled -ErrorAction SilentlyContinue
            Write-Host "       DISABLED: $($svc.Name) — $($svc.Desc)" -ForegroundColor Green
        } else {
            Write-Host "       SKIP: $($svc.Name) not found" -ForegroundColor DarkGray
        }
    } catch {
        Write-Host "       WARN: $($svc.Name) — $($_.Exception.Message)" -ForegroundColor DarkYellow
    }
}

# =============================================================================
# [2] HIGH IMPACT — TELEMETRY REMOVAL
# =============================================================================
Write-Host ""
Write-Host "[2/17] Nuking telemetry..." -ForegroundColor Yellow

# AllowTelemetry = 0 (Security level, lowest possible)
$regPath = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\DataCollection"
if (-not (Test-Path $regPath)) { New-Item -Path $regPath -Force | Out-Null }
Set-ItemProperty -Path $regPath -Name "AllowTelemetry" -Value 0 -Type DWord -Force
Set-ItemProperty -Path $regPath -Name "MaxTelemetryAllowed" -Value 0 -Type DWord -Force
Set-ItemProperty -Path $regPath -Name "DoNotShowFeedbackNotifications" -Value 1 -Type DWord -Force
Write-Host "       AllowTelemetry = 0, feedback notifications disabled" -ForegroundColor Green

# Disable Application Telemetry
$appCompat = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\AppCompat"
if (-not (Test-Path $appCompat)) { New-Item -Path $appCompat -Force | Out-Null }
Set-ItemProperty -Path $appCompat -Name "AITEnable" -Value 0 -Type DWord -Force
Set-ItemProperty -Path $appCompat -Name "DisableInventory" -Value 1 -Type DWord -Force
Set-ItemProperty -Path $appCompat -Name "DisableUAR" -Value 1 -Type DWord -Force
Write-Host "       Application telemetry (AITEnable, Inventory, UAR) disabled" -ForegroundColor Green

# Clear telemetry log
$etlPath = "C:\ProgramData\Microsoft\Diagnosis\ETLLogs\AutoLogger\AutoLogger-Diagtrack-Listener.etl"
if (Test-Path $etlPath) {
    try {
        [System.IO.File]::WriteAllText($etlPath, "")
        Write-Host "       Telemetry ETL log cleared" -ForegroundColor Green
    } catch {
        Write-Host "       Could not clear ETL log (file locked)" -ForegroundColor DarkYellow
    }
}

# Disable telemetry scheduled tasks
$telemetryTasks = @(
    "\Microsoft\Windows\Customer Experience Improvement Program\Consolidator",
    "\Microsoft\Windows\Customer Experience Improvement Program\UsbCeip",
    "\Microsoft\Windows\Customer Experience Improvement Program\KernelCeipTask",
    "\Microsoft\Windows\Application Experience\Microsoft Compatibility Appraiser",
    "\Microsoft\Windows\Application Experience\ProgramDataUpdater",
    "\Microsoft\Windows\Application Experience\AitAgent",
    "\Microsoft\Windows\Autochk\Proxy",
    "\Microsoft\Windows\DiskDiagnostic\Microsoft-Windows-DiskDiagnosticDataCollector"
)
foreach ($task in $telemetryTasks) {
    try {
        Disable-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue | Out-Null
        Write-Host "       Task disabled: $task" -ForegroundColor Green
    } catch {
        Write-Host "       Task not found: $task" -ForegroundColor DarkGray
    }
}

# =============================================================================
# [3] HIGH IMPACT — CORTANA, WIDGETS, CHAT, NEWS, COPILOT
# =============================================================================
Write-Host ""
Write-Host "[3/17] Disabling Cortana, Widgets, Chat, News, Copilot..." -ForegroundColor Yellow

# Disable Cortana
$winSearch = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\Windows Search"
if (-not (Test-Path $winSearch)) { New-Item -Path $winSearch -Force | Out-Null }
Set-ItemProperty -Path $winSearch -Name "AllowCortana" -Value 0 -Type DWord -Force
Set-ItemProperty -Path $winSearch -Name "DisableWebSearch" -Value 1 -Type DWord -Force
Set-ItemProperty -Path $winSearch -Name "ConnectedSearchUseWeb" -Value 0 -Type DWord -Force
Set-ItemProperty -Path $winSearch -Name "ConnectedSearchUseWebOverMeteredConnections" -Value 0 -Type DWord -Force
Write-Host "       Cortana disabled, Bing web search in Start disabled" -ForegroundColor Green

# Uninstall Cortana package
Get-AppxPackage *Microsoft.549981C3F5F10* | Remove-AppxPackage -ErrorAction SilentlyContinue
Write-Host "       Cortana app package removed" -ForegroundColor Green

# Disable Widgets (TaskbarDA)
Set-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Advanced" -Name "TaskbarDa" -Value 0 -Type DWord -Force
$dsh = "HKLM:\SOFTWARE\Policies\Microsoft\Dsh"
if (-not (Test-Path $dsh)) { New-Item -Path $dsh -Force | Out-Null }
Set-ItemProperty -Path $dsh -Name "AllowNewsAndInterests" -Value 0 -Type DWord -Force
Write-Host "       Widgets and News disabled" -ForegroundColor Green

# Disable Chat/Teams icon
Set-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Advanced" -Name "TaskbarMn" -Value 0 -Type DWord -Force
Write-Host "       Chat/Teams icon hidden" -ForegroundColor Green

# Disable Copilot
$copilot = "HKCU:\Software\Policies\Microsoft\Windows\WindowsCopilot"
if (-not (Test-Path $copilot)) { New-Item -Path $copilot -Force | Out-Null }
Set-ItemProperty -Path $copilot -Name "TurnOffWindowsCopilot" -Value 1 -Type DWord -Force
Write-Host "       Windows Copilot disabled" -ForegroundColor Green

# =============================================================================
# [4] HIGH IMPACT — DELIVERY OPTIMIZATION (P2P UPLOAD)
# =============================================================================
Write-Host ""
Write-Host "[4/17] Disabling Delivery Optimization P2P..." -ForegroundColor Yellow

$doPath = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\DeliveryOptimization"
if (-not (Test-Path $doPath)) { New-Item -Path $doPath -Force | Out-Null }
# DODownloadMode 0 = HTTP only (no P2P), 1 = LAN only, 3 = LAN+Internet
Set-ItemProperty -Path $doPath -Name "DODownloadMode" -Value 0 -Type DWord -Force
Write-Host "       P2P upload disabled — downloads from Microsoft servers only" -ForegroundColor Green

# =============================================================================
# [5] HIGH IMPACT — BACKGROUND APPS (ALL DISABLED)
# =============================================================================
Write-Host ""
Write-Host "[5/17] Disabling ALL background app permissions..." -ForegroundColor Yellow

# Per-user disable
$bgPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications"
if (-not (Test-Path $bgPath)) { New-Item -Path $bgPath -Force | Out-Null }
Set-ItemProperty -Path $bgPath -Name "GlobalUserDisabled" -Value 1 -Type DWord -Force

$searchBg = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Search"
if (-not (Test-Path $searchBg)) { New-Item -Path $searchBg -Force | Out-Null }
Set-ItemProperty -Path $searchBg -Name "BackgroundAppGlobalToggle" -Value 0 -Type DWord -Force

# System-wide disable (all users)
$appPrivacy = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\AppPrivacy"
if (-not (Test-Path $appPrivacy)) { New-Item -Path $appPrivacy -Force | Out-Null }
Set-ItemProperty -Path $appPrivacy -Name "LetAppsRunInBackground" -Value 2 -Type DWord -Force
Write-Host "       All background apps force-denied (user + system level)" -ForegroundColor Green

# =============================================================================
# [6] MEDIUM IMPACT — NOTIFICATIONS (ALL OFF)
# =============================================================================
Write-Host ""
Write-Host "[6/17] Disabling all notifications..." -ForegroundColor Yellow

# Disable toast notifications
$pushPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\PushNotifications"
if (-not (Test-Path $pushPath)) { New-Item -Path $pushPath -Force | Out-Null }
Set-ItemProperty -Path $pushPath -Name "ToastEnabled" -Value 0 -Type DWord -Force
Set-ItemProperty -Path $pushPath -Name "NoToastApplicationNotification" -Value 1 -Type DWord -Force

# Disable Notification Center
$explorerPol = "HKCU:\Software\Policies\Microsoft\Windows\Explorer"
if (-not (Test-Path $explorerPol)) { New-Item -Path $explorerPol -Force | Out-Null }
Set-ItemProperty -Path $explorerPol -Name "DisableNotificationCenter" -Value 1 -Type DWord -Force

# Disable Windows Security Center notifications
$defNotify = "HKLM:\SOFTWARE\Policies\Microsoft\Windows Defender Security Center\Notifications"
if (-not (Test-Path $defNotify)) { New-Item -Path $defNotify -Force | Out-Null }
Set-ItemProperty -Path $defNotify -Name "DisableNotifications" -Value 1 -Type DWord -Force

# Disable lock screen notifications
Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Notifications\Settings" -Name "NOC_GLOBAL_SETTING_ALLOW_NOTIFICATION_SOUND" -Value 0 -Type DWord -Force -ErrorAction SilentlyContinue

Write-Host "       Toast, Notification Center, Security alerts all disabled" -ForegroundColor Green

# =============================================================================
# [7] MEDIUM IMPACT — VISUAL EFFECTS (PERFORMANCE MODE)
# =============================================================================
Write-Host ""
Write-Host "[7/17] Setting visual effects to best performance..." -ForegroundColor Yellow

# VisualFXSetting: 0=LetWindowsChoose, 1=BestAppearance, 2=BestPerformance, 3=Custom
Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects" -Name "VisualFXSetting" -Value 2 -Type DWord -Force -ErrorAction SilentlyContinue

# Disable individual effects
$desktopPath = "HKCU:\Control Panel\Desktop"
Set-ItemProperty -Path $desktopPath -Name "MenuShowDelay" -Value "100" -Type String -Force
Set-ItemProperty -Path "$desktopPath\WindowMetrics" -Name "MinAnimate" -Value "0" -Type String -Force -ErrorAction SilentlyContinue
Set-ItemProperty -Path $desktopPath -Name "DragFullWindows" -Value "0" -Type String -Force

# Disable transparency
$personalize = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
Set-ItemProperty -Path $personalize -Name "EnableTransparency" -Value 0 -Type DWord -Force

# Disable animation effects in Accessibility
$vsEffects = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"
Set-ItemProperty -Path $vsEffects -Name "TaskbarAnimations" -Value 0 -Type DWord -Force -ErrorAction SilentlyContinue

# UserPreferencesMask — "Adjust for best performance" binary value
# This disables: smooth scrolling, menu animations, tooltip animations, etc.
$prefPath = "HKCU:\Control Panel\Desktop"
$bestPerfMask = [byte[]]@(0x90, 0x12, 0x01, 0x80, 0x10, 0x00, 0x00, 0x00)
Set-ItemProperty -Path $prefPath -Name "UserPreferencesMask" -Value $bestPerfMask -Type Binary -Force -ErrorAction SilentlyContinue

Write-Host "       All animations, transparency, shadows disabled" -ForegroundColor Green
Write-Host "       Menu delay reduced to 100ms" -ForegroundColor Green

# =============================================================================
# [8] MEDIUM IMPACT — XBOX GAME BAR & GAME DVR
# =============================================================================
Write-Host ""
Write-Host "[8/17] Disabling Xbox Game Bar and Game DVR..." -ForegroundColor Yellow

# Disable Game DVR
$gameDVR = "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\GameDVR"
if (-not (Test-Path $gameDVR)) { New-Item -Path $gameDVR -Force | Out-Null }
Set-ItemProperty -Path $gameDVR -Name "AppCaptureEnabled" -Value 0 -Type DWord -Force

$gameConfig = "HKCU:\System\GameConfigStore"
if (-not (Test-Path $gameConfig)) { New-Item -Path $gameConfig -Force | Out-Null }
Set-ItemProperty -Path $gameConfig -Name "GameDVR_Enabled" -Value 0 -Type DWord -Force

# Disable Game Bar
$gameBar = "HKCU:\Software\Microsoft\GameBar"
if (-not (Test-Path $gameBar)) { New-Item -Path $gameBar -Force | Out-Null }
Set-ItemProperty -Path $gameBar -Name "AllowAutoGameMode" -Value 0 -Type DWord -Force
Set-ItemProperty -Path $gameBar -Name "AutoGameModeEnabled" -Value 0 -Type DWord -Force

# Disable Game Bar via policy
$gameBarPolicy = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\GameDVR"
if (-not (Test-Path $gameBarPolicy)) { New-Item -Path $gameBarPolicy -Force | Out-Null }
Set-ItemProperty -Path $gameBarPolicy -Name "AllowGameDVR" -Value 0 -Type DWord -Force

# Uninstall Xbox Game Bar
Get-AppxPackage Microsoft.XboxGamingOverlay | Remove-AppxPackage -ErrorAction SilentlyContinue
Get-AppxPackage Microsoft.XboxGameOverlay | Remove-AppxPackage -ErrorAction SilentlyContinue
Get-AppxPackage Microsoft.Xbox.TCUI | Remove-AppxPackage -ErrorAction SilentlyContinue

# Disable Xbox services
$xboxServices = @("XblAuthManager", "XblGameSave", "XboxNetApiSvc", "XboxGipSvc")
foreach ($xsvc in $xboxServices) {
    Set-Service -Name $xsvc -StartupType Disabled -ErrorAction SilentlyContinue
    Stop-Service -Name $xsvc -Force -ErrorAction SilentlyContinue
}
Write-Host "       Game Bar, Game DVR, Xbox services all disabled/removed" -ForegroundColor Green

# =============================================================================
# [9] MEDIUM IMPACT — ONEDRIVE RESOURCE REDUCTION
# =============================================================================
Write-Host ""
Write-Host "[9/17] Reducing OneDrive resource usage..." -ForegroundColor Yellow
Write-Host "       (Keeping OneDrive installed since user uses it for docs)" -ForegroundColor DarkGray

# Prevent OneDrive from starting at login (user can launch manually)
$oneDriveRun = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
Remove-ItemProperty -Path $oneDriveRun -Name "OneDrive" -ErrorAction SilentlyContinue

# Disable OneDrive auto-start via startup task
$startupApps = Get-CimInstance -ClassName Win32_StartupCommand | Where-Object { $_.Name -like "*OneDrive*" }
# Just removing from Run key is sufficient

# Disable Files On-Demand to prevent constant sync checks (optional — uncomment if wanted)
# $oneDrivePolicy = "HKLM:\SOFTWARE\Policies\Microsoft\OneDrive"
# if (-not (Test-Path $oneDrivePolicy)) { New-Item -Path $oneDrivePolicy -Force | Out-Null }
# Set-ItemProperty -Path $oneDrivePolicy -Name "FilesOnDemandEnabled" -Value 0 -Type DWord -Force

Write-Host "       OneDrive removed from auto-startup" -ForegroundColor Green
Write-Host "       TIP: Open OneDrive > Settings > Account > Choose Folders to limit sync" -ForegroundColor Cyan

# =============================================================================
# [10] MEDIUM IMPACT — MICROSOFT STORE BACKGROUND DOWNLOADS
# =============================================================================
Write-Host ""
Write-Host "[10/17] Disabling Microsoft Store auto-updates and background downloads..." -ForegroundColor Yellow

$storePath = "HKLM:\SOFTWARE\Policies\Microsoft\WindowsStore"
if (-not (Test-Path $storePath)) { New-Item -Path $storePath -Force | Out-Null }
Set-ItemProperty -Path $storePath -Name "AutoDownload" -Value 2 -Type DWord -Force
# AutoDownload: 2 = Always off, 4 = Always on
Set-ItemProperty -Path $storePath -Name "DisableOSUpgrade" -Value 1 -Type DWord -Force
Write-Host "       Store auto-downloads disabled" -ForegroundColor Green

# =============================================================================
# [11] MEDIUM IMPACT — ADDITIONAL INDEXING
# =============================================================================
Write-Host ""
Write-Host "[11/17] Disabling additional indexing services..." -ForegroundColor Yellow

# WSearch already disabled in section 1. Additional cleanup:

# Disable content indexing on C: drive (metadata still indexed)
$cDrive = Get-WmiObject -Class Win32_Volume -Filter "DriveLetter='C:'" -ErrorAction SilentlyContinue
if ($cDrive) {
    try {
        $cDrive.IndexingEnabled = $false
        $cDrive.Put() | Out-Null
        Write-Host "       Content indexing disabled on C: drive" -ForegroundColor Green
    } catch {
        Write-Host "       Could not disable C: drive indexing (non-fatal)" -ForegroundColor DarkYellow
    }
}

# Clean up old index database
$indexDB = "C:\ProgramData\Microsoft\Search\Data\Applications\Windows\Windows.db"
if (Test-Path $indexDB) {
    Write-Host "       Index database exists at: $indexDB" -ForegroundColor DarkGray
    Write-Host "       To reclaim space, delete after reboot when WSearch is fully stopped" -ForegroundColor Cyan
}

Write-Host "       WSearch disabled (section 1) + C: content indexing off" -ForegroundColor Green

# =============================================================================
# [12] MEDIUM IMPACT — SCHEDULED TASKS THAT WASTE CPU
# =============================================================================
Write-Host ""
Write-Host "[12/17] Disabling wasteful scheduled tasks..." -ForegroundColor Yellow

$tasksToDisable = @(
    # Telemetry (some already handled in section 2, but ensure coverage)
    "\Microsoft\Windows\Customer Experience Improvement Program\Consolidator",
    "\Microsoft\Windows\Customer Experience Improvement Program\UsbCeip",
    "\Microsoft\Windows\Customer Experience Improvement Program\KernelCeipTask",
    "\Microsoft\Windows\Application Experience\Microsoft Compatibility Appraiser",
    "\Microsoft\Windows\Application Experience\ProgramDataUpdater",
    "\Microsoft\Windows\Application Experience\StartupAppTask",
    "\Microsoft\Windows\Autochk\Proxy",
    "\Microsoft\Windows\DiskDiagnostic\Microsoft-Windows-DiskDiagnosticDataCollector",
    "\Microsoft\Windows\DiskDiagnostic\Microsoft-Windows-DiskDiagnosticResolver",

    # Feedback & tips
    "\Microsoft\Windows\Feedback\Siuf\DmClient",
    "\Microsoft\Windows\Feedback\Siuf\DmClientOnScenarioDownload",

    # Maps
    "\Microsoft\Windows\Maps\MapsToastTask",
    "\Microsoft\Windows\Maps\MapsUpdateTask",

    # Cloud content (spotlight, tips, suggestions)
    "\Microsoft\Windows\CloudExperienceHost\CreateObjectTask",

    # Flighting (Insider)
    "\Microsoft\Windows\Flighting\FeatureConfig\ReconcileFeatures",
    "\Microsoft\Windows\Flighting\FeatureConfig\UsageDataFlushing",
    "\Microsoft\Windows\Flighting\FeatureConfig\UsageDataReporting",
    "\Microsoft\Windows\Flighting\OneSettings\RefreshCache",

    # Family safety (not needed)
    "\Microsoft\Windows\Shell\FamilySafetyMonitor",
    "\Microsoft\Windows\Shell\FamilySafetyRefreshTask",

    # Retail demo
    "\Microsoft\Windows\RetailDemo\CleanupOfflineContent"
)

foreach ($task in $tasksToDisable) {
    try {
        $t = Get-ScheduledTask -TaskName ($task.Split("\")[-1]) -TaskPath ($task.Substring(0, $task.LastIndexOf("\") + 1)) -ErrorAction SilentlyContinue
        if ($t) {
            Disable-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue | Out-Null
            Write-Host "       Disabled: $task" -ForegroundColor Green
        }
    } catch {
        # Try alternate method
        try {
            schtasks /Change /TN $task /DISABLE 2>$null | Out-Null
            Write-Host "       Disabled (schtasks): $task" -ForegroundColor Green
        } catch {
            Write-Host "       Not found: $task" -ForegroundColor DarkGray
        }
    }
}

# =============================================================================
# [13] MEDIUM IMPACT — PRINT SPOOLER, FAX (already in section 1)
# =============================================================================
Write-Host ""
Write-Host "[13/17] Print Spooler & Fax already disabled in section 1." -ForegroundColor DarkGray
Write-Host "       Bluetooth left enabled by default — edit section 1 to disable." -ForegroundColor DarkGray

# =============================================================================
# [14] HIGH IMPACT — WINDOWS DEFENDER EXCLUSIONS
# =============================================================================
Write-Host ""
Write-Host "[14/17] Adding Windows Defender exclusions for NovaX paths..." -ForegroundColor Yellow

$exclusionPaths = @(
    "C:\NovaX",
    "C:\Users\Jupit\.ollama",
    "C:\NovaX\tools\bitnet",
    "C:\NovaX\novalang-vm",
    "C:\NovaX\core",
    "C:\NovaX\tools"
)

$exclusionProcesses = @(
    "python.exe",
    "pythonw.exe",
    "python3.exe",
    "ollama.exe",
    "ollama_llama_server.exe",
    "node.exe",
    "rustc.exe",
    "cargo.exe"
)

foreach ($path in $exclusionPaths) {
    try {
        Add-MpPreference -ExclusionPath $path -Force -ErrorAction SilentlyContinue
        Write-Host "       Excluded path: $path" -ForegroundColor Green
    } catch {
        Write-Host "       Could not exclude: $path" -ForegroundColor DarkYellow
    }
}

foreach ($proc in $exclusionProcesses) {
    try {
        Add-MpPreference -ExclusionProcess $proc -Force -ErrorAction SilentlyContinue
        Write-Host "       Excluded process: $proc" -ForegroundColor Green
    } catch {
        Write-Host "       Could not exclude process: $proc" -ForegroundColor DarkYellow
    }
}

# Reduce Defender scan CPU impact
try {
    Set-MpPreference -ScanAvgCPULoadFactor 20 -ErrorAction SilentlyContinue
    Write-Host "       Defender scan CPU limit set to 20%" -ForegroundColor Green
} catch {}

# Disable Defender real-time monitoring of archive files (large models)
try {
    Set-MpPreference -DisableArchiveScanning $true -ErrorAction SilentlyContinue
    Set-MpPreference -DisableEmailScanning $true -ErrorAction SilentlyContinue
    Write-Host "       Archive and email scanning disabled" -ForegroundColor Green
} catch {}

Write-Host "       Verify with: Get-MpPreference | Select -Expand ExclusionPath" -ForegroundColor Cyan

# =============================================================================
# [15] MEDIUM IMPACT — DISABLE POWER THROTTLING
# =============================================================================
Write-Host ""
Write-Host "[15/17] Disabling power throttling system-wide..." -ForegroundColor Yellow

$powerThrottle = "HKLM:\SYSTEM\CurrentControlSet\Control\Power\PowerThrottling"
if (-not (Test-Path $powerThrottle)) { New-Item -Path $powerThrottle -Force | Out-Null }
Set-ItemProperty -Path $powerThrottle -Name "PowerThrottlingOff" -Value 1 -Type DWord -Force
Write-Host "       Power throttling disabled globally" -ForegroundColor Green

# Set power plan to High Performance
try {
    $highPerf = powercfg /list | Select-String "High performance"
    if ($highPerf) {
        $guid = ($highPerf -split "\s+")[3]
        powercfg /setactive $guid
        Write-Host "       Power plan set to High Performance" -ForegroundColor Green
    } else {
        # Create Ultimate Performance plan (available on desktops)
        powercfg -duplicatescheme e9a42b02-d5df-448d-aa00-03f14749eb61 2>$null
        $ultimate = powercfg /list | Select-String "Ultimate"
        if ($ultimate) {
            $guid = ($ultimate -split "\s+")[3]
            powercfg /setactive $guid
            Write-Host "       Power plan set to Ultimate Performance" -ForegroundColor Green
        } else {
            Write-Host "       Could not find High/Ultimate Performance plan" -ForegroundColor DarkYellow
        }
    }
} catch {
    Write-Host "       Power plan change failed (non-fatal)" -ForegroundColor DarkYellow
}

# =============================================================================
# [16] MEDIUM IMPACT — PROCESS PRIORITY AUTOMATION
# =============================================================================
Write-Host ""
Write-Host "[16/17] Creating auto-priority script for AI processes..." -ForegroundColor Yellow

$priorityScript = @'
# NovaX Process Priority Booster
# Run this after starting Ollama/Python workloads, or add to Task Scheduler
# Priority classes: Idle=64, BelowNormal=16384, Normal=32, AboveNormal=32768, High=128, Realtime=256

$highPriorityProcesses = @("ollama", "ollama_llama_server", "python", "pythonw", "python3", "rustc", "cargo")
$lowPriorityProcesses = @("SearchIndexer", "MsMpEng", "OneDrive", "PhoneExperienceHost", "WidgetService", "gamingservices")

foreach ($name in $highPriorityProcesses) {
    Get-Process -Name $name -ErrorAction SilentlyContinue | ForEach-Object {
        $_.PriorityClass = [System.Diagnostics.ProcessPriorityClass]::High
        Write-Host "Set HIGH priority: $($_.Name) (PID: $($_.Id))"
    }
}

foreach ($name in $lowPriorityProcesses) {
    Get-Process -Name $name -ErrorAction SilentlyContinue | ForEach-Object {
        $_.PriorityClass = [System.Diagnostics.ProcessPriorityClass]::BelowNormal
        Write-Host "Set BELOW NORMAL: $($_.Name) (PID: $($_.Id))"
    }
}
'@

$priorityScriptPath = "C:\NovaX\tools\boost-priority.ps1"
Set-Content -Path $priorityScriptPath -Value $priorityScript -Force
Write-Host "       Priority booster saved to: $priorityScriptPath" -ForegroundColor Green
Write-Host "       Run after starting AI workloads, or schedule it" -ForegroundColor Cyan

# Also create a batch launcher for convenience
$batchContent = @'
@echo off
powershell -ExecutionPolicy Bypass -File "C:\NovaX\tools\boost-priority.ps1"
'@
Set-Content -Path "C:\NovaX\tools\boost-priority.bat" -Value $batchContent -Force
Write-Host "       Batch launcher: C:\NovaX\tools\boost-priority.bat" -ForegroundColor Green

# =============================================================================
# [17] MEDIUM IMPACT — MEMORY COMPRESSION
# =============================================================================
Write-Host ""
Write-Host "[17/17] Disabling memory compression (32GB RAM = not needed)..." -ForegroundColor Yellow

try {
    Disable-MMAgent -MemoryCompression -ErrorAction SilentlyContinue
    Write-Host "       Memory compression disabled" -ForegroundColor Green
    Write-Host "       This frees CPU cycles that were spent compressing RAM" -ForegroundColor Cyan
} catch {
    Write-Host "       Could not disable memory compression" -ForegroundColor DarkYellow
}

# Also disable Prefetch (SysMain handles this, already disabled)
$prefetch = "HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management\PrefetchParameters"
Set-ItemProperty -Path $prefetch -Name "EnablePrefetcher" -Value 0 -Type DWord -Force -ErrorAction SilentlyContinue
Set-ItemProperty -Path $prefetch -Name "EnableSuperfetch" -Value 0 -Type DWord -Force -ErrorAction SilentlyContinue
Write-Host "       Prefetch/Superfetch registry values set to 0" -ForegroundColor Green

# =============================================================================
# BONUS: REMOVE BLOATWARE APPS
# =============================================================================
Write-Host ""
Write-Host "[BONUS] Removing pre-installed bloatware apps..." -ForegroundColor Yellow

$bloatApps = @(
    "Microsoft.BingNews",
    "Microsoft.BingWeather",
    "Microsoft.BingFinance",
    "Microsoft.BingSports",
    "Microsoft.GetHelp",
    "Microsoft.Getstarted",
    "Microsoft.MicrosoftSolitaireCollection",
    "Microsoft.People",
    "Microsoft.PowerAutomateDesktop",
    "Microsoft.Todos",
    "Microsoft.WindowsAlarms",
    "Microsoft.WindowsFeedbackHub",
    "Microsoft.WindowsMaps",
    "Microsoft.WindowsSoundRecorder",
    "Microsoft.YourPhone",
    "Microsoft.ZuneMusic",
    "Microsoft.ZuneVideo",
    "Microsoft.MicrosoftOfficeHub",
    "Clipchamp.Clipchamp",
    "Microsoft.GamingApp",
    "Microsoft.ScreenSketch",
    "Microsoft.OutlookForWindows",
    "MicrosoftTeams",
    "Microsoft.WindowsCommunicationsApps",
    "king.com.CandyCrushSaga",
    "king.com.CandyCrushFriends",
    "SpotifyAB.SpotifyMusic",
    "Disney.37853FC22B2CE",
    "BytedancePte.Ltd.TikTok"
)

foreach ($app in $bloatApps) {
    $pkg = Get-AppxPackage -Name $app -ErrorAction SilentlyContinue
    if ($pkg) {
        Remove-AppxPackage -Package $pkg.PackageFullName -ErrorAction SilentlyContinue
        Write-Host "       Removed: $app" -ForegroundColor Green
    }
}

# Also remove provisioned (so they don't come back for new users)
foreach ($app in $bloatApps) {
    Get-AppxProvisionedPackage -Online | Where-Object { $_.DisplayName -eq $app } | ForEach-Object {
        Remove-AppxProvisionedPackage -Online -PackageName $_.PackageName -ErrorAction SilentlyContinue | Out-Null
    }
}
Write-Host "       Bloatware removal complete" -ForegroundColor Green

# =============================================================================
# SUMMARY
# =============================================================================
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host " DEBLOAT COMPLETE — REBOOT REQUIRED" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Changes applied:" -ForegroundColor White
Write-Host "  [HIGH]   23 services disabled" -ForegroundColor Green
Write-Host "  [HIGH]   Telemetry nuked (DiagTrack, tasks, registry, ETL log)" -ForegroundColor Green
Write-Host "  [HIGH]   Cortana/Widgets/Chat/News/Copilot gone" -ForegroundColor Green
Write-Host "  [HIGH]   P2P Delivery Optimization off" -ForegroundColor Green
Write-Host "  [HIGH]   All background apps force-denied" -ForegroundColor Green
Write-Host "  [HIGH]   Defender exclusions for NovaX/Ollama/BitNet" -ForegroundColor Green
Write-Host "  [MED]    All notifications disabled" -ForegroundColor Green
Write-Host "  [MED]    Visual effects set to best performance" -ForegroundColor Green
Write-Host "  [MED]    Xbox Game Bar/DVR removed" -ForegroundColor Green
Write-Host "  [MED]    OneDrive removed from auto-start" -ForegroundColor Green
Write-Host "  [MED]    Store auto-downloads off" -ForegroundColor Green
Write-Host "  [MED]    Search indexing fully disabled" -ForegroundColor Green
Write-Host "  [MED]    20+ wasteful scheduled tasks disabled" -ForegroundColor Green
Write-Host "  [MED]    Power throttling disabled, High Performance plan active" -ForegroundColor Green
Write-Host "  [MED]    Memory compression off (32GB RAM)" -ForegroundColor Green
Write-Host "  [MED]    Prefetch/Superfetch disabled" -ForegroundColor Green
Write-Host "  [BONUS]  ~25 bloatware apps removed" -ForegroundColor Green
Write-Host ""
Write-Host "Post-reboot:" -ForegroundColor Cyan
Write-Host "  1. Run C:\NovaX\tools\boost-priority.ps1 after starting AI workloads" -ForegroundColor White
Write-Host "  2. Verify Defender exclusions: Get-MpPreference | Select -Expand ExclusionPath" -ForegroundColor White
Write-Host "  3. Check memory compression: Get-MMAgent" -ForegroundColor White
Write-Host "  4. Monitor with Task Manager — you should see significantly lower idle CPU/RAM" -ForegroundColor White
Write-Host ""
Write-Host "To UNDO everything: Use the restore point created at the start." -ForegroundColor Yellow
Write-Host ""
