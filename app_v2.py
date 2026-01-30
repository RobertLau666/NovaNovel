#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI小说自动批量生成系统 (智能补全版)
更新日志：
1. 新增【大纲自检与修复】功能：如果加载的大纲不完整（缺卷/章），会自动调用API补全剩余部分的细纲。
2. 优化【跳过逻辑】：当大纲是新补全时，会自动忽略已存在的“瞎写”txt文件，强制重新生成并覆盖。
3. 保持上下文连贯，继续利用摘要驱动剧情。
"""

import os
import re
import json
import time
from datetime import datetime
import pandas as pd
from openai import OpenAI
from typing import Optional, Dict, Any, List, Tuple
import argparse
import logging
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# ======================== 配置 ========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NOVELS_DIR = os.path.join(BASE_DIR, "novels")
TASKS_CSV = os.path.join(BASE_DIR, "novel_gen_tasks.csv")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
MODEL_NAME = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

MAX_RETRIES = 3
RETRY_DELAY = 5
SUMMARY_SEPARATOR = "#####CHAPTER_SUMMARY_SEPARATOR#####"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# ======================== API 基础函数 ========================
def get_client() -> OpenAI:
    return OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

def call_deepseek(prompt: str, system_prompt: str = None, temperature: float = 0.8) -> Optional[str]:
    client = get_client()
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                temperature=temperature,
                max_tokens=8192,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.warning(f"API调用失败 ({attempt + 1}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
    return None

def extract_json_from_response(text: str) -> Optional[Dict]:
    if not text: return None
    try: return json.loads(text)
    except: pass
    patterns = [r'```json\s*([\s\S]*?)\s*```', r'```\s*([\s\S]*?)\s*```']
    for p in patterns:
        m = re.search(p, text)
        if m:
            try: return json.loads(m.group(1))
            except: continue
    try:
        s, e = text.find('{'), text.rfind('}')
        if s != -1 and e != -1: return json.loads(re.sub(r',(\s*[}\]])', r'\1', text[s:e+1]))
    except: pass
    return None

# ======================== 大纲生成与修复模块 (核心升级) ========================

def generate_global_settings(task: Dict) -> Optional[Dict]:
    """生成宏观设定"""
    prompt = f'''请策划一部{task["novel_type"]}小说。
想法：{task["novel_idea"]}
结构：共{task["roll_num"]}卷，每卷{task["chapter_num"]}章

请返回JSON：
{{
  "作品概述": {{ "小说标题": "《xxx》", "小说简介": "...", "小说卷数": {task["roll_num"]}, "小说章数": {task["chapter_num"]} }},
  "核心设定与人物": {{ "1": {{ "姓名": "xxx", "身份": "..." }} }},
  "卷详细大纲": {{
    "1": {{ "本卷标题": "...", "本卷关键情节": "..." }},
    "2": {{ "本卷标题": "...", "本卷关键情节": "..." }}
    // 请确保生成全部 {task["roll_num"]} 卷
  }}
}}'''
    logger.info("正在生成宏观设定...")
    res = call_deepseek(prompt, "你是一位金牌小说策划。", 0.9)
    return extract_json_from_response(res)

# def generate_volume_chapters(outline: Dict, roll_index: int, chapter_count: int) -> Optional[Dict]:
#     """生成指定卷的章节大纲"""
#     overview = outline.get("作品概述", {})
#     volume_info = outline.get("卷详细大纲", {}).get(str(roll_index), {})
    
#     prompt = f'''基于小说《{overview.get("小说标题")}》，请生成**第{roll_index}卷**的章节大纲。
# 本卷标题：{volume_info.get("本卷标题", f"第{roll_index}卷")}
# 本卷核心情节：{volume_info.get("本卷关键情节", "")}

# 请返回JSON（共{chapter_count}章）：
# {{
#   "{roll_index}-1": {{
#     "本章所属卷次": "{roll_index}",
#     "本章次": "1",
#     "本章标题": "xxx",
#     "本章核心情节梗概": "xxx",
#     "本章关键冲突/爽点": "xxx"
#   }}
#   // ... 直到 {roll_index}-{chapter_count}
# }}'''
#     logger.info(f"正在补全/生成 第 {roll_index} 卷的大纲...")
#     res = call_deepseek(prompt, "你是一位大纲师。", 0.85)
#     return extract_json_from_response(res)


def generate_volume_chapters(outline: Dict, roll_index: int, chapter_count: int) -> Optional[Dict]:
    """
    第二步/补全步骤：根据全局设定 + 卷梗概，生成该卷下的具体章节大纲
    优化：引入人物卡、世界观和完整卷结构，防止人设崩坏。
    """
    # 1. 提取全局信息
    overview = outline.get("作品概述", {})
    characters = outline.get("核心设定与人物", {})
    all_volumes = outline.get("卷详细大纲", {})
    
    # 2. 提取当前卷信息
    current_vol_info = all_volumes.get(str(roll_index), {})
    if not current_vol_info:
        logger.warning(f"没有找到第{roll_index}卷的卷梗概，AI将自由发挥")
    
    # 3. 构建人物上下文 (关键！)
    char_context = ""
    for cid, char in characters.items():
        if isinstance(char, dict):
            name = char.get("姓名", "未知")
            role = char.get("身份", "")
            trait = char.get("核心性格", "")
            # 简化的拼装，节省token但保留核心
            char_context += f"- {name}：{role}，{trait}\n"

    # 4. 构建全书卷结构上下文 (让AI知道当前卷在全书的位置)
    vol_structure = ""
    for k, v in all_volumes.items():
        # 只列出标题和核心冲突，不要太长
        vol_structure += f"第{k}卷：{v.get('本卷标题', '')} (冲突：{v.get('本卷核心冲突', '')})\n"

    # 5. 组合 Prompt
    prompt = f'''你是一位专业的网文大纲师。请根据以下详尽的设定资料，为小说《{overview.get("小说标题")}》的**第{roll_index}卷**创作详细的分章大纲。

【全局设定】
- 类型/文风：{overview.get("类型")} / {overview.get("文风")}
- 核心创意：{overview.get("核心爽点和创意")}
- 简介：{overview.get("小说简介")}

【核心人物表】(请确保人物行为符合人设)
{char_context}

【全书卷结构】
{vol_structure}

【当前生成任务：第{roll_index}卷】
- 本卷标题：{current_vol_info.get("本卷标题", f"第{roll_index}卷")}
- 本卷核心冲突：{current_vol_info.get("本卷核心冲突", "")}
- 本卷关键情节：{current_vol_info.get("本卷关键情节", "")}

【生成要求】
1. 必须生成本卷完整的 **{chapter_count}** 个章节。
2. 严格遵循JSON格式，Key为 "卷数-章数"（如 "{roll_index}-1"）。
3. 每一章必须包含：标题、核心情节梗概（至少3个具体事件点）、关键冲突/爽点。
4. **剧情连贯性**：第一章要承接上一卷（或开篇），最后一章要为下一卷埋伏笔。

请返回JSON数据：
{{
  "{roll_index}-1": {{
    "本章所属卷次": "{roll_index}",
    "本章次": "1",
    "本章标题": "xxx",
    "本章核心情节梗概": "1.主角... 2.反派... 3.结果...",
    "本章关键冲突/爽点": "xxx",
    "本章人物发展/系统奖励": "xxx"
  }}
  // ... 请务必生成到 {roll_index}-{chapter_count}
}}
'''
    logger.info(f"正在基于完整设定生成第 {roll_index} 卷大纲 (共{chapter_count}章)...")
    
    # 这里的 system prompt 强调一致性
    system_prompt = "你是一位严谨的小说主编，擅长把控长篇小说的剧情结构和人物逻辑一致性。"
    
    res = call_deepseek(prompt, system_prompt, temperature=0.85)
    return extract_json_from_response(res)


# def check_and_fix_outline(outline: Dict, task: Dict) -> Tuple[Dict, bool]:
#     """
#     【核心修复逻辑】
#     检查当前 outline 是否包含所有卷的章节。如果不包含，自动补全。
#     返回: (修复后的outline, 是否进行了修复)
#     """
#     updated = False
    
#     # 初始化章大纲字典
#     if "章详细大纲" not in outline:
#         outline["章详细大纲"] = {}
        
#     required_rolls = int(task["roll_num"])
#     required_chapters = int(task["chapter_num"])
    
#     current_chapters = outline["章详细大纲"]
    
#     for r in range(1, required_rolls + 1):
#         # 检查该卷是否已有大纲（检查第一章 key 是否存在作为判断依据）
#         check_key = f"{r}-1"
#         if check_key not in current_chapters:
#             logger.warning(f"检测到缺失 第 {r} 卷大纲，开始补全...")
            
#             # 调用生成函数
#             vol_chapters = None
#             for retry in range(3):
#                 vol_chapters = generate_volume_chapters(outline, r, required_chapters)
#                 if vol_chapters:
#                     break
#                 time.sleep(3)
            
#             if vol_chapters:
#                 outline["章详细大纲"].update(vol_chapters)
#                 updated = True
#                 logger.info(f"✅ 第 {r} 卷大纲补全成功")
#             else:
#                 logger.error(f"❌ 第 {r} 卷大纲补全失败，可能导致后续内容质量下降")
#         else:
#             # logger.info(f"第 {r} 卷大纲完整，跳过。")
#             pass
            
#     return outline, updated

# def check_and_fix_outline(outline: Dict, task: Dict) -> Tuple[Dict, bool]:
#     """
#     【核心修复逻辑 - 优化版】
#     检查当前 outline 是否包含所有卷的章节。
#     优化：增加Key的模糊匹配，防止因为Key格式微小差异导致误判为缺失。
#     """
#     updated = False
    
#     # 确保字典结构存在
#     if "章详细大纲" not in outline:
#         outline["章详细大纲"] = {}
        
#     required_rolls = int(task["roll_num"])
#     required_chapters = int(task["chapter_num"])
    
#     current_chapters = outline.get("章详细大纲", {})
#     existing_keys = list(current_chapters.keys())
    
#     # === 调试信息：看看JSON里到底存了啥 ===
#     if len(existing_keys) > 0:
#         logger.info(f"当前大纲已包含的章节Key示例: {existing_keys[:5]} ... (共{len(existing_keys)}个)")
#     else:
#         logger.warning("当前大纲的'章详细大纲'为空！")
#     # ========================================
    
#     for r in range(1, required_rolls + 1):
#         # 严格检查 Key (例如 "1-1")
#         strict_key = f"{r}-1"
        
#         # 模糊检查：只要存在以 "卷数-" 开头的Key，就视为该卷已存在
#         # 比如 "1-1", "1-2" 只要有一个在，就说明这卷没丢
#         is_volume_exist = False
        
#         # 1. 先检查严格Key
#         if strict_key in current_chapters:
#             is_volume_exist = True
#         else:
#             # 2. 严格Key不在，尝试搜索模糊Key
#             prefix = f"{r}-"
#             for k in existing_keys:
#                 if k.startswith(prefix):
#                     is_volume_exist = True
#                     break
        
#         if not is_volume_exist:
#             logger.warning(f"⚠️ 未检测到 第 {r} 卷的大纲 (未找到 Key: {strict_key} 或 {r}-*)，开始补全...")
            
#             # 调用生成函数 (这里必须使用刚才优化过的含context的版本)
#             vol_chapters = None
#             for retry in range(3):
#                 # 注意：确保你也更新了 generate_volume_chapters 函数
#                 vol_chapters = generate_volume_chapters(outline, r, required_chapters)
#                 if vol_chapters:
#                     break
#                 time.sleep(3)
            
#             if vol_chapters:
#                 outline["章详细大纲"].update(vol_chapters)
#                 updated = True
#                 # 刷新一下 existing_keys，防止下一轮循环误判（虽不影响本逻辑，但好习惯）
#                 existing_keys = list(outline["章详细大纲"].keys())
#                 logger.info(f"✅ 第 {r} 卷大纲补全成功")
#             else:
#                 logger.error(f"❌ 第 {r} 卷大纲补全失败")
#         else:
#             # 只有在Debug模式或者确实想看的时候才打印，避免刷屏
#             # logger.info(f"第 {r} 卷大纲检测存在，跳过生成。")
#             pass
            
#     return outline, updated

def check_and_fix_outline(outline: Dict, task: Dict, outline_path: str, novel_dir: str) -> Tuple[Dict, bool]:
    """
    【核心修复逻辑 - 即时保存版】
    1. 检查大纲是否缺失后续卷。
    2. 如果缺失，调用API基于全局设定补全。
    3. 每补全一卷，立刻写入JSON和Excel，防止程序崩溃导致数据丢失。
    """
    updated = False
    
    # 确保字典结构存在
    if "章详细大纲" not in outline:
        outline["章详细大纲"] = {}
        
    required_rolls = int(task["roll_num"])
    required_chapters = int(task["chapter_num"])
    
    current_chapters = outline.get("章详细大纲", {})
    existing_keys = list(current_chapters.keys())
    
    # 获取书名用于Excel保存
    novel_title = outline.get("作品概述", {}).get("小说标题", "未命名")
    
    # === 调试信息 ===
    if len(existing_keys) > 0:
        logger.info(f"当前大纲已包含章节Key示例: {existing_keys[:3]}... (共{len(existing_keys)}章)")
    
    for r in range(1, required_rolls + 1):
        # 1. 检查该卷是否存在
        strict_key = f"{r}-1"
        is_volume_exist = False
        
        # 严格匹配
        if strict_key in current_chapters:
            is_volume_exist = True
        else:
            # 模糊匹配 (防止key格式差异)
            prefix = f"{r}-"
            for k in existing_keys:
                if k.startswith(prefix):
                    is_volume_exist = True
                    break
        
        # 2. 如果不存在，开始补全
        if not is_volume_exist:
            logger.warning(f"⚠️  未检测到 第 {r} 卷的大纲，开始补全...")
            
            vol_chapters = None
            for retry in range(3):
                # 调用生成函数 (确保你也更新了 generate_volume_chapters 以支持context)
                vol_chapters = generate_volume_chapters(outline, r, required_chapters)
                if vol_chapters:
                    break
                time.sleep(3)
            
            if vol_chapters:
                # 更新内存对象
                outline["章详细大纲"].update(vol_chapters)
                updated = True
                existing_keys = list(outline["章详细大纲"].keys()) # 刷新Key列表
                
                logger.info(f"✅ 第 {r} 卷大纲补全成功，正在执行【即时保存】...")
                
                # === 即时保存到 JSON ===
                try:
                    with open(outline_path, 'w', encoding='utf-8') as f:
                        json.dump(outline, f, ensure_ascii=False, indent=2)
                except Exception as e:
                    logger.error(f"JSON即时保存失败: {e}")

                # === 即时保存到 Excel ===
                try:
                    save_outline_to_excel(outline, novel_dir, novel_title)
                except Exception as e:
                    logger.error(f"Excel即时保存失败: {e}")
                    
                logger.info(f"💾 第 {r} 卷已写入硬盘 (JSON + Excel)")
                
            else:
                logger.error(f"❌ 第 {r} 卷大纲补全失败")
        else:
            # logger.info(f"第 {r} 卷已存在，跳过。")
            pass
            
    return outline, updated

def save_outline_to_excel(outline: Dict, novel_dir: str, novel_title: str) -> str:
    """保存Excel，注意类型处理"""
    excel_path = os.path.join(novel_dir, "outline.xlsx")
    
    # 尝试保留原有的 Excel 数据（主要是保留已生成的 chapter_done 状态）
    # 但如果大纲发生了"修复"（新增了行），我们需要智能合并
    old_status = {}
    if os.path.exists(excel_path):
        try:
            old_df = pd.read_excel(excel_path, sheet_name="章详细大纲", index_col=0, dtype=object)
            for idx, row in old_df.iterrows():
                if row.get('chapter_done') == 1:
                    old_status[idx] = {
                        'chapter_done': 1,
                        'summary': row.get('summary', '')
                    }
        except:
            pass

    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        for sheet_name, data in outline.items():
            if isinstance(data, dict) and sheet_name == "章详细大纲":
                # 转为DataFrame
                df = pd.DataFrame.from_dict(data, orient='index')
                
                # 初始化列
                df['chapter_done'] = 0
                df['summary'] = ''
                df['summary'] = df['summary'].astype(object)
                
                # 恢复旧状态 (只恢复那些在大纲里依然存在的章节)
                for idx in df.index:
                    if idx in old_status:
                        df.at[idx, 'chapter_done'] = old_status[idx]['chapter_done']
                        df.at[idx, 'summary'] = old_status[idx]['summary']
                
                df.to_excel(writer, sheet_name=sheet_name, index=True)
            elif isinstance(data, dict):
                 # 处理其他嵌套字典
                first_val = next(iter(data.values()), None)
                if isinstance(first_val, dict):
                    df = pd.DataFrame.from_dict(data, orient='index')
                else:
                    df = pd.DataFrame([data])
                df.to_excel(writer, sheet_name=sheet_name[:31])
            else:
                pd.DataFrame([{"内容": data}]).to_excel(writer, sheet_name=sheet_name[:31])
    
    logger.info(f"Excel大纲已更新: {excel_path}")
    return excel_path

# ======================== 内容生成模块 ========================

def build_chapter_context(outline: Dict, roll_num: int, chapter_num: int, prev_chapters: list) -> Tuple[str, str]:
    chapter_key = f"{roll_num}-{chapter_num}"
    chapters = outline.get("章详细大纲", {})
    
    # 如果刚补全了大纲，这里就能取到真实数据了
    chapter_outline = chapters.get(chapter_key, {})
    
    # 如果还是取不到（极低概率），给个兜底
    if not chapter_outline:
        chapter_title = f"第{chapter_num}章"
        core_plot = "剧情自由发展"
    else:
        chapter_title = chapter_outline.get("本章标题", f"第{chapter_num}章")
        core_plot = chapter_outline.get("本章核心情节梗概", "")

    volume_info = outline.get("卷详细大纲", {}).get(str(roll_num), {})
    
    context = f"""【小说信息】
书名：{outline.get("作品概述", {}).get("小说标题")}
当前卷：{volume_info.get("本卷标题", "")} - {volume_info.get("本卷关键情节", "")}

【本章大纲】
章节：第{roll_num}卷 第{chapter_num}章《{chapter_title}》
核心情节：{core_plot}
关键冲突：{chapter_outline.get("本章关键冲突/爽点", "")}
"""
    if prev_chapters:
        context += "\n【前情提要】\n"
        for prev in prev_chapters[-3:]:
            context += f"第{prev['roll']}卷{prev['chapter']}章：{prev['summary']}\n"
            
    return context, chapter_title

def post_process_content(content: str, roll: int, chapter: int, title: str) -> str:
    lines = content.split('\n')
    processed = [f"第{roll}卷 第{chapter}章：{title}\n"]
    for line in lines:
        line = line.strip().replace("#####", "")
        if line and line not in title and "SUMMARY" not in line:
            processed.append(f"\u3000\u3000{line}\n")
    return "\n".join(processed)

def generate_chapter(outline: Dict, roll: int, chapter: int, prev_chapters: list, word_num: int) -> Tuple[Optional[str], Optional[str]]:
    context, title = build_chapter_context(outline, roll, chapter, prev_chapters)
    
    prompt = f"""{context}
请撰写正文（约{word_num}字）。
要求：场景描写细腻，对话符合人设，严禁流水账。
格式：正文结束后，换行输出 "{SUMMARY_SEPARATOR}"，再写300字摘要。
"""
    logger.info(f"正在生成: {roll}-{chapter} {title}")
    res = call_deepseek(prompt, "你是一位网文大神。", 0.85)
    if not res: return None, None
    
    parts = res.split(SUMMARY_SEPARATOR)
    content = parts[0].strip()
    summary = parts[1].strip() if len(parts) > 1 else content[-400:]
    
    return post_process_content(content, roll, chapter, title), summary

def generate_chapter_summary(content: str) -> str:
    return call_deepseek(f"生成300字摘要：\n{content[:2000]}", temperature=0.3) or "..."

# ======================== 进度读取 ========================
def load_progress(excel_path: str) -> Dict:
    prog = {"done_set": set(), "prev_chapters": []}
    if not os.path.exists(excel_path): return prog
    try:
        df = pd.read_excel(excel_path, sheet_name="章详细大纲", index_col=0, dtype=object)
        for idx, row in df.iterrows():
            if row.get('chapter_done') == 1:
                r, c = int(row['本章所属卷次']), int(row['本章次'])
                prog["done_set"].add(f"{r}-{c}")
                if pd.notna(row.get('summary')):
                    prog["prev_chapters"].append({
                        "roll": r, "chapter": c, 
                        "summary": str(row['summary'])
                    })
    except: pass
    return prog

def save_progress(excel_path: str, r: int, c: int, summary: str):
    try:
        with pd.ExcelFile(excel_path) as xls:
            sheets = {s: pd.read_excel(xls, s, index_col=0) for s in xls.sheet_names}
        df = sheets["章详细大纲"]
        df['summary'] = df['summary'].astype(object)
        mask = (df['本章所属卷次'].astype(str) == str(r)) & (df['本章次'].astype(str) == str(c))
        if mask.any():
            df.loc[mask, 'chapter_done'] = 1
            df.loc[mask, 'summary'] = summary
        with pd.ExcelWriter(excel_path, engine='openpyxl') as w:
            for n, d in sheets.items(): d.to_excel(w, sheet_name=n)
    except Exception as e:
        logger.error(f"保存进度失败: {e}")

# ======================== 主流程 ========================
# def process_single_task(task: Dict, task_id: int, csv_path: str) -> bool:
#     logger.info(f"Processing Task {task_id}...")
#     temp_dir = os.path.join(NOVELS_DIR, f"_temp_task_{task_id}")
#     os.makedirs(temp_dir, exist_ok=True)
    
#     # 1. 大纲加载/新建
#     outline_path = os.path.join(temp_dir, "outline.json")
#     outline = None
#     if os.path.exists(outline_path):
#         with open(outline_path, 'r', encoding='utf-8') as f: outline = json.load(f)
#     else:
#         outline = generate_global_settings(task)
#         if not outline: return False
    
#     # 2. 【关键步骤】大纲自检与修复
#     # 如果是旧大纲（只有第一卷），这里会自动检测并补全后面几卷
#     outline, was_repaired = check_and_fix_outline(outline, task)
    
#     # 保存最新大纲
#     with open(outline_path, 'w', encoding='utf-8') as f:
#         json.dump(outline, f, ensure_ascii=False, indent=2)
    
#     # 3. 准备目录和Excel
#     title = outline.get("作品概述", {}).get("小说标题", f"Task_{task_id}")
#     clean_title = re.sub(r'[\\/*?:"<>|]', "", title)
#     final_dir = os.path.join(NOVELS_DIR, clean_title)
    
#     work_dir = final_dir if os.path.exists(final_dir) else temp_dir
#     if work_dir == temp_dir and not os.path.exists(final_dir):
#         os.rename(temp_dir, final_dir)
#         work_dir = final_dir
        
#     excel_path = os.path.join(work_dir, "outline.xlsx")
#     # 如果修复了大纲，或者Excel不存在，都需要重新生成/更新Excel
#     if was_repaired or not os.path.exists(excel_path):
#         save_outline_to_excel(outline, work_dir, clean_title)
        
#     content_dir = os.path.join(work_dir, "content")
#     os.makedirs(content_dir, exist_ok=True)
    
#     # 4. 生成正文
#     progress = load_progress(excel_path)
#     done_set = progress["done_set"]
#     prev_chapters = progress["prev_chapters"]
    
#     roll_num, chap_num = int(task["roll_num"]), int(task["chapter_num"])
    
#     for r in range(1, roll_num + 1):
#         for c in range(1, chap_num + 1):
#             key = f"{r}-{c}"
#             txt_path = os.path.join(content_dir, f"{r}-{c}.txt")
            
#             # 【关键跳过逻辑优化】
#             # 只有当 Excel 显示"已完成"时才跳过。
#             # 如果 Excel 显示"未完成" (0)，即使 txt 文件存在，也视为无效文件（可能是无大纲时瞎写的），强制重写。
#             if key in done_set:
#                 if key not in [f"{p['roll']}-{p['chapter']}" for p in prev_chapters]:
#                     # 补录内存上下文
#                     if os.path.exists(txt_path):
#                         with open(txt_path, 'r', encoding='utf-8') as f: 
#                             s = generate_chapter_summary(f.read())
#                         prev_chapters.append({"roll":r,"chapter":c,"summary":s})
#                 logger.info(f"跳过已完成: {key}")
#                 continue
            
#             # 生成
#             content, summary = generate_chapter(outline, r, c, prev_chapters, int(task["word_num"]))
#             if content:
#                 with open(txt_path, 'w', encoding='utf-8') as f: f.write(content)
#                 save_progress(excel_path, r, c, summary)
#                 done_set.add(key)
#                 prev_chapters.append({"roll":r,"chapter":c,"summary":summary})
#                 logger.info(f"已生成: {key}")
#                 time.sleep(2)
#             else:
#                 logger.error(f"生成失败: {key}")
                
#     return True

def process_single_task(task: Dict, task_id: int, csv_path: str) -> bool:
    logger.info(f"\n{'='*60}")
    logger.info(f"开始处理任务 task_id={task_id}")
    
    # 1. 路径锁定 (强制使用 task_{id} 作为目录名，方便断点续传)
    novel_dir = os.path.join(NOVELS_DIR, f"task_{task_id}")
    os.makedirs(novel_dir, exist_ok=True)
    logger.info(f"工作目录已锁定: {novel_dir}")

    # 2. 大纲加载/新建
    outline_path = os.path.join(novel_dir, "outline.json")
    outline = None
    
    if os.path.exists(outline_path):
        logger.info("检测到本地 outline.json，正在加载...")
        try:
            with open(outline_path, 'r', encoding='utf-8') as f: 
                outline = json.load(f)
        except Exception as e:
            logger.error(f"大纲文件损坏，正在尝试重新生成: {e}")
            outline = None
            
    if not outline:
        logger.info("准备生成新的宏观设定...")
        outline = generate_global_settings(task)
        if not outline: 
            return False
    
    # 3. 【大纲自检与修复】(自动补全缺失的卷，并即时保存)
    # 传入 outline_path 和 novel_dir 是为了在补全过程中就能实时写入硬盘
    outline, was_repaired = check_and_fix_outline(outline, task, outline_path, novel_dir)
    
    # 再次保存以防万一
    with open(outline_path, 'w', encoding='utf-8') as f:
        json.dump(outline, f, ensure_ascii=False, indent=2)
    
    # 获取书名
    novel_title = outline.get("作品概述", {}).get("小说标题", f"Task_{task_id}")
    logger.info(f"当前小说标题: {novel_title}")
    
    # 4. 准备 Excel
    excel_path = os.path.join(novel_dir, "outline.xlsx")
    # 如果修复了大纲(was_repaired=True) 或者 Excel不存在，都需要刷新Excel
    if was_repaired or not os.path.exists(excel_path):
        save_outline_to_excel(outline, novel_dir, novel_title)
        
    content_dir = os.path.join(novel_dir, "content")
    os.makedirs(content_dir, exist_ok=True)
    
    # 5. 准备生成正文
    progress = load_progress(excel_path)
    done_set = progress["done_set"]      # 集合: {"1-1", "1-2"...}
    prev_chapters = progress["prev_chapters"] # 列表: [{"roll":1,"chapter":1,"summary":"..."}, ...]
    
    roll_num = int(task["roll_num"])
    chap_num = int(task["chapter_num"])
    total_chapters = roll_num * chap_num
    
    # 6. 正文生成循环
    for r in range(1, roll_num + 1):
        for c in range(1, chap_num + 1):
            key = f"{r}-{c}"
            txt_path = os.path.join(content_dir, f"{r}-{c}.txt")
            
            # --- 跳过逻辑 ---
            # 只有 Excel 里标记为“已完成(1)”才跳过
            if key in done_set:
                # 检查是否需要补录摘要到内存(用于后续章节的上下文)
                # 查找内存里是否已经有这一章的摘要
                current_chap_context = next((item for item in prev_chapters if str(item["roll"]) == str(r) and str(item["chapter"]) == str(c)), None)
                
                if not current_chap_context:
                    # 内存里没有，但Excel说做完了，尝试读取txt文件补录摘要
                    if os.path.exists(txt_path):
                        try:
                            with open(txt_path, 'r', encoding='utf-8') as f: 
                                content_text = f.read()
                            # 简单的摘要生成，不浪费API，直接取末尾，或者调用API生成
                            # 这里为了省钱，如果文件很大，可以仅截取。
                            # 如果想要高质量续写，建议调用 generate_chapter_summary(content_text)
                            # 这里默认使用截取策略，为了速度
                            s = content_text[-500:] 
                            # 如果需要更精准，可以取消下面注释开启API生成摘要:
                            # s = generate_chapter_summary(content_text, r, c)
                            
                            prev_chapters.append({"roll":r, "chapter":c, "summary":s})
                        except Exception as e:
                            logger.warning(f"补录摘要失败 {key}: {e}")
                    else:
                        # Excel标记完成但文件不存在，视为未完成，不跳过
                        pass
                
                logger.info(f"跳过已完成: 第{r}卷 第{c}章")
                continue
            
            # --- 生成逻辑 ---
            # 如果是刚补全的大纲，Key "2-1" 已经在 outline 变量里了，这里能正常取到
            content, summary = generate_chapter(outline, r, c, prev_chapters, int(task["word_num"]))
            
            if content:
                # 1. 写入正文
                with open(txt_path, 'w', encoding='utf-8') as f: 
                    f.write(content)
                
                # 2. 写入进度到 Excel
                save_progress(excel_path, r, c, summary)
                
                # 3. 更新内存状态
                done_set.add(key)
                prev_chapters.append({"roll":r, "chapter":c, "summary":summary})
                
                logger.info(f"✅ 已生成: 第{r}卷 第{c}章")
                
                # 休息一下，避免API超频
                time.sleep(2)
            else:
                logger.error(f"❌ 生成失败: 第{r}卷 第{c}章")
                
    logger.info(f"🎉 任务 task_{task_id} 全部流程结束。")
    return True


# ======================== 辅助函数 ========================
def update_task_csv(csv_path, task_id, status):
    try:
        df = pd.read_csv(csv_path)
        if 'status' in df.columns:
            df.loc[df['task_id'] == task_id, 'status'] = status
            df.to_csv(csv_path, index=False)
    except: pass

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--file', default=TASKS_CSV)
    parser.add_argument('-i', '--ids', type=str)
    parser.add_argument('--api-key')
    args = parser.parse_args()
    
    global DEEPSEEK_API_KEY
    if args.api_key: DEEPSEEK_API_KEY = args.api_key
    if not DEEPSEEK_API_KEY: 
        print("Error: No API Key")
        return

    if not os.path.exists(args.file):
        print(f"File not found: {args.file}")
        return

    df = pd.read_csv(args.file)
    target_ids = []
    if args.ids:
        for p in args.ids.split(','):
            if '-' in p: s,e = map(int, p.split('-')); target_ids.extend(range(s,e+1))
            else: target_ids.append(int(p))
            
    for idx, row in df.iterrows():
        tid = row.get('task_id', idx+1)
        if target_ids and tid not in target_ids: continue
        if row.get('status') == 2: continue
        
        update_task_csv(args.file, tid, 1)
        success = process_single_task(row.to_dict(), tid, args.file)
        update_task_csv(args.file, tid, 2 if success else 3)

if __name__ == "__main__":
    main()