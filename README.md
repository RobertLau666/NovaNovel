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

Or you can ask [Google AI Studio](https://aistudio.google.com/) for novel generate tasks, prompt is as follows:
```
# Role: 顶级网文大数据分析师 & 金牌主编
# Profile:
你精通“番茄小说”、“起点中文网”等主流平台的算法推荐机制，能够敏锐捕捉2024-2025年的网文热点趋势。你擅长通过拆解爆款小说的“黄金三章”、“金手指设定”和“期待感钩子”，构建出高留存、高点击的小说大纲。

# Context:
我拥有一套自动化小说生成系统，需要你提供高质量的“元数据”作为输入。你的输出质量直接决定了生成小说的逻辑性和精彩程度。

# Goals:
请你深度调研当前全网排行榜前列的爆款网文，构思30个极具爆火潜力的长篇小说选题。

# Constraints & Workflow:
1. **爆款公式**：每个创意必须包含[极致反差] + [独特金手指] + [情绪价值]。
2. **安全红线（重要）**：所有背景必须架空为“蓝星”或“异界”。涉及国家/政府机构时，必须使用虚构名称（如“龙国”、“特异局”），严禁映射现实政治，严禁涉黄涉政。
3. **拒绝陈旧**：拒绝老套路，要结合“规则怪谈”、“全民转职”、“赛博修仙”、“迪化流”等新颖热点。
4. **格式严格**：严格按照CSV格式输出，无Markdown边框，无废话。
5. **排序**：按火爆潜力从高到低排序。

# Column Definition (详细要求):
- **novel_idea**: (250-300字) 包含：
    - **背景**：主角身份（架空背景）。
    - **金手指**：具体功能 + **限制条件/代价**（防止战力崩坏）。
    - **主线**：核心目标。
    - **黄金钩子**：开篇前三章的具体高潮画面，必须体现出强烈的**情绪价值**（爽、燃、泪、笑）。
- **write_style**: 5个以上关键词（如：迪化, 老六, 赛博朋克, 克苏鲁, 规则怪谈等）。
- **target_reader**: 男性/女性/通用。
- **note**: 给生成器的特别指令（置为""，留给用户填写）。
- **其他数值**: volume_num(10), chapter_num(80), chapter_word_num(2100), status(0), outline_done(0), novel_gen_start_time(), novel_gen_end_time()。

# Output Format:
task_id,novel_type,novel_idea,write_style,target_reader,note,volume_num,chapter_num,chapter_word_num,status,outline_done,novel_gen_start_time,novel_gen_end_time

# Example Row:
1,规则怪谈,背景是诡异降临蓝星，龙国面临灭国危机。主角是精神病院的重症患者，金手指是“只有我能看到规则的红字备注”，但代价是每使用一次理智值会下降。核心主线是将自己上交“龙国异常事务局”，背靠国家机器攻略副本。钩子：S级副本中，别国天选者惨死，主角却看着红字提示“诡异怕广场舞”，于是带着诡异跳起了《最炫民族风》，全球观众从绝望到笑喷，情绪价值拉满。,规则怪谈,直播,爱国,搞笑,脑洞,通用,,10,80,2100,0,0,,

现在，请生成30条数据：
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
python app.py -f test.csv               # Specify task file
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