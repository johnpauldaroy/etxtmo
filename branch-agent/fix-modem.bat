@echo off
setlocal EnableDelayedExpansion

REM ---------------------------------------------------------------------
REM  e-txtmo branch modem repair
REM
REM  Run this when the dashboard shows the modem as "error" / offline.
REM  Right-click > "Run as administrator" (stopping a service needs it).
REM
REM  What it does, in order:
REM    1. runs diagnose.py to see whether the modem is actually stuck
REM    2. if stuck, restarts the Gammu SMSD service (the usual cause:
REM       gammu-smsd keeps a dead handle on the COM port and writes into
REM       it forever)
REM    3. re-checks, and restarts the branch agent too if still bad
REM    4. tells you what to do by hand if it still cannot fix it
REM
REM  It will NOT restart anything while messages are actively being sent,
REM  because a restart mid-send can make the modem re-send a message that
REM  already went out to a real member.
REM ---------------------------------------------------------------------

set "AGENT_DIR=%~dp0"
cd /d "%AGENT_DIR%"

REM --- work out which branch this PC is, so the same file runs anywhere --
REM  setup-branch-agent.ps1 names everything after one branch code:
REM    gammu-config-<code>\  GammuSMSD-<code>  TextKonekBranchAgent-<code>
REM  so the folder name next to this file tells us the other two.
REM
REM  Override by passing the code as an argument:  fix-modem.bat 002
set "BRANCH_CODE=%~1"

if not defined BRANCH_CODE (
    for /d %%D in ("%AGENT_DIR%gammu-config-*") do (
        set "FOUND=%%~nxD"
        set "BRANCH_CODE=!FOUND:gammu-config-=!"
    )
)

if not defined BRANCH_CODE (
    echo.
    echo   [STOP] No gammu-config-* folder found next to this file, so the
    echo          branch code cannot be determined.
    echo.
    echo          Pass it explicitly, e.g.:   fix-modem.bat 002
    echo.
    pause
    exit /b 1
)

set "GAMMU_SERVICE=GammuSMSD-%BRANCH_CODE%"
set "AGENT_SERVICE=TextKonekBranchAgent-%BRANCH_CODE%"
set "SPOOL_OUTBOX=%AGENT_DIR%gammu-config-%BRANCH_CODE%\spool\outbox"

echo.
echo ============================================================
echo   e-txtmo modem repair  --  branch %BRANCH_CODE%
echo ============================================================
echo.
echo   gammu service : %GAMMU_SERVICE%
echo   agent service : %AGENT_SERVICE%

REM  A wrong branch code would otherwise fail confusingly at "net stop".
sc query "%GAMMU_SERVICE%" >nul 2>&1
if errorlevel 1 (
    echo.
    echo   [STOP] No service named "%GAMMU_SERVICE%" on this machine.
    echo.
    echo          Using branch code "%BRANCH_CODE%", but no matching
    echo          service exists. Services installed on this PC:
    echo.
    for /f "tokens=2 delims=: " %%S in ('sc query state^= all ^| findstr /i "GammuSMSD- TextKonekBranchAgent-"') do echo            %%S
    echo.
    echo          Re-run with the right code, e.g.:   fix-modem.bat 002
    echo.
    pause
    exit /b 1
)

REM --- must be admin, or the service commands fail confusingly ----------
net session >nul 2>&1
if errorlevel 1 (
    echo.
    echo   [STOP] This must run as administrator.
    echo          Close this window, right-click fix-modem.bat,
    echo          and choose "Run as administrator".
    echo.
    pause
    exit /b 1
)

REM --- find python: prefer the project venv -----------------------------
set "PY="
if exist "%AGENT_DIR%.venv\Scripts\python.exe" set "PY=%AGENT_DIR%.venv\Scripts\python.exe"
if not defined PY (
    where python >nul 2>&1 && set "PY=python"
)
if not defined PY (
    echo   [STOP] Python not found. Cannot run the diagnosis.
    pause
    exit /b 1
)

REM ---------------------------------------------------------------------
echo.
echo [1/4] Checking whether the modem is really stuck...
echo.

"%PY%" "%AGENT_DIR%diagnose.py"
set "DIAG=%errorlevel%"

if "%DIAG%"=="0" (
    echo.
    echo   Diagnosis found no blocking problem.
    echo.
    echo   If the dashboard still shows "error", wait 30 seconds for the
    echo   next heartbeat and refresh. The dashboard lags the fix.
    echo.
    choice /c YN /n /m "   Restart the services anyway? [Y/N] "
    if errorlevel 2 goto :done
)

REM --- refuse to restart mid-send ---------------------------------------
set "PENDING=0"
if exist "%SPOOL_OUTBOX%" (
    for /f %%C in ('dir /b /a-d "%SPOOL_OUTBOX%" 2^>nul ^| find /c /v ""') do set "PENDING=%%C"
)

if not "%PENDING%"=="0" (
    echo.
    echo   [CAUTION] %PENDING% message^(s^) are waiting in the outbox.
    echo.
    echo   Restarting now can make a message that was already handed to
    echo   the modem go out a second time, to a real recipient.
    echo.
    echo   Safer: wait for the outbox to drain, then run this again.
    echo.
    choice /c YN /n /m "   Restart anyway? [Y/N] "
    if errorlevel 2 goto :done
)

REM ---------------------------------------------------------------------
echo.
echo [2/4] Restarting %GAMMU_SERVICE% ...
echo.

net stop "%GAMMU_SERVICE%" 2>nul
if errorlevel 1 echo   ^(service was not running^)

REM Give Windows a moment to actually release the COM port handle.
timeout /t 3 /nobreak >nul

net start "%GAMMU_SERVICE%"
if errorlevel 1 (
    echo.
    echo   [FAIL] Could not start %GAMMU_SERVICE%.
    echo          Check: services.msc  ^>  %GAMMU_SERVICE%
    goto :manual
)

echo.
echo   Waiting 20s for the modem to answer...
timeout /t 20 /nobreak >nul

REM ---------------------------------------------------------------------
echo.
echo [3/4] Re-checking...
echo.

"%PY%" "%AGENT_DIR%diagnose.py"
set "DIAG=%errorlevel%"

if "%DIAG%"=="0" goto :fixed

REM ---------------------------------------------------------------------
echo.
echo [4/4] Still failing. Restarting the branch agent as well...
echo.

net stop "%AGENT_SERVICE%" 2>nul
timeout /t 2 /nobreak >nul
net start "%AGENT_SERVICE%"

timeout /t 15 /nobreak >nul
"%PY%" "%AGENT_DIR%diagnose.py"
set "DIAG=%errorlevel%"

if "%DIAG%"=="0" goto :fixed
goto :manual

REM ---------------------------------------------------------------------
:fixed
echo.
echo ============================================================
echo   FIXED - the modem is answering again.
echo.
echo   Refresh the Modems page. Within about 30 seconds it should
echo   change from "error" to "online".
echo ============================================================
echo.
pause
exit /b 0

REM ---------------------------------------------------------------------
:manual
echo.
echo ============================================================
echo   COULD NOT FIX IT AUTOMATICALLY
echo.
echo   Restarting the software did not bring the modem back, so
echo   this is likely hardware. Try in this order:
echo.
echo     1. Unplug the modem's USB cable, wait 10 seconds,
echo        plug it back in. THEN run this file again
echo        ^(order matters - the service must open a fresh port^).
echo.
echo     2. Device Manager ^> Ports - check the modem appears
echo        with no warning icon. If the COM number changed,
echo        update "device =" in:
echo        %AGENT_DIR%gammu-config-001\smsdrc
echo.
echo     3. Try a different USB port, then a different cable.
echo        Avoid USB hubs - connect straight to the PC.
echo.
echo     4. Check the SIM is seated and not PIN-locked.
echo.
echo   If none of that works, send the last 30 lines of:
echo   %AGENT_DIR%gammu-config-001\smsd.log
echo ============================================================
echo.
pause
exit /b 1

REM ---------------------------------------------------------------------
:done
echo.
echo   No changes made.
echo.
pause
exit /b 0
