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

/**
 * Smart relative date for transcript cards.
 *
 * - < 1 min : "just now"
 * - < 60 min: "14m ago"
 * - < 24 h  : "6h ago"
 * - Yesterday: "Yesterday 3:07 PM"
 * - This week: "Mon 3:07 PM"
 * - This year: "Mar 7"
 * - Older    : "Mar 7, 2025"
 */
export function formatRelativeDate(iso: string): string {
    const dt = new Date(iso);
    const now = new Date();
    const diffMs = now.getTime() - dt.getTime();
    const diffMin = Math.floor(diffMs / 60_000);
    const diffH = Math.floor(diffMs / 3_600_000);

    if (diffMin < 1) return "just now";
    if (diffMin < 60) return `${diffMin}m ago`;
    if (diffH < 24) return `${diffH}h ago`;

    const time = dt.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });

    // Check "yesterday"
    const yesterday = new Date(now);
    yesterday.setDate(now.getDate() - 1);
    if (
        dt.getDate() === yesterday.getDate() &&
        dt.getMonth() === yesterday.getMonth() &&
        dt.getFullYear() === yesterday.getFullYear()
    ) {
        return `Yesterday ${time}`;
    }

    // Same week (within 7 days, but not yesterday)
    if (diffH < 168) {
        const day = dt.toLocaleDateString("en-US", { weekday: "short" });
        return `${day} ${time}`;
    }

    // Same year: "Mar 7"
    if (dt.getFullYear() === now.getFullYear()) {
        return dt.toLocaleDateString("en-US", { month: "short", day: "numeric" });
    }

    // Older: "Mar 7, 2025"
    return dt.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

/**
 * Format a duration in milliseconds.
 * - Under 60s: "42s"
 * - Under 10 min: "4m 12s"
 * - 10 min or more: "22m" (seconds dropped — noise at this scale)
 * Returns "—" for non-positive values.
 */
export function formatDuration(ms: number): string {
    if (ms <= 0) return "—";
    const secs = Math.round(ms / 1000);
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    if (m === 0) return `${s}s`;
    if (m < 10) return `${m}m ${s}s`;
    return `${m}m`;
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
