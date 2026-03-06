/**
 * Shared formatting utilities used across transcript-related views.
 *
 * Extracted from TranscriptsView and TranscribeView to eliminate duplication.
 */

/** Format a Date into a human-readable day header like "January 5th". */
export function formatDayHeader(dt: Date): string {
    const day = dt.getDate();
    let suffix: string;
    if (day >= 11 && day <= 13) suffix = "th";
    else suffix = ({ 1: "st", 2: "nd", 3: "rd" } as Record<number, string>)[day % 10] ?? "th";
    return dt.toLocaleDateString("en-US", { month: "long" }) + ` ${day}${suffix}`;
}

/** Format an ISO timestamp into a 12-hour time like "3:07 p.m.". */
export function formatTime(iso: string): string {
    const dt = new Date(iso);
    let h = dt.getHours();
    const m = dt.getMinutes();
    const period = h < 12 ? "a.m." : "p.m.";
    h = h % 12 || 12;
    return `${h}:${m.toString().padStart(2, "0")} ${period}`;
}

/** Format a duration in milliseconds to "Xm Ys" or "Xs". Returns "—" for non-positive values. */
export function formatDuration(ms: number): string {
    if (ms <= 0) return "—";
    const secs = Math.round(ms / 1000);
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

/** Format words-per-minute from word count and duration in ms. Returns "—" for invalid inputs. */
export function formatWpm(words: number, ms: number): string {
    if (ms <= 0 || words <= 0) return "—";
    return `${Math.round(words / (ms / 60000))} wpm`;
}

/** Count words in a string (split on whitespace, ignoring empties). */
export function wordCount(text: string): number {
    return text ? text.split(/\s+/).filter(Boolean).length : 0;
}
