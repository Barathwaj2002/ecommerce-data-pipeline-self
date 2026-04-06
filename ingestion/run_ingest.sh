#!/bin/bash

clear
echo "========================================"
echo "      PIPELINE QUICK STATUS"
echo "      $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"

echo -e "\nDisk usage (current folder):"
du -sh

echo -e "\nMemory usage:"

if command -v free >/dev/null 2>&1; then
    free -h | grep Mem
else
    # Windows Git Bash fallback using PowerShell
    powershell -Command "
    \$os = Get-CimInstance Win32_OperatingSystem;
    \$total = [math]::Round(\$os.TotalVisibleMemorySize / 1MB, 2);
    \$free = [math]::Round(\$os.FreePhysicalMemory / 1MB, 2);
    \$used = [math]::Round(\$total - \$free, 2);
    Write-Output \"Memory Used: \$used GB / \$total GB\"
    "
fi


echo -e "\nRunning Python processes:"
ps aux | grep python | grep -v grep | head -n 5

echo -e "\nLast 10 lines of any log (if exists):"
tail -n 10 *.log 2>/dev/null || echo "No logs found"

echo -e "\n----------------------------------------"
read -p "Press ENTER to close this window..."
