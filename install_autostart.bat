@echo off
echo Installing TimeTracker to Windows Autostart...

REM Get the current directory
set "SCRIPT_DIR=%~dp0"

REM Create VBS script to create shortcut
echo Set oWS = WScript.CreateObject("WScript.Shell") > "%TEMP%\CreateShortcut.vbs"
echo sLinkFile = oWS.SpecialFolders("Startup") ^& "\TimeTracker.lnk" >> "%TEMP%\CreateShortcut.vbs"
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> "%TEMP%\CreateShortcut.vbs"
echo oLink.TargetPath = "%SCRIPT_DIR%start.bat" >> "%TEMP%\CreateShortcut.vbs"
echo oLink.WorkingDirectory = "%SCRIPT_DIR%" >> "%TEMP%\CreateShortcut.vbs"
echo oLink.Description = "TimeTracker - Activity Tracking Application" >> "%TEMP%\CreateShortcut.vbs"
echo oLink.Save >> "%TEMP%\CreateShortcut.vbs"

REM Execute VBS script
cscript //nologo "%TEMP%\CreateShortcut.vbs"

REM Clean up
del "%TEMP%\CreateShortcut.vbs"

echo.
echo TimeTracker has been added to Windows Autostart!
echo The application will start automatically when you log in.
echo.
pause
