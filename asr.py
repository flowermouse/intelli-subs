import argparse
from funasr import AutoModel

def format_time_ms(ms):
    """将毫秒转换为 SRT 时间格式 HH:MM:SS,mmm"""
    seconds = ms / 1000.0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    mmm = int(ms % 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{mmm:03d}"

def save_as_srt(res, output_file, gap_threshold=300):
    text = res[0]['text']
    timestamps = res[0]['timestamp'] # 字符级时间戳 [[start, end], ...]
    
    segments = []
    current_chars = []
    current_start = None
    previous_end = None
    
    ts_idx = 0
    # 遍历文本
    for char in text:
        # 如果是标点符号或空格，直接加入当前缓存，不触发分句，也不消耗时间戳
        if char in "，。！？；：,.;?! ":
            current_chars.append(char)
            continue
        
        # 如果是普通字符，获取其时间戳
        if ts_idx < len(timestamps):
            start, end = timestamps[ts_idx]
            
            # 核心逻辑：如果当前字符开始时间与上一个字符结束时间间隔超过阈值，则分句
            if previous_end is not None and (start - previous_end) > gap_threshold:
                if current_chars:
                    segments.append({
                        'text': "".join(current_chars).strip(),
                        'start': current_start,
                        'end': previous_end
                    })
                    current_chars = []
                    current_start = start # 新句子的开始时间
            
            if current_start is None:
                current_start = start
            
            current_chars.append(char)
            previous_end = end
            ts_idx += 1

    # 处理最后剩余的字符
    if current_chars:
        segments.append({
            'text': "".join(current_chars).strip(),
            'start': current_start,
            'end': previous_end
        })

    # 写入文件
    with open(output_file, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, 1):
            f.write(f"{i}\n")
            f.write(f"{format_time_ms(seg['start'])} --> {format_time_ms(seg['end'])}\n")
            f.write(f"{seg['text']}\n\n")
    print(f"SRT 文件已保存至: {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ASR to SRT Converter")
    parser.add_argument("input_file", type=str, help="Input audio file path")
    parser.add_argument("--output", type=str, default="output.srt", help="Output SRT file path")
    parser.add_argument("--threshold", type=int, default=800, help="Gap threshold in ms (default: 800)")
    args = parser.parse_args()

    model = AutoModel(
        model="paraformer-zh", 
        model_revision="v2.0.4",
        vad_model="fsmn-vad", 
        vad_model_revision="v2.0.4",
        punc_model="ct-punc-c", 
        punc_model_revision="v2.0.4",
    )
    res = model.generate(
        input=args.input_file, 
        batch_size_s=300, 
    )
    save_as_srt(res, args.output, gap_threshold=args.threshold)