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

if __name__ == "__main__":
    file = 'e.srt'
    subs = parse_srt(file)
    count = 0
    for sub in subs:
        if '♪' not in sub['text']:
            count += 1

    print(count)