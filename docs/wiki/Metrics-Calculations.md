# Metrics & Calculations

Vociferous provides real-time feedback on your dictation productivity using a specific set of algorithms and assumptions.

## Core Metrics

### 1. Recording Time (Raw Duration)
*   **Definition**: The total wall-clock time from the moment Recording started to when it stopped.
*   **Significance**: Represents the total cognitive "cost" of the task (thinking + speaking + pausing).
*   **Source**: Measured by the audio thread.

### 2. Speech Duration (Machine Time)
*   **Definition**: The amount of time actual voice content was detected.
*   **Source**: Calculated by the WebRTC Voice Activity Detector (VAD).
*   **Significance**: Represents the density of the dictation. High Speech Duration with low Recording Time means rapid-fire dictation.

### 3. Silence Ratio (Thinking Time)
*   **Definition**: The percentage of recording time spent in silence.
*   **Formula**: `(Recording Time - Speech Duration) / Recording Time`
*   **Significance**: Proxy for cognitive load. High silence indicates complex composition; low silence indicates stream-of-consciousness or transcription.

### 4. Words Per Minute (WPM)
*   **Definition**: The rate of idea generation.
*   **Formula**: `Word Count / (Recording Time in Minutes)`
*   **Note**: We use Recording Time (not Speech Duration) because thinking time is part of the composition process.

### 5. Time Saved (vs. Manual Typing)
*   **Definition**: Estimates productivity gain compared to typing the same text manually.
*   **Assumption**: Manual entry speed = **40 WPM** (average composition speed, including corrections).
*   **Formula**: `(Word Count / 40) - (Recording Time in Minutes)`
*   **Result**: Displays time saved in minutes/seconds. If negative, it implies typing would have been faster.

## Implementation Details

*   **Word Count**: Calculated by simple whitespace splitting of the transcribed text.
*   **Update Frequency**: Metrics update immediately upon transcription completion.
*   **Storage**: 
    *   `duration_ms`: Stored in DB (Recording Time)
    *   `speech_duration_ms`: Stored in DB (Speech Duration)
    *   All other metrics are derived dynamically at runtime.

## References

*   **Average Composition Speed**: ~40 WPM is used as a conservative baseline for "thoughtful typing" (composition), distinguishing it from "transcription typing" (which can be 60-80+ WPM).
