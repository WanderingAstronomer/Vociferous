from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Mapping

import tomllib
import tomli_w

from pydantic import BaseModel, Field, field_validator

from vociferous.domain.model import (
    DEFAULT_CANARY_MODEL,
    DEFAULT_MODEL_CACHE_DIR,
    EngineKind,
)
from vociferous.config.migrations import migrate_raw_config

logger = logging.getLogger(__name__)


class ArtifactConfig(BaseModel):
    """Configuration for intermediate artifact handling."""

    cleanup_intermediates: bool = Field(
        default=True,
        description="Delete intermediate files after successful transcription",
    )
    keep_on_error: bool = Field(
        default=True,
        description="Keep intermediate files when a step fails (for debugging)",
    )
    output_directory: Path = Field(
        default=Path("."),
        description="Directory to write intermediate artifacts",
    )
    naming_pattern: str = Field(
        default="{input_stem}_{step}.{ext}",
        description="Filename pattern for intermediate artifacts",
    )


class AppConfig(BaseModel):
    """Main application configuration for Vociferous.
    
    Essential settings:
    - engine: ASR engine (canary_qwen or whisper_turbo)
    - model_name: Model identifier for the engine
    - device: Target device (auto, cpu, cuda)
    - compute_type: Precision (auto, int8, float16, float32, etc.)
    - model_cache_dir: Directory to cache downloaded models
    
    Refinement is handled per-engine in the CLI; not config-driven.
    Audio preprocessing uses the audio module (decode, vad, condense).
    """

    # Core engine configuration
    model_name: str = DEFAULT_CANARY_MODEL
    engine: EngineKind = "canary_qwen"  # Canary-Qwen is the primary default
    compute_type: str = "auto"
    device: str = "auto"
    model_cache_dir: str | None = Field(default_factory=lambda: str(DEFAULT_MODEL_CACHE_DIR))
    model_parent_dir: str | None = Field(default_factory=lambda: str(DEFAULT_MODEL_CACHE_DIR))
    
    # Advanced settings
    numexpr_max_threads: int | None = None  # Thread limit for numexpr computations
    
    # Artifact handling for intermediate files
    artifacts: ArtifactConfig = Field(default_factory=ArtifactConfig)
    
    # Engine-specific parameters (for future extensibility)
    params: Mapping[str, str] = Field(
        default_factory=lambda: {
            "enable_batching": "false",
            "batch_size": "1",
            "word_timestamps": "false",
        }
    )

    @field_validator("compute_type")
    @classmethod
    def validate_compute_type(cls, v: str) -> str:
        allowed = {"auto", "int8", "int8_float16", "float16", "float32", "fp16", "fp32"}
        if v not in allowed:
            raise ValueError("Invalid compute_type")
        return v

    @field_validator("model_parent_dir")
    @classmethod
    def validate_model_parent_dir(cls, v: str | None) -> str:
        if not v:
            raise ValueError("model_parent_dir must be set")
        return str(Path(v).expanduser())

    @classmethod
    def model_validate(cls, obj: Mapping[str, object] | object, *args, **kwargs):  # type: ignore[override]
        # Migrate legacy keep_intermediates → artifacts.cleanup_intermediates
        if isinstance(obj, Mapping):
            data = dict(obj)
            if "artifacts" not in data and "keep_intermediates" in data:
                keep_flag = bool(data.get("keep_intermediates"))
                data["artifacts"] = {
                    "cleanup_intermediates": not keep_flag,
                    "keep_on_error": True,
                    "output_directory": str(Path(".").resolve()),
                    "naming_pattern": "{input_stem}_{step}.{ext}",
                }
            return super().model_validate(data, *args, **kwargs)
        return super().model_validate(obj, *args, **kwargs)

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "AppConfig":
        # Pydantic handles validation automatically.
        # We use model_validate to parse the dict.
        return cls.model_validate(data)


def load_config(config_path: Path | None = None) -> AppConfig:
    """Load configuration, prompting for model directory only in interactive default runs."""

    default_config_path = Path.home() / ".config" / "vociferous" / "config.toml"
    if config_path is None:
        config_path = default_config_path

    is_first_run = not config_path.exists()

    if is_first_run:
        cfg = AppConfig()
        # Always prompt on first run in interactive mode
        should_prompt = sys.stdin.isatty()
    else:
        with open(config_path, "rb") as f:
            data = tomllib.load(f)

        migrated = migrate_raw_config(data)
        cfg = AppConfig.model_validate(migrated)
        # Prompt only if model_parent_dir is missing/blank and in interactive mode
        should_prompt = (not cfg.model_parent_dir or not str(cfg.model_parent_dir).strip()) and sys.stdin.isatty()

    if should_prompt:
        default_dir = str(DEFAULT_MODEL_CACHE_DIR)
        print("\nVociferous: Please select a parent directory for your models.")
        print(f"Default: {default_dir}")
        user_input = input("Enter model parent directory (or press Enter to use default): ").strip()
        chosen_dir = user_input if user_input else default_dir
        cfg.model_parent_dir = str(Path(chosen_dir).expanduser())
        save_config(cfg, config_path)

    # Ensure model parent directory exists
    if cfg.model_parent_dir:
        Path(cfg.model_parent_dir).expanduser().mkdir(parents=True, exist_ok=True)
    # Ensure model cache directory exists if provided
    if cfg.model_cache_dir:
        Path(cfg.model_cache_dir).expanduser().mkdir(parents=True, exist_ok=True)

    # Ensure artifact output directory exists
    if cfg.artifacts and cfg.artifacts.output_directory:
        Path(cfg.artifacts.output_directory).expanduser().mkdir(parents=True, exist_ok=True)

    return cfg


def save_config(config: AppConfig, config_path: Path | None = None) -> None:
    """Save configuration to TOML file.
    
    Args:
        config: Configuration to save
        config_path: Path to config file (default: ~/.config/vociferous/config.toml)
    """
    if config_path is None:
        config_path = Path.home() / ".config" / "vociferous" / "config.toml"
    
    # Ensure config directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Convert config to dict
    config_dict = config.model_dump(exclude_none=True)
    
    # Write to TOML file
    with open(config_path, "wb") as f:
        tomli_w.dump(config_dict, f)
