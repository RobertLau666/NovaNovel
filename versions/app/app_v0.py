#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI小说自动批量生成系统
支持断点续传，调用DeepSeek API生成小说大纲和章节内容
"""

import os
import re
import json
import time
from datetime import datetime
import pandas as pd
from openai import OpenAI
from typing import Optional, Dict, Any, List
import argparse
import logging
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# ======================== 配置 ========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NOVELS_DIR = os.path.join(BASE_DIR, "novels")
TASKS_CSV = os.path.join(BASE_DIR, "novel_gen_tasks.csv")

# DeepSeek API 配置（从 .env 文件读取）
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
MODEL_NAME = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# 生成配置
MAX_RETRIES = 3
RETRY_DELAY = 5  # 秒

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# ======================== DeepSeek API 客户端 ========================
def get_client() -> OpenAI:
    """获取DeepSeek API客户端"""
    return OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)


def call_deepseek(prompt: str, system_prompt: str = None, temperature: float = 0.8) -> Optional[str]:
    """调用DeepSeek API"""
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
            logger.warning(f"API调用失败 (尝试 {attempt + 1}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
    return None


def extract_json_from_response(text: str) -> Optional[Dict]:
    """从API响应中提取JSON"""
    if not text:
        return None
    
    # 尝试直接解析
    try:
        return json.loads(text)
    except:
        pass
    
    # 尝试从markdown代码块中提取
    patterns = [
        r'```json\s*([\s\S]*?)\s*```',
        r'```\s*([\s\S]*?)\s*```',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                json_str = match.group(1)
                return json.loads(json_str)
            except:
                continue
    
    # 尝试找到最外层的 { } 并解析
    try:
        # 找到第一个 { 和最后一个 }
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            json_str = text[start:end + 1]
            return json.loads(json_str)
    except:
        pass
    
    # 尝试修复常见的 JSON 错误（如多余的逗号）
    try:
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1:
            json_str = text[start:end + 1]
            # 移除对象末尾的多余逗号
            json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
            return json.loads(json_str)
    except:
        pass
    
    return None


# ======================== 大纲生成 ========================
def generate_outline(task: Dict) -> Optional[Dict]:
    """生成小说大纲"""
    prompt = f'''请参考网络热门或者排行榜靠前的{task["novel_type"]}小说的设定和剧情爽点，写一部小说。

小说想法：{task["novel_idea"]}
文风：{task["write_style"]}
目标读者：{task["target_reader"]}
小说结构：共{task["roll_num"]}卷，每卷{task["chapter_num"]}章，每章约{task["word_num"]}字
特殊要求：{task["special_requirements"]}

请生成完整的故事大纲，严格返回以下JSON格式（不要有任何额外说明）：

{{
  "作品概述": {{
    "小说标题": "《xxx》",
    "小说副标题": "xxx",
    "小说简介": "该小说讲述了xxx的故事",
    "类型": "{task["novel_type"]}",
    "文风": "{task["write_style"]}",
    "核心爽点和创意": "xxx",
    "市场分析与亮点总结": "xxx",
    "小说卷数": {task["roll_num"]},
    "小说章数": {task["chapter_num"]},
    "每章字数": {task["word_num"]}
  }},
  "核心设定与人物": {{
    "1": {{
      "姓名": "xxx",
      "身份/职位": "xxx",
      "年龄": "xx岁",
      "外貌特征": "xxx",
      "核心性格": "xxx",
      "成长弧光": "xxx",
      "与主角关系": "主角"
    }},
    "2": {{
      "姓名": "xxx",
      "身份/职位": "xxx",
      "年龄": "xx岁",
      "外貌特征": "xxx",
      "核心性格": "xxx",
      "成长弧光": "xxx",
      "与主角关系": "xxx"
    }}
  }},
  "卷详细大纲": {{
    "1": {{
      "本卷次": "1",
      "本卷标题": "xxx",
      "本卷核心冲突": "xxx",
      "本卷关键情节": "xxx",
      "本卷目标": "xxx"
    }}
  }},
  "章详细大纲": {{
    "1-1": {{
      "本章所属卷次": "1",
      "本章次": "1",
      "本章标题": "xxx",
      "本章核心情节梗概": "xxx",
      "本章关键冲突/爽点": "xxx",
      "本章人物发展/系统奖励": "xxx"
    }},
    "1-2": {{
      "本章所属卷次": "1",
      "本章次": "2",
      "本章标题": "xxx",
      "本章核心情节梗概": "xxx",
      "本章关键冲突/爽点": "xxx",
      "本章人物发展/系统奖励": "xxx"
    }},
    "2-1": {{
      "本章所属卷次": "2",
      "本章次": "1",
      "本章标题": "xxx",
      "本章核心情节梗概": "xxx",
      "本章关键冲突/爽点": "xxx",
      "本章人物发展/系统奖励": "xxx"
    }}
  }}
}}

重要：
1. 根据卷数{task["roll_num"]}和章数{task["chapter_num"]}，生成对应数量的卷和章大纲
2. 总章数 = 卷数 × 每卷章数 = {int(task["roll_num"]) * int(task["chapter_num"])}章
3. 章详细大纲的key格式为"卷次-章次"，如"1-1"表示第1卷第1章，"2-3"表示第2卷第3章
4. 每卷的章次都从1开始编号（不是全局连续编号）
5. 人物至少3-5个主要角色
6. 只返回JSON，不要任何其他内容
'''

    system_prompt = "你是一位专业的网络小说策划师，擅长创作热门爆款小说大纲。请严格按照用户要求的JSON格式返回结果。"
    
    logger.info("正在生成小说大纲...")
    response = call_deepseek(prompt, system_prompt, temperature=0.9)
    
    if not response:
        logger.error("大纲生成失败：API无响应")
        return None
    
    outline = extract_json_from_response(response)
    if not outline:
        logger.error("大纲生成失败：JSON解析失败")
        # 保存原始响应到文件，方便调试
        debug_file = os.path.join(NOVELS_DIR, f"_debug_response_{int(time.time())}.txt")
        with open(debug_file, 'w', encoding='utf-8') as f:
            f.write(response)
        logger.error(f"原始响应已保存到: {debug_file}")
        logger.info(f"响应前500字符: {response[:500]}...")
        return None
    
    return outline


def save_outline_to_excel(outline: Dict, novel_dir: str, novel_title: str) -> str:
    """将大纲保存为Excel文件（多Sheet），包含章节进度列"""
    excel_path = os.path.join(novel_dir, "outline.xlsx")
    
    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        for sheet_name, data in outline.items():
            if isinstance(data, dict):
                # 检查是否是嵌套字典（如人物、卷、章）
                first_value = next(iter(data.values()), None)
                if isinstance(first_value, dict):
                    # 转换为DataFrame（每个key作为一行）
                    df = pd.DataFrame.from_dict(data, orient='index')
                    
                    # 对于"章详细大纲"，添加进度列
                    if sheet_name == "章详细大纲":
                        if 'chapter_done' not in df.columns:
                            df['chapter_done'] = 0
                        if 'summary' not in df.columns:
                            df['summary'] = ''
                else:
                    # 单层字典，转为单行
                    df = pd.DataFrame([data])
            else:
                df = pd.DataFrame([{"内容": data}])
            
            # Excel Sheet名称最多31字符
            safe_name = sheet_name[:31]
            df.to_excel(writer, sheet_name=safe_name, index=True)
    
    logger.info(f"大纲已保存: {excel_path}")
    return excel_path


# ======================== 章节生成 ========================
def build_chapter_context(outline: Dict, roll_num: int, chapter_num: int, prev_chapters: list) -> str:
    """构建章节生成的上下文信息"""
    overview = outline.get("作品概述", {})
    characters = outline.get("核心设定与人物", {})
    volumes = outline.get("卷详细大纲", {})
    chapters = outline.get("章详细大纲", {})
    
    # 章节key格式：卷次-章次
    chapter_key = f"{roll_num}-{chapter_num}"
    
    # 获取当前章节大纲
    chapter_outline = chapters.get(chapter_key, {})
    volume_outline = volumes.get(str(roll_num), {})
    
    context = f"""【小说基本信息】
标题：{overview.get("小说标题", "")}
类型：{overview.get("类型", "")}
文风：{overview.get("文风", "")}
简介：{overview.get("小说简介", "")}
核心爽点：{overview.get("核心爽点和创意", "")}

【主要人物设定】
"""
    for cid, char in characters.items():
        if isinstance(char, dict):
            context += f"- {char.get('姓名', '未知')}：{char.get('身份/职位', '')}，{char.get('核心性格', '')}，与主角关系：{char.get('与主角关系', '')}\n"

    context += f"""
【当前卷信息】第{roll_num}卷：{volume_outline.get("本卷标题", "")}
核心冲突：{volume_outline.get("本卷核心冲突", "")}
关键情节：{volume_outline.get("本卷关键情节", "")}
本卷目标：{volume_outline.get("本卷目标", "")}

【当前章节大纲】第{roll_num}卷 第{chapter_num}章：{chapter_outline.get("本章标题", "")}
核心情节：{chapter_outline.get("本章核心情节梗概", "")}
关键冲突/爽点：{chapter_outline.get("本章关键冲突/爽点", "")}
人物发展：{chapter_outline.get("本章人物发展/系统奖励", "")}
"""

    # # 添加前几章的摘要（最近2章）
    # if prev_chapters:
    #     context += "\n【前情提要】\n"
    #     for prev in prev_chapters[-2:]:
    #         context += f"第{prev['roll']}卷第{prev['chapter']}章《{prev['title']}》：{prev['summary']}\n"
    
    # 修改：上下文包含最近 4 章的摘要，不仅是 2 章
    # 这样能保证短期的剧情连贯性更强
    if prev_chapters:
        context += "\n【前情提要（最近剧情回顾）】\n"
        # 获取最后 4 个章节的摘要
        recent_summaries = prev_chapters[-4:]
        for prev in recent_summaries:
            context += f"Draft-第{prev['roll']}卷第{prev['chapter']}章：{prev['summary']}\n"

    return context, chapter_outline.get("本章标题", f"第{chapter_num}章")

# 1. 新增一个后处理函数
def post_process_content(content: str, roll: int, chapter: int, title: str) -> str:
    """对AI生成的内容进行格式化清洗"""
    # 移除可能的 Markdown 代码块标记
    content = re.sub(r'^```.*?\n', '', content, flags=re.MULTILINE)
    content = re.sub(r'```$', '', content, flags=re.MULTILINE)
    
    lines = content.split('\n')
    processed_lines = []
    
    # 构建标准标题
    full_title = f"第{roll}卷 第{chapter}章：{title}"
    processed_lines.append(full_title)
    processed_lines.append("") # 标题后空一行
    
    for line in lines:
        line = line.strip()
        # 跳过空行、跳过AI可能重复输出的标题
        if not line or line == full_title or line in title:
            continue
            
        # 核心：给正文每一段强制加上全角缩进
        processed_lines.append(f"\u3000\u3000{line}")
        processed_lines.append("") # 段落之间空一行，方便手机阅读
        
    return "\n".join(processed_lines)

def generate_chapter(outline: Dict, roll_num: int, chapter_num: int, 
                     prev_chapters: list, word_num: int) -> Optional[str]:
    """生成单章内容"""
    context, chapter_title = build_chapter_context(outline, roll_num, chapter_num, prev_chapters)
    
    prompt = f"""{context}

请你扮演一位白金级小说作家，根据以上设定和大纲，撰写第{roll_num}卷第{chapter_num}章的完整内容。

【写作高阶要求】
1. **沉浸式描写**：不要只写“他打了一拳”，要写拳风的呼啸、周围空气的扭曲、围观者的惊骇表情。
2. **强画面感**：多用动词和名词，少用形容词。不要写“他很生气”，要写“他捏碎了手中的茶杯，滚烫的茶水顺着指缝流下，他却浑然不觉”。
3. **拒绝流水账**：严禁出现“经过一番苦战”、“几天后”这种省略句。必须将过程细致地通过动作拆解呈现出来。
4. **对话自然**：反派不要无脑嘲讽，要有自己的逻辑；主角说话要符合人设。
5. **节奏把控**：打斗场景要短句短段，营造紧迫感；情感场景要细腻铺陈。
6. **环境渲染**：开篇需通过环境描写（光影、声音、气味）烘托氛围。在对话和动作中穿插环境描写（风声、光影、气味），让场景“活”起来。

其他要求：
1. 字数约{word_num}字左右。
2. 严格按照章节大纲的情节推进。
3. 与前文保持连贯（如有前情提要）。
4. 体现设定的文风特色。
5. 保持词汇的丰富性，在描述相似场景时使用全新的比喻和修辞。
6. 确保因果关系严密，人物行为必须符合其动机和当前处境。
7. 确保逻辑连贯，人物性格符合设定。
8. 不要出现错别字，语法错误，标点符号错误。
9. 注意格式，不要出现段落混乱，段落重复，段落缺失。
10. 段落要有缩进，段首空两格（全角空格）。
11. 直接输出正文，不要标题，不要前言，不要“好的”之类的废话。 
12. 章节开头格式：
   第{roll_num}卷 第{chapter_num}章：{chapter_title}
   
   （正文内容）

请直接输出章节内容，不要有任何额外说明。
"""

    system_prompt = f"你是一位专业的网络小说作家，擅长创作{outline.get('作品概述', {}).get('类型', '')}类型的小说。请按照大纲设定撰写精彩的章节内容，文风要求：{outline.get('作品概述', {}).get('文风', '')}。"
    
    logger.info(f"正在生成: 第{roll_num}卷 第{chapter_num}章...")
    raw_content = call_deepseek(prompt, system_prompt, temperature=0.85)
    if raw_content:
        return post_process_content(raw_content, roll_num, chapter_num, chapter_title)
    return None

# def extract_chapter_summary(content: str, max_len: int = 200) -> str:
#     """提取章节摘要（用于下一章的前情提要）"""
#     # 取最后几段作为摘要
#     lines = [l.strip() for l in content.split('\n') if l.strip()]
#     summary_lines = lines[-3:] if len(lines) > 3 else lines
#     summary = ' '.join(summary_lines)
#     return summary[:max_len] + "..." if len(summary) > max_len else summary

def generate_chapter_summary(content: str, roll: int, chapter: int) -> str:
    """
    调用 AI 对本章内容进行精准总结，用于下一章的上下文
    """
    prompt = f"""
请阅读以下小说章节内容（第{roll}卷 第{chapter}章），生成一份**剧情摘要**。
这份摘要将作为AI生成下一章的“前情提要”，所以必须包含关键的逻辑信息。

【原文内容】
{content}

【摘要要求】
1. **控制字数**：300字以内，言简意赅。
2. **核心事件**：主角做了什么？遇到了谁？打败了谁？
3. **状态变更**：
   - 获得的物品/功法/能力（如有）。
   - 人际关系变化（结仇/结盟）。
   - 主角当前的身体状态（受伤/升级）和所处位置。
4. **伏笔记录**：如果有未解开的谜题或刚刚埋下的伏笔，请记录下来。

请直接输出摘要内容，不要有任何前缀或解释。
"""
    
    # 使用较低的 temperature 保证总结的客观准确性
    summary = call_deepseek(prompt, temperature=0.3)
    
    if not summary:
        # 如果API调用失败，作为保底方案，还是截取最后一部分，但稍微长一点
        logger.warning(f"摘要生成失败，使用从末尾截取作为保底: {roll}-{chapter}")
        return content[-800:] 
        
    return summary

# ======================== 进度管理（断点续传） ========================
def update_outline_done(csv_path: str, task_id: int, done: bool = True):
    """更新 CSV 中的 outline_done 状态"""
    df = pd.read_csv(csv_path, dtype={'gen_start_time': str, 'gen_end_time': str})
    df['gen_start_time'] = df['gen_start_time'].astype(str).replace('nan', '')
    df['gen_end_time'] = df['gen_end_time'].astype(str).replace('nan', '')
    
    mask = df['task_id'] == task_id
    if mask.any():
        df.loc[mask, 'outline_done'] = 1 if done else 0
        df.to_csv(csv_path, index=False)


def get_outline_done(csv_path: str, task_id: int) -> bool:
    """从 CSV 获取 outline_done 状态"""
    df = pd.read_csv(csv_path)
    mask = df['task_id'] == task_id
    if mask.any():
        return int(df.loc[mask, 'outline_done'].iloc[0]) == 1
    return False


def load_chapter_progress_from_excel(excel_path: str) -> Dict:
    """从 Excel 的"章详细大纲" Sheet 加载章节进度"""
    progress = {"chapters_done": [], "prev_chapters": []}
    
    if not os.path.exists(excel_path):
        return progress
    
    try:
        df = pd.read_excel(excel_path, sheet_name="章详细大纲", index_col=0)
        
        for idx, row in df.iterrows():
            chapter_done = row.get('chapter_done', 0)
            if pd.notna(chapter_done) and int(chapter_done) == 1:
                roll = int(row.get('本章所属卷次', 0))
                chapter = int(row.get('本章次', 0))
                progress["chapters_done"].append(f"{roll}-{chapter}")
                
                # 加载摘要用于前情提要
                summary = row.get('summary', '')
                if pd.notna(summary) and summary:
                    progress["prev_chapters"].append({
                        "roll": roll,
                        "chapter": chapter,
                        "title": row.get('本章标题', ''),
                        "summary": str(summary)
                    })
    except Exception as e:
        logger.warning(f"读取 Excel 进度失败: {e}")
    
    return progress


def save_chapter_progress_to_excel(excel_path: str, roll: int, chapter: int, summary: str):
    """保存章节进度到 Excel 的"章详细大纲" Sheet"""
    if not os.path.exists(excel_path):
        logger.warning(f"Excel 文件不存在: {excel_path}")
        return
    
    try:
        # 读取所有 Sheet
        with pd.ExcelFile(excel_path) as xls:
            all_sheets = {sheet: pd.read_excel(xls, sheet_name=sheet, index_col=0) 
                         for sheet in xls.sheet_names}
        
        # 更新"章详细大纲" Sheet
        if "章详细大纲" in all_sheets:
            df = all_sheets["章详细大纲"]
            
            # 确保列存在
            if 'chapter_done' not in df.columns:
                df['chapter_done'] = 0
            if 'summary' not in df.columns:
                df['summary'] = ''
            
            # 找到对应章节并更新
            for idx in df.index:
                row_roll = df.loc[idx, '本章所属卷次']
                row_chapter = df.loc[idx, '本章次']
                if int(row_roll) == roll and int(row_chapter) == chapter:
                    df.loc[idx, 'chapter_done'] = 1
                    df.loc[idx, 'summary'] = summary
                    break
            
            all_sheets["章详细大纲"] = df
        
        # 重新保存所有 Sheet
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            for sheet_name, df in all_sheets.items():
                df.to_excel(writer, sheet_name=sheet_name, index=True)
                
    except Exception as e:
        logger.error(f"保存章节进度到 Excel 失败: {e}")


# ======================== 主流程 ========================
def process_single_task(task: Dict, task_id: int, csv_path: str) -> bool:
    """处理单个小说任务"""
    logger.info(f"\n{'='*60}")
    logger.info(f"开始处理任务 task_id={task_id}")
    logger.info(f"类型: {task['novel_type']} | 卷数: {task['roll_num']} | 章数: {task['chapter_num']}")
    
    # 创建临时目录（大纲生成后重命名）
    temp_dir = os.path.join(NOVELS_DIR, f"_temp_task_{task_id}")
    os.makedirs(temp_dir, exist_ok=True)
    
    outline = None
    novel_title = None
    novel_dir = temp_dir
    
    # Step 1: 生成大纲（从 CSV 读取 outline_done 状态）
    outline_cache = os.path.join(temp_dir, "outline.json")
    outline_done = get_outline_done(csv_path, task_id)
    
    if outline_done and os.path.exists(outline_cache):
        logger.info("检测到已有大纲，跳过生成...")
        with open(outline_cache, 'r', encoding='utf-8') as f:
            outline = json.load(f)
    else:
        outline = generate_outline(task)
        if not outline:
            logger.error("大纲生成失败，跳过此任务")
            return False
        
        # 保存大纲缓存
        with open(outline_cache, 'w', encoding='utf-8') as f:
            json.dump(outline, f, ensure_ascii=False, indent=2)
        
        # 更新 CSV 中的 outline_done 状态
        update_outline_done(csv_path, task_id, True)
    
    # 获取小说标题并重命名目录
    novel_title = outline.get("作品概述", {}).get("小说标题", f"未命名小说_{task_id}")
    novel_title = re.sub(r'[《》<>:"/\\|?*]', '', novel_title)  # 移除非法字符
    
    final_dir = os.path.join(NOVELS_DIR, novel_title)
    if temp_dir != final_dir:
        if os.path.exists(final_dir):
            # 目录已存在，使用已有目录
            novel_dir = final_dir
        else:
            os.rename(temp_dir, final_dir)
            novel_dir = final_dir
    
    logger.info(f"小说标题: {novel_title}")
    
    # Excel 文件路径
    excel_path = os.path.join(novel_dir, "outline.xlsx")
    
    # 保存大纲为Excel（如果不存在）
    if not os.path.exists(excel_path):
        save_outline_to_excel(outline, novel_dir, novel_title)
    
    # 创建content目录
    content_dir = os.path.join(novel_dir, "content")
    os.makedirs(content_dir, exist_ok=True)
    
    # Step 2: 生成章节内容（从 Excel 读取进度）
    roll_num = int(task["roll_num"])
    chapter_per_roll = int(task["chapter_num"])
    word_num = int(task["word_num"])
    total_chapters = roll_num * chapter_per_roll
    
    # 从 Excel 加载章节进度
    progress = load_chapter_progress_from_excel(excel_path)
    prev_chapters = progress.get("prev_chapters", [])
    chapters_done = progress.get("chapters_done", [])
    
    for r in range(1, roll_num + 1):
        for c in range(1, chapter_per_roll + 1):
            chapter_file = os.path.join(content_dir, f"{r}-{c}.txt")
            chapter_key = f"{r}-{c}"
            global_chapter = (r - 1) * chapter_per_roll + c
            
            # 检查是否已生成（从 Excel 或文件存在）
            if chapter_key in chapters_done or os.path.exists(chapter_file):
                logger.info(f"跳过已生成: 第{r}卷 第{c}章")
                # 加载已有章节的摘要用于前情提要
                if os.path.exists(chapter_file) and chapter_key not in [f"{p.get('roll', 0)}-{p.get('chapter', 0)}" for p in prev_chapters]:
                    with open(chapter_file, 'r', encoding='utf-8') as f:
                        existing_content = f.read()
                    chapter_outline = outline.get("章详细大纲", {}).get(chapter_key, {})
                    prev_chapters.append({
                        "roll": r, "chapter": c,
                        "title": chapter_outline.get("本章标题", ""),
                        # "summary": extract_chapter_summary(existing_content)
                        "summary": generate_chapter_summary(existing_content, r, c)
                    })
                continue
            
            # 生成章节
            content = generate_chapter(outline, r, c, prev_chapters, word_num)
            
            if content:
                with open(chapter_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                # 提取摘要
                # summary = extract_chapter_summary(content)
                summary = generate_chapter_summary(content, r, c)
                
                # 保存进度到 Excel
                save_chapter_progress_to_excel(excel_path, r, c, summary)
                
                # 更新前情提要
                chapter_outline = outline.get("章详细大纲", {}).get(chapter_key, {})
                prev_chapters.append({
                    "roll": r, "chapter": c,
                    "title": chapter_outline.get("本章标题", ""),
                    "summary": summary
                })
                
                logger.info(f"✅ 已生成: 第{r}卷 第{c}章 ({global_chapter}/{total_chapters})")
            else:
                logger.error(f"❌ 生成失败: 第{r}卷 第{c}章")
            
            # 避免API限流
            time.sleep(1)
    
    logger.info(f"\n🎉 小说《{novel_title}》生成完成！")
    logger.info(f"   保存路径: {novel_dir}")
    return True


def parse_task_ids(task_id_str: str) -> List[int]:
    """
    解析 task_id 参数
    支持格式：
    - "1,3,6" -> [1, 3, 6]
    - "3-6" -> [3, 4, 5, 6]
    - "1,3-5,8" -> [1, 3, 4, 5, 8]
    """
    task_ids = set()
    parts = task_id_str.split(',')
    
    for part in parts:
        part = part.strip()
        if '-' in part:
            # 范围格式: "3-6"
            try:
                start, end = part.split('-')
                start, end = int(start.strip()), int(end.strip())
                task_ids.update(range(start, end + 1))
            except ValueError:
                logger.warning(f"无效的范围格式: {part}")
        else:
            # 单个ID
            try:
                task_ids.add(int(part))
            except ValueError:
                logger.warning(f"无效的task_id: {part}")
    
    return sorted(task_ids)


def update_task_status(csv_path: str, task_id: int, status: int, 
                       start_time: str = None, end_time: str = None):
    """更新任务状态到CSV"""
    df = pd.read_csv(csv_path, dtype={'gen_start_time': str, 'gen_end_time': str})
    # 确保时间列是字符串类型
    df['gen_start_time'] = df['gen_start_time'].astype(str).replace('nan', '')
    df['gen_end_time'] = df['gen_end_time'].astype(str).replace('nan', '')
    
    mask = df['task_id'] == task_id
    
    if mask.any():
        df.loc[mask, 'status'] = status
        if start_time:
            df.loc[mask, 'gen_start_time'] = start_time
        if end_time:
            df.loc[mask, 'gen_end_time'] = end_time
        df.to_csv(csv_path, index=False)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='AI小说自动批量生成系统')
    parser.add_argument('-f', '--file', default=TASKS_CSV, help='任务CSV文件路径')
    parser.add_argument('-i', '--ids', type=str, help='指定task_id，支持: "1,3,6" 或 "3-6" 或 "1,3-5,8"')
    parser.add_argument('--api-key', help='DeepSeek API Key')
    args = parser.parse_args()
    
    # 设置API Key
    global DEEPSEEK_API_KEY
    if args.api_key:
        DEEPSEEK_API_KEY = args.api_key
    
    if not DEEPSEEK_API_KEY:
        logger.error("请在 .env 文件中设置 DEEPSEEK_API_KEY 或使用 --api-key 参数")
        logger.info("示例: 在 .env 文件中添加 DEEPSEEK_API_KEY=sk-xxx")
        return
    
    # 确保目录存在
    os.makedirs(NOVELS_DIR, exist_ok=True)
    
    # 读取任务
    csv_path = args.file
    if not os.path.exists(csv_path):
        logger.error(f"任务文件不存在: {csv_path}")
        return
    
    tasks_df = pd.read_csv(csv_path)
    logger.info(f"共加载 {len(tasks_df)} 个任务")
    
    # 解析要处理的 task_id
    target_ids = None
    if args.ids:
        target_ids = parse_task_ids(args.ids)
        logger.info(f"指定处理 task_id: {target_ids}")
    
    # 处理任务
    processed = 0
    for idx, row in tasks_df.iterrows():
        task = row.to_dict()
        task_id = int(task.get('task_id', idx + 1))
        
        # 如果指定了 task_id，检查是否在列表中
        if target_ids and task_id not in target_ids:
            continue
        
        # 检查状态（跳过已完成的）
        status = int(task.get('status', 0))
        if status == 2:
            logger.info(f"任务 {task_id} 已完成，跳过")
            continue
        
        # 更新状态为"正在生成"
        start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        update_task_status(csv_path, task_id, status=1, start_time=start_time)
        
        # 处理任务
        success = process_single_task(task, task_id, csv_path)
        
        # 更新状态
        end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        final_status = 2 if success else 0
        update_task_status(csv_path, task_id, status=final_status, end_time=end_time)
        
        processed += 1
    
    if target_ids and processed == 0:
        logger.warning(f"未找到匹配的任务，请检查 task_id: {target_ids}")
    
    logger.info(f"\n✨ 处理完成！共处理 {processed} 个任务")


if __name__ == "__main__":
    main()