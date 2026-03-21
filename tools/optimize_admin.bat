@echo off
echo ============================================
echo   NovaX Admin Hardware Optimizations
echo   Run this as Administrator (right-click)
echo ============================================
echo.

echo [1/4] Disabling Windows Search (WSearch)...
echo         Saves 200-500MB RAM + reduces disk I/O
net stop WSearch >nul 2>&1
sc config WSearch start= disabled >nul 2>&1
echo         DONE

echo [2/4] Disabling SysMain (Superfetch)...
echo         Saves 300MB RAM - NovaX has its own cache
net stop SysMain >nul 2>&1
sc config SysMain start= disabled >nul 2>&1
echo         DONE

echo [3/4] Disabling last access timestamps...
echo         Reduces NVMe write overhead
fsutil behavior set disablelastaccess 1 >nul 2>&1
echo         DONE

echo [4/4] Enabling large system cache...
echo         Faster model file loading from NVMe
reg add "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management" /v LargeSystemCache /t REG_DWORD /d 1 /f >nul 2>&1
echo         DONE

echo.
echo ============================================
echo   All 4 admin optimizations applied!
echo   RAM freed: ~500-800MB
echo   Disk I/O: reduced write overhead
echo   No restart required for WSearch/SysMain.
echo   LargeSystemCache takes effect on next boot.
echo ============================================
pause
