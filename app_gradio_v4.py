import gradio as gr
import os
import shutil
import pandas as pd
import time
import threading
import multiprocessing
import sys
import glob       # 🟢 [补全]
import argparse   # 🟢 [补全]
from dotenv import load_dotenv
from concurrent.futures import ProcessPoolExecutor

# 🟢 导入核心逻辑 (确保你的核心逻辑文件名为 app_v7.py)
from app_v7 import DeepSeekClient, DMXImageAPIGenerator, NovelGenerator, run_single_task_worker

# 🟢 [适配 macOS] 多进程设置
if sys.platform == 'darwin':
    try:
        multiprocessing.set_start_method('fork', force=True)
    except RuntimeError:
        pass

# 加载环境变量
load_dotenv()

# ================= 配置常量 (必须放在全局) =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# CSV 任务文件存放目录
NOVEL_CSVS_DIR = os.path.join(BASE_DIR, "novel_csvs") 
# 小说生成结果目录
NOVELS_DIR = os.path.join(BASE_DIR, "novels")

# 确保目录存在
os.makedirs(NOVEL_CSVS_DIR, exist_ok=True)
os.makedirs(NOVELS_DIR, exist_ok=True)

# 🟢 [新增] 全局停止事件信号
STOP_EVENT = threading.Event()

# ================= 辅助函数 =================

def get_csv_files():
    """获取 novel_csvs/ 目录下所有 csv 文件"""
    if not os.path.exists(NOVEL_CSVS_DIR): return []
    files = [f for f in os.listdir(NOVEL_CSVS_DIR) if f.endswith('.csv')]
    # 按修改时间倒序
    files.sort(key=lambda x: os.path.getmtime(os.path.join(NOVEL_CSVS_DIR, x)), reverse=True)
    return files

def parse_task_ids(text_input, all_ids):
    """解析文本输入的 task_id 范围"""
    if not text_input: return []
    
    selected_ids = set()
    # 支持中文逗号
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
            try: selected_ids.add(int(p))
            except: pass
    
    # 过滤掉不存在的 ID
    valid_ids = [tid for tid in selected_ids if tid in all_ids]
    return sorted(list(valid_ids))

# def read_specific_log(task_id, csv_filename=None):
#     """
#     读取特定 Task ID 的日志
#     :param task_id: 任务ID
#     :param csv_filename: CSV文件名 (用于定位子目录)
#     """
#     # 优先尝试精确路径: novels/{csv_name}/task_{id}/task_{id}.log
#     if csv_filename:
#         csv_name = os.path.splitext(csv_filename)[0]
#         log_path = os.path.join(NOVELS_DIR, csv_name, f"task_{task_id}", f"task_{task_id}.log")
        
#         if os.path.exists(log_path):
#             try:
#                 with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
#                     return f.read()
#             except Exception as e:
#                 return f"读取日志出错: {e}"
    
#     # 如果精确路径找不到（可能是刚开始生成，目录还没建好），尝试全局搜索（兼容旧结构）
#     search_pattern = os.path.join(NOVELS_DIR, "**", f"task_{task_id}", f"task_{task_id}.log")
#     found_files = glob.glob(search_pattern, recursive=True)
    
#     if found_files:
#         try:
#             # 如果有多个，优先选最新的或者路径匹配的
#             target_file = found_files[0]
#             if csv_filename:
#                 csv_name_clean = os.path.splitext(csv_filename)[0]
#                 for f in found_files:
#                     if csv_name_clean in f:
#                         target_file = f
#                         break
            
#             with open(target_file, 'r', encoding='utf-8', errors='ignore') as f:
#                 return f.read()
#         except Exception as e:
#             return f"读取日志出错: {e}"
            
#     # 还没找到
#     path_hint = log_path if csv_filename else search_pattern
#     return f"⏳ 正在初始化日志文件...\n(Target: {path_hint})"

def read_specific_log(task_id, csv_filename=None):
    """
    读取特定 Task ID 的日志
    目标路径格式: novels/csv-{csv_name}/csv-{csv_name}_task-{task_id}/log.log
    """
    csv_name = ""
    log_path = ""

    # 1. 尝试精确路径匹配
    if csv_filename:
        # 去掉后缀 .csv
        csv_name = os.path.splitext(csv_filename)[0]
        # 你的实际路径结构
        log_path = os.path.join(NOVELS_DIR, f"csv-{csv_name}", f"csv-{csv_name}_task-{task_id}", "log.log")
        
        if os.path.exists(log_path):
            try:
                with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read()
            except Exception as e:
                return f"读取日志出错: {e}"
    
    # 2. 如果精确路径没找到，尝试模糊搜索 (保底)
    # 搜索 novels/任意目录/*task-40*/log.log
    # 注意：你的 task 目录名中有 task-{id}，但也可能是 task_{id} (取决于生成器代码)，这里用通配符兼容
    search_pattern = os.path.join(NOVELS_DIR, "**", f"*task*{task_id}*", "log.log")
    found_files = glob.glob(search_pattern, recursive=True)
    
    if found_files:
        try:
            target_file = found_files[0]
            # 如果有多个，优先选路径里包含 csv_name 的
            if csv_filename:
                for f in found_files:
                    if csv_name in f:
                        target_file = f
                        break
            
            with open(target_file, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception as e:
            return f"读取日志出错: {e}"
            
    # 3. 还没找到，返回提示
    display_path = log_path if log_path else search_pattern
    return f"⏳ 正在初始化日志文件...\n(Target: {display_path})"

def stop_generation():
    """触发停止信号"""
    STOP_EVENT.set()
    return "🛑 正在尝试终止任务... (当前正在运行的步骤完成后将停止)", ""

# ================= Gradio 逻辑函数 =================

def upload_csv_file(file):
    if file is None: return gr.update(), "未选择文件"
    filename = os.path.basename(file.name)
    dest_path = os.path.join(NOVEL_CSVS_DIR, filename)
    
    # 覆盖文件
    shutil.copy(file.name, dest_path)
    
    # 修改权限为 666 (rw-rw-rw-)，防止权限问题
    try:
        os.chmod(dest_path, 0o666)
    except Exception as e:
        print(f"Permission modification failed: {e}")

    return gr.update(choices=get_csv_files(), value=filename), f"✅ 已上传/覆盖文件: {filename}"

def on_csv_selected(filename):
    if not filename:
        return None, gr.update(choices=[], value=[]), gr.update(value=""), "", None
    
    path = os.path.join(NOVEL_CSVS_DIR, filename)
    try:
        df = pd.read_csv(path)
        choices = []
        all_ids = []
        completed_count = 0
        
        if 'task_id' in df.columns:
            for idx, row in df.iterrows():
                try:
                    # 🟢 强制转换类型，防止 float/str 混淆
                    tid = int(row['task_id'])
                    status = int(row.get('status', 0))
                except ValueError:
                    continue

                if status == 2:
                    completed_count += 1
                    all_ids.append(tid) 
                    continue
                
                status_icon = "🔄" if status == 1 else "⏳"
                idea = str(row.get('novel_idea', '无主题'))[:15]
                label = f"ID:{tid} [{status_icon}] - {idea}..."
                choices.append((label, tid))
                all_ids.append(tid)
        
        info_text = f"共发现 {len(df)} 个任务。"
        if completed_count > 0: info_text += f" (其中 {completed_count} 个已完成任务已自动隐藏)"
        
        return df, gr.update(choices=choices, value=[]), gr.update(placeholder="输入ID范围，如: 1, 3-5"), info_text, path
    except Exception as e:
        return None, gr.update(choices=[]), gr.update(value=""), f"读取失败: {e}", None

def refresh_csv_logic():
    files = get_csv_files()
    if files:
        return gr.update(choices=files, value=files[0])
    else:
        return gr.update(choices=[], value=None)

def full_refresh():
    files = get_csv_files()
    if not files:
        return gr.update(choices=[], value=None), gr.update(value=None), gr.update(choices=[]), gr.update(value=""), "", None
    
    first_file = files[0]
    df, chk, txt, info, path = on_csv_selected(first_file)
    return gr.update(choices=files, value=first_file), df, chk, txt, info, path

# 🟢 [修改] 执行任务逻辑，加入停止检测
def execute_tasks(csv_filename, check_ids, text_ids, gen_cover):
    # 每次开始前重置停止信号
    STOP_EVENT.clear()

    if not csv_filename:
        yield "请先选择 CSV 文件", ""
        return

    csv_path = os.path.join(NOVEL_CSVS_DIR, csv_filename)
    
    try:
        df = pd.read_csv(csv_path)
        # 确保 task_id 列存在且为 int
        if 'task_id' in df.columns:
             all_existing_ids = [int(x) for x in df['task_id'].tolist() if pd.notna(x)]
        else:
             all_existing_ids = []
    except Exception as e:
        yield f"❌ 读取CSV出错: {e}", ""
        return

    target_ids = set()
    # 处理 checkbox
    for x in check_ids:
        try: target_ids.add(int(x))
        except: pass
    # 处理 textbox
    for x in parse_task_ids(text_ids, all_existing_ids):
        target_ids.add(x)
        
    target_ids = sorted(list(target_ids))
    
    if not target_ids:
        yield "❌ 未选择有效任务 ID", ""
        return

    ids_str = ", ".join(map(str, target_ids))
    msg_init = f"🚀 准备执行 {len(target_ids)} 个任务: [{ids_str}]"
    yield msg_init, ""

    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    dmx_key = os.getenv("DMX_API_KEY")

    tasks_to_run = []
    for idx, row in df.iterrows():
        try:
            tid = int(row.get('task_id', idx+1))
            if tid in target_ids:
                tasks_to_run.append((tid, row.to_dict()))
        except:
            continue

    # 多进程执行
    max_workers = 2 
    executor = ProcessPoolExecutor(max_workers=max_workers)
    
    futures = {}
    for tid, tdata in tasks_to_run:
        # 在提交任务前也检查一下是否已停止
        if STOP_EVENT.is_set():
            break

        f = executor.submit(
            run_single_task_worker,
            tdata, tid, csv_path, deepseek_key, dmx_key, gen_cover
        )
        futures[f] = tid

    finished_ids = []
    total_submitted = len(futures)
    
    # 监控逻辑
    while len(finished_ids) < total_submitted:
        # 🟢 [关键] 检查停止信号
        if STOP_EVENT.is_set():
            # 尝试取消未开始的任务
            executor.shutdown(wait=False, cancel_futures=True)
            yield "⚠️ 任务已手动终止。点击‘开始/继续生成’可继续未完成的任务。", ""
            return

        running_ids = []
        for f, tid in futures.items():
            if f.done():
                if tid not in finished_ids:
                    finished_ids.append(tid)
            else:
                running_ids.append(tid)
        
        run_str = ", ".join(map(str, running_ids))
        done_str = ", ".join(map(str, finished_ids))
        
        progress_str = f"{len(finished_ids)}/{total_submitted}" if total_submitted > 0 else "0/0"
        
        status_update = f"⏳ 正在并发生成 (并发数:{max_workers}): [{run_str}] | ✅ 已完成: [{done_str}] | 总进度: {progress_str}"
        
        # 读取日志 (优先读取正在运行的，否则读取刚完成的)
        current_log = ""
        log_target_id = None
        if running_ids: log_target_id = running_ids[0]
        elif finished_ids: log_target_id = finished_ids[-1]
        
        if log_target_id:
            # 🟢 [关键] 传入 csv_filename 以便精确定位日志路径
            current_log = read_specific_log(log_target_id, csv_filename)

        yield status_update, current_log
        time.sleep(2)

    executor.shutdown()
    yield f"🎉 所有任务执行完毕: [{ids_str}]", "All Done."

def update_excel_sheet(sheet_name, file_path):
    if not sheet_name or not file_path:
        return gr.update()
    try:
        df = pd.read_excel(file_path, sheet_name=sheet_name)
        return gr.update(value=df, visible=True)
    except Exception as e:
        return gr.update()

# ================= Gradio UI 构建 =================

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=7860, help="Gradio server port")
    parser.add_argument("--share", action="store_true", help="Create a public link")
    args = parser.parse_args()

    gradio_title = "📚 AINovel (Gradio)"
    with gr.Blocks(title=gradio_title) as demo:
        gr.Markdown(f"## {gradio_title}")
        
        # Row 1: CSV
        with gr.Row(variant="panel"):
            with gr.Column(scale=1):
                upload_comp = gr.File(label="📂 上传/覆盖 CSV (存入 novel_csvs/)", file_types=[".csv"])
            with gr.Column(scale=1):
                csv_dropdown = gr.Dropdown(choices=get_csv_files(), label="📋 选择 CSV 任务表", interactive=True)
                refresh_csv_btn = gr.Button("🔄 刷新列表", size="sm")
            with gr.Column(scale=2):
                csv_viewer = gr.DataFrame(label="📊 CSV 内容预览", wrap=True)
                csv_download = gr.File(label="⬇️ 下载选中的任务表", interactive=False)

        # Row 2: Config
        with gr.Row(variant="panel"):
            with gr.Column(scale=1):
                gen_cover_box = gr.Checkbox(label="🎨 生成封面", value=False, info="需要配置 DMX_API_KEY")
            with gr.Column(scale=3):
                gr.Markdown("### 🎯 任务选择 (Task IDs)")
                task_info_md = gr.Markdown("请选择要执行的任务（已过滤掉已完成的任务）")
                with gr.Row():
                    id_checklist = gr.CheckboxGroup(label="列表勾选", choices=[])
                    id_textbox = gr.Textbox(label="文本强制指定", placeholder="例: 1, 3-5 (可强制重跑)")

        # Row 3: Run & Stop 
        with gr.Row():
            run_btn = gr.Button("🚀 开始/继续生成", variant="primary", scale=3)
            stop_btn = gr.Button("🛑 终止生成", variant="stop", scale=1)

        # Row 4: Log
        with gr.Row():
            with gr.Column():
                status_bar = gr.Textbox(label="总体状态", show_label=True)
                log_viewer = gr.Code(label="📜 实时日志监控", language=None, lines=15, interactive=False)

        # Row 5: Files
        gr.Markdown("### 📂 成果文件浏览")
        with gr.Row():
            with gr.Column(scale=1):
                file_explorer = gr.FileExplorer(
                    root_dir=NOVELS_DIR,
                    ignore_glob="**/__pycache__/**",
                    label="📁 Novels目录 (点击文件夹刷新；刷新网页以刷新Novels目录)",
                    height=600,
                    file_count="single" 
                )

            with gr.Column(scale=2):
                gr.Markdown("#### 👁️ 文件预览 & 下载")
                selected_path_box = gr.Textbox(label="当前选中文件路径", interactive=False)
                
                sheet_dropdown = gr.Dropdown(label="📑 选择 Excel 工作表", visible=False, interactive=True)
                
                preview_img = gr.Image(label="封面预览", visible=False)
                preview_df = gr.DataFrame(label="表格预览", visible=False)
                preview_txt = gr.Code(label="文本/代码预览", visible=False, language=None)
                download_btn = gr.File(label="⬇️ 下载文件", visible=True)

        # ================= 交互逻辑 =================

        upload_comp.upload(upload_csv_file, inputs=upload_comp, outputs=[csv_dropdown, status_bar])
        
        refresh_csv_btn.click(
            full_refresh, 
            outputs=[csv_dropdown, csv_viewer, id_checklist, id_textbox, task_info_md, csv_download]
        )
        
        demo.load(refresh_csv_logic, outputs=csv_dropdown)

        csv_dropdown.change(
            on_csv_selected,
            inputs=csv_dropdown,
            outputs=[csv_viewer, id_checklist, id_textbox, task_info_md, csv_download]
        )
        
        # 开始按钮
        run_btn.click(
            execute_tasks,
            inputs=[csv_dropdown, id_checklist, id_textbox, gen_cover_box],
            outputs=[status_bar, log_viewer]
        )
        
        # 停止按钮
        stop_btn.click(
            stop_generation,
            inputs=None,
            outputs=[status_bar, log_viewer]
        )
        
        sheet_dropdown.change(
            update_excel_sheet,
            inputs=[sheet_dropdown, selected_path_box],
            outputs=[preview_df]
        )

        def preview_file(file_path):
            if not file_path:
                return [gr.update(visible=False)]*4 + [None, ""]
            
            if isinstance(file_path, list):
                if len(file_path) == 0: return [gr.update(visible=False)]*4 + [None, ""]
                file_path = file_path[0]
            
            if os.path.isdir(file_path):
                return [gr.update(visible=False)]*4 + [None, ""]
                
            ext = os.path.splitext(file_path)[1].lower()
            
            update_img = gr.update(visible=False)
            update_df = gr.update(visible=False)
            update_txt = gr.update(visible=False)
            update_sheet = gr.update(visible=False, choices=[], value=None)
            
            try:
                if ext in ['.png', '.jpg', '.jpeg']:
                    update_img = gr.update(value=file_path, visible=True)
                
                elif ext in ['.csv', '.xlsx', '.xls']:
                    if ext == '.csv':
                        df = pd.read_csv(file_path)
                        update_df = gr.update(value=df, visible=True)
                    else:
                        xls = pd.ExcelFile(file_path)
                        sheet_names = xls.sheet_names
                        if sheet_names:
                            first_sheet = sheet_names[0]
                            df = pd.read_excel(file_path, sheet_name=first_sheet)
                            update_df = gr.update(value=df, visible=True)
                            update_sheet = gr.update(visible=True, choices=sheet_names, value=first_sheet)
                        else:
                             update_df = gr.update(visible=False)
                    
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
                
            return update_img, update_df, update_txt, update_sheet, file_path, file_path

        file_explorer.change(
            preview_file,
            inputs=file_explorer,
            outputs=[preview_img, preview_df, preview_txt, sheet_dropdown, download_btn, selected_path_box]
        )

    print(f"🚀 Starting Gradio server on port {args.port}...")
    demo.queue().launch(
        server_name="0.0.0.0", 
        server_port=args.port, 
        share=args.share,
        allowed_paths=[BASE_DIR],
        theme=gr.themes.Soft()
    )