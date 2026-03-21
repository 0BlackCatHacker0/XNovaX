<#
.SYNOPSIS
    NovaX System Performance Benchmark
.DESCRIPTION
    Measures CPU, Memory, Disk, GPU, Network, and NovaX Service performance.
    Supports --before and --after modes for comparing pre/post optimization.
.PARAMETER Mode
    "before" or "after" — saves results tagged for comparison.
.PARAMETER Compare
    If set, loads both before/after results and displays comparison.
.EXAMPLE
    .\novax_benchmark.ps1 -Mode before
    .\novax_benchmark.ps1 -Mode after
    .\novax_benchmark.ps1 -Compare
#>

param(
    [ValidateSet("before", "after", "")]
    [string]$Mode = "",
    [switch]$Compare
)

$ErrorActionPreference = "Continue"
$BenchmarkDir = "C:\NovaX\benchmark_temp"
$ResultsFile = "C:\NovaX\benchmark_results.json"
$BeforeFile = "C:\NovaX\benchmark_before.json"
$AfterFile = "C:\NovaX\benchmark_after.json"

# ─────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────

function Write-Banner {
    param([string]$Text)
    $bar = "─" * 60
    Write-Host ""
    Write-Host $bar -ForegroundColor DarkCyan
    Write-Host "  $Text" -ForegroundColor Cyan
    Write-Host $bar -ForegroundColor DarkCyan
}

function Write-Metric {
    param([string]$Label, [string]$Value, [string]$Unit = "")
    $display = if ($Unit) { "$Value $Unit" } else { $Value }
    Write-Host ("  {0,-40} {1,15}" -f $Label, $display) -ForegroundColor White
}

function Measure-Block {
    param([scriptblock]$Block)
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $result = & $Block
    $sw.Stop()
    return @{ Elapsed = $sw.Elapsed; ElapsedMs = $sw.Elapsed.TotalMilliseconds; Result = $result }
}

# ─────────────────────────────────────────────
# 1. CPU BENCHMARK
# ─────────────────────────────────────────────

function Test-CPU {
    Write-Banner "CPU BENCHMARK"

    # Single-thread: count primes up to 1,000,000
    Write-Host "  Running single-thread prime sieve to 1,000,000..." -ForegroundColor DarkGray
    $stResult = Measure-Block {
        $limit = 1000000
        $sieve = [System.Collections.BitArray]::new($limit + 1, $true)
        $sieve[0] = $false; $sieve[1] = $false
        for ($i = 2; $i * $i -le $limit; $i++) {
            if ($sieve[$i]) {
                for ($j = $i * $i; $j -le $limit; $j += $i) {
                    $sieve[$j] = $false
                }
            }
        }
        $count = 0
        for ($i = 2; $i -le $limit; $i++) { if ($sieve[$i]) { $count++ } }
        $count
    }
    $singleTime = $stResult.ElapsedMs
    $primeCount = $stResult.Result
    Write-Metric "Primes found" $primeCount
    Write-Metric "Single-thread time" ("{0:N1}" -f $singleTime) "ms"

    # Multi-threaded: split range across jobs
    Write-Host "  Running multi-thread prime count (4 jobs)..." -ForegroundColor DarkGray
    $threadCount = 4
    $mtResult = Measure-Block {
        $rangeSize = 250000
        $jobs = @()
        for ($t = 0; $t -lt $threadCount; $t++) {
            $lo = $t * $rangeSize + 1
            $hi = ($t + 1) * $rangeSize
            if ($lo -lt 2) { $lo = 2 }
            $jobs += Start-Job -ScriptBlock {
                param($lo, $hi)
                $count = 0
                for ($n = $lo; $n -le $hi; $n++) {
                    $isPrime = $true
                    if ($n -lt 2) { $isPrime = $false }
                    else {
                        $sqr = [Math]::Sqrt($n)
                        for ($d = 2; $d -le $sqr; $d++) {
                            if ($n % $d -eq 0) { $isPrime = $false; break }
                        }
                    }
                    if ($isPrime) { $count++ }
                }
                $count
            } -ArgumentList $lo, $hi
        }
        $jobs | Wait-Job -Timeout 120 | Out-Null
        $total = 0
        foreach ($j in $jobs) {
            $total += (Receive-Job $j)
            Remove-Job $j -Force
        }
        $total
    }
    $multiTime = $mtResult.ElapsedMs
    $scalingFactor = if ($multiTime -gt 0) { [Math]::Round($singleTime / $multiTime, 2) } else { 0 }
    Write-Metric "Multi-thread time (4 jobs)" ("{0:N1}" -f $multiTime) "ms"
    Write-Metric "Thread scaling factor" ("{0:N2}x" -f $scalingFactor)

    # Score: baseline ~3000ms single-thread = 50 points, faster = higher
    $cpuScore = [Math]::Min(100, [Math]::Max(0, [int](100 - ($singleTime / 60))))

    return @{
        PrimeCount       = $primeCount
        SingleThreadMs   = [Math]::Round($singleTime, 1)
        MultiThreadMs    = [Math]::Round($multiTime, 1)
        ScalingFactor    = $scalingFactor
        ThreadCount      = $threadCount
        Score            = $cpuScore
    }
}

# ─────────────────────────────────────────────
# 2. MEMORY BENCHMARK
# ─────────────────────────────────────────────

function Test-Memory {
    Write-Banner "MEMORY BENCHMARK"

    $sizeMB = 256
    $elements = $sizeMB * 1024 * 1024 / 4  # int32 = 4 bytes

    # Sequential write
    Write-Host "  Sequential write ${sizeMB}MB..." -ForegroundColor DarkGray
    $writeResult = Measure-Block {
        $arr = [int[]]::new($elements)
        for ($i = 0; $i -lt $elements; $i++) { $arr[$i] = $i }
        $arr
    }
    $writeMBs = [Math]::Round($sizeMB / ($writeResult.ElapsedMs / 1000), 1)
    Write-Metric "Sequential write" ("{0:N1}" -f $writeMBs) "MB/s"

    # Sequential read
    Write-Host "  Sequential read ${sizeMB}MB..." -ForegroundColor DarkGray
    $arr = $writeResult.Result
    $readResult = Measure-Block {
        $sum = [long]0
        for ($i = 0; $i -lt $arr.Length; $i++) { $sum += $arr[$i] }
        $sum
    }
    $readMBs = [Math]::Round($sizeMB / ($readResult.ElapsedMs / 1000), 1)
    Write-Metric "Sequential read" ("{0:N1}" -f $readMBs) "MB/s"

    # Random access (sample 500K random reads)
    Write-Host "  Random access pattern (500K reads)..." -ForegroundColor DarkGray
    $randomResult = Measure-Block {
        $rng = [System.Random]::new(42)
        $sum = [long]0
        $len = $arr.Length
        for ($i = 0; $i -lt 500000; $i++) {
            $idx = $rng.Next($len)
            $sum += $arr[$idx]
        }
        $sum
    }
    $randomLatencyNs = [Math]::Round(($randomResult.ElapsedMs * 1000000) / 500000, 1)
    Write-Metric "Random read latency" ("{0:N1}" -f $randomLatencyNs) "ns/access"

    # Cleanup
    $arr = $null
    [GC]::Collect()

    # Score: 500 MB/s seq write = 50, 2000+ = 100
    $memScore = [Math]::Min(100, [Math]::Max(0, [int]($writeMBs / 20)))

    return @{
        SequentialWriteMBs  = $writeMBs
        SequentialReadMBs   = $readMBs
        RandomLatencyNs     = $randomLatencyNs
        TestSizeMB          = $sizeMB
        Score               = $memScore
    }
}

# ─────────────────────────────────────────────
# 3. DISK BENCHMARK
# ─────────────────────────────────────────────

function Test-Disk {
    Write-Banner "DISK BENCHMARK"

    if (-not (Test-Path $BenchmarkDir)) { New-Item -ItemType Directory -Path $BenchmarkDir -Force | Out-Null }

    $testFile = Join-Path $BenchmarkDir "bench_seq.dat"
    $fileSizeMB = 256
    $blockSize = 1MB

    # Sequential write
    Write-Host "  Sequential write ${fileSizeMB}MB..." -ForegroundColor DarkGray
    $writeResult = Measure-Block {
        $buffer = [byte[]]::new($blockSize)
        $rng = [System.Random]::new(42)
        $rng.NextBytes($buffer)
        $fs = [System.IO.File]::Create($testFile)
        try {
            for ($i = 0; $i -lt $fileSizeMB; $i++) {
                $fs.Write($buffer, 0, $buffer.Length)
            }
            $fs.Flush($true)
        } finally { $fs.Close() }
    }
    $seqWriteMBs = [Math]::Round($fileSizeMB / ($writeResult.ElapsedMs / 1000), 1)
    Write-Metric "Sequential write" ("{0:N1}" -f $seqWriteMBs) "MB/s"

    # Sequential read
    Write-Host "  Sequential read ${fileSizeMB}MB..." -ForegroundColor DarkGray
    $readResult = Measure-Block {
        $buffer = [byte[]]::new($blockSize)
        $fs = [System.IO.File]::OpenRead($testFile)
        try {
            while ($fs.Read($buffer, 0, $buffer.Length) -gt 0) { }
        } finally { $fs.Close() }
    }
    $seqReadMBs = [Math]::Round($fileSizeMB / ($readResult.ElapsedMs / 1000), 1)
    Write-Metric "Sequential read" ("{0:N1}" -f $seqReadMBs) "MB/s"

    # Random 4K read/write
    Write-Host "  Random 4K I/O (1000 ops each)..." -ForegroundColor DarkGray
    $rand4kFile = Join-Path $BenchmarkDir "bench_4k.dat"
    # Create 16MB file for random access
    $randFileSize = 16MB
    $buf4k = [byte[]]::new(4096)
    $rng = [System.Random]::new(42)

    # Prepare file
    $fs = [System.IO.File]::Create($rand4kFile)
    $rng.NextBytes($buf4k)
    for ($i = 0; $i -lt ($randFileSize / 4096); $i++) { $fs.Write($buf4k, 0, 4096) }
    $fs.Close()

    $maxOffset = ($randFileSize / 4096) - 1

    # Random 4K write
    $rw4k = Measure-Block {
        $fs = [System.IO.FileStream]::new($rand4kFile, 'Open', 'ReadWrite', 'None', 4096, 'RandomAccess')
        try {
            for ($i = 0; $i -lt 1000; $i++) {
                $offset = $rng.Next($maxOffset) * 4096
                $fs.Seek($offset, 'Begin') | Out-Null
                $fs.Write($buf4k, 0, 4096)
            }
            $fs.Flush($true)
        } finally { $fs.Close() }
    }
    $rand4kWriteIOPS = [Math]::Round(1000 / ($rw4k.ElapsedMs / 1000), 0)
    Write-Metric "Random 4K write IOPS" $rand4kWriteIOPS

    # Random 4K read
    $rr4k = Measure-Block {
        $fs = [System.IO.FileStream]::new($rand4kFile, 'Open', 'Read', 'Read', 4096, 'RandomAccess')
        try {
            for ($i = 0; $i -lt 1000; $i++) {
                $offset = $rng.Next($maxOffset) * 4096
                $fs.Seek($offset, 'Begin') | Out-Null
                $fs.Read($buf4k, 0, 4096) | Out-Null
            }
        } finally { $fs.Close() }
    }
    $rand4kReadIOPS = [Math]::Round(1000 / ($rr4k.ElapsedMs / 1000), 0)
    Write-Metric "Random 4K read IOPS" $rand4kReadIOPS

    # Cleanup
    Remove-Item $testFile -Force -ErrorAction SilentlyContinue
    Remove-Item $rand4kFile -Force -ErrorAction SilentlyContinue

    # Score: 500 MB/s seq write = 50, 2000+ = 100
    $diskScore = [Math]::Min(100, [Math]::Max(0, [int]($seqWriteMBs / 20)))

    return @{
        SeqWriteMBs     = $seqWriteMBs
        SeqReadMBs      = $seqReadMBs
        Rand4KWriteIOPS = $rand4kWriteIOPS
        Rand4KReadIOPS  = $rand4kReadIOPS
        TestSizeMB      = $fileSizeMB
        Score           = $diskScore
    }
}

# ─────────────────────────────────────────────
# 4. GPU BENCHMARK
# ─────────────────────────────────────────────

function Test-GPU {
    Write-Banner "GPU BENCHMARK"

    $gpuInfo = @{
        Available     = $false
        Name          = "N/A"
        ClockMHz      = 0
        MemUsedMB     = 0
        MemTotalMB    = 0
        UtilPercent   = 0
        TempC         = 0
        OllamaTokPerS = 0
        Score         = 0
    }

    # nvidia-smi query
    try {
        $smiOutput = & nvidia-smi --query-gpu=name,clocks.gr,memory.used,memory.total,utilization.gpu,temperature.gpu --format=csv,noheader,nounits 2>&1
        if ($LASTEXITCODE -eq 0 -and $smiOutput -match ",") {
            $parts = $smiOutput.ToString().Split(",") | ForEach-Object { $_.Trim() }
            $gpuInfo.Available = $true
            $gpuInfo.Name = $parts[0]
            $gpuInfo.ClockMHz = [int]$parts[1]
            $gpuInfo.MemUsedMB = [int]$parts[2]
            $gpuInfo.MemTotalMB = [int]$parts[3]
            $gpuInfo.UtilPercent = [int]$parts[4]
            $gpuInfo.TempC = [int]$parts[5]

            Write-Metric "GPU" $gpuInfo.Name
            Write-Metric "Clock" "$($gpuInfo.ClockMHz)" "MHz"
            Write-Metric "VRAM" "$($gpuInfo.MemUsedMB) / $($gpuInfo.MemTotalMB)" "MB"
            Write-Metric "Utilization" "$($gpuInfo.UtilPercent)" "%"
            Write-Metric "Temperature" "$($gpuInfo.TempC)" "C"
        } else {
            Write-Host "  nvidia-smi not available or no NVIDIA GPU." -ForegroundColor Yellow
        }
    } catch {
        Write-Host "  nvidia-smi failed: $_" -ForegroundColor Yellow
    }

    # Ollama inference benchmark
    Write-Host "  Running Ollama inference benchmark..." -ForegroundColor DarkGray
    try {
        $body = @{
            model  = "llama3.2:latest"
            prompt = "Explain quantum computing in exactly three sentences."
            stream = $false
        } | ConvertTo-Json

        $ollamaResult = Measure-Block {
            $resp = Invoke-RestMethod -Uri "http://localhost:11434/api/generate" -Method POST -Body $body -ContentType "application/json" -TimeoutSec 60
            $resp
        }

        if ($ollamaResult.Result) {
            $r = $ollamaResult.Result
            $evalCount = if ($r.eval_count) { $r.eval_count } else { 0 }
            # eval_duration is in nanoseconds
            $evalDurationSec = if ($r.eval_duration) { $r.eval_duration / 1e9 } else { 0 }
            $tokPerSec = if ($evalDurationSec -gt 0) { [Math]::Round($evalCount / $evalDurationSec, 1) } else { 0 }
            $gpuInfo.OllamaTokPerS = $tokPerSec

            Write-Metric "Ollama eval tokens" $evalCount
            Write-Metric "Ollama eval time" ("{0:N2}" -f $evalDurationSec) "s"
            Write-Metric "Ollama throughput" ("{0:N1}" -f $tokPerSec) "tok/s"
        }
    } catch {
        Write-Host "  Ollama not available: $_" -ForegroundColor Yellow
    }

    # Score: based on tok/s (40 tok/s = 50, 100+ = 100) plus GPU presence bonus
    if ($gpuInfo.Available) {
        $tokScore = [Math]::Min(80, [Math]::Max(0, [int]($gpuInfo.OllamaTokPerS * 0.8)))
        $gpuPresenceBonus = 20
        $gpuInfo.Score = [Math]::Min(100, $tokScore + $gpuPresenceBonus)
    } else {
        $gpuInfo.Score = 5  # CPU-only fallback
    }

    return $gpuInfo
}

# ─────────────────────────────────────────────
# 5. NETWORK BENCHMARK
# ─────────────────────────────────────────────

function Test-Network {
    Write-Banner "NETWORK BENCHMARK"

    $endpoints = @(
        @{ Name = "OpenAI";     URL = "https://api.openai.com/v1/models" },
        @{ Name = "Anthropic";  URL = "https://api.anthropic.com/" },
        @{ Name = "OpenRouter"; URL = "https://openrouter.ai/api/v1/models" }
    )

    $results = @{}
    foreach ($ep in $endpoints) {
        Write-Host "  Pinging $($ep.Name)..." -ForegroundColor DarkGray
        $times = @()
        for ($i = 0; $i -lt 3; $i++) {
            try {
                $sw = [System.Diagnostics.Stopwatch]::StartNew()
                $resp = Invoke-WebRequest -Uri $ep.URL -Method HEAD -TimeoutSec 10 -UseBasicParsing -ErrorAction Stop
                $sw.Stop()
                $times += $sw.Elapsed.TotalMilliseconds
            } catch {
                try {
                    # Some endpoints reject HEAD, try GET
                    $sw = [System.Diagnostics.Stopwatch]::StartNew()
                    Invoke-WebRequest -Uri $ep.URL -Method GET -TimeoutSec 10 -UseBasicParsing -ErrorAction Stop | Out-Null
                    $sw.Stop()
                    $times += $sw.Elapsed.TotalMilliseconds
                } catch {
                    # Even errors give us latency info if we got a response
                    if ($sw.IsRunning) { $sw.Stop() }
                    if ($sw.Elapsed.TotalMilliseconds -gt 0 -and $sw.Elapsed.TotalMilliseconds -lt 10000) {
                        $times += $sw.Elapsed.TotalMilliseconds
                    } else {
                        $times += 9999
                    }
                }
            }
        }
        $avg = [Math]::Round(($times | Measure-Object -Average).Average, 1)
        $min = [Math]::Round(($times | Measure-Object -Minimum).Minimum, 1)
        $results[$ep.Name] = @{ AvgMs = $avg; MinMs = $min }
        Write-Metric "$($ep.Name) avg latency" ("{0:N1}" -f $avg) "ms"
        Write-Metric "$($ep.Name) min latency" ("{0:N1}" -f $min) "ms"
    }

    # Overall average
    $allAvg = ($results.Values | ForEach-Object { $_.AvgMs } | Measure-Object -Average).Average
    $netScore = [Math]::Min(100, [Math]::Max(0, [int](100 - ($allAvg / 20))))

    return @{
        Endpoints = $results
        OverallAvgMs = [Math]::Round($allAvg, 1)
        Score = $netScore
    }
}

# ─────────────────────────────────────────────
# 6. NOVAX SERVICE BENCHMARK
# ─────────────────────────────────────────────

function Test-Services {
    Write-Banner "NOVAX SERVICE BENCHMARK"

    $serviceResults = @{
        OrchestratorMs   = 9999
        HealthyCount     = 0
        TotalCount       = 0
        AvgResponseMs    = 9999
        ServiceDetails   = @()
        Score            = 0
    }

    # Orchestrator response time
    Write-Host "  Checking orchestrator..." -ForegroundColor DarkGray
    try {
        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        $health = Invoke-RestMethod -Uri "http://localhost:9999/api/services/health" -TimeoutSec 15
        $sw.Stop()
        $serviceResults.OrchestratorMs = [Math]::Round($sw.Elapsed.TotalMilliseconds, 1)
        Write-Metric "Orchestrator response" ("{0:N1}" -f $serviceResults.OrchestratorMs) "ms"

        # Parse service health data
        if ($health.services) {
            $services = $health.services
            $totalCount = 0
            $healthyCount = 0
            $responseTimes = @()

            foreach ($svc in $services.PSObject.Properties) {
                $totalCount++
                $s = $svc.Value
                $status = if ($s.status) { $s.status } elseif ($s.state) { $s.state } else { "unknown" }
                if ($status -eq "healthy" -or $status -eq "running" -or $status -eq "+1" -or $status -eq 1) {
                    $healthyCount++
                }
                $respMs = if ($s.response_ms) { $s.response_ms } elseif ($s.latency_ms) { $s.latency_ms } else { $null }
                if ($respMs) { $responseTimes += [double]$respMs }

                $serviceResults.ServiceDetails += @{
                    Name = $svc.Name
                    Status = $status
                    ResponseMs = $respMs
                }
            }

            $serviceResults.TotalCount = $totalCount
            $serviceResults.HealthyCount = $healthyCount
            if ($responseTimes.Count -gt 0) {
                $serviceResults.AvgResponseMs = [Math]::Round(($responseTimes | Measure-Object -Average).Average, 1)
            }
        } elseif ($health.total -or $health.count) {
            $serviceResults.TotalCount = if ($health.total) { $health.total } else { $health.count }
            $serviceResults.HealthyCount = if ($health.healthy) { $health.healthy } else { 0 }
        }

        Write-Metric "Services healthy" "$($serviceResults.HealthyCount) / $($serviceResults.TotalCount)"
        Write-Metric "Avg service response" ("{0:N1}" -f $serviceResults.AvgResponseMs) "ms"

    } catch {
        Write-Host "  Orchestrator not reachable: $_" -ForegroundColor Yellow
    }

    # Score: based on healthy percentage + response time
    $healthPct = if ($serviceResults.TotalCount -gt 0) { $serviceResults.HealthyCount / $serviceResults.TotalCount * 100 } else { 0 }
    $respScore = [Math]::Min(50, [Math]::Max(0, [int](50 - ($serviceResults.AvgResponseMs / 20))))
    $serviceResults.Score = [Math]::Min(100, [Math]::Max(0, [int]($healthPct * 0.5 + $respScore)))

    return $serviceResults
}

# ─────────────────────────────────────────────
# 7. OVERALL SCORE
# ─────────────────────────────────────────────

function Compute-OverallScore {
    param($CPU, $GPU, $RAM, $Disk, $Net, $Svc)

    $weighted = (
        $CPU.Score  * 0.20 +
        $GPU.Score  * 0.30 +
        $RAM.Score  * 0.15 +
        $Disk.Score * 0.15 +
        $Net.Score  * 0.10 +
        $Svc.Score  * 0.10
    )
    return [Math]::Round($weighted, 1)
}

# ─────────────────────────────────────────────
# COMPARISON MODE
# ─────────────────────────────────────────────

function Show-Comparison {
    if (-not (Test-Path $BeforeFile)) {
        Write-Host "ERROR: No 'before' results found at $BeforeFile" -ForegroundColor Red
        Write-Host "  Run: .\novax_benchmark.ps1 -Mode before" -ForegroundColor Yellow
        return
    }
    if (-not (Test-Path $AfterFile)) {
        Write-Host "ERROR: No 'after' results found at $AfterFile" -ForegroundColor Red
        Write-Host "  Run: .\novax_benchmark.ps1 -Mode after" -ForegroundColor Yellow
        return
    }

    $before = Get-Content $BeforeFile | ConvertFrom-Json
    $after = Get-Content $AfterFile | ConvertFrom-Json

    Write-Banner "NOVAX BENCHMARK COMPARISON: BEFORE vs AFTER"
    Write-Host ""
    Write-Host ("  {0,-35} {1,12} {2,12} {3,12}" -f "METRIC", "BEFORE", "AFTER", "CHANGE") -ForegroundColor White
    Write-Host ("  " + ("-" * 71)) -ForegroundColor DarkGray

    function Show-Row {
        param([string]$Label, $Before, $After, [string]$Unit = "", [bool]$LowerBetter = $false)
        $bVal = [double]$Before
        $aVal = [double]$After
        $diff = $aVal - $bVal
        $pct = if ($bVal -ne 0) { [Math]::Round(($diff / [Math]::Abs($bVal)) * 100, 1) } else { 0 }

        $improved = if ($LowerBetter) { $diff -lt 0 } else { $diff -gt 0 }
        $color = if ($improved) { "Green" } elseif ($diff -eq 0) { "White" } else { "Red" }
        $sign = if ($pct -gt 0) { "+" } else { "" }

        $bStr = "{0:N1} {1}" -f $bVal, $Unit
        $aStr = "{0:N1} {1}" -f $aVal, $Unit
        $cStr = "{0}{1:N1}%" -f $sign, $pct

        Write-Host ("  {0,-35} {1,12} {2,12} " -f $Label, $bStr, $aStr) -ForegroundColor White -NoNewline
        Write-Host ("{0,12}" -f $cStr) -ForegroundColor $color
    }

    Show-Row "CPU Single-Thread" $before.CPU.SingleThreadMs $after.CPU.SingleThreadMs "ms" $true
    Show-Row "CPU Multi-Thread" $before.CPU.MultiThreadMs $after.CPU.MultiThreadMs "ms" $true
    Show-Row "CPU Scaling Factor" $before.CPU.ScalingFactor $after.CPU.ScalingFactor "x"
    Write-Host ""
    Show-Row "RAM Seq Write" $before.Memory.SequentialWriteMBs $after.Memory.SequentialWriteMBs "MB/s"
    Show-Row "RAM Seq Read" $before.Memory.SequentialReadMBs $after.Memory.SequentialReadMBs "MB/s"
    Show-Row "RAM Random Latency" $before.Memory.RandomLatencyNs $after.Memory.RandomLatencyNs "ns" $true
    Write-Host ""
    Show-Row "Disk Seq Write" $before.Disk.SeqWriteMBs $after.Disk.SeqWriteMBs "MB/s"
    Show-Row "Disk Seq Read" $before.Disk.SeqReadMBs $after.Disk.SeqReadMBs "MB/s"
    Show-Row "Disk 4K Write IOPS" $before.Disk.Rand4KWriteIOPS $after.Disk.Rand4KWriteIOPS ""
    Show-Row "Disk 4K Read IOPS" $before.Disk.Rand4KReadIOPS $after.Disk.Rand4KReadIOPS ""
    Write-Host ""
    Show-Row "GPU Ollama tok/s" $before.GPU.OllamaTokPerS $after.GPU.OllamaTokPerS "tok/s"
    Write-Host ""
    Show-Row "Network Avg Latency" $before.Network.OverallAvgMs $after.Network.OverallAvgMs "ms" $true
    Write-Host ""
    Show-Row "Services Healthy" $before.Services.HealthyCount $after.Services.HealthyCount ""
    Show-Row "Orchestrator Response" $before.Services.OrchestratorMs $after.Services.OrchestratorMs "ms" $true
    Show-Host ""

    Write-Host ""
    Write-Host ("  {0,-35} {1,12} {2,12}" -f "CATEGORY SCORES", "BEFORE", "AFTER") -ForegroundColor White
    Write-Host ("  " + ("-" * 59)) -ForegroundColor DarkGray
    Show-Row "CPU Score" $before.Scores.CPU $after.Scores.CPU "/100"
    Show-Row "GPU Score" $before.Scores.GPU $after.Scores.GPU "/100"
    Show-Row "RAM Score" $before.Scores.RAM $after.Scores.RAM "/100"
    Show-Row "Disk Score" $before.Scores.Disk $after.Scores.Disk "/100"
    Show-Row "Network Score" $before.Scores.Network $after.Scores.Network "/100"
    Show-Row "Services Score" $before.Scores.Services $after.Scores.Services "/100"

    Write-Host ""
    $oBefore = $before.OverallScore
    $oAfter = $after.OverallScore
    $oDiff = $oAfter - $oBefore
    $oColor = if ($oDiff -gt 0) { "Green" } elseif ($oDiff -eq 0) { "White" } else { "Red" }
    Write-Host ("  OVERALL NOVAX SCORE:  {0:N1}  -->  {1:N1}  ({2}{3:N1})" -f $oBefore, $oAfter, $(if($oDiff -ge 0){"+"}else{""}), $oDiff) -ForegroundColor $oColor
    Write-Host ""
}

# ─────────────────────────────────────────────
# MAIN EXECUTION
# ─────────────────────────────────────────────

if ($Compare) {
    Show-Comparison
    return
}

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$modeLabel = if ($Mode) { $Mode.ToUpper() } else { "STANDARD" }

Write-Host ""
Write-Host "  ╔══════════════════════════════════════════════════════════╗" -ForegroundColor Magenta
Write-Host "  ║         NOVAX SYSTEM PERFORMANCE BENCHMARK              ║" -ForegroundColor Magenta
Write-Host "  ║         Mode: $($modeLabel.PadRight(42))║" -ForegroundColor Magenta
Write-Host "  ║         $($timestamp.PadRight(49))║" -ForegroundColor Magenta
Write-Host "  ╚══════════════════════════════════════════════════════════╝" -ForegroundColor Magenta

# Ensure benchmark temp dir
if (-not (Test-Path $BenchmarkDir)) { New-Item -ItemType Directory -Path $BenchmarkDir -Force | Out-Null }

# Run all benchmarks
$cpuResults = Test-CPU
$memResults = Test-Memory
$diskResults = Test-Disk
$gpuResults = Test-GPU
$netResults = Test-Network
$svcResults = Test-Services

# Compute overall
$overallScore = Compute-OverallScore -CPU $cpuResults -GPU $gpuResults -RAM $memResults -Disk $diskResults -Net $netResults -Svc $svcResults

# Build results object
$results = @{
    Timestamp    = $timestamp
    Mode         = $Mode
    CPU          = $cpuResults
    Memory       = $memResults
    Disk         = $diskResults
    GPU          = $gpuResults
    Network      = $netResults
    Services     = $svcResults
    Scores       = @{
        CPU      = $cpuResults.Score
        GPU      = $gpuResults.Score
        RAM      = $memResults.Score
        Disk     = $diskResults.Score
        Network  = $netResults.Score
        Services = $svcResults.Score
    }
    OverallScore = $overallScore
}

# Save results
$jsonOutput = $results | ConvertTo-Json -Depth 10
$jsonOutput | Set-Content -Path $ResultsFile -Encoding UTF8

if ($Mode -eq "before") {
    $jsonOutput | Set-Content -Path $BeforeFile -Encoding UTF8
    Write-Host "  BEFORE results saved to $BeforeFile" -ForegroundColor Green
} elseif ($Mode -eq "after") {
    $jsonOutput | Set-Content -Path $AfterFile -Encoding UTF8
    Write-Host "  AFTER results saved to $AfterFile" -ForegroundColor Green
}

# Display summary
Write-Banner "PERFORMANCE SUMMARY"
Write-Host ""
Write-Host ("  {0,-30} {1,10} {2,10}" -f "CATEGORY", "SCORE", "WEIGHT") -ForegroundColor White
Write-Host ("  " + ("-" * 50)) -ForegroundColor DarkGray
Write-Metric "CPU"      "$($cpuResults.Score)/100" "(20%)"
Write-Metric "GPU"      "$($gpuResults.Score)/100" "(30%)"
Write-Metric "RAM"      "$($memResults.Score)/100" "(15%)"
Write-Metric "Disk"     "$($diskResults.Score)/100" "(15%)"
Write-Metric "Network"  "$($netResults.Score)/100" "(10%)"
Write-Metric "Services" "$($svcResults.Score)/100" "(10%)"
Write-Host ""

$scoreColor = if ($overallScore -ge 75) { "Green" } elseif ($overallScore -ge 50) { "Yellow" } else { "Red" }
Write-Host "  ┌──────────────────────────────────────┐" -ForegroundColor $scoreColor
Write-Host ("  │  NOVAX PERFORMANCE SCORE: {0,6:N1}/100  │" -f $overallScore) -ForegroundColor $scoreColor
Write-Host "  └──────────────────────────────────────┘" -ForegroundColor $scoreColor
Write-Host ""
Write-Host "  Results saved to: $ResultsFile" -ForegroundColor DarkGray

if ($Mode -eq "before") {
    Write-Host ""
    Write-Host "  Next: Apply optimizations, then run:" -ForegroundColor Yellow
    Write-Host "    .\novax_benchmark.ps1 -Mode after" -ForegroundColor Yellow
    Write-Host "    .\novax_benchmark.ps1 -Compare" -ForegroundColor Yellow
}
if ($Mode -eq "after") {
    Write-Host ""
    Write-Host "  Compare results with:" -ForegroundColor Yellow
    Write-Host "    .\novax_benchmark.ps1 -Compare" -ForegroundColor Yellow
}

# Cleanup temp dir if empty
if ((Get-ChildItem $BenchmarkDir -ErrorAction SilentlyContinue | Measure-Object).Count -eq 0) {
    Remove-Item $BenchmarkDir -Force -ErrorAction SilentlyContinue
}

Write-Host ""
