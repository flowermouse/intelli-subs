import os
import re
import argparse
import json
from pathlib import Path
from google import genai
from zhipuai import ZhipuAI
from dotenv import load_dotenv
import requests

# 加载环境变量
load_dotenv()


def get_prompt(source, target, text_list_json):
    """
    生成基于JSON的翻译提示，指示LLM翻译JSON数组中的每个字符串。
    """
    return f"""你是一个专业的字幕翻译员。我会提供一个JSON数组，其中包含了按时间顺序排列的 {source} 字幕。

请将数组中的每一句字幕翻译成 {target}，并返回一个包含翻译结果的JSON数组。

翻译要求:
1.  **返回JSON数组**: 你的输出必须是一个严格格式化的JSON数组字符串。
2.  **数量必须相等**: 返回的数组必须与原始数组包含相同数量的元素。
3.  **确保流畅性**: 翻译应符合口语习惯，自然流畅。
4.  **适当灵活性**: 你可以根据上下文语境和你的理解对某些字幕进行灵活翻译，使得翻译质量更高。
5.  **不要添加额外内容**: 你的输出应该只有JSON数组本身，不包含任何如 "```json" 或 "```" 之类的标记或任何解释。

例如：
输入: ["He is coming.", "I am not ready."]
输出: ["他来了。", "我还没准备好。"]

现在，请翻译以下JSON数组中的内容：
---
{text_list_json}
---
"""


def parse_srt(file_path):
    """解析SRT文件，返回字幕条目列表"""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 按空行分割每条字幕
    pattern = re.compile(
        r"(\d+)\s+([\d:,]+)\s+-->\s+([\d:,]+)\s+([\s\S]+?)(?=\n\n|\Z)",
        re.MULTILINE,
    )
    subtitles = []

    for match in pattern.finditer(content):
        index = match.group(1)
        time_start = match.group(2)
        time_end = match.group(3)
        text = match.group(4).strip()

        subtitles.append(
            {
                "index": index,
                "time_start": time_start,
                "time_end": time_end,
                "text": text,
            }
        )

    return subtitles


def translate_batch_zhipu(
    subtitle_batch, source_language="en", target_lang="zh"
):
    """
    使用智谱 AI GLM-4-flash API通过JSON模式批量翻译字幕文本。

    参数:
    - subtitle_batch: 字幕对象列表。
    - source_language: 源语言。
    - target_lang: 目标语言。

    返回:
    - 成功则返回翻译后的字符串列表，失败则返回None。
    """
    ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY")
    if not ZHIPU_API_KEY:
        print("错误：未设置ZHIPU_API_KEY环境变量")
        return None

    client = ZhipuAI(api_key=ZHIPU_API_KEY)
    language_map = {"en": "英文", "zh": "中文"}

    # 1. 只提取文本，并转换为JSON
    texts_to_translate = [sub["text"] for sub in subtitle_batch]
    try:
        json_input = json.dumps(texts_to_translate, ensure_ascii=False)
    except TypeError as e:
        print(f"错误：无法将文本序列化为JSON: {e}")
        return None

    # 2. 获取新的Prompt
    prompt = get_prompt(
        language_map[source_language], language_map[target_lang], json_input
    )

    try:
        response = client.chat.completions.create(
            model="glm-4-flash",
            messages=[{"role": "user", "content": prompt}],
        )
        response_text = response.choices[0].message.content.strip()

        # 3. 清理并解析返回的JSON
        # 移除可能的Markdown代码块标记
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()

        translated_texts = json.loads(response_text)

        if isinstance(translated_texts, list):
            return translated_texts
        else:
            print("错误：API未返回有效的JSON数组格式。")
            return None

    except json.JSONDecodeError:
        print(f"错误：解析翻译结果JSON失败。模型返回: {response_text}")
        return None
    except Exception as e:
        print(f"翻译过程中发生未知错误: {str(e)}")
        return None


def translate_batch_gemini(
    subtitle_batch, source_language="en", target_lang="zh"
):
    """
    使用Gemini API通过JSON模式批量翻译字幕文本。

    参数:
    - subtitle_batch: 字幕对象列表。
    - source_language: 源语言。
    - target_lang: 目标语言。

    返回:
    - 成功则返回翻译后的字符串列表，失败则返回None。
    """
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        print("错误：未设置GEMINI_API_KEY环境变量")
        return None

    client = genai.Client(api_key=GEMINI_API_KEY)
    language_map = {"en": "英文", "zh": "中文"}

    texts_to_translate = [sub["text"] for sub in subtitle_batch]
    try:
        json_input = json.dumps(texts_to_translate, ensure_ascii=False)
    except TypeError as e:
        print(f"错误：无法将文本序列化为JSON: {e}")
        return None

    prompt = get_prompt(
        language_map[source_language], language_map[target_lang], json_input
    )

    # 定义 JSON Schema：要求是字符串数组
    response_json_schema = {
        "type": "array",
        "items": {"type": "string"},
        "minItems": len(texts_to_translate),
        "maxItems": len(texts_to_translate),
        "description": "与输入字幕一一对应的翻译结果数组，每个元素是翻译后的字幕文本。",
    }

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_json_schema": response_json_schema,
            },
        )

        # Gemini 在结构化输出模式下，response.text 会是一个合法的 JSON 字符串
        response_text = response.text.strip()

        translated_texts = json.loads(response_text)

        if isinstance(translated_texts, list):
            return translated_texts
        else:
            print("错误：API未返回有效的JSON数组格式。")
            return None

    except json.JSONDecodeError:
        print(f"错误：解析翻译结果JSON失败。模型返回: {response_text}")
        return None
    except Exception as e:
        print(f"翻译过程中发生未知错误: {str(e)}")
        # Optional: Add the model listing for debugging here if you still need it
        return None


def translate_batch_ollama(
    subtitle_batch, source_language="en", target_lang="zh", model="gemma3:27b"
):
    """
    使用本地 Ollama LLM 通过JSON模式批量翻译字幕文本。

    参数:
    - subtitle_batch: 字幕对象列表。
    - source_language: 源语言。
    - target_lang: 目标语言。
    - model: Ollama 模型名称。

    返回:
    - 成功则返回翻译后的字符串列表，失败则返回None。
    """
    OLLAMA_API_URL = "http://localhost:11434/api/generate"
    language_map = {"en": "英文", "zh": "中文"}

    texts_to_translate = [sub["text"] for sub in subtitle_batch]
    try:
        json_input = json.dumps(texts_to_translate, ensure_ascii=False)
    except TypeError as e:
        print(f"错误：无法将文本序列化为JSON: {e}")
        return None

    prompt = get_prompt(
        language_map[source_language], language_map[target_lang], json_input
    )

    try:
        response = requests.post(
            OLLAMA_API_URL,
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.2  # 添加一些基本参数以提高JSON输出稳定性
                },
            },
            timeout=120,
        )
        response.raise_for_status()
        response_json = response.json()
        response_text = response_json.get("response", "").strip()

        # 清理并解析返回的JSON
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()

        translated_texts = json.loads(response_text)

        if isinstance(translated_texts, list):
            return translated_texts
        else:
            print("错误：API未返回有效的JSON数组格式。")
            return None

    except json.JSONDecodeError:
        print(f"错误：解析翻译结果JSON失败。模型返回: {response_text}")
        return None
    except Exception as e:
        print(f"Ollama翻译出错: {str(e)}")
        return None


def translate_batch_openrouter(
    subtitle_batch,
    source_language="en",
    target_lang="zh",
    model="qwen/qwen-2-72b-instruct:free",
):
    """
    使用 openrouter.ai API 通过JSON模式批量翻译字幕文本。

    参数:
    - subtitle_batch: 字幕对象列表。
    - source_language: 源语言。
    - target_lang: 目标语言。
    - model: openrouter 模型名称。

    返回:
    - 成功则返回翻译后的字符串列表，失败则返回None。
    """
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
    if not OPENROUTER_API_KEY:
        print("错误：未设置OPENROUTER_API_KEY环境变量")
        return None

    language_map = {"en": "英文", "zh": "中文"}

    texts_to_translate = [sub["text"] for sub in subtitle_batch]
    try:
        json_input = json.dumps(texts_to_translate, ensure_ascii=False)
    except TypeError as e:
        print(f"错误：无法将文本序列化为JSON: {e}")
        return None

    prompt = get_prompt(
        language_map[source_language], language_map[target_lang], json_input
    )

    try:
        # Note: Using openai library for openrouter
        from openai import OpenAI

        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY,
        )

        completion = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},  # Ask for JSON output
            timeout=120,
        )
        response_text = completion.choices[0].message.content.strip()

        # Clean up and parse JSON
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()

        translated_texts = json.loads(response_text)

        if isinstance(translated_texts, list):
            return translated_texts
        else:
            print("错误：API未返回有效的JSON数组格式。")
            return None

    except json.JSONDecodeError:
        print(f"错误：解析翻译结果JSON失败。模型返回: {response_text}")
        return None
    except Exception as e:
        print(f"openrouter翻译出错: {str(e)}")
        return None


def create_smart_batches(subtitles, min_size=30, max_size=50):
    """

    智能分批字幕，确保每批大小在min_size和max_size之间。

    (此函数逻辑保持不变)

    """

    if not subtitles:

        return []

    ending_punctuations = {
        ".",
        "?",
        "!",
        "。",
        "？",
        "！",
        "…",
        ";",
        "；",
        ":",
        "：",
    }

    batches = []

    current_batch = []

    for i, subtitle in enumerate(subtitles):

        current_batch.append(subtitle)

        text = subtitle["text"].strip()

        is_last_subtitle = i == len(subtitles) - 1

        ends_with_punctuation = text and text[-1] in ending_punctuations

        batch_size_ok = len(current_batch) >= min_size

        batch_full = len(current_batch) >= max_size

        if (
            is_last_subtitle
            or (batch_size_ok and ends_with_punctuation)
            or batch_full
        ):

            if (
                batch_full
                and not ends_with_punctuation
                and not is_last_subtitle
            ):

                found = False

                for j in range(
                    len(current_batch) - 2,
                    max(0, len(current_batch) - min_size) - 1,
                    -1,
                ):

                    if (
                        current_batch[j]["text"].strip()
                        and current_batch[j]["text"].strip()[-1]
                        in ending_punctuations
                    ):

                        next_batch_start = current_batch[j + 1 :]

                        current_batch = current_batch[: j + 1]

                        batches.append(current_batch)

                        current_batch = next_batch_start

                        found = True

                        break

                if not found:

                    batches.append(current_batch)

                    current_batch = []

            else:

                batches.append(current_batch)

                current_batch = []

    if current_batch:

        batches.append(current_batch)

    return batches


def translate_srt_file(
    input_file,
    source_language="en",
    target_language="zh",
    agent="zhipu",
    output_file=None,
    min_batch=30,
    max_batch=50,
):
    """翻译SRT文件的主函数（已重构）"""

    if not output_file:

        input_path = Path(input_file)

        output_file = str(
            input_path.with_stem(f"{input_path.stem}_{target_language}")
        )

    print(f"正在处理文件: {input_file}")

    original_subs = parse_srt(input_file)

    subs_to_translate = [sub for sub in original_subs if "♪" not in sub["text"]]

    print(
        f"共读取 {len(original_subs)} 条字幕，其中 {len(subs_to_translate)} 条需要翻译。"
    )

    batches = create_smart_batches(subs_to_translate, min_batch, max_batch)

    print(f"字幕已分为 {len(batches)} 个批次进行翻译。")

    translated_subs_map = {}

    translation_functions = {
        "zhipu": translate_batch_zhipu,
        "gemini": translate_batch_gemini,
        "ollama": translate_batch_ollama,
        "openrouter": translate_batch_openrouter,
    }

    translate_func = translation_functions[agent]

    for i, batch in enumerate(batches):

        print(
            f"--- 开始翻译第 {i+1}/{len(batches)} 批 (共 {len(batch)} 条) ---"
        )

        translated_texts = translate_func(
            batch, source_language, target_language
        )

        # 验证批处理结果

        if translated_texts and len(translated_texts) == len(batch):

            print(f"第 {i+1} 批翻译成功。")

            for original_sub, translated_text in zip(batch, translated_texts):

                new_sub = original_sub.copy()

                new_sub["text"] = translated_text

                translated_subs_map[original_sub["index"]] = new_sub

        else:

            print(
                f"第 {i+1} 批翻译失败或返回数量不匹配，正在切换到逐条翻译模式..."
            )

            for sub in batch:

                # 逐条翻译（作为列表发送）

                single_translated_text = translate_func(
                    [sub], source_language, target_language
                )

                if single_translated_text and len(single_translated_text) == 1:

                    new_sub = sub.copy()

                    new_sub["text"] = single_translated_text[0]

                    translated_subs_map[sub["index"]] = new_sub

                    print(f"  - 字幕 #{sub['index']} 翻译成功。")

                else:

                    print(
                        f"  - 警告：字幕 #{sub['index']} 逐条翻译失败，将保留原文。"
                    )

                    translated_subs_map[sub["index"]] = sub  # 保留原文

    # 重构最终的字幕列表

    final_subs = []

    for sub in original_subs:

        if sub["index"] in translated_subs_map:

            final_subs.append(translated_subs_map[sub["index"]])

        else:

            # 不需要翻译的字幕（如包含'♪'的）

            final_subs.append(sub)

    # 写入文件

    with open(output_file, "w", encoding="utf-8") as f:

        for subtitle in final_subs:

            f.write(f"{subtitle['index']}\n")

            f.write(f"{subtitle['time_start']} --> {subtitle['time_end']}\n")

            f.write(f"{subtitle['text']}\n\n")

    print(f"\n翻译完成！共处理 {len(final_subs)} 条字幕。")

    print(f"翻译结果已保存到: {output_file}")

    return output_file


def main():

    parser = argparse.ArgumentParser(
        description="将SRT字幕文件翻译成指定语言。"
    )

    parser.add_argument("input_file", help="输入的SRT文件路径")

    parser.add_argument("-o", "--output", help="输出的SRT文件路径（可选）")

    parser.add_argument(
        "--source-lang", type=str, default="en", help="源语言代码 (例如: en)"
    )

    parser.add_argument(
        "--target-lang", type=str, default="zh", help="目标语言代码 (例如: zh)"
    )

    parser.add_argument(
        "--agent",
        choices=["zhipu", "gemini", "ollama", "openrouter"],
        default="zhipu",
        help="翻译服务提供商 (默认: zhipu)",
    )

    parser.add_argument(
        "--min-batch", type=int, default=30, help="每批最小字幕数 (默认: 30)"
    )

    parser.add_argument(
        "--max-batch", type=int, default=50, help="每批最大字幕数 (默认: 50)"
    )

    args = parser.parse_args()

    translate_srt_file(
        args.input_file,
        source_language=args.source_lang,
        target_language=args.target_lang,
        agent=args.agent,
        output_file=args.output,
        min_batch=args.min_batch,
        max_batch=args.max_batch,
    )


if __name__ == "__main__":

    main()
