@echo off
REM kill_zombies.bat — Run from Admin terminal to kill elevated zombies
REM Usage: kill_zombies.bat [PID1] [PID2] ...
REM Or: kill_zombies.bat /port 9899

echo === NovaX Zombie Killer (Admin) ===

if "%1"=="/port" (
    echo Killing processes on port %2...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%2 " ^| findstr "LISTENING"') do (
        echo   Killing PID %%a...
        taskkill /F /PID %%a
    )
    goto :done
)

if "%1"=="" (
    echo Usage: kill_zombies.bat PID1 PID2 ...
    echo        kill_zombies.bat /port PORT_NUMBER
    goto :done
)

:loop
if "%1"=="" goto :done
echo Killing PID %1...
taskkill /F /PID %1
shift
goto :loop

:done
echo.
echo === Done ===
