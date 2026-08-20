@echo off
REM Clean-machine acceptance test, run inside Windows Sandbox.
REM
REM Pure batch on purpose: the machine under test has no Python, which is the
REM whole point. Anything this script needs, the installer must have supplied.
REM
REM Results are written to the mapped results folder so they survive the
REM sandbox being discarded.

setlocal enabledelayedexpansion
set RESULTS=C:\results\clean-machine-test.txt
set FAILURES=0

if not exist C:\results mkdir C:\results >nul 2>&1
echo SRE Book Builder - clean machine test> "%RESULTS%"
echo Started %DATE% %TIME%>> "%RESULTS%"
echo.>> "%RESULTS%"

call :log "=== 1. Confirm the machine really is clean ==="
where python >nul 2>&1 && (call :fail "python IS on PATH - this is not a clean machine") || call :pass "no python on PATH"
where tesseract >nul 2>&1 && (call :fail "tesseract IS on PATH - this is not a clean machine") || call :pass "no tesseract on PATH"
if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (call :fail "Tesseract is installed system-wide") else (call :pass "no system Tesseract installation")

call :log ""
call :log "=== 2. Install ==="
for %%F in (C:\install\SREBookBuilder-*-setup.exe) do set SETUP=%%F
if not defined SETUP (call :fail "no installer found in C:\install" & goto :finish)
call :log "running %SETUP%"
"%SETUP%" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /LOG=C:\results\install.log
if errorlevel 1 (call :fail "installer exited with code %ERRORLEVEL%") else (call :pass "installer completed")

set APP=%LOCALAPPDATA%\Programs\SRE Book Builder
if exist "%APP%\SREBookBuilder.exe" (call :pass "app installed to %APP%") else (call :fail "SREBookBuilder.exe not found in %APP%" & goto :finish)
if exist "%APP%\vendor\tesseract\tesseract.exe" (call :pass "Tesseract was bundled") else (call :fail "vendor\tesseract\tesseract.exe missing")
if exist "%APP%\vendor\tesseract\tessdata\configs\hocr" (call :pass "tessdata/configs/hocr present") else (call :fail "configs/hocr missing - Tesseract cannot emit hOCR")

call :log ""
call :log "=== 3. Does it know what it is? ==="
"%APP%\srebook.exe" doctor >> "%RESULTS%" 2>&1
if errorlevel 1 (call :fail "doctor reported a problem") else (call :pass "doctor passed")
"%APP%\srebook.exe" doctor 2>&1 | findstr /C:"bundled" >nul && (call :pass "using its OWN Tesseract") || call :fail "NOT using the bundled Tesseract"
"%APP%\srebook.exe" doctor 2>&1 | findstr /C:"packaged" >nul && (call :pass "running as a packaged build") || call :fail "not reporting itself as packaged"

call :log ""
call :log "=== 4. Build a real issue ==="
if not exist C:\scans\*.tif (call :log "no scans mapped - skipping" & goto :finish)
if exist C:\work rmdir /s /q C:\work
mkdir C:\work
copy /y C:\scans\*.tif C:\work\ >nul
call :log "copied scans to a writable folder"

"%APP%\srebook.exe" draft C:\work >> "%RESULTS%" 2>&1
if errorlevel 1 (call :fail "draft failed") else (call :pass "draft completed")

"%APP%\srebook.exe" build C:\work >> "%RESULTS%" 2>&1
if errorlevel 1 (call :fail "build failed") else (call :pass "build completed")

for %%P in (C:\work\output\*.pdf) do (
  call :pass "produced %%~nxP  (%%~zP bytes)"
  copy /y "%%P" C:\results\ >nul
)
if not exist C:\work\output\*.pdf call :fail "no PDF was produced"

:finish
call :log ""
if %FAILURES%==0 (
  call :log "RESULT: PASS - the installer works on a machine with nothing on it"
) else (
  call :log "RESULT: FAIL - %FAILURES% problem(s); see above"
)
call :log "Finished %DATE% %TIME%"
echo.
echo ============================================================
type "%RESULTS%"
echo ============================================================
echo.
echo Results saved to C:\results (mapped back to your dist folder).
echo This window stays open so you can read it.
pause
exit /b %FAILURES%

:log
echo %~1
echo %~1>> "%RESULTS%"
exit /b 0

:pass
echo   [ok]   %~1
echo   [ok]   %~1>> "%RESULTS%"
exit /b 0

:fail
echo   [FAIL] %~1
echo   [FAIL] %~1>> "%RESULTS%"
set /a FAILURES+=1
exit /b 0
