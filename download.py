"""Model downloader for ChatterBug (opt-in).

Usage:
    python -m download --model whisper-large-v3-turbo --dest models --yes

By default, asks for confirmation before downloading. Supports known models via
Hugging Face snapshot_download. Does not auto-run from the app; this is a manual
helper script.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

from huggingface_hub import snapshot_download
from tqdm import tqdm

DEFAULT_DEST = Path("models")

KNOWN_MODELS = {
    "whisper-large-v3-turbo": {
        "repo_id": "openai/whisper-large-v3-turbo",
        "subdir": "whisper-large-v3-turbo",
        "note": "Primary ASR (HF layout)",
        "approx_size_gb": 6.5,
    },
    "faster-whisper-small-int8": {
        "repo_id": "guillaumekln/faster-whisper-small-int8",
        "subdir": "faster_whisper_small",
        "note": "Lightweight fallback (converted F-W)",
        "approx_size_gb": 1.6,
    },
}


def _confirm(prompt: str, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    ans = input(f"{prompt} [y/N]: ").strip().lower()
    return ans in ("y", "yes")


def _check_disk(path: Path, required_gb: float) -> None:
    usage = shutil.disk_usage(str(path.resolve()))
    free_gb = usage.free / (1024**3)
    if free_gb < required_gb:
        raise RuntimeError(f"Not enough disk space at {path}: need ~{required_gb:.1f} GB, have {free_gb:.1f} GB")


def download(model_key: str, dest: Path, assume_yes: bool, revision: str | None = None) -> Path:
    if model_key not in KNOWN_MODELS:
        raise ValueError(f"Unknown model key: {model_key}. Known: {', '.join(KNOWN_MODELS)}")
    info = KNOWN_MODELS[model_key]
    repo_id = info["repo_id"]
    subdir = dest / info["subdir"]
    approx_size_gb = info["approx_size_gb"]

    dest.mkdir(parents=True, exist_ok=True)
    _check_disk(dest, approx_size_gb + 1.0)

    if subdir.exists():
        print(f"Destination already exists: {subdir}. Skipping download.")
        return subdir

    prompt = (
        f"Download {model_key} ({repo_id}) to {subdir} "
        f"(estimated size ~{approx_size_gb:.1f} GB). Continue?"
    )
    if not _confirm(prompt, assume_yes):
        raise RuntimeError("Download cancelled by user.")

    print(f"Downloading {repo_id} -> {subdir} ...")
    snapshot_download(
        repo_id=repo_id,
        local_dir=str(subdir),
        local_dir_use_symlinks=False,
        revision=revision,
        tqdm_class=tqdm,
    )
    print(f"Done. Files stored in {subdir}")
    return subdir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ChatterBug model downloader (opt-in)")
    parser.add_argument("--model", choices=KNOWN_MODELS.keys(), default="whisper-large-v3-turbo")
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST)
    parser.add_argument("--revision", type=str, default=None, help="Optional HF revision/commit")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args(argv)
    try:
        download(args.model, args.dest, assume_yes=args.yes, revision=args.revision)
    except Exception as exc:  # pragma: no cover - user IO
        print(f"Error: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
