import re
import os
import subprocess
from pydub import AudioSegment
from time import sleep

SAMPLE_RATE = 24000  # edge-tts 默认输出 24kHz
CHANNELS = 1

def parse_srt(file_path):
    """解析 SRT 文件，返回字幕列表 [{'start_ms': int, 'end_ms': int, 'text': str}, ...]"""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = re.compile(
        r"(\d+)\s+([\d:,]+)\s+-->\s+([\d:,]+)\s+([\s\S]+?)(?=\n\n|\Z)",
        re.MULTILINE,
    )
    subtitles = []

    for match in pattern.finditer(content):
        index = int(match.group(1))
        start = srt_time_to_ms(match.group(2))
        end = srt_time_to_ms(match.group(3))
        text = match.group(4).strip().replace("\n", " ")

        subtitles.append({"index": index, "start_ms": start, "end_ms": end, "text": text})

    return subtitles

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
                print(f"   ⚠️  生成失败: {e}，跳过本条字幕")
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
            p = int(round((S - 1) * 100))
            # 限制百分比范围，避免不合理数值（可根据需要调整）
            p = max(-80, min(300, p))
            rate_str = f"{p:+d}%"

            print(f"   ➤ 尝试通过 edge-tts 调整速率重生成，rate={rate_str}")
            while True:
                try:
                    mp3_path = generate_audio_for_text(text, i, voice_name, rate_str)
                    seg = AudioSegment.from_file(mp3_path)
                    seg = seg.set_frame_rate(SAMPLE_RATE).set_channels(CHANNELS)
                    audio_duration = max(1, len(seg))
                    break
                except Exception as e:
                    print(f"   ⚠️  重生成失败: {e}")
                sleep(1)

        # 删除临时 mp3 文件（保守删除，避免残留）
        try:
            os.remove(mp3_path)
        except Exception:
            pass

        # 确定本段最终目标时长：不超过 threshold，且以字幕时长为主
        desired_len = min(threshold, subtitle_duration)

        # 截断或补静音到 desired_len
        if len(seg) > desired_len:
            seg = seg[:desired_len]
        elif len(seg) < desired_len:
            seg += AudioSegment.silent(duration=desired_len - len(seg), frame_rate=SAMPLE_RATE)

        # 在加入之前，保证 merged 的当前位置对齐到本句 start
        if current_position < start_ms:
            # 在本句开始前插入静音
            pad = start_ms - current_position
            merged += AudioSegment.silent(duration=pad, frame_rate=SAMPLE_RATE)
            current_position = start_ms
        elif current_position > start_ms:
            # 已经超过了本句开始时间，裁掉 seg 开头的重叠部分
            overlap = current_position - start_ms
            if overlap >= len(seg):
                # 本段完全被覆盖，跳过
                continue
            seg = seg[overlap:]
        
        # 添加本段并推进当前位置
        merged += seg
        current_position += len(seg)

    return merged

def save_wave(filename, audio: AudioSegment):
    audio.export(filename, format="wav")

def main():
    srt_file = "1_zh.srt"  # 替换为你的 SRT 文件路径
    output_file = "1.wav"
    voice_name = "zh-CN-YunxiaoMultilingualNeural"

    print(f"📖 解析字幕文件: {srt_file}")
    subtitles = parse_srt(srt_file)
    print(f"✅ 共 {len(subtitles)} 条字幕\n")

    print("🎙️  开始生成并对齐音频...")
    merged_audio = align_and_merge_audio(subtitles, voice_name)

    print(f"\n💾 保存音频文件: {output_file}")
    save_wave(output_file, merged_audio)
    print("✅ 完成！")

if __name__ == "__main__":
    main()