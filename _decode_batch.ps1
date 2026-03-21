
$files = @(
  @{b='C:\NovaX\_f0.b64'; o='C:\NovaX\master_scripts\efficiency\Complete_Build_Script.txt'},
  @{b='C:\NovaX\_f1.b64'; o='C:\NovaX\master_scripts\shared_skills\ai_models_integration.txt'},
  @{b='C:\NovaX\_f2.b64'; o='C:\NovaX\master_scripts\efficiency\OpenClaw_Bible_FULL.txt'},
  @{b='C:\NovaX\_f3.b64'; o='C:\NovaX\master_scripts\efficiency\Server_Failure_Bible.txt'},
  @{b='C:\NovaX\_f4.b64'; o='C:\NovaX\master_scripts\efficiency\Localhost_Stack_Failure_Bible.txt'}
)
$ok=0
foreach($f in $files){
  if(Test-Path $f.b){
    try{
      $data=[System.IO.File]::ReadAllText($f.b).Trim()
      $bytes=[System.Convert]::FromBase64String($data)
      [System.IO.File]::WriteAllBytes($f.o,$bytes)
      Remove-Item $f.b
      $ok++
      Write-Output "OK: $($f.o) ($($bytes.Length)B)"
    }catch{Write-Output "FAIL: $($f.o) $_"}
  }else{Write-Output "SKIP: $($f.b) not found"}
}
Write-Output "DECODED:$ok/5"
