# import librosa
# import soundfile as sf

# input_file = 'tmp_966207990.wav'
# y, sr = librosa.load(input_file, sr=None)
# print(f'Sample Rate: {sr}')
# y_adjusted = librosa.effects.time_stretch(y, rate=1.25)
# output_file = 'adjusted_tmp.wav'
# sf.write(output_file, y_adjusted, sr)
# print(f'Adjusted audio saved to {output_file}')

from pydub import AudioSegment
sound = AudioSegment.from_wav("tmp_966207990.wav")
sound = sound.speedup(playback_speed=1.25)
sound.export("adjusted_tmp.wav", format="wav")