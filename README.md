# AINovel

**AINovel** is an automatic batch novels generation system based on the DeepSeek API, supporting batch tasks and resume from breakpoints.

## Set API Key
Create ```.env``` in project root dir.
```
# Use [DEEPSEEK](https://platform.deepseek.com/usage) to generate novel content, required
DEEPSEEK_API_KEY=

# Use [DMX](https://www.dmxapi.com/console) to generate novel cover, optional
DMX_API_KEY=
```

## Set novel tasks
Edit `*.csv` and put it under dir ```novel_gen_tasks/```.

| Field                | Description                      | Example                              |
|----------------------|----------------------------------|--------------------------------------|
| task_id              | Task ID (starting from 1)        | 1, 2, 3                              |
| novel_type           | Novel Genre                      | 玄幻、都市、言情                        |
| novel_idea           | Core Concept                     | 主角逆袭成大佬                         |
| write_style          | Writing Style                    | 轻松幽默、热血燃爆、搞笑、中二、腹黑       |
| target_reader        | Target Readers                   | 男性、女性                             |
| note                 | Note                             | 每章结尾留悬念                         |
| volume_num           | Number of Volumes                | 10                                    |
| chapter_num          | Chapters per Volume              | 80                                    |
| chapter_word_num     | Words per Chapter                | 2100                                 |
| status               | Status                           | 0=Pending, 1=Generating, 2=Completed |
| outline_done         | Outline Completion               | 0=Incomplete, 1=Completed            |
| novel_gen_start_time | Novel Generation Start Time      | Auto-filled                          |
| novel_gen_end_time   | Novel Generation End Time        | Auto-filled                          |

Or you can ask [Google AI Studio](https://aistudio.google.com/) for novel generate tasks:
```
# Role: 顶级网文大数据分析师 & 金牌主编
# Profile:
你精通“番茄小说”、“起点中文网”等主流平台的算法推荐机制，能够敏锐捕捉2024-2025年的网文热点趋势。你擅长通过拆解爆款小说的“黄金三章”、“金手指设定”和“期待感钩子”，构建出高留存、高点击的小说大纲。

# Context:
我拥有一套自动化小说生成系统，需要你提供高质量的“元数据”作为输入。你的输出质量直接决定了生成小说的逻辑性和精彩程度。

# Goals:
请你深度调研当前全网排行榜前列的爆款网文（包括但不限于：规则怪谈、全民转职、反派偷听心声、苟道修仙、赛博玄幻、神豪系统、末世囤货等），分析其核心爽点。
请结合不同流派的特点（如：克苏鲁+修仙，系统+直播，校花+高武），构思30个极具爆火潜力的长篇小说选题。

# Constraints & Workflow:
1. **爆款公式**：每个创意必须包含[核心冲突] + [独特金手指] + [极极致爽点]。
2. **拒绝陈旧**：不要写“掉悬崖捡秘籍”这种老套路，要写“系统延迟到账”、“开局上交国家”、“全民穿越”等新颖设定。
3. **格式严格**：必须严格按照指定的CSV格式输出，不要包含任何Markdown表格边框，不要有开场白和结束语，直接返回CSV文本块。
4. **排序**：按照“预计火爆程度”从高到低排序（Task 1 为最火）。

# Column Definition (详细要求):
- **novel_idea**: (重点) 必须在150-200字之间。要包含：主角背景（如废柴/穿越者/重生者）、金手指具体功能（如：只有我能看到隐藏提示）、核心主线（如：抵抗万族入侵）、以及一个具体的“钩子”剧情（开篇前三章的高潮点）。
- **write_style**: 关键词堆砌，不少于5个。例如：迪化, 老六, 杀伐果断, 腹黑, 多女主, 稳健流, 极道, 诡异, 赛博朋克, 轻松搞笑, 脑洞大开。
- **target_reader**: 男性/女性/通用。
- **note**: 给生成器的特别指令，如：每章结尾必须断章在悬念处，前三章节奏要快。
- **其他数值**: volume_num(固定10), chapter_num(固定80), chapter_word_num(固定2100), status(0), outline_done(0), novel_gen_start_time(留空), novel_gen_end_time(留空)。

# Output Format:
请输出且仅输出一个CSV格式的代码块，表头如下：
task_id,novel_type,novel_idea,write_style,target_reader,note,volume_num,chapter_num,chapter_word_num,status,outline_done,novel_gen_start_time,novel_gen_end_time

# Example Row (参考风格，不要完全照抄):
1,都市异能,全球异变，所有人类随机获得一个debuff，主角重生成为唯一没有副作用的“净化者”。开局被校花嫌弃，反手觉醒S级天赋“吞噬万物”，只要吃掉诡异生物就能无限叠加属性。全世界强者跪求主角出手，主角却在直播做菜。,杀伐果断,系统,灵气复苏,直播,无敌流,爽文,装逼打脸,男性,重点描写主角扮猪吃虎的心理活动，反派智商在线但被主角降维打击,10,80,2100,0,0,,

现在，请开始你的工作，生成30条数据：
```

## Quick Start
- Linux/macOS users:
1. First, you need to grant execution permission to the script: Open the terminal and run ```chmod +x start.sh```.
2. Starting method: Run ```./start.sh``` in the terminal.

- Windows users:
1. Just double-click ```start.bat```. Or if you have installed Git Bash, you can right-click and select ```Git Bash Here``` then run ```./start.sh```.

## Manual Start
### Install
```bash
# 1. Clone repository
git clone https://github.com/RobertLau666/AINovel.git
cd AINovel

# 2. Install venv
conda create -n ainovel python=3.12
conda activate ainovel
pip install -r requirements.txt
```

### Run
#### Command
```bash
python app.py                            # Process all tasks
python app.py -i 1                       # Only process task_id=1
python app.py -i 1,3,6                   # Process task_id=1,3,6
python app.py -i 3-6                     # Process task_id=3,4,5,6
python app.py -i 1,3-5,8                 # Mixed format: task_id=1,3,4,5,8
python app.py -f tasks.csv               # Specify task file
python app.py -i 1 --gen-cover           # Only process task_id=1, use cover generation
```

#### Gradio
```bash
python app_gradio.py --port 8080 --share
```
Then open local URL: ```http://0.0.0.0:8080``` or public URL, such as ```https://d0bf92b05a8a956e5f.gradio.live```.

![app_gradio.jpeg](./assets/app_gradio.jpeg)

## Output Structure
```
novels/
├── task_[id]/
│   ├── task_[id].log      # Log
│   ├── outline.xlsx       # Outline (Multiple Sheets, Including Chapter Progress)
│   ├── outline.json       # Original outline JSON
│   ├── cover/             # Novel cover (if you use cover generation)
│   └── content/           # Novel content
│       ├── 1-1.txt        # Roll1-Chapter1
│       ├── 1-2.txt        # Roll1-Chapter2
│       └── ...
└── task_[id].zip          # Package .zip file
```

## Postprocess
### Content expansion
Use [ChatGPT](https://chatgpt.com/) to expand content, prompt is as follows:
```
***
这章内容的字数约3770左右，请扩写到4000字，并且说明在哪里插入什么内容”
```

### Novel Cover Generation
1. Use [豆包](https://www.doubao.com/chat/) to generate cover, '图像生成' - 'Seedream 4.5', prompt is as follows:
```
***
这是我在番茄小说上发布的小说的基本信息，帮我生成一个海报，画风是动漫的，你可以参考排行榜较前的风格，我的目的是大家看到封面之后，有吸引力，能点进来阅读，封面标题必须与小说标题一致，且封面尺寸为800*1066竖版。
```
2. Use [ChatGPT](https://chatgpt.com/) to remove the watermark, upload the generated cover, prompt is as follows:
```
帮我修改一下这个图片，把左边那个语言气泡去掉，另外，把右下角的“亡灵法林默”改为“亡灵法师林默”，然后把右下角的“豆包AI生成”水印去掉。
```

## Release
Release the generated novel on [番茄小说网](https://fanqienovel.com/).

## Reference
1. Code version update information: [versions.md](versions/versions.md)