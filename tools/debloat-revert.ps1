#Requires -RunAsAdministrator
# =============================================================================
# NovaX Debloat REVERT Script — Undo All Changes
# =============================================================================
Write-Host "Reverting debloat changes..." -ForegroundColor Yellow

# Re-enable services
$servicesToEnable = @(
    "DiagTrack", "dmwappushservice", "SysMain", "WSearch", "DoSvc",
    "Spooler", "Fax", "MapsBroker", "lfsvc", "RetailDemo", "wisvc",
    "WerSvc", "wercplsupport", "PcaSvc", "DiagSvc",
    "diagnosticshub.standardcollector.service", "WMPNetworkSvc",
    "icssvc", "WpcMonSvc", "SEMgrSvc", "PhoneSvc", "TabletInputService",
    "WbioSrvc", "XblAuthManager", "XblGameSave", "XboxNetApiSvc", "XboxGipSvc"
)
foreach ($name in $servicesToEnable) {
    Set-Service -Name $name -StartupType Manual -ErrorAction SilentlyContinue
    Write-Host "  Re-enabled: $name" -ForegroundColor Green
}

# Re-enable telemetry
Remove-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\DataCollection" -Name "AllowTelemetry" -ErrorAction SilentlyContinue
Remove-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\DataCollection" -Name "MaxTelemetryAllowed" -ErrorAction SilentlyContinue

# Re-enable background apps
Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications" -Name "GlobalUserDisabled" -Value 0 -Force -ErrorAction SilentlyContinue
Remove-Item -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\AppPrivacy" -Recurse -Force -ErrorAction SilentlyContinue

# Re-enable notifications
Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\PushNotifications" -Name "ToastEnabled" -Value 1 -Force -ErrorAction SilentlyContinue
Remove-ItemProperty -Path "HKCU:\Software\Policies\Microsoft\Windows\Explorer" -Name "DisableNotificationCenter" -ErrorAction SilentlyContinue

# Re-enable visual effects
Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects" -Name "VisualFXSetting" -Value 0 -Force -ErrorAction SilentlyContinue
Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize" -Name "EnableTransparency" -Value 1 -Force -ErrorAction SilentlyContinue

# Re-enable Game DVR
Set-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\GameDVR" -Name "AppCaptureEnabled" -Value 1 -Force -ErrorAction SilentlyContinue
Set-ItemProperty -Path "HKCU:\System\GameConfigStore" -Name "GameDVR_Enabled" -Value 1 -Force -ErrorAction SilentlyContinue

# Re-enable Widgets/Chat
Set-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Advanced" -Name "TaskbarDa" -Value 1 -Force -ErrorAction SilentlyContinue
Set-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Advanced" -Name "TaskbarMn" -Value 1 -Force -ErrorAction SilentlyContinue

# Re-enable memory compression
Enable-MMAgent -MemoryCompression -ErrorAction SilentlyContinue

# Re-enable power throttling
Remove-Item -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Power\PowerThrottling" -Recurse -Force -ErrorAction SilentlyContinue

# Remove Defender exclusions
$paths = @("C:\NovaX", "C:\Users\Jupit\.ollama", "C:\NovaX\tools\bitnet", "C:\NovaX\novalang-vm", "C:\NovaX\core", "C:\NovaX\tools")
foreach ($p in $paths) { Remove-MpPreference -ExclusionPath $p -ErrorAction SilentlyContinue }

Write-Host ""
Write-Host "Revert complete. Restart your PC." -ForegroundColor Cyan
