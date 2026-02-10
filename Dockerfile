# Vociferous - Dockerfile
# PyQt6 GUI app with audio capture, optional NVIDIA GPU acceleration
#
# Build:
#   docker compose build
#
# Run:
#   docker compose up

FROM --platform=linux/amd64 python:3.12-slim-bookworm AS base

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# ---------- System dependencies ----------
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Audio (sounddevice / PortAudio / ALSA / PulseAudio client)
    libportaudio2 \
    libsndfile1 \
    libasound2 \
    pulseaudio-utils \
    # Qt6 / OpenGL
    libegl1 \
    libgl1 \
    libglib2.0-0 \
    libfontconfig1 \
    libdbus-1-3 \
    libxkbcommon0 \
    # X11 / XCB (Qt xcb platform plugin)
    libxcb1 \
    libxcb-cursor0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-shape0 \
    libxcb-xfixes0 \
    libxcb-xinerama0 \
    libxcb-xkb1 \
    libxkbcommon-x11-0 \
    libx11-xcb1 \
    # Wayland
    libwayland-client0 \
    libwayland-cursor0 \
    libwayland-egl1 \
    # Input (evdev / pynput)
    libinput10 \
    libevdev2 \
    # Misc runtime
    libffi8 \
    && rm -rf /var/lib/apt/lists/*

# ---------- Application setup ----------
WORKDIR /app

# Install Python dependencies (layer cached until requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir --prefer-binary -r requirements.txt

# Copy application source
COPY . .

# Make the launcher executable
RUN chmod +x vociferous

# ---------- Runtime configuration ----------
# Skip the venv re-exec logic -- we're already in the right Python
ENV _VOCIFEROUS_ENV_READY=1
# Default GPU device
ENV CUDA_VISIBLE_DEVICES=0
# Suppress Qt Wayland decoration warnings
ENV QT_WAYLAND_DISABLE_WINDOWDECORATION=1

# Persist data, config, cache, and models across container restarts
VOLUME ["/root/.config/vociferous", "/root/.local/share/vociferous", "/root/.cache/vociferous"]

ENTRYPOINT ["python3", "vociferous"]
