import os
import csv
import jieba
import argparse
from tqdm import tqdm
from collections import Counter

def get_all_txt_files(folder_path):
    """递归获取所有txt文件路径"""
    txt_files = []
    # 检查路径是否存在
    if not os.path.exists(folder_path):
        return []
        
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith('.txt'):
                txt_files.append(os.path.join(root, file))
    return txt_files

def process_files(source_folder, output_file, filter_single_char=True):
    """
    主处理逻辑
    :param source_folder: 包含txt的文件夹路径
    :param output_file: 输出的csv文件路径
    :param filter_single_char: 是否过滤单字
    """
    # 打印绝对路径方便调试，防止相对路径出错
    abs_source_path = os.path.abspath(source_folder)
    print(f"正在扫描文件夹: {abs_source_path}")
    
    files = get_all_txt_files(source_folder)
    
    if not files:
        print(f"错误: 在路径 '{source_folder}' 下未找到任何 .txt 文件。")
        print("请检查你的 --novel_csv_name 和 --task_id 是否正确，或者路径结构是否匹配。")
        return

    print(f"共找到 {len(files)} 个文本文件，开始处理...")
    
    word_counter = Counter()

    # for idx, file_path in tqdm(enumerate(files)):
    # for idx, file_path in enumerate(tqdm(files, desc="处理进度")):
    for idx, file_path in tqdm(enumerate(files), total=len(files), desc="处理进度"):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                words = jieba.lcut(content)
                
                cleaned_words = []
                for word in words:
                    word = word.strip()
                    if not word:
                        continue
                    # 过滤单一字符
                    if filter_single_char and len(word) < 2:
                        continue
                    cleaned_words.append(word)
                
                word_counter.update(cleaned_words)
                
            # if (idx + 1) % 10 == 0:
            #     print(f"已处理 {idx + 1}/{len(files)} 个文件...")
                
        except UnicodeDecodeError:
            print(f"Warning: 文件 {file_path} 编码非UTF-8，跳过。")
        except Exception as e:
            print(f"Error: 处理文件 {file_path} 出错: {e}")

    # 确保输出目录存在
    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    print(f"正在写入结果到 {output_file} ...")
    try:
        with open(output_file, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['词', '出现次数'])
            for word, count in word_counter.most_common():
                writer.writerow([word, count])     
        print("完成！统计结果已生成。")
        
    except IOError as e:
        print(f"写入 CSV 失败: {e}")

if __name__ == "__main__":
    # 1. 定义参数解析器
    parser = argparse.ArgumentParser(description="统计小说生成任务的词频")
    
    # 2. 添加参数
    parser.add_argument('--novel_csv_name', type=str, required=True, help='小说生成任务ID')
    parser.add_argument('--task_id', type=str, required=True, help='子任务ID')
    parser.add_argument('--filter_single', action='store_true', default=True, help='是否过滤单字 (默认过滤)')

    # 3. 解析参数
    args = parser.parse_args()

    # 4. 组装路径 (完全按照你提供的逻辑)
    # 注意：这里的相对路径是相对于你运行 python 命令时的当前目录
    source_folder = f'./novels/{args.novel_csv_name}/task_{args.task_id}/content/'
    output_file = f'./{args.novel_csv_name}_{args.task_id}_word_frequency.csv'

    # 5. 执行处理
    print(f"任务 ID: {args.novel_csv_name}, 子任务 ID: {args.task_id}")
    process_files(source_folder, output_file, filter_single_char=args.filter_single)