"""Debug script to test audio processing pipeline and save output."""

from pathlib import Path
from vociferous.audio import SileroVAD, FFmpegCondenser

# Input file
input_file = Path("samples/ASR_Test.flac")

# Step 1: Run Silero VAD
print("Running Silero VAD...")
vad = SileroVAD()
timestamps = vad.detect_speech(
    input_file,
    save_json=True  # Save timestamps for inspection
)

print(f"Found {len(timestamps)} speech segments")
total_speech = sum(ts['end'] - ts['start'] for ts in timestamps)
print(f"Total speech duration: {total_speech:.2f} seconds")

# Print first few timestamps
print("\nFirst 5 timestamps:")
for i, ts in enumerate(timestamps[:5]):
    print(f"  {i+1}. {ts['start']:.2f}s - {ts['end']:.2f}s ({ts['end']-ts['start']:.2f}s)")

# Step 2: Run Condenser
print("\nRunning FFmpeg Condenser...")
condenser = FFmpegCondenser()
output_files = condenser.condense(
    input_file,
    timestamps,
    output_dir=Path("./debug_output"),
    max_duration_minutes=30,
    min_gap_for_split_s=5.0,
    boundary_margin_s=1.0
)

print(f"\nGenerated {len(output_files)} output file(s):")
for f in output_files:
    print(f"  - {f}")
    print(f"    Size: {f.stat().st_size / 1024:.2f} KB")

print("\n✅ Done! Check the debug_output/ directory and LISTEN to the audio files.")
print("   If the audio sounds chopped up or weird, the problem is in audio processing.")
print("   If the audio sounds fine, the problem is in the transcription engine.")
