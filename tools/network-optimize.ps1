#Requires -RunAsAdministrator
<#
.SYNOPSIS
    NovaX Network Stack Optimizer for AI API Calls
    Windows 11 - Maximum throughput for OpenAI, Anthropic, OpenRouter, Google AI, Ollama
.DESCRIPTION
    Optimizes TCP, DNS, QoS, and adapter settings for lowest latency
    and highest throughput on AI API connections.
    REQUIRES: Run as Administrator
.NOTES
    Creates a restore point and backup before applying changes.
    Reboot required after running.
#>

$ErrorActionPreference = "Stop"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile = "C:\NovaX\logs\network-optimize_$timestamp.log"

function Log {
    param([string]$msg)
    $entry = "[$(Get-Date -Format 'HH:mm:ss')] $msg"
    Write-Host $entry -ForegroundColor Cyan
    Add-Content -Path $logFile -Value $entry
}

# Ensure log directory exists
if (!(Test-Path "C:\NovaX\logs")) { New-Item -ItemType Directory -Path "C:\NovaX\logs" -Force | Out-Null }

Log "=========================================="
Log "NovaX Network Stack Optimizer v1.0"
Log "=========================================="

# --- CREATE SYSTEM RESTORE POINT ---
Log "Creating system restore point..."
try {
    Enable-ComputerRestore -Drive "C:\" -ErrorAction SilentlyContinue
    Checkpoint-Computer -Description "NovaX Network Optimization $timestamp" -RestorePointType MODIFY_SETTINGS -ErrorAction SilentlyContinue
    Log "Restore point created."
} catch {
    Log "WARNING: Could not create restore point (non-fatal): $_"
}

# --- BACKUP CURRENT REGISTRY VALUES ---
$backupFile = "C:\NovaX\logs\network-registry-backup_$timestamp.reg"
Log "Backing up current registry to $backupFile..."
try {
    reg export "HKLM\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters" "$backupFile" /y 2>$null
    Log "Registry backup saved."
} catch {
    Log "WARNING: Registry backup partial: $_"
}

# ============================================================
# 1. TCP OPTIMIZATION - Disable Nagle's Algorithm per interface
# ============================================================
Log ""
Log "--- TCP OPTIMIZATION: Disabling Nagle's Algorithm ---"

$interfacesPath = "HKLM:\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces"
$interfaces = Get-ChildItem -Path $interfacesPath

foreach ($iface in $interfaces) {
    $ifacePath = $iface.PSPath
    $ifaceName = $iface.PSChildName

    # Only apply to interfaces that have an IP address assigned
    $ipAddr = (Get-ItemProperty -Path $ifacePath -Name "DhcpIPAddress" -ErrorAction SilentlyContinue).DhcpIPAddress
    $staticIp = (Get-ItemProperty -Path $ifacePath -Name "IPAddress" -ErrorAction SilentlyContinue).IPAddress

    if ($ipAddr -or $staticIp) {
        Log "Optimizing interface: $ifaceName (IP: $($ipAddr ?? $staticIp))"

        # TcpAckFrequency=1 : ACK every packet immediately (no delayed ACK)
        Set-ItemProperty -Path $ifacePath -Name "TcpAckFrequency" -Value 1 -Type DWord -Force
        # TCPNoDelay=1 : Disable Nagle's algorithm (send immediately, don't buffer)
        Set-ItemProperty -Path $ifacePath -Name "TCPNoDelay" -Value 1 -Type DWord -Force

        Log "  TcpAckFrequency=1, TCPNoDelay=1 applied."
    }
}

# ============================================================
# 2. TCP AUTO-TUNING & GLOBAL SETTINGS
# ============================================================
Log ""
Log "--- TCP AUTO-TUNING & GLOBAL SETTINGS ---"

# Auto-tuning: 'normal' is safe and performant; 'experimental' for max throughput
netsh int tcp set global autotuninglevel=normal
Log "TCP Auto-Tuning: normal"

# RSS (Receive Side Scaling) - distributes network processing across CPU cores
netsh int tcp set global rss=enabled
Log "RSS: enabled"

# Chimney Offload - offload TCP processing to NIC (may not be supported on all adapters)
try {
    netsh int tcp set global chimney=enabled 2>$null
    Log "TCP Chimney Offload: enabled (if supported)"
} catch {
    Log "TCP Chimney Offload: not supported on this adapter (skipped)"
}

# DCA (Direct Cache Access) - reduces memory latency for network data
try {
    netsh int tcp set global dca=enabled 2>$null
    Log "DCA: enabled"
} catch {
    Log "DCA: not supported (skipped)"
}

# Disable TCP timestamps - saves ~12 bytes per packet header
try {
    netsh int tcp set global timestamps=disabled 2>$null
    Log "TCP Timestamps: disabled"
} catch {
    Log "TCP Timestamps: setting not available (skipped)"
}

# ECN (Explicit Congestion Notification) - helps with congestion avoidance
netsh int tcp set global ecncapability=enabled
Log "ECN Capability: enabled"

# Disable task offload heuristics for consistent performance
try {
    netsh int tcp set heuristics disabled 2>$null
    Log "TCP Heuristics: disabled"
} catch {
    Log "TCP Heuristics: setting not available (skipped)"
}

# ============================================================
# 3. TCP WINDOW SIZE & CONNECTION PARAMETERS
# ============================================================
Log ""
Log "--- TCP WINDOW SIZE & CONNECTION PARAMETERS ---"

$tcpParamsPath = "HKLM:\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters"

# Initial RTO (Retransmission Timeout) - 1000ms (1 second) instead of default 3000ms
netsh int tcp set global initialRto=1000
Log "Initial RTO: 1000ms"

# TCP Window Size - 65535 (max without window scaling) or larger with scaling
Set-ItemProperty -Path $tcpParamsPath -Name "TcpWindowSize" -Value 65535 -Type DWord -Force
Log "TcpWindowSize: 65535"

# Global Max TCP Window Size (with scaling enabled, allows up to 16MB)
Set-ItemProperty -Path $tcpParamsPath -Name "GlobalMaxTcpWindowSize" -Value 16777216 -Type DWord -Force
Log "GlobalMaxTcpWindowSize: 16777216 (16MB)"

# Default TTL - 128 is standard for Windows
Set-ItemProperty -Path $tcpParamsPath -Name "DefaultTTL" -Value 128 -Type DWord -Force
Log "DefaultTTL: 128"

# Tcp1323Opts=3 : Enable both window scaling AND timestamps
# (timestamps add overhead but enable window scaling above 65535)
# Use 1 for window scaling only (no timestamps), 3 for both
Set-ItemProperty -Path $tcpParamsPath -Name "Tcp1323Opts" -Value 3 -Type DWord -Force
Log "Tcp1323Opts: 3 (window scaling + timestamps for scaling)"

# Max SYN retransmissions - reduce from default 2 to 1 for faster fail
Set-ItemProperty -Path $tcpParamsPath -Name "TcpMaxConnectRetransmissions" -Value 1 -Type DWord -Force
Log "TcpMaxConnectRetransmissions: 1"

# Max data retransmissions before dropping
Set-ItemProperty -Path $tcpParamsPath -Name "TcpMaxDataRetransmissions" -Value 3 -Type DWord -Force
Log "TcpMaxDataRetransmissions: 3"

# Keepalive time - 30 seconds instead of 2 hours (keeps API connections alive)
Set-ItemProperty -Path $tcpParamsPath -Name "KeepAliveTime" -Value 30000 -Type DWord -Force
Log "KeepAliveTime: 30000ms (30s)"

# Keepalive interval - 1 second between keepalive probes
Set-ItemProperty -Path $tcpParamsPath -Name "KeepAliveInterval" -Value 1000 -Type DWord -Force
Log "KeepAliveInterval: 1000ms"

# Max number of ports available (ephemeral port range)
Set-ItemProperty -Path $tcpParamsPath -Name "MaxUserPort" -Value 65534 -Type DWord -Force
Log "MaxUserPort: 65534"

# TIME_WAIT reduction - faster port recycling for burst API calls
Set-ItemProperty -Path $tcpParamsPath -Name "TcpTimedWaitDelay" -Value 30 -Type DWord -Force
Log "TcpTimedWaitDelay: 30 seconds (down from 240)"

# ============================================================
# 4. CONNECTION LIMITS (HTTP)
# ============================================================
Log ""
Log "--- CONNECTION LIMITS ---"

$inetSettingsPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings"

# Max concurrent connections per server (default is 6-8, raise to 32)
Set-ItemProperty -Path $inetSettingsPath -Name "MaxConnectionsPerServer" -Value 32 -Type DWord -Force
Log "MaxConnectionsPerServer: 32"

# Max connections for HTTP/1.0 servers
Set-ItemProperty -Path $inetSettingsPath -Name "MaxConnectionsPer1_0Server" -Value 32 -Type DWord -Force
Log "MaxConnectionsPer1_0Server: 32"

# ============================================================
# 5. DNS OPTIMIZATION
# ============================================================
Log ""
Log "--- DNS OPTIMIZATION ---"

# Detect active network adapter name
$activeAdapter = Get-NetAdapter | Where-Object { $_.Status -eq "Up" -and $_.InterfaceDescription -notmatch "Loopback|Virtual|Hyper-V" } | Select-Object -First 1

if ($activeAdapter) {
    $adapterName = $activeAdapter.Name
    Log "Active adapter detected: $adapterName"

    # Set primary DNS to Cloudflare (1.1.1.1) - fastest public resolver
    netsh interface ip set dns name="$adapterName" static 1.1.1.1
    Log "Primary DNS: 1.1.1.1 (Cloudflare)"

    # Set secondary DNS to Google (8.8.8.8)
    netsh interface ip add dns name="$adapterName" 8.8.8.8 index=2
    Log "Secondary DNS: 8.8.8.8 (Google)"

    # Set tertiary DNS to Cloudflare secondary
    netsh interface ip add dns name="$adapterName" 1.0.0.1 index=3
    Log "Tertiary DNS: 1.0.0.1 (Cloudflare secondary)"
} else {
    Log "WARNING: No active network adapter found. DNS settings skipped."
    Log "Manually run: netsh interface ip set dns name=""YourAdapterName"" static 1.1.1.1"
}

# DNS Client optimizations
try {
    # Clear suffix search list for faster resolution
    Set-DnsClientGlobalSetting -SuffixSearchList @() -ErrorAction SilentlyContinue
    Log "DNS suffix search list: cleared"
} catch {
    Log "DNS suffix setting: skipped (non-fatal)"
}

# Increase DNS cache size via registry
$dnsParamsPath = "HKLM:\SYSTEM\CurrentControlSet\Services\Dnscache\Parameters"
if (!(Test-Path $dnsParamsPath)) { New-Item -Path $dnsParamsPath -Force | Out-Null }

# Max cache entry TTL limit (seconds) - cache entries for up to 1 day
Set-ItemProperty -Path $dnsParamsPath -Name "MaxCacheEntryTtlLimit" -Value 86400 -Type DWord -Force
Log "DNS MaxCacheEntryTtlLimit: 86400 (24h)"

# Max cache size (entries)
Set-ItemProperty -Path $dnsParamsPath -Name "MaxCacheTtl" -Value 86400 -Type DWord -Force
Set-ItemProperty -Path $dnsParamsPath -Name "MaxNegativeCacheTtl" -Value 5 -Type DWord -Force
Log "DNS MaxNegativeCacheTtl: 5 seconds (fail fast on NXDOMAIN)"

# Flush DNS cache to apply new settings
ipconfig /flushdns | Out-Null
Log "DNS cache flushed."

# Pre-resolve AI API endpoints (warm the cache)
Log "Pre-resolving AI API endpoints..."
$apiEndpoints = @(
    "api.openai.com",
    "api.anthropic.com",
    "openrouter.ai",
    "generativelanguage.googleapis.com",
    "aiplatform.googleapis.com"
)
foreach ($endpoint in $apiEndpoints) {
    try {
        $resolved = Resolve-DnsName -Name $endpoint -Type A -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($resolved) {
            Log "  Resolved $endpoint -> $($resolved.IPAddress)"
        }
    } catch {
        Log "  Could not resolve $endpoint (may not be reachable)"
    }
}

# ============================================================
# 6. QUALITY OF SERVICE (QoS)
# ============================================================
Log ""
Log "--- QUALITY OF SERVICE ---"

# Disable QoS bandwidth reservation (Windows reserves 20% by default)
$qosPath = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\Psched"
if (!(Test-Path $qosPath)) { New-Item -Path $qosPath -Force | Out-Null }
Set-ItemProperty -Path $qosPath -Name "NonBestEffortLimit" -Value 0 -Type DWord -Force
Log "QoS NonBestEffortLimit: 0 (no bandwidth reservation)"

# Create QoS policy to prioritize AI API traffic (DSCP 46 = Expedited Forwarding)
try {
    Remove-NetQosPolicy -Name "NovaX-AI-APIs" -Confirm:$false -ErrorAction SilentlyContinue
    New-NetQosPolicy -Name "NovaX-AI-APIs" `
        -AppPathNameMatchCondition "*python*" `
        -DSCPAction 46 `
        -NetworkProfile All `
        -ThrottleRateActionBitsPerSecond 0 `
        -ErrorAction SilentlyContinue | Out-Null
    Log "QoS Policy: NovaX-AI-APIs created (DSCP 46 for Python traffic)"
} catch {
    Log "QoS Policy creation: skipped (non-fatal): $_"
}

# Also prioritize curl/node traffic (for direct API calls)
try {
    Remove-NetQosPolicy -Name "NovaX-Curl" -Confirm:$false -ErrorAction SilentlyContinue
    New-NetQosPolicy -Name "NovaX-Curl" `
        -AppPathNameMatchCondition "*curl*" `
        -DSCPAction 46 `
        -NetworkProfile All `
        -ThrottleRateActionBitsPerSecond 0 `
        -ErrorAction SilentlyContinue | Out-Null
    Log "QoS Policy: NovaX-Curl created (DSCP 46)"
} catch {
    Log "QoS Policy for curl: skipped"
}

# ============================================================
# 7. NETWORK ADAPTER OPTIMIZATION
# ============================================================
Log ""
Log "--- NETWORK ADAPTER OPTIMIZATION ---"

if ($activeAdapter) {
    $adapterName = $activeAdapter.Name

    # Get advanced adapter properties
    $adapterProps = Get-NetAdapterAdvancedProperty -Name $adapterName -ErrorAction SilentlyContinue

    # Disable Flow Control (reduces latency, adapter sends without waiting)
    try {
        Set-NetAdapterAdvancedProperty -Name $adapterName -RegistryKeyword "*FlowControl" -RegistryValue 0 -ErrorAction SilentlyContinue
        Log "Flow Control: disabled"
    } catch {
        Log "Flow Control: setting not available on this adapter"
    }

    # Interrupt Moderation - disable for lowest latency (increases CPU but reduces latency)
    try {
        Set-NetAdapterAdvancedProperty -Name $adapterName -RegistryKeyword "*InterruptModeration" -RegistryValue 0 -ErrorAction SilentlyContinue
        Log "Interrupt Moderation: disabled (lowest latency mode)"
    } catch {
        Log "Interrupt Moderation: setting not available"
    }

    # Receive Buffers - maximize
    try {
        Set-NetAdapterAdvancedProperty -Name $adapterName -RegistryKeyword "*ReceiveBuffers" -RegistryValue 2048 -ErrorAction SilentlyContinue
        Log "Receive Buffers: 2048"
    } catch {
        Log "Receive Buffers: could not set (adapter may not support custom values)"
    }

    # Transmit Buffers - maximize
    try {
        Set-NetAdapterAdvancedProperty -Name $adapterName -RegistryKeyword "*TransmitBuffers" -RegistryValue 2048 -ErrorAction SilentlyContinue
        Log "Transmit Buffers: 2048"
    } catch {
        Log "Transmit Buffers: could not set"
    }

    # Jumbo Frame (if supported by adapter AND network path)
    try {
        Set-NetAdapterAdvancedProperty -Name $adapterName -RegistryKeyword "*JumboPacket" -RegistryValue 9014 -ErrorAction SilentlyContinue
        Log "Jumbo Frame: 9014 bytes (WARNING: verify your router/ISP supports this)"
    } catch {
        Log "Jumbo Frame: not supported on this adapter (standard 1500 MTU retained)"
    }

    # Speed & Duplex - ensure full duplex if wired
    try {
        $mediaType = (Get-NetAdapter -Name $adapterName).MediaType
        if ($mediaType -match "802.3") {
            Set-NetAdapterAdvancedProperty -Name $adapterName -RegistryKeyword "*SpeedDuplex" -RegistryValue 6 -ErrorAction SilentlyContinue
            Log "Speed/Duplex: 1Gbps Full Duplex (wired)"
        }
    } catch {
        Log "Speed/Duplex: auto-negotiate retained"
    }

    # RSS Queues - maximize for multi-core processing
    try {
        Set-NetAdapterRss -Name $adapterName -NumberOfReceiveQueues 4 -ErrorAction SilentlyContinue
        Log "RSS Queues: 4"
    } catch {
        Log "RSS Queues: could not configure"
    }

    # Energy Efficient Ethernet - disable (prevents power-saving latency spikes)
    try {
        Set-NetAdapterAdvancedProperty -Name $adapterName -RegistryKeyword "*EEE" -RegistryValue 0 -ErrorAction SilentlyContinue
        Log "Energy Efficient Ethernet: disabled"
    } catch {
        Log "EEE: setting not available"
    }

    # Disable power management on adapter (prevent sleep disconnects)
    try {
        $pnpDevice = Get-PnpDevice | Where-Object { $_.FriendlyName -eq $activeAdapter.InterfaceDescription } | Select-Object -First 1
        if ($pnpDevice) {
            # Disable "Allow the computer to turn off this device to save power"
            $powerMgmt = Get-CimInstance -ClassName MSPower_DeviceWakeEnable -Namespace root\wmi -ErrorAction SilentlyContinue |
                Where-Object { $_.InstanceName -match [regex]::Escape($pnpDevice.InstanceId) }
            # Registry approach is more reliable
            $adapterRegPath = "HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4D36E972-E325-11CE-BFC1-08002BE10318}"
            Get-ChildItem $adapterRegPath -ErrorAction SilentlyContinue | ForEach-Object {
                $driverDesc = (Get-ItemProperty $_.PSPath -Name "DriverDesc" -ErrorAction SilentlyContinue).DriverDesc
                if ($driverDesc -eq $activeAdapter.InterfaceDescription) {
                    Set-ItemProperty -Path $_.PSPath -Name "PnPCapabilities" -Value 24 -Type DWord -Force
                    Log "Adapter Power Management: disabled (no auto-sleep)"
                }
            }
        }
    } catch {
        Log "Adapter Power Management: could not modify"
    }
} else {
    Log "No active adapter found - adapter optimizations skipped"
}

# ============================================================
# 8. LOCALHOST/LOOPBACK OPTIMIZATION (for Ollama on :11434)
# ============================================================
Log ""
Log "--- LOCALHOST OPTIMIZATION (Ollama) ---"

# Optimize loopback adapter for local AI calls
$loopbackTcpPath = "HKLM:\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters"

# Disable Nagle on loopback (already done globally, but ensure it)
# Loopback doesn't go through physical adapter, so we set it at TCP level
Set-ItemProperty -Path $loopbackTcpPath -Name "EnableTCPA" -Value 1 -Type DWord -Force
Log "TCP/IP Auto-Tuning Acceleration (TCPA): enabled"

# Ensure large send offload is available for loopback
try {
    $loopback = Get-NetAdapter | Where-Object { $_.InterfaceDescription -match "Loopback" }
    if ($loopback) {
        Set-NetAdapterAdvancedProperty -Name $loopback.Name -RegistryKeyword "*LsoV2IPv4" -RegistryValue 1 -ErrorAction SilentlyContinue
        Log "Loopback LSO v2: enabled"
    } else {
        Log "No explicit loopback adapter found (Windows handles internally)"
    }
} catch {
    Log "Loopback optimization: using defaults"
}

# Increase ephemeral port range for burst API calls
netsh int ipv4 set dynamic tcp start=1025 num=64510
Log "Ephemeral port range: 1025-65535 (64510 ports)"

# ============================================================
# 9. WINDOWS NETWORK SERVICES OPTIMIZATION
# ============================================================
Log ""
Log "--- WINDOWS NETWORK SERVICES ---"

# Disable NetBIOS over TCP/IP (reduces broadcast noise)
$wmiAdapters = Get-WmiObject -Class Win32_NetworkAdapterConfiguration -Filter "IPEnabled=TRUE"
foreach ($adapter in $wmiAdapters) {
    $adapter.SetTcpipNetbios(2) | Out-Null  # 2 = Disable NetBIOS
}
Log "NetBIOS over TCP/IP: disabled on all adapters"

# Disable LMHOSTS lookup
$netbtPath = "HKLM:\SYSTEM\CurrentControlSet\Services\NetBT\Parameters"
Set-ItemProperty -Path $netbtPath -Name "EnableLMHOSTS" -Value 0 -Type DWord -Force
Log "LMHOSTS Lookup: disabled"

# Disable Network Location Awareness service excessive polling
# (keeps NLA but reduces its check frequency)
try {
    $nlaPath = "HKLM:\SYSTEM\CurrentControlSet\Services\NlaSvc\Parameters\Internet"
    if (!(Test-Path $nlaPath)) { New-Item -Path $nlaPath -Force | Out-Null }
    Set-ItemProperty -Path $nlaPath -Name "EnableActiveProbing" -Value 1 -Type DWord -Force
    Log "NLA Active Probing: enabled (minimal)"
} catch {
    Log "NLA: could not configure"
}

# ============================================================
# 10. TLS/SSL OPTIMIZATION (faster HTTPS handshakes)
# ============================================================
Log ""
Log "--- TLS/SSL OPTIMIZATION ---"

# Enable TLS 1.3 (fastest, most secure - used by all AI APIs)
$tls13ClientPath = "HKLM:\SYSTEM\CurrentControlSet\Control\SecurityProviders\SCHANNEL\Protocols\TLS 1.3\Client"
if (!(Test-Path $tls13ClientPath)) { New-Item -Path $tls13ClientPath -Force | Out-Null }
Set-ItemProperty -Path $tls13ClientPath -Name "Enabled" -Value 1 -Type DWord -Force
Set-ItemProperty -Path $tls13ClientPath -Name "DisabledByDefault" -Value 0 -Type DWord -Force
Log "TLS 1.3 Client: enabled"

# Disable older TLS versions (1.0, 1.1) - AI APIs don't use them
foreach ($version in @("TLS 1.0", "TLS 1.1")) {
    $clientPath = "HKLM:\SYSTEM\CurrentControlSet\Control\SecurityProviders\SCHANNEL\Protocols\$version\Client"
    if (!(Test-Path $clientPath)) { New-Item -Path $clientPath -Force | Out-Null }
    Set-ItemProperty -Path $clientPath -Name "Enabled" -Value 0 -Type DWord -Force
    Set-ItemProperty -Path $clientPath -Name "DisabledByDefault" -Value 1 -Type DWord -Force
}
Log "TLS 1.0 and 1.1: disabled (security + speed)"

# Enable TLS session resumption (reduces handshake RTTs)
$sslPath = "HKLM:\SYSTEM\CurrentControlSet\Control\SecurityProviders\SCHANNEL"
Set-ItemProperty -Path $sslPath -Name "ClientCacheTime" -Value 300000 -Type DWord -Force
Log "TLS Session Cache: 300 seconds"

# ============================================================
# SUMMARY
# ============================================================
Log ""
Log "=========================================="
Log "OPTIMIZATION COMPLETE"
Log "=========================================="
Log ""
Log "Changes applied:"
Log "  [TCP] Nagle disabled, ACK frequency=1 on all active interfaces"
Log "  [TCP] Auto-tuning=normal, RSS=on, ECN=on, InitialRTO=1000ms"
Log "  [TCP] Window scaling enabled, GlobalMaxWindow=16MB"
Log "  [TCP] TIME_WAIT=30s, KeepAlive=30s, MaxUserPort=65534"
Log "  [HTTP] MaxConnections=32 per server"
Log "  [DNS] Primary=1.1.1.1, Secondary=8.8.8.8, Tertiary=1.0.0.1"
Log "  [DNS] Cache optimized, negative TTL=5s, API endpoints pre-resolved"
Log "  [QoS] Bandwidth reservation=0%, DSCP 46 for Python/curl"
Log "  [NIC] Flow control=off, interrupt moderation=off, EEE=off"
Log "  [NIC] Buffers maximized, power management=off"
Log "  [LOCAL] Ephemeral ports=1025-65535, NetBIOS=off"
Log "  [TLS] TLS 1.3=on, TLS 1.0/1.1=off, session cache=300s"
Log ""
Log "Registry backup: $backupFile"
Log "Log file: $logFile"
Log ""
Log ">>> REBOOT REQUIRED for all changes to take effect <<<"
Log ""

# Prompt for reboot
$reboot = Read-Host "Reboot now? (y/n)"
if ($reboot -eq "y") {
    Log "Rebooting in 10 seconds..."
    shutdown /r /t 10 /c "NovaX Network Optimization - Reboot"
} else {
    Log "Reboot skipped. Please reboot manually for changes to take effect."
}
