#############################################################################
# NovaX Disk Space Analysis & Cleanup Script
# Run as Administrator for full access: Right-click PowerShell > Run as Admin
# Usage: powershell -ExecutionPolicy Bypass -File C:\NovaX\tools\disk-analysis.ps1
#############################################################################

param(
    [switch]$Cleanup,        # Actually delete files (default: report only)
    [switch]$CompressAnalysis # Run NTFS compression analysis (slow)
)

$ErrorActionPreference = "SilentlyContinue"
$divider = "=" * 70

function Format-Size($bytes) {
    if ($bytes -ge 1TB) { "{0:N2} TB" -f ($bytes / 1TB) }
    elseif ($bytes -ge 1GB) { "{0:N2} GB" -f ($bytes / 1GB) }
    elseif ($bytes -ge 1MB) { "{0:N2} MB" -f ($bytes / 1MB) }
    else { "{0:N2} KB" -f ($bytes / 1KB) }
}

Write-Host "`n$divider" -ForegroundColor Cyan
Write-Host " NOVAX DISK SPACE ANALYSIS" -ForegroundColor Cyan
Write-Host " $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor DarkCyan
Write-Host "$divider`n" -ForegroundColor Cyan

###########################################################################
# 1. DRIVE OVERVIEW
###########################################################################
Write-Host "[1] DRIVE OVERVIEW" -ForegroundColor Yellow
$drive = Get-PSDrive C
$used = $drive.Used
$free = $drive.Free
$total = $used + $free
$pctUsed = [math]::Round(($used / $total) * 100, 1)

Write-Host "  Total:  $(Format-Size $total)"
Write-Host "  Used:   $(Format-Size $used) ($pctUsed%)"
Write-Host "  Free:   $(Format-Size $free)"

# Visual bar
$barLen = 50
$filledLen = [math]::Round($pctUsed / 100 * $barLen)
$bar = ("#" * $filledLen) + ("-" * ($barLen - $filledLen))
$color = if ($pctUsed -gt 90) { "Red" } elseif ($pctUsed -gt 75) { "Yellow" } else { "Green" }
Write-Host "  [$bar] $pctUsed%" -ForegroundColor $color
Write-Host ""

###########################################################################
# 2. TOP SPACE CONSUMERS (top-level C:\ folders)
###########################################################################
Write-Host "[2] TOP SPACE CONSUMERS (C:\ top-level folders)" -ForegroundColor Yellow
Write-Host "  Scanning... (this takes a minute)" -ForegroundColor DarkGray

$topFolders = Get-ChildItem C:\ -Directory -Force -ErrorAction SilentlyContinue | ForEach-Object {
    $size = (Get-ChildItem $_.FullName -Recurse -Force -ErrorAction SilentlyContinue |
             Measure-Object -Property Length -Sum -ErrorAction SilentlyContinue).Sum
    [PSCustomObject]@{
        Folder = $_.FullName
        SizeBytes = [long]$size
        Size = Format-Size ([long]$size)
    }
} | Sort-Object SizeBytes -Descending | Select-Object -First 15

$topFolders | ForEach-Object {
    $pct = [math]::Round($_.SizeBytes / $used * 100, 1)
    Write-Host ("  {0,-40} {1,12}  ({2}%)" -f $_.Folder, $_.Size, $pct)
}
Write-Host ""

###########################################################################
# 3. OLLAMA MODELS ANALYSIS
###########################################################################
Write-Host "[3] OLLAMA MODELS ANALYSIS" -ForegroundColor Yellow

$ollamaBase = "$env:USERPROFILE\.ollama\models"
if (Test-Path $ollamaBase) {
    # Total size
    $allFiles = Get-ChildItem $ollamaBase -Recurse -Force -File
    $totalOllama = ($allFiles | Measure-Object -Property Length -Sum).Sum
    Write-Host "  Total Ollama models dir: $(Format-Size $totalOllama)"
    Write-Host "  Total files: $($allFiles.Count)"

    # Blobs analysis (content-addressed storage)
    $blobsDir = Join-Path $ollamaBase "blobs"
    if (Test-Path $blobsDir) {
        $blobs = Get-ChildItem $blobsDir -File -Force
        $blobTotal = ($blobs | Measure-Object -Property Length -Sum).Sum
        $blobCount = $blobs.Count

        # Ollama uses SHA256 content-addressed blobs
        # Same hash = same content = already deduplicated
        # Different model variants (e.g., llama3:8b-instruct vs llama3:8b-chat)
        # share base layer blobs automatically
        Write-Host ""
        Write-Host "  BLOB STORAGE (content-addressed SHA256):" -ForegroundColor DarkCyan
        Write-Host "  Total blobs: $blobCount"
        Write-Host "  Total blob size: $(Format-Size $blobTotal)"

        # Group by size to find potential duplicates (same size != same content, but indicative)
        $sizeGroups = $blobs | Group-Object Length | Where-Object { $_.Count -gt 1 }
        $potentialDupSize = ($sizeGroups | ForEach-Object {
            ($_.Count - 1) * $_.Group[0].Length
        } | Measure-Object -Sum).Sum

        Write-Host "  Blob groups with same size: $($sizeGroups.Count)"
        Write-Host "  Potential dup by size (upper bound): $(Format-Size $potentialDupSize)"
        Write-Host ""
        Write-Host "  NOTE: Ollama ALREADY deduplicates via content-addressed storage." -ForegroundColor Green
        Write-Host "  Blobs are stored by SHA256 hash. If two models share a layer," -ForegroundColor Green
        Write-Host "  they reference the SAME blob file. No further dedup needed." -ForegroundColor Green

        # Size distribution
        Write-Host ""
        Write-Host "  BLOB SIZE DISTRIBUTION:" -ForegroundColor DarkCyan
        $ranges = @(
            @{Label="< 1 MB";    Min=0;        Max=1MB},
            @{Label="1-100 MB";  Min=1MB;      Max=100MB},
            @{Label="100MB-1GB"; Min=100MB;    Max=1GB},
            @{Label="1-5 GB";    Min=1GB;      Max=5GB},
            @{Label="5-10 GB";   Min=5GB;      Max=10GB},
            @{Label="> 10 GB";   Min=10GB;     Max=[long]::MaxValue}
        )
        foreach ($r in $ranges) {
            $inRange = $blobs | Where-Object { $_.Length -ge $r.Min -and $_.Length -lt $r.Max }
            $rangeSize = ($inRange | Measure-Object Length -Sum).Sum
            if ($inRange.Count -gt 0) {
                Write-Host ("    {0,-12} {1,5} blobs  {2,12}" -f $r.Label, $inRange.Count, (Format-Size $rangeSize))
            }
        }

        # List largest individual blobs
        Write-Host ""
        Write-Host "  TOP 10 LARGEST BLOBS:" -ForegroundColor DarkCyan
        $blobs | Sort-Object Length -Descending | Select-Object -First 10 | ForEach-Object {
            Write-Host ("    {0}  {1}" -f (Format-Size $_.Length), $_.Name.Substring(0, [Math]::Min(60, $_.Name.Length)))
        }
    }

    # Manifests (model definitions)
    $manifestsDir = Join-Path $ollamaBase "manifests"
    if (Test-Path $manifestsDir) {
        $manifests = Get-ChildItem $manifestsDir -Recurse -File -Force
        Write-Host ""
        Write-Host "  Model manifests: $($manifests.Count)"

        # List all model names
        Write-Host "  Models installed:" -ForegroundColor DarkCyan
        $modelDirs = Get-ChildItem (Join-Path $manifestsDir "registry.ollama.ai\library") -Directory -ErrorAction SilentlyContinue
        foreach ($model in $modelDirs) {
            $tags = (Get-ChildItem $model.FullName -Recurse -File).Name -join ", "
            Write-Host "    $($model.Name): $tags"
        }
    }
} else {
    Write-Host "  Ollama models directory not found at $ollamaBase"
    # Check alternative locations
    foreach ($alt in @("C:\Ollama", "D:\Ollama", "$env:LOCALAPPDATA\Ollama")) {
        if (Test-Path $alt) { Write-Host "  Found alternative: $alt" }
    }
}
Write-Host ""

###########################################################################
# 4. TEMP FILES & CACHES
###########################################################################
Write-Host "[4] TEMP FILES & CACHES" -ForegroundColor Yellow

$tempLocations = @(
    @{Path="$env:TEMP";                          Label="User Temp"},
    @{Path="C:\Windows\Temp";                    Label="Windows Temp"},
    @{Path="$env:LOCALAPPDATA\Temp";             Label="AppData Local Temp"},
    @{Path="$env:LOCALAPPDATA\pip\cache";        Label="Pip Cache"},
    @{Path="$env:LOCALAPPDATA\Brave Software\Brave-Browser\User Data\Default\Cache"; Label="Brave Cache"},
    @{Path="$env:LOCALAPPDATA\Microsoft\Edge\User Data\Default\Cache"; Label="Edge Cache"},
    @{Path="$env:LOCALAPPDATA\Google\Chrome\User Data\Default\Cache";  Label="Chrome Cache"},
    @{Path="$env:LOCALAPPDATA\npm-cache";        Label="NPM Cache"},
    @{Path="$env:LOCALAPPDATA\NuGet\v3-cache";   Label="NuGet Cache"},
    @{Path="$env:LOCALAPPDATA\Microsoft\Windows\Explorer"; Label="Explorer Thumbcache"},
    @{Path="C:\Windows\SoftwareDistribution\Download"; Label="Windows Update Downloads"},
    @{Path="C:\Windows\Installer\`$PatchCache`$"; Label="Windows Installer Patch Cache"},
    @{Path="$env:LOCALAPPDATA\CrashDumps";       Label="Crash Dumps"},
    @{Path="$env:USERPROFILE\.cargo\registry\cache"; Label="Rust Cargo Cache"},
    @{Path="$env:USERPROFILE\.rustup\toolchains"; Label="Rustup Toolchains"},
    @{Path="$env:APPDATA\Code\Cache";            Label="VS Code Cache"},
    @{Path="$env:APPDATA\Code\CachedData";       Label="VS Code CachedData"},
    @{Path="$env:APPDATA\Code\logs";             Label="VS Code Logs"},
    @{Path="$env:LOCALAPPDATA\Docker";           Label="Docker"},
    @{Path="$env:USERPROFILE\.gradle\caches";    Label="Gradle Cache"},
    @{Path="C:\`$Recycle.Bin";                   Label="Recycle Bin"}
)

$totalReclaimable = 0
$cacheResults = @()

foreach ($loc in $tempLocations) {
    if (Test-Path $loc.Path) {
        $size = (Get-ChildItem $loc.Path -Recurse -Force -ErrorAction SilentlyContinue |
                 Measure-Object -Property Length -Sum -ErrorAction SilentlyContinue).Sum
        if ($size -gt 1MB) {
            $cacheResults += [PSCustomObject]@{
                Label = $loc.Label
                Path = $loc.Path
                SizeBytes = [long]$size
                Size = Format-Size ([long]$size)
            }
            $totalReclaimable += $size
        }
    }
}

$cacheResults | Sort-Object SizeBytes -Descending | ForEach-Object {
    $safe = if ($_.Label -match "Temp|Cache|Dumps|Recycle|Logs") { "[SAFE]" } else { "[REVIEW]" }
    $col = if ($safe -eq "[SAFE]") { "Green" } else { "Yellow" }
    Write-Host ("  {0,-7} {1,-30} {2,12}  {3}" -f $safe, $_.Label, $_.Size, $_.Path) -ForegroundColor $col
}

Write-Host ""
Write-Host "  TOTAL RECLAIMABLE (estimate): $(Format-Size $totalReclaimable)" -ForegroundColor Magenta
Write-Host ""

###########################################################################
# 5. PYTHON __PYCACHE__ DIRECTORIES
###########################################################################
Write-Host "[5] PYTHON __PYCACHE__ DIRECTORIES" -ForegroundColor Yellow

$pycacheDirs = @()
foreach ($searchRoot in @("C:\NovaX", "$env:USERPROFILE\OneDrive\Documents")) {
    if (Test-Path $searchRoot) {
        Get-ChildItem $searchRoot -Directory -Recurse -Force -Filter "__pycache__" -ErrorAction SilentlyContinue | ForEach-Object {
            $size = (Get-ChildItem $_.FullName -Recurse -Force -ErrorAction SilentlyContinue |
                     Measure-Object Length -Sum).Sum
            $pycacheDirs += [PSCustomObject]@{Path=$_.FullName; SizeBytes=[long]$size; Size=Format-Size([long]$size)}
        }
    }
}
$pycacheTotal = ($pycacheDirs | Measure-Object SizeBytes -Sum).Sum
Write-Host "  Found $($pycacheDirs.Count) __pycache__ dirs, total $(Format-Size $pycacheTotal)"
if ($pycacheDirs.Count -gt 0 -and $pycacheDirs.Count -le 30) {
    $pycacheDirs | Sort-Object SizeBytes -Descending | Select-Object -First 10 | ForEach-Object {
        Write-Host "    $($_.Size)  $($_.Path)"
    }
}
Write-Host ""

###########################################################################
# 6. WINDOWS COMPONENT STORE (WinSxS)
###########################################################################
Write-Host "[6] WINDOWS COMPONENT STORE" -ForegroundColor Yellow
$winsxs = (Get-ChildItem "C:\Windows\WinSxS" -Force -ErrorAction SilentlyContinue |
            Measure-Object).Count
$winsxsSize = (Get-ChildItem "C:\Windows\WinSxS" -Recurse -Force -ErrorAction SilentlyContinue |
                Measure-Object Length -Sum -ErrorAction SilentlyContinue).Sum
Write-Host "  WinSxS entries: $winsxs"
Write-Host "  WinSxS size: $(Format-Size $winsxsSize)"
Write-Host "  NOTE: WinSxS uses hard links; actual unique data is much less." -ForegroundColor DarkGray
Write-Host "  Run as Admin: DISM /Online /Cleanup-Image /StartComponentCleanup" -ForegroundColor DarkCyan
Write-Host ""

###########################################################################
# 7. DEDUPLICATION ANALYSIS
###########################################################################
Write-Host "[7] DEDUPLICATION OPPORTUNITIES" -ForegroundColor Yellow
Write-Host ""
Write-Host "  OLLAMA (already handled):" -ForegroundColor DarkCyan
Write-Host "    Ollama uses content-addressed SHA256 blob storage."
Write-Host "    Models sharing layers (e.g., llama3 variants) already share blobs."
Write-Host "    No additional dedup needed for Ollama."
Write-Host ""
Write-Host "  WINDOWS 11 HOME DEDUP OPTIONS:" -ForegroundColor DarkCyan
Write-Host "    - Native NTFS dedup: NOT available (Server SKU only)"
Write-Host "    - ReFS dedup: NOT available on Home edition"
Write-Host "    - WinBtrfs: Experimental, NOT recommended for system drive"
Write-Host ""
Write-Host "  PRACTICAL ALTERNATIVES:" -ForegroundColor DarkCyan
Write-Host "    1. NTFS Compression (built-in, safe, ~30-50% on text/code)"
Write-Host "    2. Hard links for identical files (fsutil hardlink create)"
Write-Host "    3. Symbolic links for relocated folders (mklink /D)"
Write-Host "    4. Manual dedup: identify large duplicate files with tools like:"
Write-Host "       - dupeGuru (free), AllDup (free), WizTree (fast scanner)"
Write-Host ""

###########################################################################
# 8. NTFS COMPRESSION CANDIDATES
###########################################################################
Write-Host "[8] NTFS COMPRESSION CANDIDATES" -ForegroundColor Yellow

$compressCandidates = @(
    @{Path="C:\NovaX";                   Label="NovaX codebase (code compresses well)"},
    @{Path="$env:USERPROFILE\OneDrive\Documents"; Label="Documents"},
    @{Path="$env:USERPROFILE\.cargo";    Label="Rust cargo (source + indices)"},
    @{Path="$env:USERPROFILE\.rustup";   Label="Rustup toolchains"},
    @{Path="C:\Windows\Logs";           Label="Windows Logs"}
)

foreach ($c in $compressCandidates) {
    if (Test-Path $c.Path) {
        $size = (Get-ChildItem $c.Path -Recurse -Force -ErrorAction SilentlyContinue |
                 Measure-Object Length -Sum).Sum
        $estSaved = [long]($size * 0.35)  # Conservative 35% estimate for code/text
        Write-Host ("  {0,-45} {1,10} -> save ~{2}" -f $c.Label, (Format-Size $size), (Format-Size $estSaved))
    }
}

Write-Host ""
Write-Host "  To compress a folder:" -ForegroundColor DarkCyan
Write-Host '    compact /c /s /i /q "C:\NovaX"' -ForegroundColor White
Write-Host "  To check compression status:" -ForegroundColor DarkCyan
Write-Host '    compact /s /q "C:\NovaX"' -ForegroundColor White
Write-Host ""

###########################################################################
# 9. CLEANUP ACTIONS (if -Cleanup flag)
###########################################################################
if ($Cleanup) {
    Write-Host "$divider" -ForegroundColor Red
    Write-Host " CLEANUP MODE - DELETING FILES" -ForegroundColor Red
    Write-Host "$divider" -ForegroundColor Red

    # User temp (older than 7 days)
    Write-Host "  Cleaning User Temp (>7 days old)..."
    $cleaned = 0
    Get-ChildItem $env:TEMP -Recurse -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-7) } |
        ForEach-Object {
            try { Remove-Item $_.FullName -Recurse -Force -ErrorAction Stop; $cleaned += $_.Length } catch {}
        }
    Write-Host "    Cleaned: $(Format-Size $cleaned)"

    # Windows Temp (older than 7 days)
    Write-Host "  Cleaning Windows Temp (>7 days old)..."
    $cleaned = 0
    Get-ChildItem "C:\Windows\Temp" -Recurse -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-7) } |
        ForEach-Object {
            try { Remove-Item $_.FullName -Recurse -Force -ErrorAction Stop; $cleaned += $_.Length } catch {}
        }
    Write-Host "    Cleaned: $(Format-Size $cleaned)"

    # __pycache__
    Write-Host "  Cleaning __pycache__ directories..."
    $cleaned = 0
    foreach ($d in $pycacheDirs) {
        try {
            $cleaned += $d.SizeBytes
            Remove-Item $d.Path -Recurse -Force -ErrorAction Stop
        } catch {}
    }
    Write-Host "    Cleaned: $(Format-Size $cleaned)"

    # Crash dumps
    $crashDir = "$env:LOCALAPPDATA\CrashDumps"
    if (Test-Path $crashDir) {
        Write-Host "  Cleaning crash dumps..."
        $size = (Get-ChildItem $crashDir -Recurse -Force | Measure-Object Length -Sum).Sum
        Remove-Item "$crashDir\*" -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "    Cleaned: $(Format-Size $size)"
    }

    # Pip cache
    Write-Host "  Cleaning pip cache..."
    pip cache purge 2>$null
    Write-Host "    Done"

    Write-Host ""
    Write-Host "  Additional manual cleanup commands:" -ForegroundColor Yellow
    Write-Host '    # Windows Update cleanup (run as Admin):'
    Write-Host '    DISM /Online /Cleanup-Image /StartComponentCleanup'
    Write-Host '    DISM /Online /Cleanup-Image /StartComponentCleanup /ResetBase'
    Write-Host ''
    Write-Host '    # Disk Cleanup utility:'
    Write-Host '    cleanmgr /d C'
    Write-Host ''
    Write-Host '    # Empty Recycle Bin:'
    Write-Host '    Clear-RecycleBin -DriveLetter C -Force'
    Write-Host ''
    Write-Host '    # Remove old Ollama models (list first, then remove):'
    Write-Host '    ollama list'
    Write-Host '    ollama rm <model_name>'

} else {
    Write-Host "$divider" -ForegroundColor Green
    Write-Host " REPORT ONLY - No files deleted" -ForegroundColor Green
    Write-Host " Re-run with -Cleanup to delete safe temp/cache files" -ForegroundColor Green
    Write-Host " Example: .\disk-analysis.ps1 -Cleanup" -ForegroundColor Green
    Write-Host "$divider" -ForegroundColor Green
}

###########################################################################
# 10. SUMMARY & RECOMMENDATIONS
###########################################################################
Write-Host ""
Write-Host "[RECOMMENDATIONS]" -ForegroundColor Cyan
Write-Host ""
Write-Host "  1. QUICK WINS (safe, immediate):" -ForegroundColor White
Write-Host "     - Run this script with -Cleanup flag"
Write-Host "     - Run Disk Cleanup: cleanmgr /d C"
Write-Host "     - DISM cleanup: DISM /Online /Cleanup-Image /StartComponentCleanup"
Write-Host "     - Clear Recycle Bin"
Write-Host ""
Write-Host "  2. OLLAMA MODEL PRUNING:" -ForegroundColor White
Write-Host "     - 102 models is a LOT. Review with: ollama list"
Write-Host "     - Remove unused models: ollama rm <name>"
Write-Host "     - Keep only actively used models"
Write-Host "     - Ollama ALREADY deduplicates shared layers (no extra dedup needed)"
Write-Host ""
Write-Host "  3. NTFS COMPRESSION (free space, zero risk for code):" -ForegroundColor White
Write-Host '     - compact /c /s /i "C:\NovaX"  (code compresses 40-60%)'
Write-Host '     - compact /c /s /i "$env:USERPROFILE\.cargo"  (Rust cache)'
Write-Host "     - Do NOT compress: Ollama blobs, databases, already-compressed files"
Write-Host ""
Write-Host "  4. MOVE LARGE DATA (if second drive available):" -ForegroundColor White
Write-Host "     - Set OLLAMA_MODELS env var to move models to D:\"
Write-Host "     - Symlink large folders to another drive"
Write-Host ""
