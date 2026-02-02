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
[DEEPSEEK](https://platform.deepseek.com/usage)
[DMX](https://www.dmxapi.com/console)

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