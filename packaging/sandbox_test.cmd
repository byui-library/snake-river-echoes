@echo off
REM Clean-machine acceptance test, run inside Windows Sandbox.
REM
REM Pure batch on purpose: the machine under test has no Python, which is the
REM whole point. Anything this script needs, the installer must have supplied.
REM
REM Style note, learned the hard way: no "&" chaining and no goto out of a
REM parenthesised if-block. cmd parses the whole block before running it, and an
REM earlier version jumped to the summary mid-run and wrote two phantom
REM failures into a report that had otherwise passed. Every check below is a
REM single unparenthesised statement, and the verdict is derived at the end by
REM scanning the report itself rather than trusting a counter.

setlocal
set RESULTS=C:\results\clean-machine-test.txt
set APP=%LOCALAPPDATA%\Programs\SRE Book Builder

if not exist C:\results mkdir C:\results >nul 2>&1
> "%RESULTS%" echo SRE Book Builder - clean machine test
call :note "Started %DATE% %TIME%"

call :section "1. Confirm the machine really is clean"
call :forbid_cmd  python                                     "no python on PATH"
call :forbid_cmd  tesseract                                  "no tesseract on PATH"
call :forbid_file "C:\Program Files\Tesseract-OCR\tesseract.exe" "no system Tesseract installation"

call :section "2. Install"
set SETUP=
for %%F in (C:\install\SREBookBuilder-*-setup.exe) do set SETUP=%%F
if not defined SETUP call :fail "no installer found in C:\install"
if not defined SETUP goto :summary
call :note "running %SETUP%"
"%SETUP%" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /LOG=C:\results\install.log
set RC=%ERRORLEVEL%
if "%RC%"=="0" call :pass "installer completed"
if not "%RC%"=="0" call :fail "installer exited with code %RC%"

call :require_file "%APP%\SREBookBuilder.exe"                          "the window is installed"
call :require_file "%APP%\srebook.exe"                                 "the command line is installed"
call :require_file "%APP%\vendor\tesseract\tesseract.exe"              "Tesseract was bundled"
call :require_file "%APP%\vendor\tesseract\tessdata\eng.traineddata"   "English language data present"
call :require_file "%APP%\vendor\tesseract\tessdata\configs\hocr"      "tessdata\configs\hocr present"
if not exist "%APP%\srebook.exe" goto :summary

call :section "3. Does it know what it is?"
"%APP%\srebook.exe" doctor >> "%RESULTS%" 2>&1
set RC=%ERRORLEVEL%
if "%RC%"=="0" call :pass "doctor passed"
if not "%RC%"=="0" call :fail "doctor reported a problem (exit %RC%)"
call :expect_in_doctor "bundled"  "using its OWN Tesseract, not one from the host"
call :expect_in_doctor "packaged" "reporting itself as a packaged build"

call :section "4. Build a real issue"
if not exist C:\scans\*.tif call :fail "no scans mapped to C:\scans"
if not exist C:\scans\*.tif goto :summary
if exist C:\work rmdir /s /q C:\work
mkdir C:\work
copy /y C:\scans\*.tif C:\work\ >nul
call :note "copied scans to a writable folder"

"%APP%\srebook.exe" draft C:\work >> "%RESULTS%" 2>&1
set RC=%ERRORLEVEL%
if "%RC%"=="0" call :pass "draft completed"
if not "%RC%"=="0" call :fail "draft failed (exit %RC%)"

REM --force because nobody reviews the draft in an unattended run. The build
REM refuses unreviewed bookmarks by design; this test is about packaging, not
REM editorial review, so it says so out loud rather than hiding the override.
call :note "building with --force (unattended: no operator reviewed the draft)"
"%APP%\srebook.exe" build C:\work --force >> "%RESULTS%" 2>&1
set RC=%ERRORLEVEL%
if "%RC%"=="0" call :pass "build completed"
if not "%RC%"=="0" call :fail "build failed (exit %RC%)"

set PDF=
for %%P in (C:\work\output\*.pdf) do set PDF=%%P
if not defined PDF call :fail "no PDF was produced"
if defined PDF call :report_pdf

:summary
call :section "Result"
REM Derive the verdict from what was actually recorded. A counter can be lost
REM to a control-flow mistake; the report cannot.
findstr /c:"[FAIL]" "%RESULTS%" >nul
set FOUND=%ERRORLEVEL%
if "%FOUND%"=="0" call :note "RESULT: FAIL - see the [FAIL] lines above"
if not "%FOUND%"=="0" call :note "RESULT: PASS - the installer works on a machine with nothing on it"
call :note "Finished %DATE% %TIME%"

echo.
echo ============================================================
type "%RESULTS%"
echo ============================================================
echo.
echo Results and the finished PDF are in C:\results, which is mapped
echo back to your sandbox-results folder. This window stays open so
echo you can read it; closing the sandbox discards everything else.
pause
exit /b 0

REM ------------------------------------------------------------------ helpers

:section
echo.
echo(>> "%RESULTS%"
call :note "=== %~1 ==="
exit /b 0

:note
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
exit /b 0

:require_file
if exist "%~1" call :pass "%~2"
if not exist "%~1" call :fail "%~2 -- MISSING: %~1"
exit /b 0

:forbid_file
if not exist "%~1" call :pass "%~2"
if exist "%~1" call :fail "%~2 -- but it IS present: %~1  (not a clean machine)"
exit /b 0

:forbid_cmd
where %~1 >nul 2>&1
set WRC=%ERRORLEVEL%
if not "%WRC%"=="0" call :pass "%~2"
if "%WRC%"=="0" call :fail "%~2 -- but %~1 IS on PATH (not a clean machine)"
exit /b 0

:expect_in_doctor
"%APP%\srebook.exe" doctor 2>&1 | findstr /c:"%~1" >nul
set DRC=%ERRORLEVEL%
if "%DRC%"=="0" call :pass "%~2"
if not "%DRC%"=="0" call :fail "%~2 -- doctor did not report '%~1'"
exit /b 0

:report_pdf
for %%P in ("%PDF%") do call :pass "produced %%~nxP  (%%~zP bytes)"
copy /y "%PDF%" C:\results\ >nul
copy /y "C:\work\output\*.srebook.json" C:\results\ >nul 2>&1
exit /b 0
