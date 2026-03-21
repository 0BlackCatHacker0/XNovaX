Add-Type -AssemblyName PresentationCore
# Generate with edge-tts
& "C:\NovaX\ai_env\Scripts\edge-tts.exe" --voice "en-US-AvaNeural" --text "Hello. I am Nova. Your AI operating system is online and ready." --write-media "C:\NovaX\tmp\nova_speak.mp3" 2>$null
# Play
$p = New-Object System.Windows.Media.MediaPlayer
$p.Open([Uri]"C:\NovaX\tmp\nova_speak.mp3")
Start-Sleep -Milliseconds 500
$p.Play()
while ($p.Position -lt $p.NaturalDuration.TimeSpan -and $p.Position.TotalSeconds -lt 30) {
    Start-Sleep -Milliseconds 200
}
$p.Close()
