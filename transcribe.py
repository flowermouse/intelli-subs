import subprocess
import torch

def transcribe(file, model, language=None, initial_prompt=None):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")
    cmd = f"whisper --model {model} --language {language} --output_format {output_format} --device {device} --task transcribe --initial_prompt '{initial_prompt}' --verbose True {file}"
    subprocess.run(cmd, shell=True, check=True)

if __name__ == "__main__":
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = input("please input the model name (e.g., tiny, base, small, medium, large, turbo): ")
    language = "en"
    output_format = "srt"
    file = input("please input the audio/video file path: ")
    theme = input("please input the theme of the audio/video: ")
    initial_prompt = f"This is a YouTube video about {theme}."
    cmd = f"whisper --model {model} --language {language} --output_format {output_format} --device {device} --task transcribe --initial_prompt '{initial_prompt}' --verbose True {file}"
    subprocess.run(cmd, shell=True, check=True)