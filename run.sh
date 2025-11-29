# edge-tts
edge-tts --voice zh-CN-YunyangNeural --rate=-25% --text '你好，世界' --write-media hello.mp3

# 分离背景音
demucs -d cpu --two-stems=vocals 1.mp3

ffmpeg -i bg.wav -i voice.wav \
  -filter_complex amix=inputs=2:normalize=1 \
  -c:a aac -b:a 192k out_mix.m4a

ffmpeg -i input.mp4 -i out_mix.m4a \
  -c:v copy -c:a copy \
  -map 0:v:0 -map 1:a:0 \
  output_with_new_audio.mp4