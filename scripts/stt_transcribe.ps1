# stt_transcribe.ps1 -- NovaX STT PowerShell Helper (Zero Python)
# Called by nova_stt_service.nova via shell()
# Usage: powershell -File C:\NovaX\scripts\stt_transcribe.ps1 -AudioPath <path> [-Language en]
# Output: JSON to stdout

param(
    [Parameter(Mandatory=$true)][string]$AudioPath,
    [string]$Language = "en",
    [string]$Mode = "file"  # "file" = transcribe file, "mic" = live mic (3s)
)

$ErrorActionPreference = "SilentlyContinue"
$result = @{ ok = $false; text = ""; duration = 0; engine = "windows-stt"; trit = -1 }
$t0 = Get-Date

try {
    Add-Type -AssemblyName System.Speech

    $rec = New-Object System.Speech.Recognition.SpeechRecognitionEngine
    $grammar = New-Object System.Speech.Recognition.DictationGrammar
    $rec.LoadGrammar($grammar)

    if ($Mode -eq "mic") {
        # Live microphone capture (3 second window)
        $rec.SetInputToDefaultAudioDevice()
        $recognized = $rec.Recognize([TimeSpan]::FromSeconds(3))
    }
    elseif (Test-Path $AudioPath) {
        # Transcribe audio file
        $rec.SetInputToWaveFile($AudioPath)
        $recognized = $rec.Recognize()
    }
    else {
        $result.text = ""
        $result.error = "File not found: $AudioPath"
        $result | ConvertTo-Json -Compress
        exit 1
    }

    $duration = ((Get-Date) - $t0).TotalSeconds
    $result.duration = [math]::Round($duration, 3)

    if ($recognized -and $recognized.Text) {
        $result.ok = $true
        $result.text = $recognized.Text
        $result.confidence = [math]::Round($recognized.Confidence, 3)

        # Trit scoring based on confidence (N-S Reynolds mapping)
        # Re < 27 (H3^3) = laminar = high confidence (+1)
        # Re < 125 (H5^3) = transitional = partial (0)
        # Re >= 125 = turbulent = low confidence (-1)
        if ($recognized.Confidence -ge 0.7) {
            $result.trit = 1
        } elseif ($recognized.Confidence -ge 0.4) {
            $result.trit = 0
        } else {
            $result.trit = -1
        }
    }
    else {
        $result.ok = $false
        $result.text = ""
        $result.trit = -1
    }

    $rec.Dispose()
}
catch {
    $result.error = $_.Exception.Message
    $result.trit = -1
}

$result | ConvertTo-Json -Compress
