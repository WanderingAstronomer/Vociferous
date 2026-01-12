"""
MetricsExplanationDialog - Explains calculation methods for transcript metrics.

Shows detailed explanations of:
- Recording Time (raw duration)
- Speech Duration (VAD-filtered)
- Silence Ratio
- Words Per Minute
- Typing Time Saved
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.components.title_bar import DialogTitleBar
from ui.constants import Colors, Dimensions, Typography


class MetricsExplanationDialog(QDialog):
    """
    Dialog explaining how transcript metrics are calculated.

    Provides transparency about measurement methodology and assumptions.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setModal(True)
        self.setMinimumSize(700, 500)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Create the dialog layout."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Structural Frame Wrapper (The Dialog Frame)
        self._dialog_frame = QFrame()
        self._dialog_frame.setObjectName("dialogFrame")
        main_layout.addWidget(self._dialog_frame)

        # Frame layout
        frame_layout = QVBoxLayout(self._dialog_frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(0)

        # Title bar
        title_bar = DialogTitleBar("Metrics Calculations", self)
        title_bar.closeRequested.connect(self.reject)
        frame_layout.addWidget(title_bar)

        # Scrollable content area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("dialogContent")
        scroll.setStyleSheet(f"""
            QScrollArea {{
                background: {Colors.SURFACE};
                border: none;
            }}
            QScrollArea > QWidget > QWidget {{
                background: {Colors.SURFACE};
            }}
        """)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(20)
        layout.setContentsMargins(24, 20, 24, 20)

        # Introduction
        intro = self._create_text(
            "Vociferous tracks multiple time-based metrics to provide transparency "
            "about how dictation saves time compared to manual typing. Below are detailed "
            "explanations of each metric and how it's calculated.",
            is_intro=True,
        )
        layout.addWidget(intro)

        # Metric 1: Recording Time
        layout.addWidget(self._create_section_header("Recording Time (Raw Duration)"))
        layout.addWidget(
            self._create_text(
                "<b>What it measures:</b> Total time you spent recording, including speaking, "
                "thinking, pauses, and hesitations. This represents your actual <i>human cognitive time</i>."
            )
        )
        layout.addWidget(self._create_formula("Recording Time = Total Audio Length"))
        layout.addWidget(
            self._create_text(
                "Calculated from the raw audio buffer size divided by sample rate (16,000 Hz). "
                "This includes all silence and pauses — your full recording session from start to finish."
            )
        )

        # Metric 2: Speech Duration
        layout.addWidget(
            self._create_section_header("Speech Duration (Effective Speech)")
        )
        layout.addWidget(
            self._create_text(
                "<b>What it measures:</b> Time spent actually speaking, after silence/pause removal. "
                "This represents the <i>machine-usable content time</i>."
            )
        )
        layout.addWidget(
            self._create_formula("Speech Duration = Σ(segment.end - segment.start)")
        )
        layout.addWidget(
            self._create_text(
                "Calculated by summing all speech segments detected by Whisper's Voice Activity Detection (VAD). "
                "Each segment has a start and end timestamp; we add up all (end - start) durations. "
                "This excludes silence, breathing pauses, and gaps between words."
            )
        )

        # Metric 3: Silence Time
        layout.addWidget(self._create_section_header("Silence Time"))
        layout.addWidget(
            self._create_text(
                "<b>What it measures:</b> Absolute time spent thinking, pausing, or silent during recording. "
                "This makes your cognitive process visible and measurable."
            )
        )
        layout.addWidget(
            self._create_formula("Silence Time = Recording Time - Speech Duration")
        )
        layout.addWidget(
            self._create_text(
                "Calculated by subtracting Speech Duration (VAD-filtered active speech) from Recording Time (total session). "
                "This is the time you spent composing thoughts, choosing words, or breathing between phrases."
            )
        )
        layout.addWidget(
            self._create_text(
                "<b>Example:</b> 60s recording with 40s of speech → Silence Time = 60 - 40 = 20s<br>"
                "This means you spent 20 seconds thinking, which is <i>not waste</i> — it's cognition.",
                is_example=True,
            )
        )

        # Metric 4: Words Per Minute
        layout.addWidget(self._create_section_header("Words Per Minute"))
        layout.addWidget(
            self._create_text(
                "<b>What it measures:</b> Your <i>idea throughput</i> — how many words you produce per minute "
                "of recording time (including pauses). This is NOT speaking speed; it's cognitive productivity."
            )
        )
        layout.addWidget(
            self._create_formula("WPM = (Word Count / Recording Time in seconds) × 60")
        )
        layout.addWidget(
            self._create_text(
                "Word count is calculated by splitting the transcript on whitespace. "
                "We use <i>Recording Time</i> (not Speech Duration) because your thinking/pause time is part of "
                "the content creation process."
            )
        )

        # Metric 5: Typing Time Saved
        layout.addWidget(self._create_section_header("Typing Time Saved"))
        layout.addWidget(
            self._create_text(
                "<b>What it measures:</b> Time saved compared to manually typing the same content. "
                "Uses explicit assumption about your typing speed."
            )
        )
        layout.addWidget(
            self._create_formula(
                "Typing Time = (Word Count / 40 WPM) × 60<br>"
                "Time Saved = Typing Time - Recording Time"
            )
        )
        layout.addWidget(
            self._create_text(
                "<b>Assumption:</b> Average typing speed during composition = 40 words per minute. "
                "This is slower than pure typing tests because it includes thinking time while typing."
            )
        )
        layout.addWidget(
            self._create_text(
                "<b>Example:</b> 120 words dictated in 50 seconds:<br>"
                "• Typing would take: (120 / 40) × 60 = 180 seconds (3 minutes)<br>"
                "• You took: 50 seconds<br>"
                "• Time saved: 180 - 50 = 130 seconds (2m 10s)",
                is_example=True,
            )
        )

        # Metric 6: Speaking Rate
        layout.addWidget(self._create_section_header("Speaking Rate"))
        layout.addWidget(
            self._create_text(
                "<b>What it measures:</b> Your actual speaking speed when you're actively talking, "
                "excluding all pauses and silence. This shows how fast you articulate when speech is happening."
            )
        )
        layout.addWidget(
            self._create_formula(
                "Speaking Rate = (Word Count / Speech Duration in seconds) × 60"
            )
        )
        layout.addWidget(
            self._create_text(
                "Calculated using <i>Speech Duration</i> (VAD-filtered time) instead of Recording Time. "
                "This isolates pure articulation speed from cognitive pauses."
            )
        )
        layout.addWidget(
            self._create_text(
                "<b>Comparison:</b><br>"
                "• <b>Words/Min</b> = overall productivity (includes thinking)<br>"
                "• <b>Speaking Rate</b> = pure speech velocity (excludes thinking)<br><br>"
                "<b>Example:</b> 100 words in 60s total, but only 40s of actual speech:<br>"
                "• Words/Min = 100 WPM (productivity)<br>"
                "• Speaking Rate = 150 WPM (articulation speed)",
                is_example=True,
            )
        )

        # Philosophy note
        layout.addWidget(self._create_section_header("Design Philosophy"))
        layout.addWidget(
            self._create_text(
                "<b>Silence is not waste — it's cognition.</b> Vociferous tracks both human time "
                "(thinking + speaking) and machine time (pure speech) to give you a complete picture. "
                "We never hide your pause time; instead, we measure it explicitly as part of your "
                "creative process.",
                is_philosophy=True,
            )
        )

        layout.addStretch()

        scroll.setWidget(content)
        frame_layout.addWidget(scroll)

    def _create_section_header(self, text: str) -> QLabel:
        """Create a section header label."""
        label = QLabel(text)
        label.setStyleSheet(f"""
            color: {Colors.TEXT_PRIMARY};
            font-size: {Typography.FONT_SIZE_BASE}px;
            font-weight: {Typography.FONT_WEIGHT_EMPHASIS};
            padding-top: 8px;
        """)
        label.setWordWrap(True)
        return label

    def _create_text(
        self,
        text: str,
        is_intro: bool = False,
        is_example: bool = False,
        is_philosophy: bool = False,
    ) -> QLabel:
        """Create a body text label."""
        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.RichText)

        if is_intro:
            style = f"""
                color: {Colors.TEXT_PRIMARY};
                font-size: {Typography.FONT_SIZE_SM}px;
                line-height: 1.5;
                background: {Colors.SURFACE_ALT};
                padding: 12px;
                border-radius: {Dimensions.BORDER_RADIUS_SM}px;
            """
        elif is_example:
            style = f"""
                color: {Colors.TEXT_SECONDARY};
                font-size: {Typography.FONT_SIZE_SM}px;
                line-height: 1.6;
                background: {Colors.BACKGROUND};
                padding: 10px;
                border-left: 3px solid {Colors.PRIMARY};
                font-family: monospace;
            """
        elif is_philosophy:
            style = f"""
                color: {Colors.TEXT_PRIMARY};
                font-size: {Typography.FONT_SIZE_SM}px;
                line-height: 1.5;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(90, 159, 212, 0.2),
                    stop:1 {Colors.SURFACE});
                padding: 12px;
                border-radius: {Dimensions.BORDER_RADIUS_SM}px;
                border-left: 3px solid {Colors.PRIMARY};
            """
        else:
            style = f"""
                color: {Colors.TEXT_SECONDARY};
                font-size: {Typography.FONT_SIZE_SM}px;
                line-height: 1.5;
            """

        label.setStyleSheet(style)
        return label

    def _create_formula(self, formula: str) -> QLabel:
        """Create a formula display label."""
        label = QLabel(formula)
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setStyleSheet(f"""
            color: {Colors.PRIMARY};
            font-size: {Typography.FONT_SIZE_SM}px;
            font-family: 'Courier New', monospace;
            background: {Colors.BACKGROUND};
            padding: 10px 16px;
            border-radius: {Dimensions.BORDER_RADIUS_SM}px;
            border: 1px solid rgba(90, 159, 212, 0.33);
        """)
        return label
