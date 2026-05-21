<script lang="ts">
    /**
     * SafetyDataCard — confirmation preference, data export, danger zone.
     *
     * Settings rows here are real persistent preferences (confirm-delete).
     * Export and Clear-All are data-management actions, not settings — they
     * live in dedicated sections with the visual weight they deserve.
     */

    import { clearAllTranscripts, getHealth, getTranscripts } from "../api";
    import type { HealthInfo } from "../api";
    import type { GetConfigValue, SetConfigValue, VociferousConfig } from "../config.svelte";
    import { confirmDeleteAction } from "../deleteConfirm";
    import { exportDialog } from "../exportDialog.svelte";
    import { toast } from "../toast.svelte";
    import { AlertTriangle, Download, ShieldCheck, Trash2 } from "lucide-svelte";
    import StyledButton from "./StyledButton.svelte";
    import ToggleSwitch from "./ToggleSwitch.svelte";

    interface Props {
        config: VociferousConfig;
        health: HealthInfo;
        getSafe: GetConfigValue;
        setSafe: SetConfigValue;
        onTranscriptsCleared: () => void;
    }

    let { config, health, getSafe, setSafe, onTranscriptsCleared }: Props = $props();

    let clearing = $state(false);

    function errorMessage(error: unknown): string {
        return error instanceof Error ? error.message : String(error);
    }

    async function handleExportOpen() {
        // Open dialog with current transcript count visible up front
        try {
            const { total } = await getTranscripts({ limit: 1 });
            exportDialog.show(total);
        } catch {
            // Fall back to health count if listing fails
            exportDialog.show(health.transcripts ?? 0);
        }
    }

    async function handleClearTranscripts() {
        const confirmed = await confirmDeleteAction({
            title: "Delete all transcripts?",
            message: `This permanently removes ${health.transcripts} transcript${health.transcripts !== 1 ? "s" : ""} and their variants. This cannot be undone.`,
            confirmLabel: "Delete Everything",
            cancelLabel: "Keep Data",
        });
        if (!confirmed) return;
        clearing = true;
        try {
            const result = await clearAllTranscripts();
            toast.success(`Cleared ${result.deleted} transcript${result.deleted !== 1 ? "s" : ""}`);
            try {
                await getHealth();
            } catch {
                // best-effort refresh
            }
            onTranscriptsCleared();
        } catch (e: unknown) {
            toast.error(errorMessage(e) || "Clear failed");
        } finally {
            clearing = false;
        }
    }
</script>

<div class="flex flex-col gap-[var(--space-5)]">
    <!-- ===== Safety ===== -->
    <section class="flex flex-col gap-[var(--space-3)]">
        <h3
            class="m-0 text-[var(--text-xs)] uppercase tracking-wider font-[var(--weight-emphasis)] text-[var(--text-tertiary)] flex items-center gap-[var(--space-2)]"
        >
            <ShieldCheck size={12} /> Safety
        </h3>

        <div class="grid grid-cols-[200px_minmax(0,1fr)] items-start gap-x-[var(--space-4)] min-h-[36px]">
            <label
                id="setting-confirm-delete-label"
                class="text-[var(--text-sm)] text-[var(--text-primary)]"
                for="setting-confirm-delete"
                data-tip="Applies to transcript, tag, and bulk delete actions across the app."
            >
                Confirm Before Delete
            </label>
            <div class="flex flex-col gap-[var(--space-1)]">
                <ToggleSwitch
                    id="setting-confirm-delete"
                    ariaLabelledby="setting-confirm-delete-label"
                    bind:checked={
                        () => getSafe(config, "safety.confirm_delete", true),
                        (checked: boolean) => setSafe("safety.confirm_delete", checked)
                    }
                />
                <span class="text-[var(--text-xs)] text-[var(--text-tertiary)] leading-[var(--leading-normal)]">
                    Applies to transcript, tag, and bulk delete actions.
                </span>
            </div>
        </div>
    </section>

    <!-- ===== Export ===== -->
    <section class="flex flex-col gap-[var(--space-3)]">
        <h3
            class="m-0 text-[var(--text-xs)] uppercase tracking-wider font-[var(--weight-emphasis)] text-[var(--text-tertiary)] flex items-center gap-[var(--space-2)]"
        >
            <Download size={12} /> Export
        </h3>

        <div class="grid grid-cols-[200px_minmax(0,1fr)] items-start gap-x-[var(--space-4)]">
            <span class="text-[var(--text-sm)] text-[var(--text-primary)]">Export Transcripts</span>
            <div class="flex flex-col gap-[var(--space-2)] items-start">
                <span class="text-[var(--text-xs)] text-[var(--text-tertiary)] leading-[var(--leading-normal)]">
                    Save your transcripts to JSON, CSV, plain text, or Markdown.
                </span>
                <StyledButton variant="primary" onclick={handleExportOpen}>
                    <Download size={14} /> Export Transcripts…
                </StyledButton>
            </div>
        </div>
    </section>

    <!-- ===== Danger Zone ===== -->
    <section class="flex flex-col gap-[var(--space-3)]">
        <h3
            class="m-0 text-[var(--text-xs)] uppercase tracking-wider font-[var(--weight-emphasis)] text-[var(--color-danger)] flex items-center gap-[var(--space-2)]"
        >
            <AlertTriangle size={12} /> Danger Zone
        </h3>

        <div
            class="rounded-[var(--radius-lg)] border border-[var(--color-danger)]/40 bg-[color:rgba(220,38,38,0.04)] p-[var(--space-4)] flex flex-col gap-[var(--space-3)]"
        >
            <div class="flex items-start gap-[var(--space-3)]">
                <Trash2 size={20} class="shrink-0 mt-px text-[var(--color-danger)]" />
                <div class="flex-1 flex flex-col gap-[var(--space-1)]">
                    <div class="text-[var(--text-sm)] font-[var(--weight-emphasis)] text-[var(--text-primary)]">
                        Delete All Transcripts
                    </div>
                    <div class="text-[var(--text-sm)] text-[var(--text-secondary)] leading-[var(--leading-normal)]">
                        Permanently removes <span class="font-[var(--weight-emphasis)] tabular-nums"
                            >{health.transcripts ?? 0}</span
                        > transcript{health.transcripts !== 1 ? "s" : ""} and every refinement variant attached to them.
                        This cannot be undone. Export first if you want a backup.
                    </div>
                </div>
            </div>
            <div class="flex justify-end">
                <StyledButton
                    variant="destructive"
                    onclick={handleClearTranscripts}
                    disabled={clearing || (health.transcripts ?? 0) === 0}
                >
                    {clearing ? "Deleting…" : "Delete All Transcripts"}
                </StyledButton>
            </div>
        </div>
    </section>
</div>
