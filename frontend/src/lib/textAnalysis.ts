/**
 * Text analysis utilities — readability metrics, syllable counting, etc.
 *
 * TypeScript mirror of src/core/text_analysis.py so the frontend can compute
 * per-transcript metrics client-side from raw_text and normalized_text.
 */

// ---------------------------------------------------------------------------
// Syllable estimation
// ---------------------------------------------------------------------------

const VOWEL_GROUPS = /[aeiouy]+/gi;
const SILENT_E = /[^l]e$/i;
const TRAILING_ES_ED = /(?:es|ed)$/i;

/** Estimate syllable count for an English word (heuristic). */
export function estimateSyllables(word: string): number {
    let w = word.trim().toLowerCase().replace(/[^a-z]/g, "");
    if (!w) return 0;

    const matches = w.match(VOWEL_GROUPS);
    let count = matches ? matches.length : 0;

    if (SILENT_E.test(w)) count--;
    if (TRAILING_ES_ED.test(w) && w.length > 3) count--;

    return Math.max(count, 1);
}

// ---------------------------------------------------------------------------
// Sentence splitting
// ---------------------------------------------------------------------------

const SENTENCE_BOUNDARY = /(?<=[.!?])\s+/;

/** Split text into sentences. Falls back to one sentence if no punctuation. */
export function splitSentences(text: string): string[] {
    const trimmed = text?.trim();
    if (!trimmed) return [];
    const sentences = trimmed.split(SENTENCE_BOUNDARY).filter((s) => s.trim());
    return sentences.length ? sentences : [trimmed];
}

// ---------------------------------------------------------------------------
// Flesch-Kincaid Grade Level
// ---------------------------------------------------------------------------

/** Compute Flesch-Kincaid Grade Level. Returns 0 for empty/degenerate input. */
export function fleschKincaidGrade(text: string): number {
    const sentences = splitSentences(text);
    if (!sentences.length) return 0;

    const words = text.split(/\s+/).filter(Boolean);
    if (!words.length) return 0;

    const totalSyllables = words.reduce((s, w) => s + estimateSyllables(w), 0);
    const grade = 0.39 * (words.length / sentences.length) + 11.8 * (totalSyllables / words.length) - 15.59;

    return Math.round(Math.min(Math.max(grade, 0), 20) * 10) / 10;
}

// ---------------------------------------------------------------------------
// Filler word detection
// ---------------------------------------------------------------------------

const FILLER_SINGLE = new Set([
    "um",
    "uh",
    "uhm",
    "umm",
    "er",
    "err",
    "like",
    "basically",
    "literally",
    "actually",
    "so",
    "well",
    "right",
    "okay",
]);
const FILLER_MULTI = ["you know", "i mean", "kind of", "sort of"];

/** Count filler words and phrases in a string. */
export function countFillers(text: string): number {
    if (!text) return 0;
    const lower = text.toLowerCase();
    let count = 0;

    // Multi-word fillers
    for (const phrase of FILLER_MULTI) {
        let idx = 0;
        while ((idx = lower.indexOf(phrase, idx)) !== -1) {
            count++;
            idx += phrase.length;
        }
    }

    // Single-word fillers
    for (const w of lower.split(/\s+/)) {
        const c = w.replace(/^[.,!?;:'"()\[\]{}]+|[.,!?;:'"()\[\]{}]+$/g, "");
        if (FILLER_SINGLE.has(c)) count++;
    }

    return count;
}

/** Per-filler breakdown: returns { word_or_phrase: count } for fillers that appear. */
export function countFillersByWord(text: string): Record<string, number> {
    if (!text) return {};
    const lower = text.toLowerCase();
    const breakdown: Record<string, number> = {};

    for (const phrase of FILLER_MULTI) {
        let idx = 0;
        while ((idx = lower.indexOf(phrase, idx)) !== -1) {
            breakdown[phrase] = (breakdown[phrase] || 0) + 1;
            idx += phrase.length;
        }
    }

    for (const w of lower.split(/\s+/)) {
        const c = w.replace(/^[.,!?;:'"()\[\]{}]+|[.,!?;:'"()\[\]{}]+$/g, "");
        if (FILLER_SINGLE.has(c)) {
            breakdown[c] = (breakdown[c] || 0) + 1;
        }
    }

    return breakdown;
}

// ---------------------------------------------------------------------------
// Composite text metrics
// ---------------------------------------------------------------------------

export interface TextMetrics {
    wordCount: number;
    sentenceCount: number;
    avgSentenceLength: number;
    avgWordLength: number;
    longWordRatio: number;
    fkGrade: number;
    fillerCount: number;
    fillerDensity: number;
}

/** Compute all text metrics for a block of text. */
export function computeTextMetrics(text: string): TextMetrics {
    if (!text?.trim()) {
        return {
            wordCount: 0,
            sentenceCount: 0,
            avgSentenceLength: 0,
            avgWordLength: 0,
            longWordRatio: 0,
            fkGrade: 0,
            fillerCount: 0,
            fillerDensity: 0,
        };
    }

    const words = text.split(/\s+/).filter(Boolean);
    const wc = words.length;
    const sentences = splitSentences(text);
    const sc = sentences.length;

    const cleaned = words.map((w) => w.replace(/[^a-zA-Z]/g, "")).filter(Boolean);
    const totalChars = cleaned.reduce((s, c) => s + c.length, 0);
    const longWords = cleaned.filter((c) => c.length > 6).length;
    const fillers = countFillers(text);

    return {
        wordCount: wc,
        sentenceCount: sc,
        avgSentenceLength: sc ? Math.round((wc / sc) * 10) / 10 : 0,
        avgWordLength: cleaned.length ? Math.round((totalChars / cleaned.length) * 10) / 10 : 0,
        longWordRatio: cleaned.length ? Math.round((longWords / cleaned.length) * 1000) / 1000 : 0,
        fkGrade: fleschKincaidGrade(text),
        fillerCount: fillers,
        fillerDensity: wc ? Math.round((fillers / wc) * 10000) / 10000 : 0,
    };
}



