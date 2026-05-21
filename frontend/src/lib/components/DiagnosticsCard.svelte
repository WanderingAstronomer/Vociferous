<script lang="ts">
    /**
     * DiagnosticsCard — runtime health, engine controls, and (collapsed) low-level details.
     *
     * Replaces the diagnostics half of the old MaintenanceCard. Settings preferences
     * live elsewhere; this surface is purely observational + operational. Feedback
     * goes through toasts, never the Settings save bar.
     */

    import { cleanupEngine, getEngineStatus, openLogDirectory, restartEngine } from "../api";
    import type { EngineStatusInfo, HealthInfo } from "../api";
    import type { GetConfigValue, SetConfigValue, VociferousConfig } from "../config.svelte";
    import { toast } from "../toast.svelte";
    import {
        AlertCircle,
        CheckCircle,
        ChevronDown,
        Clipboard,
        FolderOpen,
        Loader2,
        Mic,
        RotateCcw,
        TriangleAlert,
    } from "lucide-svelte";
    import CustomSelect from "./CustomSelect.svelte";
    import StyledButton from "./StyledButton.svelte";

    interface Props {
        config: VociferousConfig;
        health: HealthInfo;
        engineStatus: EngineStatusInfo | null;
        restartPending: boolean;
        getSafe: GetConfigValue;
        setSafe: SetConfigValue;
        onRestartEngine: () => void;
        onStatusChanged: () => void;
    }

    let {
        config,
        health,
        engineStatus,
        restartPending,
        getSafe,
        setSafe,
        onRestartEngine,
        onStatusChanged,
    }: Props = $props();

    let detailsOpen = $state(false);
    let cleaningTemp = $state(false);
    let cleaningSpools = $state(false);

    let engineReady = $derived(engineStatus?.status === "ready" || engineStatus?.status === "degraded");
    let asrLoadedDevice = $derived(formatDevice(engineStatus?.asr.device));
    let slmLoadedDevice = $derived(formatDevice(engineStatus?.slm.device));
    let gpuRuntimeMismatch = $derived(Boolean(health.gpu?.driver_detected) && !health.gpu?.cuda_available);

    let activeProvider = $derived(engineStatus?.providers.find((provider) => provider.active));
    let packageEntries = $derived(engineStatus ? Object.entries(engineStatus.packages) : []);

    function formatStatus(value: string | undefined | null): string {
        if (!value) return "—";
        return value
            .split("_")
            .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
            .join(" ");
    }

    function formatDevice(value: string | undefined | null): string {
        if (!value) return "—";
        const lower = value.toLowerCase();
        if (lower === "cuda" || lower.includes("gpu")) return "GPU";
        if (lower === "cpu" || lower.includes("cpu")) return "CPU";
        return value.toUpperCase();
    }

    function errorMessage(error: unknown): string {
        return error instanceof Error ? error.message : String(error);
    }

    async function handleOpenLogDirectory() {
        try {
            const result = await openLogDirectory();
            if (result.status !== "opened") {
                toast.error(result.error || `Could not open log directory: ${result.path}`);
                return;
            }
            toast.success(`Opened ${result.path}`);
        } catch (e: unknown) {
            toast.error(errorMessage(e) || "Could not open log directory");
        }
    }

    async function refreshEngineStatus(): Promise<void> {
        try {
            await getEngineStatus();
        } catch {
            // Status refresh is best-effort
        } finally {
            onStatusChanged();
        }
    }

    async function handleCleanupTemp() {
        cleaningTemp = true;
        try {
            const result = await cleanupEngine(false);
            const count = result.removed.length;
            if (result.errors.length > 0) {
                toast.error(`Cleaned ${count} import${count !== 1 ? "s" : ""}; ${result.errors.length} failed`);
            } else {
                toast.success(`Cleaned ${count} temporary import${count !== 1 ? "s" : ""}`);
            }
            await refreshEngineStatus();
        } catch (e: unknown) {
            toast.error(errorMessage(e) || "Cleanup failed");
        } finally {
            cleaningTemp = false;
        }
    }

    async function handleCleanupSpools() {
        cleaningSpools = true;
        try {
            const result = await cleanupEngine(true);
            const count = result.removed.length;
            toast.success(`Cleaned ${count} artifact${count !== 1 ? "s" : ""} including orphan spools`);
            await refreshEngineStatus();
        } catch (e: unknown) {
            toast.error(errorMessage(e) || "Cleanup failed");
        } finally {
            cleaningSpools = false;
        }
    }

    async function handleCopyDiagnostics() {
        if (!engineStatus) {
            toast.info("Engine status not loaded");
            return;
        }
        const lines = [
            `Vociferous Diagnostics`,
            `Version: ${health.version}`,
            `Engine status: ${formatStatus(engineStatus.status)}`,
            `ASR: ${formatStatus(engineStatus.asr.state)} · ${engineStatus.asr.device ?? "-"} · ${engineStatus.asr.model_id ?? "-"}`,
            `Refinement: ${formatStatus(engineStatus.slm.state)} · ${engineStatus.slm.device ?? "-"} · ${engineStatus.slm.model_id ?? "-"}`,
            `Provider: ${activeProvider?.name ?? "-"} (${activeProvider?.kind ?? "-"})`,
            `Hardware: ${engineStatus.hardware.backend.toUpperCase()}${engineStatus.hardware.gpu_name ? " · " + engineStatus.hardware.gpu_name : ""}`,
            `GPU detail: ${health.gpu?.detail ?? "-"}`,
            `Mic: ${health.mic?.device_name ?? "-"} (${health.mic?.supports_16k ? "16kHz ok" : "16kHz unknown"})`,
            `Python: ${engineStatus.python.version} · ${engineStatus.python.platform}`,
            `Packages:`,
            ...packageEntries.map(([name, version]) => `  ${name} ${version ?? "missing"}`),
        ];
        try {
            await navigator.clipboard.writeText(lines.join("\n"));
            toast.success("Diagnostics copied to clipboard");
        } catch {
            toast.error("Could not copy diagnostics");
        }
    }
</script>

<div class="flex flex-col gap-[var(--space-5)]">
    <!-- ===== Runtime Summary ===== -->
    <section class="flex flex-col gap-[var(--space-3)]">
        <h3
            class="m-0 text-[var(--text-xs)] uppercase tracking-wider font-[var(--weight-emphasis)] text-[var(--text-tertiary)]"
        >
            Runtime
        </h3>

        <div class="flex flex-col gap-[var(--space-2)]">
            <!-- ASR row -->
            <div class="flex items-start gap-[var(--space-3)]">
                <span class="diag-icon" class:diag-icon-ok={engineStatus?.asr.ready} class:diag-icon-warn={!engineStatus?.asr.ready}>
                    {#if engineStatus?.asr.ready}<CheckCircle size={14} />{:else}<AlertCircle size={14} />{/if}
                </span>
                <div class="flex flex-col">
                    <div class="text-[var(--text-sm)] text-[var(--text-primary)]">
                        ASR: {formatStatus(engineStatus?.asr.state)}{#if engineStatus?.asr.model_name}
                            · {engineStatus.asr.model_name}{/if} · {asrLoadedDevice}
                    </div>
                    {#if engineStatus?.asr.detail}
                        <div class="text-[var(--text-xs)] text-[var(--text-tertiary)] leading-[var(--leading-normal)]">
                            {engineStatus.asr.detail}
                        </div>
                    {/if}
                </div>
            </div>

            <!-- Refinement row -->
            <div class="flex items-start gap-[var(--space-3)]">
                <span class="diag-icon" class:diag-icon-ok={engineStatus?.slm.ready} class:diag-icon-warn={!engineStatus?.slm.ready}>
                    {#if engineStatus?.slm.ready}<CheckCircle size={14} />{:else}<AlertCircle size={14} />{/if}
                </span>
                <div class="flex flex-col">
                    <div class="text-[var(--text-sm)] text-[var(--text-primary)]">
                        Refinement: {formatStatus(engineStatus?.slm.state)}{#if engineStatus?.slm.model_name}
                            · {engineStatus.slm.model_name}{/if} · {slmLoadedDevice}
                    </div>
                    {#if engineStatus?.slm.detail}
                        <div class="text-[var(--text-xs)] text-[var(--text-tertiary)] leading-[var(--leading-normal)]">
                            {engineStatus.slm.detail}
                        </div>
                    {/if}
                </div>
            </div>

            <!-- Hardware row -->
            <div class="flex items-start gap-[var(--space-3)]">
                <span class="diag-icon" class:diag-icon-ok={health.gpu?.cuda_available} class:diag-icon-warn={!health.gpu?.cuda_available}>
                    {#if health.gpu?.cuda_available}<CheckCircle size={14} />{:else}<AlertCircle size={14} />{/if}
                </span>
                <div class="flex flex-col">
                    <div class="text-[var(--text-sm)] text-[var(--text-primary)]">
                        Hardware: {engineStatus?.hardware.backend.toUpperCase() ?? "—"}{#if engineStatus?.hardware.gpu_name}
                            · {engineStatus.hardware.gpu_name}{/if}{#if engineStatus?.hardware.vram_total_mb}
                            · {Math.round(engineStatus.hardware.vram_free_mb)} MB free / {Math.round(engineStatus.hardware.vram_total_mb)} MB{/if}
                    </div>
                    {#if health.gpu?.detail}
                        <div class="text-[var(--text-xs)] text-[var(--text-tertiary)] leading-[var(--leading-normal)]">
                            {health.gpu.detail}
                        </div>
                    {/if}
                </div>
            </div>

            <!-- Microphone row -->
            <div class="flex items-start gap-[var(--space-3)]">
                <span class="diag-icon" class:diag-icon-ok={health.mic?.available} class:diag-icon-warn={!health.mic?.available}>
                    <Mic size={14} />
                </span>
                <div class="flex flex-col">
                    <div class="text-[var(--text-sm)] text-[var(--text-primary)]">
                        Microphone: {health.mic?.available ? health.mic?.device_name || "Available" : "Not detected"}
                    </div>
                    {#if health.mic?.detail}
                        <div class="text-[var(--text-xs)] text-[var(--text-tertiary)] leading-[var(--leading-normal)]">
                            {health.mic.detail}
                        </div>
                    {/if}
                </div>
            </div>
        </div>

        {#if gpuRuntimeMismatch}
            <div
                class="rounded-[var(--radius-md)] border border-amber-500/40 bg-amber-500/10 px-[var(--space-3)] py-[var(--space-2)] text-[var(--text-sm)] text-[var(--text-secondary)] flex items-start gap-[var(--space-2)]"
            >
                <TriangleAlert size={16} class="shrink-0 mt-px text-[var(--color-warning)]" />
                <span>
                    NVIDIA driver detected{#if health.gpu?.gpu_name} for {health.gpu.gpu_name}{/if}, but CTranslate2 cannot use CUDA yet.
                    Install CUDA 12 plus cuDNN 9, then restart the engine.
                </span>
            </div>
        {/if}
        {#if health.mic?.available && !health.mic?.supports_16k}
            <div
                class="rounded-[var(--radius-md)] border border-amber-500/40 bg-amber-500/10 px-[var(--space-3)] py-[var(--space-2)] text-[var(--text-sm)] text-[var(--text-secondary)] flex items-start gap-[var(--space-2)]"
            >
                <TriangleAlert size={16} class="shrink-0 mt-px text-[var(--color-warning)]" />
                <span>
                    '{health.mic.device_name}' may not support 16 kHz mono recording. Transcription quality could
                    suffer. Try a different default input device.
                </span>
            </div>
        {/if}
    </section>

    <!-- ===== Engine Controls ===== -->
    <section class="flex flex-col gap-[var(--space-3)]">
        <h3
            class="m-0 text-[var(--text-xs)] uppercase tracking-wider font-[var(--weight-emphasis)] text-[var(--text-tertiary)]"
        >
            Engine
        </h3>

        <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
            <span
                class="text-[var(--text-sm)] text-[var(--text-primary)]"
                data-tip="Reloads ASR and refinement models with the current configuration."
            >
                Engine Process
            </span>
            <div class="flex items-center gap-[var(--space-2)]">
                <StyledButton variant="secondary" onclick={onRestartEngine} disabled={restartPending}>
                    {#if restartPending}
                        <Loader2 size={14} class="spin" /> Restarting…
                    {:else}
                        <RotateCcw size={14} /> Restart Engine
                    {/if}
                </StyledButton>
                {#if !engineReady && !restartPending}
                    <span class="text-[var(--text-xs)] text-[var(--text-tertiary)]">
                        Status: {formatStatus(engineStatus?.status)}
                    </span>
                {/if}
            </div>
        </div>

        <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
            <label
                class="text-[var(--text-sm)] text-[var(--text-primary)]"
                for="setting-console-log-level"
                data-tip="Controls terminal log verbosity. On-disk log files always capture full DEBUG detail."
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
                data-tip="Open the persistent Vociferous log directory."
            >
                Log Files
            </span>
            <div>
                <StyledButton variant="secondary" onclick={handleOpenLogDirectory}>
                    <FolderOpen size={14} /> Open Log Directory
                </StyledButton>
            </div>
        </div>

        <!-- Download queue -->
        {#if engineStatus && engineStatus.downloads.length > 0}
            <div class="grid grid-cols-[200px_minmax(0,1fr)] items-start gap-x-[var(--space-4)] min-h-[36px]">
                <span class="text-[var(--text-sm)] text-[var(--text-primary)]">Active Downloads</span>
                <div class="flex flex-col gap-[var(--space-1)]">
                    {#each engineStatus.downloads.slice(0, 3) as download (`${download.model_type}-${download.model_id}`)}
                        <div class="text-[var(--text-sm)] text-[var(--text-secondary)] leading-[var(--leading-normal)]">
                            {download.model_id}: {formatStatus(download.status)} · {download.message}
                        </div>
                    {/each}
                </div>
            </div>
        {/if}
    </section>

    <!-- ===== Cleanup ===== -->
    {#if engineStatus}
        <section class="flex flex-col gap-[var(--space-3)]">
            <h3
                class="m-0 text-[var(--text-xs)] uppercase tracking-wider font-[var(--weight-emphasis)] text-[var(--text-tertiary)]"
            >
                Cleanup
            </h3>

            <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
                <span
                    class="text-[var(--text-sm)] text-[var(--text-primary)]"
                    data-tip="Temporary files written during audio imports that are no longer referenced."
                    >Temporary Imports</span
                >
                <div class="flex items-center gap-[var(--space-2)]">
                    <span class="text-[var(--text-sm)] text-[var(--text-secondary)] tabular-nums">
                        {engineStatus.cleanup.import_temp_count} file{engineStatus.cleanup.import_temp_count !== 1 ? "s" : ""}
                    </span>
                    <StyledButton
                        variant="secondary"
                        onclick={handleCleanupTemp}
                        disabled={cleaningTemp || engineStatus.cleanup.import_temp_count === 0}
                    >
                        {cleaningTemp ? "Cleaning…" : "Clean Imports"}
                    </StyledButton>
                </div>
            </div>

            <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
                <span
                    class="text-[var(--text-sm)] text-[var(--text-primary)]"
                    data-tip="Audio spool files left behind by crashed or interrupted recordings. Deleting these discards any unsaved audio."
                    >Orphan Audio Spools</span
                >
                <div class="flex items-center gap-[var(--space-2)]">
                    <span class="text-[var(--text-sm)] text-[var(--text-secondary)] tabular-nums">
                        {engineStatus.cleanup.orphan_spool_count} file{engineStatus.cleanup.orphan_spool_count !== 1 ? "s" : ""}
                    </span>
                    <StyledButton
                        variant="secondary"
                        onclick={handleCleanupSpools}
                        disabled={cleaningSpools || engineStatus.cleanup.orphan_spool_count === 0}
                    >
                        {cleaningSpools ? "Cleaning…" : "Clean Spools"}
                    </StyledButton>
                </div>
            </div>
        </section>
    {/if}

    <!-- ===== Details (collapsed) ===== -->
    <section class="flex flex-col gap-[var(--space-2)]">
        <button
            type="button"
            class="flex items-center gap-[var(--space-2)] py-[var(--space-2)] px-0 text-[var(--text-sm)] text-[var(--text-tertiary)] bg-transparent border-none cursor-pointer transition-colors duration-[var(--transition-fast)] hover:text-[var(--text-primary)] self-start"
            onclick={() => (detailsOpen = !detailsOpen)}
        >
            <ChevronDown
                size={14}
                class="transition-transform duration-[var(--transition-fast)] {detailsOpen ? 'rotate-0' : '-rotate-90'}"
            />
            {detailsOpen ? "Hide" : "Show"} low-level details
        </button>

        {#if detailsOpen}
            <div class="flex flex-col gap-[var(--space-3)] pl-[var(--space-3)] border-l-2 border-[var(--shell-border)]">
                <div class="grid grid-cols-[200px_minmax(0,1fr)] items-start gap-x-[var(--space-4)]">
                    <span class="text-[var(--text-sm)] text-[var(--text-primary)]">Provider</span>
                    <span class="text-[var(--text-sm)] text-[var(--text-secondary)]">
                        {activeProvider?.name ?? "—"} · {activeProvider?.kind ?? "—"}
                    </span>
                </div>
                {#if engineStatus}
                    <div class="grid grid-cols-[200px_minmax(0,1fr)] items-start gap-x-[var(--space-4)]">
                        <span class="text-[var(--text-sm)] text-[var(--text-primary)]">Python</span>
                        <span class="text-[var(--text-sm)] text-[var(--text-secondary)] break-words">
                            {engineStatus.python.version} · {engineStatus.python.platform}
                        </span>
                    </div>
                {/if}
                <div class="grid grid-cols-[200px_minmax(0,1fr)] items-start gap-x-[var(--space-4)]">
                    <span class="text-[var(--text-sm)] text-[var(--text-primary)]">Packages</span>
                    <div class="flex flex-col gap-[2px]">
                        {#each packageEntries as [name, version] (name)}
                            <span class="text-[var(--text-xs)] text-[var(--text-tertiary)] font-mono">
                                {name} {version ?? "missing"}
                            </span>
                        {/each}
                    </div>
                </div>
                <div>
                    <StyledButton variant="secondary" onclick={handleCopyDiagnostics}>
                        <Clipboard size={14} /> Copy Diagnostics
                    </StyledButton>
                </div>
            </div>
        {/if}
    </section>
</div>

<style>
    .diag-icon {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 22px;
        height: 22px;
        border-radius: 6px;
        flex-shrink: 0;
        margin-top: 1px;
    }
    .diag-icon-ok {
        color: var(--color-success, #22c55e);
        background: color-mix(in srgb, var(--color-success, #22c55e) 12%, transparent);
    }
    .diag-icon-warn {
        color: var(--text-tertiary);
        background: color-mix(in srgb, var(--text-tertiary) 10%, transparent);
    }
</style>
