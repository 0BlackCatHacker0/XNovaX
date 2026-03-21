@echo off
echo Compressing Ollama model blobs (163GB)...
echo This may take 5-15 minutes on NVMe.
compact /c /s /f "C:\Users\Jupit\.ollama\models\blobs"
echo.
echo === COMPRESSION COMPLETE ===
echo Check disk space with: wmic logicaldisk get size,freespace,caption
pause
