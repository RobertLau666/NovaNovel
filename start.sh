#!/bin/bash

# ================= 配置 =================
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color
MARKER_FILE="venv/.installed_flag"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}       AINovel 智能启动助手             ${NC}"
echo -e "${GREEN}========================================${NC}"

# ================= 1. 环境检查与创建 =================

# 检查 Python
if command -v python3 &>/dev/null; then
    PY_CMD=python3
elif command -v python &>/dev/null; then
    PY_CMD=python
else
    echo -e "${YELLOW}[ERROR] 未找到 Python3，请先安装！${NC}"
    exit 1
fi

# 检查 venv 是否存在
if [ ! -d "venv" ]; then
    echo -e "${BLUE}[INIT] 未检测到虚拟环境，正在创建 'venv'...${NC}"
    $PY_CMD -m venv venv
    if [ $? -ne 0 ]; then
        echo -e "${YELLOW}[ERROR] 虚拟环境创建失败。${NC}"
        exit 1
    fi
fi

# ================= 2. 激活环境 =================

source venv/bin/activate

# ================= 3. 智能依赖安装 =================

NEED_INSTALL=false

if [ ! -f "$MARKER_FILE" ]; then
    echo -e "${BLUE}[INFO] 首次运行或标记丢失，准备安装依赖...${NC}"
    NEED_INSTALL=true
elif [ "requirements.txt" -nt "$MARKER_FILE" ]; then
    # -nt 表示 Newer Than (比...新)
    echo -e "${BLUE}[UPDATE] 检测到 requirements.txt 有更新，准备更新依赖...${NC}"
    NEED_INSTALL=true
else
    echo -e "${GREEN}[SKIP] 依赖已是最新，跳过安装。${NC}"
fi

if [ "$NEED_INSTALL" = true ]; then
    echo -e "${YELLOW}[INSTALL] 正在安装依赖，请稍候...${NC}"
    pip install --upgrade pip -q
    pip install -r requirements.txt
    
    if [ $? -eq 0 ]; then
        # 安装成功，更新标记文件的时间戳
        touch "$MARKER_FILE"
        echo -e "${GREEN}[SUCCESS] 依赖安装完成！${NC}"
    else
        echo -e "${YELLOW}[ERROR] 依赖安装失败，请检查网络。${NC}"
        exit 1
    fi
fi

# ================= 4. 启动程序 =================

PORT=8080
URL="http://localhost:$PORT"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   正在启动 AINovel Gradio...           ${NC}"
echo -e "${GREEN}   地址: $URL                     ${NC}"
echo -e "${GREEN}========================================${NC}"

# 自动打开浏览器 (Linux/Mac)
(
    sleep 3
    if [[ "$OSTYPE" == "darwin"* ]]; then
        open "$URL"
    elif command -v xdg-open &>/dev/null; then
        xdg-open "$URL"
    fi
) &

# 启动 Python
python app_gradio.py --port $PORT --share