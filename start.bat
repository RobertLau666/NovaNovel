@echo off
chcp 65001 >nul
echo ========================================
echo        AINovel 一键启动助手 (Windows)
echo ========================================

:: 1. 检查 Python 是否安装
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] 未检测到 Python，请先安装 Python 并添加到环境变量！
    pause
    exit /b
)

:: 2. 检查并创建虚拟环境
if not exist venv (
    echo [INFO] 未检测到虚拟环境，正在创建 'venv'...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] 创建虚拟环境失败。
        pause
        exit /b
    )
    echo [SUCCESS] 虚拟环境创建完成。
) else (
    echo [INFO] 检测到已有虚拟环境 'venv'。
)

:: 3. 激活环境
echo [INFO] 正在激活虚拟环境...
call venv\Scripts\activate.bat

:: 4. 安装依赖
echo [INFO] 正在检查依赖...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] 依赖安装失败。
    pause
    exit /b
)

:: 5. 启动浏览器 (预判)
echo [INFO] 正在启动浏览器...
start http://localhost:8080

:: 6. 启动程序
echo [INFO] 正在启动 AINovel...
python app_gradio.py --port 8080 --share

pause