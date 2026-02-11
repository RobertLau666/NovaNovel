#!/bin/bash

# ================= 配置 =================
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color
MARKER_FILE="venv/.installed_flag"
TARGET_PYTHON_VERSION="3.12.1"
PORT=8080

# 屏蔽 jieba 等库的 SyntaxWarning
export PYTHONWARNINGS="ignore::SyntaxWarning"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}       AINovel 智能启动助手 v2.1        ${NC}"
echo -e "${GREEN}========================================${NC}"

# ================= 1. 环境准备 (UV & Python) =================

if [ ! -d "venv" ]; then
    echo -e "${BLUE}[INIT] 未检测到虚拟环境，正在准备 Python ${TARGET_PYTHON_VERSION}...${NC}"
    
    if ! command -v uv &>/dev/null; then
        echo -e "${YELLOW}[DOWNLOAD] 正在下载 uv 包管理器...${NC}"
        # 增加超时限制，防止此处也卡住
        curl -LsSf https://astral.sh/uv/install.sh --connect-timeout 10 | sh
        if [ -f "$HOME/.cargo/bin/uv" ]; then export PATH="$HOME/.cargo/bin:$PATH"; 
        elif [ -f "$HOME/.local/bin/uv" ]; then export PATH="$HOME/.local/bin:$PATH"; fi
    fi

    if command -v uv &>/dev/null; then
        echo -e "${BLUE}[SETUP] 使用 uv 创建虚拟环境...${NC}"
        uv venv venv --python ${TARGET_PYTHON_VERSION}
    else
        echo -e "${YELLOW}[WARN] uv 安装失败，尝试使用系统 Python...${NC}"
        python3 -m venv venv
    fi

    if [ $? -ne 0 ]; then echo -e "${RED}[ERROR] 虚拟环境创建失败。${NC}"; exit 1; fi
fi

source venv/bin/activate

# ================= 2. 依赖安装 =================

if [ ! -f "$MARKER_FILE" ] || [ "requirements.txt" -nt "$MARKER_FILE" ]; then
    echo -e "${YELLOW}[INSTALL] 正在安装/更新依赖，请稍候...${NC}"
    if command -v uv &>/dev/null; then
        uv pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    else
        pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple -q
    fi
    if [ $? -eq 0 ]; then touch "$MARKER_FILE"; echo -e "${GREEN}[SUCCESS] 依赖安装完成！${NC}"; else echo -e "${RED}[ERROR] 依赖安装失败。${NC}"; exit 1; fi
else
    echo -e "${GREEN}[SKIP] 依赖已是最新。${NC}"
fi

# ================= 3. 自动修复 Gradio Share 组件 (优化网络处理) =================

FRPC_DIR="$HOME/.cache/huggingface/gradio/frpc"
FRPC_FILE="$FRPC_DIR/frpc_darwin_amd64_v0.3"
DOWNLOAD_URL="https://cdn-media.huggingface.co/frpc-gradio-0.3/frpc_darwin_amd64"

if [ ! -f "$FRPC_FILE" ]; then
    echo -e "${BLUE}[FIX] 检测到 Gradio Share 组件缺失...${NC}"
    mkdir -p "$FRPC_DIR"
    
    echo -e "${YELLOW}[DOWNLOAD] 正在下载 frpc (用于生成公开链接)...${NC}"
    echo -e "${YELLOW}           (如网络不通将自动跳过，不影响本地使用)${NC}"
    
    # 核心修改：显示进度条 (-#)，5秒连接超时，20秒总耗时限制
    curl -L "$DOWNLOAD_URL" -o "$FRPC_FILE" -# --connect-timeout 5 --max-time 20
    
    if [ -f "$FRPC_FILE" ] && [ -s "$FRPC_FILE" ]; then
        chmod +x "$FRPC_FILE"
        echo -e "${GREEN}[SUCCESS] Share 组件修复成功！${NC}"
    else
        # 下载失败处理
        rm -f "$FRPC_FILE" # 删除可能的空文件
        echo -e "${RED}[WARN] 下载超时或失败 (国内网络原因)${NC}"
        echo -e "${RED}       已跳过此步骤，程序将继续启动。${NC}"
        echo -e "${RED}       (注意：本次启动无法生成 Share 公开链接，仅限本地访问)${NC}"
        echo -e "若需 Share 功能：1. 请手动下载: $DOWNLOAD_URL 文件；2. 重命名为 frpc_darwin_amd64_v0.3；3. 放入: $FRPC_DIR 文件夹中。"
    fi
fi

# ================= 4. 启动服务与健康检查 =================

echo -e "${BLUE}[START] 正在启动 Gradio 服务 (端口: $PORT)...${NC}"
echo -e "${YELLOW}[WAIT] 程序加载中 (这通常需要 3-5 秒)...${NC}"

python app_gradio_v3.py --port $PORT --share > /dev/null 2>&1 &
SERVER_PID=$!

# 循环检查端口
MAX_RETRIES=60
COUNT=0
SPIN='-\|/'

while ! nc -z localhost $PORT >/dev/null 2>&1; do
    if ! ps -p $SERVER_PID > /dev/null; then
        echo -e "\n${RED}[ERROR] Python 程序启动失败！${NC}"
        # 尝试前台运行一次以显示报错
        echo -e "${YELLOW}正在尝试前台运行以捕获错误信息：${NC}"
        # python app_gradio_v3.py --port $PORT --share

        # 🟢 [修改] 增加环境变量，允许 macOS 使用 fork 模式，并强制无缓冲输出
        export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
        export PYTHONUNBUFFERED=1
        python app_gradio_v3.py --port $PORT --share

        exit 1
    fi
    
    # 动态加载动画
    i=$(( (i+1) %4 ))
    printf "\r${YELLOW}[LOADING] ${SPIN:$i:1} 等待服务响应 ($COUNT/60s)...${NC}"
    
    sleep 1
    COUNT=$((COUNT+1))
    
    if [ $COUNT -ge $MAX_RETRIES ]; then
        echo -e "\n${RED}[TIMEOUT] 服务启动超时。${NC}"
        kill $SERVER_PID
        exit 1
    fi
done

# ================= 5. 启动成功 =================

URL="http://localhost:$PORT"

echo -e "\n"
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   🚀 服务已成功启动！                 ${NC}"
echo -e "${GREEN}   👉 本地访问: $URL            ${NC}"
echo -e "${GREEN}========================================${NC}"

# 自动打开浏览器
if [[ "$OSTYPE" == "darwin"* ]]; then
    open "$URL"
elif command -v xdg-open &>/dev/null; then
    xdg-open "$URL"
fi

wait $SERVER_PID