# Engine Batch Interface Usage Guide

## Overview

The refactored engine architecture provides a new batch processing interface that's simpler and eliminates the overlapping segments issue. This guide shows how to use it.

## New Batch Interface

Both `WhisperTurboEngine` and `VoxtralLocalEngine` now have a `transcribe_file()` method:

```python
def transcribe_file(
    self, 
    audio_path: Path, 
    options: TranscriptionOptions
) -> list[TranscriptSegment]:
    """Transcribe entire audio file in one batch operation."""
```

## Example: Direct Engine Usage (Batch Only)

```python
from pathlib import Path
from vociferous.engines import WhisperTurboEngine
from vociferous.domain.model import EngineConfig, TranscriptionOptions

# 1. Configure engine
config = EngineConfig(
    model_name="tiny",
    device="cpu",
    compute_type="int8",
)

# 2. Create engine
engine = WhisperTurboEngine(config)

# 3. Set transcription options
options = TranscriptionOptions(
    language="en",
    beam_size=1,
)

# 4. Transcribe preprocessed audio file
# Note: Audio should already be decoded and condensed (16kHz mono PCM WAV)
audio_path = Path("samples/ASR_Test_30s_condensed.wav")
segments = engine.transcribe_file(audio_path, options)

# 5. Output results (engine should already emit clean, non-overlapping segments)
for seg in segments:
    print(f"{seg.start_s:.2f}-{seg.end_s:.2f}: {seg.text}")
```

## Key Improvements

### Before Refactoring
- ❌ Internal VAD in engine duplicated preprocessing VAD
- ❌ Sliding window overlap caused duplicate segments
- ❌ Complex streaming state
- ❌ Output: `36.48-38.40: 14, 15, 16, 16, 16, 16, 16...` (repeating)

### After Refactoring
- ✅ Single VAD pass in preprocessing
- ✅ No sliding window overlap
- ✅ Simple batch processing (`transcribe_file()` only)
- ✅ Engines emit clean segments directly (no arbiter step)

## Streaming Interface Status

The streaming interface (`start()`, `push_audio()`, `flush()`, `poll_segments()`) has been removed from the supported API. Engines are batch-only: provide a preprocessed file path and receive the complete set of segments in one call. Do not reintroduce streaming abstractions.

## Benefits

1. **No Duplicate Segments**: Preprocessing + batch engines produce clean, non-overlapping output
2. **Clean Boundaries**: Respect natural breaks without post-processing arbiters
3. **Simpler Code**: Direct file processing, no streaming state
4. **Better Performance**: Single pass through audio
5. **Easier Testing**: Deterministic input/output with real files
