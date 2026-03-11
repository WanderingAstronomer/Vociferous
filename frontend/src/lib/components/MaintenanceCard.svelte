<script lang="ts">
    /**
     * MaintenanceCard — Data management and engine restart.
     *
     * Self-contained: owns export formatting, clear-all confirmation modal,
     * and engine restart action.
     */

    import { getTranscripts, clearAllTranscripts, exportFile, restartEngine } from "../api";
    import { buildExportPayload, type ExportFormat } from "../exportUtils";
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

    let exportFormat = $state<ExportFormat>("json");
    let preferSaveDialog = $state(true);

    /* ===== Clear state ===== */

    let clearingTranscripts = $state(false);
    let showClearTranscriptsConfirm = $state(false);

    /* ===== Actions ===== */

    async function handleExportTranscripts() {
        try {
            const { items: transcripts } = await getTranscripts({ limit: 99999 });
            const { filename, content } = buildExportPayload(transcripts, exportFormat);

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

<div class="grid grid-cols-2 gap-[var(--space-4)]">
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
        <div class="flex justify-between gap-[var(--space-2)] flex-wrap">
            <StyledButton variant="destructive" onclick={handleClearTranscripts} disabled={clearingTranscripts}>
                {clearingTranscripts ? "Clearing…" : "Clear All"}</StyledButton
            >
            <StyledButton variant="primary" onclick={handleExportTranscripts}>Export</StyledButton>
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
