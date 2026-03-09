<script lang="ts">
    /**
     * MaintenanceCard — Data management and engine restart.
     *
     * Self-contained: owns export formatting, clear-all confirmation modal,
     * and engine restart action.
     */

    import { getTranscripts, clearAllTranscripts, exportFile, restartEngine } from "../api";
    import { RotateCcw } from "lucide-svelte";
    import ToggleSwitch from "./ToggleSwitch.svelte";
    import CustomSelect from "./CustomSelect.svelte";
    import StyledButton from "./StyledButton.svelte";
    interface Props {
        config: Record<string, any>;
        models: { asr: Record<string, any>; slm: Record<string, any> };
        health: {
            gpu?: { cuda_available?: boolean };
        };
        getSafe: (obj: any, path: string, fallback?: any) => any;
        showMessage: (msg: string, type: "success" | "error") => void;
    }

    let { config, models, health, getSafe, showMessage }: Props = $props();

    /* ===== Export state ===== */

    let exportFormat = $state<"json" | "csv" | "txt" | "md">("json");
    let preferSaveDialog = $state(true);

    /* ===== Clear state ===== */

    let clearingTranscripts = $state(false);
    let showClearTranscriptsConfirm = $state(false);

    /* ===== Export helpers ===== */

    function escapeCsvValue(value: unknown): string {
        const text = String(value ?? "").replace(/"/g, '""');
        return `"${text}"`;
    }

    function transcriptsToCsv(transcripts: Record<string, unknown>[]): string {
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
        for (const transcript of transcripts) {
            const tags = Array.isArray(transcript.tags)
                ? (transcript.tags as { name: string }[]).map((t) => t.name).join("; ")
                : "";
            const row = [
                transcript.id,
                transcript.timestamp,
                tags,
                transcript.text,
                transcript.raw_text,
                transcript.normalized_text,
                transcript.duration_ms,
                transcript.speech_duration_ms,
            ].map(escapeCsvValue);
            lines.push(row.join(","));
        }
        return lines.join("\n");
    }

    function transcriptsToTxt(transcripts: Record<string, unknown>[]): string {
        return transcripts
            .map((transcript, index) => {
                const title = `Transcript ${index + 1}`;
                const timestamp = `Timestamp: ${String(transcript.timestamp ?? "unknown")}`;
                const tags = Array.isArray(transcript.tags)
                    ? `Tags: ${(transcript.tags as { name: string }[]).map((t) => t.name).join(", ") || "none"}`
                    : "Tags: none";
                const text = String(transcript.text ?? transcript.normalized_text ?? transcript.raw_text ?? "");
                return `${title}\n${timestamp}\n${tags}\n\n${text}`;
            })
            .join("\n\n---\n\n");
    }

    function transcriptsToMarkdown(transcripts: Record<string, unknown>[]): string {
        const header = `# Vociferous Export\n\n_${new Date().toLocaleDateString()} — ${transcripts.length} transcripts_\n`;
        const body = transcripts
            .map((t, i) => {
                const ts = String(t.timestamp ?? "unknown");
                const tags = Array.isArray(t.tags)
                    ? (t.tags as { name: string }[]).map((tg) => tg.name).join(", ") || "none"
                    : "none";
                const text = String(t.text ?? t.normalized_text ?? t.raw_text ?? "");
                return `## ${i + 1}. Transcript\n\n**Date:** ${ts}  \n**Tags:** ${tags}\n\n${text}`;
            })
            .join("\n\n---\n\n");
        return `${header}\n${body}\n`;
    }

    function buildExportPayload(transcripts: Record<string, unknown>[], format: "json" | "csv" | "txt" | "md") {
        const datePart = new Date().toISOString().slice(0, 10);
        if (format === "csv") {
            const content = transcriptsToCsv(transcripts);
            return { filename: `vociferous-export-${datePart}.csv`, content };
        }
        if (format === "txt") {
            const content = transcriptsToTxt(transcripts);
            return { filename: `vociferous-export-${datePart}.txt`, content };
        }
        if (format === "md") {
            const content = transcriptsToMarkdown(transcripts);
            return { filename: `vociferous-export-${datePart}.md`, content };
        }
        const content = JSON.stringify(transcripts, null, 2);
        return { filename: `vociferous-export-${datePart}.json`, content };
    }

    /* ===== Actions ===== */

    async function handleExportTranscripts() {
        try {
            const { items: transcripts } = await getTranscripts({ limit: 99999 });
            const { filename, content } = buildExportPayload(
                transcripts as unknown as Record<string, unknown>[],
                exportFormat,
            );

            if (preferSaveDialog) {
                const result = await exportFile(content, filename);
                showMessage(
                    `Exported ${transcripts.length} transcript${transcripts.length !== 1 ? "s" : ""} to ${result.path}`,
                    "success",
                );
                return;
            }

            const blob = new Blob([content], { type: "application/octet-stream" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = filename;
            a.click();
            URL.revokeObjectURL(url);
            showMessage(
                `Exported ${transcripts.length} transcript${transcripts.length !== 1 ? "s" : ""} to default download location`,
                "success",
            );
        } catch (e: any) {
            if ((e as any)?.error === "cancelled" || e?.message?.includes("cancelled")) {
                showMessage("Export cancelled", "error");
                return;
            }
            showMessage((e as any).message || "Export failed", "error");
        }
    }

    function handleClearTranscripts() {
        showClearTranscriptsConfirm = true;
    }

    async function confirmClearTranscripts() {
        showClearTranscriptsConfirm = false;
        clearingTranscripts = true;
        try {
            const result = await clearAllTranscripts();
            showMessage(`Cleared ${result.deleted} transcript${result.deleted !== 1 ? "s" : ""}`, "success");
        } catch (e: any) {
            showMessage(e.message || "Clear failed", "error");
        } finally {
            clearingTranscripts = false;
        }
    }

    async function handleRestartEngine() {
        showMessage("Restarting engine…", "success");
        try {
            await restartEngine();
        } catch (e: any) {
            showMessage(e.message || "Engine restart failed", "error");
        }
    }


</script>

<div
    class="bg-[var(--surface-secondary)] border border-[var(--shell-border)] rounded-[var(--radius-lg)] p-[var(--space-4)] xl:col-span-2"
>
    <div
        class="flex items-center gap-[var(--space-2)] text-[var(--text-base)] font-[var(--weight-emphasis)] text-[var(--text-primary)] mb-[var(--space-4)] pb-[var(--space-2)] border-b border-[var(--shell-border)]"
    >
        <RotateCcw size={18} class="text-[var(--accent)]" /><span>Maintenance</span>
    </div>
    <div class="grid grid-cols-1 gap-[var(--space-3)]">
        <!-- Transcriptions: export + clear -->
        <div
            class="flex flex-col gap-[var(--space-2)] border border-[var(--shell-border)] rounded-[var(--radius-md)] p-[var(--space-3)]"
        >
            <span class="text-[var(--text-sm)] text-[var(--text-primary)] font-[var(--weight-emphasis)]"
                >Transcriptions</span
            >
            <div class="flex flex-col gap-[var(--space-2)]">
                <div class="flex items-center justify-between gap-[var(--space-3)]">
                    <span class="text-[var(--text-xs)] text-[var(--text-secondary)]">Format</span>
                    <div class="w-full max-w-[180px]">
                        <CustomSelect
                            id="history-export-format"
                            options={[
                                { value: "json", label: "JSON" },
                                { value: "csv", label: "CSV" },
                                { value: "txt", label: "Plain Text" },
                                { value: "md", label: "Markdown" },
                            ]}
                            value={exportFormat}
                            onchange={(v: string) => {
                                if (v === "json" || v === "csv" || v === "txt" || v === "md") {
                                    exportFormat = v;
                                }
                            }}
                        />
                    </div>
                </div>
                <div class="flex items-center justify-between gap-[var(--space-3)]">
                    <span
                        class="text-[var(--text-xs)] text-[var(--text-secondary)]"
                        title="Uses native save dialog when supported; otherwise downloads to your default location."
                        >Choose Location</span
                    >
                    <ToggleSwitch checked={preferSaveDialog} onChange={() => (preferSaveDialog = !preferSaveDialog)} />
                </div>
            </div>
            <div class="flex gap-[var(--space-2)] flex-wrap">
                <StyledButton variant="secondary" onclick={handleExportTranscripts}>Export</StyledButton>
                <StyledButton variant="destructive" onclick={handleClearTranscripts} disabled={clearingTranscripts}>
                    {clearingTranscripts ? "Clearing…" : "Clear All"}</StyledButton
                >
            </div>
        </div>

        <!-- Engine: status + restart -->
        <div
            class="flex flex-col gap-[var(--space-2)] border border-[var(--shell-border)] rounded-[var(--radius-md)] p-[var(--space-3)]"
        >
            <span class="text-[var(--text-sm)] text-[var(--text-primary)] font-[var(--weight-emphasis)]">Engine</span>
            <div class="flex flex-col gap-1">
                <span class="text-[var(--text-xs)] text-[var(--text-tertiary)]">
                    ASR: {(models.asr[getSafe(config, "model.model", "")] as any)?.name ??
                        (getSafe(config, "model.model", "") || "—")}
                </span>
                <span class="text-[var(--text-xs)] text-[var(--text-tertiary)]">
                    SLM: {getSafe(config, "refinement.enabled", false)
                        ? ((models.slm[getSafe(config, "refinement.model_id", "")] as any)?.name ??
                          (getSafe(config, "refinement.model_id", "") || "—"))
                        : "Disabled"}
                </span>
                <span class="text-[var(--text-xs)] text-[var(--text-tertiary)]">
                    Compute: {health.gpu?.cuda_available ? "GPU (CUDA)" : "CPU"}
                </span>
            </div>
            <div class="flex gap-[var(--space-2)] flex-wrap">
                <StyledButton variant="secondary" onclick={handleRestartEngine}>Restart Engine</StyledButton>
            </div>
        </div>
    </div>
</div>

{#if showClearTranscriptsConfirm}
    <div
        class="fixed inset-0 z-[120] bg-black/50 flex items-center justify-center p-[var(--space-4)]"
        role="presentation"
        onclick={(e) => {
            if (e.target === e.currentTarget) showClearTranscriptsConfirm = false;
        }}
    >
        <div
            class="w-full max-w-[520px] bg-[var(--surface-secondary)] border border-[var(--shell-border)] rounded-[var(--radius-lg)] p-[var(--space-4)] flex flex-col gap-[var(--space-3)]"
            role="dialog"
            aria-modal="true"
            aria-labelledby="clear-transcripts-title"
            aria-describedby="clear-transcripts-description"
        >
            <h3
                id="clear-transcripts-title"
                class="m-0 text-[var(--text-base)] font-[var(--weight-emphasis)] text-[var(--text-primary)]"
            >
                Clear all transcriptions?
            </h3>
            <p id="clear-transcripts-description" class="m-0 text-[var(--text-sm)] text-[var(--text-secondary)]">
                This permanently deletes all transcripts and their variants. This action cannot be undone.
            </p>
            <div class="flex justify-end gap-[var(--space-2)] pt-[var(--space-1)]">
                <StyledButton
                    variant="secondary"
                    onclick={() => (showClearTranscriptsConfirm = false)}
                    disabled={clearingTranscripts}>Cancel</StyledButton
                >
                <StyledButton variant="destructive" onclick={confirmClearTranscripts} disabled={clearingTranscripts}
                    >{clearingTranscripts ? "Clearing…" : "Delete Everything"}</StyledButton
                >
            </div>
        </div>
    </div>
{/if}
