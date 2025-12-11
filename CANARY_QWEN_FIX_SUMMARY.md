# Canary-Qwen Engine Fix Summary

## Problem
The Canary-Qwen engine was incorrectly using the Transformers library to load `nvidia/canary-qwen-2.5b`, which is actually a **NeMo model** (not a Transformers model).

**Error symptoms:**
```
Engine initialization error: Failed to load Canary-Qwen model: Can't load feature extractor for 'nvidia/canary-qwen-2.5b'
```

**Root cause:**
- Model repo contains only: `config.json`, `model.safetensors` (no `preprocessor_config.json`)
- Model README specifies: `library_name: nemo`
- Code was attempting: `AutoProcessor.from_pretrained()` + `AutoModelForSpeechSeq2Seq.from_pretrained()`
- NeMo models require: `nemo.collections.asr.models.ASRModel.from_pretrained()`

## Changes Made

### 1. `vociferous/engines/canary_qwen.py`

#### Changed imports:
```python
# OLD (wrong):
from transformers import AutoProcessor, AutoModelForSpeechSeq2Seq

# NEW (correct):
from nemo.collections.asr.models import ASRModel
```

#### Changed `_lazy_model()`:
```python
# OLD (wrong):
self._processor = AutoProcessor.from_pretrained(...)
self._model = AutoModelForSpeechSeq2Seq.from_pretrained(...)

# NEW (correct):
self._model = ASRModel.from_pretrained(model_name="nvidia/canary-qwen-2.5b")
```

#### Changed `_transcribe_bytes()`:
```python
# OLD (wrong):
inputs = self._processor(array, sampling_rate=16000, return_tensors="pt")
generated_ids = self._model.generate(**inputs, max_length=256)
transcription = self._processor.batch_decode(generated_ids, skip_special_tokens=True)

# NEW (correct):
transcriptions = self._model.transcribe([samples], batch_size=1)
return transcriptions[0] if transcriptions else ""
```

**Key differences:**
- NeMo models don't use separate processor/feature extractor
- NeMo `transcribe()` accepts list of numpy arrays directly
- No need for torch tensors or manual device placement
- Returns list of strings (one per audio input)

### 2. `vociferous/cli/commands/deps.py`

#### Changed `_get_engine_requirements()`:
```python
# OLD (wrong):
if engine == "canary_qwen":
    packages = ["transformers>=4.38.0", "torch>=2.0.0", "accelerate>=0.28.0"]

# NEW (correct):
if engine == "canary_qwen":
    packages = ["nemo_toolkit[asr]>=2.0.0"]
```

**Note:** `nemo_toolkit[asr]` includes all necessary dependencies (torch, etc.)

## Installation

To use Canary-Qwen, install NeMo toolkit:
```bash
pip install nemo_toolkit[asr]
```

## Verification Status

- ✅ Code rewritten to use NeMo API
- ✅ Dependencies updated in `deps.py`
- ⏳ Testing pending (requires `nemo_toolkit[asr]` installation)

## Next Steps

1. Install NeMo: `pip install nemo_toolkit[asr]`
2. Test transcription: `vociferous transcribe samples/ASR_Test.wav --engine canary_qwen`
3. Verify model downloads correctly
4. Update check command if NeMo uses different cache structure

## References

- NeMo Toolkit: https://github.com/NVIDIA/NeMo
- Canary Model: https://huggingface.co/nvidia/canary-qwen-2.5b
- NeMo ASR Docs: https://docs.nvidia.com/nemo-framework/user-guide/latest/nemotoolkit/asr/intro.html
