Add-Type -AssemblyName PresentationCore
$p = New-Object System.Windows.Media.MediaPlayer
$p.Open([Uri]"C:/NovaX/tmp/nova_speak.mp3")
Start-Sleep -Milliseconds 500
$p.Play()
while ($p.Position -lt $p.NaturalDuration.TimeSpan -and $p.Position.TotalSeconds -lt 120) {
    Start-Sleep -Milliseconds 200
}
$p.Close()
