Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.Volume = 100
$s.Rate = 1
$s.Speak("Testing NovaX voice. Can you hear me right now?")
