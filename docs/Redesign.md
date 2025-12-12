## 🔴 Critical Priority (Must Fix)

### 1. **First-Time User Experience**

**Current State:**
```bash
$ vociferous transcribe audio.mp3
# 21 seconds of silence
# User thinks it crashed
```

**Permanent Solution Architecture:**

```python
# vociferous/setup/first_run.py

class FirstRunManager:
    """Manages first-time setup and model initialization."""
    
    SETUP_MARKER = Path. home() / ".cache" / "vociferous" / ". setup_complete"
    
    def is_first_run(self) -> bool:
        return not self.SETUP_MARKER.exists()
    
    def run_first_time_setup(self, config: Config) -> None:
        """Interactive first-time setup with clear progress."""
        console = Console()
        
        console.print("[bold]Welcome to Vociferous![/bold]")
        console.print("\nFirst-time setup required (~2 minutes):\n")
        
        steps = [
            "Checking system dependencies",
            "Downloading Canary-Qwen model (~4GB)",
            "Verifying GPU availability",
            "Warming up model",
        ]
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
        ) as progress:
            
            for step in steps:
                task = progress.add_task(step, total=100)
                
                if "Downloading" in step:
                    self._download_model_with_progress(progress, task)
                elif "Warming" in step:
                    self._warm_model_with_progress(progress, task)
                else:
                    self._run_step(step, progress, task)
                
                progress.update(task, completed=100)
        
        self.SETUP_MARKER.touch()
        console.print("\n✓ Setup complete! You're ready to transcribe.\n")
    
    def _download_model_with_progress(self, progress, task):
        """Download model with real progress tracking."""
        from huggingface_hub import snapshot_download
        
        def progress_callback(current_bytes, total_bytes):
            progress.update(task, completed=(current_bytes / total_bytes) * 100)
        
        snapshot_download(
            repo_id="nvidia/canary-qwen-2.5b",
            local_dir=self._get_model_cache_dir(),
            progress_callback=progress_callback,
        )
    
    def _warm_model_with_progress(self, progress, task):
        """Load model with simulated progress (can't track actual loading)."""
        import threading
        
        # Simulate progress while model loads
        def update_progress():
            for i in range(100):
                time.sleep(0.16)  # ~16s total
                progress.update(task, completed=i)
        
        thread = threading.Thread(target=update_progress)
        thread.start()
        
        # Actually load model
        engine = create_engine(config.engine_profile)
        
        thread. join()
        progress.update(task, completed=100)


# Integration point in CLI
@app.command("transcribe")
def transcribe_cmd(audio:  Path, ... ):
    # Check for first run
    first_run = FirstRunManager()
    if first_run.is_first_run():
        first_run.run_first_time_setup(config)
    
    # Normal transcription flow
    result = transcribe_file_workflow(...)
```

**Benefits:**
- ✅ One-time setup wizard
- ✅ Clear progress indicators
- ✅ User knows exactly what's happening
- ✅ Permanent state tracking (`.setup_complete` marker)
- ✅ Reusable for GUI integration

**Effort:** 8 hours  
**Files:**
- `vociferous/setup/first_run.py` (NEW)
- `vociferous/cli/commands/transcribe.py` (UPDATE)
- `vociferous/gui/app.py` (UPDATE when GUI is ready)

---

### 2. **Refinement Output Quality**

**Current Problem:**
Qwen3's `<think>` blocks appear in output unpredictably:

```
Input: "this is a test"
Output: "This is a test.  <think>Wait, I should check capitalization... </think>"
```

**Root Cause Analysis:**

The issue is **not just extraction**—it's that Qwen3 is using chain-of-thought reasoning when we want **direct text transformation**.

**Permanent Solution:  Constrained Generation**

```python
# vociferous/engines/canary_qwen.py

class CanaryQwenEngine: 
    
    DEFAULT_REFINE_PROMPT = """You are a transcript editor. Output ONLY the corrected text. 

Rules:
- Fix grammar and punctuation
- Fix capitalization
- Remove filler words (um, uh, like)
- Preserve all factual content
- Output the corrected text and nothing else

Do not explain your changes. Do not add commentary. Just output the corrected text."""

    def refine_text(self, raw_text: str, instructions: str | None = None) -> str:
        """Refine text using constrained generation."""
        
        prompt = instructions or self.DEFAULT_REFINE_PROMPT
        cleaned = raw_text.strip()
        
        if not cleaned:
            return ""
        
        # Construct prompt that discourages thinking
        prompts = [[{
            "role": "system",
            "content": "You are a text editor. Respond with only the edited text."
        }, {
            "role": "user", 
            "content": f"{prompt}\n\nText to edit:\n{cleaned}\n\nEdited text:"
        }]]
        
        with self._model. llm.disable_adapter():
            # Use deterministic generation to reduce randomness
            answer_ids = self._model.generate(
                prompts=prompts,
                max_new_tokens=self._resolve_refine_tokens(cleaned),
                temperature=0.1,  # Low temperature = more deterministic
                top_p=0.9,
                repetition_penalty=1.1,
                do_sample=True,  # But still sample to avoid degeneration
            )
        
        # Extract response
        raw_output = self._model.tokenizer.ids_to_text(answer_ids[0]. cpu()).strip()
        
        # Robust extraction
        refined = self._extract_assistant_response(raw_output)
        
        # Validation:  ensure output is reasonable
        refined = self._validate_refinement(cleaned, refined)
        
        return refined
    
    def _extract_assistant_response(self, raw_output: str) -> str:
        """Extract clean response from chat template format."""
        
        # Remove everything before assistant marker
        if "<|im_start|>assistant" in raw_output:
            raw_output = raw_output.split("<|im_start|>assistant")[-1]
        
        # Remove closing markers
        if "<|im_end|>" in raw_output:
            raw_output = raw_output.split("<|im_end|>")[0]
        
        # Remove ALL thinking blocks (before, after, or in middle of response)
        import re
        raw_output = re.sub(
            r'<think>.*?</think>',
            '',
            raw_output,
            flags=re.DOTALL | re.IGNORECASE
        )
        
        # Remove common artifacts
        raw_output = re. sub(r'^\s*Edited text:\s*', '', raw_output, flags=re.IGNORECASE)
        raw_output = re.sub(r'^\s*Here is the corrected text:\s*', '', raw_output, flags=re.IGNORECASE)
        
        return raw_output.strip()
    
    def _validate_refinement(self, original: str, refined: str) -> str:
        """Validate refinement output is reasonable."""
        
        # If refinement is empty or too short, return original
        if not refined or len(refined) < len(original) * 0.3:
            logger.warning(f"Refinement output too short ({len(refined)} chars), using original")
            return original
        
        # If refinement is way too long, it probably includes thinking/explanation
        if len(refined) > len(original) * 2. 5:
            logger.warning(f"Refinement output suspiciously long ({len(refined)} chars), using original")
            return original
        
        # If refinement contains obvious artifacts, return original
        artifacts = [
            "here is the corrected",
            "i have corrected",
            "the edited version",
            "here's the refined",
            "<think>",
            "explanation:",
        ]
        
        refined_lower = refined.lower()
        if any(artifact in refined_lower for artifact in artifacts):
            logger.warning("Refinement contains artifacts, using original")
            return original
        
        return refined
```

**Why This is Permanent:**

1. **System prompt** explicitly constrains output format
2. **Low temperature** reduces creative randomness
3. **Regex removes all thinking blocks** (not just trailing ones)
4. **Validation** catches when model ignores constraints
5. **Fallback to original** if refinement is garbage

**Testing:**

```python
# tests/engines/test_refinement_quality.py

@pytest.mark.parametrize("input_text,expected_patterns", [
    # Basic punctuation
    ("this is a test", r"This is a test\. "),
    
    # Capitalization
    ("john went to walmart", r"John went to Walmart\."),
    
    # Filler words
    ("um so like i think that uh we should", r"(I think|We should)"),
    
    # No artifacts
    ("test input", lambda out: "<think>" not in out. lower()),
    ("test input", lambda out: "here is" not in out.lower()),
])
def test_refinement_quality(canary_engine, input_text, expected_patterns):
    """Ensure refinement produces clean output."""
    refined = canary_engine.refine_text(input_text)
    
    if callable(expected_patterns):
        assert expected_patterns(refined)
    else:
        assert re.search(expected_patterns, refined)
    
    # Ensure no artifacts
    assert "<think>" not in refined. lower()
    assert "edited text:" not in refined.lower()
```

**Effort:** 4 hours  
**Files:**
- `vociferous/engines/canary_qwen.py` (UPDATE `refine_text()`)
- `tests/engines/test_refinement_quality.py` (NEW)

---

### 3. **Progress Feedback for Long Transcriptions**

**Current State:**
```bash
$ vociferous transcribe 2_hour_podcast.mp3
# 5 minutes of silence
# User kills process thinking it hung
```

**Permanent Solution: Rich Progress Integration**

```python
# vociferous/app/progress.py

from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.console import Console

class TranscriptionProgress: 
    """Manages progress display for transcription workflow."""
    
    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.console = Console()
        
        if verbose:
            self.progress = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task. percentage:>3.0f}%"),
                TimeElapsedColumn(),
                TimeRemainingColumn(),
                console=self.console,
            )
        else:
            self.progress = None
    
    def __enter__(self):
        if self.progress:
            self.progress.__enter__()
        return self
    
    def __exit__(self, *args):
        if self.progress:
            self.progress.__exit__(*args)
    
    def add_step(self, description: str, total: int | None = None):
        """Add a progress step."""
        if self.progress:
            return self.progress.add_task(description, total=total)
        return None
    
    def update(self, task_id, **kwargs):
        """Update progress."""
        if self.progress and task_id is not None:
            self.progress.update(task_id, **kwargs)
    
    def advance(self, task_id, amount: float = 1.0):
        """Advance progress."""
        if self.progress and task_id is not None:
            self.progress.advance(task_id, amount)
    
    def complete(self, task_id):
        """Mark step complete."""
        if self.progress and task_id is not None: 
            self.progress.update(task_id, completed=True)
            self.progress.remove_task(task_id)
    
    def print(self, message: str, style: str | None = None):
        """Print message without disrupting progress."""
        if self. verbose:
            if self.progress:
                self.progress.console.print(message, style=style)
            else:
                self.console.print(message, style=style)


# vociferous/app/workflow.py

def transcribe_file_workflow(
    source: Source,
    engine_profile: EngineProfile,
    segmentation_profile: SegmentationProfile,
    *,
    refine: bool = True,
    use_daemon: bool = False,
    progress: TranscriptionProgress | None = None,
    # ... other params
) -> TranscriptionResult:
    """Transcription workflow with progress tracking."""
    
    # Create progress tracker if not provided
    if progress is None: 
        progress = TranscriptionProgress(verbose=True)
    
    with progress:
        # Step 1: Decode
        decode_task = progress.add_step("Decoding audio to WAV.. .", total=None)
        decoded_path = decode_component. decode(source.path, ...)
        progress.complete(decode_task)
        
        # Step 2: VAD
        vad_task = progress.add_step("Detecting speech segments...", total=None)
        timestamps = vad_component.detect_speech(decoded_path)
        progress.complete(vad_task)
        progress.print(f"Found {len(timestamps)} speech segments")
        
        # Step 3: Condense
        condense_task = progress.add_step("Condensing audio...", total=None)
        condensed_paths = condenser.condense(decoded_path, timestamps, ...)
        progress.complete(condense_task)
        progress.print(f"Audio split into {len(condensed_paths)} chunks")
        
        # Step 4: Transcribe chunks
        transcribe_task = progress.add_step(
            f"Transcribing chunks...",
            total=len(condensed_paths)
        )
        
        all_segments = []
        for i, chunk_path in enumerate(condensed_paths, 1):
            progress.update(
                transcribe_task,
                description=f"Transcribing chunk {i}/{len(condensed_paths)}..."
            )
            
            if use_daemon:
                segments = transcribe_via_daemon(chunk_path)
                if segments is None:
                    segments = transcribe_direct(chunk_path, engine_profile)
            else:
                segments = transcribe_direct(chunk_path, engine_profile)
            
            all_segments.extend(segments)
            progress.advance(transcribe_task)
        
        progress.complete(transcribe_task)
        
        # Step 5: Refinement (if enabled)
        if refine:
            refine_task = progress.add_step("Refining transcript...", total=None)
            raw_text = "\n".join(seg.text for seg in all_segments)
            
            if use_daemon:
                refined_text = refine_via_daemon(raw_text)
                if refined_text is None: 
                    refined_text = refine_direct(raw_text, engine_profile)
            else:
                refined_text = refine_direct(raw_text, engine_profile)
            
            # Update segments with refined text
            all_segments = apply_refinement(all_segments, refined_text)
            progress. complete(refine_task)
        
        progress.print("✓ Transcription complete", style="bold green")
    
    return TranscriptionResult(segments=all_segments, ...)
```

**CLI Integration:**

```python
@app.command("transcribe")
def transcribe_cmd(
    audio: Path,
    verbose: bool = typer.Option(True, help="Show progress"),
    ...
):
    """Transcribe audio file."""
    
    progress = TranscriptionProgress(verbose=verbose)
    
    result = transcribe_file_workflow(
        source=FileSource(audio),
        progress=progress,
        ...
    )
```

**GUI Integration (Future):**

```python
# vociferous/gui/transcription_tab.py

class TranscriptionTab:
    def on_transcribe_button(self, audio_path):
        # Create GUI progress tracker
        gui_progress = GUIProgress(self.progress_bar, self.status_label)
        
        # Run transcription in background thread
        def transcribe_async():
            result = transcribe_file_workflow(
                source=FileSource(audio_path),
                progress=gui_progress,
                ...
            )
            self.display_result(result)
        
        threading.Thread(target=transcribe_async).start()


class GUIProgress(TranscriptionProgress):
    """Progress tracker that updates GUI widgets."""
    
    def __init__(self, progress_bar: Widget, status_label: Widget):
        super().__init__(verbose=False)  # Don't print to console
        self.progress_bar = progress_bar
        self. status_label = status_label
    
    def add_step(self, description, total):
        self.status_label.text = description
        if total: 
            self.progress_bar. max = total
            self.progress_bar.value = 0
        return description  # Use description as task_id
    
    def update(self, task_id, **kwargs):
        if "description" in kwargs:
            self. status_label.text = kwargs["description"]
        if "completed" in kwargs:
            self. progress_bar.value = kwargs["completed"]
```

**Why This is Permanent:**

1. **Abstraction layer** (`TranscriptionProgress`) works for CLI and GUI
2. **Rich library** is industry-standard (maintained, stable)
3. **Zero impact** when `verbose=False` (no overhead for batch scripts)
4. **Extensible** to other workflows (batch, live, etc.)

**Effort:** 6 hours  
**Files:**
- `vociferous/app/progress.py` (NEW)
- `vociferous/app/workflow.py` (UPDATE all workflows)
- `vociferous/cli/commands/transcribe.py` (UPDATE to use progress)

---

## 🟡 Major Priority (Should Fix)

### 4. **Daemon Auto-Start**

**Current Pain:**
```bash
vociferous transcribe audio.wav --use-daemon
# Falls back to cold start if daemon not running
# User confused why it's slow
```

**Permanent Solution: Smart Daemon Management**

```python
# vociferous/server/manager.py

class DaemonManager:
    """Manages daemon lifecycle with auto-start capability."""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self.host = host
        self.port = port
        self.client = DaemonClient(host, port)
    
    def ensure_running(self, auto_start: bool = True, progress: TranscriptionProgress | None = None) -> bool:
        """Ensure daemon is running, optionally auto-starting it."""
        
        # Check if already running
        if self.client. ping():
            return True
        
        # Not running - auto-start if requested
        if not auto_start:
            return False
        
        if progress: 
            progress.print("Daemon not running, starting automatically...")
            task = progress.add_step("Starting warm model daemon...", total=None)
        
        try:
            self.start_daemon_sync()
            
            if progress:
                progress.complete(task)
                progress.print("✓ Daemon started successfully")
            
            return True
        
        except Exception as e: 
            logger.error(f"Failed to auto-start daemon: {e}")
            
            if progress:
                progress. complete(task)
                progress. print(f"⚠️ Daemon auto-start failed: {e}", style="yellow")
            
            return False
    
    def start_daemon_sync(self, timeout: float = 30.0):
        """Start daemon and wait for it to be ready."""
        
        # Start daemon process
        proc = subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn",
                "vociferous.server.api:app",
                "--host", self.host,
                "--port", str(self.port),
                "--log-level", "info",
            ],
            stdout=subprocess. PIPE,
            stderr=subprocess. STDOUT,
            start_new_session=True,
        )
        
        # Write PID file
        _write_pid_file(proc.pid)
        
        # Wait for health check
        start_time = time.time()
        while time.time() - start_time < timeout:
            time.sleep(1)
            
            if self.client.ping():
                logger.info(f"Daemon started successfully (PID: {proc. pid})")
                return
        
        # Timeout - daemon didn't start
        proc.kill()
        _remove_pid_file()
        raise DaemonError(f"Daemon failed to start within {timeout}s")


# Update workflow integration
def transcribe_via_daemon(
    audio_path: Path,
    auto_start: bool = True,
    progress: TranscriptionProgress | None = None
) -> list[TranscriptSegment] | None:
    """Transcribe via daemon with optional auto-start."""
    
    manager = DaemonManager()
    
    # Ensure daemon is running
    if not manager.ensure_running(auto_start=auto_start, progress=progress):
        return None  # Daemon not available and auto-start disabled/failed
    
    # Transcribe using daemon
    try:
        return manager.client.transcribe(audio_path)
    except DaemonError as e:
        logger.warning(f"Daemon transcription failed: {e}")
        return None
```

**CLI Integration:**

```python
@app.command("transcribe")
def transcribe_cmd(
    audio: Path,
    daemon: str = typer.Option(
        "auto",
        help="Daemon mode:  'auto' (use if running), 'always' (start if needed), 'never' (direct only)"
    ),
    ...
):
    """Transcribe audio file."""
    
    use_daemon = daemon in ["auto", "always"]
    auto_start = daemon == "always"
    
    result = transcribe_file_workflow(
        source=FileSource(audio),
        use_daemon=use_daemon,
        daemon_auto_start=auto_start,
        ... 
    )
```

**Why This is Permanent:**

1. **Three explicit modes**:  `auto` (try daemon), `always` (start daemon), `never` (direct only)
2. **Progress integration**:  Shows what's happening during auto-start
3. **Robust error handling**: Falls back gracefully if auto-start fails
4. **User control**: User can disable auto-start if desired

**Effort:** 4 hours  
**Files:**
- `vociferous/server/manager. py` (NEW)
- `vociferous/server/client.py` (UPDATE to use manager)
- `vociferous/app/workflow.py` (UPDATE to use manager)
- `vociferous/cli/commands/transcribe.py` (UPDATE with `--daemon` option)

---

### 5. **Error Messages & Troubleshooting**

**Current State:**
```bash
$ vociferous transcribe broken. mp3
Error: FFmpeg error code 1
```

**Permanent Solution: Error Context System**

```python
# vociferous/domain/exceptions.py

class VociferousError(Exception):
    """Base exception with rich error context."""
    
    def __init__(
        self,
        message: str,
        *,
        cause: Exception | None = None,
        context: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.cause = cause
        self.context = context or {}
        self.suggestions = suggestions or []
    
    def format_error(self) -> str:
        """Format error with full context for CLI display."""
        from rich.console import Console
        from rich.panel import Panel
        from rich.text import Text
        
        console = Console()
        
        # Main error message
        output = Text()
        output.append("✗ Error:  ", style="bold red")
        output.append(self.message)
        
        # Context information
        if self.context:
            output.append("\n\nDetails:\n", style="bold")
            for key, value in self.context.items():
                output.append(f"  • {key}: {value}\n")
        
        # Suggestions
        if self.suggestions:
            output.append("\nPossible solutions:\n", style="bold yellow")
            for i, suggestion in enumerate(self.suggestions, 1):
                output. append(f"  {i}. {suggestion}\n", style="yellow")
        
        # Root cause
        if self.cause:
            output.append(f"\nCaused by: {type(self.cause).__name__}: {self.cause}\n", style="dim")
        
        return Panel(output, border_style="red", title="[bold]Error[/bold]")


class AudioDecodeError(VociferousError):
    """Raised when audio file cannot be decoded."""
    
    @classmethod
    def from_ffmpeg_error(cls, audio_path: Path, returncode: int, stderr: str):
        """Create error from FFmpeg failure with helpful context."""
        
        # Analyze FFmpeg error
        suggestions = []
        
        if "Invalid data found" in stderr or "could not find codec" in stderr:
            suggestions. extend([
                f"File may be corrupted.  Try playing it with VLC or another player.",
                f"Convert to a standard format:  ffmpeg -i {audio_path} output.wav",
                "Supported formats: MP3, WAV, FLAC, M4A, OGG, OPUS",
            ])
        
        elif "Permission denied" in stderr:
            suggestions.extend([
                f"Check file permissions:  ls -l {audio_path}",
                f"Try:  chmod 644 {audio_path}",
            ])
        
        elif "No such file" in stderr:
            suggestions.extend([
                f"File does not exist: {audio_path}",
                "Check the path and try again.",
            ])
        
        else:
            suggestions.append("Run with --verbose to see full FFmpeg output")
        
        return cls(
            f"Failed to decode audio file: {audio_path. name}",
            context={
                "file": str(audio_path),
                "ffmpeg_exit_code": returncode,
            },
            suggestions=suggestions,
        )


class VADError(VociferousError):
    """Raised when VAD fails or detects no speech."""
    
    @classmethod
    def no_speech_detected(cls, audio_path: Path, audio_duration_s: float, threshold: float):
        """Create error when VAD finds no speech."""
        return cls(
            f"No speech detected in audio file",
            context={
                "file": str(audio_path),
                "duration":  f"{audio_duration_s:.1f}s",
                "vad_threshold": threshold,
            },
            suggestions=[
                "Audio may be silent or very quiet. Check recording levels.",
                "Background noise may be drowning out speech.  Try noise reduction.",
                f"Lower VAD sensitivity:  --vad-threshold {threshold * 0.7:. 2f}",
                "Use --vad-aggressive to detect quieter speech",
            ],
        )


class UnsplittableSegmentError(VociferousError):
    """Raised when a single segment exceeds max chunk duration."""
    
    def __init__(self, segment_start: float, segment_end: float, max_chunk_s: float):
        duration = segment_end - segment_start
        
        super().__init__(
            f"Single speech segment is too long ({duration:.1f}s exceeds {max_chunk_s:.1f}s limit)",
            context={
                "segment_duration": f"{duration:.1f}s",
                "max_allowed": f"{max_chunk_s:.1f}s",
                "segment_range": f"{segment_start:.1f}s - {segment_end:.1f}s",
            },
            suggestions=[
                "VAD failed to detect pauses. Try adjusting VAD parameters:",
                "  --min-silence-ms 300  (detect shorter pauses)",
                "  --vad-threshold 0.3   (lower sensitivity)",
                "Pre-split audio manually at known boundaries",
                "Use a different engine with longer context support",
            ],
        )
```

**CLI Error Handler:**

```python
# vociferous/cli/main.py

def main():
    """Main CLI entry point with error handling."""
    try:
        app()
    except VociferousError as e: 
        # Rich formatted error
        console = Console()
        console.print(e.format_error())
        raise typer.Exit(1)
    except KeyboardInterrupt:
        console = Console()
        console.print("\n⚠️  Operation cancelled by user", style="yellow")
        raise typer.Exit(130)
    except Exception as e: 
        # Unexpected error - show full traceback in verbose mode
        console = Console()
        if os.getenv("VOCIFEROUS_VERBOSE"):
            console.print_exception()
        else:
            console. print(f"[red]✗ Unexpected error: {e}[/red]")
            console.print("[dim]Run with VOCIFEROUS_VERBOSE=1 for full traceback[/dim]")
        raise typer.Exit(1)
```

**Why This is Permanent:**

1. **Structured error system** with cause, context, suggestions
2. **Rich formatting** for readable CLI output
3. **Extensible** - easy to add new error types
4. **Maintains stack traces** for debugging
5. **User-friendly** while still informative

**Effort:** 6 hours  
**Files:**
- `vociferous/domain/exceptions.py` (MAJOR UPDATE)
- All modules that raise exceptions (UPDATE to use new error classes)
- `vociferous/cli/main.py` (UPDATE error handler)

---

### 6. **Audio Preprocessing**

**Current Pain:**
Users with noisy/quiet audio must manually preprocess: 

```bash
ffmpeg -i noisy.wav -af "highpass=f=200,volume=2" clean.wav
vociferous transcribe clean.wav
```

**Permanent Solution: Preprocessing Pipeline**

```python
# vociferous/audio/preprocessing.py

from dataclasses import dataclass
from pathlib import Path
import subprocess

@dataclass
class PreprocessingConfig:
    """Configuration for audio preprocessing."""
    
    denoise: bool = False
    normalize: bool = False
    highpass_hz: int | None = None
    lowpass_hz: int | None = None
    volume_adjust_db: float | None = None
    
    @classmethod
    def from_preset(cls, preset: str) -> "PreprocessingConfig":
        """Create config from preset name."""
        presets = {
            "none": cls(),
            "basic": cls(normalize=True),
            "clean": cls(denoise=True, normalize=True),
            "phone": cls(denoise=True, normalize=True, highpass_hz=300, lowpass_hz=3400),
            "podcast": cls(normalize=True, highpass_hz=80),
        }
        
        if preset not in presets:
            raise ValueError(f"Unknown preset: {preset}. Choose from: {list(presets. keys())}")
        
        return presets[preset]


class AudioPreprocessor:
    """Applies audio preprocessing filters using FFmpeg."""
    
    def __init__(self, config: PreprocessingConfig):
        self.config = config
    
    def needs_preprocessing(self) -> bool:
        """Check if any preprocessing is enabled."""
        return any([
            self.config.denoise,
            self.config.normalize,
            self.config.highpass_hz is not None,
            self.config.lowpass_hz is not None,
            self.config.volume_adjust_db is not None,
        ])
    
    def preprocess(
        self,
        input_path: Path,
        output_path: Path,
        progress: TranscriptionProgress | None = None,
    ) -> Path:
        """Apply preprocessing filters to audio file."""
        
        if not self.needs_preprocessing():
            return input_path  # No preprocessing needed
        
        if progress:
            task = progress.add_step("Preprocessing audio...", total=None)
        
        try: 
            filters = self._build_filter_chain()
            
            cmd = [
                "ffmpeg",
                "-i", str(input_path),
                "-af", filters,
                "-y",  # Overwrite output
                str(output_path),
            ]
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
            
            if progress:
                progress.complete(task)
                progress.print(f"✓ Preprocessing applied:  {self._describe_filters()}")
            
            return output_path
        
        except subprocess.CalledProcessError as e:
            raise AudioProcessingError(
                "Audio preprocessing failed",
                cause=e,
                context={"filters": filters},
                suggestions=[
                    "Try without preprocessing:  remove --preprocess flag",
                    "Check FFmpeg is installed:  ffmpeg -version",
                ],
            )
    
    def _build_filter_chain(self) -> str:
        """Build FFmpeg filter chain from config."""
        filters = []
        
        if self.config. highpass_hz: 
            filters.append(f"highpass=f={self.config.highpass_hz}")
        
        if self.config.lowpass_hz:
            filters.append(f"lowpass=f={self.config.lowpass_hz}")
        
        if self.config.denoise:
            # Simple noise reduction using high/low pass
            if not self.config.highpass_hz:
                filters.append("highpass=f=200")  # Remove low-frequency rumble
            if not self.config.lowpass_hz:
                filters.append("lowpass=f=3500")  # Remove high-frequency hiss
        
        if self.config.volume_adjust_db:
            filters.append(f"volume={self.config.volume_adjust_db}dB")
        
        if self.config.normalize:
            # EBU R128 loudness normalization
            filters.append("loudnorm=I=-16: TP=-1.5:LRA=11")
        
        return ",".join(filters)
    
    def _describe_filters(self) -> str:
        """Human-readable description of applied filters."""
        descriptions = []
        
        if self.config.denoise:
            descriptions.append("noise reduction")
        if self.config.normalize:
            descriptions.append("volume normalization")
        if self.config.highpass_hz:
            descriptions.append(f"highpass {self.config.highpass_hz}Hz")
        if self.config.lowpass_hz:
            descriptions.append(f"lowpass {self.config.lowpass_hz}Hz")
        if self.config.volume_adjust_db:
            descriptions.append(f"{self.config.volume_adjust_db: +.1f}dB gain")
        
        return ", ".join(descriptions)
```

**Workflow Integration:**

```python
# In transcribe_file_workflow()

def transcribe_file_workflow(
    source: Source,
    preprocessing: PreprocessingConfig | None = None,
    ... 
):
    """Transcription workflow with optional preprocessing."""
    
    with progress: 
        # Decode
        decoded_path = decode_component. decode(source. path)
        
        # Preprocess (if requested)
        if preprocessing and preprocessing.needs_preprocessing():
            preprocessor = AudioPreprocessor(preprocessing)
            preprocessed_path = artifact_dir / f"{decoded_path.stem}_preprocessed. wav"
            audio_to_transcribe = preprocessor.preprocess(
                decoded_path,
                preprocessed_path,
                progress=progress
            )
        else:
            audio_to_transcribe = decoded_path
        
        # VAD on preprocessed audio
        timestamps = vad_component.detect_speech(audio_to_transcribe)
        
        # ...  rest of workflow ... 
```

**CLI Integration:**

```python
@app.command("transcribe")
def transcribe_cmd(
    audio: Path,
    preprocess: str = typer.Option(
        "none",
        help="Preprocessing preset: none, basic, clean, phone, podcast"
    ),
    denoise: bool = typer.Option(False, help="Apply noise reduction"),
    normalize: bool = typer.Option(False, help="Normalize volume"),
    ...
):
    """Transcribe audio file."""
    
    # Build preprocessing config
    if preprocess != "none":
        preprocessing = PreprocessingConfig.from_preset(preprocess)
    elif denoise or normalize:
        preprocessing = PreprocessingConfig(denoise=denoise, normalize=normalize)
    else:
        preprocessing = None
    
    result = transcribe_file_workflow(
        source=FileSource(audio),
        preprocessing=preprocessing,
        ...
    )
```

**Why This is Permanent:**

1. **Preset system** makes it easy for users ("clean", "phone", etc.)
2. **Granular control** available for power users
3. **FFmpeg-based** (no new dependencies, uses existing tool)
4. **Optional** (zero impact if not used)
5. **Extensible** (easy to add new presets/filters)

**Effort:** 8 hours  
**Files:**
- `vociferous/audio/preprocessing.py` (NEW)
- `vociferous/app/workflow.py` (UPDATE to integrate preprocessing)
- `vociferous/cli/commands/transcribe.py` (UPDATE with preprocessing options)
- `docs/preprocessing.md` (NEW - document presets and filters)

---

### 7. **Batch Processing**

**Current Pain:**
```bash
# User must script batch transcription
for f in *.mp3; do
    vociferous transcribe "$f"
done
```

**Permanent Solution: Native Batch Command**

```python
# vociferous/cli/commands/batch.py

@app.command("batch")
def batch_transcribe(
    files: list[Path] = typer.Argument(..., help="Audio files to transcribe"),
    output_dir: Path = typer. Option(None, "--output-dir", "-o", help="Output directory"),
    combined:  bool = typer.Option(False, "--combined", help="Generate combined transcript"),
    continue_on_error: bool = typer.Option(True, help="Continue if a file fails"),
    daemon: str = typer.Option("always", help="Daemon mode (always recommended for batch)"),
    parallel: int = typer.Option(1, "--parallel", "-j", help="Number of parallel transcriptions (use with daemon)"),
    ...
):
    """Transcribe multiple audio files in batch. 
    
    Examples:
        # Transcribe all MP3 files in current directory
        vociferous batch *.mp3
        
        # With preprocessing
        vociferous batch *. wav --preprocess clean
        
        # Generate combined transcript
        vociferous batch podcast_ep*. mp3 --combined --output-dir transcripts/
        
        # Parallel processing (requires daemon)
        vociferous batch *.mp3 --parallel 3
    """
    
    from vociferous.app.batch import BatchTranscriptionRunner
    
    # Validate files
    valid_files = [f for f in files if f. exists()]
    invalid_files = [f for f in files if not f.exists()]
    
    if invalid_files: 
        console. print(f"⚠️  Skipping {len(invalid_files)} non-existent files", style="yellow")
    
    if not valid_files:
        console. print("✗ No valid files to transcribe", style="red")
        raise typer.Exit(1)
    
    # Setup output directory
    if output_dir is None:
        output_dir = Path.cwd() / "transcripts"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create runner
    runner = BatchTranscriptionRunner(
        files=valid_files,
        output_dir=output_dir,
        daemon_mode=daemon,
        parallel=parallel,
        continue_on_error=continue_on_error,
        # ... pass other transcription params ...
    )
    
    # Execute
    results = runner.run()
    
    # Summary
    successful = sum(1 for r in results if r.success)
    failed = len(results) - successful
    
    console.print(f"\n{'='*60}")
    console.print(f"Batch transcription complete:")
    console.print(f"  ✓ Successful: {successful}")
    if failed:
        console.print(f"  ✗ Failed: {failed}", style="red")
    console.print(f"  Output: {output_dir}")
    console.print(f"{'='*60}")
    
    # Generate combined transcript
    if combined and successful > 0:
        combined_path = output_dir / "combined_transcript.txt"
        with open(combined_path, "w") as f:
            for result in results:
                if result. success:
                    f.write(f"# {result.source_file.name}\n\n")
                    f.write(result.transcript_text)
                    f.write("\n\n")
        
        console.print(f"\n✓ Combined transcript:  {combined_path}", style="green")


# vociferous/app/batch.py

@dataclass
class BatchResult:
    source_file: Path
    success: bool
    transcript_text:  str | None = None
    output_path: Path | None = None
    error: Exception | None = None
    duration_s: float = 0.0


class BatchTranscriptionRunner: 
    """Manages batch transcription with progress tracking and error handling."""
    
    def __init__(
        self,
        files: list[Path],
        output_dir: Path,
        daemon_mode: str = "always",
        parallel: int = 1,
        continue_on_error: bool = True,
        **transcription_kwargs,
    ):
        self.files = files
        self.output_dir = output_dir
        self.daemon_mode = daemon_mode
        self.parallel = parallel
        self.continue_on_error = continue_on_error
        self.transcription_kwargs = transcription_kwargs
    
    def run(self) -> list[BatchResult]:
        """Execute batch transcription."""
        
        # Ensure daemon is running if needed
        if self.daemon_mode in ["auto", "always"]:
            manager = DaemonManager()
            if not manager.ensure_running(auto_start=self.daemon_mode == "always"):
                console.print("⚠️  Daemon not available, using direct engine", style="yellow")
        
        # Single-threaded or parallel? 
        if self.parallel == 1:
            return self._run_sequential()
        else:
            return self._run_parallel()
    
    def _run_sequential(self) -> list[BatchResult]: 
        """Process files sequentially with progress bar."""
        results = []
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
        ) as progress:
            
            task = progress.add_task("Batch transcription", total=len(self.files))
            
            for i, audio_file in enumerate(self.files, 1):
                progress.update(task, description=f"[{i}/{len(self.files)}] {audio_file.name}")
                
                result = self._transcribe_single(audio_file)
                results.append(result)
                
                progress.advance(task)
                
                # Stop on error if requested
                if not result.success and not self.continue_on_error:
                    progress.console.print(f"✗ Stopping due to error: {result.error}", style="red")
                    break
        
        return results
    
    def _run_parallel(self) -> list[BatchResult]: 
        """Process files in parallel using ThreadPoolExecutor."""
        import concurrent.futures
        
        results = []
        
        with Progress(... ) as progress:
            task = progress.add_task("Batch transcription", total=len(self.files))
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.parallel) as executor:
                # Submit all jobs
                futures = {
                    executor.submit(self._transcribe_single, f): f
                    for f in self.files
                }
                
                # Collect results as they complete
                for future in concurrent.futures.as_completed(futures):
                    audio_file = futures[future]
                    result = future.result()
                    results.append(result)
                    
                    progress.update(task, description=f"Completed {audio_file.name}")
                    progress.advance(task)
        
        return results
    
    def _transcribe_single(self, audio_file: Path) -> BatchResult:
        """Transcribe a single file."""
        start_time = time.time()
        
        try:
            # Transcribe
            result = transcribe_file_workflow(
                source=FileSource(audio_file),
                use_daemon=(self.daemon_mode in ["auto", "always"]),
                daemon_auto_start=(self.daemon_mode == "always"),
                progress=None,  # No nested progress bars
                **self.transcription_kwargs,
            )
            
            # Save output
            output_path = self. output_dir / f"{audio_file.stem}_transcript.txt"
            output_path.write_text(result.text)
            
            duration = time.time() - start_time
            
            return BatchResult(
                source_file=audio_file,
                success=True,
                transcript_text=result. text,
                output_path=output_path,
                duration_s=duration,
            )
        
        except Exception as e: 
            duration = time.time() - start_time
            
            logger.error(f"Failed to transcribe {audio_file}:  {e}")
            
            return BatchResult(
                source_file=audio_file,
                success=False,
                error=e,
                duration_s=duration,
            )
```

**Why This is Permanent:**

1. **Native command** (no shell scripting required)
2. **Parallel processing** option for speed
3. **Error handling** with continue-on-error
4. **Combined output** option
5. **Progress tracking** for entire batch
6. **Daemon integration** (always uses daemon for speed)

**Effort:** 8 hours  
**Files:**
- `vociferous/cli/commands/batch.py` (NEW)
- `vociferous/app/batch.py` (NEW)
- Register batch command in CLI main

---

## 📊 Summary:  Recommended Implementation Order

| Priority | Feature | Effort | User Impact | Dependencies |
|----------|---------|--------|-------------|--------------|
| 🥇 #1 | **First-time UX** | 8h | Critical | None |
| 🥇 #2 | **Refinement quality** | 4h | Critical | None |
| 🥇 #3 | **Progress feedback** | 6h | Critical | Rich library (already used) |
| 🥈 #4 | **Daemon auto-start** | 4h | Major | Progress feedback |
| 🥈 #5 | **Error messages** | 6h | Major | Rich library |
| 🥈 #6 | **Audio preprocessing** | 8h | Major | Progress feedback |
| 🥈 #7 | **Batch processing** | 8h | Major | Daemon auto-start, Progress |