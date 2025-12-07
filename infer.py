from indextts.infer_v2 import IndexTTS2

tts = IndexTTS2(
    cfg_path="checkpoints/config.yaml",
    model_dir="checkpoints",
    use_fp16=False,
    use_cuda_kernel=False,
    use_deepspeed=False,
)
text = "这是一段用于测试的中文文本。我们希望通过这段文本来验证语音合成系统的性能和效果。"
tts.infer(
    spk_audio_prompt="refs/Newsom.wav",
    text=text,
    output_path="gen.wav",
    verbose=True,
)
