$stubs = @(
    "nova_physics_engine_stub.nova",
    "nova_core_engine_stub.nova",
    "nova_render_engine_stub.nova",
    "nova_sim_engine_stub.nova",
    "nova_audio_engine_stub.nova",
    "nova_prime_stub.nova",
    "nova_script_vault_stub.nova",
    "nova_ternary_sql_stub.nova"
)
foreach ($stub in $stubs) {
    $p = New-Object System.Diagnostics.Process
    $p.StartInfo.FileName = "C:\NovaX\novalang.exe"
    $p.StartInfo.Arguments = "C:\NovaX\$stub"
    $p.StartInfo.WorkingDirectory = "C:\NovaX"
    $p.StartInfo.UseShellExecute = $false
    $p.StartInfo.CreateNoWindow = $true
    $p.Start() | Out-Null
    Write-Host "Started $stub (PID: $($p.Id))"
    Start-Sleep -Seconds 3
}
