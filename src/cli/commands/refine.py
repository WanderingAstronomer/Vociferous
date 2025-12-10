from __future__ import annotations

from pathlib import Path

import typer

from vociferous.cli.helpers import build_refiner_config
from vociferous.config import load_config
from vociferous.domain.exceptions import ConfigurationError, DependencyError
from vociferous.refinement.factory import build_refiner


def register_refine(app: typer.Typer) -> None:
    @app.command("refine", rich_help_panel="Refinement Components")
    def refine_cmd(
        input: Path = typer.Argument(..., metavar="TRANSCRIPT", help="Path to raw transcript text file"),
        output: Path | None = typer.Option(
            None,
            "--output",
            "-o",
            metavar="PATH",
            help="Write refined text to file (default: stdout)",
        ),
        instructions: str | None = typer.Option(
            None,
            "--instructions",
            "-i",
            help="Optional refinement instructions to guide the LLM",
            show_default=False,
        ),
        model: str | None = typer.Option(
            None,
            "--model",
            "-m",
            help="Refiner model (defaults to config refinement_model)",
            show_default=False,
        ),
        max_tokens: int = typer.Option(128, help="Max tokens for LLM-based refiners"),
        temperature: float = typer.Option(0.2, help="Temperature for LLM-based refiners"),
        gpu_layers: int = typer.Option(0, help="GPU layers for llama-cpp refiners"),
        context_length: int = typer.Option(2048, help="Context length for llama-cpp refiners"),
    ) -> None:
        """Refine a transcript text file using the refinement module."""
        if not input.exists():
            typer.echo(f"Error: transcript not found: {input}", err=True)
            raise typer.Exit(code=2)
        try:
            raw_text = input.read_text(encoding="utf-8")
        except OSError as exc:
            typer.echo(f"Error reading transcript: {exc}", err=True)
            raise typer.Exit(code=2) from exc

        if not raw_text.strip():
            typer.echo("Error: transcript is empty", err=True)
            raise typer.Exit(code=2)

        config = load_config()
        base_params = dict(config.refinement_params)
        # Allow CLI overrides for core LLM knobs
        base_params.update(
            {
                "max_tokens": str(max_tokens),
                "temperature": str(temperature),
                "gpu_layers": str(gpu_layers),
                "context_length": str(context_length),
            }
        )

        refiner_config = build_refiner_config(
            enabled=True,
            model=model or config.refinement_model,
            base_params=base_params,
            max_tokens=max_tokens,
            temperature=temperature,
            gpu_layers=gpu_layers,
            context_length=context_length,
        )

        try:
            refiner = build_refiner(refiner_config)
        except (DependencyError, ConfigurationError, RuntimeError, ValueError) as exc:
            typer.echo(f"Refiner initialization error: {exc}", err=True)
            raise typer.Exit(code=3) from exc

        refined = refiner.refine(raw_text, instructions or config.canary_qwen_refinement_instructions)

        if output:
            output.write_text(refined, encoding="utf-8")
            typer.echo(f"✓ Refined transcript written to {output}")
        else:
            typer.echo(refined)

    refine_cmd.dev_only = True  # type: ignore[attr-defined]
    return None
