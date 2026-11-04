@echo off
chcp 65001 >nul
setlocal
title PyQuadDir v2.5 4분할 파일 탐색기 (실사용 중)
set "PROJ_DIR=D:\workspace\projects\active\pyquaddir"
cd /d "%PROJ_DIR%"
if /I "%AGY_SMOKE_TEST%"=="1" (
    python -m py_compile "%PROJ_DIR%\pyquaddir.py"
    exit /b %ERRORLEVEL%
)
if /I "%~1"=="--self-test" (
    python -m py_compile "%PROJ_DIR%\pyquaddir.py"
    exit /b %ERRORLEVEL%
)
if exist "%PROJ_DIR%\dist\PyQuadDir.exe" (
    start "" "%PROJ_DIR%\dist\PyQuadDir.exe"
    exit /b 0
)
if exist "%PROJ_DIR%\pyquaddir.py" (
    start "" pythonw "%PROJ_DIR%\pyquaddir.py"
    exit /b 0
)
exit /b 0
