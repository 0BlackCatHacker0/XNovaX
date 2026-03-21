#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Rollback RTX 4060 GPU optimizations to Windows defaults
.NOTES
    Run as Administrator. Reboot required after.
#>

$ErrorActionPreference = "Continue"

Write-Host "Rolling back GPU optimizations..." -ForegroundColor Yellow

# Remove CUDA/GGML environment variables
$envVarsToRemove = @(
    "CUDA_MODULE_LOADING", "CUDA_DEVICE_MAX_CONNECTIONS", "CUDA_CACHE_MAXSIZE",
    "CUDA_CACHE_PATH", "CUDA_AUTO_BOOST", "CUDA_VISIBLE_DEVICES",
    "CUDA_FORCE_PTX_JIT", "GGML_CUDA_ENABLE_UNIFIED_MEMORY",
    "GGML_CUDA_FORCE_CUBLAS", "GGML_CUDA_NO_PINNED_MEMORY",
    "NVIDIA_TF32_OVERRIDE", "CUDA_DEVICE_ORDER",
    "PYTORCH_CUDA_ALLOC_CONF", "TORCH_CUDA_ARCH_LIST", "CUDA_LAUNCH_BLOCKING"
)

foreach ($var in $envVarsToRemove) {
    [System.Environment]::SetEnvironmentVariable($var, $null, "Machine")
    Write-Host "  Removed: $var" -ForegroundColor Gray
}

# Remove driver registry tweaks (find NVIDIA GPU paths)
$videoBasePath = "HKLM:\SYSTEM\CurrentControlSet\Control\Video"
$driverKeysToRemove = @(
    "RMGpuPstateOnModuleUnload", "EnableMidBufferPreemption",
    "EnableMidGfxPreemption", "EnableMidGfxPreemptionVGPU",
    "EnableCEPreemption", "EnableSCGPreemption",
    "DisableDynamicPstate", "EnablePerformanceMode"
)

if (Test-Path $videoBasePath) {
    Get-ChildItem $videoBasePath | ForEach-Object {
        $subPath = Join-Path $_.PSPath "0000"
        if (Test-Path $subPath) {
            $desc = (Get-ItemProperty -Path $subPath -Name "DriverDesc" -ErrorAction SilentlyContinue).DriverDesc
            if ($desc -and $desc -match "NVIDIA") {
                foreach ($key in $driverKeysToRemove) {
                    Remove-ItemProperty -Path $subPath -Name $key -ErrorAction SilentlyContinue
                    Write-Host "  Removed: $key from $subPath" -ForegroundColor Gray
                }
            }
        }
    }
}

# Reset HwSchMode to default (2 is actually Windows default on Win11, 1 = off)
# Leave at 2 since it's the Win11 default

# Remove NVTweak overrides
$nvTweakPath = "HKCU:\Software\NVIDIA Corporation\Global\NVTweak"
if (Test-Path $nvTweakPath) {
    Remove-ItemProperty -Path $nvTweakPath -Name "PowerMizerEnable" -ErrorAction SilentlyContinue
    Remove-ItemProperty -Path $nvTweakPath -Name "PerfLevelSrc" -ErrorAction SilentlyContinue
    Remove-ItemProperty -Path $nvTweakPath -Name "PowerMizerLevel" -ErrorAction SilentlyContinue
    Write-Host "  Removed NVTweak overrides" -ForegroundColor Gray
}

Write-Host ""
Write-Host "Rollback complete. Reboot required." -ForegroundColor Yellow
