import os
import re
import json
import glob
import soundfile as sf
from pydub import AudioSegment
from tqdm import tqdm

DATA = 'data/*.wav'
MIN_DURATION = 0.5  # seconds
MAX_DURATION = 10.0  # seconds
SAMPLE_RATE = 44100  # Hz

def parse_srt(srt_path):
    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    pattern = re.compile(r'(\d+)\s+(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s+([\s\S]*?)(?=\n\d+\n|\Z)', re.MULTILINE)
    segments = []
    for match in pattern.finditer(content):
        idx, start, end, text = match.groups()
        text = text.strip().replace('\n', '')
        segments.append({
            "index": int(idx),
            "start": start.replace(',', '.'),
            "end": end.replace(',', '.'),
            "text": text
        })
    return segments

def time_to_ms(t):
    h, m, s = t.split(':')
    s, ms = s.split('.')
    return (int(h)*3600 + int(m)*60 + int(s)) * 1000 + int(ms)

def main():
    os.makedirs('output', exist_ok=True)
    jsonl_lines = []
    mp3_files = glob.glob(DATA)
    for mp3_path in tqdm(mp3_files, desc="Processing MP3 files"):
        base = os.path.splitext(os.path.basename(mp3_path))[0]
        srt_path = f'data/{base}.srt'
        if not os.path.exists(srt_path):
            print(f"Warning: {srt_path} not found, skip {mp3_path}")
            continue
        audio = AudioSegment.from_file(mp3_path)
        segments = parse_srt(srt_path)
        for seg in segments:
            start_ms = time_to_ms(seg['start'])
            end_ms = time_to_ms(seg['end'])
            audio_chunk = audio[start_ms:end_ms]
            audio_chunk = audio_chunk.set_frame_rate(SAMPLE_RATE).set_channels(1)
            duration = len(audio_chunk) / 1000.0  # 秒
            if duration < MIN_DURATION or duration > MAX_DURATION:
                continue  # 跳过过短或过长的片段
            out_wav = f'output/{base}-{seg["index"]}.wav'
            audio_chunk.export(out_wav, format='wav')
            # double check sample rate
            data, sr = sf.read(out_wav)
            if sr != SAMPLE_RATE:
                sf.write(out_wav, data, SAMPLE_RATE)
            jsonl_lines.append({
                "audio": os.path.basename(out_wav),
                "text": seg["text"],
                "duration": duration
            })
    # 写入 jsonl
    jsonl_lines.sort(key=lambda x: x["audio"])
    with open('output/segments.jsonl', 'w', encoding='utf-8') as f:
        for line in jsonl_lines:
            f.write(json.dumps(line, ensure_ascii=False) + '\n')

if __name__ == "__main__":
    main()