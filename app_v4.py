#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI小说自动批量生成系统 (智能补全版 - 类封装带日志版)
"""

import os
import sys
import shutil
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

# ======================== 日志类 (参考修改版) ========================
class Logger(object):
    def __init__(self, log_dir: str, task_id: int, task_config: Dict):
        # 🟢 1. 确保 logs 目录存在
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # 🟢 2. 设置文件名: logs/task_[id].log
        self.log_file_name = os.path.join(log_dir, f"task_{task_id}.log")
        
        # 保存原本的 stdout 以便在终端也能看到 (如果需要)
        self.terminal = sys.__stdout__ 
        self.write_in_terminal = True # 是否同时在控制台输出

        # 🟢 3. 追加模式打开文件
        self.log = open(self.log_file_name, 'a', encoding='utf-8')
        
        # 在控制台提示日志位置 (此时还没有替换sys.stdout)
        print(f"📄 [Logger] 日志文件目标: {self.log_file_name}")

        # 🟢 4. 写入分割线和配置信息
        start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        divider = f"\n\n{'='*20} 🚀 新的任务运行开始: {start_time} {'='*20}\n"
        self.log.write(divider)

        # 写入任务配置信息
        config_str = f"Task Config (ID: {task_id}) = \n{json.dumps(task_config, indent=4, ensure_ascii=False, default=str)}\n"
        self.log.write(config_str)
        
        self.log.flush()
        
    def write(self, message):
        if self.write_in_terminal:
            self.terminal.write(message)
        self.log.write(message)
        self.log.flush()

    def flush(self):
        if self.write_in_terminal:
            self.terminal.flush()
        self.log.flush()

# ======================== AI 小说生成器类 ========================

class NovelGenerator:
    def __init__(self, api_key: str, base_url: str, model_name: str, base_dir: str):
        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name
        self.base_dir = base_dir
        
        self.novels_dir = os.path.join(base_dir, "novels")
        self.tasks_csv = os.path.join(base_dir, "novel_gen_tasks.csv")
        self.logs_dir = os.path.join(base_dir, "logs")
        
        # 初始化配置
        self.max_retries = 3
        self.retry_delay = 5
        self.summary_separator = "#####CHAPTER_SUMMARY_SEPARATOR#####"
        
        # 初始化 Client
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        
        # 初始化基础 Logging (输出格式)
        # 注意：后续我们会重定向 stdout，所以这里的 StreamHandler 会自动被 Logger 捕获
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%H:%M:%S',
            force=True # 强制重新配置，防止冲突
        )
        self.logger = logging.getLogger(__name__)

    # ======================== API 基础函数 ========================
    
    def call_deepseek(self, prompt: str, system_prompt: str = None, temperature: float = 0.8) -> Optional[str]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=8192,
                )
                return response.choices[0].message.content
            except Exception as e:
                self.logger.warning(f"API调用失败 ({attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
        return None

    def extract_json_from_response(self, text: str) -> Optional[Dict]:
        if not text: return None
        try: 
            return json.loads(text)
        except (json.JSONDecodeError, ValueError): 
            pass
        patterns = [r'```json\s*([\s\S]*?)\s*```', r'```\s*([\s\S]*?)\s*```']
        for p in patterns:
            m = re.search(p, text)
            if m:
                try: 
                    return json.loads(m.group(1))
                except (json.JSONDecodeError, ValueError): 
                    continue
        try:
            s, e = text.find('{'), text.rfind('}')
            if s != -1 and e != -1: 
                return json.loads(re.sub(r',(\s*[}\]])', r'\1', text[s:e+1]))
        except (json.JSONDecodeError, ValueError): 
            pass
        return None

    # ======================== 大纲生成与修复模块 ========================

    def generate_global_settings(self, task: Dict) -> Optional[Dict]:
        """生成完整的宏观设定（含卷大纲，不含章大纲）"""
        # ==================== PROMPT START (DO NOT MODIFY) ====================
        prompt = f'''请参考网络热门或者排行榜靠前的{task["novel_type"]}小说的设定和剧情爽点，写一部小说。

小说想法：{task["novel_idea"]}
文风：{task["write_style"]}
目标读者：{task["target_reader"]}
小说结构：共{task["roll_num"]}卷，每卷{task["chapter_num"]}章，每章至少约{task["word_num"]}字
特殊要求：{task["special_requirements"]}

请生成小说的宏观设定，严格返回以下JSON格式（不要有任何额外说明）：

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
    "每章字数至少": {task["word_num"]}
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
    }},
    "2": {{
      "本卷次": "2",
      "本卷标题": "xxx",
      "本卷核心冲突": "xxx",
      "本卷关键情节": "xxx",
      "本卷目标": "xxx"
    }}
  }}
}}

重要：
1. 根据卷数{task["roll_num"]}，生成对应数量的卷大纲（注意：此步骤不生成章大纲，章大纲会在后续步骤按卷生成）
2. 人物至少3-5个主要角色，每个角色要有完整的设定
3. 只返回JSON，不要任何其他内容
'''
        # ==================== PROMPT END ====================
        
        self.logger.info("正在生成宏观设定（含作品概述、人物设定、卷大纲）...")
        res = self.call_deepseek(prompt, "你是一位专业的网络小说策划师，擅长创作热门爆款小说大纲。请严格按照用户要求的JSON格式返回结果。", 0.9)
        return self.extract_json_from_response(res)

    def generate_volume_chapters(self, outline: Dict, roll_index: int, chapter_count: int) -> Optional[Dict]:
        """第二步/补全步骤：根据全局设定 + 卷梗概，生成该卷下的具体章节大纲"""
        overview = outline.get("作品概述", {})
        characters = outline.get("核心设定与人物", {})
        all_volumes = outline.get("卷详细大纲", {})
        
        current_vol_info = all_volumes.get(str(roll_index), {})
        if not current_vol_info:
            self.logger.warning(f"没有找到第{roll_index}卷的卷梗概，AI将自由发挥")
        
        char_context = ""
        for cid, char in characters.items():
            if isinstance(char, dict):
                name = char.get("姓名", "未知")
                role = char.get("身份/职位", char.get("身份", ""))
                trait = char.get("核心性格", "")
                relation = char.get("与主角关系", "")
                char_context += f"- {name}：{role}，{trait}，与主角关系：{relation}\n"

        vol_structure = ""
        for k, v in all_volumes.items():
            vol_structure += f"第{k}卷：{v.get('本卷标题', '')} (冲突：{v.get('本卷核心冲突', '')})\n"

        # ==================== PROMPT START (DO NOT MODIFY) ====================
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
        # ==================== PROMPT END ====================

        self.logger.info(f"正在基于完整设定生成第 {roll_index} 卷大纲 (共{chapter_count}章)...")
        system_prompt = "你是一位严谨的小说主编，擅长把控长篇小说的剧情结构和人物逻辑一致性。"
        res = self.call_deepseek(prompt, system_prompt, temperature=0.85)
        return self.extract_json_from_response(res)

    def check_and_fix_outline(self, outline: Dict, task: Dict, outline_path: str, novel_dir: str) -> Tuple[Dict, bool]:
        updated = False
        if "章详细大纲" not in outline:
            outline["章详细大纲"] = {}
            
        required_rolls = int(task["roll_num"])
        required_chapters = int(task["chapter_num"])
        current_chapters = outline.get("章详细大纲", {})
        existing_keys = list(current_chapters.keys())
        novel_title = outline.get("作品概述", {}).get("小说标题", "未命名")
        
        if len(existing_keys) > 0:
            self.logger.info(f"当前大纲已包含章节Key示例: {existing_keys[:3]}... (共{len(existing_keys)}章)")
        
        for r in range(1, required_rolls + 1):
            strict_key = f"{r}-1"
            is_volume_exist = False
            if strict_key in current_chapters:
                is_volume_exist = True
            else:
                prefix = f"{r}-"
                for k in existing_keys:
                    if k.startswith(prefix):
                        is_volume_exist = True
                        break
            
            if not is_volume_exist:
                self.logger.warning(f"⚠️  未检测到 第 {r} 卷的大纲，开始补全...")
                vol_chapters = None
                for retry in range(3):
                    vol_chapters = self.generate_volume_chapters(outline, r, required_chapters)
                    if vol_chapters:
                        break
                    time.sleep(3)
                
                if vol_chapters:
                    outline["章详细大纲"].update(vol_chapters)
                    updated = True
                    existing_keys = list(outline["章详细大纲"].keys())
                    self.logger.info(f"✅ 第 {r} 卷大纲补全成功，正在执行【即时保存】...")
                    
                    try:
                        with open(outline_path, 'w', encoding='utf-8') as f:
                            json.dump(outline, f, ensure_ascii=False, indent=2)
                    except Exception as e:
                        self.logger.error(f"JSON即时保存失败: {e}")

                    try:
                        self.save_outline_to_excel(outline, novel_dir, novel_title)
                    except Exception as e:
                        self.logger.error(f"Excel即时保存失败: {e}")
                        
                    self.logger.info(f"💾 第 {r} 卷已写入硬盘 (JSON + Excel)")
                else:
                    self.logger.error(f"❌ 第 {r} 卷大纲补全失败")
            else:
                pass
                
        return outline, updated

    def save_outline_to_excel(self, outline: Dict, novel_dir: str, novel_title: str) -> str:
        excel_path = os.path.join(novel_dir, "outline.xlsx")
        old_chapter_status = {}
        
        if os.path.exists(excel_path):
            try:
                old_df = pd.read_excel(excel_path, sheet_name="章详细大纲", index_col=0, dtype=object)
                for idx, row in old_df.iterrows():
                    if self.is_chapter_done(row.get('chapter_done', 0)):
                        old_chapter_status[str(idx)] = {
                            'chapter_done': 1,
                            'summary': row.get('summary', '')
                        }
                if old_chapter_status:
                    self.logger.info(f"📋 已备份 {len(old_chapter_status)} 章的历史进度")
            except Exception as e:
                self.logger.warning(f"读取旧Excel状态时遇到小问题（不影响后续）: {e}")

        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            for sheet_name, data in outline.items():
                if sheet_name == "章详细大纲" and isinstance(data, dict):
                    df = pd.DataFrame.from_dict(data, orient='index')
                    if 'chapter_done' not in df.columns: df['chapter_done'] = 0
                    if 'summary' not in df.columns: df['summary'] = ''
                    df['summary'] = df['summary'].astype(object)
                    
                    for idx in df.index:
                        str_idx = str(idx)
                        if str_idx in old_chapter_status:
                            df.at[idx, 'chapter_done'] = 1
                            old_sum = old_chapter_status[str_idx]['summary']
                            if pd.notna(old_sum) and str(old_sum).strip():
                                df.at[idx, 'summary'] = old_sum
                    df.to_excel(writer, sheet_name=sheet_name, index=True)
                elif isinstance(data, dict):
                    first_val = next(iter(data.values()), None)
                    if isinstance(first_val, dict):
                        df = pd.DataFrame.from_dict(data, orient='index')
                    else:
                        df = pd.DataFrame([data])
                    df.to_excel(writer, sheet_name=sheet_name[:31])
                else:
                    pd.DataFrame([{"内容": data}]).to_excel(writer, sheet_name=sheet_name[:31])
        
        self.logger.info(f"Excel大纲已更新（保留了历史进度）: {excel_path}")
        return excel_path

    # ======================== 内容生成模块 ========================

    def build_chapter_context(self, outline: Dict, roll_num: int, chapter_num: int, prev_chapters: list) -> Tuple[str, str]:
        chapter_key = f"{roll_num}-{chapter_num}"
        chapters = outline.get("章详细大纲", {})
        chapter_outline = chapters.get(chapter_key, {})
        
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

    def post_process_content(self, content: str, roll: int, chapter: int, title: str) -> str:
        lines = content.split('\n')
        processed = [f"第{roll}卷 第{chapter}章：{title}\n"]
        for line in lines:
            line = line.strip().replace("#####", "")
            if line and line not in title and "SUMMARY" not in line:
                processed.append(f"\u3000\u3000{line}\n")
        return "\n".join(processed)

    def generate_chapter(self, outline: Dict, roll: int, chapter: int, prev_chapters: list, word_num: int) -> Tuple[Optional[str], Optional[str]]:
        context, title = self.build_chapter_context(outline, roll, chapter, prev_chapters)
        
        # ==================== PROMPT START (DO NOT MODIFY) ====================
        prompt = f"""{context}
请撰写正文（至少约{word_num}字）。
要求：场景描写细腻，对话符合人设，严禁流水账。
格式：正文结束后，换行输出 "{self.summary_separator}"，再写300字摘要。
"""
        # ==================== PROMPT END ====================
        
        self.logger.info(f"正在生成: {roll}-{chapter} {title}")
        res = self.call_deepseek(prompt, "你是一位网文大神。", 0.85)
        if not res: return None, None
        
        parts = res.split(self.summary_separator)
        content = parts[0].strip()
        summary = parts[1].strip() if len(parts) > 1 else content[-400:]
        
        return self.post_process_content(content, roll, chapter, title), summary

    # ======================== 进度读取 ========================
    def is_chapter_done(self, val) -> bool:
        if pd.isna(val): return False
        try: return int(float(val)) == 1
        except (ValueError, TypeError): return str(val).strip() == '1'

    def load_progress(self, excel_path: str) -> Dict:
        prog = {"done_set": set(), "prev_chapters": []}
        if not os.path.exists(excel_path): 
            return prog
        try:
            df = pd.read_excel(excel_path, sheet_name="章详细大纲", index_col=0, dtype=object)
            for idx, row in df.iterrows():
                if self.is_chapter_done(row.get('chapter_done')):
                    r, c = int(float(row['本章所属卷次'])), int(float(row['本章次']))
                    prog["done_set"].add(f"{r}-{c}")
                    if pd.notna(row.get('summary')):
                        prog["prev_chapters"].append({
                            "roll": r, "chapter": c, 
                            "summary": str(row['summary'])
                        })
        except Exception as e:
            self.logger.warning(f"加载进度失败: {e}")
        return prog

    def save_progress(self, excel_path: str, r: int, c: int, summary: str):
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
            self.logger.error(f"保存进度失败: {e}")

    def update_task_csv(self, csv_path: str, task_id: int, status: int = None, 
                        outline_done: int = None, gen_start: bool = False, gen_end: bool = False):
        try:
            df = pd.read_csv(csv_path, dtype={'gen_start_time': str, 'gen_end_time': str})
            mask = df['task_id'] == task_id
            
            if status is not None and 'status' in df.columns:
                df.loc[mask, 'status'] = status
            
            if outline_done is not None and 'outline_done' in df.columns:
                df.loc[mask, 'outline_done'] = outline_done
                
            if gen_start and 'gen_start_time' in df.columns:
                df.loc[mask, 'gen_start_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
            if gen_end and 'gen_end_time' in df.columns:
                df.loc[mask, 'gen_end_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            df.to_csv(csv_path, index=False)
        except Exception as e:
            self.logger.warning(f"更新CSV失败: {e}")
    
    def zip_novel_folder(self, novel_dir: str):
        """
        压缩小说文件夹为ZIP文件
        生成路径: novels/task_[id].zip
        """
        try:
            self.logger.info("正在打包文件以便下载...")
            # shutil.make_archive(压缩包名(不含后缀), 格式, 要压缩的目录)
            # 这里 base_name=novel_dir 意味着会在 novel_dir 同级目录下生成同名zip
            zip_path = shutil.make_archive(novel_dir, 'zip', novel_dir)
            self.logger.info(f"📦 打包成功! 下载路径: {zip_path}")
            return zip_path
        except Exception as e:
            self.logger.error(f"❌ 打包失败: {e}")
            return None

    # ======================== 处理单个任务 ========================

    def process_task(self, task: Dict, task_id: int) -> bool:
        # 🟢 设置 Logger 并接管 stdout/stderr
        # 这样所有的 print 和 self.logger 的输出都会进入文件
        custom_logger = Logger(self.logs_dir, task_id, task)
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        sys.stdout = custom_logger
        sys.stderr = custom_logger
        
        try:
            self.logger.info(f"开始处理任务 task_id={task_id}")
            
            novel_dir = os.path.join(self.novels_dir, f"task_{task_id}")
            os.makedirs(novel_dir, exist_ok=True)
            self.logger.info(f"工作目录: {novel_dir}")

            # 1. 加载大纲
            outline_path = os.path.join(novel_dir, "outline.json")
            outline = None
            if os.path.exists(outline_path):
                try:
                    with open(outline_path, 'r', encoding='utf-8') as f: outline = json.load(f)
                except (json.JSONDecodeError, IOError) as e:
                    self.logger.warning(f"加载大纲失败: {e}")
                    
            if not outline:
                self.logger.info("生成新宏观设定...")
                outline = self.generate_global_settings(task)
                if not outline: 
                    self.logger.error("宏观设定生成失败")
                    return False
                with open(outline_path, 'w', encoding='utf-8') as f:
                    json.dump(outline, f, ensure_ascii=False, indent=2)
                self.logger.info(f"💾 宏观设定已保存: {outline_path}")
            
            # 2. 补全大纲
            outline, was_repaired = self.check_and_fix_outline(outline, task, outline_path, novel_dir)
            
            with open(outline_path, 'w', encoding='utf-8') as f:
                json.dump(outline, f, ensure_ascii=False, indent=2)

            novel_title = outline.get("作品概述", {}).get("小说标题", f"Task_{task_id}")
            excel_path = os.path.join(novel_dir, "outline.xlsx")
            
            if not os.path.exists(excel_path):
                self.save_outline_to_excel(outline, novel_dir, novel_title)
            
            self.update_task_csv(self.tasks_csv, task_id, outline_done=1)
                
            content_dir = os.path.join(novel_dir, "content")
            os.makedirs(content_dir, exist_ok=True)
            
            # 3. 准备生成
            progress = self.load_progress(excel_path)
            done_set = progress["done_set"]
            prev_chapters = progress["prev_chapters"]
            
            roll_num, chap_num = int(task["roll_num"]), int(task["chapter_num"])
            chapter_outlines = outline.get("章详细大纲", {}) 
            
            for r in range(1, roll_num + 1):
                for c in range(1, chap_num + 1):
                    key = f"{r}-{c}"
                    txt_path = os.path.join(content_dir, f"{r}-{c}.txt")
                    
                    if key not in chapter_outlines:
                        self.logger.error(f"❌ 大纲缺失: {key} (JSON中未找到该章设定)，跳过生成TXT")
                        continue 
                    
                    if key in done_set:
                        has_context = any(str(p['roll'])==str(r) and str(p['chapter'])==str(c) for p in prev_chapters)
                        if not has_context and os.path.exists(txt_path):
                            try:
                                with open(txt_path, 'r', encoding='utf-8') as f: 
                                    s = f.read()[-500:] 
                                prev_chapters.append({"roll":r, "chapter":c, "summary":s})
                            except IOError as e:
                                self.logger.warning(f"读取已有章节失败: {e}")
                        
                        self.logger.info(f"跳过已完成: {key}")
                        continue
                    
                    content, summary = self.generate_chapter(outline, r, c, prev_chapters, int(task["word_num"]))
                    
                    if content:
                        with open(txt_path, 'w', encoding='utf-8') as f: f.write(content)
                        self.save_progress(excel_path, r, c, summary)
                        done_set.add(key)
                        prev_chapters.append({"roll":r, "chapter":c, "summary":summary})
                        self.logger.info(f"✅ 已生成: {key}")
                        time.sleep(2)
                    else:
                        self.logger.error(f"❌ 生成失败: {key}")
                        
            self.logger.info(f"任务结束: {task_id}")
            self.zip_novel_folder(novel_dir)
            return True
            
        except Exception as e:
            self.logger.exception(f"任务执行过程中发生未捕获异常: {e}")
            return False
        finally:
            # 🟢 恢复标准输出，防止影响后续逻辑（如果有的话）
            sys.stdout = original_stdout
            sys.stderr = original_stderr
            # 显式关闭文件句柄
            try:
                custom_logger.log.close()
            except:
                pass


# ======================== 主入口 ========================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--file', default="novel_gen_tasks.csv")
    parser.add_argument('-i', '--ids', type=str)
    parser.add_argument('--api-key')
    args = parser.parse_args()
    
    # 路径处理
    base_dir = os.path.dirname(os.path.abspath(__file__))
    tasks_csv_path = os.path.join(base_dir, args.file)

    # API Key 优先级：命令行 > 环境变量
    api_key = args.api_key or os.getenv("DEEPSEEK_API_KEY", "")
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    model_name = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    if not api_key: 
        print("Error: No API Key provided.")
        return

    if not os.path.exists(tasks_csv_path):
        print(f"File not found: {tasks_csv_path}")
        return

    # 初始化生成器
    generator = NovelGenerator(api_key, base_url, model_name, base_dir)

    df = pd.read_csv(tasks_csv_path)
    target_ids = []
    if args.ids:
        for p in args.ids.split(','):
            if '-' in p: s,e = map(int, p.split('-')); target_ids.extend(range(s,e+1))
            else: target_ids.append(int(p))
            
    for idx, row in df.iterrows():
        tid = row.get('task_id', idx+1)
        if target_ids and tid not in target_ids: continue
        if row.get('status') == 2: 
            print(f"Skipping completed task_id={tid}")
            continue
        
        # 记录开始时间和状态
        generator.update_task_csv(tasks_csv_path, tid, status=1, gen_start=True)
        
        # 执行任务 (内部会接管日志到 logs/task_[id].log)
        success = generator.process_task(row.to_dict(), tid)
        
        # 记录结束时间和状态
        generator.update_task_csv(tasks_csv_path, tid, status=2 if success else 3, gen_end=True)

if __name__ == "__main__":
    main()