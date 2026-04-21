/**
 * UserView metrics — pure derivation utilities (ISS-116).
 *
 * Extracts the metric computation that previously lived inline inside
 * `frontend/src/views/UserView.svelte` so it can be unit tested without
 * mounting the view component.
 *
 * Every function here is pure: given the same inputs it returns the same
 * output, has no side effects, and does not touch global state. The view
 * remains responsible for `$derived` wiring, formatting, and rendering.
 */

import type { Transcript } from "./api";
import { fleschKincaidGrade, countFillers, countFillersByWord } from "./textAnalysis";

export const SPEAKING_SPEED_WPM = 150;
export const DEFAULT_TYPING_WPM = 40;

const PUNCT_TRIM_RE = /^[.,!?;:'"()\[\]{}]+|[.,!?;:'"()\[\]{}]+$/g;

function safeText(e: { text?: string }): string {
    return e.text || "";
}

function wordCount(text: string): number {
    return text.split(/\s+/).filter(Boolean).length;
}

export function totalWords(entries: Transcript[]): number {
    return entries.reduce((s, e) => s + wordCount(safeText(e)), 0);
}

export function recordedSeconds(entries: Transcript[], words: number): number {
    const dur = entries.reduce((s, e) => s + (e.duration_ms || 0), 0) / 1000;
    if (dur > 0) return dur;
    if (words > 0) return (words / SPEAKING_SPEED_WPM) * 60;
    return 0;
}

export function typingSeconds(words: number, typingWpm: number): number {
    if (typingWpm <= 0) return 0;
    return (words / typingWpm) * 60;
}

export function timeSavedSeconds(words: number, typingWpm: number, recorded: number): number {
    return Math.max(0, typingSeconds(words, typingWpm) - recorded);
}

export function totalSpeechSeconds(entries: Transcript[]): number {
    let total = 0;
    for (const e of entries) {
        if (e.speech_duration_ms > 0) {
            total += e.speech_duration_ms / 1000;
        } else if (e.duration_ms > 0) {
            const w = wordCount(safeText(e));
            total += Math.min((w / SPEAKING_SPEED_WPM) * 60, e.duration_ms / 1000);
        }
    }
    return total;
}

export function avgWpm(words: number, speechSeconds: number): number {
    return speechSeconds > 0 ? Math.round((words / speechSeconds) * 60) : 0;
}

export function totalSilenceSeconds(entries: Transcript[]): number {
    let total = 0;
    for (const e of entries) {
        if (e.duration_ms && e.duration_ms > 0) {
            const dur = e.duration_ms / 1000;
            const speech = (e.speech_duration_ms || 0) / 1000;
            total += Math.max(0, dur - speech);
        }
    }
    return total;
}

export function avgSilenceSeconds(entries: Transcript[]): number {
    let total = 0;
    let withDuration = 0;
    for (const e of entries) {
        if (e.duration_ms && e.duration_ms > 0) {
            const dur = e.duration_ms / 1000;
            const speech = (e.speech_duration_ms || 0) / 1000;
            total += Math.max(0, dur - speech);
            withDuration++;
        }
    }
    return withDuration > 0 ? total / withDuration : 0;
}

export function fillerCount(entries: Transcript[]): number {
    let total = 0;
    for (const e of entries) total += countFillers(safeText(e));
    return total;
}

export function fillerBreakdown(entries: Transcript[]): [string, number][] {
    const agg: Record<string, number> = {};
    for (const e of entries) {
        for (const [word, wc] of Object.entries(countFillersByWord(safeText(e)))) {
            agg[word] = (agg[word] || 0) + wc;
        }
    }
    return Object.entries(agg)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5);
}

export function vocabularyRatio(entries: Transcript[]): number {
    const allWords: string[] = [];
    for (const e of entries) {
        for (const w of safeText(e).toLowerCase().split(/\s+/)) {
            const c = w.replace(PUNCT_TRIM_RE, "");
            if (c) allWords.push(c);
        }
    }
    if (allWords.length === 0) return 0;
    return new Set(allWords).size / allWords.length;
}

export interface Streaks {
    current: number;
    longest: number;
}

export function streaks(entries: Transcript[], today: number = Math.floor(Date.now() / 86400000)): Streaks {
    const dates = new Set<number>();
    for (const e of entries) {
        try {
            const d = new Date(e.created_at);
            if (!isNaN(d.getTime())) {
                dates.add(Math.floor(d.getTime() / 86400000));
            }
        } catch {
            /* skip */
        }
    }

    let current = 0;
    let longest = 0;

    if (dates.size > 0) {
        let d = today;
        while (dates.has(d)) {
            current++;
            d--;
        }

        const sorted = [...dates].sort((a, b) => a - b);
        let run = 1;
        for (let i = 1; i < sorted.length; i++) {
            if (sorted[i] === sorted[i - 1] + 1) {
                run++;
            } else {
                longest = Math.max(longest, run);
                run = 1;
            }
        }
        longest = Math.max(longest, run);
    }

    return { current, longest };
}

export function refinedEntries(entries: Transcript[]): Transcript[] {
    return entries.filter((e) => e.normalized_text && e.normalized_text !== e.raw_text);
}

export function verbatimFillerCount(entries: Transcript[]): number {
    let total = 0;
    for (const e of entries) total += countFillers(e.raw_text || "");
    return total;
}

export function rawFillersInRefined(refined: Transcript[]): number {
    let total = 0;
    for (const e of refined) total += countFillers(e.raw_text || "");
    return total;
}

export function refinedFillerCount(refined: Transcript[]): number {
    let total = 0;
    for (const e of refined) total += countFillers(e.normalized_text || "");
    return total;
}

function avgFkGradeOver(texts: string[]): number {
    const grades = texts.map((t) => fleschKincaidGrade(t)).filter((g) => g > 0);
    if (!grades.length) return 0;
    return Math.round((grades.reduce((s, g) => s + g, 0) / grades.length) * 10) / 10;
}

export function verbatimAvgFkGrade(entries: Transcript[]): number {
    return avgFkGradeOver(entries.map((e) => e.raw_text || ""));
}

export function refinedAvgFkGrade(refined: Transcript[]): number {
    return avgFkGradeOver(refined.map((e) => e.normalized_text || ""));
}

export function verbatimFkForRefined(refined: Transcript[]): number {
    return avgFkGradeOver(refined.map((e) => e.raw_text || ""));
}

export function totalTranscriptionSeconds(entries: Transcript[]): number {
    let total = 0;
    for (const e of entries) total += e.transcription_time_ms || 0;
    return total / 1000;
}

export function totalRefinementSeconds(entries: Transcript[]): number {
    let total = 0;
    for (const e of entries) total += e.refinement_time_ms || 0;
    return total / 1000;
}

export function avgTranscriptionSpeedX(recorded: number, transcriptionTime: number): number {
    if (transcriptionTime <= 0 || recorded <= 0) return 0;
    return Math.round((recorded / transcriptionTime) * 10) / 10;
}

export function avgRefinementWpm(refined: Transcript[], refinementSeconds: number): number {
    if (refinementSeconds <= 0) return 0;
    const refinedWords = refined.reduce((s, e) => s + wordCount(safeText(e)), 0);
    return Math.round(refinedWords / (refinementSeconds / 60));
}

/**
 * Refinement time saved: manual editing time minus actual SLM time.
 * Manual editing speed ≈ typing_wpm / 2 (reading + restructuring).
 */
export function refinementTimeSaved(
    refined: Transcript[],
    typingWpm: number,
    refinementSeconds: number,
): number {
    if (refined.length === 0) return 0;
    const refinedWords = refined.reduce((s, e) => s + wordCount(safeText(e)), 0);
    if (refinedWords === 0) return 0;
    const manualEditWpm = Math.max(1, typingWpm / 2);
    const manualSeconds = (refinedWords / manualEditWpm) * 60;
    return Math.max(0, manualSeconds - refinementSeconds);
}
