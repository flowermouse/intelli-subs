import re
import librosa
import argparse
import numpy as np
import soundfile as sf
from voxcpm import VoxCPM

PROMPT_AUDIO_PATH = "refs/Newsom.wav"
PROMPT_AUDIO_TEXT = "Honestly, a few words about the events of last few days. This past weekend federal agents conducted large scale raids in and around los Angelas, those raids continued as I speak. California is no stranger to immigration."
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

def generate_audio_for_text(text, model, duration):
    """用 VoxCPM 生成音频，并用 librosa 调整到 duration 长度"""
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
    target_len = int(duration / 1000 * SAMPLE_RATE)  # 目标采样点数
    ratio = len(wav) / target_len
    adjusted_wav = librosa.effects.time_stretch(wav, rate=ratio) # rate > 1.0 -> 加速，< 1.0 -> 减速
    return adjusted_wav

def align_and_merge_audio(subtitles, model):
    segments = []
    for i, sub in enumerate(subtitles):
        start_ms = sub["start_ms"]
        end_ms = sub["end_ms"]
        text = sub["text"]
        print(f"[{i+1}/{len(subtitles)}] 生成音频: {text[:30]}... ({start_ms}ms -> {end_ms}ms)")
        subtitle_duration = max(1, end_ms - start_ms)
        seg = generate_audio_for_text(text, model, subtitle_duration)
        # 补齐长度
        target_len = int(subtitle_duration / 1000 * SAMPLE_RATE)
        if len(seg) < target_len:
            seg = np.pad(seg, (0, target_len - len(seg)), mode="constant")
        else:
            seg = seg[:target_len]
        segments.append(seg)
    merged = np.concatenate(segments)
    return merged

def save_wave(filename, audio: np.ndarray):
    sf.write(filename, audio, SAMPLE_RATE)

def main():
    parser = argparse.ArgumentParser(description="根据 SRT 文件生成配音音频")
    parser.add_argument("--srt", required=True, help="输入 SRT 字幕文件路径")
    parser.add_argument("--output_file", required=True, help="输出音频文件路径（wav 格式）")
    args = parser.parse_args()

    model = VoxCPM.from_pretrained("openbmb/VoxCPM1.5")

    print(f"📖 解析字幕文件: {args.srt}")
    subtitles = parse_srt(args.srt)
    print(f"✅ 共 {len(subtitles)} 条字幕\n")

    print("🎙️  开始生成并对齐音频...")
    merged_audio = align_and_merge_audio(subtitles, model)

    print(f"\n💾 保存音频文件: {args.output_file}")
    save_wave(filename=args.output_file, audio=merged_audio)
    print("✅ 完成！")

if __name__ == "__main__":
    main()