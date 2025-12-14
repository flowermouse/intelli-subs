for f in *.*; do
  [ -f "$f" ] && ext="${f##*.}" && mv "$f" "${f:0:3}.$ext"
done

setopt +o nomatch
for f in *.{mp3,wav,m4a,flac,ogg}; do
  [ -e "$f" ] || continue
  whisper "$f" --language Chinese --model turbo --output_format srt
done

python finetune.py --config_path finetune.yaml

python ft_infer.py --ckpt_dir /home/u-wuhc/intelli-subs/finetune_all/step_0001155 --text "你好，这是一段测试文本。" --output ft_test.wav