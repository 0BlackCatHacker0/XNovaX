#Requires -Version 5.1
<#
.SYNOPSIS
    NovaX System Benchmark Suite v1.0.0
.DESCRIPTION
    Comprehensive system benchmark: CPU, Memory, Disk, Network, AI inference.
    Outputs JSON results to C:\NovaX\data\benchmark_results.json and compares
    against previous runs to show percentage improvement.
.NOTES
    Run as Administrator for most accurate disk benchmarks.
#>

param(
    [string]$ResultsPath = "C:\NovaX\data\benchmark_results.json",
    [string]$TempFile    = "C:\NovaX\data\_bench_temp.bin",
    [int]$DiskTestSizeMB = 1024,
    [int]$MemTestSizeMB  = 1024,
    [int]$PrimeLimit     = 1000000,
    [int]$NetPingCount   = 1000,
    [string]$OllamaModel = "qwen2.5-coder:1.5b",
    [switch]$SkipNetwork,
    [switch]$SkipAI,
    [switch]$SkipDisk
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

# ─────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────
function Write-Banner([string]$Text) {
    $bar = "═" * 60
    Write-Host ""
    Write-Host "╔$bar╗" -ForegroundColor Cyan
    Write-Host ("║ {0,-58} ║" -f $Text) -ForegroundColor Cyan
    Write-Host "╚$bar╝" -ForegroundColor Cyan
}

function Write-Metric([string]$Label, [string]$Value, [string]$Unit = "") {
    $display = if ($Unit) { "$Value $Unit" } else { $Value }
    Write-Host ("  {0,-40} {1}" -f $Label, $display) -ForegroundColor White
}

function Write-Comparison([string]$Label, [double]$Current, [double]$Previous, [string]$Unit, [bool]$LowerIsBetter = $true) {
    if ($Previous -eq 0) { Write-Metric $Label "$([math]::Round($Current,2))" $Unit; return }
    $pct = (($Current - $Previous) / [math]::Abs($Previous)) * 100
    $arrow = if (($LowerIsBetter -and $pct -lt 0) -or (-not $LowerIsBetter -and $pct -gt 0)) { "▲" } elseif ($pct -eq 0) { "─" } else { "▼" }
    $color = if ($arrow -eq "▲") { "Green" } elseif ($arrow -eq "▼") { "Red" } else { "Yellow" }
    $pctStr = "{0:+0.0;-0.0;0.0}%" -f $pct
    Write-Host ("  {0,-34} {1,8} {2}  {3} {4}" -f $Label, [math]::Round($Current,2), $Unit, $arrow, $pctStr) -ForegroundColor $color
}

function Measure-Block([scriptblock]$Block) {
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    & $Block
    $sw.Stop()
    return $sw.Elapsed.TotalSeconds
}

# ─────────────────────────────────────────────
# 1. SYSTEM INFO
# ─────────────────────────────────────────────
Write-Banner "SYSTEM INFORMATION"

$cpuWmi   = Get-CimInstance Win32_Processor | Select-Object -First 1
$gpuWmi   = Get-CimInstance Win32_VideoController | Where-Object { $_.AdapterRAM -gt 0 } | Select-Object -First 1
$memWmi   = Get-CimInstance Win32_PhysicalMemory
$diskWmi  = Get-CimInstance Win32_DiskDrive | Select-Object -First 1
$volWmi   = Get-CimInstance Win32_LogicalDisk | Where-Object { $_.DeviceID -eq "C:" }
$osWmi    = Get-CimInstance Win32_OperatingSystem

$totalRAM     = [math]::Round(($memWmi | Measure-Object -Property Capacity -Sum).Sum / 1GB, 1)
$availRAM     = [math]::Round($osWmi.FreePhysicalMemory / 1MB, 1)
$memSpeed     = ($memWmi | Select-Object -First 1).Speed
$memChannels  = ($memWmi | Measure-Object).Count
$diskSizeGB   = [math]::Round($diskWmi.Size / 1GB, 1)
$diskFreeGB   = [math]::Round($volWmi.FreeSpace / 1GB, 1)
$gpuVRAM_MB   = if ($gpuWmi.AdapterRAM) { [math]::Round($gpuWmi.AdapterRAM / 1MB, 0) } else { 0 }

# Try to get GPU driver version from nvidia-smi if available
$nvidiaInfo = $null
try {
    $nvOut = & nvidia-smi --query-gpu=gpu_name,memory.total,driver_version,clocks.gr -i 0 --format=csv,noheader,nounits 2>$null
    if ($nvOut) {
        $parts = $nvOut -split ",\s*"
        $nvidiaInfo = @{
            Name    = $parts[0]
            VRAM_MB = [int]$parts[1]
            Driver  = $parts[2]
            ClockMHz = [int]$parts[3]
        }
    }
} catch {}

$sysInfo = [ordered]@{
    cpu_model       = $cpuWmi.Name.Trim()
    cpu_cores       = [int]$cpuWmi.NumberOfCores
    cpu_threads     = [int]$cpuWmi.NumberOfLogicalProcessors
    cpu_clock_mhz   = [int]$cpuWmi.MaxClockSpeed
    gpu_model       = if ($nvidiaInfo) { $nvidiaInfo.Name } else { $gpuWmi.Name }
    gpu_vram_mb     = if ($nvidiaInfo) { $nvidiaInfo.VRAM_MB } else { $gpuVRAM_MB }
    gpu_driver      = if ($nvidiaInfo) { $nvidiaInfo.Driver } else { $gpuWmi.DriverVersion }
    gpu_clock_mhz   = if ($nvidiaInfo) { $nvidiaInfo.ClockMHz } else { 0 }
    ram_total_gb    = $totalRAM
    ram_available_gb = $availRAM
    ram_speed_mhz   = $memSpeed
    ram_channels    = $memChannels
    disk_model      = $diskWmi.Model
    disk_size_gb    = $diskSizeGB
    disk_free_gb    = $diskFreeGB
    disk_filesystem = $volWmi.FileSystem
    os_version      = $osWmi.Caption
    os_build        = $osWmi.BuildNumber
}

foreach ($k in $sysInfo.Keys) {
    Write-Metric ($k -replace "_", " ") "$($sysInfo[$k])"
}

# ─────────────────────────────────────────────
# 2. CPU BENCHMARKS
# ─────────────────────────────────────────────
Write-Banner "CPU BENCHMARK"

# Sieve of Eratosthenes - single core
Write-Host "  [*] Single-core: primes up to $PrimeLimit ..." -ForegroundColor DarkGray
$singleCoreSec = Measure-Block {
    $sieve = [System.Collections.BitArray]::new($PrimeLimit + 1, $true)
    $sieve[0] = $false; $sieve[1] = $false
    $sqrtN = [int][math]::Sqrt($PrimeLimit)
    for ($i = 2; $i -le $sqrtN; $i++) {
        if ($sieve[$i]) {
            for ($j = $i * $i; $j -le $PrimeLimit; $j += $i) {
                $sieve[$j] = $false
            }
        }
    }
    $script:primeCount = 0
    for ($i = 2; $i -le $PrimeLimit; $i++) { if ($sieve[$i]) { $script:primeCount++ } }
}
Write-Metric "Single-core primes found" $script:primeCount
Write-Metric "Single-core time" ([math]::Round($singleCoreSec, 3)) "sec"

# Multi-core - parallel segmented sieve using Tasks
Write-Host "  [*] Multi-core: parallel prime segmented sieve ..." -ForegroundColor DarkGray
$threadCount = [Environment]::ProcessorCount
$multiCoreSec = Measure-Block {
    $segSize = [math]::Ceiling($PrimeLimit / $threadCount)
    $tasks = [System.Collections.Generic.List[System.Threading.Tasks.Task[int]]]::new()

    for ($t = 0; $t -lt $threadCount; $t++) {
        $lo = $t * $segSize + 1
        $hi = [math]::Min(($t + 1) * $segSize, $PrimeLimit)
        if ($lo -lt 2) { $lo = 2 }
        $taskLo = $lo; $taskHi = $hi; $taskLimit = $PrimeLimit
        $task = [System.Threading.Tasks.Task]::Factory.StartNew([Func[int]]{
            $count = 0
            for ($n = $taskLo; $n -le $taskHi; $n++) {
                if ($n -lt 2) { continue }
                if ($n -eq 2 -or $n -eq 3) { $count++; continue }
                if ($n % 2 -eq 0 -or $n % 3 -eq 0) { continue }
                $isPrime = $true
                $d = 5
                while ($d * $d -le $n) {
                    if ($n % $d -eq 0 -or $n % ($d + 2) -eq 0) { $isPrime = $false; break }
                    $d += 6
                }
                if ($isPrime) { $count++ }
            }
            return $count
        })
        $tasks.Add($task)
    }
    [System.Threading.Tasks.Task]::WaitAll($tasks.ToArray())
    $script:multiPrimeCount = 0
    foreach ($task in $tasks) { $script:multiPrimeCount += $task.Result }
}
Write-Metric "Multi-core threads used" $threadCount
Write-Metric "Multi-core primes found" $script:multiPrimeCount
Write-Metric "Multi-core time" ([math]::Round($multiCoreSec, 3)) "sec"
$speedup = if ($multiCoreSec -gt 0) { [math]::Round($singleCoreSec / $multiCoreSec, 2) } else { 0 }
Write-Metric "Parallel speedup" "${speedup}x"

# ─────────────────────────────────────────────
# 3. MEMORY BENCHMARKS
# ─────────────────────────────────────────────
Write-Banner "MEMORY BENCHMARK"

$memElements = ($MemTestSizeMB * 1MB) / 4  # int32 = 4 bytes

# Sequential read
Write-Host "  [*] Allocating ${MemTestSizeMB}MB array ..." -ForegroundColor DarkGray
$memAllocSec = Measure-Block {
    $script:memArray = [int[]]::new($memElements)
}
Write-Metric "Allocation time (${MemTestSizeMB}MB)" ([math]::Round($memAllocSec, 3)) "sec"

Write-Host "  [*] Sequential read ..." -ForegroundColor DarkGray
$seqReadSec = Measure-Block {
    $sum = [long]0
    $len = $script:memArray.Length
    for ($i = 0; $i -lt $len; $i += 64) {
        $sum += $script:memArray[$i]
    }
}
$seqBandwidth = [math]::Round($MemTestSizeMB / $seqReadSec, 0)
Write-Metric "Sequential read time" ([math]::Round($seqReadSec, 3)) "sec"
Write-Metric "Sequential read bandwidth" $seqBandwidth "MB/s"

# Random read
Write-Host "  [*] Random read ..." -ForegroundColor DarkGray
$rng = [System.Random]::new(42)
$randomIndices = [int[]]::new(1000000)
for ($i = 0; $i -lt $randomIndices.Length; $i++) {
    $randomIndices[$i] = $rng.Next(0, $memElements)
}
$randReadSec = Measure-Block {
    $sum = [long]0
    for ($i = 0; $i -lt $randomIndices.Length; $i++) {
        $sum += $script:memArray[$randomIndices[$i]]
    }
}
Write-Metric "Random read time (1M accesses)" ([math]::Round($randReadSec, 3)) "sec"

# Allocation/deallocation speed
Write-Host "  [*] Alloc/free cycles ..." -ForegroundColor DarkGray
$allocCycles = 20
$allocSec = Measure-Block {
    for ($c = 0; $c -lt $allocCycles; $c++) {
        $tmp = [byte[]]::new(100MB)
        $tmp = $null
    }
}
$allocRate = [math]::Round(($allocCycles * 100) / $allocSec, 0)
Write-Metric "Alloc/free rate (100MB blocks)" $allocRate "MB/s"

$script:memArray = $null
[GC]::Collect()

# ─────────────────────────────────────────────
# 4. DISK BENCHMARKS
# ─────────────────────────────────────────────
$diskResults = [ordered]@{}
if (-not $SkipDisk) {
    Write-Banner "DISK BENCHMARK"

    $blockSize = 1MB
    $blocks = ($DiskTestSizeMB * 1MB) / $blockSize
    $writeBuffer = [byte[]]::new($blockSize)
    [System.Random]::new(0).NextBytes($writeBuffer)

    # Sequential write
    Write-Host "  [*] Sequential write ${DiskTestSizeMB}MB ..." -ForegroundColor DarkGray
    $seqWriteSec = Measure-Block {
        $fs = [System.IO.FileStream]::new($TempFile, [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None, $blockSize, [System.IO.FileOptions]::WriteThrough)
        for ($i = 0; $i -lt $blocks; $i++) {
            $fs.Write($writeBuffer, 0, $blockSize)
        }
        $fs.Flush($true)
        $fs.Close()
    }
    $writeBW = [math]::Round($DiskTestSizeMB / $seqWriteSec, 0)
    Write-Metric "Sequential write" $writeBW "MB/s"

    # Sequential read
    Write-Host "  [*] Sequential read ${DiskTestSizeMB}MB ..." -ForegroundColor DarkGray
    $readBuffer = [byte[]]::new($blockSize)
    $seqReadDiskSec = Measure-Block {
        $fs = [System.IO.FileStream]::new($TempFile, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::None, $blockSize, [System.IO.FileOptions]::SequentialScan)
        while ($fs.Read($readBuffer, 0, $blockSize) -gt 0) { }
        $fs.Close()
    }
    $readBW = [math]::Round($DiskTestSizeMB / $seqReadDiskSec, 0)
    Write-Metric "Sequential read" $readBW "MB/s"

    # Random 4K reads
    Write-Host "  [*] Random 4K reads (1000) ..." -ForegroundColor DarkGray
    $fileLen = (Get-Item $TempFile).Length
    $rng4k = [System.Random]::new(42)
    $buf4k = [byte[]]::new(4096)
    $random4kSec = Measure-Block {
        $fs = [System.IO.FileStream]::new($TempFile, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::Read, 4096, [System.IO.FileOptions]::RandomAccess)
        for ($i = 0; $i -lt 1000; $i++) {
            $pos = [long]($rng4k.NextDouble() * ($fileLen - 4096))
            $fs.Seek($pos, [System.IO.SeekOrigin]::Begin) | Out-Null
            $fs.Read($buf4k, 0, 4096) | Out-Null
        }
        $fs.Close()
    }
    $iops = [math]::Round(1000 / $random4kSec, 0)
    Write-Metric "Random 4K read IOPS" $iops "IOPS"
    Write-Metric "Random 4K read time" ([math]::Round($random4kSec, 3)) "sec"

    # Cleanup
    if (Test-Path $TempFile) { Remove-Item $TempFile -Force }

    $diskResults = [ordered]@{
        seq_write_mbps   = $writeBW
        seq_read_mbps    = $readBW
        random_4k_iops   = $iops
        seq_write_sec    = [math]::Round($seqWriteSec, 3)
        seq_read_sec     = [math]::Round($seqReadDiskSec, 3)
        random_4k_sec    = [math]::Round($random4kSec, 3)
    }
} else {
    Write-Host "`n  [SKIP] Disk benchmark skipped" -ForegroundColor Yellow
}

# ─────────────────────────────────────────────
# 5. NETWORK BENCHMARKS
# ─────────────────────────────────────────────
$netResults = [ordered]@{}
if (-not $SkipNetwork) {
    Write-Banner "NETWORK BENCHMARK"

    $healthUrl = "http://localhost:9999/health"
    # Quick check if orchestrator is up
    $orchUp = $false
    try {
        $r = Invoke-WebRequest -Uri $healthUrl -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
        if ($r.StatusCode -eq 200) { $orchUp = $true }
    } catch {}

    if ($orchUp) {
        # Localhost latency - sequential pings
        Write-Host "  [*] Localhost latency ($NetPingCount requests) ..." -ForegroundColor DarkGray
        $latencies = [System.Collections.Generic.List[double]]::new()
        $netTotalSec = Measure-Block {
            for ($i = 0; $i -lt $NetPingCount; $i++) {
                $sw = [System.Diagnostics.Stopwatch]::StartNew()
                try {
                    Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop | Out-Null
                } catch {}
                $sw.Stop()
                $latencies.Add($sw.Elapsed.TotalMilliseconds)
            }
        }
        $latArr = $latencies.ToArray()
        [Array]::Sort($latArr)
        $avgLatency = [math]::Round(($latArr | Measure-Object -Average).Average, 2)
        $p50 = [math]::Round($latArr[[math]::Floor($latArr.Length * 0.5)], 2)
        $p95 = [math]::Round($latArr[[math]::Floor($latArr.Length * 0.95)], 2)
        $p99 = [math]::Round($latArr[[math]::Floor($latArr.Length * 0.99)], 2)
        $rps = [math]::Round($NetPingCount / $netTotalSec, 0)

        Write-Metric "Avg latency" $avgLatency "ms"
        Write-Metric "P50 latency" $p50 "ms"
        Write-Metric "P95 latency" $p95 "ms"
        Write-Metric "P99 latency" $p99 "ms"
        Write-Metric "Requests/sec (sequential)" $rps "rps"

        # Concurrent throughput - 10 parallel tasks
        Write-Host "  [*] Concurrent throughput (10 parallel, 100 each) ..." -ForegroundColor DarkGray
        $concurrentSec = Measure-Block {
            $tasks = @()
            for ($w = 0; $w -lt 10; $w++) {
                $tasks += [System.Threading.Tasks.Task]::Factory.StartNew([Action]{
                    for ($r = 0; $r -lt 100; $r++) {
                        try {
                            $wc = [System.Net.WebClient]::new()
                            $wc.DownloadString("http://localhost:9999/health") | Out-Null
                            $wc.Dispose()
                        } catch {}
                    }
                })
            }
            [System.Threading.Tasks.Task]::WaitAll($tasks)
        }
        $concurrentRps = [math]::Round(1000 / $concurrentSec, 0)
        Write-Metric "Concurrent requests/sec" $concurrentRps "rps"

        $netResults = [ordered]@{
            avg_latency_ms    = $avgLatency
            p50_latency_ms    = $p50
            p95_latency_ms    = $p95
            p99_latency_ms    = $p99
            sequential_rps    = $rps
            concurrent_rps    = $concurrentRps
        }
    } else {
        Write-Host "  [!] Orchestrator not responding at $healthUrl - skipping" -ForegroundColor Yellow
    }
} else {
    Write-Host "`n  [SKIP] Network benchmark skipped" -ForegroundColor Yellow
}

# ─────────────────────────────────────────────
# 6. AI-SPECIFIC BENCHMARKS
# ─────────────────────────────────────────────
$aiResults = [ordered]@{}
if (-not $SkipAI) {
    Write-Banner "AI BENCHMARK"

    $ollamaUp = $false
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
        if ($r.StatusCode -eq 200) { $ollamaUp = $true }
    } catch {}

    if ($ollamaUp) {
        # Check if model is available
        $modelAvailable = $false
        try {
            $tags = (Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -UseBasicParsing).Content | ConvertFrom-Json
            foreach ($m in $tags.models) {
                if ($m.name -like "$OllamaModel*") { $modelAvailable = $true; break }
            }
        } catch {}

        if ($modelAvailable) {
            $prompt = '{"model":"' + $OllamaModel + '","prompt":"Return only the number 42.","stream":false}'

            # Cold load (first inference includes model load)
            Write-Host "  [*] Ollama cold inference ($OllamaModel) ..." -ForegroundColor DarkGray
            $coldSec = Measure-Block {
                try {
                    $script:aiResp = Invoke-WebRequest -Uri "http://localhost:11434/api/generate" -Method POST -Body $prompt -ContentType "application/json" -TimeoutSec 120 -UseBasicParsing
                } catch { $script:aiResp = $null }
            }
            $coldData = $null
            if ($script:aiResp) {
                $coldData = $script:aiResp.Content | ConvertFrom-Json
            }
            $loadDurationMs = if ($coldData -and $coldData.load_duration) { [math]::Round($coldData.load_duration / 1e6, 0) } else { 0 }
            $evalDurationMs = if ($coldData -and $coldData.eval_duration) { [math]::Round($coldData.eval_duration / 1e6, 0) } else { 0 }
            $evalCount      = if ($coldData -and $coldData.eval_count) { $coldData.eval_count } else { 0 }
            $tokPerSec      = if ($evalDurationMs -gt 0 -and $evalCount -gt 0) { [math]::Round($evalCount / ($evalDurationMs / 1000), 1) } else { 0 }

            Write-Metric "Cold inference total" ([math]::Round($coldSec, 3)) "sec"
            Write-Metric "Model load time" $loadDurationMs "ms"
            Write-Metric "Eval duration" $evalDurationMs "ms"
            Write-Metric "Tokens generated" $evalCount
            Write-Metric "Tokens/sec" $tokPerSec "tok/s"

            # Warm inference (model already loaded)
            Write-Host "  [*] Ollama warm inference ..." -ForegroundColor DarkGray
            $warmSec = Measure-Block {
                try {
                    $script:aiResp2 = Invoke-WebRequest -Uri "http://localhost:11434/api/generate" -Method POST -Body $prompt -ContentType "application/json" -TimeoutSec 120 -UseBasicParsing
                } catch { $script:aiResp2 = $null }
            }
            $warmData = $null
            if ($script:aiResp2) { $warmData = $script:aiResp2.Content | ConvertFrom-Json }
            $warmEvalMs  = if ($warmData -and $warmData.eval_duration) { [math]::Round($warmData.eval_duration / 1e6, 0) } else { 0 }
            $warmTokSec  = if ($warmData -and $warmData.eval_count -and $warmEvalMs -gt 0) { [math]::Round($warmData.eval_count / ($warmEvalMs / 1000), 1) } else { 0 }

            Write-Metric "Warm inference total" ([math]::Round($warmSec, 3)) "sec"
            Write-Metric "Warm tokens/sec" $warmTokSec "tok/s"

            $aiResults = [ordered]@{
                model             = $OllamaModel
                cold_total_sec    = [math]::Round($coldSec, 3)
                model_load_ms     = $loadDurationMs
                eval_duration_ms  = $evalDurationMs
                tokens_generated  = $evalCount
                tokens_per_sec    = $tokPerSec
                warm_total_sec    = [math]::Round($warmSec, 3)
                warm_tokens_per_sec = $warmTokSec
            }
        } else {
            Write-Host "  [!] Model $OllamaModel not found in Ollama - skipping" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  [!] Ollama not responding at localhost:11434 - skipping" -ForegroundColor Yellow
    }
} else {
    Write-Host "`n  [SKIP] AI benchmark skipped" -ForegroundColor Yellow
}

# ─────────────────────────────────────────────
# 7. COMPILE RESULTS & SAVE JSON
# ─────────────────────────────────────────────
Write-Banner "RESULTS SUMMARY"

$timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
$results = [ordered]@{
    timestamp   = $timestamp
    version     = "1.0.0"
    system      = $sysInfo
    cpu         = [ordered]@{
        prime_limit          = $PrimeLimit
        single_core_sec      = [math]::Round($singleCoreSec, 3)
        multi_core_sec       = [math]::Round($multiCoreSec, 3)
        threads_used         = $threadCount
        parallel_speedup     = $speedup
        primes_found         = $script:primeCount
    }
    memory      = [ordered]@{
        test_size_mb         = $MemTestSizeMB
        alloc_sec            = [math]::Round($memAllocSec, 3)
        seq_read_sec         = [math]::Round($seqReadSec, 3)
        seq_read_bandwidth   = $seqBandwidth
        random_read_sec      = [math]::Round($randReadSec, 3)
        alloc_free_rate_mbps = $allocRate
    }
    disk        = $diskResults
    network     = $netResults
    ai          = $aiResults
}

# Load previous results for comparison
$previous = $null
if (Test-Path $ResultsPath) {
    try {
        $prevJson = Get-Content $ResultsPath -Raw | ConvertFrom-Json
        # Support both single result and array of results
        if ($prevJson -is [array]) {
            $previous = $prevJson[-1]
        } else {
            $previous = $prevJson
        }
    } catch {}
}

# Save results (append to history array)
$history = @()
if (Test-Path $ResultsPath) {
    try {
        $existing = Get-Content $ResultsPath -Raw | ConvertFrom-Json
        if ($existing -is [array]) {
            $history = @($existing)
        } else {
            $history = @($existing)
        }
    } catch {}
}
$history += $results
$history | ConvertTo-Json -Depth 10 | Set-Content $ResultsPath -Encoding UTF8
Write-Host "  Results saved to: $ResultsPath" -ForegroundColor Green

# ─────────────────────────────────────────────
# COMPARISON TABLE
# ─────────────────────────────────────────────
if ($previous) {
    Write-Banner "COMPARISON vs PREVIOUS RUN"
    Write-Host "  Previous run: $($previous.timestamp)" -ForegroundColor DarkGray
    Write-Host "  Current run:  $timestamp" -ForegroundColor DarkGray
    Write-Host ""

    Write-Host "  --- CPU ---" -ForegroundColor Yellow
    Write-Comparison "Single-core (sec)" $results.cpu.single_core_sec $previous.cpu.single_core_sec "sec" $true
    Write-Comparison "Multi-core (sec)" $results.cpu.multi_core_sec $previous.cpu.multi_core_sec "sec" $true
    Write-Comparison "Parallel speedup" $results.cpu.parallel_speedup $previous.cpu.parallel_speedup "x" $false

    Write-Host "  --- Memory ---" -ForegroundColor Yellow
    Write-Comparison "Alloc time (sec)" $results.memory.alloc_sec $previous.memory.alloc_sec "sec" $true
    Write-Comparison "Seq read (sec)" $results.memory.seq_read_sec $previous.memory.seq_read_sec "sec" $true
    Write-Comparison "Seq bandwidth" $results.memory.seq_read_bandwidth $previous.memory.seq_read_bandwidth "MB/s" $false
    Write-Comparison "Random read (sec)" $results.memory.random_read_sec $previous.memory.random_read_sec "sec" $true
    Write-Comparison "Alloc/free rate" $results.memory.alloc_free_rate_mbps $previous.memory.alloc_free_rate_mbps "MB/s" $false

    if ($results.disk.Count -gt 0 -and $previous.disk) {
        Write-Host "  --- Disk ---" -ForegroundColor Yellow
        Write-Comparison "Seq write" $results.disk.seq_write_mbps $previous.disk.seq_write_mbps "MB/s" $false
        Write-Comparison "Seq read" $results.disk.seq_read_mbps $previous.disk.seq_read_mbps "MB/s" $false
        Write-Comparison "Random 4K IOPS" $results.disk.random_4k_iops $previous.disk.random_4k_iops "IOPS" $false
    }

    if ($results.network.Count -gt 0 -and $previous.network) {
        Write-Host "  --- Network ---" -ForegroundColor Yellow
        Write-Comparison "Avg latency" $results.network.avg_latency_ms $previous.network.avg_latency_ms "ms" $true
        Write-Comparison "P99 latency" $results.network.p99_latency_ms $previous.network.p99_latency_ms "ms" $true
        Write-Comparison "Sequential RPS" $results.network.sequential_rps $previous.network.sequential_rps "rps" $false
        Write-Comparison "Concurrent RPS" $results.network.concurrent_rps $previous.network.concurrent_rps "rps" $false
    }

    if ($results.ai.Count -gt 0 -and $previous.ai) {
        Write-Host "  --- AI ---" -ForegroundColor Yellow
        Write-Comparison "Cold inference" $results.ai.cold_total_sec $previous.ai.cold_total_sec "sec" $true
        Write-Comparison "Model load" $results.ai.model_load_ms $previous.ai.model_load_ms "ms" $true
        Write-Comparison "Tokens/sec" $results.ai.tokens_per_sec $previous.ai.tokens_per_sec "tok/s" $false
        Write-Comparison "Warm tok/sec" $results.ai.warm_tokens_per_sec $previous.ai.warm_tokens_per_sec "tok/s" $false
    }

    # Overall score: geometric mean of key ratios (lower time = better)
    $ratios = @()
    if ($previous.cpu.single_core_sec -gt 0) { $ratios += $previous.cpu.single_core_sec / [math]::Max($results.cpu.single_core_sec, 0.001) }
    if ($previous.cpu.multi_core_sec -gt 0) { $ratios += $previous.cpu.multi_core_sec / [math]::Max($results.cpu.multi_core_sec, 0.001) }
    if ($previous.memory.seq_read_sec -gt 0) { $ratios += $previous.memory.seq_read_sec / [math]::Max($results.memory.seq_read_sec, 0.001) }
    if ($previous.disk -and $previous.disk.seq_write_mbps -gt 0 -and $results.disk.seq_write_mbps) {
        $ratios += $results.disk.seq_write_mbps / $previous.disk.seq_write_mbps
    }

    if ($ratios.Count -gt 0) {
        $product = 1.0
        foreach ($r in $ratios) { $product *= $r }
        $geoMean = [math]::Pow($product, 1.0 / $ratios.Count)
        $overallPct = [math]::Round(($geoMean - 1) * 100, 1)
        Write-Host ""
        $color = if ($overallPct -ge 0) { "Green" } else { "Red" }
        $sign = if ($overallPct -ge 0) { "+" } else { "" }
        Write-Host "  OVERALL: ${sign}${overallPct}% vs previous run" -ForegroundColor $color
    }
} else {
    Write-Host "  No previous results found - this is the baseline run." -ForegroundColor Yellow
}

Write-Banner "BENCHMARK COMPLETE"
Write-Host "  Timestamp: $timestamp" -ForegroundColor White
Write-Host "  Results:   $ResultsPath" -ForegroundColor White
Write-Host ""
