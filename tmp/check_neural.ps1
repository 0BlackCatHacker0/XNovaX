Add-Type -AssemblyName System.Speech
# Check OneCore voices via registry
$voices = Get-ChildItem "HKLM:\SOFTWARE\Microsoft\Speech_OneCore\Voices\Tokens" -ErrorAction SilentlyContinue
if ($voices) {
    foreach ($v in $voices) {
        $name = (Get-ItemProperty $v.PSPath)."(default)" 
        $attrs = Get-ItemProperty "$($v.PSPath)\Attributes" -ErrorAction SilentlyContinue
        $gender = if ($attrs) { $attrs.Gender } else { "?" }
        $lang = if ($attrs) { $attrs.Language } else { "?" }
        Write-Host "$name | $gender | $lang"
    }
} else {
    Write-Host "No OneCore voices found"
}
Write-Host "---"
# Also check via SpeechSynthesizer with OneCore trick
try {
    $synth = New-Object -ComObject SAPI.SpVoice
    $allVoices = $synth.GetVoices()
    Write-Host "SAPI voices: $($allVoices.Count)"
    for ($i=0; $i -lt $allVoices.Count; $i++) {
        Write-Host "  $($allVoices.Item($i).GetDescription())"
    }
} catch {
    Write-Host "SAPI check failed"
}
