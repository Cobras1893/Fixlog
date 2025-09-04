@echo off
:: Compile RepairLauncher.exe using .NET Framework csc.exe (no dotnet SDK needed)
setlocal
set "DEST=C:\Program Files\RepairLauncher"
set "OUT=%DEST%\RepairLauncher.exe"

:: run as admin check
net session >nul 2>&1
if %errorlevel% neq 0 (
  echo [!] Please run this batch as Administrator.
  pause
  exit /b 1
)

:: locate csc.exe
set "CSC=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if not exist "%CSC%" set "CSC=%WINDIR%\Microsoft.NET\Framework\v4.0.30319\csc.exe"
if not exist "%CSC%" (
  echo [!] csc.exe not found. Install ".NET Framework 4.8 Developer Pack" or "Visual Studio Build Tools".
  pause
  exit /b 2
)

if not exist "%DEST%" mkdir "%DEST%"

:: compile
"%CSC%" /nologo /target:winexe /platform:anycpu /unsafe- /optimize+ ^
  /out:"%OUT%" ^
  /reference:"System.Windows.Forms.dll" /reference:"System.Web.dll" ^
  "%~dp0Program_ascii.cs"

if errorlevel 1 (
  echo [!] Compile failed.
  pause
  exit /b 3
) else (
  echo [OK] Built %OUT%
)

:: register protocol
reg add "HKEY_CLASSES_ROOT\repairtool" /ve /d "URL:Repair Tool Protocol" /f >nul
reg add "HKEY_CLASSES_ROOT\repairtool" /v "URL Protocol" /d "" /f >nul
reg add "HKEY_CLASSES_ROOT\repairtool\DefaultIcon" /ve /d "%OUT%,0" /f >nul
reg add "HKEY_CLASSES_ROOT\repairtool\shell\open\command" /ve /d "\"%OUT%\" \"%%1\"" /f >nul

echo [OK] Protocol registered. Test URL:
echo   repairtool://10.103.127.177/app/OA_debug/aspen%25E7%2584%25A1%25E6%25B3%2595%25E9%2596%258B%25E5%2595%259F/aspen_debug.exe
pause
