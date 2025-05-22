#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import argparse
from pathlib import Path
import google.generativeai as genai
from zhipuai import ZhipuAI
from dotenv import load_dotenv
import requests

# 加载环境变量
load_dotenv()

def get_prompt(source, target, formatted_input):
    return f"""请将以下关于星球大战剧集"Andor"《安多》的SRT字幕文件从{source}翻译成{target}:

{formatted_input}

翻译要求:
1. 保留原始SRT格式，包括序号、时间戳（序号和时间戳不要变动）和翻译文本, 并且严格保证字幕条数相等（重要）
2. 直接返回完整的翻译后SRT格式
3. 确保输出格式为:
   序号
   时间戳
   中文翻译文本

   序号
   时间戳
   中文翻译文本
   
   (以此类推)
"""

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

def translate_batch_zhipu(subtitle_batch, source_language='en', target_lang='zh'):
    """使用智谱 AI GLM-4-flash API批量翻译字幕，保留完整SRT格式
    
    参数:
    - subtitle_batch: 字幕对象列表，每个对象包含index, time_start, time_end和text
    - target_lang: 目标语言，默认为中文
    
    返回:
    - 翻译结果列表，每个元素包含index, time_start, time_end和translated_text
    """
    # 从环境变量获取智谱 API 密钥
    ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY")
    
    if not ZHIPU_API_KEY:
        print("错误：未设置ZHIPU_API_KEY环境变量")
        return []
        
    # 创建智谱 AI 客户端
    client = ZhipuAI(api_key=ZHIPU_API_KEY)

    language_map = {'en': '英文', 'zh': '中文'}
    
    # 准备输入格式，完全保留原始SRT格式
    formatted_subtitles = []
    for sub in subtitle_batch:
        formatted_subtitles.append(f"{sub['index']}\n{sub['time_start']} --> {sub['time_end']}\n{sub['text']}")
    
    formatted_input = "\n\n".join(formatted_subtitles)

    prompt = get_prompt(language_map[source_language], language_map[target_lang], formatted_input)
    
    try:
        response = client.chat.completions.create(
            model="glm-4-flash",  # 使用智谱的 GLM-4-flash 模型
            messages=[
                {"role": "user", "content": prompt}
            ],
        )
        
        response_text = response.choices[0].message.content.strip()
        
        # 解析返回的SRT格式 (包括序号、时间戳和翻译文本)
        translated_subtitles = []
        pattern = re.compile(r'(\d+)\s+([\d:,]+)\s+-->\s+([\d:,]+)\s+([\s\S]+?)(?=\n\n\d+|\Z)', re.MULTILINE)
        
        for match in pattern.finditer(response_text):
            index = match.group(1)
            time_start = match.group(2)
            time_end = match.group(3)
            translated_text = match.group(4).strip()
            
            # 将解析后的结果保存为字典
            translated_subtitles.append({
                'index': index,
                'time_start': time_start,
                'time_end': time_end,
                'translated_text': translated_text
            })
        
        print(f"成功翻译 {len(translated_subtitles)} / {len(subtitle_batch)} 条字幕")
        return translated_subtitles
    except Exception as e:
        print(f"翻译出错: {str(e)}")
        return []

def translate_batch_gemini(subtitle_batch, source_language='en', target_lang='zh'):
    """使用Gemini 2.0 Flash Lite API批量翻译字幕，保留完整SRT格式
    
    参数:
    - subtitle_batch: 字幕对象列表，每个对象包含index, time_start, time_end和text
    - target_lang: 目标语言，默认为中文
    
    返回:
    - 翻译结果列表，每个元素包含index, time_start, time_end和translated_text
    """
    # 获取API密钥
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

    if not GEMINI_API_KEY:
        raise ValueError("请设置GEMINI_API_KEY环境变量或在.env文件中配置")

    # 配置Gemini API
    genai.configure(api_key=GEMINI_API_KEY)

    # 使用 Gemini 2.0 Flash 模型
    model = genai.GenerativeModel('gemini-2.0-flash')
    # 使用 Gemini 2.5 Flash 模型
    # model = genai.GenerativeModel('gemini-2.5-flash-preview-04-17')

    language_map = {'en': '英文', 'zh': '中文'}
    
    # 准备输入格式，完全保留原始SRT格式
    formatted_subtitles = []
    for sub in subtitle_batch:
        formatted_subtitles.append(f"{sub['index']}\n{sub['time_start']} --> {sub['time_end']}\n{sub['text']}")
    
    formatted_input = "\n\n".join(formatted_subtitles)

    prompt = get_prompt(language_map[source_language], language_map[target_lang], formatted_input)
    
    try:
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # 解析返回的SRT格式 (包括序号、时间戳和翻译文本)
        translated_subtitles = []
        pattern = re.compile(r'(\d+)\s+([\d:,]+)\s+-->\s+([\d:,]+)\s+([\s\S]+?)(?=\n\n\d+|\Z)', re.MULTILINE)
        
        for match in pattern.finditer(response_text):
            index = match.group(1)
            time_start = match.group(2)
            time_end = match.group(3)
            translated_text = match.group(4).strip()
            
            # 将解析后的结果保存为字典
            translated_subtitles.append({
                'index': index,
                'time_start': time_start,
                'time_end': time_end,
                'translated_text': translated_text
            })
        
        print(f"成功翻译 {len(translated_subtitles)} / {len(subtitle_batch)} 条字幕")
        return translated_subtitles
    except Exception as e:
        print(f"翻译出错: {str(e)}")
        try:
            # 尝试列出可用模型，帮助用户排查问题
            print("尝试获取可用模型列表...")
            available_models = genai.list_models()
            print("可用的模型有:")
            for model in available_models:
                print(f" - {model.name}")
        except Exception as list_error:
            print(f"无法获取可用模型列表: {str(list_error)}")
        return []

def translate_batch_ollama(subtitle_batch, source_language='en', target_lang='zh', model='gemma3:27b'):
    """
    使用本地 Ollama LLM 批量翻译字幕，保留完整SRT格式

    参数:
    - subtitle_batch: 字幕对象列表，每个对象包含index, time_start, time_end和text
    - source_language: 源语言代码
    - target_lang: 目标语言代码
    - model: Ollama 本地模型名称（如 'llama3'）

    返回:
    - 翻译结果列表，每个元素包含index, time_start, time_end和translated_text
    """
    # Ollama API endpoint
    OLLAMA_API_URL = "http://localhost:11434/api/generate"

    language_map = {'en': '英文', 'zh': '中文'}

    # 准备输入格式，完全保留原始SRT格式
    formatted_subtitles = []
    for sub in subtitle_batch:
        formatted_subtitles.append(f"{sub['index']}\n{sub['time_start']} --> {sub['time_end']}\n{sub['text']}")
    formatted_input = "\n\n".join(formatted_subtitles)

    prompt = get_prompt(language_map[source_language], language_map[target_lang], formatted_input)

    try:
        response = requests.post(
            OLLAMA_API_URL,
            json={
                "model": model,
                "prompt": prompt,
                "stream": False
            },
            timeout=120
        )
        response.raise_for_status()
        response_json = response.json()
        response_text = response_json.get("response", "").strip()

        # 解析返回的SRT格式 (包括序号、时间戳和翻译文本)
        translated_subtitles = []
        pattern = re.compile(r'(\d+)\s+([\d:,]+)\s+-->\s+([\d:,]+)\s+([\s\S]+?)(?=\n\n\d+|\Z)', re.MULTILINE)

        for match in pattern.finditer(response_text):
            index = match.group(1)
            time_start = match.group(2)
            time_end = match.group(3)
            translated_text = match.group(4).strip()

            translated_subtitles.append({
                'index': index,
                'time_start': time_start,
                'time_end': time_end,
                'translated_text': translated_text
            })

        print(f"Ollama翻译成功 {len(translated_subtitles)} / {len(subtitle_batch)} 条字幕")
        return translated_subtitles
    except Exception as e:
        print(f"Ollama翻译出错: {str(e)}")
        return []
    

def translate_batch_openrouter(subtitle_batch, source_language='en', target_lang='zh', model="qwen/qwen3-235b-a22b:free"): 
    """
    使用 openrouter.ai API 批量翻译字幕，保留完整SRT格式
    
    参数:
    - subtitle_batch: 字幕对象列表，每个对象包含index, time_start, time_end和text
    - source_language: 源语言代码
    - target_lang: 目标语言代码
    - model: openrouter 支持的模型名称
    
    返回:
    - 翻译结果列表，每个元素包含index, time_start, time_end和translated_text
    """
    import os
    import re
    from openai import OpenAI

    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
    if not OPENROUTER_API_KEY:
        print("错误：未设置OPENROUTER_API_KEY环境变量")
        return []

    language_map = {'en': '英文', 'zh': '中文'}
    formatted_subtitles = []
    for sub in subtitle_batch:
        formatted_subtitles.append(f"{sub['index']}\n{sub['time_start']} --> {sub['time_end']}\n{sub['text']}")
    formatted_input = "\n\n".join(formatted_subtitles)

    prompt = get_prompt(language_map[source_language], language_map[target_lang], formatted_input)

    try:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY,
        )
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": prompt}
            ],
            extra_headers={
                # 可选：可自定义 Referer 和 X-Title
                # "HTTP-Referer": "https://your-site.com",
                # "X-Title": "YourSiteName",
            },
            extra_body={},
            timeout=120
        )
        response_text = completion.choices[0].message.content.strip()
        # 解析返回的SRT格式 (包括序号、时间戳和翻译文本)
        translated_subtitles = []
        pattern = re.compile(r'(\d+)\s+([\d:,]+)\s+-->\s+([\d:,]+)\s+([\s\S]+?)(?=\n\n\d+|\Z)', re.MULTILINE)
        for match in pattern.finditer(response_text):
            index = match.group(1)
            time_start = match.group(2)
            time_end = match.group(3)
            translated_text = match.group(4).strip()
            translated_subtitles.append({
                'index': index,
                'time_start': time_start,
                'time_end': time_end,
                'translated_text': translated_text
            })
        print(f"openrouter翻译成功 {len(translated_subtitles)} / {len(subtitle_batch)} 条字幕")
        return translated_subtitles
    except Exception as e:
        print(f"openrouter翻译出错: {str(e)}")
        return []

def create_smart_batches(subtitles, min_size=30, max_size=50):
    """
    智能分批字幕，确保每批大小在min_size和max_size之间，且每批的最后一条字幕以标点符号结束
    
    参数:
    - subtitles: 字幕列表
    - min_size: 每批最小字幕数
    - max_size: 每批最大字幕数
    
    返回:
    - 分批后的字幕列表的列表
    """
    if not subtitles:
        return []
    
    # 常见标点符号集合
    ending_punctuations = {'.', '?', '!', '。', '？', '！', '…', ';', '；', ':', '：'}
    
    batches = []
    current_batch = []
    
    for i, subtitle in enumerate(subtitles):
        current_batch.append(subtitle)
        
        # 检查当前批次是否已达到最小大小，并且当前字幕以标点符号结束
        # 或者达到最大批次大小，或者是最后一条字幕
        text = subtitle['text'].strip()
        is_last_subtitle = (i == len(subtitles) - 1)
        ends_with_punctuation = text and text[-1] in ending_punctuations
        batch_size_ok = len(current_batch) >= min_size
        batch_full = len(current_batch) >= max_size
        
        if is_last_subtitle or (batch_size_ok and ends_with_punctuation) or batch_full:
            # 如果达到最大批次大小但不是以标点符号结束，向前查找最近的以标点符号结束的字幕
            if batch_full and not ends_with_punctuation and not is_last_subtitle:
                # 从当前批次的最后往前找，寻找最近的以标点符号结束的字幕
                found = False
                for j in range(len(current_batch) - 1, -1, -1):
                    if j < len(current_batch) - min_size:  # 确保不会导致批次大小小于min_size
                        break
                        
                    if current_batch[j]['text'].strip() and current_batch[j]['text'].strip()[-1] in ending_punctuations:
                        # 将这个位置之后的字幕移出当前批次
                        next_batch_start = current_batch[j+1:]
                        current_batch = current_batch[:j+1]
                        batches.append(current_batch)
                        current_batch = next_batch_start
                        found = True
                        break
                
                # 如果没找到合适的分割点，就使用整个批次
                if not found:
                    batches.append(current_batch)
                    current_batch = []
            else:
                batches.append(current_batch)
                current_batch = []
    
    # 处理可能剩余的字幕
    if current_batch:
        batches.append(current_batch)
    
    return batches


def translate_srt_file(input_file, source_language='en', target_language='zh', agent='zhipu', output_file=None, min_batch=30, max_batch=50):
    """翻译SRT文件的主函数"""
    # 如果未指定输出文件，则基于输入文件名生成
    if not output_file:
        input_path = Path(input_file)
        output_file = str(input_path.with_stem(f"{input_path.stem}_zh"))
    
    print(f"正在处理文件: {input_file}")
    print(f"将保存到: {output_file}")
    
    # 解析SRT文件
    subtitles = parse_srt(input_file)
    print(f"共读取 {len(subtitles)} 条字幕")
    
    # 智能分批字幕
    batches = create_smart_batches(subtitles, min_batch, max_batch)
    print(f"字幕已分为 {len(batches)} 个批次")
    
    # 保存所有翻译后的结果
    all_translations = []
    
    # 按批次进行翻译
    for i, batch in enumerate(batches):
        print(f"正在翻译第 {i+1}/{len(batches)} 批，包含 {len(batch)} 条字幕...")
        
        # 发送翻译请求
        if agent == 'zhipu':
            translated_texts = translate_batch_zhipu(batch, source_language, target_language)
        elif agent == 'gemini':
            translated_texts = translate_batch_gemini(batch, source_language, target_language)
        elif agent == 'ollama':
            translated_texts = translate_batch_ollama(batch, source_language, target_language)
        elif agent == 'openrouter':
            translated_texts = translate_batch_openrouter(batch, source_language, target_language)
        
        # 如果翻译成功，整合结果
        if translated_texts:
            # 重新解析从AI返回的翻译结果
            # 此处不再检查翻译结果数量是否匹配原始输入
            # 直接使用AI返回的结果构建翻译后的字幕
            
            # 整合当前批次的翻译结果
            for j, text in enumerate(translated_texts):
                if j < len(batch):  # 避免索引越界
                    subtitle_item = {
                        'index': batch[j]['index'],
                        'time_start': batch[j]['time_start'],
                        'time_end': batch[j]['time_end'],
                        'translated_text': text['translated_text'].replace('```', '').strip()
                    }
                    all_translations.append(subtitle_item)
        else:
            # 翻译失败，添加原始字幕作为占位符
            print("当前批次翻译失败，跳过...")
    
    # 保存翻译后的SRT文件
    if all_translations:
        save_translated_srt(all_translations, output_file)
        print(f"翻译完成，共处理 {len(all_translations)} 条字幕")
        print(f"翻译结果已保存到: {output_file}")
        return output_file
    else:
        print("翻译失败，未生成任何结果")
        return None
    
def save_translated_srt(translated_subtitles, output_file):
    """将翻译后的字幕保存到SRT文件"""
    with open(output_file, 'w', encoding='utf-8') as f:
        # 使用AI返回的翻译结果和时间戳，不做任何强制匹配或调整
        for i, subtitle in enumerate(translated_subtitles, 1):
            # 直接使用翻译结果中的信息
            f.write(f"{subtitle['index']}\n")
            f.write(f"{subtitle['time_start']} --> {subtitle['time_end']}\n")
            
            # 确保只写入翻译后的文本内容，而不是整个字典对象
            if isinstance(subtitle['translated_text'], dict) and 'translated_text' in subtitle['translated_text']:
                # 如果出现嵌套字典的情况
                f.write(f"{subtitle['translated_text']['translated_text']}\n\n")
            elif isinstance(subtitle['translated_text'], dict):
                # 如果是字典但没有translated_text键，尝试找到文本内容
                text = str(next(iter(subtitle['translated_text'].values())))
                f.write(f"{text}\n\n")
            else:
                # 标准情况：直接写入翻译文本
                f.write(f"{subtitle['translated_text']}\n\n")


def main():
    parser = argparse.ArgumentParser(description='将英文SRT字幕文件翻译成中文')
    parser.add_argument('input_file', help='输入的英文SRT文件路径')
    parser.add_argument('-o', '--output', help='输出的中文SRT文件路径（可选）')
    parser.add_argument('--source-lang', type=str, default='en', help='源语言（默认英文）')
    parser.add_argument('--target-lang', type=str, default='zh', help='目标语言（默认中文）')
    parser.add_argument('--agent', choices=['zhipu', 'gemini', 'ollama', 'openrouter'], default='zhipu', help='翻译代理（默认智谱，可选ollama/gemini/zhipu/openrouter）')
    parser.add_argument('--min-batch', type=int, default=30, help='每批最小字幕数量（默认30）')
    parser.add_argument('--max-batch', type=int, default=50, help='每批最大字幕数量（默认50）')
    
    args = parser.parse_args()
    
    translate_srt_file(args.input_file, 
                       source_language=args.source_lang,
                       target_language=args.target_lang,
                       agent=args.agent,
                       output_file=args.output,
                       min_batch=args.min_batch,
                       max_batch=args.max_batch)

if __name__ == '__main__':
    main()