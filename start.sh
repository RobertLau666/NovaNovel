#!/bin/bash

# ================= 配置颜色 =================
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}       AINovel 一键启动助手             ${NC}"
echo -e "${GREEN}========================================${NC}"

# ================= 1. 系统检测 =================
OS="$(uname -s)"
case "${OS}" in
    Linux*)     machine=Linux;;
    Darwin*)    machine=Mac;;
    CYGWIN*)    machine=Cygwin;;
    MINGW*)     machine=MinGW;;
    MSYS*)      machine=MSYS;;
    *)          machine="UNKNOWN:${OS}"
esac

echo -e "${YELLOW}[INFO] 检测到当前系统为: ${machine}${NC}"

# ================= 2. 环境检查与虚拟环境创建 =================

# 检测 Python 命令
if command -v python3 &>/dev/null; then
    PY_CMD=python3
elif command -v python &>/dev/null; then
    PY_CMD=python
else
    echo -e "${RED}[ERROR] 未检测到 Python，请先安装 Python 3.10+ 版本！${NC}"
    exit 1
fi

echo -e "${YELLOW}[INFO] 使用 Python 解释器: $($PY_CMD --version)${NC}"

# 检查 venv 文件夹是否存在
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}[INFO] 未检测到虚拟环境，正在创建 'venv'...${NC}"
    $PY_CMD -m venv venv
    if [ $? -ne 0 ]; then
        echo -e "${RED}[ERROR] 虚拟环境创建失败，请检查是否安装了 python3-venv (Linux) 或 Python 安装是否完整。${NC}"
        exit 1
    fi
    echo -e "${GREEN}[SUCCESS] 虚拟环境创建完成。${NC}"
else
    echo -e "${GREEN}[INFO] 检测到已有虚拟环境 'venv'，跳过创建。${NC}"
fi

# ================= 3. 激活环境与依赖安装 =================

echo -e "${YELLOW}[INFO] 正在激活虚拟环境...${NC}"

# 根据系统不同，激活脚本位置不同
if [[ "$machine" == "MinGW" || "$machine" == "MSYS" || "$machine" == "Cygwin" ]]; then
    # Windows Git Bash
    source venv/Scripts/activate
else
    # Linux / Mac
    source venv/bin/activate
fi

# 检查激活是否成功
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo -e "${RED}[ERROR] 虚拟环境激活失败！${NC}"
    exit 1
fi

echo -e "${YELLOW}[INFO] 正在检查并安装依赖 (requirements.txt)...${NC}"
# 升级 pip 以避免一些兼容性问题
pip install --upgrade pip -q

if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo -e "${RED}[ERROR] 依赖安装失败，请检查网络或配置源。${NC}"
        exit 1
    fi
else
    echo -e "${RED}[ERROR] 未找到 requirements.txt 文件！${NC}"
    exit 1
fi

echo -e "${GREEN}[SUCCESS] 环境准备就绪！${NC}"

# ================= 4. 启动程序 =================

PORT=8080
URL="http://localhost:$PORT"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   正在启动 AINovel Gradio 界面...      ${NC}"
echo -e "${GREEN}   访问地址: $URL                 ${NC}"
echo -e "${GREEN}========================================${NC}"

# 尝试在浏览器中打开链接 (后台运行)
# 等待几秒钟让服务先启动
(
    sleep 5
    if [[ "$machine" == "Mac" ]]; then
        open "$URL"
    elif [[ "$machine" == "Linux" ]]; then
        xdg-open "$URL"
    elif [[ "$machine" == "MinGW" || "$machine" == "MSYS" ]]; then
        start "$URL"
    fi
) &

# 启动 Python 程序
python app_gradio.py --port $PORT --share

# 退出时取消激活
deactivate