<script lang="ts">
    /**
     * ExportDialog — modal for exporting transcripts.
     *
     * Owns format + destination as action parameters, not persistent settings.
     * Opens via `exportDialog.isOpen()`, returns nothing — the dialog drives the
     * export itself and surfaces feedback via toasts.
     */

    import { exportFile, getTranscripts } from "../api";
    import type { Transcript } from "../api";
    import { buildExportPayload, type ExportFormat } from "../exportUtils";
    import { exportDialog } from "../exportDialog.svelte";
    import { toast } from "../toast.svelte";
    import CustomSelect from "./CustomSelect.svelte";
    import StyledButton from "./StyledButton.svelte";
    import ToggleSwitch from "./ToggleSwitch.svelte";

    const EXPORT_PAGE_SIZE = 1000;

    let dialogEl: HTMLDivElement | undefined = $state();
    let format = $state<ExportFormat>("json");
    let preferSaveDialog = $state(true);
    let exporting = $state(false);

    $effect(() => {
        if (exportDialog.isOpen && dialogEl) dialogEl.focus();
    });

    function close(): void {
        if (exporting) return;
        exportDialog.close();
    }

    function errorMessage(error: unknown): string {
        return error instanceof Error ? error.message : String(error);
    }

    function isObjectWithError(value: unknown): value is { error: string } {
        return typeof value === "object" && value !== null && "error" in value;
    }

    async function fetchAllTranscripts(): Promise<Transcript[]> {
        const transcripts: Transcript[] = [];
        let offset = 0;
        let total = Number.POSITIVE_INFINITY;

        while (offset < total) {
            const result = await getTranscripts({ limit: EXPORT_PAGE_SIZE, offset });
            transcripts.push(...result.items);
            total = result.total;
            if (result.items.length === 0) break;
            offset += result.items.length;
        }

        return transcripts;
    }

    async function handleExport() {
        exporting = true;
        try {
            const transcripts = await fetchAllTranscripts();
            const { filename, content } = buildExportPayload(transcripts, format);

            if (preferSaveDialog) {
                const result = await exportFile(content, filename);
                toast.success(
                    `Exported ${transcripts.length} transcript${transcripts.length !== 1 ? "s" : ""} to ${result.path}`,
                );
            } else {
                const blob = new Blob([content], { type: "application/octet-stream" });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = filename;
                a.click();
                URL.revokeObjectURL(url);
                toast.success(
                    `Exported ${transcripts.length} transcript${transcripts.length !== 1 ? "s" : ""} to default download location`,
                );
            }
            exportDialog.close();
        } catch (e: unknown) {
            const message = errorMessage(e);
            if ((isObjectWithError(e) && e.error === "cancelled") || message.includes("cancelled")) {
                toast.info("Export cancelled");
            } else {
                toast.error(message || "Export failed");
            }
        } finally {
            exporting = false;
        }
    }

    function handleKeydown(event: KeyboardEvent): void {
        if (!exportDialog.isOpen) return;
        if (event.key === "Escape") {
            event.preventDefault();
            close();
        }
    }
</script>

<svelte:window onkeydown={handleKeydown} />

{#if exportDialog.isOpen}
    <div
        class="fixed inset-0 z-[300] flex items-center justify-center bg-black/55 p-[var(--space-4)]"
        role="presentation"
        onclick={close}
        onkeydown={() => {}}
    >
        <div
            bind:this={dialogEl}
            class="w-full max-w-[520px] rounded-[var(--radius-lg)] border border-[var(--shell-border)] bg-[var(--surface-secondary)] shadow-2xl outline-none"
            role="dialog"
            aria-modal="true"
            aria-labelledby="export-dialog-title"
            tabindex="-1"
            onclick={(event) => event.stopPropagation()}
            onkeydown={(event) => event.stopPropagation()}
        >
            <div class="flex flex-col gap-[var(--space-4)] p-[var(--space-4)]">
                <div class="flex flex-col gap-[var(--space-1)]">
                    <h3
                        id="export-dialog-title"
                        class="m-0 text-[var(--text-base)] font-[var(--weight-emphasis)] text-[var(--text-primary)]"
                    >
                        Export Transcripts
                    </h3>
                    <p class="m-0 text-[var(--text-sm)] leading-[var(--leading-normal)] text-[var(--text-secondary)]">
                        Choose a format and destination. {exportDialog.transcriptCount} transcript{exportDialog.transcriptCount !== 1 ? "s" : ""} will be included.
                    </p>
                </div>

                <div class="flex flex-col gap-[var(--space-3)]">
                    <div class="grid grid-cols-[140px_minmax(0,1fr)] items-center gap-x-[var(--space-3)]">
                        <label
                            class="text-[var(--text-sm)] text-[var(--text-primary)]"
                            for="export-dialog-format">Format</label
                        >
                        <CustomSelect
                            id="export-dialog-format"
                            options={[
                                { value: "json", label: "JSON" },
                                { value: "csv", label: "CSV" },
                                { value: "txt", label: "Plain Text" },
                                { value: "md", label: "Markdown" },
                            ]}
                            value={format}
                            onchange={(v: string) => {
                                if (v === "json" || v === "csv" || v === "txt" || v === "md") format = v;
                            }}
                        />
                    </div>
                    <div class="grid grid-cols-[140px_minmax(0,1fr)] items-center gap-x-[var(--space-3)]">
                        <span
                            id="export-dialog-savepicker-label"
                            class="text-[var(--text-sm)] text-[var(--text-primary)]">Ask Where to Save</span
                        >
                        <div class="flex items-center gap-[var(--space-2)]">
                            <ToggleSwitch
                                bind:checked={preferSaveDialog}
                                ariaLabelledby="export-dialog-savepicker-label"
                            />
                            <span class="text-[var(--text-xs)] text-[var(--text-tertiary)]">
                                {preferSaveDialog ? "Native save dialog" : "Default download location"}
                            </span>
                        </div>
                    </div>
                </div>

                <div class="flex justify-end gap-[var(--space-2)] pt-[var(--space-1)]">
                    <StyledButton size="sm" variant="secondary" onclick={close} disabled={exporting}>
                        Cancel
                    </StyledButton>
                    <StyledButton size="sm" variant="primary" onclick={handleExport} disabled={exporting}>
                        {exporting ? "Exporting…" : "Export"}
                    </StyledButton>
                </div>
            </div>
        </div>
    </div>
{/if}
