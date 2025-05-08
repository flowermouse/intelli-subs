#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import argparse
from pathlib import Path
import copy

def parse_time(time_str):
    """
    将SRT时间字符串转换为总毫秒数
    例如："00:00:10,500" -> 10500 (毫秒)
    """
    hours, minutes, seconds_ms = time_str.split(':')
    seconds, milliseconds = seconds_ms.split(',')
    total_ms = int(hours) * 3600000 + int(minutes) * 60000 + int(seconds) * 1000 + int(milliseconds)
    return total_ms

def format_time(total_ms):
    """
    将总毫秒数转换为SRT时间字符串
    例如：10500 (毫秒) -> "00:00:10,500"
    """
    hours = total_ms // 3600000
    minutes = (total_ms % 3600000) // 60000
    seconds = (total_ms % 60000) // 1000
    milliseconds = total_ms % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

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

def save_srt(subtitles, output_path):
    """保存字幕列表为SRT文件"""
    with open(output_path, 'w', encoding='utf-8') as f:
        for i, subtitle in enumerate(subtitles, 1):
            f.write(f"{i}\n")
            f.write(f"{subtitle['time_start']} --> {subtitle['time_end']}\n")
            f.write(f"{subtitle['text']}\n\n")
    
    print(f"已保存规范化的字幕文件: {output_path}")

def normalize_subtitles(subtitles):
    """
    规范化字幕，确保每一行字幕均以标点符号结束，并合并特定短句
    1. 先分割含有中间标点的字幕
    2. 再合并未以标点结束的字幕
    3. 合并以逗号(,)、中文逗号(，)或顿号(、)结尾的短句，使每个合并后的句子不超过10个单词
    
    参数:
    - subtitles: 原始字幕列表
    
    返回:
    - 规范化后的字幕列表
    """
    if not subtitles:
        return []
    
    # 定义标点符号集合
    punctuations = {'.', '。', '!', '！', '?', '？', ',', '，', ';', '；', ':', '：', '、'}
    
    # 第一步：对含有中间标点的字幕进行分割
    split_subtitles = []
    
    for subtitle in subtitles:
        text = subtitle['text']
        # 如果文本为空或只有一个字符，无需处理
        if len(text) <= 1:
            split_subtitles.append(subtitle)
            continue
        
        # 查找中间的标点符号位置
        split_positions = []
        for i in range(len(text) - 1):  # 不检查最后一个字符
            if text[i] in punctuations and text[i + 1] == ' ':
                split_positions.append(i)
        
        # 如果没有中间标点，保持不变
        if not split_positions:
            split_subtitles.append(subtitle)
            continue
        
        # 计算时间分配
        start_time_ms = parse_time(subtitle['time_start'])
        end_time_ms = parse_time(subtitle['time_end'])
        total_duration_ms = end_time_ms - start_time_ms
        time_per_char = total_duration_ms / len(text)
        
        # 进行分割
        start_idx = 0
        current_start_time_ms = start_time_ms
        
        for pos in split_positions:
            # 计算当前分段的结束时间
            current_end_time_ms = int(start_time_ms + (pos + 1) * time_per_char)
            
            # 创建新的字幕条目
            split_subtitles.append({
                'index': subtitle['index'],  # 暂时保留原索引，稍后重新编号
                'time_start': format_time(current_start_time_ms),
                'time_end': format_time(current_end_time_ms),
                'text': text[start_idx:pos+1].strip()
            })
            
            # 更新下一段的起始位置和时间
            start_idx = pos + 1
            current_start_time_ms = current_end_time_ms
        
        # 添加最后一段
        if start_idx < len(text):
            split_subtitles.append({
                'index': subtitle['index'],
                'time_start': format_time(current_start_time_ms),
                'time_end': format_time(end_time_ms),
                'text': text[start_idx:].strip()
            })
    
    # 第二步：合并未以标点结束的字幕
    merged_subtitles = []
    current_subtitle = None
    
    for subtitle in split_subtitles:
        text = subtitle['text']
        
        if not current_subtitle:
            current_subtitle = copy.deepcopy(subtitle)
            continue
        
        # 检查当前字幕是否以标点符号结束
        if not text.strip() or not current_subtitle['text'].strip():
            continue
            
        if current_subtitle['text'].strip()[-1] in punctuations:
            # 当前字幕以标点结束，保存并开始新字幕
            merged_subtitles.append(current_subtitle)
            current_subtitle = copy.deepcopy(subtitle)
        else:
            # 当前字幕不以标点结束，合并到当前字幕
            current_subtitle['time_end'] = subtitle['time_end']
            current_subtitle['text'] += " " + subtitle['text']
    
    # 处理最后一条字幕
    if current_subtitle:
        merged_subtitles.append(current_subtitle)
    
    # 第三步：只合并以逗号(,)、中文逗号(，)或顿号(、)结尾的短句
    comma_punctuations = {',', '，', '、'}  # 定义需要合并的标点符号
    short_merged_subtitles = []
    current_subtitle = None
    word_count = 0
    
    for subtitle in merged_subtitles:
        text = subtitle['text'].strip()
        # 计算当前字幕中的单词数
        current_words = len(text.split())
        
        if not current_subtitle:
            current_subtitle = copy.deepcopy(subtitle)
            word_count = current_words
            continue
        
        # 检查上一个字幕是否以需要合并的标点符号结尾
        prev_text = current_subtitle['text'].strip()
        ends_with_comma = prev_text and prev_text[-1] in comma_punctuations
        
        # 只有当上一个字幕以逗号等结尾，且合并后不超过10个单词时，才进行合并
        if ends_with_comma and word_count + current_words <= 10:
            # 可以合并短句
            current_subtitle['time_end'] = subtitle['time_end']
            current_subtitle['text'] += " " + text
            word_count += current_words
        else:
            # 不能合并，保存当前字幕并开始新一条
            short_merged_subtitles.append(current_subtitle)
            current_subtitle = copy.deepcopy(subtitle)
            word_count = current_words
    
    # 处理最后一条字幕
    if current_subtitle:
        short_merged_subtitles.append(current_subtitle)
    
    # 重新编号字幕
    for i, subtitle in enumerate(short_merged_subtitles, 1):
        subtitle['index'] = str(i)
    
    return short_merged_subtitles

def normalize_srt_file(input_file, output_file=None):
    """规范化SRT文件的主函数"""
    # 如果未指定输出文件，则基于输入文件名生成
    if not output_file:
        input_path = Path(input_file)
        output_file = str(input_path.with_stem(f"{input_path.stem}_normalized"))
    
    print(f"正在处理文件: {input_file}")
    print(f"将保存到: {output_file}")
    
    # 解析SRT文件
    subtitles = parse_srt(input_file)
    print(f"共读取 {len(subtitles)} 条字幕")
    
    # 规范化字幕
    normalized = normalize_subtitles(subtitles)
    print(f"规范化后为 {len(normalized)} 条字幕")
    
    # 保存为SRT文件
    save_srt(normalized, output_file)
    
    return output_file

def main():
    parser = argparse.ArgumentParser(description='规范化SRT字幕文件，合并相连的字幕')
    parser.add_argument('input_file', help='输入的SRT文件路径')
    parser.add_argument('-o', '--output', help='输出的规范化SRT文件路径（可选）')
    
    args = parser.parse_args()
    
    # 检查输入文件是否存在
    if not os.path.exists(args.input_file):
        print(f"错误：输入文件 {args.input_file} 不存在")
        return
    
    normalize_srt_file(args.input_file, args.output)

if __name__ == '__main__':
    main()