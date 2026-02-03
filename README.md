# AINovel

**AINovel** is an automatic batch novels generation system based on the DeepSeek API, supporting batch tasks and resume from breakpoints.

## Install
```bash
# 1. Clone repository
git clone https://github.com/RobertLau666/AINovel.git
cd AINovel

# 2. Install venv
conda create -n ainovel python=3.12
conda activate ainovel
pip install -r requirements.txt
```

## Set API Key
Create ```.env``` in project root dir.
```
DEEPSEEK_API_KEY=sk-xxxxxxxxxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

DMX_API_KEY=sk-xxxxxxxxxx
```

[DEEPSEEK](https://platform.deepseek.com/usage): Used to generate novel content

[DMX](https://www.dmxapi.com/console): Used to generate novel cover

## Set novel tasks
Edit `novel_gen_tasks.csv`:

| Field                | Description                      | Example                              |
|----------------------|----------------------------------|--------------------------------------|
| task_id              | Task ID (starting from 1)        | 1, 2, 3                              |
| novel_type           | Novel Genre                      | 玄幻、都市、言情                        |
| novel_idea           | Core Concept                     | 主角逆袭成大佬                         |
| write_style          | Writing Style                    | 轻松幽默、热血燃爆                      |
| target_reader        | Target Readers                   | 男性、女性                             |
| special_requirements | Special Requirements             | 每章结尾留悬念                         |
| volume_num           | Number of Volumes                | 2                                    |
| chapter_num          | Chapters per Volume              | 5                                    |
| word_num             | Words per Chapter                | 2000                                 |
| status               | Status                           | 0=Pending, 1=Generating, 2=Completed |
| outline_done         | Outline Completion               | 0=Incomplete, 1=Completed            |
| gen_start_time       | Generation Start Time            | Auto-filled                          |
| gen_end_time         | Generation End Time              | Auto-filled                          |

Ask [Google AI Studio](https://aistudio.google.com/) for novel generate tasks:
```
你是一个熟悉现在各大小说app上畅销书和写作风格的分析专家，你知道什么样的小说很火，你可以深度调研，写一个兴趣调查分析报告，你知道大家都喜欢读什么样子的小说，比如：废柴打怪升级、变强、科幻休闲、穿越、迎娶白富美，或者这些不同类型可以杂糅，会不会变得更有趣呢，我不太了解，你自己看着办吧。
帮我出出主意，我的目标是成为排行榜前几的写作大佬。然后仿照下面这种格式 返回给我一个csv表格,包含30条任务（按照预计火爆程度进行从其拿到后排序），其中novel_idea可以尽情发挥，字数多一些
task_id,novel_type,novel_idea,write_style,target_reader,special_requirements,roll_num,chapter_num,word_num,status,outline_done,gen_start_time,gen_end_time
1,玄幻,主角从萌新升级成为上界大佬，要有逆袭情节剧情精彩详实，有反转,热血燃爆,男性,每章要有起承转合，结尾留有悬念,10,80,2000,0,0,,
```

## Run
### Command
```bash
python app.py                            # Process all tasks
python app.py -i 1                       # Only process task_id=1
python app.py -i 1,3,6                   # Process task_id=1,3,6
python app.py -i 3-6                     # Process task_id=3,4,5,6
python app.py -i 1,3-5,8                 # Mixed format: task_id=1,3,4,5,8
python app.py --deepseek-api-key sk-xxx  # Specify DeepSeek API Key
python app.py -f tasks.csv               # Specify task file
python app.py -i 1 --gen-cover           # Only process task_id=1, use cover generation
```

### Gradio
```bash
python app_gradio.py --port 8080 --share
```
![app_gradio.jpeg](./assets/app_gradio.jpeg)

## Output Structure
```
novels/
└── task_[id]/
|   ├── outline.xlsx       # Outline (Multiple Sheets, Including Chapter Progress)
|   ├── outline.json       # Original outline JSON
|   ├── task_[id].log      # Log
|   └── cover/             # Novel cover
|   └── content/
|       ├── 1-1.txt        # Roll1-Chapter1
|       ├── 1-2.txt        # Roll1-Chapter2
|       └── ...
└── task_[id].zip          # Package .zip file
```

## Novel Cover Generation
1. [豆包](https://www.doubao.com/chat/) '图像生成' - 'Seedream 4.5', generation cover.
```
***
这是我在番茄小说上发布的小说的基本信息，帮我生成一个海报，画风是动漫的，你可以参考排行榜较前的风格，我的目的是大家看到封面之后，有吸引力，能点进来阅读，封面标题必须与小说标题一致，且封面尺寸为800*1066竖版
```
2. [ChatGPT](https://chatgpt.com/), upload the generated cover, remove the watermark.
```
帮我修改一下这个图片，把左边那个语言气泡去掉，另外，把右下角的“亡灵法林默”改为“亡灵法师林默”，然后把右下角的“豆包AI生成”水印去掉
```

## Release
[番茄小说网](https://fanqienovel.com/)