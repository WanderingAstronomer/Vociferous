"""
Text injection module for Vociferous.

This module handles the \"last mile\" of dictation - taking transcribed text
and injecting it into the currently focused application as if typed.

The Problem:
------------
Modern Linux has multiple display protocols (X11, Wayland), each with
different approaches to input simulation. What works on X11 doesn't work
on Wayland, and vice versa. This module abstracts those differences.

Supported Backends:
-------------------
```
┌─────────────────────────────────────────────────────────────────┐
│                     InputSimulator                              │
├─────────────────────────────────────────────────────────────────┤
│  Backend     │  Protocol  │  How It Works                       │
├──────────────┼────────────┼─────────────────────────────────────┤
│  pynput      │  X11       │  XTEST extension, synthetic events  │
│  ydotool     │  Wayland   │  Virtual /dev/uinput device         │
│  dotool      │  Wayland   │  Same as ydotool, persistent proc   │
│  clipboard   │  Any       │  Copy to clipboard (manual paste)   │
└─────────────────────────────────────────────────────────────────┘
```

Why So Many Backends?
---------------------

**X11 (pynput)**: The X11 protocol allows any app to send synthetic
key events. This is convenient but insecure (keyloggers can do the same).
pynput uses the XTEST extension, which is simple and reliable.

**Wayland (ydotool/dotool)**: Wayland's security model prevents apps
from sending arbitrary input. The workaround is to create a virtual
input device (/dev/uinput), which requires either:
- Running ydotoold as a daemon (ydotool)
- Root permissions or uinput group membership

**Clipboard fallback**: When nothing else works, we copy to clipboard
and let the user paste. Less elegant but universally compatible.

dotool vs ydotool:
------------------
Both use uinput, but:
- **ydotool**: Spawns new process per command (slow for many chars)
- **dotool**: Keeps process alive, writes commands to stdin (fast)

We use dotool when available because it's faster for streaming text.

Process Management Pattern:
---------------------------
The dotool backend demonstrates proper subprocess handling:

```python
self.dotool_process = subprocess.Popen(
    \"dotool\",
    stdin=subprocess.PIPE,  # We write commands here
    text=True               # Text mode (not bytes)
)
```

On cleanup:
1. Close stdin (signals EOF to dotool)
2. terminate() for graceful shutdown
3. wait() with timeout
4. kill() if needed
5. Final wait() to reap and avoid zombie processes

contextlib.suppress Pattern:
----------------------------
```python
with suppress(ProcessLookupError, OSError):
    proc.terminate()
```

This is cleaner than try/except/pass for expected exceptions.
It's saying \"I know this might fail, and that's OK.\"

Python 3.12+ Features:
----------------------
- Match/case for backend selection
- `subprocess.Popen | None` union type hints
- contextlib.suppress for clean exception handling
"""
import logging
import subprocess
import time
from contextlib import suppress

from pynput.keyboard import Controller as PynputController

from utils import ConfigManager

# Optional clipboard support
try:
    import pyperclip
    HAS_PYPERCLIP = True
except ImportError:
    HAS_PYPERCLIP = False

logger = logging.getLogger(__name__)


class InputSimulator:
    """
    Simulates keyboard input to inject transcribed text into applications.

    This class abstracts the complexity of text injection across different
    Linux display servers and provides a unified interface.

    Initialization Pattern:
    -----------------------
    Uses match/case for backend selection:

    ```python
    match self.input_method:
        case 'pynput':
            self.keyboard = PynputController()
        case 'dotool':
            self._initialize_dotool()
    ```

    This is cleaner than if/elif and makes it easy to add new backends.

    Backend Fallback Chain:
    -----------------------
    When a backend fails, we gracefully degrade:
    1. Try configured backend
    2. If error, fall back to clipboard
    3. If pyperclip unavailable, try wl-copy
    4. If all fail, log error (text is lost)

    Attributes:
        input_method: Current backend name ('pynput', 'ydotool', 'dotool', 'clipboard')
        dotool_process: Persistent subprocess for dotool backend (or None)
        keyboard: pynput Controller instance (or None if using other backend)
    """

    def __init__(self) -> None:
        self.input_method: str = ConfigManager.get_config_value(
            'output_options', 'input_method'
        ) or 'pynput'
        self.dotool_process: subprocess.Popen | None = None
        self.keyboard: PynputController | None = None

        match self.input_method:
            case 'pynput':
                self.keyboard = PynputController()
            case 'dotool':
                self._initialize_dotool()

        ConfigManager.console_print(f'Input method: {self.input_method}')

    def _initialize_dotool(self) -> None:
        """Initialize dotool process for persistent Wayland input."""
        try:
            self.dotool_process = subprocess.Popen(
                "dotool",
                stdin=subprocess.PIPE,
                text=True
            )
        except FileNotFoundError:
            logger.warning('dotool not found, falling back to pynput')
            self.input_method = 'pynput'
            self.keyboard = PynputController()

    def _terminate_dotool(self) -> None:
        """
        Terminate dotool subprocess safely, preventing zombie processes.

        Zombie Prevention Pattern:
        --------------------------
        A zombie process is one that has exited but whose parent hasn't
        called wait() to read its exit status. The kernel keeps it around.

        Our termination sequence:
        1. Clear self.dotool_process immediately (no double-terminate)
        2. Close stdin (dotool sees EOF, may exit cleanly)
        3. terminate() sends SIGTERM (polite "please exit")
        4. wait(timeout=0.5) gives it 500ms to comply
        5. kill() sends SIGKILL if still alive (forceful)
        6. Final wait() reaps the process (critical for no zombie)

        The `suppress()` blocks handle races where the process might
        exit between our checks - expected, not an error.
        """
        if self.dotool_process is None:
            return

        proc = self.dotool_process
        self.dotool_process = None  # Clear reference immediately

        with suppress(ProcessLookupError, OSError):
            # Close stdin first to signal EOF
            if proc.stdin:
                with suppress(OSError, BrokenPipeError):
                    proc.stdin.close()

            # Graceful termination with timeout
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()  # Reap to avoid zombie

    def typewrite(self, text: str) -> None:
        """
        Type the given text using the configured input method.

        This is the main entry point for text injection. It dispatches
        to the appropriate backend based on configuration.

        Dispatch Pattern:
        -----------------
        ```python
        match self.input_method:
            case 'pynput':   self._typewrite_pynput(text, interval)
            case 'ydotool':  self._typewrite_ydotool(text, interval)
            case 'dotool':   self._typewrite_dotool(text, interval)
            case 'clipboard': self._copy_to_clipboard(text)
        ```

        This structural pattern matching is exhaustive - if a new backend
        is added to config but not here, it will fall through (doing nothing).
        Adding a `case _:` default would catch that.

        Key Press Delay:
        ----------------
        The `interval` parameter controls delay between keystrokes.
        This is important because:
        - Too fast: Some apps drop characters
        - Too slow: User waits forever
        - Default 5ms is a good balance

        Args:
            text: The text to type into the focused application
        """
        if not text:
            return

        interval: float = ConfigManager.get_config_value(
            'output_options', 'writing_key_press_delay'
        ) or 0.005

        match self.input_method:
            case 'pynput':
                self._typewrite_pynput(text, interval)
            case 'ydotool':
                self._typewrite_ydotool(text, interval)
            case 'dotool':
                self._typewrite_dotool(text, interval)
            case 'clipboard':
                self._copy_to_clipboard(text)

    def _typewrite_pynput(self, text: str, interval: float) -> None:
        """Type using pynput (X11)."""
        for char in text:
            self.keyboard.press(char)
            self.keyboard.release(char)
            time.sleep(interval)

    def _typewrite_ydotool(self, text: str, interval: float) -> None:
        """Type using ydotool (Wayland)."""
        try:
            subprocess.run([
                "ydotool", "type",
                "--key-delay", str(int(interval * 1000)),
                "--", text
            ], check=True, capture_output=True)
        except FileNotFoundError:
            logger.error('ydotool not found! Install with: sudo pacman -S ydotool')
        except subprocess.CalledProcessError as e:
            logger.warning(f'ydotool error: {e}. Falling back to clipboard.')
            self._copy_to_clipboard(text)

    def _typewrite_dotool(self, text: str, interval: float) -> None:
        """Type using dotool (Wayland, persistent process)."""
        if not self.dotool_process or not self.dotool_process.stdin:
            logger.warning('dotool stdin unavailable, falling back to clipboard')
            self._copy_to_clipboard(text)
            return

        try:
            self.dotool_process.stdin.write(f"typedelay {int(interval * 1000)}\
")
            self.dotool_process.stdin.write(f"type {text}\
")
            self.dotool_process.stdin.flush()
        except Exception as e:
            logger.warning(f'dotool error: {e}. Falling back to clipboard.')
            self._copy_to_clipboard(text)

    def _copy_to_clipboard(self, text: str) -> None:
        """Copy text to clipboard using pyperclip or wl-copy."""
        if not text:
            return

        if HAS_PYPERCLIP:
            with suppress(Exception):
                pyperclip.copy(text)
                ConfigManager.console_print('Copied transcription to clipboard.')
                return

        try:
            subprocess.run(["wl-copy"], input=text, text=True, check=True)
            ConfigManager.console_print('Copied transcription to clipboard via wl-copy.')
        except Exception:
            logger.error('Clipboard copy failed. Install wl-clipboard or pyperclip.')

    def cleanup(self) -> None:
        """Clean up resources."""
        if self.input_method == 'dotool':
            self._terminate_dotool()
