import re

def parse_srt(file_path):
    """解析SRT文件，返回字幕条目列表"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 按空行分割每条字幕
    pattern = re.compile(r'(\d+)\s+([\d:,]+)\s+-->\s+([\d:,]+)\s+([\s\S]+?)(?=\n\n|\Z)', re.MULTILINE)
    subtitles = []
    
    for match in pattern.finditer(content):
        index = match.group(1)
        time_start = match.group(2)
        time_end = match.group(3)
        text = match.group(4).strip()
        
        subtitles.append({
            'index': index,
            'time_start': time_start,
            'time_end': time_end,
            'text': text
        })
    
    return subtitles

def save_srt(subtitles, file_path):
    """将字幕条目列表保存为SRT文件"""
    # 创建目录如果不存在
    with open(file_path, 'w', encoding='utf-8') as f:
        for subtitle in subtitles:
            f.write(f"{subtitle['index']}\n")
            f.write(f"{subtitle['time_start']} --> {subtitle['time_end']}\n")
            f.write(f"{subtitle['text']}\n\n")


if __name__ == "__main__":
    # 示例用法
    file_path = '2.1.srt'  # 替换为你的SRT文件路径
    subtitles = parse_srt(file_path)
    
    for i, subtitle in enumerate(subtitles):
        subtitles[i]['index'] = str(i + 1)

    # 保存修正后的SRT文件
    output_path = '2.srt'  # 替换为你想保存的路径
    save_srt(subtitles, output_path)
    print(f"已保存修正后的字幕文件: {output_path}")

        