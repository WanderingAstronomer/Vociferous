<body>

<h1 id="vociferous">Vociferous</h1>

<h3>Privacy-First Speech-to-Text for Linux</h3>

<p><em>Your voice. Your machine. Your data.</em></p>

<p>
    <a href="https://www.python.org/downloads/">
        <img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python 3.12+">
    </a>
    <a href="LICENSE">
        <img src="https://img.shields.io/badge/License-AGPL%20v3-blue.svg" alt="AGPL-3.0">
    </a>
    <a href="https://www.riverbankcomputing.com/software/pyqt/">
        <img src="https://img.shields.io/badge/GUI-PyQt6-green.svg" alt="PyQt6">
    </a>
    <a href="https://github.com/openai/whisper">
        <img src="https://img.shields.io/badge/ASR-OpenAI%20Whisper-orange.svg" alt="OpenAI Whisper">
    </a>
</p>

<img src="docs/images/transcribe_view.png" width="700" alt="Vociferous Main Interface">

<p>
    <a href="#features">Features</a> •
    <a href="#installation">Installation</a> •
    <a href="#quick-start">Quick Start</a> •
    <a href="#documentation">Documentation</a> •
    <a href="#architecture">Architecture</a>
</p>

<hr>

<h2>What is Vociferous?</h2>

<p>
    Vociferous is a production-grade, local-first dictation system that transforms speech into text entirely on your machine.
    Built with architectural rigor and attention to user experience, it leverages OpenAI's Whisper for state-of-the-art
    transcription and offers optional AI-powered refinement to polish your text with grammar correction and formatting.
</p>

<p>
    Unlike cloud-based alternatives, Vociferous processes everything locally—your voice never leaves your computer.
    No subscriptions, no usage limits, no privacy compromises.
</p>

<hr>

<h2 id="features">Features</h2>

<ul>
    <li><strong>Complete Privacy</strong> — All transcription and refinement happens on-device using local models</li>
    <li><strong>Whisper ASR</strong> — OpenAI's state-of-the-art speech recognition via <a href="https://github.com/SYSTRAN/faster-whisper">faster-whisper</a></li>
    <li><strong>AI Refinement</strong> — Optional SLM-powered text improvement (grammar, punctuation, formatting)</li>
    <li><strong>Native Linux Support</strong> — First-class Wayland integration with global hotkey support</li>
    <li><strong>Persistent History</strong> — SQLite-backed transcript storage with full-text search and organization</li>
    <li><strong>GPU Acceleration</strong> — CUDA support for real-time transcription and refinement</li>
    <li><strong>Modern UI</strong> — Sleek PyQt6 interface with polished design system</li>
    <li><strong>Intent-Driven Architecture</strong> — Clean separation between user intent and execution logic</li>
    <li><strong>Dual-Text Model</strong> — Preserves raw Whisper output while allowing user edits</li>
    <li><strong>Pluggable Backends</strong> — Modular input handling, model selection, and audio processing</li>
    <li><strong>Production-Ready</strong> — Comprehensive test suite, type safety, and architectural guardrails</li>
    <li><strong>Fully Offline</strong> — No internet connection required after initial model download</li>
</ul>

<hr>

<h2>Screenshots</h2>

<details>
<summary><strong>View Gallery (Click to expand)</strong></summary>

<table>
    <tr>
        <td align="center">
            <img src="docs/images/transcribe_view.png" width="400" alt="Transcribe View"><br>
            <em>Transcribe View — Live dictation and recording</em>
        </td>
        <td align="center">
            <img src="docs/images/history_view.png" width="400" alt="History View"><br>
            <em>History View — Browse and manage transcripts</em>
        </td>
    </tr>
    <tr>
        <td align="center">
            <img src="docs/images/search_and_manage_view.png" width="400" alt="Search View"><br>
            <em>Search &amp; Manage — Filter and organize</em>
        </td>
        <td align="center">
            <img src="docs/images/refinement_view.png" width="400" alt="Refine View"><br>
            <em>Refine View — AI-powered text improvement</em>
        </td>
    </tr>
    <tr>
        <td align="center">
            <img src="docs/images/settings_view.png" width="400" alt="Settings View"><br>
            <em>Settings View — Configure transcription and refinement</em>
        </td>
        <td align="center">
            <img src="docs/images/user_view.png" width="400" alt="User View"><br>
            <em>User View — Metrics and documentation</em>
        </td>
    </tr>
</table>

<h4>Onboarding Experience</h4>

<table>
    <tr>
        <td align="center">
            <img src="docs/images/onboarding_welcome.png" width="300" alt="Onboarding Welcome"><br>
            <em>Welcome screen</em>
        </td>
        <td align="center">
            <img src="docs/images/onboarding_transcription_model_choice.png" width="300" alt="Model Selection"><br>
            <em>Model selection</em>
        </td>
        <td align="center">
            <img src="docs/images/onboarding_choose_hotkey.png" width="300" alt="Hotkey Setup"><br>
            <em>Hotkey configuration</em>
        </td>
    </tr>
</table>
</details>

<hr>

<h2 id="installation">Installation</h2>

<h3>Prerequisites</h3>

<table border="1" cellpadding="6">
    <tr>
        <th>Requirement</th>
        <th>Minimum</th>
        <th>Recommended</th>
    </tr>
    <tr>
        <td><strong>OS</strong></td>
        <td>Linux (X11/Wayland)</td>
        <td>Linux (Wayland)</td>
    </tr>
    <tr>
        <td><strong>Python</strong></td>
        <td>3.12+</td>
        <td>3.12</td>
    </tr>
    <tr>
        <td><strong>RAM</strong></td>
        <td>4 GB</td>
        <td>8 GB</td>
    </tr>
    <tr>
        <td><strong>GPU</strong></td>
        <td>None (CPU mode)</td>
        <td>NVIDIA CUDA</td>
    </tr>
    <tr>
        <td><strong>VRAM</strong></td>
        <td>N/A</td>
        <td>4+ GB</td>
    </tr>
</table>

<h3>Wayland Setup</h3>

<pre><code>sudo usermod -a -G input $USER
# Log out and back in for changes to take effect</code></pre>

<h3>Install Steps</h3>

<ol>
    <li>Clone the repository</li>
</ol>

<pre><code>git clone https://github.com/yourusername/Vociferous.git
cd Vociferous</code></pre>

<ol start="2">
    <li>Create virtual environment</li>
</ol>

<pre><code>python3 -m venv .venv</code></pre>

<ol start="3">
    <li>Install dependencies</li>
</ol>

<pre><code>.venv/bin/pip install -r requirements.txt</code></pre>

<ol start="4">
    <li>Launch Vociferous</li>
</ol>

<pre><code>./vociferous</code></pre>

<p><strong>Important:</strong> Always use the <code>./vociferous</code> launcher script.</p>

<hr>

<h2 id="quick-start">Quick Start</h2>

<h3>Your First Recording</h3>

<ol>
    <li>Launch the application</li>
    <li>Press Right Alt to start recording</li>
    <li>Speak clearly</li>
    <li>Press Right Alt again to stop</li>
    <li>Wait for transcription</li>
    <li>Review your transcript</li>
</ol>

<hr>

<h2 id="documentation">Documentation</h2>

<p>Comprehensive documentation is available in the project wiki.</p>

<hr>

<h2 id="architecture">Architecture</h2>

<p>
    Vociferous follows a strict intent-driven design that enforces clean separation between user intent and execution.
</p>

<pre><code>User Action → Intent → Signal → Controller → Execution</code></pre>

<hr>

<h2>License</h2>

<p>
    This project is licensed under the <strong>AGPL-3.0</strong>.
</p>

<hr>

<div align="center">
    <strong>Built with love for the Linux community</strong><br>
    <a href="#vociferous">Back to Top</a>
</div>

</body>
