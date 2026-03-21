#Requires -RunAsAdministrator
<#
.SYNOPSIS
    RTX 4060 Laptop Maximum Performance Optimization
    Sets CUDA/NVIDIA environment variables and registry keys
.DESCRIPTION
    Targets: NVIDIA GeForce RTX 4060 Laptop GPU (AD107, 8GB GDDR6, 128-bit)
    - CUDA environment variables (system-level)
    - NVIDIA driver registry keys (preemption, P-state, shader cache)
    - Hardware-accelerated GPU scheduling
    - NVIDIA Control Panel overrides
.NOTES
    Run as Administrator. Reboot required after applying.
    Created: 2026-03-14 for NovaX project
#>

$ErrorActionPreference = "Stop"
$script:changes = @()
$script:errors = @()

function Log-Change {
    param([string]$Category, [string]$Key, [string]$Value, [string]$Status)
    $script:changes += [PSCustomObject]@{
        Category = $Category
        Key      = $Key
        Value    = $Value
        Status   = $Status
    }
}

function Log-Error {
    param([string]$Message)
    $script:errors += $Message
    Write-Host "  [ERROR] $Message" -ForegroundColor Red
}

Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "  RTX 4060 Laptop GPU Optimization Script" -ForegroundColor Cyan
Write-Host "  NovaX Project - Maximum AI/Compute Performance" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host ""

# ============================================================================
# SECTION 1: CUDA CACHE DIRECTORY
# ============================================================================
Write-Host "[1/6] Creating CUDA cache directory..." -ForegroundColor Yellow

$cudaCachePath = "C:\NovaX\cache\cuda"
if (-not (Test-Path $cudaCachePath)) {
    New-Item -ItemType Directory -Path $cudaCachePath -Force | Out-Null
    Write-Host "  Created: $cudaCachePath" -ForegroundColor Green
} else {
    Write-Host "  Already exists: $cudaCachePath" -ForegroundColor Green
}

# ============================================================================
# SECTION 2: SYSTEM ENVIRONMENT VARIABLES
# ============================================================================
Write-Host ""
Write-Host "[2/6] Setting CUDA & GGML environment variables (system-level)..." -ForegroundColor Yellow

$envVars = @{
    # CUDA Core Settings
    "CUDA_MODULE_LOADING"                   = "LAZY"          # Lazy-load CUDA modules, saves VRAM on startup
    "CUDA_DEVICE_MAX_CONNECTIONS"            = "8"             # Max concurrent CUDA streams (default=8 for compute 7.x+)
    "CUDA_CACHE_MAXSIZE"                     = "4294967296"    # 4GB shader cache (default is 256MB)
    "CUDA_CACHE_PATH"                        = $cudaCachePath  # Custom cache location in NovaX tree
    "CUDA_AUTO_BOOST"                        = "1"             # Allow automatic clock boosting
    "CUDA_VISIBLE_DEVICES"                   = "0"             # Pin to first (only) GPU
    "CUDA_FORCE_PTX_JIT"                     = "1"             # Force PTX JIT compilation for latest arch optimization

    # GGML/llama.cpp CUDA Settings
    "GGML_CUDA_ENABLE_UNIFIED_MEMORY"        = "1"             # Allow VRAM overflow to system RAM (critical for large models on 8GB)
    "GGML_CUDA_FORCE_CUBLAS"                 = "1"             # Force cuBLAS for matrix multiply
    "GGML_CUDA_NO_PINNED_MEMORY"             = "0"             # Keep pinned memory enabled (faster transfers)

    # NVIDIA Driver Behavior
    "NVIDIA_TF32_OVERRIDE"                   = "1"             # Enable TF32 tensor cores (2x throughput for FP32 workloads)
    "CUDA_DEVICE_ORDER"                      = "PCI_BUS_ID"    # Consistent GPU ordering by PCI bus

    # PyTorch / Deep Learning
    "PYTORCH_CUDA_ALLOC_CONF"                = "expandable_segments:True"  # Better memory fragmentation handling
    "TORCH_CUDA_ARCH_LIST"                   = "8.9"           # AD107 = compute capability 8.9
    "CUDA_LAUNCH_BLOCKING"                   = "0"             # Async kernel launches (faster, set to 1 only for debugging)
}

foreach ($kv in $envVars.GetEnumerator()) {
    try {
        $existing = [System.Environment]::GetEnvironmentVariable($kv.Key, "Machine")
        [System.Environment]::SetEnvironmentVariable($kv.Key, $kv.Value, "Machine")
        $status = if ($existing -eq $kv.Value) { "UNCHANGED" } elseif ($existing) { "UPDATED" } else { "SET" }
        Write-Host "  $status : $($kv.Key) = $($kv.Value)" -ForegroundColor $(if ($status -eq "UNCHANGED") { "Gray" } else { "Green" })
        Log-Change "EnvVar" $kv.Key $kv.Value $status
    } catch {
        Log-Error "Failed to set $($kv.Key): $_"
    }
}

# ============================================================================
# SECTION 3: FIND GPU GUID AND APPLY DRIVER REGISTRY KEYS
# ============================================================================
Write-Host ""
Write-Host "[3/6] Finding GPU GUID and applying driver registry keys..." -ForegroundColor Yellow

# Method 1: Search Video controller registry entries for NVIDIA
$gpuRegPaths = @()
$videoBasePath = "HKLM:\SYSTEM\CurrentControlSet\Control\Video"

if (Test-Path $videoBasePath) {
    $guids = Get-ChildItem $videoBasePath -ErrorAction SilentlyContinue
    foreach ($guid in $guids) {
        $subPath = Join-Path $guid.PSPath "0000"
        if (Test-Path $subPath) {
            $desc = (Get-ItemProperty -Path $subPath -Name "DriverDesc" -ErrorAction SilentlyContinue).DriverDesc
            if ($desc -and $desc -match "NVIDIA") {
                $gpuRegPaths += $subPath
                Write-Host "  Found NVIDIA GPU: $desc" -ForegroundColor Green
                Write-Host "  Registry path: $subPath" -ForegroundColor Gray
            }
        }
    }
}

if ($gpuRegPaths.Count -eq 0) {
    Log-Error "No NVIDIA GPU found in Video registry. Trying WMI fallback..."
    $gpu = Get-CimInstance Win32_VideoController | Where-Object { $_.Name -match "NVIDIA" }
    if ($gpu) {
        Write-Host "  Found via WMI: $($gpu.Name)" -ForegroundColor Yellow
        Write-Host "  PNP Device ID: $($gpu.PNPDeviceID)" -ForegroundColor Gray
        Write-Host "  Skipping driver-level registry keys (GUID not resolved)" -ForegroundColor Yellow
    } else {
        Log-Error "No NVIDIA GPU found at all. Are drivers installed?"
    }
}

# Apply preemption and P-state settings to each found GPU path
foreach ($gpuPath in $gpuRegPaths) {
    Write-Host ""
    Write-Host "  Applying to: $gpuPath" -ForegroundColor Cyan

    $driverKeys = @{
        # Preemption Controls - disable mid-buffer/graphics preemption for sustained throughput
        # These prevent the GPU from being interrupted mid-computation
        "RMGpuPstateOnModuleUnload"      = @{ Value = 1;  Type = "DWord"; Desc = "Keep high P-state when CUDA modules unload" }
        "EnableMidBufferPreemption"       = @{ Value = 0;  Type = "DWord"; Desc = "Disable mid-buffer preemption" }
        "EnableMidGfxPreemption"          = @{ Value = 0;  Type = "DWord"; Desc = "Disable mid-graphics preemption" }
        "EnableMidGfxPreemptionVGPU"      = @{ Value = 0;  Type = "DWord"; Desc = "Disable mid-gfx preemption (vGPU)" }
        "EnableCEPreemption"              = @{ Value = 0;  Type = "DWord"; Desc = "Disable copy engine preemption" }
        "EnableSCGPreemption"             = @{ Value = 0;  Type = "DWord"; Desc = "Disable SCG preemption" }

        # Disable power-saving P-state transitions during compute
        "DisableDynamicPstate"            = @{ Value = 1;  Type = "DWord"; Desc = "Lock GPU to highest P-state" }
        "EnablePerformanceMode"           = @{ Value = 1;  Type = "DWord"; Desc = "Enable max performance mode" }
    }

    foreach ($kv in $driverKeys.GetEnumerator()) {
        try {
            $existing = (Get-ItemProperty -Path $gpuPath -Name $kv.Key -ErrorAction SilentlyContinue).$($kv.Key)
            Set-ItemProperty -Path $gpuPath -Name $kv.Key -Value $kv.Value.Value -Type $kv.Value.Type -Force
            $status = if ($existing -eq $kv.Value.Value) { "UNCHANGED" } elseif ($null -ne $existing) { "UPDATED" } else { "SET" }
            Write-Host "    $status : $($kv.Key) = $($kv.Value.Value) ($($kv.Value.Desc))" -ForegroundColor $(if ($status -eq "UNCHANGED") { "Gray" } else { "Green" })
            Log-Change "DriverReg" $kv.Key "$($kv.Value.Value)" $status
        } catch {
            Log-Error "Failed to set $($kv.Key): $_"
        }
    }
}

# ============================================================================
# SECTION 4: NVIDIA CONTROL PANEL REGISTRY OVERRIDES
# ============================================================================
Write-Host ""
Write-Host "[4/6] Applying NVIDIA Control Panel registry overrides..." -ForegroundColor Yellow

# NVTweak path - per-user NVIDIA tweaks
$nvTweakPath = "HKCU:\Software\NVIDIA Corporation\Global\NVTweak"
if (-not (Test-Path $nvTweakPath)) {
    New-Item -Path $nvTweakPath -Force | Out-Null
    Write-Host "  Created NVTweak registry path" -ForegroundColor Green
}

$nvTweakKeys = @{
    "PowerMizerEnable" = @{ Value = 1;      Type = "DWord"; Desc = "Enable PowerMizer control" }
    "PerfLevelSrc"     = @{ Value = 0x2222;  Type = "DWord"; Desc = "All perf levels = max (AC+Battery)" }
    "PowerMizerLevel"  = @{ Value = 1;       Type = "DWord"; Desc = "Prefer maximum performance" }
}

foreach ($kv in $nvTweakKeys.GetEnumerator()) {
    try {
        Set-ItemProperty -Path $nvTweakPath -Name $kv.Key -Value $kv.Value.Value -Type $kv.Value.Type -Force
        Write-Host "    SET : $($kv.Key) = $($kv.Value.Value) ($($kv.Value.Desc))" -ForegroundColor Green
        Log-Change "NVTweak" $kv.Key "$($kv.Value.Value)" "SET"
    } catch {
        Log-Error "Failed to set NVTweak $($kv.Key): $_"
    }
}

# Global NVIDIA profile settings
$nvGlobalPath = "HKCU:\Software\NVIDIA Corporation\Global"
$nvProfilePath = "HKCU:\Software\NVIDIA Corporation\Global\NVTweak\DisplayPowerSaving"
if (-not (Test-Path $nvProfilePath)) {
    New-Item -Path $nvProfilePath -Force | Out-Null
}

# Power management mode: Prefer Maximum Performance
try {
    Set-ItemProperty -Path $nvProfilePath -Name "Enable" -Value 0 -Type DWord -Force
    Write-Host "    SET : DisplayPowerSaving\Enable = 0 (Disable display power saving)" -ForegroundColor Green
    Log-Change "NVTweak" "DisplayPowerSaving\Enable" "0" "SET"
} catch {
    Log-Error "Failed to set DisplayPowerSaving: $_"
}

# ============================================================================
# SECTION 5: HARDWARE-ACCELERATED GPU SCHEDULING + SHADER CACHE
# ============================================================================
Write-Host ""
Write-Host "[5/6] Configuring GPU scheduling and shader cache..." -ForegroundColor Yellow

# Hardware-accelerated GPU scheduling
$gfxDriversPath = "HKLM:\SYSTEM\CurrentControlSet\Control\GraphicsDrivers"
if (Test-Path $gfxDriversPath) {
    try {
        $currentHwSch = (Get-ItemProperty -Path $gfxDriversPath -Name "HwSchMode" -ErrorAction SilentlyContinue).HwSchMode
        Set-ItemProperty -Path $gfxDriversPath -Name "HwSchMode" -Value 2 -Type DWord -Force
        $status = if ($currentHwSch -eq 2) { "UNCHANGED" } else { "SET" }
        Write-Host "    $status : HwSchMode = 2 (Hardware-accelerated GPU scheduling ON)" -ForegroundColor $(if ($status -eq "UNCHANGED") { "Gray" } else { "Green" })
        Log-Change "GfxDrivers" "HwSchMode" "2" $status
    } catch {
        Log-Error "Failed to set HwSchMode: $_"
    }

    # Variable refresh rate / VRR scheduling
    try {
        Set-ItemProperty -Path $gfxDriversPath -Name "EnableVRR" -Value 1 -Type DWord -Force
        Write-Host "    SET : EnableVRR = 1 (Variable refresh rate enabled)" -ForegroundColor Green
        Log-Change "GfxDrivers" "EnableVRR" "1" "SET"
    } catch {
        Log-Error "Failed to set EnableVRR: $_"
    }
}

# NVIDIA Shader Cache (driver-level)
$nvlddmkmPath = "HKLM:\SYSTEM\CurrentControlSet\Services\nvlddmkm"
if (Test-Path $nvlddmkmPath) {
    # Shader cache size - set to max (0xFFFFFFFF = unlimited)
    try {
        Set-ItemProperty -Path $nvlddmkmPath -Name "D3D_Shader_Cache_Size" -Value 0xFFFFFFFF -Type DWord -Force
        Write-Host "    SET : D3D_Shader_Cache_Size = unlimited" -ForegroundColor Green
        Log-Change "nvlddmkm" "D3D_Shader_Cache_Size" "0xFFFFFFFF" "SET"
    } catch {
        Log-Error "Failed to set shader cache size: $_"
    }

    # Ensure shader cache is enabled
    try {
        Set-ItemProperty -Path $nvlddmkmPath -Name "EnableShaderCache" -Value 1 -Type DWord -Force
        Write-Host "    SET : EnableShaderCache = 1" -ForegroundColor Green
        Log-Change "nvlddmkm" "EnableShaderCache" "1" "SET"
    } catch {
        Log-Error "Failed to set EnableShaderCache: $_"
    }
} else {
    Log-Error "nvlddmkm service path not found. NVIDIA drivers may not be installed."
}

# NVIDIA shader cache FBC/encode settings
$nvEncPath = "HKLM:\SYSTEM\CurrentControlSet\Services\nvlddmkm\FTS"
if (-not (Test-Path $nvEncPath)) {
    New-Item -Path $nvEncPath -Force | Out-Null 2>$null
}
if (Test-Path $nvEncPath) {
    try {
        Set-ItemProperty -Path $nvEncPath -Name "EnableRID73779" -Value 1 -Type DWord -Force
        Write-Host "    SET : FTS\EnableRID73779 = 1 (Unlock NVENC sessions)" -ForegroundColor Green
        Log-Change "nvlddmkm\FTS" "EnableRID73779" "1" "SET"
    } catch {
        Log-Error "Failed to set NVENC unlock: $_"
    }
}

# ============================================================================
# SECTION 6: VERIFICATION
# ============================================================================
Write-Host ""
Write-Host "[6/6] Verifying settings..." -ForegroundColor Yellow
Write-Host ""

# Verify environment variables
Write-Host "  --- Environment Variables (will take effect in new processes) ---" -ForegroundColor Cyan
foreach ($kv in $envVars.GetEnumerator()) {
    $val = [System.Environment]::GetEnvironmentVariable($kv.Key, "Machine")
    $match = $val -eq $kv.Value
    $icon = if ($match) { "OK" } else { "MISMATCH" }
    $color = if ($match) { "Green" } else { "Red" }
    Write-Host "    [$icon] $($kv.Key) = $val" -ForegroundColor $color
}

# Verify GPU info
Write-Host ""
Write-Host "  --- GPU Information ---" -ForegroundColor Cyan
$gpuInfo = Get-CimInstance Win32_VideoController | Where-Object { $_.Name -match "NVIDIA" }
if ($gpuInfo) {
    Write-Host "    Name           : $($gpuInfo.Name)" -ForegroundColor White
    Write-Host "    Driver Version : $($gpuInfo.DriverVersion)" -ForegroundColor White
    Write-Host "    VRAM           : $([math]::Round($gpuInfo.AdapterRAM / 1GB, 1)) GB (reported)" -ForegroundColor White
    Write-Host "    Status         : $($gpuInfo.Status)" -ForegroundColor White
    Write-Host "    PNP Device ID  : $($gpuInfo.PNPDeviceID)" -ForegroundColor Gray
}

# Check nvidia-smi if available
$nvidiaSmi = Get-Command "nvidia-smi" -ErrorAction SilentlyContinue
if ($nvidiaSmi) {
    Write-Host ""
    Write-Host "  --- nvidia-smi Quick Check ---" -ForegroundColor Cyan
    $smiOutput = & nvidia-smi --query-gpu=name,temperature.gpu,power.draw,clocks.current.graphics,clocks.current.memory,memory.used,memory.total --format=csv,noheader,nounits 2>$null
    if ($smiOutput) {
        $parts = $smiOutput -split ","
        if ($parts.Count -ge 7) {
            Write-Host "    GPU Temp       : $($parts[1].Trim()) C" -ForegroundColor White
            Write-Host "    Power Draw     : $($parts[2].Trim()) W" -ForegroundColor White
            Write-Host "    GPU Clock      : $($parts[3].Trim()) MHz" -ForegroundColor White
            Write-Host "    Mem Clock      : $($parts[4].Trim()) MHz" -ForegroundColor White
            Write-Host "    VRAM Used      : $($parts[5].Trim()) / $($parts[6].Trim()) MiB" -ForegroundColor White
        }
    }
}

# Check CUDA toolkit
$nvcc = Get-Command "nvcc" -ErrorAction SilentlyContinue
if ($nvcc) {
    $cudaVer = & nvcc --version 2>$null | Select-String "release"
    Write-Host ""
    Write-Host "  --- CUDA Toolkit ---" -ForegroundColor Cyan
    Write-Host "    $cudaVer" -ForegroundColor White
}

# ============================================================================
# SUMMARY
# ============================================================================
Write-Host ""
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "  SUMMARY" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan

$setCount = ($script:changes | Where-Object { $_.Status -eq "SET" }).Count
$updatedCount = ($script:changes | Where-Object { $_.Status -eq "UPDATED" }).Count
$unchangedCount = ($script:changes | Where-Object { $_.Status -eq "UNCHANGED" }).Count
$errorCount = $script:errors.Count

Write-Host "  New settings applied : $setCount" -ForegroundColor Green
Write-Host "  Settings updated     : $updatedCount" -ForegroundColor Yellow
Write-Host "  Already correct      : $unchangedCount" -ForegroundColor Gray
Write-Host "  Errors               : $errorCount" -ForegroundColor $(if ($errorCount -gt 0) { "Red" } else { "Green" })

if ($script:errors.Count -gt 0) {
    Write-Host ""
    Write-Host "  Errors:" -ForegroundColor Red
    foreach ($err in $script:errors) {
        Write-Host "    - $err" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "  REBOOT REQUIRED for all changes to take effect." -ForegroundColor Yellow
Write-Host "  Registry changes apply after restart." -ForegroundColor Yellow
Write-Host "  Environment variables apply to new processes immediately." -ForegroundColor Yellow
Write-Host ""
Write-Host "=" * 70 -ForegroundColor Cyan

# ============================================================================
# OPTIONAL: Export settings for backup/restore
# ============================================================================
$exportPath = "C:\NovaX\tools\gpu_settings_backup.json"
$backup = @{
    Timestamp    = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
    GPU          = if ($gpuInfo) { $gpuInfo.Name } else { "Unknown" }
    EnvVars      = $envVars
    Changes      = $script:changes
    Errors       = $script:errors
}
$backup | ConvertTo-Json -Depth 4 | Set-Content -Path $exportPath -Encoding UTF8
Write-Host "  Settings backup saved to: $exportPath" -ForegroundColor Gray
Write-Host ""
