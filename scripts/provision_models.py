#!/usr/bin/env python3
"""
Model Provisioning CLI Tool (Wrapper)

This script is a wrapper around the core provisioning CLI.
It maintains backwards compatibility with existing usage patterns.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.provisioning.cli import app

if __name__ == "__main__":
    app()
