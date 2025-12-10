---
name: "[UPDATE] README.md - Remove streaming interface references"
about: "Fix README.md contradictions with ARCHITECTURE.md regarding batch vs streaming"
title: "[UPDATE] README.md - Remove streaming interface references"
labels: documentation, bug, architecture
assignees: ''
---

## Description

The README.md currently describes engines as "stateful and push-based" with a streaming interface, but ARCHITECTURE.md clearly states Vociferous uses batch processing. This contradiction needs to be fixed.

## Current Problem

**README.md line 27 says:**
```
Engines are stateful and push-based: start() → push_audio() → flush() → poll_segments()
```

**This is wrong because:**
- Vociferous uses batch processing (complete file in, complete result out)
- User submits complete audio files, not continuous streams
- ML models (Canary, Whisper) work best on complete files
- Streaming adds unnecessary complexity for our use case

## Required Changes

### 1. Remove streaming terminology
- Delete references to `start()`, `push_audio()`, `flush()`, `poll_segments()`
- Remove "stateful and push-based" description

### 2. Document batch interface
```markdown
## Engine Interface

Engines use a simple batch interface:

```python
segments = engine.transcribe_file(audio_path)
```

The engine receives a preprocessed audio file (decoded, VAD-filtered, silence removed) 
and returns the complete transcript in one operation.
```

### 3. Clarify preprocessing pipeline
```markdown
## Audio Pipeline

Before transcription, audio is preprocessed in stages:
1. **Decode:** Normalize to PCM mono 16kHz
2. **VAD:** Detect speech boundaries
3. **Condense:** Remove silence
4. **Transcribe:** Engine receives clean, condensed audio

Each stage is batch processing - complete file in, complete file out.
```

### 4. Update engine descriptions
- `whisper_turbo` - Batch processing via CTranslate2
- `voxtral_local` - Batch processing via transformers
- `canary_qwen` - Batch processing with dual-pass (ASR + refinement)

### 5. Add note about why batch
```markdown
**Why Batch Processing?**
- User submits complete audio files (not live streams)
- ML models work best on complete audio
- Simpler architecture (no state management)
- Easier to test and debug
```

## Files to Update

- `README.md` (main file)
- `docs/ENGINE_BATCH_INTERFACE.md` (if it contradicts, update or remove)
- Any other docs that mention streaming

## Success Criteria

- [ ] All streaming interface references removed from README
- [ ] Batch interface documented with code examples
- [ ] Pipeline stages explained (all batch)
- [ ] Rationale for batch processing included
- [ ] Engine descriptions updated to reflect batch processing
- [ ] No contradictions between README and ARCHITECTURE.md

## Related Issues

- Related: #1 (Rewrite ARCHITECTURE.md - batch vs streaming section)
- Related: #21 (Standardize engine interface to batch-only - code changes)

## Notes

This is a **documentation-only** change. The actual code refactoring to remove streaming interfaces is tracked in issue #21.
