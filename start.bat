@echo off
chcp 65001 >nul
setlocal

echo ========================================
echo        AINovel 智能启动助手 (Windows)
echo ========================================

set "VENV_DIR=venv"
set "MARKER_FILE=%VENV_DIR%\.installed_flag"
set "REQ_FILE=requirements.txt"

:: 1. 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] 未检测到 Python，请先安装 Python 3.10+ 并添加到 PATH！
    pause
    exit /b
)

:: 2. 检查/创建虚拟环境
if not exist "%VENV_DIR%" (
    echo [INIT] 未检测到虚拟环境，正在创建...
    python -m venv %VENV_DIR%
    if %errorlevel% neq 0 (
        echo [ERROR] 创建虚拟环境失败。
        pause
        exit /b
    )
)

:: 3. 激活环境
call %VENV_DIR%\Scripts\activate.bat

:: 4. 智能依赖检测 (使用 PowerShell 比较时间戳)
set NEED_INSTALL=0

if not exist "%MARKER_FILE%" (
    set NEED_INSTALL=1
    echo [INFO] 首次运行，准备安装依赖...
) else (
    :: 比较 requirements.txt 是否比 marker_file 新
    powershell -Command "if ((Get-Item '%REQ_FILE%').LastWriteTime -gt (Get-Item '%MARKER_FILE%').LastWriteTime) { exit 1 } else { exit 0 }"
    if errorlevel 1 (
        set NEED_INSTALL=1
        echo [UPDATE] 发现 requirements.txt 更新，准备升级依赖...
    ) else (
        echo [SKIP] 依赖已是最新，跳过安装。
    )
)

:: 5. 执行安装 (如果需要)
if %NEED_INSTALL%==1 (
    echo [INSTALL] 正在安装依赖...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] 依赖安装失败。
        pause
        exit /b
    )
    :: 创建/更新标记文件的时间戳
    type nul > "%MARKER_FILE%"
)

:: 6. 启动程序
echo ========================================
echo    正在启动程序... 
echo    http://localhost:8080
echo ========================================

:: 后台启动浏览器
start http://localhost:8080

:: 启动 Python
python app_gradio.py --port 8080 --share

pause