from silero_vad import load_silero_vad, read_audio, get_speech_timestamps

model, _ = load_silero_vad()
wav = read_audio('samples/ASR_Test.flac')

print(f'Audio shape: {wav.shape}, dtype: {wav.dtype}')
print(f'Audio stats: min={wav.min():.4f}, max={wav.max():.4f}, mean={wav.abs().mean():.4f}')

# Try very loose thresholds
timestamps = get_speech_timestamps(
    wav, 
    model, 
    threshold=0.1,
    min_silence_duration_ms=300,
    min_speech_duration_ms=100,
    return_seconds=True
)

print(f'Segments with threshold=0.1: {len(timestamps)}')
if timestamps:
    print('First 5 segments:')
    for i, ts in enumerate(timestamps[:5]):
        print(f"  {i+1}. {ts['start']:.2f}s - {ts['end']:.2f}s")
