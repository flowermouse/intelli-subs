import os
import re
import json
import glob
import soundfile as sf
from pydub import AudioSegment

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
    mp3_files = glob.glob('data/*.mp3')
    for mp3_path in mp3_files:
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
            audio_chunk = audio_chunk.set_frame_rate(44100)
            duration = len(audio_chunk) / 1000.0  # 秒
            if duration < 0.5:
                continue  # 跳过过短片段
            out_wav = f'output/{base}-{seg["index"]}.wav'
            audio_chunk.export(out_wav, format='wav')
            # double check sample rate
            data, sr = sf.read(out_wav)
            if sr != 44100:
                sf.write(out_wav, data, 44100)
            jsonl_lines.append({
                "audio": os.path.basename(out_wav),
                "text": seg["text"],
                "duration": duration
            })
    # 写入 jsonl
    with open('output/segments.jsonl', 'w', encoding='utf-8') as f:
        for line in jsonl_lines:
            f.write(json.dumps(line, ensure_ascii=False) + '\n')

if __name__ == "__main__":
    main()