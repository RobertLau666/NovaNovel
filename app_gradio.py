import gradio as gr
import os
import shutil
import pandas as pd
import time
import threading
import glob
import argparse
from dotenv import load_dotenv

# 导入核心逻辑
from app_v4 import DeepSeekClient, DMXImageAPIGenerator, NovelGenerator

# 加载环境变量
load_dotenv()

# ================= 配置常量 =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSVS_DIR = os.path.join(BASE_DIR, "csvs")
NOVELS_DIR = os.path.join(BASE_DIR, "novels")
LINKS_DIR = os.path.join(BASE_DIR, "temp_novels_views")

# 确保目录存在
os.makedirs(CSVS_DIR, exist_ok=True)
os.makedirs(NOVELS_DIR, exist_ok=True)
os.makedirs(LINKS_DIR, exist_ok=True)

# 全局变量
current_view_path = NOVELS_DIR 

# ================= 辅助函数 =================

def get_csv_files():
    """获取 csvs/ 目录下所有 csv 文件"""
    if not os.path.exists(CSVS_DIR): return []
    # 按修改时间排序，最近修改的在前面
    files = [f for f in os.listdir(CSVS_DIR) if f.endswith('.csv')]
    files.sort(key=lambda x: os.path.getmtime(os.path.join(CSVS_DIR, x)), reverse=True)
    return files

def parse_task_ids(text_input, all_ids):
    """解析文本输入的 task_id 范围"""
    if not text_input:
        return []
    
    selected_ids = set()
    parts = text_input.replace('，', ',').split(',')
    for p in parts:
        p = p.strip()
        if not p: continue
        if '-' in p:
            try:
                s, e = map(int, p.split('-'))
                selected_ids.update(range(s, e + 1))
            except: pass
        else:
            try:
                selected_ids.add(int(p))
            except: pass
    
    valid_ids = [tid for tid in selected_ids if tid in all_ids]
    return sorted(list(valid_ids))

def read_specific_log(task_id):
    """读取特定 Task ID 的日志"""
    log_path = os.path.join(NOVELS_DIR, f"task_{task_id}", f"task_{task_id}.log")
    if os.path.exists(log_path):
        try:
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception as e:
            return f"读取日志出错: {e}"
    else:
        return f"等待日志文件生成...\n目标路径: {log_path}"

# ================= 后台任务：软链接刷新 =================

def refresh_symlink():
    global current_view_path
    timestamp = int(time.time())
    new_link_name = f"novels_view_{timestamp}"
    new_link_path = os.path.join(LINKS_DIR, new_link_name)
    
    try:
        if os.path.exists(new_link_path):
            os.remove(new_link_path)
        os.symlink(NOVELS_DIR, new_link_path)
        
        current_view_path = new_link_path
        
        all_links = sorted(glob.glob(os.path.join(LINKS_DIR, "novels_view_*")))
        if len(all_links) > 5:
            for old_link in all_links[:-5]:
                try: os.remove(old_link)
                except: pass
        return new_link_path
    except Exception as e:
        print(f"软链接刷新失败: {e}")
        return NOVELS_DIR

# ================= Gradio 逻辑函数 =================

def upload_csv_file(file):
    if file is None:
        return gr.update(), "未选择文件"
    
    filename = os.path.basename(file.name)
    dest_path = os.path.join(CSVS_DIR, filename)
    
    # shutil.copy 会直接覆盖同名文件
    shutil.copy(file.name, dest_path)
    
    # 强制刷新列表，并选中刚上传的文件
    return gr.update(choices=get_csv_files(), value=filename), f"✅ 已上传/覆盖文件: {filename}"

def on_csv_selected(filename):
    if not filename:
        return None, gr.update(choices=[], value=[]), gr.update(value=""), ""
    
    path = os.path.join(CSVS_DIR, filename)
    try:
        df = pd.read_csv(path)
        
        choices = []
        all_ids = []
        completed_count = 0
        
        if 'task_id' in df.columns:
            for idx, row in df.iterrows():
                tid = row['task_id']
                status = row.get('status', 0)
                
                # 🟢 [需求实现] 如果任务已完成 (status=2)，跳过添加到选项列表
                if status == 2:
                    completed_count += 1
                    all_ids.append(tid) # 依然加入 all_ids 以便通过文本框强制指定
                    continue
                
                status_icon = "🔄" if status == 1 else "⏳"
                idea = str(row.get('novel_idea', '无主题'))[:15]
                label = f"ID:{tid} [{status_icon}] - {idea}..."
                
                choices.append((label, tid))
                all_ids.append(tid)
        
        info_text = f"共发现 {len(df)} 个任务。"
        if completed_count > 0:
            info_text += f" (其中 {completed_count} 个已完成任务已自动隐藏)"
        
        return df, gr.update(choices=choices, value=[]), gr.update(placeholder="输入ID范围，如: 1, 3-5"), info_text

    except Exception as e:
        return None, gr.update(choices=[]), gr.update(value=""), f"读取失败: {e}"

def execute_tasks(csv_filename, check_ids, text_ids, gen_cover):
    if not csv_filename:
        yield "请先选择 CSV 文件", ""
        return

    csv_path = os.path.join(CSVS_DIR, csv_filename)
    df = pd.read_csv(csv_path)
    all_existing_ids = df['task_id'].tolist() if 'task_id' in df.columns else []

    target_ids = set(check_ids)
    target_ids.update(parse_task_ids(text_ids, all_existing_ids))
    target_ids = sorted(list(target_ids))
    
    if not target_ids:
        yield "❌ 未选择有效任务 ID", ""
        return

    yield f"🚀 准备执行任务 IDs: {target_ids}...\n", ""

    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    if not deepseek_key:
        yield "❌ 错误: 未找到 DEEPSEEK_API_KEY", ""
        return

    try:
        llm = DeepSeekClient(
            api_key=deepseek_key,
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            model_name=os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        )
        
        dmx = None
        if gen_cover:
            dmx_key = os.getenv("DMX_API_KEY")
            if dmx_key:
                dmx = DMXImageAPIGenerator(api_key=dmx_key)
            else:
                yield "⚠️ 警告: 勾选了封面生成但未配置 DMX_API_KEY，将跳过封面。\n", ""

        generator = NovelGenerator(llm, dmx, csv_path)

    except Exception as e:
        yield f"❌ 初始化失败: {e}", ""
        return

    # 筛选任务
    tasks_queue = []
    for idx, row in df.iterrows():
        tid = row.get('task_id', idx+1)
        if tid in target_ids:
            tasks_queue.append((tid, row.to_dict()))

    total = len(tasks_queue)
    for i, (tid, task_data) in enumerate(tasks_queue):
        msg_prefix = f"▶️ [{i+1}/{total}] Task {tid}: "
        yield msg_prefix + "正在启动...", ""
        
        generator.update_task_csv(csv_path, tid, status=1, gen_start=True)
        
        task_thread_finished = False
        
        def run_thread():
            nonlocal task_thread_finished
            try:
                success = generator.process_task(task_data, tid)
                final_status = 2 if success else 3
                generator.update_task_csv(csv_path, tid, status=final_status, gen_end=True)
            except Exception as e:
                print(f"Task {tid} Exception: {e}")
                generator.update_task_csv(csv_path, tid, status=3)
            finally:
                task_thread_finished = True

        t = threading.Thread(target=run_thread)
        t.start()
        
        while not task_thread_finished:
            log_content = read_specific_log(tid)
            yield msg_prefix + "执行中...", log_content
            time.sleep(1.5)
            
        t.join()
        
        log_content = read_specific_log(tid)
        yield f"✅ Task {tid} 完成。\n", log_content
        
    yield "🎉 所有任务执行完毕！", "All Done."

# ================= Gradio UI 构建 =================

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=7860, help="Gradio server port")
    parser.add_argument("--share", action="store_true", help="Create a public link")
    args = parser.parse_args()

    # 将 theme 移动到 launch
    gradio_title = "📚 AINovel (Gradio)"
    with gr.Blocks(title=gradio_title) as demo:
        gr.Markdown(f"## {gradio_title}")
        
        # Row 1: CSV 上传与选择
        with gr.Row(variant="panel"):
            with gr.Column(scale=1):
                upload_comp = gr.File(label="📂 上传/覆盖 CSV", file_types=[".csv"])
            
            with gr.Column(scale=1):
                csv_dropdown = gr.Dropdown(choices=get_csv_files(), label="📋 选择 CSV 任务表", interactive=True)
                refresh_csv_btn = gr.Button("🔄 刷新列表", size="sm")
            
            with gr.Column(scale=2):
                csv_viewer = gr.DataFrame(label="📊 CSV 内容预览", wrap=True)

        # Row 2: 任务配置
        with gr.Row(variant="panel"):
            with gr.Column(scale=1):
                gen_cover_box = gr.Checkbox(label="🎨 生成封面", value=False, info="需要配置 DMX_API_KEY")
            
            with gr.Column(scale=3):
                gr.Markdown("### 🎯 任务选择 (Task IDs)")
                
                # 🟢 [需求实现] 提示信息组件
                task_info_md = gr.Markdown("请选择要执行的任务（已过滤掉已完成的任务）")
                
                with gr.Row():
                    id_checklist = gr.CheckboxGroup(label="列表勾选", choices=[])
                    id_textbox = gr.Textbox(label="文本强制指定", placeholder="例: 1, 3-5 (可强制重跑)")

        # Row 3: 启动
        with gr.Row():
            run_btn = gr.Button("🚀 开始生成", variant="primary", scale=2)

        # Row 4: 日志
        with gr.Row():
            with gr.Column():
                status_bar = gr.Textbox(label="总体状态", show_label=True)
                log_viewer = gr.Code(label="📜 实时日志监控", language=None, lines=15, interactive=False)

        # Row 5: 结果文件
        gr.Markdown("### 📂 成果文件浏览")
        
        with gr.Row():
            with gr.Column(scale=1):
                # 🟢 [需求实现] file_count="single"
                file_explorer = gr.FileExplorer(
                    root_dir=NOVELS_DIR,
                    ignore_glob="**/__pycache__/**",
                    label="📁 Novels 目录 (自动刷新)",
                    height=600,
                    file_count="single" 
                )
                dir_refresh_timer = gr.Timer(value=3 * 60)

            with gr.Column(scale=2):
                gr.Markdown("#### 👁️ 文件预览 & 下载")
                selected_path_box = gr.Textbox(label="当前选中文件路径", interactive=False)
                
                preview_img = gr.Image(label="封面预览", visible=False)
                preview_df = gr.DataFrame(label="表格预览", visible=False)
                preview_txt = gr.Code(label="文本/代码预览", visible=False, language=None)
                download_btn = gr.File(label="⬇️ 下载文件", visible=True)

        # ================= 交互逻辑 =================

        upload_comp.upload(upload_csv_file, inputs=upload_comp, outputs=[csv_dropdown, status_bar])
        
        refresh_csv_btn.click(lambda: gr.update(choices=get_csv_files()), outputs=csv_dropdown)
        
        # 🟢 选中 CSV 时触发，更新选项并显示隐藏信息
        csv_dropdown.change(
            on_csv_selected,
            inputs=csv_dropdown,
            outputs=[csv_viewer, id_checklist, id_textbox, task_info_md]
        )
        
        run_btn.click(
            execute_tasks,
            inputs=[csv_dropdown, id_checklist, id_textbox, gen_cover_box],
            outputs=[status_bar, log_viewer]
        )
        
        def auto_refresh_dir():
            new_path = refresh_symlink()
            return gr.update(root_dir=new_path)

        dir_refresh_timer.tick(auto_refresh_dir, outputs=file_explorer)
        
        def preview_file(file_path):
            if not file_path:
                return [gr.update(visible=False)]*3 + [None, ""]
            
            # 🟢 即便设置了 single，Gradio 可能返回列表，兼容处理
            if isinstance(file_path, list):
                if len(file_path) == 0: return [gr.update(visible=False)]*3 + [None, ""]
                file_path = file_path[0]
                
            ext = os.path.splitext(file_path)[1].lower()
            
            update_img = gr.update(visible=False)
            update_df = gr.update(visible=False)
            update_txt = gr.update(visible=False)
            
            try:
                if ext in ['.png', '.jpg', '.jpeg']:
                    update_img = gr.update(value=file_path, visible=True)
                
                elif ext in ['.csv', '.xlsx', '.xls']:
                    if ext == '.csv':
                        df = pd.read_csv(file_path)
                    else:
                        df = pd.read_excel(file_path)
                    update_df = gr.update(value=df, visible=True)
                    
                elif ext in ['.txt', '.json', '.log', '.md', '.py']:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read(20000)
                        if len(content) == 20000: content += "\n... (内容过长截断)"
                    
                    lang_map = {'.json': 'json', '.py': 'python', '.md': 'markdown'}
                    lang = lang_map.get(ext, None)
                    update_txt = gr.update(value=content, language=lang, visible=True)
                    
                elif ext == '.zip':
                    update_txt = gr.update(value="📦 ZIP 压缩包，请点击下方下载按钮。", language=None, visible=True)
                
                else:
                    update_txt = gr.update(value=f"暂不支持预览 {ext} 格式，请下载查看。", language=None, visible=True)
                    
            except Exception as e:
                update_txt = gr.update(value=f"预览出错: {e}", language=None, visible=True)
                
            return update_img, update_df, update_txt, file_path, file_path

        file_explorer.change(
            preview_file,
            inputs=file_explorer,
            outputs=[preview_img, preview_df, preview_txt, download_btn, selected_path_box]
        )

    print(f"🚀 Starting Gradio server on port {args.port}...")
    demo.queue().launch(
        server_name="0.0.0.0", 
        server_port=args.port, 
        share=args.share,
        allowed_paths=[BASE_DIR],
        theme=gr.themes.Soft()
    )