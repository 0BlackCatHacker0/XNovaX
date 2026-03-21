Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.Volume = 100
$s.Rate = 0
$s.Speak("Testing. One. Two. Three. Can you hear Nova?")
