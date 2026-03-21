Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voices = $s.GetInstalledVoices()
foreach ($v in $voices) {
    $info = $v.VoiceInfo
    Write-Host "$($info.Name) | $($info.Gender) | $($info.Culture) | $($info.Age)"
}
