<script lang="ts">
    /**
     * SettingsView — Tabbed configuration surface.
     *
     * Horizontal tab bar at top, one section per tab. Content scrolls
     * independently; save bar pins to the bottom.
     */

    import { getConfig, updateConfig, getModels, getHealth, downloadModel } from "../lib/api";
    import { toast } from "../lib/toast.svelte";
    import { ws } from "../lib/ws";
    import { onMount, onDestroy } from "svelte";
    import { Save, Undo2, Loader2, Cpu, Mic, Sliders, Eye, RotateCcw, Check, BarChart3, Sparkles, TriangleAlert } from "lucide-svelte";
    import CustomSelect from "../lib/components/CustomSelect.svelte";
    import KeyBindCapture from "../lib/components/KeyBindCapture.svelte";
    import MaintenanceCard from "../lib/components/MaintenanceCard.svelte";
    import OutputCard from "../lib/components/OutputCard.svelte";
    import AsrModelCard from "../lib/components/AsrModelCard.svelte";
    import RefinementCard from "../lib/components/RefinementCard.svelte";
    import StyledButton from "../lib/components/StyledButton.svelte";
    import EmptyState from "../lib/components/EmptyState.svelte";
    import ToggleSwitch from "../lib/components/ToggleSwitch.svelte";
    import type { DownloadProgressData, EngineStatusData } from "../lib/events";

    /* ===== Tabs ===== */

    type SettingsTab = "analytics" | "appearance" | "maintenance" | "output" | "recording" | "refinement" | "asr";

    const tabs: { id: SettingsTab; label: string; icon: typeof Cpu }[] = [
        { id: "analytics", label: "Analytics", icon: BarChart3 },
        { id: "appearance", label: "Appearance", icon: Eye },
        { id: "maintenance", label: "Maintenance", icon: RotateCcw },
        { id: "output", label: "Output", icon: Sliders },
        { id: "recording", label: "Recording", icon: Mic },
        { id: "refinement", label: "Refinement", icon: Sparkles },
        { id: "asr", label: "Transcription", icon: Cpu },
    ];

    let activeTab = $state<SettingsTab>("asr");

    /* ===== State ===== */

    let config: Record<string, any> = $state({});
    let originalConfig = $state("");
    let models: { asr: Record<string, any>; slm: Record<string, any> } = $state({ asr: {}, slm: {} });
    let health: {
        status: string;
        version: string;
        transcripts: number;
        gpu?: {
            cuda_available?: boolean;
            driver_detected?: boolean;
            cuda_device_count?: number;
            gpu_name?: string;
            detail?: string;
            slm_gpu_layers?: number;
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
    } = $state({
        status: "unknown",
        version: "",
        transcripts: 0,
    });
    let loading = $state(true);
    let saving = $state(false);
    let message = $state("");
    let messageType = $state<"success" | "error">("success");

    /* ===== Download state ===== */

    let downloadingModel = $state<string | null>(null);
    let downloadMessage = $state("");
    let downloadErrorAsr = $state("");
    let downloadErrorSlm = $state("");

    /* ===== Derived ===== */

    let isDirty = $derived(JSON.stringify(config) !== originalConfig);
    let showGpuRuntimeWarning = $derived(Boolean(health.gpu?.driver_detected && !health.gpu?.cuda_available));

    /* ===== Lifecycle ===== */

    let unsubDownload: (() => void) | null = null;
    let unsubEngineStatus: (() => void) | null = null;

    onMount(async () => {
        unsubDownload = ws.on("download_progress", (data: DownloadProgressData) => {
            if (data.status === "downloading") {
                downloadMessage = data.message || "Downloading...";
            } else if (data.status === "complete") {
                downloadMessage = "";
                downloadingModel = null;
                downloadErrorAsr = "";
                downloadErrorSlm = "";
                getModels()
                    .then((m) => (models = m))
                    .catch(() => {});
                showMessage(`${data.model_id} downloaded`, "success");
            } else if (data.status === "error") {
                const isSlm = Object.keys(models.slm).includes(data.model_id);
                if (isSlm) {
                    downloadErrorSlm = data.message || "Download failed";
                } else {
                    downloadErrorAsr = data.message || "Download failed";
                }
                downloadingModel = null;
                downloadMessage = "";
            }
        });

        unsubEngineStatus = ws.on("engine_status", (data: EngineStatusData) => {
            if (data?.asr === "ready") {
                showMessage("Engine restarted — ASR ready", "success");
                // Refresh health after engine restart (mic/GPU state may have changed)
                getHealth()
                    .then((h) => (health = h))
                    .catch(() => {});
            } else if (data?.asr === "unavailable") {
                showMessage("Engine restart: ASR model unavailable", "error");
            }
        });

        try {
            const [c, m, h] = await Promise.all([getConfig(), getModels(), getHealth()]);
            config = c;
            const validRecordingModes = ["press_to_toggle", "hold_to_record"];
            if (!validRecordingModes.includes(getSafe(config, "recording.recording_mode", ""))) {
                setSafe("recording.recording_mode", "press_to_toggle");
            }
            originalConfig = JSON.stringify(config);
            models = m;
            health = h;
        } catch (e: any) {
            showMessage(`Failed to load: ${e.message}`, "error");
        } finally {
            loading = false;
        }
    });

    onDestroy(() => {
        unsubDownload?.();
        unsubEngineStatus?.();
    });

    // Re-fetch health when switching to the Maintenance tab so mic status stays current
    $effect(() => {
        if (activeTab === "maintenance") {
            getHealth()
                .then((h) => (health = h))
                .catch(() => {});
        }
    });

    /* ===== Actions ===== */

    async function saveConfig() {
        saving = true;
        // Snapshot model IDs before save to detect model changes.
        const prev = JSON.parse(originalConfig);
        const prevAsr = prev?.model?.model ?? "";
        const prevSlm = prev?.refinement?.model_id ?? "";
        try {
            config = (await updateConfig(config)) as Record<string, any>;
            originalConfig = JSON.stringify(config);

            const asrChanged = prevAsr !== getSafe(config, "model.model", "");
            const slmChanged = prevSlm !== getSafe(config, "refinement.model_id", "");

            if (asrChanged || slmChanged) {
                showMessage("Settings saved — restart required to apply model change", "success");
                toast.success("Model change saved. Go to Maintenance → Restart Engine to apply.");
            } else {
                showMessage("Settings saved", "success");
                toast.success("Settings saved");
            }
        } catch (e: any) {
            showMessage(`Error: ${e.message}`, "error");
            toast.error(`Settings save failed: ${e.message}`);
        } finally {
            saving = false;
        }
    }

    function revertConfig() {
        config = JSON.parse(originalConfig);
        showMessage("Changes reverted", "success");
    }

    function showMessage(msg: string, type: "success" | "error") {
        message = msg;
        messageType = type;
        if (type === "success") setTimeout(() => (message = ""), 3000);
    }

    /* ===== Helpers ===== */

    function getSafe(obj: any, path: string, fallback: any = ""): any {
        return path.split(".").reduce((o, k) => o?.[k], obj) ?? fallback;
    }

    function setSafe(path: string, value: any) {
        const keys = path.split(".");
        let obj = config;
        for (let i = 0; i < keys.length - 1; i++) {
            if (!obj[keys[i]]) obj[keys[i]] = {};
            obj = obj[keys[i]];
        }
        obj[keys[keys.length - 1]] = value;
        config = { ...config };
    }

    /* ===== Tip bar (replaces native title= tooltips) ===== */

    let hoveredTip = $state("");

    function handleTipOver(e: Event) {
        const el = (e.target as HTMLElement).closest("[data-tip]");
        hoveredTip = el?.getAttribute("data-tip") || "";
    }

    async function handleDownload(type: "asr" | "slm", modelId: string) {
        downloadingModel = modelId;
        downloadMessage = "Starting download...";
        if (type === "asr") downloadErrorAsr = "";
        else downloadErrorSlm = "";
        try {
            await downloadModel(type, modelId);
        } catch (e: any) {
            if (type === "asr") downloadErrorAsr = e.message;
            else downloadErrorSlm = e.message;
            downloadingModel = null;
            downloadMessage = "";
        }
    }
</script>

<div class="flex flex-col h-full">
    {#if loading}
        <EmptyState icon={Loader2} message="Loading settings…" spinning />
    {:else}
        <!-- Unified scroll area — tab bar is sticky inside so both it and content share the same
             width reference for mx-auto. When a scrollbar appears it affects both equally,
             eliminating the centering offset that occurs when the tab bar is outside the scroll container. -->
        <!-- svelte-ignore a11y_mouse_events_have_key_events -->
        <div class="flex-1 overflow-y-auto" onmouseover={handleTipOver} onmouseleave={() => (hoveredTip = "")} onfocusin={handleTipOver} onfocusout={() => (hoveredTip = "")}>
            <div class="sticky top-0 z-10 border-b border-[var(--shell-border)] bg-[var(--surface-primary)]">
                <div class="w-full max-w-5xl mx-auto px-[var(--space-5)] flex gap-0" role="tablist">
                    {#each tabs as tab (tab.id)}
                        <button
                            role="tab"
                            aria-selected={activeTab === tab.id}
                            class="relative flex items-center gap-[var(--space-1)] px-[var(--space-3)] py-[var(--space-2)] text-[var(--text-sm)] border-b-2 transition-colors duration-[var(--transition-fast)] bg-transparent cursor-pointer
                                {activeTab === tab.id
                                ? 'text-[var(--accent)] border-[var(--accent)] font-[var(--weight-emphasis)]'
                                : 'text-[var(--text-tertiary)] border-transparent hover:text-[var(--text-primary)]'}"
                            onclick={() => (activeTab = tab.id)}
                        >
                            <tab.icon size={15} />
                            {tab.label}
                        </button>
                    {/each}
                </div>
            </div>

            <!-- Tab panel content -->
            <div
                class="w-full max-w-5xl mx-auto py-[var(--space-5)] px-[var(--space-5)] pb-[var(--space-7)]"
                role="tabpanel"
            >
                {#if showGpuRuntimeWarning}
                    <div class="mb-[var(--space-4)] rounded-[var(--radius-lg)] border border-[var(--color-warning)]/40 bg-[color:rgba(255,165,0,0.08)] px-[var(--space-4)] py-[var(--space-3)]">
                        <div class="flex items-start gap-[var(--space-2)]">
                            <TriangleAlert size={18} class="mt-[2px] shrink-0 text-[var(--color-warning)]" />
                            <div class="min-w-0">
                                <div class="text-[var(--text-sm)] font-[var(--weight-emphasis)] text-[var(--text-primary)]">
                                    NVIDIA driver detected, but CUDA inference is not ready.
                                </div>
                                <div class="mt-[var(--space-1)] text-[var(--text-sm)] text-[var(--text-secondary)] leading-[var(--leading-normal)]">
                                    {health.gpu?.gpu_name || "Detected GPU"} is visible to the driver, but CTranslate2 cannot use CUDA yet. Vociferous will fall back to CPU until you install a usable CUDA 12 runtime.
                                </div>
                                {#if health.gpu?.detail}
                                    <div class="mt-[var(--space-1)] text-[var(--text-xs)] text-[var(--text-tertiary)] break-words">
                                        Probe detail: {health.gpu.detail}
                                    </div>
                                {/if}
                                <div class="mt-[var(--space-2)] text-[var(--text-xs)] text-[var(--text-secondary)] leading-[var(--leading-normal)]">
                                    Recommended: install CUDA Toolkit 12.x plus cuDNN 9 on Windows. Alternative: install `nvidia-cuda-runtime-cu12`, `nvidia-cuda-nvrtc-cu12`, `nvidia-cublas-cu12`, and `nvidia-cudnn-cu12` into the app venv manually.
                                </div>
                            </div>
                        </div>
                    </div>
                {/if}

                {#if activeTab === "analytics"}
                    <div class="flex flex-col gap-[var(--space-3)]">
                        <div
                            class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]"
                        >
                            <label
                                class="text-[var(--text-sm)] text-[var(--text-primary)]"
                                for="setting-typing-wpm"
                                data-tip="Your manual typing speed. Used to calculate Time Saved on the dashboard. Default: 40 WPM."
                                >Typing Speed (WPM)</label
                            >
                            <input
                                id="setting-typing-wpm"
                                type="number"
                                min="10"
                                max="200"
                                class="h-9 w-24 rounded-[var(--radius-md)] border border-[var(--shell-border)] bg-[var(--surface-primary)] px-[var(--space-2)] text-[var(--text-sm)] text-[var(--text-primary)] [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
                                value={getSafe(config, "user.typing_wpm", 40)}
                                onchange={(e: Event) => {
                                    const v = parseInt((e.target as HTMLInputElement).value);
                                    if (!isNaN(v) && v >= 10 && v <= 200) setSafe("user.typing_wpm", v);
                                }}
                            />
                        </div>
                        <div
                            class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]"
                        >
                            <label
                                class="text-[var(--text-sm)] text-[var(--text-primary)]"
                                for="setting-exclude-imported"
                                data-tip="Automatically excludes imported audio file transcriptions from analytics calculations."
                                >Exclude Imports from Analytics</label
                            >
                            <ToggleSwitch
                                checked={getSafe(config, "output.exclude_imported_from_analytics", false)}
                                onChange={() =>
                                    setSafe(
                                        "output.exclude_imported_from_analytics",
                                        !getSafe(config, "output.exclude_imported_from_analytics", false),
                                    )}
                            />
                        </div>
                    </div>
                {:else if activeTab === "recording"}
                    <div class="flex flex-col gap-[var(--space-3)]">
                        <div
                            class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]"
                        >
                            <label
                                class="text-[var(--text-sm)] text-[var(--text-primary)]"
                                for="setting-hotkey"
                                data-tip="Click Set Key to capture a new global hotkey. Works system-wide, even when the app is in the background."
                                >Activation Key</label
                            >
                            <KeyBindCapture
                                id="setting-hotkey"
                                value={getSafe(config, "recording.activation_key") ?? ""}
                                onchange={(combo) => setSafe("recording.activation_key", combo)}
                            />
                        </div>
                        <div
                            class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]"
                        >
                            <label
                                class="text-[var(--text-sm)] text-[var(--text-primary)]"
                                for="setting-recmode"
                                data-tip="Toggle: press once to start, again to stop. Hold: hold key to record, release to stop."
                                >Recording Mode</label
                            >
                            <div class="w-full max-w-[460px]">
                                <CustomSelect
                                    id="setting-recmode"
                                    options={[
                                        { value: "press_to_toggle", label: "Press to Toggle" },
                                        { value: "hold_to_record", label: "Hold to Record" },
                                    ]}
                                    value={getSafe(config, "recording.recording_mode", "press_to_toggle")}
                                    onchange={(v: string) => setSafe("recording.recording_mode", v)}
                                />
                            </div>
                        </div>
                        <div
                            class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]"
                        >
                            <label
                                class="text-[var(--text-sm)] text-[var(--text-primary)]"
                                for="setting-max-recording-minutes"
                                data-tip="Safety cap for a single recording session. Prevents runaway recordings from chewing through disk and time forever."
                                >Max Recording Length (minutes)</label
                            >
                            <div class="flex items-center gap-[var(--space-1)]">
                                <button
                                    type="button"
                                    class="flex items-center justify-center w-9 h-9 rounded-[var(--radius-md)] border border-[var(--shell-border)] bg-[var(--surface-primary)] text-[var(--accent)] cursor-pointer transition-colors duration-150 hover:bg-[var(--hover-overlay-blue)] disabled:opacity-40 disabled:cursor-not-allowed"
                                    aria-label="Decrease max recording length"
                                    disabled={getSafe(config, "recording.max_recording_minutes", 60) <= 1}
                                    onclick={() => {
                                        const cur = getSafe(config, "recording.max_recording_minutes", 60);
                                        if (cur > 1) setSafe("recording.max_recording_minutes", Math.max(1, cur - 5));
                                    }}
                                >
                                    <svg width="14" height="14" viewBox="0 0 14 14"
                                        ><path
                                            d="M3 7h8"
                                            stroke="currentColor"
                                            stroke-width="1.5"
                                            stroke-linecap="round"
                                        /></svg
                                    >
                                </button>
                                <input
                                    id="setting-max-recording-minutes"
                                    type="number"
                                    min="1"
                                    max="1440"
                                    step="5"
                                    class="h-9 w-24 rounded-[var(--radius-md)] border border-[var(--shell-border)] bg-[var(--surface-primary)] px-[var(--space-2)] text-[var(--text-sm)] text-[var(--text-primary)] text-center [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                                    value={getSafe(config, "recording.max_recording_minutes", 60)}
                                    oninput={(e) => {
                                        const v = parseFloat((e.target as HTMLInputElement).value);
                                        if (!isNaN(v) && v >= 1 && v <= 1440)
                                            setSafe("recording.max_recording_minutes", v);
                                    }}
                                />
                                <button
                                    type="button"
                                    class="flex items-center justify-center w-9 h-9 rounded-[var(--radius-md)] border border-[var(--shell-border)] bg-[var(--surface-primary)] text-[var(--accent)] cursor-pointer transition-colors duration-150 hover:bg-[var(--hover-overlay-blue)] disabled:opacity-40 disabled:cursor-not-allowed"
                                    aria-label="Increase max recording length"
                                    disabled={getSafe(config, "recording.max_recording_minutes", 60) >= 1440}
                                    onclick={() => {
                                        const cur = getSafe(config, "recording.max_recording_minutes", 60);
                                        if (cur < 1440)
                                            setSafe("recording.max_recording_minutes", Math.min(1440, cur + 5));
                                    }}
                                >
                                    <svg width="14" height="14" viewBox="0 0 14 14"
                                        ><path
                                            d="M7 3v8M3 7h8"
                                            stroke="currentColor"
                                            stroke-width="1.5"
                                            stroke-linecap="round"
                                        /></svg
                                    >
                                </button>
                            </div>
                        </div>
                        <div
                            class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]"
                        >
                            <label
                                class="text-[var(--text-sm)] text-[var(--text-primary)]"
                                for="setting-audiocache"
                                data-tip="Keep recorded audio on disk for crash recovery. Oldest recordings are pruned when the limit is exceeded. Set to 0 to disable."
                                >Audio Cache (minutes)</label
                            >
                            <div class="flex items-center gap-[var(--space-1)]">
                                <button
                                    type="button"
                                    class="flex items-center justify-center w-9 h-9 rounded-[var(--radius-md)] border border-[var(--shell-border)] bg-[var(--surface-primary)] text-[var(--accent)] cursor-pointer transition-colors duration-150 hover:bg-[var(--hover-overlay-blue)] disabled:opacity-40 disabled:cursor-not-allowed"
                                    aria-label="Decrease audio cache"
                                    disabled={getSafe(config, "recording.audio_cache_minutes", 60) <= 0}
                                    onclick={() => {
                                        const cur = getSafe(config, "recording.audio_cache_minutes", 60);
                                        if (cur > 0) setSafe("recording.audio_cache_minutes", Math.max(0, cur - 15));
                                    }}
                                >
                                    <svg width="14" height="14" viewBox="0 0 14 14"
                                        ><path
                                            d="M3 7h8"
                                            stroke="currentColor"
                                            stroke-width="1.5"
                                            stroke-linecap="round"
                                        /></svg
                                    >
                                </button>
                                <input
                                    id="setting-audiocache"
                                    type="number"
                                    min="0"
                                    max="480"
                                    step="15"
                                    class="h-9 w-20 rounded-[var(--radius-md)] border border-[var(--shell-border)] bg-[var(--surface-primary)] px-[var(--space-2)] text-[var(--text-sm)] text-[var(--text-primary)] text-center [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                                    value={getSafe(config, "recording.audio_cache_minutes", 60)}
                                    oninput={(e) => {
                                        const v = parseFloat((e.target as HTMLInputElement).value);
                                        if (!isNaN(v) && v >= 0 && v <= 480)
                                            setSafe("recording.audio_cache_minutes", v);
                                    }}
                                />
                                <button
                                    type="button"
                                    class="flex items-center justify-center w-9 h-9 rounded-[var(--radius-md)] border border-[var(--shell-border)] bg-[var(--surface-primary)] text-[var(--accent)] cursor-pointer transition-colors duration-150 hover:bg-[var(--hover-overlay-blue)] disabled:opacity-40 disabled:cursor-not-allowed"
                                    aria-label="Increase audio cache"
                                    disabled={getSafe(config, "recording.audio_cache_minutes", 60) >= 480}
                                    onclick={() => {
                                        const cur = getSafe(config, "recording.audio_cache_minutes", 60);
                                        if (cur < 480)
                                            setSafe("recording.audio_cache_minutes", Math.min(480, cur + 15));
                                    }}
                                >
                                    <svg width="14" height="14" viewBox="0 0 14 14"
                                        ><path
                                            d="M7 3v8M3 7h8"
                                            stroke="currentColor"
                                            stroke-width="1.5"
                                            stroke-linecap="round"
                                        /></svg
                                    >
                                </button>
                            </div>
                        </div>
                    </div>
                {:else if activeTab === "output"}
                    <OutputCard {config} {getSafe} {setSafe} />
                {:else if activeTab === "appearance"}
                    <div class="flex flex-col gap-[var(--space-3)]">
                        <div
                            class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]"
                        >
                            <label
                                class="text-[var(--text-sm)] text-[var(--text-primary)]"
                                for="setting-uiscale"
                                data-tip="Scale the entire interface. Useful for high-DPI displays or accessibility."
                                >UI Scale</label
                            >
                            <div class="w-full max-w-[460px]">
                                <CustomSelect
                                    id="setting-uiscale"
                                    options={[
                                        { value: "75", label: "75%" },
                                        { value: "90", label: "90%" },
                                        { value: "100", label: "100%" },
                                        { value: "125", label: "125%" },
                                        { value: "150", label: "150%" },
                                        { value: "175", label: "175%" },
                                        { value: "200", label: "200%" },
                                    ]}
                                    value={String(getSafe(config, "display.ui_scale", 100))}
                                    onchange={(v: string) => setSafe("display.ui_scale", parseInt(v, 10))}
                                />
                            </div>
                        </div>
                        <div
                            class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]"
                        >
                            <label
                                class="text-[var(--text-sm)] text-[var(--text-primary)]"
                                for="setting-username"
                                data-tip="Your name. Used in the greeting on the Transcribe screen and the title of your Vociferous Journey."
                                >Your Name</label
                            >
                            <input
                                id="setting-username"
                                type="text"
                                maxlength="40"
                                class="h-9 w-48 rounded-[var(--radius-md)] border border-[var(--shell-border)] bg-[var(--surface-primary)] px-[var(--space-2)] text-[var(--text-sm)] text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)]"
                                placeholder="Optional"
                                value={getSafe(config, "user.name", "")}
                                oninput={(e) => setSafe("user.name", (e.target as HTMLInputElement).value)}
                            />
                        </div>
                    </div>
                {:else if activeTab === "maintenance"}
                    <MaintenanceCard {config} {models} {health} {getSafe} {setSafe} {showMessage} />
                {:else if activeTab === "refinement"}
                    <RefinementCard
                        {config}
                        {models}
                        {downloadingModel}
                        {downloadMessage}
                        {downloadErrorSlm}
                        {getSafe}
                        {setSafe}
                        {handleDownload}
                    />
                {:else if activeTab === "asr"}
                    <AsrModelCard
                        {config}
                        {models}
                        {downloadingModel}
                        {downloadMessage}
                        {downloadErrorAsr}
                        {getSafe}
                        {setSafe}
                        {handleDownload}
                    />
                {/if}
            </div>
        </div>

        <!-- Tip bar — shows data-tip text when hovering a setting label -->
        <div
            class="shrink-0 h-7 flex items-center justify-center px-[var(--space-4)] text-[11px] text-[var(--text-tertiary)] italic overflow-hidden transition-opacity duration-150 {hoveredTip
                ? 'opacity-100'
                : 'opacity-0'}"
        >
            {hoveredTip}
        </div>

        <!-- Save bar -->
        <div
            class="shrink-0 border-t border-[var(--shell-border)] bg-[var(--surface-primary)] py-[var(--space-2)] px-[var(--space-4)] transition-[opacity,max-height] duration-[var(--transition-normal)] {isDirty ||
            message
                ? 'opacity-100 max-h-20'
                : 'opacity-0 max-h-0 overflow-hidden'}"
        >
            <div class="flex items-center gap-[var(--space-2)] w-full mx-auto">
                {#if message}
                    <span
                        class="text-[var(--text-xs)] flex items-center gap-1 {messageType === 'error'
                            ? 'text-[var(--color-danger)]'
                            : 'text-[var(--color-success)]'}"
                    >
                        {#if messageType === "success"}<Check size={14} />{/if}
                        {message}
                    </span>
                {/if}
                <div class="flex-1"></div>
                {#if isDirty}
                    <StyledButton variant="ghost" size="sm" onclick={revertConfig} disabled={saving}>
                        <Undo2 size={14} /> Revert
                    </StyledButton>
                    <StyledButton variant="primary" size="sm" onclick={saveConfig} disabled={saving}>
                        {#if saving}<Loader2 size={14} class="spin" /> Saving…{:else}<Save size={14} /> Save Settings{/if}
                    </StyledButton>
                {/if}
            </div>
        </div>
    {/if}
</div>
