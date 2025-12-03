pip install voxcpm

# 第一次运行时会自动下载模型文件，也可以手动下载：
hf download openbmb/VoxCPM-0.5B

# cli
voxcpm --text "VoxCPM is an innovative end-to-end TTS model from ModelBest, designed to generate highly expressive speech." --output out.wav

