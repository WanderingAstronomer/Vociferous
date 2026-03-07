<script lang="ts">
    /**
     * MaintenanceCard — Data management, batch retitle, engine restart.
     *
     * Self-contained: owns batch retitle WS subscription, export formatting,
     * clear-all confirmation modal, and engine restart action.
     */

    import { getTranscripts, clearAllTranscripts, exportFile, batchRetitle, restartEngine } from "../api";
    import { ws } from "../ws";
    import { onMount, onDestroy } from "svelte";
    import { RotateCcw, Loader2 } from "lucide-svelte";
    import ToggleSwitch from "./ToggleSwitch.svelte";
    import CustomSelect from "./CustomSelect.svelte";
    import StyledButton from "./StyledButton.svelte";
    import type { BatchRetitleProgressData } from "../events";

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

    /* ===== Batch retitle state ===== */

    let batchRetitling = $state(false);
    let batchRetitleTotal = $state(0);
    let batchRetitleProcessed = $state(0);
    let batchRetitleSkipped = $state(0);
    let batchRetitleCurrent = $state(0);
    let batchRetitleMessage = $state("");

    /* ===== WS subscription ===== */

    let unsubBatchRetitle: (() => void) | null = null;

    onMount(() => {
        unsubBatchRetitle = ws.on("batch_retitle_progress", (data: BatchRetitleProgressData) => {
            if (data.status === "started") {
                batchRetitling = true;
                batchRetitleTotal = data.total ?? 0;
                batchRetitleProcessed = 0;
                batchRetitleSkipped = 0;
                batchRetitleCurrent = 0;
                batchRetitleMessage = `Retitling 0 / ${data.total ?? 0}…`;
            } else if (data.status === "progress") {
                batchRetitleProcessed = data.processed ?? 0;
                batchRetitleSkipped = data.skipped ?? 0;
                batchRetitleCurrent = data.current ?? 0;
                batchRetitleTotal = data.total ?? batchRetitleTotal;
                batchRetitleMessage = `Retitling ${data.current ?? 0} / ${data.total ?? batchRetitleTotal}…`;
            } else if (data.status === "complete") {
                batchRetitling = false;
                const msg = `Retitled ${data.processed ?? 0} transcript${(data.processed ?? 0) !== 1 ? "s" : ""}${(data.skipped ?? 0) > 0 ? `, ${data.skipped} skipped` : ""}`;
                showMessage(msg, "success");
                batchRetitleMessage = "";
            } else if (data.status === "error") {
                batchRetitling = false;
                showMessage(data.message ?? "Batch retitle failed", "error");
                batchRetitleMessage = "";
            }
        });
    });

    onDestroy(() => {
        unsubBatchRetitle?.();
    });

    /* ===== Export helpers ===== */

    function escapeCsvValue(value: unknown): string {
        const text = String(value ?? "").replace(/"/g, '""');
        return `"${text}"`;
    }

    function transcriptsToCsv(transcripts: Record<string, unknown>[]): string {
        const headers = [
            "id",
            "timestamp",
            "project_name",
            "text",
            "raw_text",
            "normalized_text",
            "duration_ms",
            "speech_duration_ms",
        ];
        const lines = [headers.join(",")];
        for (const transcript of transcripts) {
            const row = [
                transcript.id,
                transcript.timestamp,
                transcript.project_name,
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
                const project = `Project: ${String(transcript.project_name ?? "unassigned")}`;
                const text = String(transcript.text ?? transcript.normalized_text ?? transcript.raw_text ?? "");
                return `${title}\n${timestamp}\n${project}\n\n${text}`;
            })
            .join("\n\n---\n\n");
    }

    function transcriptsToMarkdown(transcripts: Record<string, unknown>[]): string {
        const header = `# Vociferous Export\n\n_${new Date().toLocaleDateString()} — ${transcripts.length} transcripts_\n`;
        const body = transcripts
            .map((t, i) => {
                const ts = String(t.timestamp ?? "unknown");
                const project = String(t.project_name ?? "unassigned");
                const text = String(t.text ?? t.normalized_text ?? t.raw_text ?? "");
                return `## ${i + 1}. Transcript\n\n**Date:** ${ts}  \n**Project:** ${project}\n\n${text}`;
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
            const transcripts = await getTranscripts(99999);
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

    async function handleBatchRetitle() {
        batchRetitling = true;
        batchRetitleMessage = "Starting batch retitle…";
        try {
            await batchRetitle();
        } catch (e: any) {
            batchRetitling = false;
            showMessage(e.message || "Batch retitle failed", "error");
            batchRetitleMessage = "";
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
            <span class="text-[var(--text-sm)] text-[var(--text-secondary)] font-[var(--weight-emphasis)]"
                >Transcriptions</span
            >
            <div class="flex flex-col gap-[var(--space-2)] mb-[var(--space-1)]">
                <div class="flex items-center justify-between gap-[var(--space-3)]">
                    <span class="text-[var(--text-xs)] text-[var(--text-tertiary)] uppercase">Format</span>
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
                    <span class="text-[var(--text-xs)] text-[var(--text-tertiary)] uppercase">Choose Location</span>
                    <ToggleSwitch checked={preferSaveDialog} onChange={() => (preferSaveDialog = !preferSaveDialog)} />
                </div>
                <span class="text-[var(--text-xs)] text-[var(--text-tertiary)] italic"
                    >Uses native save dialog when supported; otherwise downloads to your default location.</span
                >
            </div>
            <div class="flex gap-[var(--space-2)] flex-wrap">
                <StyledButton variant="secondary" onclick={handleExportTranscripts}>Export Transcriptions</StyledButton>
                <StyledButton variant="destructive" onclick={handleClearTranscripts} disabled={clearingTranscripts}>
                    {clearingTranscripts ? "Clearing…" : "Clear All Transcriptions"}</StyledButton
                >
            </div>
        </div>

        <!-- Titles: batch retitle -->
        <div
            class="flex flex-col gap-[var(--space-2)] border border-[var(--shell-border)] rounded-[var(--radius-md)] p-[var(--space-3)]"
        >
            <span class="text-[var(--text-sm)] text-[var(--text-secondary)] font-[var(--weight-emphasis)]">Titles</span>
            <span class="text-[var(--text-xs)] text-[var(--text-tertiary)] italic"
                >Generate SLM-powered titles for all untitled transcripts. This may take several minutes if you have
                many transcripts. Recordings shorter than ~25 words are skipped.</span
            >
            {#if batchRetitling}
                <div class="flex items-center gap-2 text-[var(--text-xs)] text-[var(--accent)]">
                    <Loader2 size={14} class="spin" />
                    <span>{batchRetitleMessage}</span>
                </div>
                {#if batchRetitleTotal > 0}
                    <div class="w-full h-1.5 bg-[var(--surface-primary)] rounded-full overflow-hidden">
                        <div
                            class="h-full bg-[var(--accent)] transition-all duration-300 rounded-full"
                            style="width: {Math.round((batchRetitleCurrent / batchRetitleTotal) * 100)}%"
                        ></div>
                    </div>
                    <span class="text-[var(--text-xs)] text-[var(--text-tertiary)]">
                        {batchRetitleProcessed} titled, {batchRetitleSkipped} skipped
                    </span>
                {/if}
            {/if}
            <div class="flex gap-[var(--space-2)] flex-wrap">
                <StyledButton variant="secondary" onclick={handleBatchRetitle} disabled={batchRetitling}>
                    {batchRetitling ? "Retitling…" : "Retitle All Untitled"}
                </StyledButton>
            </div>
        </div>

        <!-- Engine: status + restart -->
        <div
            class="flex flex-col gap-[var(--space-2)] border border-[var(--shell-border)] rounded-[var(--radius-md)] p-[var(--space-3)]"
        >
            <span class="text-[var(--text-sm)] text-[var(--text-secondary)] font-[var(--weight-emphasis)]">Engine</span>
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
