@echo off
chcp 65001 >nul
setlocal
title PyQuadDir v3.2.0 4분할 파일 탐색기
set "PROJ_DIR=%~dp0"
cd /d "%PROJ_DIR%"
if /I "%AGY_SMOKE_TEST%"=="1" (
    python -c "import pathlib,sys; p=pathlib.Path(sys.argv[1]); compile(p.read_text(encoding='utf-8-sig'),str(p),'exec')" "%PROJ_DIR%\pyquaddir.py"
    if errorlevel 1 exit /b 1
    exit /b 0
)
if /I "%~1"=="--self-test" (
    python -c "import pathlib,sys; p=pathlib.Path(sys.argv[1]); compile(p.read_text(encoding='utf-8-sig'),str(p),'exec')" "%PROJ_DIR%\pyquaddir.py"
    if errorlevel 1 exit /b 1
    exit /b 0
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
