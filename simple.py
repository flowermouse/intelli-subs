import ChatTTS
import torch
import torchaudio

chat = ChatTTS.Chat()
chat.load(compile=False) # Set to True for better performance

texts = ["先说明，高区论文难度在那，我能在一年内发3篇，运气成分很大。当然，也是掌握了一些些小秘诀。这些技巧不是我自己摸索的，都是我的论文老师教的。"]

wavs = chat.infer(texts)

torchaudio.save("output1.wav", torch.from_numpy(wavs[0]), 24000)