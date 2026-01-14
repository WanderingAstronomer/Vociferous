from dataclasses import dataclass

@dataclass(slots=True)
class HistoryEntry:
    """
    Single transcription history entry with timestamp, text, and duration.
    DTO for UI consumption, mapped from Transcript model.
    """

    timestamp: str
    text: str
    duration_ms: int
    speech_duration_ms: int = 0
    focus_group_id: int | None = None
    id: int | None = None

    def to_display_string(self, max_length: int = 80) -> str:
        """Format for display in list widget: [HH:MM:SS] text preview..."""
        # Timestamp expected format: YYYY-MM-DDTHH:MM:SS.mmmmmm or similar
        try:
            timestamp_short = self.timestamp.split("T")[1][:8]  # HH:MM:SS
        except IndexError:
            timestamp_short = self.timestamp

        display_text = self.text.replace("\n", " ")
        if len(display_text) > max_length:
            display_text = display_text[:max_length] + "..."

        return f"[{timestamp_short}] {display_text}"
