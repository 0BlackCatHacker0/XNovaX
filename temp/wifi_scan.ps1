Add-Type -AssemblyName System.Runtime.WindowsRuntime

# Helper to await WinRT async tasks
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
Function Await($WinRtTask, $ResultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    $netTask.Result
}

# Load WinRT WiFi types
[void][Windows.Devices.WiFi.WiFiAdapter,Windows.Devices.WiFi,ContentType=WindowsRuntime]

# Find all WiFi adapters
$adapters = Await ([Windows.Devices.WiFi.WiFiAdapter]::FindAllAdaptersAsync()) ([System.Collections.Generic.IReadOnlyList[Windows.Devices.WiFi.WiFiAdapter]])

if ($adapters.Count -eq 0) {
    Write-Host '{"ok":false,"networks":[],"error":"No WiFi adapters found via WinRT"}'
    exit
}

$adapter = $adapters[0]

# Scan for networks
$scanTask = $adapter.ScanAsync()
$scanTask.AsTask().Wait(-1) | Out-Null

# Collect results
$results = @()
foreach ($net in $adapter.NetworkReport.AvailableNetworks) {
    $ssid = $net.Ssid
    if ([string]::IsNullOrWhiteSpace($ssid)) { continue }
    $signal = $net.SignalBars  # 0-4 bars
    $rssi = $net.NetworkRssiInDecibelMilliwatts
    $auth = $net.SecuritySettings.NetworkAuthenticationType.ToString()
    # Convert bars to percentage approximation
    $signalPct = switch ($signal) { 0 {0} 1 {20} 2 {40} 3 {65} 4 {90} default {50} }
    $results += @{ ssid=$ssid; signal=$signalPct; auth=$auth; rssi=$rssi; bssid="" }
}

# Deduplicate by SSID keeping strongest
$best = @{}
foreach ($r in $results) {
    $s = $r.ssid
    if (-not $best.ContainsKey($s) -or $r.signal -gt $best[$s].signal) {
        $best[$s] = $r
    }
}

$sorted = $best.Values | Sort-Object signal -Descending
$json = $sorted | ConvertTo-Json -Compress
if ($sorted.Count -eq 1) { $json = "[$json]" }
if ($sorted.Count -eq 0) { $json = "[]" }
Write-Host $json
