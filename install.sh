conda env create -n subs python=3.10
conda activate subs

pip install -r requirements.txt

# nvidia/parakeet-tdt-0.6b-v2
python new_transcribe.py $input_video -o ${input_video%.mp4}.srt 
# new_transcribe.py 运行时自动下载
# Linux/MacOS: ~/.cache/huggingface/hub/models--nvidia--parakeet-tdt-0.6b-v2/
# 2.47 GB

# whisper
whisper 021.mp3 --language Chinese --model turbo --output_format srt
# 模型运行时自动下载
# Linux/MacOS: ~/.cache/whisper/
# 1.51 GB

# ffmpeg
conda install -c conda-forge ffmpeg -y

# demucs
demucs --two-stems=vocals ${input_video%.mp4}.mp3
# demucs xxx.mp3 时自动下载模型
# Linux/MacOS 路径: /home/u-wuhc/.cache/torch/hub/checkpoints/
# 80.2 MB

# voxcpm
pip intall voxcpm
# 第一次运行时会自动下载模型文件，也可以手动下载：
hf download openbmb/VoxCPM1.5
# Linux/MacOS: ~/.cache/huggingface/hub/models--openbmb--VoxCPM1.5/
# 2 GB
