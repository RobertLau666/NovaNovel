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
4. 任务完成后加上打包为zip