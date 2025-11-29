import nemo.collections.asr as nemo_asr
from pathlib import Path
import re
import argparse
import os
from pydub import AudioSegment, silence


def format_time_srt(seconds: float) -> str:
    ms = int((seconds - int(seconds)) * 1000)
    s = int(seconds) % 60
    m = (int(seconds) // 60) % 60
    h = int(seconds) // 3600
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def save_srt(subtitles, output_path):
    with open(output_path, "w", encoding="utf-8") as f:
        for i, sub in enumerate(subtitles, 1):
            f.write(f"{i}\n{sub['start']} --> {sub['end']}\n{sub['text']}\n\n")


def split_by_punctuation_with_word_timestamps(text):
    """
    按句号、问号、感叹号、逗号分句，保留标点
    返回: [(句子文本, 起始词索引, 结束词索引), ...]
    """
    sentences = []
    buf = ""
    idx_map = []  # 记录每个词在 word_times 的索引
    word_idx = 0
    words = text.split()
    for w in words:
        if not w:
            continue
        buf += w + " "
        idx_map.append(word_idx)
        word_idx += 1
        # 以标点结尾则切分
        if re.match(r".*[.,!?，。！？]$", w):
            sentences.append((buf.strip(), idx_map[0], idx_map[-1]))
            buf = ""
            idx_map = []
    if buf:
        sentences.append((buf.strip(), idx_map[0], idx_map[-1]))
    return sentences


def merge_short_sentences(split_sentences, max_words=12):
    """
    合并短句，直到达到 max_words 限制或遇到非逗号结尾的句子
    输入: [(句子文本, 起始词索引, 结束词索引), ...]
    返回: [(合并后句子文本, 起始词索引, 结束词索引), ...]
    """
    comma_punctuations = {",", "，", "、"}
    merged = []
    current = None
    word_count = 0
    for sent, start_idx, end_idx in split_sentences:
        sent_words = sent.split()
        current_words = len(sent_words)
        if not current:
            current = [sent, start_idx, end_idx]
            word_count = current_words
            continue
        prev_text = current[0].strip()
        ends_with_comma = prev_text and prev_text[-1] in comma_punctuations
        if ends_with_comma and word_count + current_words <= max_words:
            current[0] += " " + sent
            current[2] = end_idx
            word_count += current_words
        else:
            merged.append(tuple(current))
            current = [sent, start_idx, end_idx]
            word_count = current_words
    if current:
        merged.append(tuple(current))
    return merged


def ffmpeg_convert(input_audio, output_audio):
    """
    用 ffmpeg 将音频转为单声道 16kHz wav
    """
    temp_dir = Path("./temp")
    temp_dir.mkdir(exist_ok=True)
    output_audio = str(temp_dir / Path(output_audio).name)
    cmd = f"ffmpeg -y -i '{input_audio}' -ac 1 -ar 16000 '{output_audio}'"
    print(f"正在转换音频格式: {cmd}")
    os.system(cmd)
    return output_audio


def split_audio_by_silence(
    input_audio, chunk_length_sec=300, min_silence_len=700, silence_thresh=-40
):
    """
    将长音频按静音片段分段，尽量每段不超过 chunk_length_sec 秒
    返回: [(分段文件路径, 该段在原音频的开始秒数), ...]
    """
    temp_dir = Path("./temp")
    temp_dir.mkdir(exist_ok=True)
    audio = AudioSegment.from_file(input_audio)
    duration = len(audio) / 1000.0

    silence_ranges = silence.detect_silence(
        audio, min_silence_len=min_silence_len, silence_thresh=silence_thresh
    )
    silence_ranges = [
        (start / 1000.0, end / 1000.0) for start, end in silence_ranges
    ]

    segment_points = [0.0]
    target = float(chunk_length_sec)

    while segment_points[-1] + target < duration:
        seg_start = segment_points[-1]
        seg_end = seg_start + target
        # 找到距离 seg_end 最近的静音点（给一点缓冲区）
        candidates = [
            s for s in silence_ranges if seg_start + 60 < s[0] < seg_end + 60
        ]
        if candidates:
            segment_points.append(candidates[0][0])
        else:
            segment_points.append(seg_end)

    segment_points.append(duration)

    chunk_data = []
    for i in range(len(segment_points) - 1):
        chunk_start_sec = segment_points[i]
        chunk_end_sec = segment_points[i + 1]

        chunk_start_ms = int(chunk_start_sec * 1000)
        chunk_end_ms = int(chunk_end_sec * 1000)

        chunk = audio[chunk_start_ms:chunk_end_ms]
        chunk_path = temp_dir / f"{Path(input_audio).stem}_chunk{i}.wav"
        chunk.export(chunk_path, format="wav")

        chunk_data.append((str(chunk_path), chunk_start_sec))

    return chunk_data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="ASR转字幕，自动分句并合并短句"
    )
    parser.add_argument("input_audio", help="输入音频或视频文件路径")
    parser.add_argument("-o", "--output", help="输出SRT文件路径（可选）")
    parser.add_argument(
        "--chunk-minutes",
        type=int,
        default=5,
        help="每个分段的最大时长（分钟），默认5分钟",
    )
    args = parser.parse_args()

    input_audio = args.input_audio
    audio_exts = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg"}
    video_exts = {".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv", ".webm"}
    input_ext = Path(input_audio).suffix.lower()

    temp_dir = Path("./temp")
    temp_dir.mkdir(exist_ok=True)

    if input_ext in audio_exts:
        wav_audio = str(temp_dir / (Path(input_audio).stem + ".mono16k.wav"))
        ffmpeg_convert(input_audio, wav_audio)
    elif input_ext in video_exts:
        wav_audio = str(temp_dir / (Path(input_audio).stem + ".mono16k.wav"))
        cmd = f"ffmpeg -y -i '{input_audio}' -vn -ac 1 -ar 16000 '{wav_audio}'"
        print(f"正在从视频提取音频并转码: {cmd}")
        os.system(cmd)
    else:
        print(f"不支持的文件格式: {input_ext}")
        exit(1)

    # 静音分段
    print(f"正在分段音频: {wav_audio}")
    chunk_data_list = split_audio_by_silence(
        wav_audio, chunk_length_sec=args.chunk_minutes * 60
    )
    print(f"分段完成，共 {len(chunk_data_list)} 段")

    # ASR识别
    print("正在进行语音识别...")
    asr_model = nemo_asr.models.ASRModel.from_pretrained(
        model_name="nvidia/parakeet-tdt-0.6b-v2"
    )

    all_srt_subs = []

    for chunk_path, chunk_start_offset in chunk_data_list:
        print(
            f"正在处理分段: {chunk_path} (开始时间: {chunk_start_offset:.2f}s)"
        )
        output = asr_model.transcribe([chunk_path], timestamps=True)

        if not output or not output[0].timestamp:
            continue

        word_timestamps = output[0].timestamp.get("word", [])
        segment_timestamps = output[0].timestamp.get("segment", [])
        if not segment_timestamps:
            continue

        srt_subs = []

        for seg in segment_timestamps:
            seg_text = seg["segment"]
            seg_start = seg["start"] + chunk_start_offset
            seg_end = seg["end"] + chunk_start_offset

            seg_word_times = [
                w
                for w in word_timestamps
                if w["start"] >= seg["start"] and w["end"] <= seg["end"]
            ]

            # 没有词级时间戳时，整段直接用 segment 时间
            if not seg_word_times:
                srt_subs.append(
                    {
                        "start": format_time_srt(seg_start),
                        "end": format_time_srt(seg_end),
                        "text": seg_text,
                    }
                )
                continue

            split_sentences = split_by_punctuation_with_word_timestamps(
                seg_text
            )

            merged_sentences = merge_short_sentences(
                split_sentences, max_words=12
            )

            for sent, start_idx, end_idx in merged_sentences:
                if start_idx >= len(seg_word_times) or end_idx >= len(
                    seg_word_times
                ):
                    continue

                word_start = (
                    seg_word_times[start_idx]["start"] + chunk_start_offset
                )
                word_end = seg_word_times[end_idx]["end"] + chunk_start_offset

                srt_subs.append(
                    {
                        "start": format_time_srt(word_start),
                        "end": format_time_srt(word_end),
                        "text": sent,
                    }
                )

        all_srt_subs.extend(srt_subs)

    if args.output:
        output_path = args.output
    else:
        output_path = str(Path(input_audio).with_suffix(".srt"))

    save_srt(all_srt_subs, output_path)
    print(f"SRT saved to {output_path}")
