$data = [System.IO.File]::ReadAllText('C:\NovaX\_all.b64').Trim()
$manifest = @(
  @{s=0;l=3752;p='C:\NovaX\master_scripts\models\claude\nova_extension_bg.js'},
  @{s=3752;l=9148;p='C:\NovaX\master_scripts\models\claude\nova_extension_popup.html'},
  @{s=12900;l=13680;p='C:\NovaX\master_scripts\models\claude\nova_extension_popup.js'},
  @{s=26580;l=7844;p='C:\NovaX\master_scripts\efficiency\OpenClaw_Bible_FULL.txt'},
  @{s=34424;l=7196;p='C:\NovaX\master_scripts\efficiency\Complete_Build_Script.txt'},
  @{s=41620;l=9584;p='C:\NovaX\master_scripts\shared_skills\ai_models_integration.txt'},
  @{s=51204;l=21872;p='C:\NovaX\master_scripts\efficiency\Server_Failure_Bible.txt'},
  @{s=73076;l=27392;p='C:\NovaX\master_scripts\efficiency\Localhost_Stack_Failure_Bible.txt'}
)
$ok=0
foreach($m in $manifest){
  try{
    $chunk=$data.Substring($m.s,$m.l)
    $bytes=[System.Convert]::FromBase64String($chunk)
    $dir=[System.IO.Path]::GetDirectoryName($m.p)
    if(!(Test-Path $dir)){New-Item -ItemType Directory -Force $dir | Out-Null}
    [System.IO.File]::WriteAllBytes($m.p,$bytes)
    $ok++
    Write-Output "OK: $($m.p) ($($bytes.Length) bytes)"
  }catch{Write-Output "FAIL: $($m.p) $_"}
}
Write-Output "DECODED: $ok/8 files"
Remove-Item C:\NovaX\_all.b64 -ErrorAction SilentlyContinue
Remove-Item C:\NovaX\_decoder.ps1 -ErrorAction SilentlyContinue