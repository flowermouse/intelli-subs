# 只保留文件名前三位字符，重命名文件
for f in *.*; do
  [ -f "$f" ] && ext="${f##*.}" && mv "$f" "${f:0:3}.$ext"
done

# 使用 demucs 进行音频分离 vocals
for f in *.mp3; do
  [ -e "$f" ] || continue
  demucs --device cuda --two-stems=vocals "$f"
done

# 移动分离出来的 vocals 文件到当前目录并重命名为原文件名 (*)
for d in separated/htdemucs/*/vocals.wav; do
  base=$(basename "$(dirname "$d")")
  cp "$d" "${base}.wav"
done

# 使用 Whisper 进行音频转录
setopt +o nomatch
for f in *.wav; do
  [ -e "$f" ] || continue
  whisper "$f" --language Chinese --model turbo --output_format srt
done

cd ..

# 切分音频文件
python process.py

# 保存数据集
zip -r data.zip output

# jsonl 文件加上路径
python tmp.py

python finetune.py --config_path finetune.yaml

python ft_infer.py --ckpt_dir ./finetune/step_0002000 --text "直到现在，国内的体育圈——注意，我说的是体育圈，仍然处在封建主义阶段。" --output ft_test.wav