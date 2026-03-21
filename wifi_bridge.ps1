# NovaX WiFi Bridge - Bond 2 adapters for combined bandwidth
# Run as Administrator
param([string]$Adapter1='WIFI_1_NAME',[string]$Adapter2='WIFI_2_NAME')
Write-Host '=== NovaX WiFi Bridge ===' -ForegroundColor Cyan
Write-Host "Bonding: $Adapter1 + $Adapter2" -ForegroundColor Yellow
Write-Host 'Available Network Adapters:' -ForegroundColor Green
Get-NetAdapter | Format-Table Name, Status, LinkSpeed, InterfaceDescription -AutoSize
Write-Host 'Creating bridge...' -ForegroundColor Yellow
try {
  $existing = Get-NetAdapter | Where-Object {$_.Name -like '*Bridge*'}
  New-NetLbfoTeam -Name 'NovaX_Bridge' -TeamMembers $Adapter1,$Adapter2 -TeamingMode SwitchIndependent -LoadBalancingAlgorithm Dynamic -ErrorAction Stop
  Write-Host 'NIC Team created: NovaX_Bridge' -ForegroundColor Green
} catch {
  Write-Host 'NIC Teaming requires manual bridge.' -ForegroundColor Red
  Write-Host 'Manual steps:' -ForegroundColor Cyan
  Write-Host '1. Open ncpa.cpl'
  Write-Host '2. Select both adapters (Ctrl+Click)'
  Write-Host '3. Right-click > Bridge Connections'
  Write-Host 'Or install Speedify for automatic bonding' -ForegroundColor Yellow
}
Write-Host '=== Network Speed Monitor ===' -ForegroundColor Cyan
for ($i=0;$i -lt 10;$i++) {
  $s = Get-NetAdapterStatistics -ErrorAction SilentlyContinue
  $tr = ($s | Measure-Object -Property ReceivedBytes -Sum).Sum
  $ts = ($s | Measure-Object -Property SentBytes -Sum).Sum
  Write-Host ('  Recv: {0:N0} MB | Sent: {1:N0} MB' -f ($tr/1MB),($ts/1MB))
  Start-Sleep -Seconds 1
}
