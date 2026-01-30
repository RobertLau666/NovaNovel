# AINovel

基于 DeepSeek API 的小说自动批量生成系统，支持批量任务、断点续传。

## 快速开始
```bash
# 1. Clone
git clone https://github.com/RobertLau666/AINovel.git
cd AINovel

# 2. Install venv
conda create -n ainovel python=3.12
conda activate ainovel
pip install -r requirements.txt

# 3. set API Key in .env
DEEPSEEK_API_KEY=sk-xxxxxxxxxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

## 任务配置
Edit `novel_gen_tasks.csv`：

| 字段 | 说明 | 示例 |
|------|------|------|
| task_id | 任务ID（从1开始） | 1, 2, 3 |
| novel_type | 小说类型 | 玄幻、都市、言情 |
| novel_idea | 核心创意 | 主角逆袭成大佬 |
| write_style | 文风 | 轻松幽默、热血燃爆 |
| target_reader | 目标读者 | 男性、女性 |
| special_requirements | 特殊要求 | 每章结尾留悬念 |
| roll_num | 卷数 | 2 |
| chapter_num | 每卷章数 | 5 |
| word_num | 每章字数 | 2000 |
| status | 状态 | 0=待生成, 1=生成中, 2=已完成 |
| outline_done | 大纲完成 | 0=未完成, 1=已完成 |
| gen_start_time | 开始时间 | 自动填充 |
| gen_end_time | 结束时间 | 自动填充 |

## 运行
```bash
python app.py
```

## 命令参数
```bash
python app.py                    # 处理所有任务
python app.py -i 1               # 只处理 task_id=1 的任务
python app.py -i 1,3,6           # 处理 task_id=1,3,6 的任务
python app.py -i 3-6             # 处理 task_id=3,4,5,6 的任务
python app.py -i 1,3-5,8         # 混合格式: task_id=1,3,4,5,8
python app.py --api-key sk-xxx   # 指定 API Key
python app.py -f tasks.csv       # 指定任务文件
```

## 输出结构
```
novels/
└── 小说标题/
    ├── outline.xlsx       # 大纲（多Sheet，含章节进度）
    ├── outline.json       # 大纲原始JSON
    └── content/
        ├── 1-1.txt        # 第1卷第1章
        ├── 1-2.txt        # 第1卷第2章
        └── ...
```

## 断点续传
程序意外中断后，重新运行即可从中断处继续。进度存储位置：