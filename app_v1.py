#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI小说自动批量生成系统 (费用优化版)
支持断点续传，调用DeepSeek API生成小说大纲和章节内容
优化：单次API调用同时生成正文与摘要，降低API成本
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

# DeepSeek API 配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
MODEL_NAME = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# 生成配置
MAX_RETRIES = 3
RETRY_DELAY = 5  # 秒

# 定义正文与摘要的分隔符 (尽量复杂，避免正文中出现)
SUMMARY_SEPARATOR = "#####CHAPTER_SUMMARY_SEPARATOR#####"

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
    
    try:
        return json.loads(text)
    except:
        pass
    
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
    
    try:
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            json_str = text[start:end + 1]
            return json.loads(json_str)
    except:
        pass
    
    try:
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1:
            json_str = text[start:end + 1]
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
    "小说标题": "《xxx》" # 仿照畅销书的取名风格，要吸引人,
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
      "本章核心情节梗概": "必须包含至少3个具体的细分情节/转折点。例如：1.主角遭遇奸商刁难；2.反派登场抢夺；3.主角出手打脸夺宝。",
      "本章关键冲突/爽点": "xxx",
      "本章人物发展/系统奖励": "xxx"
    }},
    "1-2": {{
      "本章所属卷次": "1",
      "本章次": "2",
      "本章标题": "xxx",
      "本章核心情节梗概": "必须包含至少3个具体的细分情节/转折点。例如：1.主角遭遇奸商刁难；2.反派登场抢夺；3.主角出手打脸夺宝。",
      "本章关键冲突/爽点": "xxx",
      "本章人物发展/系统奖励": "xxx"
    }}
  }}
}}

重要：
1. 根据卷数{task["roll_num"]}和章数{task["chapter_num"]}，生成对应数量的卷和章大纲
2. 总章数 = 卷数 × 每卷章数 = {int(task["roll_num"]) * int(task["chapter_num"])}章
3. 章详细大纲的key格式为"卷次-章次"，如"1-1"表示第1卷第1章
4. 人物至少3-5个主要角色
5. 只返回JSON，不要任何其他内容
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
        debug_file = os.path.join(NOVELS_DIR, f"_debug_response_{int(time.time())}.txt")
        with open(debug_file, 'w', encoding='utf-8') as f:
            f.write(response)
        logger.error(f"原始响应已保存到: {debug_file}")
        return None
    
    return outline


def save_outline_to_excel(outline: Dict, novel_dir: str, novel_title: str) -> str:
    """将大纲保存为Excel文件"""
    excel_path = os.path.join(novel_dir, "outline.xlsx")
    
    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        for sheet_name, data in outline.items():
            if isinstance(data, dict):
                first_value = next(iter(data.values()), None)
                if isinstance(first_value, dict):
                    df = pd.DataFrame.from_dict(data, orient='index')
                    if sheet_name == "章详细大纲":
                        if 'chapter_done' not in df.columns:
                            df['chapter_done'] = 0
                        if 'summary' not in df.columns:
                            df['summary'] = ''
                else:
                    df = pd.DataFrame([data])
            else:
                df = pd.DataFrame([{"内容": data}])
            
            safe_name = sheet_name[:31]
            df.to_excel(writer, sheet_name=safe_name, index=True)
    
    logger.info(f"大纲已保存: {excel_path}")
    return excel_path


# ======================== 章节生成 ========================
def build_chapter_context(outline: Dict, roll_num: int, chapter_num: int, prev_chapters: list) -> Tuple[str, str]:
    """构建章节生成的上下文信息"""
    overview = outline.get("作品概述", {})
    characters = outline.get("核心设定与人物", {})
    volumes = outline.get("卷详细大纲", {})
    chapters = outline.get("章详细大纲", {})
    
    chapter_key = f"{roll_num}-{chapter_num}"
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

    if prev_chapters:
        context += "\n【前情提要（最近剧情回顾）】\n"
        recent_summaries = prev_chapters[-4:]
        for prev in recent_summaries:
            context += f"Draft-第{prev['roll']}卷第{prev['chapter']}章：{prev['summary']}\n"

    return context, chapter_outline.get("本章标题", f"第{chapter_num}章")


def post_process_content(content: str, roll: int, chapter: int, title: str) -> str:
    """对AI生成的内容进行格式化清洗"""
    # 移除可能的 Markdown 代码块
    content = re.sub(r'^```.*?\n', '', content, flags=re.MULTILINE)
    content = re.sub(r'```$', '', content, flags=re.MULTILINE)
    
    lines = content.split('\n')
    processed_lines = []
    
    full_title = f"第{roll}卷 第{chapter}章：{title}"
    processed_lines.append(full_title)
    processed_lines.append("") 
    
    for line in lines:
        line = line.strip()
        # 跳过空行和重复标题
        if not line or line == full_title or line in title:
            continue
            
        # 强制全角缩进
        processed_lines.append(f"\u3000\u3000{line}")
        processed_lines.append("") 
        
    return "\n".join(processed_lines)


# def generate_chapter(outline: Dict, roll_num: int, chapter_num: int, 
#                      prev_chapters: list, word_num: int) -> Tuple[Optional[str], Optional[str]]:
#     """
#     生成单章内容 + 摘要 (One-Pass)
#     返回: (content, summary)
#     """
#     context, chapter_title = build_chapter_context(outline, roll_num, chapter_num, prev_chapters)
    
#     prompt = f"""{context}

# 请你扮演一位白金级小说作家，根据以上设定和大纲，撰写第{roll_num}卷第{chapter_num}章的完整内容。

# 【任务要求】
# 你需要在一次输出中完成两件事：
# 1. **撰写正文**：按照高阶写作要求撰写精彩的小说正文。
# 2. **生成摘要**：在正文结束后，输出分割线 "{SUMMARY_SEPARATOR}"，然后紧接着写一段300字以内的本章剧情摘要。

# 【写作高阶要求】
# 1. **沉浸式描写**：不要只写“他打了一拳”，要写拳风的呼啸、周围空气的扭曲。
# 2. **强画面感**：多用动词和名词，少用形容词。
# 3. **拒绝流水账**：严禁出现“经过一番苦战”这种省略句，必须细致描写过程。
# 4. **对话自然**：反派不要无脑嘲讽，要有逻辑；主角说话符合人设。
# 5. **节奏把控**：打斗短句短段，文戏细腻铺陈。
# 6. **环境渲染**：开篇及文中穿插环境描写（光影、声音、气味）。

# 【其他要求】
# 1. 正文字数约{word_num}字左右。
# 2. 严格按照章节大纲的情节推进，确保逻辑连贯。
# 3. 保持词汇丰富，避免重复。
# 4. **注意格式**：直接输出正文，不要标题，不要前言。
# 5. **关键**：正文结束后，必须换行输出 "{SUMMARY_SEPARATOR}"，然后输出摘要。

# 【摘要内容要求】
# 摘要需包含：核心事件（主角做了什么/打败了谁）、状态变更（获得物品/关系变化）、伏笔记录。

# 请开始创作：
# """

#     system_prompt = f"你是一位专业的网络小说作家。请严格遵循格式要求，在正文后附带剧情摘要。"
    
#     logger.info(f"正在生成: 第{roll_num}卷 第{chapter_num}章 (含摘要)...")
    
#     raw_response = call_deepseek(prompt, system_prompt, temperature=0.85)
    
#     if not raw_response:
#         return None, None
        
#     # === 解析响应，分离正文和摘要 ===
#     content_raw = raw_response
#     summary_raw = None
    
#     if SUMMARY_SEPARATOR in raw_response:
#         parts = raw_response.split(SUMMARY_SEPARATOR)
#         content_raw = parts[0].strip()
#         summary_raw = parts[1].strip()
#     else:
#         logger.warning(f"AI未输出分割线，尝试自动兜底: {roll_num}-{chapter_num}")
#         # 如果没有分割线，假设全是正文，摘要取最后一段
#         content_raw = raw_response
#         summary_raw = content_raw[-500:] if len(content_raw) > 500 else content_raw

#     # 对正文进行排版
#     final_content = post_process_content(content_raw, roll_num, chapter_num, chapter_title)
    
#     return final_content, summary_raw

def generate_chapter(outline: Dict, roll_num: int, chapter_num: int, prev_chapters: list, word_num: int) -> Tuple[Optional[str], Optional[str]]:
    """
    生成单章内容 + 摘要 (One-Pass 终极优化版)
    功能：
    1. 根据 word_num 动态调整写作策略（防止字数少时啰嗦，字数多时注水）。
    2. 一次性返回正文和摘要，节省40%费用。
    """
    context, chapter_title = build_chapter_context(outline, roll_num, chapter_num, prev_chapters)
    
    # 定义分隔符（确保足够独特，不会在小说正文中出现）
    SEPARATOR = "#####CHAPTER_SUMMARY_SEPARATOR#####"

    # === 核心逻辑：根据字数动态构建 Prompt ===
    if word_num < 1000:
        # 【调试/短篇模式】
        logger.info(f"检测到字数要求较低 ({word_num}字)，切换为【紧凑模式】")
        writing_instructions = f"""
1. **控制篇幅**：这是一个短章节或调试章节，请严格控制字数在 {word_num} 字左右。
2. **言简意赅**：剧情推进要快，省略不必要的环境渲染和心理铺垫。
3. **直奔主题**：直接描写核心冲突，不要在无关细节上浪费笔墨。
"""
    else:
        # 【正式/长篇模式】 -> 重点防止“注水”和“啰嗦”
        logger.info(f"检测到字数要求正常 ({word_num}字)，切换为【高密度扩写模式】")
        writing_instructions = """
【如何写够字数而不啰嗦？请严格遵循以下扩展法则】

1. **心理博弈（增加20%篇幅）**：
   - 不要只写主角“做了什么”，要深挖他“为什么这么做”。
   - 展现决策过程中的犹豫、权衡、对风险的预判。
   - 描写对手在表面嚣张之下，内心深处的那一丝惊疑不定。

2. **战斗/冲突的颗粒度（增加30%篇幅）**：
   - **拒绝流水账**：严禁出现“两人过了几十招”、“经过一番苦战”这种省略句。
   - **招式拆解**：必须将动作慢放。例如：不要写“躲开了攻击”，要写“侧身避开锋芒，锐利的剑气割断了几根发丝，皮肤感到一阵刺痛”。
   - **战损与生理反应**：描写呼吸的紊乱、肌肉的酸痛、血液流失带来的眩晕感。

3. **世界观渗透（增加15%篇幅）**：
   - 在剧情中自然带出世界观设定（如：功法的历史渊源、灵气流动的特殊规律）。
   - 让环境与人物互动（例如：不仅仅是风吹过，而是风中夹杂的血腥味让主角想起了往事）。

4. **拒绝无效注水**：
   - ❌ 严禁出现无意义的“你好/再见/吃了吗”式对话。
   - ❌ 严禁重复描写已知的信息（如反复介绍同一个人的身份）。
"""

    # === 构建最终 Prompt ===
    prompt = f"""{context}

请你扮演一位白金级小说作家（如辰东、土豆的风格），根据以上设定和大纲，撰写第{roll_num}卷第{chapter_num}章的完整内容。

【任务要求】
你需要在一次输出中完成两件事，顺序如下：
1. **撰写正文**：按照下方的【写作指导】撰写精彩的小说正文。
2. **输出分隔符**：正文结束后，换行输出 "{SEPARATOR}"。
3. **生成摘要**：紧接着写一段300字以内的剧情摘要（包含核心事件、物品获取、人物状态变化）。

【写作指导】
{writing_instructions}

【通用要求】
1. **字数目标**：约 {word_num} 字（请根据模式调整节奏）。
2. **对话自然**：反派不要无脑降智，要有自己的利益逻辑；主角说话符合人设。
3. **逻辑连贯**：严格按照章节大纲的情节推进，承接上文伏笔。
4. **格式规范**：直接输出正文，不要标题，不要前言，不要“好的”之类的废话。

请开始创作：
"""

    system_prompt = f"你是一位专业的网络小说作家。当前任务目标字数：{word_num}字。请严格遵守指令，在正文后附带摘要。"
    
    logger.info(f"正在生成: 第{roll_num}卷 第{chapter_num}章 (目标{word_num}字)...")
    
    # 调用 API (建议使用流式输出版本 call_deepseek)
    raw_response = call_deepseek(prompt, system_prompt, temperature=0.85)
    
    if not raw_response:
        return None, None
        
    # === 解析响应，分离正文和摘要 ===
    content_raw = raw_response
    summary_raw = None
    
    if SEPARATOR in raw_response:
        parts = raw_response.split(SEPARATOR)
        content_raw = parts[0].strip()
        summary_raw = parts[1].strip()
    else:
        # 容错处理：如果AI忘了写分隔符，假设全文都是正文，手动截取摘要
        logger.warning(f"⚠️ AI未输出分隔符，启用自动截取摘要: {roll_num}-{chapter_num}")
        content_raw = raw_response
        summary_raw = content_raw[-400:] # 取最后400字作为摘要

    # === 后处理排版（缩进、去标题等） ===
    final_content = post_process_content(content_raw, roll_num, chapter_num, chapter_title)
    
    return final_content, summary_raw


def generate_chapter_summary(content: str, roll: int, chapter: int) -> str:
    """
    独立生成摘要函数
    （仅用于断点续传时，文件存在但没有摘要记录的情况，平时生成时不调用此函数以节省Token）
    """
    prompt = f"""
请阅读以下小说章节内容（第{roll}卷 第{chapter}章），生成一份**剧情摘要**。
这份摘要将作为AI生成下一章的“前情提要”，所以必须包含关键的逻辑信息。

【原文内容】
{content}

【摘要要求】
1. 300字以内，言简意赅。
2. 核心事件：主角做了什么？遇到的谁？
3. 状态变更：获得的物品/功法/能力，人际关系变化。
4. 伏笔记录。

请直接输出摘要内容。
"""
    summary = call_deepseek(prompt, temperature=0.3)
    if not summary:
        return content[-800:] 
    return summary


# ======================== 进度管理（断点续传） ========================
def update_outline_done(csv_path: str, task_id: int, done: bool = True):
    df = pd.read_csv(csv_path, dtype={'gen_start_time': str, 'gen_end_time': str})
    df['gen_start_time'] = df['gen_start_time'].astype(str).replace('nan', '')
    df['gen_end_time'] = df['gen_end_time'].astype(str).replace('nan', '')
    
    mask = df['task_id'] == task_id
    if mask.any():
        df.loc[mask, 'outline_done'] = 1 if done else 0
        df.to_csv(csv_path, index=False)


def get_outline_done(csv_path: str, task_id: int) -> bool:
    df = pd.read_csv(csv_path)
    mask = df['task_id'] == task_id
    if mask.any():
        return int(df.loc[mask, 'outline_done'].iloc[0]) == 1
    return False


def load_chapter_progress_from_excel(excel_path: str) -> Dict:
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
    if not os.path.exists(excel_path):
        return
    
    try:
        with pd.ExcelFile(excel_path) as xls:
            all_sheets = {sheet: pd.read_excel(xls, sheet_name=sheet, index_col=0) 
                         for sheet in xls.sheet_names}
        
        if "章详细大纲" in all_sheets:
            df = all_sheets["章详细大纲"]
            if 'chapter_done' not in df.columns:
                df['chapter_done'] = 0
            if 'summary' not in df.columns:
                df['summary'] = ''
            
            # 使用更健壮的查找方式
            mask = (df['本章所属卷次'].astype(int) == roll) & (df['本章次'].astype(int) == chapter)
            if mask.any():
                df.loc[mask, 'chapter_done'] = 1
                df.loc[mask, 'summary'] = summary
            
            all_sheets["章详细大纲"] = df
        
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
    
    # 路径准备
    temp_dir = os.path.join(NOVELS_DIR, f"_temp_task_{task_id}")
    os.makedirs(temp_dir, exist_ok=True)
    
    # Step 1: 大纲处理
    outline_cache = os.path.join(temp_dir, "outline.json")
    outline_done = get_outline_done(csv_path, task_id)
    
    outline = None
    if outline_done and os.path.exists(outline_cache):
        logger.info("检测到已有大纲，加载中...")
        with open(outline_cache, 'r', encoding='utf-8') as f:
            outline = json.load(f)
    else:
        outline = generate_outline(task)
        if not outline:
            return False
        with open(outline_cache, 'w', encoding='utf-8') as f:
            json.dump(outline, f, ensure_ascii=False, indent=2)
        update_outline_done(csv_path, task_id, True)
    
    # 目录重命名
    novel_title = outline.get("作品概述", {}).get("小说标题", f"未命名小说_{task_id}")
    novel_title = re.sub(r'[《》<>:"/\\|?*]', '', novel_title)
    final_dir = os.path.join(NOVELS_DIR, novel_title)
    
    novel_dir = temp_dir
    if temp_dir != final_dir:
        if os.path.exists(final_dir):
            novel_dir = final_dir
        else:
            os.rename(temp_dir, final_dir)
            novel_dir = final_dir
            
    logger.info(f"小说标题: {novel_title}")
    
    excel_path = os.path.join(novel_dir, "outline.xlsx")
    if not os.path.exists(excel_path):
        save_outline_to_excel(outline, novel_dir, novel_title)
    
    content_dir = os.path.join(novel_dir, "content")
    os.makedirs(content_dir, exist_ok=True)
    
    # Step 2: 章节生成
    roll_num = int(task["roll_num"])
    chapter_per_roll = int(task["chapter_num"])
    word_num = int(task["word_num"])
    total_chapters = roll_num * chapter_per_roll
    
    progress = load_chapter_progress_from_excel(excel_path)
    prev_chapters = progress.get("prev_chapters", [])
    chapters_done = progress.get("chapters_done", [])
    
    for r in range(1, roll_num + 1):
        for c in range(1, chapter_per_roll + 1):
            chapter_key = f"{r}-{c}"
            chapter_file = os.path.join(content_dir, f"{r}-{c}.txt")
            global_chapter = (r - 1) * chapter_per_roll + c
            
            # --- 断点续传逻辑 (跳过已存在) ---
            if chapter_key in chapters_done or os.path.exists(chapter_file):
                logger.info(f"跳过已生成: 第{r}卷 第{c}章")
                
                # 如果文件存在但内存中没有摘要（比如刚重启程序），需要补录上下文
                # 检查当前章节是否已经在 prev_chapters 中
                if chapter_key not in [f"{p.get('roll', 0)}-{p.get('chapter', 0)}" for p in prev_chapters]:
                    if os.path.exists(chapter_file):
                        with open(chapter_file, 'r', encoding='utf-8') as f:
                            existing_content = f.read()
                        
                        logger.info(f"正在为已存在章节补充摘要: {r}-{c}")
                        # 这里调用单独的摘要函数，因为文件已存在，不消耗生成的费用
                        summary = generate_chapter_summary(existing_content, r, c)
                        
                        chapter_outline = outline.get("章详细大纲", {}).get(chapter_key, {})
                        prev_chapters.append({
                            "roll": r, "chapter": c,
                            "title": chapter_outline.get("本章标题", ""),
                            "summary": summary
                        })
                continue
            
            # --- 新生成逻辑 (One-Pass) ---
            # 这里的 generate_chapter 会同时返回 content 和 summary
            content, summary = generate_chapter(outline, r, c, prev_chapters, word_num)
            
            if content:
                # 1. 保存正文
                with open(chapter_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                # 2. 摘要兜底 (如果AI没返回摘要，手动截取)
                if not summary:
                    summary = content[-500:]
                
                # 3. 保存进度和更新上下文
                save_chapter_progress_to_excel(excel_path, r, c, summary)
                
                chapter_outline = outline.get("章详细大纲", {}).get(chapter_key, {})
                prev_chapters.append({
                    "roll": r, "chapter": c,
                    "title": chapter_outline.get("本章标题", ""),
                    "summary": summary
                })
                
                logger.info(f"✅ 已生成: 第{r}卷 第{c}章 ({global_chapter}/{total_chapters})")
            else:
                logger.error(f"❌ 生成失败: 第{r}卷 第{c}章")
            
            time.sleep(1)
    
    logger.info(f"\n🎉 小说《{novel_title}》生成完成！")
    return True


# ======================== 工具函数 ========================
def parse_task_ids(task_id_str: str) -> List[int]:
    task_ids = set()
    parts = task_id_str.split(',')
    for part in parts:
        part = part.strip()
        if '-' in part:
            try:
                start, end = part.split('-')
                start, end = int(start.strip()), int(end.strip())
                task_ids.update(range(start, end + 1))
            except ValueError:
                pass
        else:
            try:
                task_ids.add(int(part))
            except ValueError:
                pass
    return sorted(task_ids)


def update_task_status(csv_path: str, task_id: int, status: int, 
                       start_time: str = None, end_time: str = None):
    df = pd.read_csv(csv_path, dtype={'gen_start_time': str, 'gen_end_time': str})
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
    parser = argparse.ArgumentParser(description='AI小说自动批量生成系统')
    parser.add_argument('-f', '--file', default=TASKS_CSV, help='任务CSV文件路径')
    parser.add_argument('-i', '--ids', type=str, help='指定task_id')
    parser.add_argument('--api-key', help='DeepSeek API Key')
    args = parser.parse_args()
    
    global DEEPSEEK_API_KEY
    if args.api_key:
        DEEPSEEK_API_KEY = args.api_key
    
    if not DEEPSEEK_API_KEY:
        logger.error("请设置 DEEPSEEK_API_KEY")
        return
    
    os.makedirs(NOVELS_DIR, exist_ok=True)
    
    if not os.path.exists(args.file):
        logger.error(f"任务文件不存在: {args.file}")
        return
    
    tasks_df = pd.read_csv(args.file)
    target_ids = parse_task_ids(args.ids) if args.ids else None
    
    for idx, row in tasks_df.iterrows():
        task = row.to_dict()
        task_id = int(task.get('task_id', idx + 1))
        
        if target_ids and task_id not in target_ids:
            continue
        
        if int(task.get('status', 0)) == 2:
            continue
        
        start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        update_task_status(args.file, task_id, 1, start_time=start_time)
        
        success = process_single_task(task, task_id, args.file)
        
        end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        update_task_status(args.file, task_id, 2 if success else 0, end_time=end_time)


if __name__ == "__main__":
    main()