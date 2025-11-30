import re
import os
import math
import subprocess
import argparse
from time import sleep
from pydub import AudioSegment

SAMPLE_RATE = 24000  # edge-tts 默认输出 24kHz
CHANNELS = 1

def parse_srt(file_path, merge_gap_ms=300):
    """解析 SRT 文件，返回字幕列表 [{'start_ms': int, 'end_ms': int, 'text': str}, ...]
       若相邻两条字幕的间隔 <= merge_gap_ms，则合并为一条。
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = re.compile(
        r"(\d+)\s+([\d:,]+)\s+-->\s+([\d:,]+)\s+([\s\S]+?)(?=\n\n|\Z)",
        re.MULTILINE,
    )
    raw_subtitles = []

    for match in pattern.finditer(content):
        index = int(match.group(1))
        start = srt_time_to_ms(match.group(2))
        end = srt_time_to_ms(match.group(3))
        text = match.group(4).strip().replace("\n", " ")

        raw_subtitles.append(
            {"index": index, "start_ms": start, "end_ms": end, "text": text}
        )

    if not raw_subtitles:
        return []

    # 合并间隔 <= merge_gap_ms 的相邻字幕
    merged = []
    current = raw_subtitles[0].copy()

    for sub in raw_subtitles[1:]:
        gap = sub["start_ms"] - current["end_ms"]
        if gap <= merge_gap_ms:
            # 合并：起始时间取当前的，结束时间取后一条的，文本拼接
            current["end_ms"] = max(current["end_ms"], sub["end_ms"])
            current["text"] = current["text"].rstrip() + " " + sub["text"].lstrip()
        else:
            merged.append(current)
            current = sub.copy()

    merged.append(current)

    # 重新编号 index
    for i, sub in enumerate(merged, start=1):
        sub["index"] = i

    return merged

def srt_time_to_ms(time_str):
    """将 SRT 时间格式 (HH:MM:SS,mmm) 转换为毫秒"""
    hours, minutes, seconds = time_str.split(":")
    seconds, milliseconds = seconds.split(",")
    total_ms = (
        int(hours) * 3600000
        + int(minutes) * 60000
        + int(seconds) * 1000
        + int(milliseconds)
    )
    return total_ms

def generate_audio_for_text(text, idx, voice_name="zh-CN-YunxiaoMultilingualNeural", rate=None):
    """用 edge-tts 生成音频，返回 mp3 文件路径"""
    out_mp3 = f"tmp_{idx}.mp3"
    cmd = [
        "edge-tts",
        "--voice", voice_name,
        "--text", text,
        "--write-media", out_mp3
    ]
    if rate:
        cmd.extend([f"--rate={rate}"])
    subprocess.run(cmd, check=True)
    return out_mp3

def align_and_merge_audio(subtitles, voice_name="zh-CN-YunxiaoMultilingualNeural"):
    merged = AudioSegment.silent(duration=0, frame_rate=SAMPLE_RATE)
    current_position = 0

    for i, sub in enumerate(subtitles):
        start_ms = sub["start_ms"]
        end_ms = sub["end_ms"]
        text = sub["text"]

        print(f"[{i+1}/{len(subtitles)}] 生成音频: {text[:30]}... ({start_ms}ms -> {end_ms}ms)")

        while True:
            try:
                mp3_path = generate_audio_for_text(text, i, voice_name)
                seg = AudioSegment.from_file(mp3_path)
                seg = seg.set_frame_rate(SAMPLE_RATE).set_channels(CHANNELS)
                break
            except Exception as e:
                print(f"   ⚠️  生成失败: {e}, 重试中...")
            sleep(1)
        
        # 下一条字幕的开始时间 - 当前字幕的开始时间 作为阈值
        threshold = subtitles[i+1]["start_ms"] - start_ms if i + 1 < len(subtitles) else float('inf')
        subtitle_duration = max(1, end_ms - start_ms)  # 毫秒
        audio_duration = max(1, len(seg))  # 毫秒

        # 如果时长差异超过阈值，则用 rate 参数重新生成直到接近匹配（最多尝试若干次）
        if audio_duration > threshold or audio_duration/subtitle_duration > 1.2 or audio_duration/subtitle_duration < 0.8:

            # 计算初始所需速度因子 S = audio_duration / subtitle_duration
            S = audio_duration / subtitle_duration
            # 将因子转为 edge-tts 的 rate 百分比 p
            # S=1.5 -> +50%
            # S=0.8 -> -20%
            p = int(math.ceil((S - 1) * 100))
            # 限制百分比范围，避免不合理数值（可根据需要调整）
            p = max(-50, min(150, p))
            rate_str = f"{p:+d}%"

            while True:
                print(f"   ➤ 尝试通过 edge-tts 调整速率重生成，rate={rate_str}")
                try:
                    mp3_path = generate_audio_for_text(text, i, voice_name, rate_str)
                    seg = AudioSegment.from_file(mp3_path)
                    seg = seg.set_frame_rate(SAMPLE_RATE).set_channels(CHANNELS)
                    audio_duration = max(1, len(seg))
                    if audio_duration <= threshold:
                        break
                    else:
                        new_S = audio_duration / subtitle_duration
                        # 重新计算 rate 百分比，需要在上一轮基础上调整
                        S = new_S * S  # 乘以上一次的 S
                        p = int(math.ceil((S - 1) * 100))
                        p = max(-50, min(150, p))
                        rate_str = f"{p:+d}%"
                except Exception as e:
                    print(f"   ⚠️  重生成失败: {e}, 重试中...")

        # 删除临时 mp3 文件（保守删除，避免残留）
        try:
            os.remove(mp3_path)
        except Exception:
            pass

        if len(seg) < threshold:
            seg += AudioSegment.silent(duration=threshold - len(seg), frame_rate=SAMPLE_RATE)
        else:
            # 这个分支一般不会触发，因为上面已经控制了长度
            seg = seg[:threshold]
        
        # 添加本段并推进当前位置
        merged += seg
        current_position += len(seg)

    return merged

def save_wave(filename, audio: AudioSegment):
    audio.export(filename, format="wav")

def main():
    # srt_file = "1_zh.srt"  # 替换为你的 SRT 文件路径
    # output_file = "1.wav"
    # voice_name = "zh-CN-YunxiaoMultilingualNeural"
    parser = argparse.ArgumentParser(description="根据 SRT 文件生成配音音频")
    parser.add_argument("--srt", required=True, help="输入 SRT 字幕文件路径")
    parser.add_argument("--output_file", required=True, help="输出音频文件路径（wav 格式）")
    parser.add_argument(
        "--voice_name",
        default="zh-CN-YunxiaoMultilingualNeural",
        help="edge-tts 语音名称，默认 zh-CN-YunxiaoMultilingualNeural",
    )
    args = parser.parse_args()

    print(f"📖 解析字幕文件: {args.srt}")
    subtitles = parse_srt(args.srt)
    print(f"✅ 共 {len(subtitles)} 条字幕\n")

    print("🎙️  开始生成并对齐音频...")
    merged_audio = align_and_merge_audio(subtitles, args.voice_name)

    print(f"\n💾 保存音频文件: {args.output_file}")
    save_wave(filename=args.output_file, audio=merged_audio)
    print("✅ 完成！")

if __name__ == "__main__":
    main()