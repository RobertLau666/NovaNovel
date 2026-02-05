# app
## app_v0.py
1. 重新再调用一次API生成总结

## app_v1.py
1. 一次生成summary

## app_v2.py 202601302059
1. 依次生成每卷的章，实时保存到outline.json和outline.xlsx中，支持中断处重新生成

## app_v3.py 202601302133
问题1	宏观设定生成后立即保存 JSON，防止崩溃丢失
问题2	添加 is_chapter_done() 函数，兼容 int/float/string 类型
问题3	大纲完成后自动更新 CSV 的 outline_done=1
问题4	添加 gen_start_time 和 gen_end_time 记录
问题5	将 bare except 替换为具体异常类型
问题6	统一使用 is_chapter_done() 判断进度

## app_v4.py 202602012117
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
16. log放在task_id目录下
17. 封面自动生成
18. 加参数gen-cover，是否使用封面生成
19. outline.xlsx中的列标题统一为中文
20. 加上app_gradio.py

## app_v5.py 202602031124
1. 完善build_chapter_context函数
2. 优化各处prompt
3. 动态调整“温度” (提升创造力)
4. 封面生成的时机 (优化体验)
5. 并发/异步生成 (核心性能优化)
6. outline.xlsx中加上“用户初始设定”
7. 优化prompt

## app_v6.py 202602050006
1. 修改 generate_volume_chapters 函数，让它**“切片”**生成章详细大纲。（开始跑2.csv的task_id1）

## app_v7.py 202602052041
1. 加上"【全书大结局特别指令】"
2. style_guides.py新增v6（继续生成2.csv的task_id1 8-72之后）
3. 加上phase_style、micro_pacing


# app_gradio
## app_gradio_v1.py 202602022030
1. 功能全部完善了

## app_gradio_v2.py 202602031124
1. 去掉刷新生成软链接功能
2. 预览xlsx文件可以选择sheet
3. gradio中也可以并发/异步生成
4. 预览的csv支持下载

## app_gradio_v3.py 202602050056
1. 加上“终止生成”按钮