# transcibe

input_video="3.mp4"

python new_transcribe.py $input_video -o ${input_video%.mp4}.srt 

# translate
python translator.py ${input_video%.mp4}.srt --agent gemini -o ${input_video%.mp4}_zh.srt

# dubbing
python dub.py --srt ${input_video%.mp4}_zh.srt --output_file ${input_video%.mp4}.wav

# 分离背景音
ffmpeg -i $input_video -map 0:a:0 ${input_video%.mp4}.mp3
demucs -d cpu --two-stems=vocals ${input_video%.mp4}.mp3

ffmpeg -i separated/htdemucs/${input_video%.mp4}/no_vocals.wav -i ${input_video%.mp4}.wav \
  -filter_complex amix=inputs=2:normalize=1 \
  -c:a aac -b:a 192k out_mix.m4a

ffmpeg -i $input_video -i out_mix.m4a \
  -c:v copy -c:a copy \
  -map 0:v:0 -map 1:a:0 \
  ${input_video%.mp4}_dubbed.mp4

# cleanup
rm ${input_video%.mp4}.wav
rm ${input_video%.mp4}.mp3
rm out_mix.m4a
rm -r separated
rm -r temp

# final output
# ${input_video%.mp4}.srt
# ${input_video%.mp4}_zh.srt
# ${input_video%.mp4}_dubbed.mp4
