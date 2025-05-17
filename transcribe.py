import torch
import whisper
import re

def words_to_srt(segments):
    lines = []
    idx = 1
    buffer = []
    buffer_times = []
    long_idx = []

    for seg in segments:
        words = seg.get("words", [])
        # print(words)
        for w in words:
            buffer.append(w["word"])
            buffer_times.append((w["start"], w["end"]))
            # 如果遇到句号、问号、感叹号等标点，或者buffer太长，则分句
            if w["word"].strip()[-1] in {'.', '?', '!', ';', '。', '？', '！', '；'}:
                start = buffer_times[0][0]
                end = buffer_times[-1][1]
                text = "".join(buffer).strip()
                if (len(text.split()) >= 18):
                    long_idx.append(idx)
                lines.append(f"{idx}\n{format_time_srt(start)} --> {format_time_srt(end)}\n{text}\n")
                idx += 1
                buffer = []
                buffer_times = []
            if len(buffer) >= 15:
                start = buffer_times[0][0]
                for i in range(len(buffer)):
                    if i >= 2 and buffer[i].strip()[-1] in {',', '，', ':', '：'}:
                        end = buffer_times[i][1]
                        text = "".join(buffer[:i+1]).strip()
                        if (len(text.split()) >= 18):
                            long_idx.append(idx)
                        lines.append(f"{idx}\n{format_time_srt(start)} --> {format_time_srt(end)}\n{text}\n")
                        idx += 1
                        buffer = buffer[i+1:]
                        buffer_times = buffer_times[i+1:]
                        break

    # 处理最后一段
    if buffer:
        start = buffer_times[0][0]
        end = buffer_times[-1][1]
        text = "".join(buffer).strip()
        lines.append(f"{idx}\n{format_time_srt(start)} --> {format_time_srt(end)}\n{text}\n")
    print("长句索引:", long_idx)
    return "\n".join(lines)

def format_time_srt(seconds):
    ms = int((seconds - int(seconds)) * 1000)
    s = int(seconds) % 60
    m = (int(seconds) // 60) % 60
    h = int(seconds) // 3600
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def segments_to_srt(segments):
    lines = []
    for i, seg in enumerate(segments, 1):
        start = format_time_srt(seg['start'])
        end = format_time_srt(seg['end'])
        text = seg['text'].strip()
        lines.append(f"{i}\n{start} --> {end}\n{text}\n")
    return "\n".join(lines)

def transcribe(file, model, language=None, initial_prompt=None):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")
    model = whisper.load_model(model, device=device)
    options = {
        "language": language,
        "initial_prompt": initial_prompt,
        "word_timestamps": True,
        "task": "transcribe",
        "verbose": True
    }
    result = model.transcribe(file, **options)
    srt_file = file.rsplit(".", 1)[0] + ".srt"
    with open(srt_file, "w", encoding="utf-8") as f:
        f.write(words_to_srt(result["segments"]))
    print(f"转录字幕文件已保存到： {srt_file}")

if __name__ == "__main__":
    device = "cuda" if torch.cuda.is_available() else "cpu"
    # model = input("please input the model name (e.g., tiny, base, small, medium, large, turbo): ")
    model = "turbo"
    language = "en"
    output_format = "srt"
    # file = input("please input the audio/video file path: ")
    file = "Luthen.webm"
    # theme = input("please input the theme of the audio/video: ")
    theme = "star wars"
    initial_prompt = f"This is a YouTube video about {theme}."
    transcribe(file, model, language, initial_prompt)