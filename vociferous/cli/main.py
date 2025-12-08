from __future__ import annotations

from pathlib import Path
import logging
import subprocess
import shutil

from vociferous.app import TranscriptionSession, configure_logging
from vociferous.audio.sources import FileSource
from vociferous.app.sinks import PolishingSink
from vociferous.config import load_config
from vociferous.domain.model import TranscriptionPreset, EngineKind
from vociferous.domain.exceptions import (
    DependencyError, EngineError, AudioDecodeError, ConfigurationError
)
from vociferous.engines.factory import build_engine
from vociferous.polish.factory import build_polisher
from vociferous.tui import run_tui
from vociferous.cli.helpers import build_sink, build_transcribe_configs_from_cli

try:
    import typer
    from typer.core import TyperGroup
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.table import Table
    from rich.theme import Theme
    import click
except ImportError as exc:  # pragma: no cover - tooling dependency guard
    raise DependencyError("typer and rich are required for the CLI") from exc


configure_logging()

# Custom theme with bright, readable colors
console = Console(theme=Theme({
    "option": "bright_cyan",
    "switch": "bright_green", 
    "metavar": "bright_yellow",
    "metavar_sep": "white",
    "usage": "bold white",
}))

# Custom help colors for Click/Typer
class ColorHelpFormatter(click.HelpFormatter):
    """Help formatter with bright colors instead of dim grey."""
    def write_usage(self, prog: str, args: str = "", prefix: str | None = "Usage: ") -> None:
        colorized_prefix = click.style(prefix or "", fg="bright_yellow", bold=True)
        colorized_prog = click.style(prog, fg="bright_white", bold=True)
        self.write(f"{colorized_prefix}{colorized_prog} {args}\n")
    
    def write_heading(self, heading: str) -> None:
        self.write(f"\n{click.style(heading, fg='bright_yellow', bold=True)}\n")
    
    def write_text(self, text: str) -> None:
        # Make description text bright white instead of dim
        self.write(f"{click.style(text, fg='bright_white')}\n")

class BrightTyperGroup(TyperGroup):
    """TyperGroup with bright help colors."""
    def get_help(self, ctx: click.Context) -> str:
        formatter = ColorHelpFormatter()
        self.format_help(ctx, formatter)
        return formatter.getvalue()

app = typer.Typer(
    help="Vociferous - Local-first speech transcription",
    cls=BrightTyperGroup,
    rich_markup_mode="rich",
    pretty_exceptions_show_locals=False,
)
cli_app = app  # alias for embedding


@app.command(rich_help_panel="Core Commands")
def transcribe(
    file: Path = typer.Argument(..., metavar="FILE", help="Audio file to transcribe"),
    engine: EngineKind = typer.Option(
        "whisper_turbo",
        "--engine",
        "-e",
        rich_help_panel="Core Options",
        help="Transcription engine to use. 'whisper_turbo' is fast and accurate. 'voxtral_local' uses Mistral for smart punctuation.",
    ),
    language: str = typer.Option(
        "en",
        "--language",
        "-l",
        rich_help_panel="Core Options",
        help="Language code (ISO 639-1, e.g., 'en', 'es', 'fr') or 'auto' for detection.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        metavar="PATH",
        rich_help_panel="Core Options",
        help="Save transcript to file (default: stdout)",
    ),
    preset: TranscriptionPreset | None = typer.Option(
        None,
        "--preset",
        "-p",
        rich_help_panel="Core Options",
        help="Quality preset: 'fast' (speed), 'balanced' (default), 'high_accuracy' (best quality).",
        case_sensitive=False,
        show_default=False,
    ),
) -> None:
    """Transcribe an audio file to text using local ASR engines.

    ENGINES:
      whisper_turbo - Fast, accurate, works offline (default)
      voxtral_local - Smart punctuation, Mistral-based
      whisper_vllm  - Use vLLM server for Whisper
      voxtral_vllm  - Use vLLM server for Voxtral

    EXAMPLES:
      vociferous transcribe audio.mp3
      vociferous transcribe audio.wav --language fr --preset high_accuracy
      vociferous transcribe audio.flac --engine voxtral_local --output transcript.txt
      
    ADVANCED SETTINGS:
      Edit ~/.config/vociferous/config.toml to configure:
        • Model selection, device (CPU/CUDA), compute type
        • Batching, VAD filtering, chunk sizes
        • Polish settings, vLLM endpoint, etc.
    """
    logging.basicConfig(level=logging.INFO)
    config = load_config()
    
    # Build all configs from user-facing CLI options + config file
    bundle = build_transcribe_configs_from_cli(
        app_config=config,
        engine=engine,
        language=language,
        preset=preset,
    )
    
    # Apply numexpr thread limit if configured
    if bundle.numexpr_threads is not None:
        import os
        os.environ["NUMEXPR_MAX_THREADS"] = str(bundle.numexpr_threads)

    # Build engine and polisher
    try:
        engine_adapter = build_engine(engine, bundle.engine_config)
        polisher = build_polisher(bundle.polisher_config)
    except (DependencyError, EngineError) as exc:
        typer.echo(f"Engine initialization error: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    except ConfigurationError as exc:
        typer.echo(f"Polisher error: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    # Build audio source with default chunk settings
    source = FileSource(
        file,
        chunk_ms=config.chunk_ms,
    )
    
    # Build output sink
    sink = build_sink(output=output)
    if polisher is not None:
        sink = PolishingSink(sink, polisher)

    # Validate file exists before showing banner
    if not file.exists():
        console.print(Panel(f"[red]File not found: {file}[/red]", title="❌ File Not Found", border_style="red"))
        raise typer.Exit(code=2)

    if file.is_dir():
        console.print(
            Panel(
                f"[red]{file} is a directory, not an audio file.\n"
                f"Example: vociferous transcribe {file / 'your_audio_file.wav'}",
                title="❌ Directory, Not File",
                border_style="red",
            )
        )
        raise typer.Exit(code=2)

    if output is not None and output.is_dir():
        console.print(
            Panel(
                f"[red]{output} is a directory. Provide a filename (e.g., {output / 'transcript.txt'}).",
                title="⚠️  Invalid Output",
                border_style="yellow",
            )
        )
        raise typer.Exit(code=2)

    # Pretty startup banner
    file_size_mb = file.stat().st_size / (1024 * 1024)
    banner = Panel(
        f"[cyan]File:[/cyan] {file.name}\n"
        f"[cyan]Size:[/cyan] {file_size_mb:.2f} MB\n"
        f"[cyan]Engine:[/cyan] [yellow]{engine}[/yellow]\n"
        f"[cyan]Language:[/cyan] {language}",
        title="[bold green]Starting Transcription[/bold green]",
        border_style="green",
    )
    console.print(banner)

    session = TranscriptionSession()

    try:
        session.start(source, engine_adapter, sink, bundle.options, engine_kind=engine)
        session.join()
    except FileNotFoundError as exc:
        console.print(Panel(f"[red]{exc}[/red]", title="❌ File Not Found", border_style="red"))
        raise typer.Exit(code=2) from exc
    except EngineError as exc:
        console.print(Panel(f"[red]{exc}[/red]", title="⚠️  Engine Error", border_style="red"))
        raise typer.Exit(code=4) from exc
    except (AudioDecodeError, ConfigurationError) as exc:
        console.print(Panel(f"[red]{exc}[/red]", title="⚠️  Configuration Error", border_style="red"))
        raise typer.Exit(code=2) from exc
    except Exception as exc:  # pragma: no cover - safety net
        console.print(Panel(f"[red]{exc}[/red]", title="Unexpected Error", border_style="red"))
        raise typer.Exit(code=1) from exc


@app.command(rich_help_panel="Interfaces")
def tui(
    file: Path | None = typer.Option(None, help="Optional audio file; default is microphone"),
    engine: EngineKind = "whisper_turbo",
    language: str = "en",
) -> None:
    """[bold magenta]Full-screen TUI[/bold magenta] for live transcription. [yellow](Experimental)[/yellow]"""
    try:
        run_tui(file=file, engine=engine, language=language)
    except Exception as exc:
        typer.echo(f"TUI error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command(rich_help_panel="Utilities")
def check() -> None:
    """[bold blue]✅ Verify system prerequisites[/bold blue] before transcribing.

    Checks for:
      • [cyan]ffmpeg[/cyan] - Audio decoding (install: apt install ffmpeg)
      • [cyan]sounddevice[/cyan] - Microphone capture (install: pip install sounddevice)
      • [cyan]Model cache[/cyan] - Storage location for downloaded models

    [white]Run this after installing Vociferous to ensure everything works.[/white]
    """
    import importlib.util

    table = Table(title="System Check", show_header=True, header_style="bold cyan")
    table.add_column("Component", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Details", style="dim")

    ok = True

    # Check ffmpeg
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        table.add_row("ffmpeg", "[green]✅[/green]", ffmpeg_path)
    else:
        table.add_row("ffmpeg", "[red]❌[/red]", "Not found on PATH")
        ok = False

    # Check sounddevice
    if importlib.util.find_spec("sounddevice") is not None:
        table.add_row("sounddevice", "[green]✅[/green]", "Installed")
    else:
        table.add_row("sounddevice", "[yellow]⚠️[/yellow]", "Not installed (mic capture disabled)")
        ok = False

    # Check model cache
    cfg = load_config()
    cache_path = Path(cfg.model_cache_dir) if cfg.model_cache_dir else None
    if cache_path and cache_path.exists():
        table.add_row("Model cache", "[green]✅[/green]", str(cache_path))
    elif cache_path:
        table.add_row("Model cache", "[yellow]⚠️[/yellow]", f"{cache_path} (will be created)")
    else:
        table.add_row("Model cache", "[dim]➖[/dim]", "Not configured")

    console.print(table)

    if ok:
        console.print("\n[bold green]✅ All checks passed! Ready to transcribe.[/bold green]")
    else:
        console.print("\n[bold red]❌ Some prerequisites missing. Install them for full functionality.[/bold red]")
        raise typer.Exit(code=1)


@app.command(rich_help_panel="vLLM Server")
def check_vllm(
    endpoint: str | None = typer.Option(None, help="vLLM server endpoint (default from config)"),
) -> None:
    """[bold yellow]Check vLLM server connection[/bold yellow] and list available models.

    Use this to verify your vLLM server is running and accessible.
    The server must be started separately with [cyan]vociferous serve-vllm[/cyan].
    """
    config = load_config()
    target = endpoint or config.vllm_endpoint

    try:
        import openai
    except ImportError as exc:  # pragma: no cover - optional dependency guard
        raise DependencyError("openai package is required for vLLM checks; pip install openai") from exc

    client = openai.OpenAI(base_url=f"{target}/v1", api_key="EMPTY")
    try:
        models = client.models.list()
    except Exception as exc:  # pragma: no cover - network dependent
        typer.echo(f"vLLM check failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    served = [m.id for m in models.data]
    if not served:
        typer.echo(f"Connected to {target} but no models are served.")
        raise typer.Exit(code=1)

    typer.echo(f"vLLM endpoint: {target}")
    typer.echo("Models:")
    for mid in served:
        typer.echo(f" - {mid}")


@app.command(rich_help_panel="vLLM Server")
def serve_vllm(
    model: str = typer.Option("openai/whisper-large-v3-turbo", help="Model to serve with vLLM"),
    dtype: str = typer.Option("bfloat16", help="Model dtype (bfloat16|float16|auto)"),
    port: int = typer.Option(8000, help="Port to bind vLLM server"),
) -> None:
    """[bold yellow]Start a vLLM server[/bold yellow] for batch transcription.

    [bold]vLLM provides:[/bold]
      • High-throughput batch processing
      • GPU-optimized inference
      • OpenAI-compatible API

    [bold]Example:[/bold]
      [cyan]vociferous serve-vllm --model openai/whisper-large-v3-turbo[/cyan]

    [white]Note: Requires ~24GB VRAM. Use --engine whisper_turbo for local fallback.[/white]
    """
    if shutil.which("vllm") is None:
        typer.echo("vllm CLI not found on PATH. Install vllm and ensure it's available.", err=True)
        raise typer.Exit(code=1)

    cmd = [
        "vllm",
        "serve",
        model,
        "--dtype",
        dtype,
        "--port",
        str(port),
    ]

    typer.echo(f"Starting vLLM: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as exc:  # pragma: no cover - runtime dependent
        typer.echo(f"vLLM serve exited with code {exc.returncode}", err=True)
        raise typer.Exit(code=exc.returncode) from exc


def main() -> None:
    """CLI entrypoint for Vociferous."""
    try:
        app()
    except KeyboardInterrupt:
        typer.echo("\nInterrupted by user.", err=True)
        raise typer.Exit(code=130)
    except Exception as exc:
        typer.echo(f"Fatal error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


if __name__ == "__main__":
    main()
