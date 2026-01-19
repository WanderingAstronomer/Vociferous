# User View

The User View is a dedicated informational surface focusing on your journey with Vociferous.

---

## Overview

The User View provides:
- **Lifetime Statistics**: A dashboard of your dictation productivity.
- **Usage Insights**: Personalized analysis of your speaking vs. typing speed.
- **About Information**: Version details and documentation links.

<img src="https://raw.githubusercontent.com/WanderingAstronomer/Vociferous/main/docs/images/user_view.png" alt="User View" width="800" />

---

## Location

`src/ui/views/user_view.py`

**View ID:** `VIEW_USER` = `"user"`

---

## Metric Groups

The view organizes statistics into three semantic groups:

### 1. Productivity Impact
*   **Time Saved**: Estimated hours saved compared to manual typing (assuming approx. 40 WPM typing speed).
*   **Words Captured**: Total word count across all transcripts.

### 2. Usage & Activity
*   **Transcriptions**: Total count of recording sessions.
*   **Time Recorded**: Total duration of audio captured.
*   **Avg. Length**: Average duration per recording session.
*   **Total Silence**: Accumulated silence duration (pauses) within recordings.

### 3. Speech Quality
*   **Vocabulary**: Lexical complexity metric (unique words / total words).
*   **Avg. Pauses**: Average duration of silence between speech segments.
*   **Filler Words**: Count of detected disfluencies (um, uh, like, etc.).

---

## Insights Engine

The view generates dynamic insights based on your usage patterns:

*   **Speed Comparison**: Calculates the ratio between your speaking speed and average typing speed.
    *   *Example:* "Speaking 3.2x faster than typing—voice is your superpower!"
*   **Style Analysis**: Classifies your session style based on average duration.
    *   *Short bursts:* "Quick-capture style: rapid-fire notes and thoughts."
    *   *Long sessions:* "Deep-work style: long-form dictation sessions."

---

## Layout

The view uses a centered, scrollable layout with a "Journey" header.

1.  **Title Bar**: `Your Vociferous Journey` (or personalized if configured).
2.  **Stats Container**: Grouped metrics cards.
3.  **Methodology**: Collapsible explanation of how metrics are calculated.
4.  **Footer**: About links and version info.

---

## Capabilities

The User View is **read-only** and informational.

| Capability | Supported |
|------------|-----------|
| `can_edit` | No |
| `can_refresh` | Yes (Auto-refreshes on view activation) |

---

## See Also

- [View-History](View-History) — Where the data comes from
- [View-Settings](View-Settings) — Application configuration
- [Data-and-Persistence](Data-and-Persistence) — Underlying metrics data
