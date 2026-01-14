#!/usr/bin/env python3
"""Quick import test for morphing blob visualizer."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ui.widgets.waveform_visualizer import MorphingBlobVisualizer, WaveformVisualizer

print("✓ Import successful!")
print(f"  - WaveformVisualizer: {WaveformVisualizer.__name__}")
print(f"  - MorphingBlobVisualizer: {MorphingBlobVisualizer.__name__}")
print(f"\nMorphingBlobVisualizer attributes:")
blob = MorphingBlobVisualizer()
print(f"  - Base radius: {blob.base_radius}px")
print(f"  - Number of points: {blob.num_points}")
print(f"  - Number of layers: {blob.num_layers}")
print(f"  - Max deformation: {blob.max_deform}px")
print(f"  - Noise threshold: {blob.noise_threshold}")
