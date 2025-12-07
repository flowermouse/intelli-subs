import re
import os
import librosa
import argparse
import numpy as np
import soundfile as sf
from indextts.infer_v2 import IndexTTS2

PROMPT_AUDIO_PATH = "refs/Newsom.wav"
SAMPLE_RATE = 22050

def parse_srt(file_path, merge_gap_ms=300):
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
    merged = []
    current = raw_subtitles[0].copy()
    for sub in raw_subtitles[1:]:
        gap = sub["start_ms"] - current["end_ms"]
        if gap <= merge_gap_ms:
            current["end_ms"] = max(current["end_ms"], sub["end_ms"])
            current["text"] = current["text"].rstrip() + " " + sub["text"].lstrip()
        else:
            merged.append(current)
            current = sub.copy()
    merged.append(current)
    for i, sub in enumerate(merged, start=1):
        sub["index"] = i
    return merged

def srt_time_to_ms(time_str):
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
    # 用 IndexTTS2 生成音频
    wav_path = f"tmp_{np.random.randint(1e9)}.wav"
    model.infer(
        spk_audio_prompt=PROMPT_AUDIO_PATH,
        text=text,
        output_path=wav_path,
        verbose=False,
    )
    wav, sr = librosa.load(wav_path, sr=SAMPLE_RATE)
    target_len = int(duration / 1000 * SAMPLE_RATE)
    ratio = len(wav) / target_len
    adjusted_wav = librosa.effects.time_stretch(wav, rate=ratio)
    # 删除临时文件
    os.remove(wav_path)
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
    parser = argparse.ArgumentParser(description="根据 SRT 文件生成配音音频（IndexTTS2）")
    parser.add_argument("--srt", required=True, help="输入 SRT 字幕文件路径")
    parser.add_argument("--output_file", required=True, help="输出音频文件路径（wav 格式）")
    parser.add_argument("--config", default="checkpoints/config.yaml", help="IndexTTS2 配置文件路径")
    parser.add_argument("--model_dir", default="checkpoints", help="IndexTTS2 模型目录")
    args = parser.parse_args()

    model = IndexTTS2(
        cfg_path=args.config,
        model_dir=args.model_dir,
        use_fp16=False,
        use_cuda_kernel=False,
        use_deepspeed=False,
    )

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