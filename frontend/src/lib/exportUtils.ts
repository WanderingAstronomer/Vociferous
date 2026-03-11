/**
 * Shared export formatting utilities.
 * Used by both MaintenanceCard (bulk "Export All") and TranscriptsView (contextual export).
 */
import type { Transcript } from "./api";

export type ExportFormat = "json" | "csv" | "txt" | "md";

function escapeCsvValue(value: unknown): string {
    const text = String(value ?? "").replace(/"/g, '""');
    return `"${text}"`;
}

function formatDurationHuman(ms: number): string {
    if (ms <= 0) return "—";
    const secs = Math.round(ms / 1000);
    if (secs < 60) return `${secs}s`;
    const mins = Math.floor(secs / 60);
    const rem = secs % 60;
    return rem > 0 ? `${mins}m ${rem}s` : `${mins}m`;
}

function bestText(t: Transcript): string {
    return t.text || t.normalized_text || t.raw_text || "";
}

function formatTimestamp(iso: string): string {
    try {
        const d = new Date(iso);
        return d.toLocaleString(undefined, {
            year: "numeric",
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
        });
    } catch {
        return iso;
    }
}

function tagList(t: Transcript): string {
    return t.tags.map((tg) => tg.name).join(", ") || "none";
}

/* ===== Format functions ===== */

export function transcriptsToCsv(transcripts: Transcript[]): string {
    const headers = [
        "id",
        "timestamp",
        "tags",
        "text",
        "raw_text",
        "normalized_text",
        "duration_ms",
        "speech_duration_ms",
    ];
    const lines = [headers.join(",")];
    for (const t of transcripts) {
        const row = [
            t.id,
            t.timestamp,
            tagList(t),
            t.text,
            t.raw_text,
            t.normalized_text,
            t.duration_ms,
            t.speech_duration_ms,
        ].map(escapeCsvValue);
        lines.push(row.join(","));
    }
    return lines.join("\n");
}

export function transcriptsToTxt(transcripts: Transcript[]): string {
    return transcripts
        .map((t, i) => {
            const title = t.display_name || `Transcript ${i + 1}`;
            const ts = formatTimestamp(t.timestamp);
            const tags = `Tags: ${tagList(t)}`;
            const duration = t.duration_ms > 0 ? `Duration: ${formatDurationHuman(t.duration_ms)}` : "";
            const meta = [ts, tags, duration].filter(Boolean).join("\n");
            return `${title}\n${meta}\n\n${bestText(t)}`;
        })
        .join("\n\n---\n\n");
}

export function transcriptsToMarkdown(transcripts: Transcript[]): string {
    const datePart = new Date().toLocaleDateString(undefined, {
        year: "numeric",
        month: "long",
        day: "numeric",
    });
    const header = `# Vociferous Export\n\n_Exported ${datePart} — ${transcripts.length} transcript${transcripts.length !== 1 ? "s" : ""}_\n\n---\n`;

    const body = transcripts
        .map((t) => {
            const title = t.display_name || "Untitled Transcript";
            const ts = formatTimestamp(t.timestamp);
            const tags = tagList(t);
            const duration =
                t.duration_ms > 0 ? `**Duration:** ${formatDurationHuman(t.duration_ms)}  ` : "";

            let meta = `**Date:** ${ts}  \n**Tags:** ${tags}`;
            if (duration) meta += `\n${duration}`;

            const text = bestText(t);
            return `## ${title}\n\n${meta}\n\n${text}`;
        })
        .join("\n\n---\n\n");

    return `${header}\n${body}\n`;
}

export function buildExportPayload(
    transcripts: Transcript[],
    format: ExportFormat,
): { filename: string; content: string } {
    const datePart = new Date().toISOString().slice(0, 10);
    const ext = format === "md" ? "md" : format;
    const prefix =
        transcripts.length === 1 && transcripts[0].display_name
            ? transcripts[0].display_name.replace(/[^a-zA-Z0-9_-]/g, "_").slice(0, 60)
            : `vociferous-export-${datePart}`;

    switch (format) {
        case "csv":
            return { filename: `${prefix}.csv`, content: transcriptsToCsv(transcripts) };
        case "txt":
            return { filename: `${prefix}.txt`, content: transcriptsToTxt(transcripts) };
        case "md":
            return { filename: `${prefix}.md`, content: transcriptsToMarkdown(transcripts) };
        default:
            return { filename: `${prefix}.json`, content: JSON.stringify(transcripts, null, 2) };
    }
}
