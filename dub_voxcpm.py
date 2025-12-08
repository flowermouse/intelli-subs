import re
import argparse
import numpy as np
from voxcpm import VoxCPM
from pydub import AudioSegment

PROMPT_AUDIO_PATH = "refs/Newsom.wav"
PROMPT_AUDIO_TEXT = "Honestly, a few words about the events of last few days. This past weekend federal agents conducted large scale raids in and around los Angelas, those raids continued as I speak."
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


def generate_audio_for_text(text, model, duration):
    """用 VoxCPM 生成音频，并用 pydub 调整到 duration 长度（全内存，无需保存文件）"""
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
    # numpy -> int16 bytes
    if wav.dtype != np.int16:
        wav_int16 = (wav * 32767).astype(np.int16)
    else:
        wav_int16 = wav
    audio_bytes = wav_int16.tobytes()
    sound = AudioSegment(
        data=audio_bytes, sample_width=2, frame_rate=SAMPLE_RATE, channels=1
    )
    target_len_ms = int(duration)
    orig_len_ms = len(sound)
    playback_speed = orig_len_ms / target_len_ms
    adjusted_sound = sound.speedup(playback_speed=playback_speed)
    return adjusted_sound


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
            continue
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
