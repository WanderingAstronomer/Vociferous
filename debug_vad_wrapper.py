"""Debug VAD wrapper directly."""

from pathlib import Path
from vociferous.audio.decoder import FfmpegDecoder
from vociferous.audio.vad import VadWrapper

audio_path = Path("samples/ASR_Test.flac")

print("Decoding audio...")
decoder = FfmpegDecoder()
decoded = decoder.decode(str(audio_path))

print(f"Decoded audio: {len(decoded.samples)} bytes, {decoded.sample_rate}Hz, {decoded.channels} channels")
print(f"Duration: {len(decoded.samples) / (decoded.sample_rate * 2):.2f} seconds")

print("\nRunning VadWrapper...")
vad = VadWrapper(sample_rate=decoded.sample_rate)
spans = vad.speech_spans(
    decoded.samples,
    threshold=0.5,
    min_silence_ms=500,
    min_speech_ms=250,
)

print(f"Found {len(spans)} speech spans")
for i, (start, end) in enumerate(spans[:10]):
    start_s = start / decoded.sample_rate
    end_s = end / decoded.sample_rate
    duration = end_s - start_s
    print(f"  {i+1}. {start_s:7.2f}s - {end_s:7.2f}s  (duration: {duration:5.2f}s)")
