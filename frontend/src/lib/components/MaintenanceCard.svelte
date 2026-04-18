<script lang="ts">
    /**
     * MaintenanceCard — GPU status, engine info + restart, data management.
     *
     * Flat layout matching other Settings tabs. No bordered cards.
     */

    import { getTranscripts, clearAllTranscripts, exportFile, openLogDirectory, restartEngine } from "../api";
    import { buildExportPayload, type ExportFormat } from "../exportUtils";
    import { CheckCircle, AlertCircle } from "lucide-svelte";
    import ToggleSwitch from "./ToggleSwitch.svelte";
    import CustomSelect from "./CustomSelect.svelte";
    import StyledButton from "./StyledButton.svelte";

    interface Props {
        config: Record<string, any>;
        models: { asr: Record<string, any>; slm: Record<string, any> };
        health: {
            gpu?: {
                cuda_available?: boolean;
                driver_detected?: boolean;
                cuda_device_count?: number;
                gpu_name?: string;
                detail?: string;
            };
            mic?: {
                available?: boolean;
                device_name?: string;
                host_api?: string;
                input_channels?: number;
                default_sample_rate?: number;
                supports_16k?: boolean;
                detail?: string;
            };
        };
        getSafe: (obj: any, path: string, fallback?: any) => any;
        setSafe: (path: string, value: any) => void;
        showMessage: (msg: string, type: "success" | "error") => void;
    }

    let { config, models, health, getSafe, setSafe, showMessage }: Props = $props();

    /* ===== Export state ===== */

    let exportFormat = $state<ExportFormat>("json");
    let preferSaveDialog = $state(true);

    /* ===== Clear state ===== */

    let clearingTranscripts = $state(false);
    let showClearTranscriptsConfirm = $state(false);

    /* ===== Derived ===== */

    let asrDeviceLabel = $derived(
        ({ auto: "Automatic", gpu: "GPU", cpu: "CPU" } as Record<string, string>)[
            getSafe(config, "model.device", "auto")
        ] ?? "Auto",
    );

    let slmEnabled = $derived(getSafe(config, "refinement.enabled", false));

    let slmDeviceLabel = $derived(
        !slmEnabled ? "—" : getSafe(config, "refinement.n_gpu_layers", -1) === 0 ? "CPU" : "GPU",
    );

    let asrModelName = $derived(
        (models.asr[getSafe(config, "model.model", "")] as any)?.name ?? (getSafe(config, "model.model", "") || "—"),
    );

    let slmModelName = $derived(
        !slmEnabled
            ? "Disabled"
            : ((models.slm[getSafe(config, "refinement.model_id", "")] as any)?.name ??
                  (getSafe(config, "refinement.model_id", "") || "—")),
    );

    let gpuRuntimeMismatch = $derived(Boolean(health.gpu?.driver_detected) && !health.gpu?.cuda_available);

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

    async function handleOpenLogDirectory() {
        try {
            const result = await openLogDirectory();
            if (result.status !== "opened") {
                showMessage(result.error || `Could not open log directory: ${result.path}`, "error");
                return;
            }
            showMessage(`Opened log directory: ${result.path}`, "success");
        } catch (e: any) {
            showMessage(e.message || "Could not open log directory", "error");
        }
    }
</script>

<div class="flex flex-col gap-[var(--space-3)]">
    <!-- GPU Status -->
    <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
        <div
            class="text-[var(--text-sm)] text-[var(--text-primary)]"
            data-tip="GPU acceleration status. Requires CTranslate2 compiled with CUDA support."
        >
            GPU Status
        </div>
        <div
            class="gpu-status-badge"
            class:gpu-available={health.gpu?.cuda_available}
            class:gpu-unavailable={!health.gpu?.cuda_available}
        >
            {#if health.gpu?.cuda_available}
                <CheckCircle size={14} />
                <span>{health.gpu.detail || "CUDA available"}</span>
            {:else}
                <AlertCircle size={14} />
                <span>{health.gpu?.detail || "No GPU detected"}</span>
            {/if}
        </div>
    </div>

    {#if gpuRuntimeMismatch}
        <div class="grid grid-cols-[200px_minmax(0,1fr)] gap-x-[var(--space-4)]">
            <span class="text-[var(--text-sm)] text-[var(--text-primary)]">GPU Warning</span>
            <div
                class="rounded-[var(--radius-md)] border border-amber-500/40 bg-amber-500/10 px-[var(--space-3)] py-[var(--space-2)] text-[var(--text-sm)] text-[var(--text-secondary)]"
            >
                NVIDIA driver detected{#if health.gpu?.gpu_name}
                    for {health.gpu.gpu_name}{/if}, but CTranslate2 cannot use CUDA yet. Install CUDA 12 plus cuDNN 9,
                or install the Python runtime packages nvidia-cuda-runtime-cu12, nvidia-cuda-nvrtc-cu12,
                nvidia-cublas-cu12, and nvidia-cudnn-cu12 into the venv, then restart the engine.
            </div>
        </div>
    {/if}

    <!-- Microphone Status -->
    <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
        <div
            class="text-[var(--text-sm)] text-[var(--text-primary)]"
            data-tip="Default input device detected by PortAudio."
        >
            Microphone
        </div>
        <div
            class="gpu-status-badge"
            class:gpu-available={health.mic?.available}
            class:gpu-unavailable={!health.mic?.available}
        >
            {#if health.mic?.available}
                <CheckCircle size={14} />
                <span>{health.mic.detail || health.mic.device_name || "Available"}</span>
            {:else}
                <AlertCircle size={14} />
                <span>{health.mic?.detail || "No microphone detected"}</span>
            {/if}
        </div>
    </div>

    {#if health.mic?.available && !health.mic?.supports_16k}
        <div class="grid grid-cols-[200px_minmax(0,1fr)] gap-x-[var(--space-4)]">
            <span class="text-[var(--text-sm)] text-[var(--text-primary)]">Mic Warning</span>
            <div
                class="rounded-[var(--radius-md)] border border-amber-500/40 bg-amber-500/10 px-[var(--space-3)] py-[var(--space-2)] text-[var(--text-sm)] text-[var(--text-secondary)]"
            >
                '{health.mic.device_name}' may not support 16 kHz mono recording. Transcription could fail or produce
                poor results. Try selecting a different default input device in your OS audio settings.
            </div>
        </div>
    {/if}

    <!-- ASR info -->
    <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
        <span class="text-[var(--text-sm)] text-[var(--text-primary)]">ASR Model</span>
        <span class="text-[var(--text-sm)] text-[var(--text-secondary)]">{asrModelName}</span>
    </div>
    <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
        <span class="text-[var(--text-sm)] text-[var(--text-primary)]">ASR Device</span>
        <span class="text-[var(--text-sm)] text-[var(--text-secondary)]">{asrDeviceLabel}</span>
    </div>

    <!-- SLM info -->
    <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
        <span class="text-[var(--text-sm)] text-[var(--text-primary)]">Refinement Model</span>
        <span class="text-[var(--text-sm)] text-[var(--text-secondary)]">{slmModelName}</span>
    </div>
    <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
        <span class="text-[var(--text-sm)] text-[var(--text-primary)]">Refinement Device</span>
        <span class="text-[var(--text-sm)] text-[var(--text-secondary)]">{slmDeviceLabel}</span>
    </div>

    <!-- Restart -->
    <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
        <span
            class="text-[var(--text-sm)] text-[var(--text-primary)]"
            data-tip="Reloads ASR and SLM models with the current configuration. Required after changing model or device settings."
        >
            Engine
        </span>
        <div>
            <StyledButton variant="secondary" onclick={handleRestartEngine}>Restart Engine</StyledButton>
        </div>
    </div>

    <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
        <label
            class="text-[var(--text-sm)] text-[var(--text-primary)]"
            for="setting-console-log-level"
            data-tip="Controls terminal log verbosity for local troubleshooting. On-disk log files always capture full DEBUG detail."
            >Console Log Verbosity</label
        >
        <div class="w-full max-w-[460px]">
            <CustomSelect
                id="setting-console-log-level"
                options={[
                    { value: "DEBUG", label: "Debug" },
                    { value: "INFO", label: "Info" },
                    { value: "WARNING", label: "Warning" },
                    { value: "ERROR", label: "Error" },
                ]}
                value={getSafe(config, "logging.level", "INFO")}
                onchange={(v: string) => setSafe("logging.level", v)}
            />
        </div>
    </div>

    <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
        <span
            class="text-[var(--text-sm)] text-[var(--text-primary)]"
            data-tip="Open the persistent Vociferous log directory so support logs are easy to inspect or share."
        >
            Log Files
        </span>
        <div>
            <StyledButton variant="secondary" onclick={handleOpenLogDirectory}>Open Log Directory</StyledButton>
        </div>
    </div>

    <!-- Separator -->
    <div class="border-t border-[var(--shell-border)] my-[var(--space-1)]"></div>

    <!-- Transcriptions -->
    <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
        <label class="text-[var(--text-sm)] text-[var(--text-primary)]" for="history-export-format">Export Format</label
        >
        <div class="w-full max-w-[460px]">
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
    <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
        <label
            class="text-[var(--text-sm)] text-[var(--text-primary)]"
            for="setting-save-dialog"
            data-tip="Uses native save dialog when supported; otherwise downloads to your default location."
            >Choose Location</label
        >
        <ToggleSwitch checked={preferSaveDialog} onChange={() => (preferSaveDialog = !preferSaveDialog)} />
    </div>
    <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
        <span class="text-[var(--text-sm)] text-[var(--text-primary)]">Transcriptions</span>
        <div class="flex gap-[var(--space-2)]">
            <StyledButton variant="primary" onclick={handleExportTranscripts}>Export</StyledButton>
            <StyledButton variant="destructive" onclick={handleClearTranscripts} disabled={clearingTranscripts}>
                {clearingTranscripts ? "Clearing…" : "Clear All"}
            </StyledButton>
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

<style>
    .gpu-status-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: var(--text-xs);
        font-weight: 500;
        width: fit-content;
    }
    .gpu-status-badge.gpu-available {
        color: var(--color-success, #22c55e);
        background: color-mix(in srgb, var(--color-success, #22c55e) 12%, transparent);
    }
    .gpu-status-badge.gpu-unavailable {
        color: var(--text-tertiary);
        background: color-mix(in srgb, var(--text-tertiary) 10%, transparent);
    }
</style>
