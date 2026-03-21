$blobDir = "C:\Users\Jupit\.ollama\models\blobs"
$files = Get-ChildItem $blobDir -File | Where-Object { $_.Length -gt 104857600 }
Write-Host "Found $($files.Count) files over 100MB to compress"
$totalBefore = 0
foreach ($f in $files) {
    $totalBefore += $f.Length
}
Write-Host "Total size before: $([math]::Round($totalBefore/1GB, 1)) GB"
Write-Host "Starting NTFS compression..."
compact /c /s /f $blobDir
$totalAfter = 0
$filesAfter = Get-ChildItem $blobDir -File | Where-Object { $_.Length -gt 104857600 }
foreach ($f in $filesAfter) {
    $totalAfter += $f.Length
}
Write-Host "Total size after: $([math]::Round($totalAfter/1GB, 1)) GB"
Write-Host "Done."
