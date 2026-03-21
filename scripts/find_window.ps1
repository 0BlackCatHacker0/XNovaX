Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
using System.Text;
using System.Collections.Generic;
public class WinFinder {
    [DllImport("user32.dll")] public static extern IntPtr FindWindow(string cls, string title);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)]
    public static extern int GetWindowText(IntPtr hWnd, StringBuilder sb, int max);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint pid);

    public delegate bool EnumProc(IntPtr hwnd, IntPtr lParam);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr lParam);
}
"@

$results = [System.Collections.ArrayList]::new()
$callback = [WinFinder+EnumProc]{
    param($hwnd, $lParam)
    if ([WinFinder]::IsWindowVisible($hwnd)) {
        $sb = New-Object System.Text.StringBuilder 256
        [WinFinder]::GetWindowText($hwnd, $sb, 256) | Out-Null
        $title = $sb.ToString()
        if ($title.Length -gt 0) {
            $pid = [uint32]0
            [WinFinder]::GetWindowThreadProcessId($hwnd, [ref]$pid) | Out-Null
            $null = $results.Add("$pid|$hwnd|$title")
        }
    }
    return $true
}

[WinFinder]::EnumWindows($callback, [IntPtr]::Zero) | Out-Null

Write-Host "=== All visible windows with titles ==="
foreach ($r in $results) {
    $parts = $r -split '\|', 3
    $title = $parts[2]
    if ($title -match 'blend|Blend|BLEND') {
        Write-Host "BLENDER >>> PID=$($parts[0]) HWND=$($parts[1]) TITLE=$title"
    }
}
Write-Host "=== Total windows: $($results.Count) ==="
Write-Host ""
Write-Host "=== Searching by class GHOST_WindowClass ==="
$h = [WinFinder]::FindWindow("GHOST_WindowClass", $null)
Write-Host "GHOST_WindowClass: $h"
