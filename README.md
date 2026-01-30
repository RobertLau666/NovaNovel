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
```

## Set novel tasks
Edit `novel_gen_tasks.csv`:

| Field                | Description                      | Example                              |
|----------------------|----------------------------------|--------------------------------------|
| task_id              | Task ID (starting from 1)        | 1, 2, 3                              |
| novel_type           | Novel Genre                      | Fantasy, Urban, Romance              |
| novel_idea           | Core Concept                     | Protagonist's comeback to become a top dog |
| write_style          | Writing Style                    | Light and humorous, Passionate and thrilling |
| target_reader        | Target Readers                   | Male, Female                         |
| special_requirements | Special Requirements             | End each chapter with a cliffhanger  |
| roll_num             | Number of Volumes                | 2                                    |
| chapter_num          | Chapters per Volume              | 5                                    |
| word_num             | Words per Chapter                | 2000                                 |
| status               | Status                           | 0=Pending, 1=Generating, 2=Completed |
| outline_done         | Outline Completion               | 0=Incomplete, 1=Completed            |
| gen_start_time       | Generation Start Time            | Auto-filled                          |
| gen_end_time         | Generation End Time              | Auto-filled                          |

## Run
```bash
python app.py
```

## Command params
```bash
python app.py                    # Process all tasks
python app.py -i 1               # Only process task_id=1
python app.py -i 1,3,6           # Process task_id=1,3,6
python app.py -i 3-6             # Process task_id=3,4,5,6
python app.py -i 1,3-5,8         # Mixed format: task_id=1,3,4,5,8
python app.py --api-key sk-xxx   # Specify API Key
python app.py -f tasks.csv       # Specify task file
```

## Output Structure
```
novels/
└── task_[id]/
    ├── outline.xlsx       # Outline (Multiple Sheets, Including Chapter Progress)
    ├── outline.json       # Original outline JSON
    └── content/
        ├── 1-1.txt        # Roll1-Chapter1
        ├── 1-2.txt        # Roll1-Chapter2
        └── ...
```