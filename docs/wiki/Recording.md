# Recording

Vociferous uses a **press-to-toggle** recording mode with both hotkey and UI button support.

## How It Works

1. **Start** recording via:
   - Press the activation key (default: Right Alt), or
   - Click the **Record** button in the workspace
2. **Speak** into your microphone — a real-time waveform shows your audio
3. **Stop** recording via:
   - Press the activation key again, or
   - Click the **Stop** button

After transcription completes, the text is copied to your clipboard. Paste with Ctrl+V.

## Status Indicators

| State | Workspace Display |
| --- | --- |
| Idle | Greeting message (Good Morning/Afternoon/Evening) |
| Recording | Waveform visualization, "Recording..." status, Stop/Cancel buttons |
| Transcribing | "Transcribing..." status |
| Complete | Transcript with per-transcription metrics |

## Waveform Visualization

During recording, the workspace displays a **real-time waveform** that visualizes your audio input:

- Responsive scaling based on audio levels
- Visual confirmation that audio is being captured
- Clears automatically when recording stops

## Voice Activity Detection

While recording, VAD (Voice Activity Detection) monitors your audio:

- Detects speech vs. silence
- Trims silence from the audio buffer
- Improves transcription quality
- Calculates speech duration for metrics

VAD does **not** automatically stop recording. You must press the activation key or click Stop.

## Cancel Recording

To abort a recording without transcribing:

- Click the **Cancel** button in the workspace
- The status returns to idle

## Recording Controls

The workspace provides three control buttons:

| Button | Action |
| --- | --- |
| **Record** | Start recording (shown when idle) |
| **Stop** | Stop recording and transcribe |
| **Cancel** | Abort recording without transcribing |

## Tips

- **Speak clearly** into a good microphone for best results
- **Short pauses** are fine — VAD handles natural speech patterns
- **Background noise** may affect accuracy; consider a noise-canceling mic
- **Recording length** is limited by available memory, but typical dictations (under 5 minutes) work well
- **Watch the waveform** to confirm your audio is being captured

## Hotkey Configuration

The default activation key is **Right Alt**. To change it:

1. Open **Settings** (gear icon or Edit → Settings)
2. Find **Activation Key**
3. Click the capture field and press your preferred key
4. Settings apply immediately