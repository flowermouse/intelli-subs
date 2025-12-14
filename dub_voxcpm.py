import re
import os
import argparse
import subprocess
import numpy as np
import soundfile as sf
from voxcpm import VoxCPM
from pydub import AudioSegment

PROMPT_AUDIO_PATH = "refs/sf.wav"
PROMPT_AUDIO_TEXT = "那些有头有脸的焦俊居民完全不讲逻辑，把家门口当作拼死一搏的阵地，与他们陈腐乏味，死气沉沉的生活相对抗。为了得到免费的披萨，他们对别人撒谎，同时也自欺欺人，编造打电话订外卖的时间。"
SAMPLE_RATE = 44100


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
            current["text"] = (
                current["text"].rstrip() + " " + sub["text"].lstrip()
            )
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


def ffmpeg_time_stretch(wav: np.ndarray, speed: float) -> AudioSegment:
    """使用 ffmpeg atempo 做高质量变速不变调"""
    import tempfile

    # 写入临时 wav
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f_in, \
         tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f_out:
        sf.write(f_in.name, wav, SAMPLE_RATE)

        # atempo 变速；>2 或 <0.5 时可以先截断在这个范围
        speed = max(0.5, min(2.0, float(speed)))
        cmd = [
            "ffmpeg",
            "-y",
            "-loglevel", "error",
            "-i", f_in.name,
            "-filter:a", f"atempo={speed}",
            f_out.name,
        ]
        subprocess.run(cmd, check=True)

        seg = AudioSegment.from_wav(f_out.name)

    os.remove(f_in.name)
    os.remove(f_out.name)
    return seg


def generate_audio_for_text(text, model, duration):
    """用 VoxCPM 生成音频，并用 ffmpeg atempo 调整到 duration 长度"""
    wav = model.generate(
        text=text,
        prompt_wav_path=PROMPT_AUDIO_PATH,
        prompt_text=PROMPT_AUDIO_TEXT,
        cfg_value=2.0,
        inference_timesteps=10,
        normalize=False,
        denoise=False,
        retry_badcase=True,
        retry_badcase_max_times=3,
        retry_badcase_ratio_threshold=6.0,
    )

    # VoxCPM 一般输出 float [-1, 1]，确保是 float32
    wav = wav.astype(np.float32, copy=False)

    # 原始/目标时长（毫秒）
    orig_len_ms = len(wav) / SAMPLE_RATE * 1000.0
    target_len_ms = max(1, int(duration))

    # 需要的变速倍数：>1 加速，<1 减速
    speed = orig_len_ms / target_len_ms

    # 用 ffmpeg atempo 做高质量 time-stretch
    seg = ffmpeg_time_stretch(wav, speed)

    # 再精确裁剪/补静音到目标长度，避免累计误差
    if len(seg) < target_len_ms:
        seg += AudioSegment.silent(
            duration=target_len_ms - len(seg),
            frame_rate=SAMPLE_RATE,
        )
    else:
        seg = seg[:target_len_ms]

    return seg


def align_and_merge_audio(subtitles, model):
    merged = AudioSegment.silent(duration=0, frame_rate=SAMPLE_RATE)
    for i, sub in enumerate(subtitles):
        start_ms = sub["start_ms"]
        end_ms = sub["end_ms"]
        text = sub["text"]
        print(
            f"[{i+1}/{len(subtitles)}] 生成音频: {text[:30]}... ({start_ms}ms -> {end_ms}ms)"
        )
        subtitle_duration = end_ms - start_ms
        threshold = (
            subtitles[i + 1]["start_ms"] - start_ms
            if i + 1 < len(subtitles)
            else float("inf")
        )
        seg = generate_audio_for_text(text, model, subtitle_duration)
        if threshold == float("inf"):
            merged += seg
            break
        if len(seg) >= threshold:
            seg = seg[:threshold]
        else:
            silence_duration = threshold - len(seg)
            seg += AudioSegment.silent(
                duration=silence_duration, frame_rate=SAMPLE_RATE
            )
        merged += seg
    return merged


def main():
    parser = argparse.ArgumentParser(description="根据 SRT 文件生成配音音频")
    parser.add_argument("--srt", required=True, help="输入 SRT 字幕文件路径")
    parser.add_argument(
        "--output_file", required=True, help="输出音频文件路径（wav 格式）"
    )
    args = parser.parse_args()

    model = VoxCPM.from_pretrained("openbmb/VoxCPM1.5")

    print(f"📖 解析字幕文件: {args.srt}")
    subtitles = parse_srt(args.srt)
    print(f"✅ 共 {len(subtitles)} 条字幕\n")

    print("🎙️  开始生成并对齐音频...")
    merged_audio = align_and_merge_audio(subtitles, model)

    print(f"\n💾 保存音频文件: {args.output_file}")
    merged_audio.export(args.output_file, format="wav")
    print("✅ 完成！")


if __name__ == "__main__":
    main()
