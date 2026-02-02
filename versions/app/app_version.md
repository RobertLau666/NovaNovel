# app_v0.py
1. 重新再调用一次API生成总结

# app_v1.py
1. 一次生成summary

# app_v2.py 202601302059
1. 依次生成每卷的章，实时保存到outline.json和outline.xlsx中，支持中断处重新生成

# app_v3.py 202601302133
问题1	宏观设定生成后立即保存 JSON，防止崩溃丢失
问题2	添加 is_chapter_done() 函数，兼容 int/float/string 类型
问题3	大纲完成后自动更新 CSV 的 outline_done=1
问题4	添加 gen_start_time 和 gen_end_time 记录
问题5	将 bare except 替换为具体异常类型
问题6	统一使用 is_chapter_done() 判断进度

# app_v4.py 202602012117
1. 删除注释
2. 封装成NovelGenerator类
3. 加上log
4. 字数部分加上“至少”
5. 任务完成后加上打包为zip
6. 在novels下新建同csv名的子文件夹，防止task_id文件夹被覆盖掉
7. outline.xlsx的Sheet“章详细大纲”中的“chapter_done”后面加上“chapter_word_num”
8. 在outline.xlsx的Sheet“卷详细大纲”的列“roll_done”,并且在“roll_done”的后面加上一列“roll_word_num”
9. 返回JSON的键名称一定要跟下面JSON模版的键名称保持一致，例如返回"本章关键冲突/爽点"，而不是“本章关键冲突/爽点补充”
10. 删除字数的“至少”
11. 加上indent_size，定义缩进的个数
12. 不要输出到终端了
13. README.md表格的示例重新改为中文
14. summary改为chapter_summary
15. deepseek封装成类
16. 封面自动生成
17. 加参数gen-cover，是否使用封面生成