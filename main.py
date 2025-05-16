#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import argparse
from pathlib import Path
import time
import subprocess
import shutil

# 导入各个模块的主要功能
from transcribe import transcribe
from normalize import normalize_srt_file
from translator import translate_srt_file

def embed_subtitle(video_file, subtitle_file, output_file, subtitle_format='srt', subtitle_title='chs'):
    """
    使用 ffmpeg 将字幕嵌入到视频文件中
    
    参数:
    - video_file: 视频文件路径
    - subtitle_file: 字幕文件路径
    - output_file: 输出文件路径
    - subtitle_format: 字幕格式，默认为 srt
    - subtitle_title: 字幕标题，默认为"中文字幕"
    
    返回:
    - 输出文件路径
    """
    if not os.path.exists(video_file):
        print(f"错误：视频文件 '{video_file}' 不存在！")
        return None
    
    if not os.path.exists(subtitle_file):
        print(f"错误：字幕文件 '{subtitle_file}' 不存在！")
        return None
    
    print(f"开始嵌入字幕到视频中...")
    
    # 构建 ffmpeg 命令
    cmd = [
        'ffmpeg', '-i', video_file, '-i', subtitle_file,
        '-map', '0:v', '-map', '0:a', '-map', '1:s', '-map', '0:s?',
        '-c:v', 'copy', '-c:a', 'copy', '-c:s', subtitle_format,
        '-disposition:s:0', 'default', '-metadata:s:s:0', f'title={subtitle_title}',
        output_file
    ]
    
    try:
        # 执行 ffmpeg 命令
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"字幕嵌入成功！输出文件: {output_file}")
        return output_file
    except subprocess.CalledProcessError as e:
        print(f"字幕嵌入失败: {e}")
        print(f"错误输出: {e.stderr}")
        return None
    except Exception as e:
        print(f"发生错误: {e}")
        return None

def main():
    """
    整合音频转字幕、字幕规范化、字幕翻译、字幕嵌入的完整流程
    流程：
    1. 转录音频生成英文SRT字幕
    2. 规范化字幕（分割长句、确保每行以标点结束、合并短句）
    3. 翻译字幕为中文
    4. 将字幕嵌入到视频文件中（如果提供了视频文件）
    """
    parser = argparse.ArgumentParser(description='音频转字幕、规范化、翻译、嵌入的一体化工具')
    parser.add_argument('input_file', help='输入的音频或视频文件路径')
    parser.add_argument('-o', '--output', help='输出的最终字幕文件路径（可选）')
    parser.add_argument('-sl', '--source-language', choices=['zh', 'en'], default='en',
                      help='翻译前的源语言（zh：中文，en：英文），默认为英文')
    parser.add_argument('-tl', '--target-language', choices=['zh', 'en'], default='zh',
                      help='翻译后的目标语言（zh：中文，en：英文），默认为中文')
    parser.add_argument('-m', '--model', choices=['tiny', 'base', 'small', 'medium', 'turbo', 'large'], default='turbo',
                      help='Whisper模型大小（默认turbo，越大越精确但越慢）')
    parser.add_argument('-t', '--theme', help='音频/视频主题（用于转录时的初始提示）', default='YouTube video')
    parser.add_argument('-a', '--agent', choices=['gemini', 'zhipu'], default='zhipu',
                      help='翻译代理（gemini, zhipu），默认为智谱翻译）')
    parser.add_argument('--skip-transcribe', action='store_true',
                      help='跳过转录步骤，直接从字幕规范化开始（需要提供现有SRT文件）')
    parser.add_argument('--skip-normalize', action='store_true',
                      help='跳过规范化步骤，直接翻译原始字幕')
    parser.add_argument('--intermediate-dir', default='temp',
                      help='中间文件保存目录，默认为"temp"')
    # 新增参数：用于字幕嵌入功能
    parser.add_argument('--embed-subtitle', action='store_true',
                      help='将生成的字幕嵌入到视频文件中（需要提供视频文件）')
    parser.add_argument('--video-file', 
                      help='用于嵌入字幕的视频文件路径（如果与输入文件相同，可以不提供）')
    parser.add_argument('--output-video',
                      help='嵌入字幕后的输出视频文件路径（可选）')
    parser.add_argument('--subtitle-title', default='chs',
                      help='嵌入字幕的标题，默认为"chs"')
    
    args = parser.parse_args()
    
    # 创建中间文件目录（如果不存在）
    intermediate_dir = Path(args.intermediate_dir)
    intermediate_dir.mkdir(exist_ok=True)
    
    input_file = args.input_file
    input_path = Path(input_file)
    
    # 根据输入文件名生成各阶段的输出文件名
    transcribed_srt = str(intermediate_dir / f"{input_path.stem}.srt")
    normalized_srt = str(intermediate_dir / f"{input_path.stem}_normalized.srt")
    
    # 如果未指定最终输出文件，则根据输入文件名生成
    if not args.output:
        if args.target_language == 'zh':
            final_output = str(input_path.with_stem(f"{input_path.stem}_zh").with_suffix('.srt'))
        else:
            final_output = str(input_path.with_stem(f"{input_path.stem}_en").with_suffix('.srt'))
    else:
        final_output = args.output
    
    total_start_time = time.time()
    
    # 步骤 1: 转录音频生成SRT字幕
    if not args.skip_transcribe:
        print("\n===== 步骤 1: 转录音频 =====")
        print(f"输入文件: {input_file}")
        print(f"输出SRT: {transcribed_srt}")
        
        if not os.path.exists(input_file):
            print(f"错误: 输入文件 {input_file} 不存在")
            return
        
        step_start_time = time.time()
        
        # 调用转录功能
        transcribe(
            input_file,
            args.model,
            args.source_language,
            args.theme
        )
        
        step_time = time.time() - step_start_time
        print(f"转录完成，用时: {step_time:.2f} 秒")
        input_file = transcribed_srt  # 更新输入文件为转录结果
        
    # 步骤 2: 规范化字幕
    if not args.skip_normalize:
        print("\n===== 步骤 2: 规范化字幕 =====")
        print(f"输入SRT: {input_file}")
        print(f"输出规范化SRT: {normalized_srt}")
        
        if not os.path.exists(input_file):
            print(f"错误: 输入文件 {input_file} 不存在")
            return
        
        step_start_time = time.time()
        
        # 调用字幕规范化功能
        normalize_srt_file(input_file, normalized_srt)
        
        step_time = time.time() - step_start_time
        print(f"规范化完成，用时: {step_time:.2f} 秒")
        input_file = normalized_srt  # 更新输入文件为规范化结果
    
    # 步骤 3: 翻译字幕（如果需要）
    if args.source_language != args.target_language:
        print("\n===== 步骤 3: 翻译字幕 =====")
        print(f"输入SRT: {input_file}")
        print(f"输出翻译SRT: {final_output}")
        
        if not os.path.exists(input_file):
            print(f"错误: 输入文件 {input_file} 不存在")
            return
        
        step_start_time = time.time()
        
        # 调用字幕翻译功能
        translate_srt_file(input_file, args.source_language, args.target_language, args.agent, final_output)
        
        step_time = time.time() - step_start_time
        print(f"翻译完成，用时: {step_time:.2f} 秒")
    else:
        # 如果跳过翻译，或目标语言是英文，直接复制规范化后的文件作为最终输出
        shutil.copy2(input_file, final_output)
        print(f"\n已跳过翻译，最终输出: {final_output}")
    
    # 步骤 4: 嵌入字幕到视频（如果需要）
    if args.embed_subtitle:
        print("\n===== 步骤 4: 嵌入字幕到视频 =====")
        
        # 确定视频文件路径
        video_file = args.video_file
        if not video_file:
            # 如果未指定视频文件，检查输入文件是否为视频
            input_ext = input_path.suffix.lower()
            video_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm']
            if input_ext in video_extensions:
                video_file = str(input_path)
                print(f"使用原始输入文件作为视频源: {video_file}")
            else:
                print("错误: 未指定视频文件，且输入文件不是视频文件")
                print("请使用 --video-file 参数指定视频文件")
                return
        
        # 确定输出视频文件路径
        if not args.output_video:
            output_video = str(Path(video_file).with_stem(f"{Path(video_file).stem}_{args.target_language}_subtitled"))
        else:
            output_video = args.output_video
        
        step_start_time = time.time()
        
        # 调用字幕嵌入功能
        embed_subtitle(
            video_file,
            final_output,
            output_video,
            'srt',
            args.subtitle_title
        )
        
        step_time = time.time() - step_start_time
        print(f"字幕嵌入完成，用时: {step_time:.2f} 秒")
        print(f"输出视频文件: {output_video}")
    
    total_time = time.time() - total_start_time
    print(f"\n===== 处理完成 =====")
    print(f"总用时: {total_time:.2f} 秒")
    print(f"最终字幕文件: {final_output}")
    if args.embed_subtitle:
        print(f"带字幕视频文件: {output_video}")

if __name__ == "__main__":
    main()