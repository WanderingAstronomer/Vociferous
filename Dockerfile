# Vociferous — Multi-stage Dockerfile
# Stage 1: Build frontend (Svelte + Vite)
# Stage 2: Runtime (Python + pywebview GTK + audio)
#
# Build:  docker compose build
# Run:    docker compose up

# ── Stage 1: Frontend Build ──────────────────────────────────────────────────
FROM node:22-slim AS frontend-builder

WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --silent
COPY frontend/ .
RUN npx vite build

# ── Stage 2: Runtime ─────────────────────────────────────────────────────────
FROM python:3.12-slim-bookworm AS runtime

ENV DEBIAN_FRONTEND=noninteractive

# System dependencies for pywebview (GTK/WebKitGTK), audio, and input
RUN apt-get update && apt-get install -y --no-install-recommends \
    # GTK 3 + WebKitGTK (pywebview[gtk] backend)
    python3-gi \
    python3-gi-cairo \
    gir1.2-gtk-3.0 \
    gir1.2-webkit2-4.1 \
    libgirepository1.0-dev \
    gobject-introspection \
    # Wayland (first-class support)
    libwayland-client0 \
    libwayland-cursor0 \
    libwayland-egl1 \
    # X11 fallback
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    # Display / rendering
    libegl1 \
    libgl1 \
    libglib2.0-0 \
    libfontconfig1 \
    libdbus-1-3 \
    libxkbcommon0 \
    # Audio (sounddevice / PortAudio / PulseAudio)
    libportaudio2 \
    libsndfile1 \
    libasound2 \
    pulseaudio-utils \
    # Input (evdev / pynput for global hotkeys)
    libinput10 \
    libevdev2 \
    # Build tools for native Python packages
    build-essential \
    python3-dev \
    pkg-config \
    libcairo2-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies (cached until requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir --prefer-binary -r requirements.txt

# Copy application source
COPY src/ src/
COPY assets/ assets/
COPY vociferous pyproject.toml ./

# Copy pre-built frontend from stage 1
COPY --from=frontend-builder /build/dist/ frontend/dist/

# Make launcher executable
RUN chmod +x vociferous

# ── Runtime Configuration ────────────────────────────────────────────────────

# Skip venv re-exec logic inside the container
ENV _VOCIFEROUS_ENV_READY=1

# Wayland by default (X11 fallback available via compose override)
ENV GDK_BACKEND=wayland,x11
ENV WEBKIT_DISABLE_COMPOSITING_MODE=1

# Default GPU device for CUDA
ENV CUDA_VISIBLE_DEVICES=0

# Persist config, database, cache, and models across restarts
VOLUME ["/root/.config/vociferous", "/root/.local/share/vociferous", "/root/.cache/vociferous"]

ENTRYPOINT ["python3", "-m", "src.main"]
