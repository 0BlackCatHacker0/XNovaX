@echo off
echo [trit_engine] Building release DLL...
cd /d "%~dp0"

cargo build --release
if errorlevel 1 (
    echo [trit_engine] BUILD FAILED
    exit /b 1
)

echo [trit_engine] Copying DLL...
copy /Y target\release\trit_engine.dll ..\trit_engine.dll >nul
if exist target\release\trit_engine.dll.lib (
    copy /Y target\release\trit_engine.dll.lib ..\trit_engine.dll.lib >nul
)

echo [trit_engine] Build complete: ..\trit_engine.dll
echo [trit_engine] Size:
for %%A in (..\trit_engine.dll) do echo   %%~zA bytes
