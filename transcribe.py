#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import argparse
import time
import torch
import whisper
from pathlib import Path
from datetime import timedelta
from pydub import AudioSegment

def format_timestamp(seconds):
    """将秒转换为SRT格式的时间戳"""
    # SRT格式: 00:00:00,000
    td = timedelta(seconds=seconds)
    hours, remainder = divmod(td.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    milliseconds = td.microseconds // 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

def load_whisper_model(model_name="base"):
    """
    加载本地Whisper模型
    
    参数:
    - model_name: 模型大小，可选值有 "tiny", "base", "small", "medium", "turbo", "large"
    
    返回:
    - 加载好的模型
    """
    print(f"首次加载可能需要下载模型，请耐心等待...")
    print(f"正在加载 Whisper {model_name} 模型...")
    try:
        # 检查CUDA是否可用，如果可用则使用GPU
        device = "cuda" if torch.cuda.is_available() else "cpu"
        if device == "cuda":
            print(f"使用GPU进行处理")
        else:
            print(f"使用CPU进行处理（较慢）")
        
        model = whisper.load_model(model_name, device=device)
        print(f"模型加载完成")
        return model
    except Exception as e:
        print(f"加载模型时发生错误: {str(e)}")
        return None

def transcribe_audio_local(model, file_path, language=None):
    """
    使用本地Whisper模型转录音频
    
    参数:
    - model: 加载好的Whisper模型
    - file_path: 音频文件路径
    - language: 音频语言代码（如'zh'或'en'），默认为自动检测
    
    返回:
    - 字幕内容（SRT格式）
    """
    print(f"正在转录 {file_path}...")
    try:
        # 设置转录参数
        transcription_options = {
            "task": "transcribe",
            "fp16": torch.cuda.is_available(),
        }
        
        # 如果指定了语言，则添加到参数中
        if language:
            transcription_options["language"] = language
        
        print("开始转录音频...")
        # 转录音频
        result = model.transcribe(file_path, **transcription_options, verbose=True)
        
        segments = result["segments"]
            
        # 构建SRT格式的结果
        srt_content = []
        for i, segment in enumerate(segments, 1):
            start_time = format_timestamp(segment["start"])
            end_time = format_timestamp(segment["end"])
            text = segment["text"].replace("```", "").strip()
            
            srt_content.extend([
                f"{i}",
                f"{start_time} --> {end_time}",
                f"{text}",
                ""
            ])
        
        return "\n".join(srt_content)
    except Exception as e:
        print(f"转录时发生错误: {str(e)}")
        return ""

def transcribe(file_path, output_path, model_name="base", language=None):
    """直接处理完整音频文件
    
    参数:
    - file_path: 音频文件路径
    - output_path: 输出SRT字幕文件路径
    - model_name: Whisper模型大小
    - language: 音频语言代码
    """
    # 加载模型
    model = load_whisper_model(model_name)
    if not model:
        print("模型加载失败，无法继续转录")
        return None
    
    print(f"开始处理完整音频文件: {file_path}")
    
    # 直接转录完整音频
    transcription = transcribe_audio_local(model, file_path, language)
    
    # 保存结果
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(transcription)
    
    print(f"转录完成，已保存到: {output_path}")
    return output_path

def main():
    parser = argparse.ArgumentParser(description='使用本地Whisper模型将MP3文件转录为SRT字幕文件')
    parser.add_argument('input_file', help='输入的MP3文件路径')
    parser.add_argument('-o', '--output', help='输出的SRT字幕文件路径（可选）')
    parser.add_argument('-l', '--language', choices=['zh', 'en'], help='指定语言（zh：中文，en：英文，默认自动检测）')
    parser.add_argument('-c', '--chunk-minutes', type=int, default=10, help='每个音频块的长度（分钟），默认为10分钟')
    parser.add_argument('-m', '--model', choices=['tiny', 'base', 'small', 'medium', 'large'], default='base',
                      help='Whisper模型大小（默认base，越大越精确但越慢）')
    
    args = parser.parse_args()
    
    # 检查输入文件是否存在
    if not os.path.exists(args.input_file):
        print(f"错误：输入文件 {args.input_file} 不存在")
        return
    
    # 如果未指定输出文件，则基于输入文件名生成
    if not args.output:
        input_path = Path(args.input_file)
        args.output = str(input_path.with_suffix('.srt'))
    
    start_time = time.time()
    
    print("使用整体处理模式（适合30分钟以内的音频）...")
    transcribe(
        args.input_file, 
        args.output, 
        args.model, 
        args.language, 
    )
    
    elapsed_time = time.time() - start_time
    print(f"总转录时间: {elapsed_time:.2f} 秒")

if __name__ == '__main__':
    main()