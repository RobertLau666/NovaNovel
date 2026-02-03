#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI小说自动批量生成系统 (智能补全版 - 类封装带日志版 - 增强Excel统计)
"""

import os
import sys
import re
import json
import json_repair
import time
import requests
import shutil
import argparse
import logging
import http.client
import pandas as pd
from datetime import datetime
from openai import OpenAI
from typing import Optional, Dict, Any, List, Tuple
from dotenv import load_dotenv
from concurrent.futures import ProcessPoolExecutor
import style_guides

# ======================== 日志类 ========================
class Logger(object):
    def __init__(self, log_file_path: str, task_config: Dict):
        self.log_file_path = log_file_path
        self.terminal = sys.__stdout__
        self.write_in_terminal = False
        self.log = open(self.log_file_path, 'a', encoding='utf-8')
        print(f"📄 [Logger] 日志文件目标: {self.log_file_path}")
        start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        divider = f"\n\n{'='*20} 🚀 新的任务运行开始: {start_time} {'='*20}\n"
        self.log.write(divider)
        config_str = f"Task Config = \n{json.dumps(task_config, indent=4, ensure_ascii=False, default=str)}\n"
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

class DeepSeekClient:
    def __init__(self, api_key: str, base_url: str, model_name: str, max_retries: int = 3, retry_delay: int = 5):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model_name = model_name
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.logger = logging.getLogger(__name__)

    def call(self, prompt: str, system_prompt: str = None, temperature: float = 0.8) -> Optional[str]:
        """
        统一的 API 调用入口
        """
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
                self.logger.warning(f"API调用失败 ({attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
        
        self.logger.error("API调用多次失败，放弃请求。")
        return None

class DMXImageAPIGenerator:
    def __init__(self, api_key: str, api_host: str = "www.dmxapi.com"):
        self.api_key = api_key
        self.api_host = api_host
        self.api_endpoint = "/v1/images/generations"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "User-Agent": "DMXAPI/1.0.0 (https://www.dmxapi.com)",
            "Content-Type": "application/json",
        }

    def generate_image(self, prompt: str, model: str = "sora_image", size: str = "936x1664", max_retries: int = 10, retry_interval: int = 5) -> str:
        # model: "hunyuan-large", # "seedream-3.0", # "dall-e-3", # "sora_image", # "gpt-4o-image"
        """发送图像生成请求并返回图片 URL，失败时自动重试"""
        payload = json.dumps({
            "prompt": prompt,
            "n": 1,
            "model": model,
            "size": size,
        })

        for attempt in range(1, max_retries + 1):
            try:
                conn = http.client.HTTPSConnection(self.api_host)
                conn.request("POST", self.api_endpoint, payload, self.headers)
                res = conn.getresponse()
                data = res.read().decode("utf-8").replace("\\u0026", "&")
                data_dict = json.loads(data)
                img_url = data_dict["data"][0]["url"]
                print(f"✅ 成功获取图片 URL: {img_url}")
                return img_url

            except (json.JSONDecodeError, KeyError, IndexError) as e:
                print(f"⚠️ 第 {attempt}/{max_retries} 次尝试失败：{e}")
                print(f"原始响应内容: {data}")
                if attempt < max_retries:
                    print(f"⏳ 等待 {retry_interval}s 后重试...\n")
                    time.sleep(retry_interval)
                else:
                    print("❌ 图片生成失败，已达最大重试次数")

        return None

# ======================== AI 小说生成器类 ========================
class NovelGenerator:
    def __init__(self, llm_client: DeepSeekClient, img_generator: DMXImageAPIGenerator, tasks_csv_path: str):
        # 🟢 1. 接收外部传入的 client 实例
        self.llm = llm_client 
        self.img_generator = img_generator 
        
        # 路径设置
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.novels_dir = os.path.join(self.base_dir, "novels")
        self.logs_dir = os.path.join(self.base_dir, "logs")
        self.tasks_csv_path = tasks_csv_path
        
        # 其他配置
        self.indent_size = 2
        self.chapter_summary_separator = "#####CHAPTER_SUMMARY_SEPARATOR#####"

        self.cover_nums = 4
        self.cover_size = "800x1066"

        # 🟢 [新增] 上下文回溯配置
        self.context_prev_vol_num = 10  # 往前回顾多少卷
        self.context_prev_chap_num = 3  # 往前回顾多少章

        self.style_guide = style_guides.style_guide_dict['v5']['prompt']

        # 初始化 Logger 配置 (保持原样，或者放在 main 中也可，这里保留以防万一)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%H:%M:%S',
            force=True
        )
        self.logger = logging.getLogger(__name__)

    # def extract_json_from_response(self, text: str) -> Optional[Dict]:
    #     if not text: return None
        
    #     # 🟢 [修改] 尝试解析，如果失败，记录原始文本以便调试
    #     try:
    #         # 1. 尝试直接解析
    #         return json.loads(text)
    #     except (json.JSONDecodeError, ValueError):
    #         pass
            
    #     # 2. 尝试提取 Markdown 代码块
    #     patterns = [r'```json\s*([\s\S]*?)\s*```', r'```\s*([\s\S]*?)\s*```']
    #     for p in patterns:
    #         m = re.search(p, text)
    #         if m:
    #             try: 
    #                 return json.loads(m.group(1))
    #             except (json.JSONDecodeError, ValueError): 
    #                 continue
        
    #     # 3. 尝试寻找最外层的大括号
    #     try:
    #         s, e = text.find('{'), text.rfind('}')
    #         if s != -1 and e != -1: 
    #             # 尝试修复常见的尾部逗号问题
    #             json_str = text[s:e+1]
    #             json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
    #             return json.loads(json_str)
    #     except (json.JSONDecodeError, ValueError): 
    #         pass
            
    #     # 🟢 [新增] 如果所有方法都失败，打印错误日志
    #     self.logger.error(f"❌ JSON解析彻底失败。原始返回内容如下:\n{text[:500]}...\n(后略)")
    #     return None

    def extract_json_from_response(self, text: str) -> Optional[Dict]:
        if not text: return None
        
        # 🟢 方案一：尝试使用 json_repair (神器，能修复绝大多数 LLM 格式错误)
        try:
            import json_repair
            decoded_obj = json_repair.loads(text)
            # json_repair 有时会把纯文本误判为字符串，这里做个双重检查
            if isinstance(decoded_obj, dict):
                return decoded_obj
        except ImportError:
            # 如果用户没装这个库，就在日志里提醒一下
            self.logger.warning("建议 pip install json_repair 以获得更强的容错能力")
        except Exception:
            pass # 继续尝试下面的手动方法

        # 🟢 方案二：手动清洗 Markdown 标记 (增强版)
        # 即使没有闭合的 ``` 也能提取
        clean_text = text.strip()
        
        # 移除开头的 ```json 或 ```
        clean_text = re.sub(r'^```(json)?\s*', '', clean_text, flags=re.IGNORECASE)
        # 移除结尾的 ``` 
        clean_text = re.sub(r'\s*```$', '', clean_text)
        
        try:
            return json.loads(clean_text)
        except (json.JSONDecodeError, ValueError):
            pass

        # 🟢 方案三：寻找最外层大括号 (容错截断)
        try:
            s = text.find('{')
            e = text.rfind('}')
            if s != -1 and e != -1: 
                json_str = text[s:e+1]
                # 尝试修复尾部逗号
                json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
                # 尝试去除注释 //
                json_str = re.sub(r'(?<!:)//.*$', '', json_str, flags=re.MULTILINE)
                return json.loads(json_str)
        except (json.JSONDecodeError, ValueError): 
            pass
            
        # 失败日志
        self.logger.error(f"❌ JSON解析彻底失败。原始返回内容如下:\n{text[:500]}...\n(后略)")
        return None

    # ======================== 大纲生成与修复模块 ========================

    def generate_global_settings(self, task: Dict) -> Optional[Dict]:
        prompt = f'''你是一位不仅精通爽文套路，更擅长“反套路”和“脑洞文”的顶尖网文大神。
请根据以下要求，构思一部甚至能霸榜的{task["novel_type"]}小说。

【基础信息】
- 创意/脑洞：{task["novel_idea"]}
- 目标受众：{task["target_reader"]} (偏好快节奏、高爽点、有趣味)
- 结构：共{task["volume_num"]}卷，每卷{task["chapter_num"]}章，每章约{task["chapter_word_num"]}字
- 备注：{task["note"]}

【通用质量标准】
{self.style_guide}

【本特定任务风格要求】
{task.get("write_style", "精彩网文")}

【任务要求】
请生成小说的宏观设定，严格返回以下JSON格式：
{{
  "作品概述": {{
    "小说标题": "《取一个极具网感、吸引眼球的标题》",
    "小说副标题": "xxx",
    "小说简介": "写一个黄金三章式的简介，突出金手指、核心矛盾和爽点，让人看一眼就想点进去",
    "类型": "{task["novel_type"]}",
    "文风": "{task["write_style"]}",
    "核心爽点和创意": "xxx",
    "市场分析与亮点总结": "xxx",
    "小说卷数": {task["volume_num"]},
    "小说章数": {task["chapter_num"]},
    "每章字数约": {task["chapter_word_num"]}
  }},
  "核心设定与人物": {{
    "1": {{
      "姓名": "xxx (主角)",
      "身份": "xxx",
      "年龄": "xx岁",
      "外貌特征": "xxx",
      "核心性格": "用3个词形容 (如: 究极咸鱼、被迫害妄想症、逻辑鬼才)",
      "金手指/能力": "详细描述系统的功能或特殊能力",
      "口头禅/标志性动作": "xxx",
      "与主角关系": "主角"
    }},
    "2": {{
      "姓名": "xxx（高智商反派/重要配角）",
      "身份": "xxx",
      "年龄": "xx岁",
      "外貌特征": "xxx",
      "核心性格": "拒绝脸谱化，要有独特魅力或执念",
      "金手指/能力": "详细描述系统的功能或特殊能力（若没有，可以填无）",
      "口头禅/标志性动作": "xxx（若没有，可以填无）",
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
2. 人物至少5-10个主要角色，每个角色要有完整的设定，人物关系要错综复杂
3. 只返回JSON，不要任何其他内容
'''
        self.logger.info("正在生成宏观设定（含作品概述、人物设定、卷大纲）...")
        # 🟢 [修改] temperature=1.0 (最大化脑洞)，将 1.0 改为 0.9，提高 JSON 格式稳定性
        res = self.llm.call(prompt, "你是一位专业的网络小说策划师，擅长创作热门爆款小说大纲。请严格按照用户要求的JSON格式返回结果。", 0.9)
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

        prompt = f'''你是一位对剧情节奏把控极强的网文主编。请基于以下设定，为《{overview.get("小说标题")}》第{volume_index}卷创作分章细纲。

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

【剧情节奏分布要求】
请将本卷的 {chapter_count} 个章节按“剧情小弧段”进行排布。请确保章节之间具备明显的“呼吸感”，严禁全程高能。请遵循以下节奏模式：
1. **铺垫与探索 (25%)**：介绍背景，埋下伏笔，节奏轻快，展现世界观的奇观感。
2. **矛盾与蓄势 (35%)**：冲突初现，反派挑衅或遇到难题，给读者“憋屈感”或期待感。
3. **爆发与逆袭 (25%)**：全书的高能时刻。爽点爆发，底牌尽出，节奏极快，强调冲击力。
4. **沉淀与收获 (15%)**：节奏放缓，描写主角的心理变化、战利品整理、以及周围人的评价（侧面衬托）。

【生成要求】
1. **生成数量**：必须生成本卷完整的 **{chapter_count}** 个章节。
2. **剧情逻辑**：情节发展要意料之外情理之中，利用“信息差”制造爽点（迪化流）。
3. **拒绝水文**：每一章必须有一个具体的“事件钩子”或“笑点/爽点”，禁止平铺直叙。
4. **连贯性**：
   - 第一章：如果是全书开头，必须遵循“黄金三秒”，直接切入冲突。如果是卷首，要承接上卷余韵并开启新地图。
   - 每一章结尾：必须留有“小钩子”（悬念），让人忍不住点下一章。
5. 返回JSON的键名称一定要跟下面JSON模版的键名称保持一致，例如返回"本章关键冲突/爽点"，而不是“本章关键冲突/爽点补充”

请返回JSON数据 (Key格式 "{volume_index}-1"):
{{
  "{volume_index}-1": {{
    "本章所属卷次": "{volume_index}",
    "本章次": "1",
    "本章标题": "取一个有噱头、让人想点击的标题",
    "本章核心情节梗概": "1. 开篇即高能... 2. 主角骚操作... 3. 反派自我脑补...",
    "本章节奏类型": "可选值：[铺垫/蓄势/高潮/沉淀]", 
    "本章情绪基调": "悬疑/好奇/压抑/愤怒/...",
    "本章关键冲突/爽点": "具体描述打脸或震惊的瞬间",
    "本章伏笔/悬念": "结尾留下的悬念"
  }}
  // ...
}}
'''

        self.logger.info(f"正在基于完整设定生成第 {volume_index} 卷的章详细大纲 (共{chapter_count}章)...")
        system_prompt = "你是一位严谨的小说主编，擅长把控长篇小说的剧情结构和人物逻辑一致性。"
        # 🟢 [修改] temperature=0.95 (增加剧情变数和精彩度)
        res = self.llm.call(prompt, system_prompt, temperature=0.95)
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
                self.logger.warning(f"⚠️  未检测到 第 {r} 卷的章详细大纲，开始补全...")
                vol_chapters = None
                for retry in range(3):
                    vol_chapters = self.generate_volume_chapters(outline, r, required_chapters)
                    if vol_chapters: break
                    time.sleep(3)
                
                if vol_chapters:
                    outline["章详细大纲"].update(vol_chapters)
                    updated = True
                    existing_keys = list(outline["章详细大纲"].keys())
                    self.logger.info(f"✅ 第 {r} 卷的章详细大纲补全成功，执行即时保存...")
                    
                    try:
                        with open(outline_path, 'w', encoding='utf-8') as f:
                            json.dump(outline, f, ensure_ascii=False, indent=2)
                    except Exception as e:
                        self.logger.error(f"JSON即时保存失败: {e}")

                    try:
                        self.save_outline_to_excel(outline, novel_dir, novel_title, task_data=task)
                    except Exception as e:
                        self.logger.error(f"Excel即时保存失败: {e}")
                else:
                    self.logger.error(f"❌ 第 {r} 卷的章详细大纲补全失败")
                
        return outline, updated

    # def save_outline_to_excel(self, outline: Dict, novel_dir: str, novel_title: str) -> str:
    #     """
    #     [修改] 增强版 Excel 保存：
    #     1. 强制指定 Sheet 顺序 (作品概述 -> 人物 -> 卷 -> 章)
    #     2. 自动添加列 “本章字数“, “本卷完成情况“, “本卷字数”
    #     3. 严格保留历史数据
    #     """
    #     excel_path = os.path.join(novel_dir, "outline.xlsx")
        
    #     old_chapter_data = {}
    #     old_volume_data = {}

    #     # === 1. 备份旧数据 (保持不变) ===
    #     if os.path.exists(excel_path):
    #         try:
    #             # 备份章进度
    #             old_ch_df = pd.read_excel(excel_path, sheet_name="章详细大纲", index_col=0, dtype=object)
    #             for idx, row in old_ch_df.iterrows():
    #                 if self.is_chapter_done(row.get('本章完成情况', 0)):
    #                     old_chapter_data[str(idx)] = {
    #                         '本章完成情况': 1,
    #                         '本章总结': row.get('本章总结', ''),
    #                         '本章字数': row.get('本章字数', 0)
    #                     }
    #             # 备份卷进度
    #             try:
    #                 old_vol_df = pd.read_excel(excel_path, sheet_name="卷详细大纲", index_col=0, dtype=object)
    #                 for idx, row in old_vol_df.iterrows():
    #                      old_volume_data[str(idx)] = {
    #                          '本卷完成情况': row.get('本卷完成情况', 0),
    #                          '本卷字数': row.get('本卷字数', 0)
    #                      }
    #             except: pass
    #         except Exception as e:
    #             self.logger.warning(f"读取旧Excel状态时遇到小问题: {e}")

    #     # === 2. 写入新数据 (修改循环逻辑) ===
    #     with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            
    #         # ✅ [关键修改] 定义期望的 Sheet 顺序
    #         target_order = ["作品概述", "核心设定与人物", "卷详细大纲", "章详细大纲"]
            
    #         # 获取大纲中实际存在的所有 key
    #         existing_keys = list(outline.keys())
            
    #         # 构建有序列表：先放 target_order 里的，再放剩余没见过的
    #         sorted_keys = []
    #         for k in target_order:
    #             if k in existing_keys:
    #                 sorted_keys.append(k)
            
    #         # 把不在目标顺序里的其他 Sheet (如果有) 放到最后
    #         for k in existing_keys:
    #             if k not in sorted_keys:
    #                 sorted_keys.append(k)
            
    #         # ✅ [关键修改] 按有序列表遍历
    #         for sheet_name in sorted_keys:
    #             data = outline[sheet_name]
                
    #             # === 下面的逻辑完全保持不变 ===
                
    #             # Case A: 处理 "章详细大纲"
    #             if sheet_name == "章详细大纲" and isinstance(data, dict):
    #                 df = pd.DataFrame.from_dict(data, orient='index')
                    
    #                 if '本章完成情况' not in df.columns: df['本章完成情况'] = 0
    #                 if '本章字数' not in df.columns: df['本章字数'] = 0
    #                 if '本章总结' not in df.columns: df['本章总结'] = ''
    #                 df['本章总结'] = df['本章总结'].astype(object)
                    
    #                 for idx in df.index:
    #                     str_idx = str(idx)
    #                     if str_idx in old_chapter_data:
    #                         info = old_chapter_data[str_idx]
    #                         df.at[idx, '本章完成情况'] = 1
    #                         df.at[idx, '本章字数'] = info.get('本章字数', 0)
    #                         if pd.notna(info.get('本章总结')):
    #                             df.at[idx, '本章总结'] = info['本章总结']
                    
    #                 cols = ['本章所属卷次', '本章次', '本章标题', '本章完成情况', '本章字数', '本章总结'] 
    #                 other_cols = [c for c in df.columns if c not in cols]
    #                 df = df[cols + other_cols]
    #                 df.to_excel(writer, sheet_name=sheet_name, index=True)

    #             # Case B: 处理 "卷详细大纲"
    #             elif sheet_name == "卷详细大纲" and isinstance(data, dict):
    #                 df = pd.DataFrame.from_dict(data, orient='index')
                    
    #                 if '本卷完成情况' not in df.columns: df['本卷完成情况'] = 0
    #                 if '本卷字数' not in df.columns: df['本卷字数'] = 0
                    
    #                 for idx in df.index:
    #                     str_idx = str(idx)
    #                     if str_idx in old_volume_data:
    #                         info = old_volume_data[str_idx]
    #                         df.at[idx, '本卷完成情况'] = info.get('本卷完成情况', 0)
    #                         df.at[idx, '本卷字数'] = info.get('本卷字数', 0)
                    
    #                 df.to_excel(writer, sheet_name=sheet_name, index=True)

    #             # Case C: 其他 Sheet
    #             elif isinstance(data, dict):
    #                 first_val = next(iter(data.values()), None)
    #                 if isinstance(first_val, dict):
    #                     df = pd.DataFrame.from_dict(data, orient='index')
    #                 else:
    #                     df = pd.DataFrame([data])
    #                 df.to_excel(writer, sheet_name=sheet_name[:31])
    #             else:
    #                 pd.DataFrame([{"内容": data}]).to_excel(writer, sheet_name=sheet_name[:31])
        
    #     self.logger.info(f"Excel大纲结构已更新: {excel_path}")
    #     return excel_path

    # 在 NovelGenerator 类中修改此方法
    # def save_outline_to_excel(self, outline: Dict, novel_dir: str, novel_title: str, task_data: Dict = None) -> str:
    #     """
    #     [修改版] 增强版 Excel 保存：
    #     1. 增加“用户初始设定” Sheet
    #     2. 强制指定 Sheet 顺序 (用户初始设定 -> 作品概述 -> 核心设定与人物 -> 卷详细大纲 -> 章详细大纲)
    #     """
    #     excel_path = os.path.join(novel_dir, "outline.xlsx")
        
    #     old_chapter_data = {}
    #     old_volume_data = {}

    #     # === 1. 备份旧数据 (逻辑不变) ===
    #     if os.path.exists(excel_path):
    #         try:
    #             old_ch_df = pd.read_excel(excel_path, sheet_name="章详细大纲", index_col=0, dtype=object)
    #             for idx, row in old_ch_df.iterrows():
    #                 if self.is_chapter_done(row.get('本章完成情况', 0)):
    #                     old_chapter_data[str(idx)] = {
    #                         '本章完成情况': 1,
    #                         '本章总结': row.get('本章总结', ''),
    #                         '本章字数': row.get('本章字数', 0)
    #                     }
    #             try:
    #                 old_vol_df = pd.read_excel(excel_path, sheet_name="卷详细大纲", index_col=0, dtype=object)
    #                 for idx, row in old_vol_df.iterrows():
    #                      old_volume_data[str(idx)] = {
    #                          '本卷完成情况': row.get('本卷完成情况', 0),
    #                          '本卷字数': row.get('本卷字数', 0)
    #                      }
    #             except: pass
    #         except Exception as e:
    #             self.logger.warning(f"读取旧Excel状态时遇到小问题: {e}")

    #     # === 2. 准备数据并写入 ===
    #     with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
    #         # 🟢 [关键修改] 定义期望的 Sheet 顺序，把初始设定排在第一位
    #         target_order = ["用户初始设定", "作品概述", "核心设定与人物", "卷详细大纲", "章详细大纲"]
            
    #         # 构建一个临时字典存储所有要写的 Dataframe
    #         all_sheets_to_write = {}

    #         # 写入“用户初始设定”
    #         if task_data:
    #             all_sheets_to_write["用户初始设定"] = pd.DataFrame([task_data])

    #         # 填充其他大纲数据
    #         for k, v in outline.items():
    #             if k == "章详细大纲":
    #                 df = pd.DataFrame.from_dict(v, orient='index')
    #                 if '本章完成情况' not in df.columns: df['本章完成情况'] = 0
    #                 if '本章字数' not in df.columns: df['本章字数'] = 0
    #                 if '本章总结' not in df.columns: df['本章总结'] = ''
    #                 for idx in df.index:
    #                     str_idx = str(idx)
    #                     if str_idx in old_chapter_data:
    #                         info = old_chapter_data[str_idx]
    #                         df.at[idx, '本章完成情况'] = 1
    #                         df.at[idx, '本章字数'] = info.get('本章字数', 0)
    #                         if pd.notna(info.get('本章总结')): df.at[idx, '本章总结'] = info['本章总结']
    #                 cols = ['本章所属卷次', '本章次', '本章标题', '本章完成情况', '本章字数', '本章总结'] 
    #                 other_cols = [c for c in df.columns if c not in cols]
    #                 all_sheets_to_write[k] = df[cols + other_cols]
                
    #             elif k == "卷详细大纲":
    #                 df = pd.DataFrame.from_dict(v, orient='index')
    #                 if '本卷完成情况' not in df.columns: df['本卷完成情况'] = 0
    #                 if '本卷字数' not in df.columns: df['本卷字数'] = 0
    #                 for idx in df.index:
    #                     str_idx = str(idx)
    #                     if str_idx in old_volume_data:
    #                         info = old_volume_data[str_idx]
    #                         df.at[idx, '本卷完成情况'] = info.get('本卷完成情况', 0)
    #                         df.at[idx, '本卷字数'] = info.get('本卷字数', 0)
    #                 all_sheets_to_write[k] = df
                
    #             elif isinstance(v, dict):
    #                 first_val = next(iter(v.values()), None)
    #                 all_sheets_to_write[k] = pd.DataFrame.from_dict(v, orient='index') if isinstance(first_val, dict) else pd.DataFrame([v])
    #             else:
    #                 all_sheets_to_write[k] = pd.DataFrame([{"内容": v}])

    #         # 🟢 按顺序写入
    #         final_keys = [ko for ko in target_order if ko in all_sheets_to_write]
    #         # 补上不在顺序列表里的其他 key
    #         for remaining in all_sheets_to_write.keys():
    #             if remaining not in final_keys: final_keys.append(remaining)
            
    #         for skey in final_keys:
    #             all_sheets_to_write[skey].to_excel(writer, sheet_name=skey[:31], index=(skey != "用户初始设定" and skey != "作品概述"))
        
    #     self.logger.info(f"Excel大纲已保存 (含初始设定): {excel_path}")
    #     return excel_path

    # 注意：记得在 process_task 中调用 save_outline_to_excel 时传入 task 字典
    # 找到 process_task 里的这一行：
    # self.save_outline_to_excel(outline, novel_dir, novel_title)
    # 修改为：
    # self.save_outline_to_excel(outline, novel_dir, novel_title, task_data=task)

    def save_outline_to_excel(self, outline: Dict, novel_dir: str, novel_title: str, task_data: Dict = None) -> str:
        """
        [修改版] 增强版 Excel 保存：
        1. 增加“用户初始设定” Sheet (放在第一页)
        2. 严格控制 Sheet 顺序
        """
        excel_path = os.path.join(novel_dir, "outline.xlsx")
        
        old_chapter_data = {}
        old_volume_data = {}

        # === 1. 备份旧数据 (逻辑不变) ===
        if os.path.exists(excel_path):
            try:
                old_ch_df = pd.read_excel(excel_path, sheet_name="章详细大纲", index_col=0, dtype=object)
                for idx, row in old_ch_df.iterrows():
                    if self.is_chapter_done(row.get('本章完成情况', 0)):
                        old_chapter_data[str(idx)] = {
                            '本章完成情况': 1,
                            '本章总结': row.get('本章总结', ''),
                            '本章字数': row.get('本章字数', 0)
                        }
                try:
                    old_vol_df = pd.read_excel(excel_path, sheet_name="卷详细大纲", index_col=0, dtype=object)
                    for idx, row in old_vol_df.iterrows():
                         old_volume_data[str(idx)] = {
                             '本卷完成情况': row.get('本卷完成情况', 0),
                             '本卷字数': row.get('本卷字数', 0)
                         }
                except: pass
            except Exception as e:
                self.logger.warning(f"读取旧Excel状态时遇到小问题: {e}")

        # === 2. 写入新数据 ===
        # with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        with pd.ExcelWriter(excel_path, engine='openpyxl', datetime_format='YYYY-MM-DD HH:MM:SS') as writer:
            
            # ✅ [关键改动] 定义 Sheet 顺序，把初始设定放第一
            target_order = ["用户初始设定", "作品概述", "核心设定与人物", "卷详细大纲", "章详细大纲"]
            
            # ✅ [关键改动] 先把用户初始设定写进去
            if task_data:
                pd.DataFrame([task_data]).to_excel(writer, sheet_name="用户初始设定", index=False)

            existing_keys = list(outline.keys())
            for sheet_name in target_order:
                if sheet_name == "用户初始设定": continue # 跳过已写的
                if sheet_name not in outline: continue
                
                data = outline[sheet_name]
                
                # Case A: 处理 "章详细大纲" (合并旧进度)
                if sheet_name == "章详细大纲" and isinstance(data, dict):
                    df = pd.DataFrame.from_dict(data, orient='index')
                    if '本章完成情况' not in df.columns: df['本章完成情况'] = 0
                    if '本章字数' not in df.columns: df['本章字数'] = 0
                    if '本章总结' not in df.columns: df['本章总结'] = ''
                    for idx in df.index:
                        str_idx = str(idx)
                        if str_idx in old_chapter_data:
                            info = old_chapter_data[str_idx]
                            df.at[idx, '本章完成情况'] = 1
                            df.at[idx, '本章字数'] = info.get('本章字数', 0)
                            if pd.notna(info.get('本章总结')): df.at[idx, '本章总结'] = info['本章总结']
                    
                    cols = ['本章所属卷次', '本章次', '本章标题', '本章完成情况', '本章字数', '本章总结'] 
                    other_cols = [c for c in df.columns if c not in cols]
                    df[cols + other_cols].to_excel(writer, sheet_name=sheet_name, index=True)

                # Case B: 处理 "卷详细大纲"
                elif sheet_name == "卷详细大纲" and isinstance(data, dict):
                    df = pd.DataFrame.from_dict(data, orient='index')
                    if '本卷完成情况' not in df.columns: df['本卷完成情况'] = 0
                    if '本卷字数' not in df.columns: df['本卷字数'] = 0
                    for idx in df.index:
                        str_idx = str(idx)
                        if str_idx in old_volume_data:
                            info = old_volume_data[str_idx]
                            df.at[idx, '本卷完成情况'] = info.get('本卷完成情况', 0)
                            df.at[idx, '本卷字数'] = info.get('本卷字数', 0)
                    df.to_excel(writer, sheet_name=sheet_name, index=True)

                # Case C: 其他 Sheet (作品概述, 核心设定等)
                elif isinstance(data, dict):
                    first_val = next(iter(data.values()), None)
                    df = pd.DataFrame.from_dict(data, orient='index') if isinstance(first_val, dict) else pd.DataFrame([data])
                    df.to_excel(writer, sheet_name=sheet_name[:31])
        
        self.logger.info(f"Excel大纲结构已更新: {excel_path}")
        return excel_path

    # ======================== 内容生成模块 ========================
    def build_chapter_context(self, outline: Dict, volume_num: int, chapter_num: int, prev_chapters: list) -> Tuple[str, str]:
        """
        构建生成当前章节所需的完整上下文Prompt
        """
        # 1. 获取当前章大纲
        chapter_key = f"{volume_num}-{chapter_num}"
        chapters_outline = outline.get("章详细大纲", {})
        curr_chap_data = chapters_outline.get(chapter_key, {})
        
        if not curr_chap_data:
            chapter_title = f"第{chapter_num}章"
            core_plot = "剧情自由发展"
            conflict = "未知"
        else:
            chapter_title = curr_chap_data.get("本章标题", f"第{chapter_num}章")
            core_plot = curr_chap_data.get("本章核心情节梗概", "")
            conflict = curr_chap_data.get("本章关键冲突/爽点", "")

        # 2. 构建【作品概述】(JSON)
        overview_data = outline.get("作品概述", {})
        overview_json = json.dumps(overview_data, ensure_ascii=False, indent=2)

        # 3. 构建【核心设定与人物】(JSON)
        characters_data = outline.get("核心设定与人物", {})
        characters_json = json.dumps(characters_data, ensure_ascii=False, indent=2)

        # 4. 构建【之前卷信息】(Text)
        # 获取所有卷数据
        all_volumes = outline.get("卷详细大纲", {})
        prev_volumes_text = ""
        
        # 计算起始卷：当前卷 - 回溯卷数，最小为第1卷
        start_vol = max(1, volume_num - self.context_prev_vol_num)
        # 遍历范围：[start_vol, volume_num - 1]
        if start_vol < volume_num:
            for v in range(start_vol, volume_num):
                v_str = str(v)
                if v_str in all_volumes:
                    v_data = all_volumes[v_str]
                    prev_volumes_text += f"第{v}卷：{v_data.get('本卷标题', '')}\n"
                    prev_volumes_text += f"  - 核心冲突：{v_data.get('本卷核心冲突', '')}\n"
                    prev_volumes_text += f"  - 关键情节：{v_data.get('本卷关键情节', '')}\n"
                    prev_volumes_text += f"  - 目标：{v_data.get('本卷目标', '')}\n\n"
        
        if not prev_volumes_text:
            prev_volumes_text = "（无前序卷信息）"

        # 5. 构建【当前卷信息】(Text)
        curr_vol_data = all_volumes.get(str(volume_num), {})
        curr_volume_text = f"第{volume_num}卷：{curr_vol_data.get('本卷标题', '')}\n"
        curr_volume_text += f"核心冲突：{curr_vol_data.get('本卷核心冲突', '')}\n"
        curr_volume_text += f"关键情节：{curr_vol_data.get('本卷关键情节', '')}\n"
        curr_volume_text += f"目标：{curr_vol_data.get('本卷目标', '')}"

        # 6. 构建【前情提要】(Text - 最近N章)
        prev_chapters_text = ""
        if prev_chapters:
            # 取最后 N 章
            recent_chapters = prev_chapters[-self.context_prev_chap_num:]
            for prev in recent_chapters:
                # 兼容旧数据 key 可能不同的情况
                p_vol = prev.get('volume', prev.get('roll', '?'))
                p_chap = prev.get('chapter', '?')
                p_sum = prev.get('本章总结', prev.get('summary', ''))
                prev_chapters_text += f"第{p_vol}卷{p_chap}章：{p_sum}\n"
        else:
            prev_chapters_text = "（这是本书的第一章，无前情提要）"

        # 7. 组装最终 Context
        context = f"""
【作品概述】
{overview_json}

【核心设定与人物】
{characters_json}

【之前卷信息】(回顾最近{self.context_prev_vol_num}卷)
{prev_volumes_text.strip()}

【当前卷信息】
{curr_volume_text}

【前情提要】(回顾最近{self.context_prev_chap_num}章)
{prev_chapters_text.strip()}

【本章大纲】
当前章节：第{volume_num}卷 第{chapter_num}章《{chapter_title}》
核心情节：{core_plot}
关键冲突：{conflict}
"""
        return context, chapter_title, curr_chap_data

    def post_process_content(self, content: str, volume: int, chapter: int, title: str) -> str:
        lines = content.split('\n')
        processed = [f"第{volume}卷 第{chapter}章：{title}\n"]
        for line in lines:
            line = line.strip().replace("#####", "")
            if line and line not in title and "SUMMARY" not in line:
                processed.append(f"{'\u3000' * self.indent_size}{line}\n")
        return "\n".join(processed)

    def generate_chapter(self, outline: Dict, volume: int, chapter: int, prev_chapters: list, chapter_word_num: int) -> Tuple[Optional[str], Optional[str]]:
        context, title, curr_chap_data = self.build_chapter_context(outline, volume, chapter, prev_chapters)

        # 在 generate_chapter 函数中
        chap_type = curr_chap_data.get("本章节奏类型", "铺垫")
        # if chap_type == "沉淀":
        #     pacing_instruction = "本章为沉淀章，节奏请放缓。重点描写主角的心理满足感、实力的实质性提升，以及外界（配角、路人）对主角先前壮举的震撼反应。多一些生活气息或温馨互动。"
        # elif chap_type == "高潮":
        #     pacing_instruction = "本章为高潮章，节奏极快。多用短句，强调动作的破坏力和视觉冲击力。减少冗长的心理描写，直接让主角‘打脸’，给读者最直接的感官刺激。"
        # else:
        #     pacing_instruction = "按照常规节奏进行，注重逻辑铺垫和伏笔埋设。"

        # 🟢 3. 定义动态节奏指令
        if chap_type == "蓄势":
            pacing_instruction = """
【蓄势章特别指令】：
- 节奏：沉稳中带有压抑，制造“风雨欲来”的紧迫感。
- 重点：描写矛盾的升级、反派的嚣张或主角面临的困难，为下一章爆发做极致的铺垫。
- 描写：注重心理活动和伏笔埋设。
"""
        elif chap_type == "高潮":
            pacing_instruction = """
【高潮章特别指令】：
- 节奏：极快，多用短句，强调动作的瞬间爆发力。
- 重点：描写敌人的震惊、主角底牌尽出的华丽感、以及彻底破局的爽快感。
- 描写：减少环境描写，增加碰撞感、破碎感和情绪的顶点。
"""
        elif chap_type == "沉淀":
            pacing_instruction = """
【沉淀章特别指令】：
- 节奏：舒缓，注重细节描写和人物内心的满足感。
- 重点：描写战利品的消化、实力的实质性巩固、以及外界（配角、路人）对主角壮举的震撼脑补（迪化反馈）。
- 描写：增加烟火气或温馨互动，让读者紧绷的神经放松。
"""
        else: # 铺垫
            pacing_instruction = "【铺垫章特别指令】：节奏正常。重点在于世界观展示、新人物引入或剧情线的铺设，保持读者的好奇心。"

        # 判断是否是全书第一章，如果是，加强开篇要求
        is_first_chapter = (volume == 1 and chapter == 1)
        # 🟢 [优化] 黄金三章特化逻辑
        # start_requirement = "请注意：这是全书第一章！第一段话必须是“黄金三秒”，直接抛出巨大的悬念、冲突或极其荒谬的场景，死死抓住读者眼球！" if is_first_chapter else "开头不要废话，紧接上一章结尾或直接切入本章核心事件。"
        start_requirement = "开头不要废话，紧接上一章结尾或直接切入本章核心事件。"
        if volume == 1:
            if chapter == 1:
                start_requirement = """
                【黄金开篇·第一章】：
                1. **切入点**：直接切入剧烈的冲突现场（如退婚现场、被杀现场、审判现场），禁止写天气和背景介绍。
                2. **困境**：主角必须处于一个看似必死的困境或巨大的羞辱中，拉满读者的同情和愤慨。
                3. **结尾**：章节最后一句，主角的金手指（系统/宝物/记忆）必须到账，或者主角眼神发生变化（重生），留下巨大期待。
                """
            elif chapter == 2:
                start_requirement = """
                【黄金开篇·第二章】：
                1. **金手指试探**：主角初步了解或尝试金手指的威力，产生“这局能赢”的底气（信息差）。
                2. **反派骑脸**：反派变本加厉地逼迫，将主角逼到悬崖边，情绪压抑到极致。
                """
            elif chapter == 3:
                start_requirement = """
                【黄金开篇·第三章】：
                1. **第一次爆发**：利用金手指或前世经验，完成第一次“不可能的反杀”或“打脸”。
                2. **震惊全场**：重点描写周围人（原本看不起主角的人）眼球掉一地的反应。
                3. **收获**：解决眼前的危机，获得第一个战利品，并引出更大的地图。
                """

        prompt = f"""{context}

【写作指令】
你现在就是网文界的“大神作家”，请根据大纲撰写正文（字数要求：{chapter_word_num}字左右）。
一切剧情演绎必须严丝合缝地锚定在给定的【本章大纲】之内。严禁为了制造冲突而凭空捏造与后续大纲冲突的人物或设定。

【通用质量标准】
{self.style_guide}

【节奏调控指令】
{pacing_instruction}

【其他文风要求】
{outline["作品概述"].get("文风", "精彩网文")}

【本章特别要求】
1. **{start_requirement}**
2. **场景描写**：只写必要场景，多用动词，少用形容词。
3. **对话互动**：对话要像“网聊”一样有梗，人物之间要有拉扯感。主角内心戏可以适当发癫（中二/吐槽）。
4. **逻辑自洽**：虽然情节可以荒诞有趣，但人物的行为逻辑必须符合其人设（尤其是高智商反派，不要强行降智）。

【大神级镜头控制】
- 70% 的篇幅用于描写对话和即时动作，30% 用于心理活动。
- 严禁‘上帝视角’的说明文，必须通过主角的视角看世界（第一人称或受限第三人称）。
- 加入‘情绪标识符’：主角此刻的心情是愤怒、戏谑还是冷静？请通过细节（如：指尖颤抖、嘴角上扬）表达出来。

【格式要求】
正文结束后，换行输出 "{self.chapter_summary_separator}"。
然后写一段本章的**功能性摘要**（300字以内），摘要必须包含：
- 本章发生的关键剧情转折、核心进展。
- 主角获得的物品/能力/信息（如有）。
- 人物关系的重要变化（如有）。
- 留下的悬念/伏笔（供下一章参考）。
"""

        self.logger.info(f"正在生成: {volume}-{chapter} {title}")
        # 🟢 [修改] temperature=0.85 (保持稳定输出，防止正文逻辑崩坏)
        res = self.llm.call(prompt, "你是一位网文大神。", 0.85)
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
                if self.is_chapter_done(row.get('本章完成情况')):
                    r, c = int(float(row['本章所属卷次'])), int(float(row['本章次']))
                    prog["done_set"].add(f"{r}-{c}")
                    if pd.notna(row.get('本章总结')):
                        prog["prev_chapters"].append({
                            "volume": r, 
                            "chapter": c, 
                            "本章总结": str(row['本章总结'])
                        })
        except Exception as e:
            self.logger.warning(f"加载进度失败: {e}")
        return prog

    def save_progress(self, excel_path: str, r: int, c: int, chapter_summary: str, word_count: int):
        """
        [修改] 增加 word_count 参数，写入 本章字数
        """
        try:
            with pd.ExcelFile(excel_path) as xls:
                sheets = {s: pd.read_excel(xls, s, index_col=0) for s in xls.sheet_names}
            
            if "章详细大纲" in sheets:
                df = sheets["章详细大纲"]
                df['本章总结'] = df['本章总结'].astype(object)
                
                # 确保列存在
                if '本章字数' not in df.columns: df['本章字数'] = 0

                mask = (df['本章所属卷次'].astype(str) == str(r)) & (df['本章次'].astype(str) == str(c))
                if mask.any():
                    df.loc[mask, '本章完成情况'] = 1
                    df.loc[mask, '本章总结'] = chapter_summary
                    df.loc[mask, '本章字数'] = word_count # 写入字数

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
            done_count = chapter_rows['本章完成情况'].apply(lambda x: 1 if self.is_chapter_done(x) else 0).sum()
            current_volume_words = chapter_rows['本章字数'].fillna(0).sum()
            is_volume_done = 1 if done_count >= total_chapters else 0
            
            self.logger.info(f"📊 第 {volume_num} 卷统计: 进度 {done_count}/{total_chapters}, 总字数 {current_volume_words}")

            # 2. 更新卷大纲
            if '本卷完成情况' not in df_volumes.columns: df_volumes['本卷完成情况'] = 0
            if '本卷字数' not in df_volumes.columns: df_volumes['本卷字数'] = 0
            
            vol_key = str(volume_num)
            # 兼容索引类型
            if vol_key in df_volumes.index.astype(str):
                try:
                     df_volumes.loc[int(vol_key), '本卷完成情况'] = is_volume_done
                     df_volumes.loc[int(vol_key), '本卷字数'] = current_volume_words
                except KeyError:
                     df_volumes.loc[vol_key, '本卷完成情况'] = is_volume_done
                     df_volumes.loc[vol_key, '本卷字数'] = current_volume_words

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
            df = pd.read_csv(csv_path, dtype={'novel_gen_start_time': str, 'novel_gen_end_time': str})
            mask = df['task_id'] == task_id
            
            if status is not None and 'status' in df.columns:
                df.loc[mask, 'status'] = status
            
            if outline_done is not None and 'outline_done' in df.columns:
                df.loc[mask, 'outline_done'] = outline_done
                
            if gen_start and 'novel_gen_start_time' in df.columns:
                df.loc[mask, 'novel_gen_start_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
            if gen_end and 'novel_gen_end_time' in df.columns:
                df.loc[mask, 'novel_gen_end_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
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
        novel_dir = os.path.join(self.novels_dir, os.path.splitext(os.path.basename(self.tasks_csv_path))[0], f"task_{task_id}")
        os.makedirs(novel_dir, exist_ok=True)
        self.logger.info(f"工作目录: {novel_dir}")

        # 🟢 [新增] 记录开始生成时间并存入 task 字典
        task['novel_gen_start_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # 🟢 设置 Logger 并接管 stdout/stderr
        custom_logger = Logger(os.path.join(novel_dir, f"task_{task_id}.log"), task)
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
        
        # 屏蔽 httpx 和 openai 的 INFO 级别日志，只看报错
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("openai").setLevel(logging.WARNING)

        # 更新 self.logger (确保它使用新的配置)
        self.logger = logging.getLogger(__name__)
        
        try:
            self.logger.info(f"开始处理任务 task_id={task_id}") # 这句话现在会出现在日志文件里了！
            
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
                self.save_outline_to_excel(outline, novel_dir, novel_title, task_data=task)
            
            self.update_task_csv(self.tasks_csv_path, task_id, outline_done=1)

            # 生成封面
            if self.img_generator:
                self.logger.info(f"🔄 正在生成小说封面...")
                cover_save_dir = os.path.join(novel_dir, "cover")
                if not os.path.exists(cover_save_dir):
                    os.makedirs(cover_save_dir)
                if len(os.listdir(cover_save_dir)) != self.cover_size:
                    cover_prompt = f"""
                    {outline.get("作品概述", {})}
                    这是我在番茄小说上发布的小说的基本信息，帮我生成一个封面海报，画风是动漫的，你可以参考排行榜较前的风格，我的目的是大家看到封面之后，有吸引力，能点进来阅读，封面标题必须与小说标题一致（不要有错字），且封面尺寸为{self.cover_size}竖版
                    """
                    for c in range(self.cover_nums):
                        image_url = self.img_generator.generate_image(
                            prompt=cover_prompt,
                            size=self.cover_size,
                        )
                        image_path = os.path.join(cover_save_dir, f"{c}.png")
                        # Download the image from the URL and save it
                        try:
                            response = requests.get(image_url, stream=True)
                            response.raise_for_status()  # Check if the request was successful

                            with open(image_path, "wb") as f:
                                for chunk in response.iter_content(chunk_size=8192):
                                    f.write(chunk)  # Write the image data to the file
                            print(f"Image {c} saved at {image_path}")
                        except requests.exceptions.RequestException as e:
                            print(f"Error downloading image {c}: {e}")

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
                                prev_chapters.append({"volume":r, "chapter":c, "本章总结":s})
                            except IOError as e:
                                self.logger.warning(f"读取已有章节失败: {e}")
                        
                        self.logger.info(f"跳过已完成: {key}")
                        # 即使跳过，也要标记可能需要更新卷状态(防止上次crash没更新卷状态)
                        is_volume_dirty = True
                        continue
                    
                    content, chapter_summary = self.generate_chapter(outline, r, c, prev_chapters, int(task["chapter_word_num"]))
                    
                    # [修改] 计算字数
                    content_len = len(content) if content else 0

                    if content:
                        with open(txt_path, 'w', encoding='utf-8') as f: f.write(content)
                        
                        # [修改] 传入字数
                        self.save_progress(excel_path, r, c, chapter_summary, content_len)
                        
                        done_set.add(key)
                        prev_chapters.append({"volume":r, "chapter":c, "本章总结":chapter_summary})
                        self.logger.info(f"✅ 已生成: {key} (字数: {content_len})")
                        is_volume_dirty = True
                        time.sleep(2)
                    else:
                        self.logger.error(f"❌ 生成失败: {key}")
                
                # [新增] 卷循环结束，更新卷统计
                if is_volume_dirty:
                    self.logger.info(f"🔄 正在更新第 {r} 卷的统计信息...")
                    self.update_volume_progress(excel_path, r)
            
            # -------------------------------------------------------
            # 🟢 [关键修改] 任务正文全部生成完毕后，更新结束时间并重写 Excel
            # -------------------------------------------------------
            task['novel_gen_end_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.logger.info(f"正在更新 Excel 中的生成时间统计...")
            self.save_outline_to_excel(outline, novel_dir, novel_title, task_data=task)
            # -------------------------------------------------------

            self.logger.info(f"任务结束: {task_id}")
            self.zip_novel_folder(novel_dir)
            return True
            
        except Exception as e:
            # 🟢 [建议添加] 哪怕失败了，也记录一下结束时间，方便排查耗时
            task['novel_gen_end_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S (异常中断)')
            self.save_outline_to_excel(outline, novel_dir, novel_title, task_data=task)

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

def run_single_task_worker(task_data: Dict, task_id: int, csv_path: str, deepseek_key: str, dmx_key: str, gen_cover: bool):
    """
    独立的工作进程函数：负责初始化环境并执行单个任务
    """
    # 1. 重新初始化客户端 (因为 API Client 可能无法跨进程 pickle)
    llm = DeepSeekClient(api_key=deepseek_key, base_url="https://api.deepseek.com", model_name="deepseek-chat")
    dmx = DMXImageAPIGenerator(api_key=dmx_key) if gen_cover and dmx_key else None
    
    # 2. 初始化生成器
    generator = NovelGenerator(llm, dmx, csv_path)
    
    # 3. 更新状态并执行
    # 注意：这里可能有多进程同时写CSV的风险，但 pandas 读写通常够快，暂时忽略锁
    generator.update_task_csv(csv_path, task_id, status=1, gen_start=True)
    
    try:
        success = generator.process_task(task_data, task_id)
        final_status = 2 if success else 3
        generator.update_task_csv(csv_path, task_id, status=final_status, gen_end=True)
        return f"Task {task_id}: Success"
    except Exception as e:
        generator.update_task_csv(csv_path, task_id, status=3)
        return f"Task {task_id}: Failed ({e})"

# ======================== 主入口 (保持不变) ========================
def main():
    # 加载 .env 文件
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--tasks_csv_path', default="./novel_gen_tasks/test.csv")
    parser.add_argument('-i', '--task_ids', type=str)
    parser.add_argument('--gen-cover', action='store_true', help='Whether to use the cover generation function')
    args = parser.parse_args()
    
    deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_base_url = "https://api.deepseek.com"
    deepseek_model_name = "deepseek-chat"
    dmx_api_key = os.getenv("DMX_API_KEY", "")

    if not deepseek_api_key: 
        print("Error: No DEEPSEEK API Key provided.")
        return
    # 🟢 1. 先实例化 DeepSeekClient
    llm_client = DeepSeekClient(
        api_key=deepseek_api_key, 
        base_url=deepseek_base_url, 
        model_name=deepseek_model_name
    )

    if args.gen_cover:
        if not dmx_api_key: 
            print("Error: No DMX API Key provided.")
            return
        dmx_generator = DMXImageAPIGenerator(api_key=dmx_api_key)
    else:
        dmx_generator = None

    if not os.path.exists(args.tasks_csv_path):
        print(f"File not found: {args.tasks_csv_path}")
        return

    # 🟢 2. 将 client 传入 NovelGenerator
    generator = NovelGenerator(
        llm_client=llm_client, 
        img_generator=dmx_generator,
        tasks_csv_path=args.tasks_csv_path
    )

    df = pd.read_csv(args.tasks_csv_path)

    # target_task_ids = []
    # if args.task_ids:
    #     for p in args.task_ids.split(','):
    #         if '-' in p: s,e = map(int, p.split('-')); target_task_ids.extend(range(s,e+1))
    #         else: target_task_ids.append(int(p))
            
    # for idx, row in df.iterrows():
    #     tid = row.get('task_id', idx+1)
    #     if target_task_ids and tid not in target_task_ids: continue
    #     if row.get('status') == 2: 
    #         print(f"Skipping completed task_id={tid}")
    #         continue
        
    #     generator.update_task_csv(args.tasks_csv_path, tid, status=1, gen_start=True)
    #     success = generator.process_task(row.to_dict(), tid)
    #     generator.update_task_csv(args.tasks_csv_path, tid, status=2 if success else 3, gen_end=True)

    # 筛选需要执行的任务
    target_task_ids = []
    if args.task_ids:
        for p in args.task_ids.split(','):
            if '-' in p: s,e = map(int, p.split('-')); target_task_ids.extend(range(s,e+1))
            else: target_task_ids.append(int(p))
            
    tasks_to_run = []
    for idx, row in df.iterrows():
        tid = row.get('task_id', idx+1)
        if target_task_ids and tid not in target_task_ids: continue
        if row.get('status') == 2: 
            print(f"Skipping completed task_id={tid}")
            continue
        tasks_to_run.append((tid, row.to_dict()))

    if not tasks_to_run:
        print("没有需要执行的任务。")
        return

    # 🟢 [修改] 提取 ID 并拼接成字符串
    # tasks_to_run 的结构是List[(tid, row_dict)]，所以我们取 t[0]
    ids_str = ", ".join([str(t[0]) for t in tasks_to_run])
    
    print(f"🚀 准备并发执行 {len(tasks_to_run)} 个任务: [{ids_str}]")
    print(f"⚠️ 注意：并发数过多可能导致 API Rate Limit 报错，建议 deepseek 并发不超过 5-10")

    # 🟢 [核心修改] 使用 ProcessPoolExecutor 进行多进程并发
    # max_workers = 2 : 同时跑 2 本书 (根据你的 API 额度调整)
    max_workers = 2
    
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for tid, task_data in tasks_to_run:
            # 提交任务到进程池
            f = executor.submit(
                run_single_task_worker,
                task_data, 
                tid, 
                args.tasks_csv_path, 
                deepseek_api_key, 
                dmx_api_key, 
                args.gen_cover
            )
            futures.append(f)
        
        # 等待所有任务完成
        for f in futures:
            try:
                print(f.result())
            except Exception as e:
                print(f"Worker Exception: {e}")

if __name__ == "__main__":
    main()