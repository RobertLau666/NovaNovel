# NovaNovel

**NovaNovel** is an automatic batch novels generation system based on the DeepSeek API, supporting batch tasks and resume from breakpoints.

## Set API Key
Create a ```.env``` file in project root dir.
```
# Use [DEEPSEEK](https://platform.deepseek.com/usage) to generate novel content, required
DEEPSEEK_API_KEY=[Required]

# Use [DMX](https://www.dmxapi.com/console) to generate novel cover, optional
DMX_API_KEY=[Optional]
```

## Set novel tasks
1. Creat a `*.csv` file including novel generate tasks.

| Field                | Description                      | Example                              |
|----------------------|----------------------------------|--------------------------------------|
| task_id              | Task ID (starting from 1)        | 1, 2, 3                              |
| novel_type           | Novel Genre                      | 玄幻、都市、言情                        |
| novel_idea           | Core Concept                     | 主角逆袭成大佬                         |
| write_style          | Writing Style                    | 轻松幽默、热血燃爆、搞笑、中二、腹黑       |
| target_reader        | Target Readers                   | 男性、女性、通用                        |
| reference_novel      | Reference Novel                  | 主宰规则怪谈（怪谈直播间！）             |
| note                 | Note                             | 每章结尾留悬念                         |
| volume_num           | Number of Volumes                | 10                                   |
| chapter_num          | Chapters per Volume              | 80                                   |
| chapter_word_num     | Words per Chapter                | 2100                                 |
| status               | Status                           | 0=Pending, 1=Generating, 2=Completed |
| outline_done         | Outline Completion               | 0=Incomplete, 1=Completed            |
| novel_gen_start_time | Novel Generation Start Time      | Auto-filled                          |
| novel_gen_end_time   | Novel Generation End Time        | Auto-filled                          |

Regarding the content inside, you can manually fill it in or ask [Google AI Studio](https://aistudio.google.com/), prompt is as follows:
```
# Role: 顶级网文架构师 & 番茄千万级爆款策划人
# Profile:
你精通下沉市场与爆款网文（例如番茄/起点）的流量算法，深谙长篇小说的“留存逻辑”与“情绪价值”。你知道一个绝佳的选题不仅要有“黄金三秒”的惊艳开头，更要具备能支撑200万字的“深层爽点循环”和“核心矛盾”。

# Goals:
构思 10 个极具爆火潜力的长篇小说选题（涵盖系统流、规则怪谈、脑洞都市、赛博修仙、反派迪化等热门赛道）。选题必须具备“强反差”、“微短剧式的极速打脸”或“发疯/反套路”特质。

# Constraints & Workflow:
1. **去同质化与缝合微创新**：拒绝烂大街的无脑套路。采用“旧瓶装新酒”或“元素碰撞”（例如：修仙+规则怪谈，神豪+克苏鲁）。
2. **拒绝具体烂梗**：严禁出现现实中的具体人名、歌名、梗名，必须使用“泛指描述”（如“某洗脑神曲”、“某顶流偶像”），确保纯架空。
3. **安全红线**：彻底架空（蓝星/异界），官方机构使用化名（如“镇守司”、“异常局”），严禁涉黄涉政涉黑。
4. **格式与解析安全**：严格输出CSV格式。为了防止CSV格式错乱，所有包含标点符号的文本字段（尤其是 novel_idea 和 note）必须用双引号 `""` 完全包裹！

# Column Definition (高密度设定模型):
- **novel_type**: 小说类型（如：都市脑洞 / 赛博修仙 / 规则怪谈 / 极道反派 / 迪化幕后）。
- **novel_idea**: (400-500字) 它是整本书的“基因库”，必须包含以下6个高密度要素：
    1. 【世界观微创新】：不要常规背景。加一个扭曲的设定（例：修仙界被资本化，灵气需要氪金购买；或全世界都变异了，只有主角是正常人）。
    2. 【极致人设】：主角必须有“反常理”的特质或“癫感”（例：只要给钱连邪神都敢揍的极度贪财者；表面儒雅随和实则重度精神病的法外狂徒）。
    3. 【核心外挂与代价】：金手指的具体机制 + 严苛的触发条件/代价（例：能掠夺他人寿元，但每天必须进行一次极限作死；能读取心声，但一旦被发现就会肉体抹杀）。
    4. 【持续爽点机制】：支撑200万字的常规打脸套路是什么？（例：利用信息差让全世界大佬疯狂脑补；或者一次次在必死局里反向敲诈规则）。
    5. 【宏观主线】：主角最终要颠覆或对抗的终极目标（不仅仅是无敌，而是摧毁旧秩序、斩神、或修复天道）。
    6. 【黄金开局画面】：第一章前300字的极限绝杀。直接切入绝境或巨大反差冲突，并展示主角“发疯”破局的瞬间。
- **write_style**: 5个以上关键词（如：群像, 智斗, 幕后流, 克苏鲁, 唯我独法, 迪化, 慢热神作, 微短剧式快节奏、发疯反套路、杀伐果断、降维打击、腹黑沙雕、迪化脑补、极致爽文、信息差碾压、不按常理出牌等能增加厚度的词。用‘、’连接）。
- **target_reader**: 男性/女性/通用。
- **reference_novel**: 参考的经典或现象级神作名称（给系统作基调参考）。
- **note**: 给后续AI写作引擎的“变奏/避坑指令”。（例：“重点展现主角的神经质，反派无需降智，用主角的不按套路出牌来制造降维打击的爽感”）。
- **其他系统默认值**: volume_num(10), chapter_num(30), chapter_word_num(2000), status(0), outline_done(0), novel_gen_start_time(), novel_gen_end_time()。

# Output Format:
task_id,novel_type,novel_idea,write_style,target_reader,reference_novel,note,volume_num,chapter_num,chapter_word_num,status,outline_done,novel_gen_start_time,novel_gen_end_time

# Example Row:
1,诡异脑洞,"【世界观微创新】诡异全面入侵现实，人类只能靠献祭寿命换取苟延残喘。但诡异的运作完全遵循“资本市场逻辑”，恐惧是唯一硬通货。【极致人设】主角是个前世在华尔街被卷死的极品资本家，拥有“反向压榨”的癫狂属性，比诡异还要唯利是图。【核心外挂与代价】『黑心资本家系统』：能强行与诡异签订“不平等劳动合同”，代价是必须每个月保证资产（诡异币）翻倍，否则灵魂破产。【持续爽点机制】当别人在惊悚副本里九死一生时，主角在副本里开流水线，逼着贞子踩缝纫机、让吸血鬼无偿献血，利用信息差和金融杠杆收割诡异和全球觉醒者。【宏观主线】买下整个诡异降临的源头公司，成为凌驾于邪神之上的终极董事长。【黄金开局画面】A级血腥副本降临，一只缝合怪正要把刀劈向主角，主角不仅不躲，反而狂热地掏出一份合同拍在厉鬼脸上：“兄弟，我看你骨骼惊奇，有没有兴趣了解一下996福报？包吃住，每天只抽你500cc血！”厉鬼直接宕机。",微短剧式快节奏、腹黑沙雕、降维打击、发疯反套路、不按常理出牌,男性,诡异纪元：我比诡异还嚣张,"【AI避坑指令】严禁刻画主角内心的恐惧。所有的恐怖氛围渲染，都是为了反衬主角拿出“劳动合同”那一刻的荒诞感和降维打击爽感。多用侧面描写表现诡异的崩溃。",10,30,2000,0,0,,

现在，请严格按照格式生成 10 条高质量选题数据（确保不要省略双引号）：
```
Then copy the generated content into a text file and save it as ```.csv``` file.

2. Put the ```.csv``` file under dir ```novel_csvs/```.

## Start
### Quick Start
- Linux/macOS users:
1. First, you need to grant execution permission to the script: Open the terminal and run ```chmod +x start.sh```.
2. Starting method: Run ```./start.sh``` in the terminal.

- Windows users:
1. Just double-click ```start.bat```. Or if you have installed Git Bash, you can right-click and select ```Git Bash Here``` then run ```./start.sh```.

### Manual Start
#### Install
```bash
# Install conda
wget https://repo.anaconda.com/archive/Anaconda3-2024.10-1-Linux-x86_64.sh
bash Anaconda3-2024.10-1-Linux-x86_64.sh
source ~/.bashrc

# Change user from 'admin' to 'root'
sudo -i

# Clone repository
git clone https://github.com/RobertLau666/NovaNovel.git
cd NovaNovel

# Create virtual environment
conda create -n novanovel python=3.12
conda activate novanovel
pip install -r requirements.txt
```

#### Run
##### Command
```bash
python app.py                            # Process all tasks
python app.py -i 1                       # Only process task_id=1
python app.py -i 1,3,6                   # Process task_id=1,3,6
python app.py -i 3-6                     # Process task_id=3,4,5,6
python app.py -i 1,3-5,8                 # Mixed format: task_id=1,3,4,5,8
python app.py -f test.csv                # Specify task file
python app.py -i 1 --gen-cover           # Only process task_id=1, use cover generation
```

##### Gradio
```bash
python app_gradio.py --port 8080 --share
```
Then open the local URL http://127.0.0.1:8080 or http://localhost:8080 in your browser, or use the public URL if accessing remotely.

![app_gradio.jpeg](./assets/app_gradio.jpeg)

## Output Structure
```
novels/
├── csv-[novel_csv_name]/
│   ├── csv-[novel_csv_name]_task-[task_id]/
│   │   ├── log.log                 # Log
│   │   ├── outline.xlsx            # Outline (Multiple Sheets, Including Chapter Progress)
│   │   ├── outline.json            # Original outline JSON
│   │   ├── cover/                  # Novel cover (if you use cover generation)
│   │   └── content/                # Novel content
│   │       ├── 1/                  # Roll1
│   │       │   ├── 1-1.txt         # Roll1-Chapter1
│   │       │   ├── 1-2.txt         # Roll1-Chapter2
│   │       │   └── ...
│   │       ├── 2/                  # Roll2
│   │       │   ├── 2-1.txt         # Roll2-Chapter1
│   │       │   ├── 2-2.txt         # Roll2-Chapter2
│   │       │   └── ...
│   │       └── ...
│   └── csv-[novel_csv_name]_task-[task_id].zip   # Package .zip file
```

## Pack
### On Mac
```bash
source venv/bin/activate
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

pyinstaller --onefile \
  --collect-all gradio \
  --collect-all safehttpx \
  --collect-all groovy \
  --collect-all aiofiles \
  --collect-all httpx \
  app_gradio.py
```
Then double-click ```app_gradio``` under folder ```dist/```.
Then open the local URL http://127.0.0.1:8080 or http://localhost:8080 in your browser, or use the public URL if accessing remotely.

## Tools
### Count words
```bash
python tools/count_words.py --novel_csv_name 'test' --task_id '29'
```

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
这是我在小说网站上发布的小说的作品概述，帮我生成一个海报，你可以参考各大小说网站排行榜较前的小说封面风格，我的目的是大家看到封面之后，有吸引力，能点进来阅读，封面标题必须与小说标题一致，且封面尺寸为800*1066竖版，不要出现“AI生成”、“番茄小说”、“点击阅读”等之类的字眼
```
2. Use [ChatGPT](https://chatgpt.com/) to remove the watermark, upload the generated cover, prompt is as follows:
```
帮我修改一下这个图片，把左边那个语言气泡去掉，另外，把右下角的“亡灵法林默”改为“亡灵法师林默”，然后把右下角的“豆包AI生成”水印去掉。
```

## Release
Release the generated novel on [番茄小说网](https://fanqienovel.com/). The [rules](https://fanqienovel.com/welfare?enter_from=menu) are as follows:
```
1. 小说内容生成好后，立刻上传并立即发布部分，然后签约（到2万字）、推荐验证（到8万字）、推荐（到10万字）等，达到10万字的次月开始可算全勤；
2. 之后确保每天至少更新6000字以上（一般为2-3章），设置定时发布（最好每天早上8:00），然后上传当前月和下一月的字数，定下月月末闹钟，根据下月收益决定是否上传下下月的内容。
```

## Reference
1. Code version update information: [versions.md](versions/versions.md)
