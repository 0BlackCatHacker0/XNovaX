try {
    $null = [Windows.Media.SpeechSynthesis.SpeechSynthesizer,Windows.Media,ContentType=WindowsRuntime]
    $synth = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer
    $voices = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices
    Write-Host "Windows 11 Neural Voices: $($voices.Count)"
    foreach ($v in $voices) {
        Write-Host "  $($v.DisplayName) | $($v.Gender) | $($v.Language)"
    }
} catch {
    Write-Host "UWP speech not available: $_"
}
