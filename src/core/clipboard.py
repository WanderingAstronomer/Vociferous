"""
Platform-native clipboard helper.

Uses CLI tools so it works without window focus and without pulling in a GUI
toolkit dependency. Linux requires xclip or xsel.
"""

from __future__ import annotations

import logging
import platform
import subprocess

logger = logging.getLogger(__name__)


def copy_to_system_clipboard(text: str) -> None:
    """Copy text to the system clipboard using platform-native CLI tools."""
    system = platform.system()
    try:
        if system == "Linux":
            for cmd in (
                ["xclip", "-selection", "clipboard"],
                ["xsel", "--clipboard", "--input"],
            ):
                try:
                    subprocess.run(cmd, input=text.encode("utf-8"), check=True, timeout=3)
                    logger.debug("Copied %d chars to clipboard via %s", len(text), cmd[0])
                    return
                except FileNotFoundError:
                    continue
            logger.warning("No clipboard tool found (install xclip or xsel)")
        elif system == "Darwin":
            subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True, timeout=3)
            logger.debug("Copied %d chars to clipboard via pbcopy", len(text))
        elif system == "Windows":
            subprocess.run(["clip.exe"], input=text.encode("utf-16le"), check=True, timeout=3)
            logger.debug("Copied %d chars to clipboard via clip.exe", len(text))
        else:
            logger.warning("Auto-copy not supported on %s", system)
    except Exception:
        logger.warning("Failed to copy to system clipboard", exc_info=True)
