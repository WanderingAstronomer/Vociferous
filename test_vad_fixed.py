import torchaudio
import torchaudio.functional as F
from silero_vad import load_silero_vad, get_speech_timestamps

# Load audio
wav, sr = torchaudio.load('samples/ASR_Test.flac')
print(f'Original: shape={wav.shape}, sr={sr}')

# Convert stereo to mono by averaging channels
if wav.shape[0] > 1:
    wav = wav.mean(dim=0, keepdim=True)
    print(f'After mono conversion: shape={wav.shape}')

# Resample to 16kHz (required by Silero)
if sr != 16000:
    wav = F.resample(wav, sr, 16000)
    sr = 16000
    print(f'After resampling: shape={wav.shape}, sr={sr}')

# Squeeze to 1D tensor
wav = wav.squeeze(0)
print(f'Final shape: {wav.shape}')

# Load Silero VAD model
print('Loading Silero VAD model...')
model, _ = load_silero_vad()

# Detect speech with loose thresholds
print('Running VAD with threshold=0.1...')
timestamps = get_speech_timestamps(
    wav,
    model,
    threshold=0.1,
    min_silence_duration_ms=300,
    min_speech_duration_ms=100,
    return_seconds=True
)

print(f'\nFound {len(timestamps)} speech segments')
if timestamps:
    print('\nFirst 10 segments:')
    for i, ts in enumerate(timestamps[:10]):
        duration = ts['end'] - ts['start']
        print(f"  {i+1}. {ts['start']:7.2f}s - {ts['end']:7.2f}s (duration: {duration:5.2f}s)")
else:
    print('NO SPEECH DETECTED - Audio may be silent or corrupted')
