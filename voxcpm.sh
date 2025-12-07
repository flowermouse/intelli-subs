pip install voxcpm

# 第一次运行时会自动下载模型文件，也可以手动下载：
hf download openbmb/VoxCPM-0.5B

# cli
voxcpm --text "VoxCPM is an innovative end-to-end TTS model from ModelBest, designed to generate highly expressive speech." --output out.wav


pip install f5-tts

f5-tts_infer-cli --model F5TTS_v1_Base \
--ref_audio "Newsom.wav" \
--ref_text "Honestly, a few words about the events of last few days. This past weekend federal agents conducted large scale raids in and around los Angelas, those raids continued as I speak. California is no stranger to immigration." \
--gen_text "这是一段用于测试的中文文本。F5-TTS支持多种语言的文本到语音合成，包括但不限于英语、中文、西班牙语等。"

