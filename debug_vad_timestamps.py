"""Quick VAD timestamp inspection script."""

from pathlib import Path
from vociferous.audio import SileroVAD

vad = SileroVAD()
timestamps = vad.detect_speech(Path("samples/ASR_Test.flac"), save_json=True)

print(f"Total segments: {len(timestamps)}")
print("\nAll timestamps:")
for i, ts in enumerate(timestamps):
    duration = ts['end'] - ts['start']
    print(f"{i+1:3d}. {ts['start']:7.2f}s - {ts['end']:7.2f}s  (duration: {duration:5.2f}s)")
