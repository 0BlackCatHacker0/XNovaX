$blobDir = "C:\Users\Jupit\.ollama\models\blobs"
$files = Get-ChildItem $blobDir -File
Write-Host "Total blob files: $($files.Count)"
$big = $files | Where-Object { $_.Length -gt 104857600 }
Write-Host "Files over 100MB: $($big.Count)"

$before = (Get-Volume -DriveLetter C).SizeRemaining
Write-Host "Disk free before: $([math]::Round($before/1GB, 1)) GB"

$i = 0
foreach ($f in $big) {
    $i++
    $sizeMB = [math]::Round($f.Length/1MB)
    Write-Host "[$i/$($big.Count)] Compressing $($f.Name.Substring(0,16))... ($sizeMB MB)"
    compact /c $f.FullName | Out-Null
}

$after = (Get-Volume -DriveLetter C).SizeRemaining
Write-Host ""
Write-Host "Disk free after: $([math]::Round($after/1GB, 1)) GB"
Write-Host "Space recovered: $([math]::Round(($after - $before)/1GB, 1)) GB"
Write-Host "Done."
