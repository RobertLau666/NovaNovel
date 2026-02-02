#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI小说自动批量生成系统 (智能补全版 - 类封装带日志版 - 增强Excel统计)
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

# ======================== 日志类 ========================
class Logger(object):
    def __init__(self, log_dir: str, task_id: int, task_config: Dict):
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        self.log_file_name = os.path.join(log_dir, f"task_{task_id}.log")
        self.terminal = sys.__stdout__ 
        self.write_in_terminal = False
        self.log = open(self.log_file_name, 'a', encoding='utf-8')
        print(f"📄 [Logger] 日志文件目标: {self.log_file_name}")
        start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        divider = f"\n\n{'='*20} 🚀 新的任务运行开始: {start_time} {'='*20}\n"
        self.log.write(divider)
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
    def __init__(self, api_key: str, base_url: str, model_name: str, tasks_csv_path: str):
        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name

        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.novels_dir = os.path.join(self.base_dir, "novels")
        self.logs_dir = os.path.join(self.base_dir, "logs")
        self.tasks_csv_path = tasks_csv_path
        
        self.max_retries = 3
        self.retry_delay = 5
        self.indent_size = 2
        self.chapter_summary_separator = "#####CHAPTER_SUMMARY_SEPARATOR#####"
        
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%H:%M:%S',
            force=True
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
        # (Prompt 保持不变，省略以节省空间)
        prompt = f'''请参考网络热门或者排行榜靠前的{task["novel_type"]}小说的设定和剧情爽点，写一部小说。

小说想法：{task["novel_idea"]}
文风：{task["write_style"]}
目标读者：{task["target_reader"]}
小说结构：共{task["volume_num"]}卷，每卷{task["chapter_num"]}章，每章约{task["word_num"]}字
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
    "小说卷数": {task["volume_num"]},
    "小说章数": {task["chapter_num"]},
    "每章字数约": {task["word_num"]}
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
1. 根据卷数{task["volume_num"]}，生成对应数量的卷大纲（注意：此步骤不生成章大纲，章大纲会在后续步骤按卷生成）
2. 人物至少3-5个主要角色，每个角色要有完整的设定
3. 只返回JSON，不要任何其他内容
'''
        self.logger.info("正在生成宏观设定（含作品概述、人物设定、卷大纲）...")
        res = self.call_deepseek(prompt, "你是一位专业的网络小说策划师，擅长创作热门爆款小说大纲。请严格按照用户要求的JSON格式返回结果。", 0.9)
        return self.extract_json_from_response(res)

    def generate_volume_chapters(self, outline: Dict, volume_index: int, chapter_count: int) -> Optional[Dict]:
        # (保持原有的生成逻辑)
        overview = outline.get("作品概述", {})
        characters = outline.get("核心设定与人物", {})
        all_volumes = outline.get("卷详细大纲", {})
        
        current_vol_info = all_volumes.get(str(volume_index), {})
        
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

        prompt = f'''你是一位专业的网文大纲师。请根据以下详尽的设定资料，为小说《{overview.get("小说标题")}》的**第{volume_index}卷**创作详细的分章大纲。

【全局设定】
- 类型/文风：{overview.get("类型")} / {overview.get("文风")}
- 核心创意：{overview.get("核心爽点和创意")}
- 简介：{overview.get("小说简介")}

【核心人物表】(请确保人物行为符合人设)
{char_context}

【全书卷结构】
{vol_structure}

【当前生成任务：第{volume_index}卷】
- 本卷标题：{current_vol_info.get("本卷标题", f"第{volume_index}卷")}
- 本卷核心冲突：{current_vol_info.get("本卷核心冲突", "")}
- 本卷关键情节：{current_vol_info.get("本卷关键情节", "")}

【生成要求】
1. 必须生成本卷完整的 **{chapter_count}** 个章节。
2. 严格遵循JSON格式，Key为 "卷数-章数"（如 "{volume_index}-1"）。
3. 每一章必须包含：标题、核心情节梗概（至少3个具体事件点）、关键冲突/爽点。
4. **剧情连贯性**：第一章要承接上一卷（或开篇），最后一章要为下一卷埋伏笔。
5. 返回JSON的键名称一定要跟下面JSON模版的键名称保持一致，例如返回"本章关键冲突/爽点"，而不是“本章关键冲突/爽点补充”

请返回JSON数据：
{{
  "{volume_index}-1": {{
    "本章所属卷次": "{volume_index}",
    "本章次": "1",
    "本章标题": "xxx",
    "本章核心情节梗概": "1.主角... 2.反派... 3.结果...",
    "本章关键冲突/爽点": "xxx",
    "本章人物发展/系统奖励": "xxx"
  }}
  // ... 请务必生成到 {volume_index}-{chapter_count}
}}
'''
        self.logger.info(f"正在基于完整设定生成第 {volume_index} 卷大纲 (共{chapter_count}章)...")
        system_prompt = "你是一位严谨的小说主编，擅长把控长篇小说的剧情结构和人物逻辑一致性。"
        res = self.call_deepseek(prompt, system_prompt, temperature=0.85)
        return self.extract_json_from_response(res)

    def check_and_fix_outline(self, outline: Dict, task: Dict, outline_path: str, novel_dir: str) -> Tuple[Dict, bool]:
        updated = False
        if "章详细大纲" not in outline:
            outline["章详细大纲"] = {}
            
        required_volumes = int(task["volume_num"])
        required_chapters = int(task["chapter_num"])
        current_chapters = outline.get("章详细大纲", {})
        existing_keys = list(current_chapters.keys())
        novel_title = outline.get("作品概述", {}).get("小说标题", "未命名")
        
        for r in range(1, required_volumes + 1):
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
                    if vol_chapters: break
                    time.sleep(3)
                
                if vol_chapters:
                    outline["章详细大纲"].update(vol_chapters)
                    updated = True
                    existing_keys = list(outline["章详细大纲"].keys())
                    self.logger.info(f"✅ 第 {r} 卷大纲补全成功，执行即时保存...")
                    
                    try:
                        with open(outline_path, 'w', encoding='utf-8') as f:
                            json.dump(outline, f, ensure_ascii=False, indent=2)
                    except Exception as e:
                        self.logger.error(f"JSON即时保存失败: {e}")

                    try:
                        self.save_outline_to_excel(outline, novel_dir, novel_title)
                    except Exception as e:
                        self.logger.error(f"Excel即时保存失败: {e}")
                else:
                    self.logger.error(f"❌ 第 {r} 卷大纲补全失败")
                
        return outline, updated

    def save_outline_to_excel(self, outline: Dict, novel_dir: str, novel_title: str) -> str:
        """
        [修改] 增强版 Excel 保存：
        1. 强制指定 Sheet 顺序 (作品概述 -> 人物 -> 卷 -> 章)
        2. 自动添加 chapter_word_num, volume_done, volume_word_num
        3. 严格保留历史数据
        """
        excel_path = os.path.join(novel_dir, "outline.xlsx")
        
        old_chapter_data = {}
        old_volume_data = {}

        # === 1. 备份旧数据 (保持不变) ===
        if os.path.exists(excel_path):
            try:
                # 备份章进度
                old_ch_df = pd.read_excel(excel_path, sheet_name="章详细大纲", index_col=0, dtype=object)
                for idx, row in old_ch_df.iterrows():
                    if self.is_chapter_done(row.get('chapter_done', 0)):
                        old_chapter_data[str(idx)] = {
                            'chapter_done': 1,
                            'chapter_summary': row.get('chapter_summary', ''),
                            'chapter_word_num': row.get('chapter_word_num', 0)
                        }
                # 备份卷进度
                try:
                    old_vol_df = pd.read_excel(excel_path, sheet_name="卷详细大纲", index_col=0, dtype=object)
                    for idx, row in old_vol_df.iterrows():
                         old_volume_data[str(idx)] = {
                             'volume_done': row.get('volume_done', 0),
                             'volume_word_num': row.get('volume_word_num', 0)
                         }
                except: pass
            except Exception as e:
                self.logger.warning(f"读取旧Excel状态时遇到小问题: {e}")

        # === 2. 写入新数据 (修改循环逻辑) ===
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            
            # ✅ [关键修改] 定义期望的 Sheet 顺序
            target_order = ["作品概述", "核心设定与人物", "卷详细大纲", "章详细大纲"]
            
            # 获取大纲中实际存在的所有 key
            existing_keys = list(outline.keys())
            
            # 构建有序列表：先放 target_order 里的，再放剩余没见过的
            sorted_keys = []
            for k in target_order:
                if k in existing_keys:
                    sorted_keys.append(k)
            
            # 把不在目标顺序里的其他 Sheet (如果有) 放到最后
            for k in existing_keys:
                if k not in sorted_keys:
                    sorted_keys.append(k)
            
            # ✅ [关键修改] 按有序列表遍历
            for sheet_name in sorted_keys:
                data = outline[sheet_name]
                
                # === 下面的逻辑完全保持不变 ===
                
                # Case A: 处理 "章详细大纲"
                if sheet_name == "章详细大纲" and isinstance(data, dict):
                    df = pd.DataFrame.from_dict(data, orient='index')
                    
                    if 'chapter_done' not in df.columns: df['chapter_done'] = 0
                    if 'chapter_word_num' not in df.columns: df['chapter_word_num'] = 0
                    if 'chapter_summary' not in df.columns: df['chapter_summary'] = ''
                    df['chapter_summary'] = df['chapter_summary'].astype(object)
                    
                    for idx in df.index:
                        str_idx = str(idx)
                        if str_idx in old_chapter_data:
                            info = old_chapter_data[str_idx]
                            df.at[idx, 'chapter_done'] = 1
                            df.at[idx, 'chapter_word_num'] = info.get('chapter_word_num', 0)
                            if pd.notna(info.get('chapter_summary')):
                                df.at[idx, 'chapter_summary'] = info['chapter_summary']
                    
                    cols = ['本章所属卷次', '本章次', '本章标题', 'chapter_done', 'chapter_word_num', 'chapter_summary'] 
                    other_cols = [c for c in df.columns if c not in cols]
                    df = df[cols + other_cols]
                    df.to_excel(writer, sheet_name=sheet_name, index=True)

                # Case B: 处理 "卷详细大纲"
                elif sheet_name == "卷详细大纲" and isinstance(data, dict):
                    df = pd.DataFrame.from_dict(data, orient='index')
                    
                    if 'volume_done' not in df.columns: df['volume_done'] = 0
                    if 'volume_word_num' not in df.columns: df['volume_word_num'] = 0
                    
                    for idx in df.index:
                        str_idx = str(idx)
                        if str_idx in old_volume_data:
                            info = old_volume_data[str_idx]
                            df.at[idx, 'volume_done'] = info.get('volume_done', 0)
                            df.at[idx, 'volume_word_num'] = info.get('volume_word_num', 0)
                    
                    df.to_excel(writer, sheet_name=sheet_name, index=True)

                # Case C: 其他 Sheet
                elif isinstance(data, dict):
                    first_val = next(iter(data.values()), None)
                    if isinstance(first_val, dict):
                        df = pd.DataFrame.from_dict(data, orient='index')
                    else:
                        df = pd.DataFrame([data])
                    df.to_excel(writer, sheet_name=sheet_name[:31])
                else:
                    pd.DataFrame([{"内容": data}]).to_excel(writer, sheet_name=sheet_name[:31])
        
        self.logger.info(f"Excel大纲结构已更新: {excel_path}")
        return excel_path

    # ======================== 内容生成模块 ========================

    def build_chapter_context(self, outline: Dict, volume_num: int, chapter_num: int, prev_chapters: list) -> Tuple[str, str]:
        # (保持不变)
        chapter_key = f"{volume_num}-{chapter_num}"
        chapters = outline.get("章详细大纲", {})
        chapter_outline = chapters.get(chapter_key, {})
        
        if not chapter_outline:
            chapter_title = f"第{chapter_num}章"
            core_plot = "剧情自由发展"
        else:
            chapter_title = chapter_outline.get("本章标题", f"第{chapter_num}章")
            core_plot = chapter_outline.get("本章核心情节梗概", "")

        volume_info = outline.get("卷详细大纲", {}).get(str(volume_num), {})
        
        context = f"""
【小说信息】
小说标题：{outline.get("作品概述", {}).get("小说标题")}

【当前卷信息】
本卷标题：{volume_info.get("本卷标题", "")}
本卷关键情节：{volume_info.get("本卷关键情节", "")}

【本章大纲】
章节：第{volume_num}卷 第{chapter_num}章《{chapter_title}》
核心情节：{core_plot}
关键冲突：{chapter_outline.get("本章关键冲突/爽点", "")}
"""
        if prev_chapters:
            context += "\n【前情提要】\n"
            for prev in prev_chapters[-3:]:
                context += f"第{prev['volume']}卷{prev['chapter']}章：{prev['chapter_summary']}\n"
                
        return context, chapter_title

    def post_process_content(self, content: str, volume: int, chapter: int, title: str) -> str:
        lines = content.split('\n')
        processed = [f"第{volume}卷 第{chapter}章：{title}\n"]
        for line in lines:
            line = line.strip().replace("#####", "")
            if line and line not in title and "SUMMARY" not in line:
                processed.append(f"{'\u3000' * self.indent_size}{line}\n")
        return "\n".join(processed)

    def generate_chapter(self, outline: Dict, volume: int, chapter: int, prev_chapters: list, word_num: int) -> Tuple[Optional[str], Optional[str]]:
        context, title = self.build_chapter_context(outline, volume, chapter, prev_chapters)
        
        prompt = f"""{context}
请撰写正文（约{word_num}字）。
要求：场景描写细腻，对话符合人设，严禁流水账。
格式：正文结束后，换行输出 "{self.chapter_summary_separator}"，再写300字摘要。
"""
        self.logger.info(f"正在生成: {volume}-{chapter} {title}")
        res = self.call_deepseek(prompt, "你是一位网文大神。", 0.85)
        if not res: return None, None
        
        parts = res.split(self.chapter_summary_separator)
        content = parts[0].strip()
        chapter_summary = parts[1].strip() if len(parts) > 1 else content[-400:]
        
        return self.post_process_content(content, volume, chapter, title), chapter_summary

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
                    if pd.notna(row.get('chapter_summary')):
                        prog["prev_chapters"].append({
                            "volume": r, "chapter": c, 
                            "chapter_summary": str(row['chapter_summary'])
                        })
        except Exception as e:
            self.logger.warning(f"加载进度失败: {e}")
        return prog

    def save_progress(self, excel_path: str, r: int, c: int, chapter_summary: str, word_count: int):
        """
        [修改] 增加 word_count 参数，写入 chapter_word_num
        """
        try:
            with pd.ExcelFile(excel_path) as xls:
                sheets = {s: pd.read_excel(xls, s, index_col=0) for s in xls.sheet_names}
            
            if "章详细大纲" in sheets:
                df = sheets["章详细大纲"]
                df['chapter_summary'] = df['chapter_summary'].astype(object)
                
                # 确保列存在
                if 'chapter_word_num' not in df.columns: df['chapter_word_num'] = 0

                mask = (df['本章所属卷次'].astype(str) == str(r)) & (df['本章次'].astype(str) == str(c))
                if mask.any():
                    df.loc[mask, 'chapter_done'] = 1
                    df.loc[mask, 'chapter_summary'] = chapter_summary
                    df.loc[mask, 'chapter_word_num'] = word_count # 写入字数

            with pd.ExcelWriter(excel_path, engine='openpyxl') as w:
                for n, d in sheets.items(): d.to_excel(w, sheet_name=n)
        except Exception as e:
            self.logger.error(f"保存进度失败: {e}")

    def update_volume_progress(self, excel_path: str, volume_num: int):
        """
        [新增] 统计并更新某一卷的完成状态和总字数
        """
        try:
            with pd.ExcelFile(excel_path) as xls:
                if "章详细大纲" not in xls.sheet_names or "卷详细大纲" not in xls.sheet_names: return
                df_chapters = pd.read_excel(xls, "章详细大纲", index_col=0)
                df_volumes = pd.read_excel(xls, "卷详细大纲", index_col=0)
                other_sheets = {s: pd.read_excel(xls, s, index_col=0) for s in xls.sheet_names 
                                if s not in ["章详细大纲", "卷详细大纲"]}

            # 1. 统计该卷的所有章节
            volume_mask = df_chapters['本章所属卷次'].astype(str) == str(volume_num)
            chapter_rows = df_chapters[volume_mask]
            
            if chapter_rows.empty: return

            total_chapters = len(chapter_rows)
            done_count = chapter_rows['chapter_done'].apply(lambda x: 1 if self.is_chapter_done(x) else 0).sum()
            current_volume_words = chapter_rows['chapter_word_num'].fillna(0).sum()
            is_volume_done = 1 if done_count >= total_chapters else 0
            
            self.logger.info(f"📊 第 {volume_num} 卷统计: 进度 {done_count}/{total_chapters}, 总字数 {current_volume_words}")

            # 2. 更新卷大纲
            if 'volume_done' not in df_volumes.columns: df_volumes['volume_done'] = 0
            if 'volume_word_num' not in df_volumes.columns: df_volumes['volume_word_num'] = 0
            
            vol_key = str(volume_num)
            # 兼容索引类型
            if vol_key in df_volumes.index.astype(str):
                try:
                     df_volumes.loc[int(vol_key), 'volume_done'] = is_volume_done
                     df_volumes.loc[int(vol_key), 'volume_word_num'] = current_volume_words
                except KeyError:
                     df_volumes.loc[vol_key, 'volume_done'] = is_volume_done
                     df_volumes.loc[vol_key, 'volume_word_num'] = current_volume_words

            # 3. 保存
            with pd.ExcelWriter(excel_path, engine='openpyxl') as w:
                df_chapters.to_excel(w, sheet_name="章详细大纲")
                df_volumes.to_excel(w, sheet_name="卷详细大纲")
                for n, d in other_sheets.items(): d.to_excel(w, sheet_name=n)
                
        except Exception as e:
            self.logger.error(f"更新卷进度失败: {e}")

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
        try:
            self.logger.info("正在打包文件以便下载...")
            zip_path = shutil.make_archive(novel_dir, 'zip', novel_dir)
            self.logger.info(f"📦 打包成功! 下载路径: {zip_path}")
            return zip_path
        except Exception as e:
            self.logger.error(f"❌ 打包失败: {e}")
            return None

    # ======================== 处理单个任务 ========================

    def process_task(self, task: Dict, task_id: int) -> bool:
        # 🟢 设置 Logger 并接管 stdout/stderr
        custom_logger = Logger(os.path.join(self.logs_dir, os.path.splitext(os.path.basename(self.tasks_csv_path))[0]), task_id, task)
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        
        # 1. 重定向系统输出
        sys.stdout = custom_logger
        sys.stderr = custom_logger
        
        # 🟢 [关键修改] 2. 强制重新配置 logging，让它输出到新的 sys.stdout (即 custom_logger)
        # 这样 logger.info 的内容就会经过 custom_logger.write，从而同时写入文件和终端
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
            
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%H:%M:%S',
            stream=sys.stdout, # 这里现在指向 custom_logger
            force=True
        )
        
        # 更新 self.logger (确保它使用新的配置)
        self.logger = logging.getLogger(__name__)
        
        try:
            self.logger.info(f"开始处理任务 task_id={task_id}") # 这句话现在会出现在日志文件里了！
            
            novel_dir = os.path.join(self.novels_dir, os.path.splitext(os.path.basename(self.tasks_csv_path))[0], f"task_{task_id}")
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
            
            self.update_task_csv(self.tasks_csv_path, task_id, outline_done=1)
                
            content_dir = os.path.join(novel_dir, "content")
            os.makedirs(content_dir, exist_ok=True)
            
            # 3. 准备生成
            progress = self.load_progress(excel_path)
            done_set = progress["done_set"]
            prev_chapters = progress["prev_chapters"]
            
            volume_num, chap_num = int(task["volume_num"]), int(task["chapter_num"])
            chapter_outlines = outline.get("章详细大纲", {}) 
            
            for r in range(1, volume_num + 1):
                # 标记该卷是否有变动
                is_volume_dirty = False 

                for c in range(1, chap_num + 1):
                    key = f"{r}-{c}"
                    txt_path = os.path.join(content_dir, f"{r}-{c}.txt")
                    
                    if key not in chapter_outlines:
                        self.logger.error(f"❌ 大纲缺失: {key} (JSON中未找到该章设定)，跳过生成TXT")
                        continue 
                    
                    if key in done_set:
                        # (跳过逻辑保持不变)
                        has_context = any(str(p['volume'])==str(r) and str(p['chapter'])==str(c) for p in prev_chapters)
                        if not has_context and os.path.exists(txt_path):
                            try:
                                with open(txt_path, 'r', encoding='utf-8') as f: 
                                    s = f.read()[-500:] 
                                prev_chapters.append({"volume":r, "chapter":c, "chapter_summary":s})
                            except IOError as e:
                                self.logger.warning(f"读取已有章节失败: {e}")
                        
                        self.logger.info(f"跳过已完成: {key}")
                        # 即使跳过，也要标记可能需要更新卷状态(防止上次crash没更新卷状态)
                        is_volume_dirty = True
                        continue
                    
                    content, chapter_summary = self.generate_chapter(outline, r, c, prev_chapters, int(task["word_num"]))
                    
                    # [修改] 计算字数
                    content_len = len(content) if content else 0

                    if content:
                        with open(txt_path, 'w', encoding='utf-8') as f: f.write(content)
                        
                        # [修改] 传入字数
                        self.save_progress(excel_path, r, c, chapter_summary, content_len)
                        
                        done_set.add(key)
                        prev_chapters.append({"volume":r, "chapter":c, "chapter_summary":chapter_summary})
                        self.logger.info(f"✅ 已生成: {key} (字数: {content_len})")
                        is_volume_dirty = True
                        time.sleep(2)
                    else:
                        self.logger.error(f"❌ 生成失败: {key}")
                
                # [新增] 卷循环结束，更新卷统计
                if is_volume_dirty:
                    self.logger.info(f"🔄 正在更新第 {r} 卷的统计信息...")
                    self.update_volume_progress(excel_path, r)
            
            self.logger.info(f"任务结束: {task_id}")
            self.zip_novel_folder(novel_dir)
            return True
            
        except Exception as e:
            self.logger.exception(f"任务执行过程中发生未捕获异常: {e}")
            return False
        finally:
            # 🟢 恢复现场
            
            # 1. 恢复 logging 到标准输出 (防止影响下一个任务或主程序)
            for handler in logging.root.handlers[:]:
                logging.root.removeHandler(handler)
            
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s [%(levelname)s] %(message)s',
                datefmt='%H:%M:%S',
                stream=original_stdout, # 恢复到原来的终端
                force=True
            )
            self.logger = logging.getLogger(__name__)

            # 2. 恢复 stdout/stderr
            sys.stdout = original_stdout
            sys.stderr = original_stderr
            
            # 3. 关闭文件句柄
            try:
                custom_logger.log.close()
            except:
                pass

# ======================== 主入口 (保持不变) ========================
def main():
    # 加载 .env 文件
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--tasks_csv_path', default="./csvs/novel_gen_tasks_test.csv")
    parser.add_argument('-i', '--task_ids', type=str)
    parser.add_argument('--api-key')
    args = parser.parse_args()
    
    api_key = args.api_key or os.getenv("DEEPSEEK_API_KEY", "")
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    model_name = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    if not api_key: 
        print("Error: No API Key provided.")
        return

    if not os.path.exists(args.tasks_csv_path):
        print(f"File not found: {args.tasks_csv_path}")
        return

    generator = NovelGenerator(api_key, base_url, model_name, args.tasks_csv_path)

    df = pd.read_csv(args.tasks_csv_path)
    target_task_ids = []
    if args.task_ids:
        for p in args.task_ids.split(','):
            if '-' in p: s,e = map(int, p.split('-')); target_task_ids.extend(range(s,e+1))
            else: target_task_ids.append(int(p))
            
    for idx, row in df.iterrows():
        tid = row.get('task_id', idx+1)
        if target_task_ids and tid not in target_task_ids: continue
        if row.get('status') == 2: 
            print(f"Skipping completed task_id={tid}")
            continue
        
        generator.update_task_csv(args.tasks_csv_path, tid, status=1, gen_start=True)
        success = generator.process_task(row.to_dict(), tid)
        generator.update_task_csv(args.tasks_csv_path, tid, status=2 if success else 3, gen_end=True)

if __name__ == "__main__":
    main()