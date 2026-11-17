@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -m pip install -r requirements.txt
  if errorlevel 1 goto error
  py main.py
) else (
  python -m pip install -r requirements.txt
  if errorlevel 1 goto error
  python main.py
)
pause
exit /b 0
:error
echo.
echo 安装依赖失败，请检查 Python 是否安装、网络是否可用。
pause
exit /b 1
