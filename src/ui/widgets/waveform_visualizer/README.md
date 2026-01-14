# Morphing Blob Visualizer

## Overview

The `MorphingBlobVisualizer` is an organic, liquid-like audio visualizer that creates mesmerizing blob animations in response to voice input. It features multiple translucent layers with smooth deformations and gradient colors.

## Features

- **Organic Movement**: Smooth, flowing animations with natural-looking deformations
- **Multi-Layer Depth**: Three overlapping blob layers create a sense of depth
- **Audio Responsive**: Deforms and pulses based on audio amplitude
- **Idle Animation**: Gentle, calming movement when no audio is present
- **Performance Optimized**: 60 FPS rendering with efficient painting
- **Color Integration**: Uses Vociferous color palette (PRIMARY and PRIMARY_HOVER)

## Usage

### Basic Integration

```python
from ui.widgets.waveform_visualizer import MorphingBlobVisualizer

# Create the visualizer
visualizer = MorphingBlobVisualizer(parent=some_widget)

# Start animation
visualizer.start()

# Feed audio levels (0.0 to 1.0)
visualizer.add_level(amplitude)

# Stop animation
visualizer.stop()

# Clean up
visualizer.cleanup()
```

### Demo

Run the interactive demo to see it in action:

```bash
python scripts/demo_morphing_blob.py
```

The demo includes:
- Manual amplitude control via slider
- Start/Stop controls
- Auto Pulse mode (simulates organic speech patterns)

## Configuration

The visualizer can be customized by modifying these attributes after instantiation:

```python
visualizer = MorphingBlobVisualizer()

# Blob shape complexity (default: 12)
visualizer.num_points = 16

# Base size in pixels (default: 60)
visualizer.base_radius = 80

# Maximum deformation amplitude (default: 25)
visualizer.max_deform = 30

# Noise gate threshold 0.0-1.0 (default: 0.08)
visualizer.noise_threshold = 0.10

# Number of layers for depth (default: 3)
visualizer.num_layers = 4

# Animation speed (default: 16ms = ~60 FPS)
visualizer.timer.setInterval(33)  # 30 FPS
```

## Technical Details

### Animation System

- **Frame Rate**: 60 FPS (16ms interval)
- **Interpolation**: Smooth exponential decay (`lerp` factor: 0.2)
- **Time Accumulation**: Continuous time value for organic sine wave generation
- **Decay Rate**: 0.92 (natural falloff when silent)

### Rendering

- **Drawing**: Custom `QPainterPath` with quadratic Bezier curves
- **Gradients**: Radial gradients per layer for depth effect
- **Antialiasing**: Enabled for smooth edges
- **Transparency**: Alpha blending for layer composition
- **Glow Effect**: Additional radial gradient when amplitude > 0.3

### Layer System

Each layer has:
- Unique phase offset for variety
- Scale reduction (back layers smaller)
- Opacity gradient (back layers more transparent)
- Independent deformation states

### Mathematical Model

```python
# Per-point deformation calculation
angle = (point_index / num_points) * 2π
idle_wave = sin(time * 1.5 + angle * 2 + phase) * 0.15
voice_wave = sin(time * 3 + angle * 3 + phase) * current_level
deformation = (idle_wave + voice_wave) * max_deform
```

## Design Principles

1. **Intent-Driven**: Follows Vociferous architecture patterns
2. **Resource Management**: Proper cleanup and timer management
3. **Type Safety**: Full type hints with PyQt6 stubs
4. **Performance**: Fixed size, optimized painting, minimal allocations
5. **Accessibility**: Transparent background, works on dark themes

## Comparison with WaveformVisualizer

| Feature | WaveformVisualizer | MorphingBlobVisualizer |
|---------|-------------------|------------------------|
| Style | Linear bars | Organic blob |
| Layout | Horizontal scroll | Centered circle |
| Size | Expanding width | Fixed square |
| Layers | Single | Multiple (3) |
| Animation | 30 FPS | 60 FPS |
| Use Case | Recording timeline | Voice presence |

## Integration Notes

### Size Requirements

- **Fixed Size**: 200×200 pixels
- **Minimum Size**: 150×150 pixels
- **Aspect Ratio**: Square (1:1)
- **Size Policy**: Fixed

### Lifecycle

```python
def setup_visualizer(self):
    self.blob = MorphingBlobVisualizer()
    self.layout.addWidget(self.blob)
    
def begin_recording(self):
    self.blob.start()
    
def handle_audio_chunk(self, amplitude: float):
    self.blob.add_level(amplitude)
    
def stop_recording(self):
    self.blob.stop()
    
def cleanup(self):
    self.blob.cleanup()
```

### Thread Safety

The visualizer is **not thread-safe**. Always call methods from the Qt main thread:

```python
# In background thread - DON'T do this:
self.blob.add_level(amplitude)  # WRONG

# Instead, use signals:
audio_level_signal.emit(amplitude)  # CORRECT

# In main thread slot:
@pyqtSlot(float)
def on_audio_level(self, amplitude: float):
    self.blob.add_level(amplitude)  # CORRECT
```

## Future Enhancements

Potential improvements:
- Color customization API
- Configurable noise gate
- Beat detection integration
- Frequency-based deformation
- Export as animated GIF/video
- Accessibility settings (reduced motion)

## See Also

- [waveform_visualizer.py](waveform_visualizer.py) - Horizontal bar visualizer
- [UI Architecture](../../../docs/wiki/UI-Architecture.md) - Vociferous UI patterns
- [Backend Architecture](../../../docs/wiki/Backend-Architecture.md) - Audio pipeline
