<script lang="ts">
    /**
     * SettingsView — Card-based configuration surface.
     *
     * Ported from PyQt6 SettingsView with:
     * - Scrollable content centered within min/max width
     * - Card-based sections: ASR, Recording, Output, Visualization, Calibration
     * - ToggleSwitch for boolean settings
     * - History and application controls
     * - Save/cancel footer
     */

    import {
        getConfig,
        updateConfig,
        getModels,
        getHealth,
        downloadModel,
        restartEngine,
        getTranscripts,
        clearAllTranscripts,
    } from "../lib/api";
    import type { ModelInfo } from "../lib/api";
    import { ws } from "../lib/ws";
    import { onMount, onDestroy } from "svelte";
    import {
        Save,
        Undo2,
        Loader2,
        Cpu,
        Mic,
        Sliders,
        Eye,
        RotateCcw,
        Activity,
        Check,
        Download,
        CheckCircle,
        AlertCircle,
    } from "lucide-svelte";
    import ToggleSwitch from "../lib/components/ToggleSwitch.svelte";
    import StyledButton from "../lib/components/StyledButton.svelte";
    import CustomSelect from "../lib/components/CustomSelect.svelte";
    import KeyBindCapture from "../lib/components/KeyBindCapture.svelte";
    import type { DownloadProgressData, EngineStatusData } from "../lib/events";

    /* ===== State ===== */

    let config: Record<string, any> = $state({});
    let originalConfig = $state("");
    let models: { asr: Record<string, any>; slm: Record<string, any> } = $state({ asr: {}, slm: {} });
    let health: {
        status: string;
        version: string;
        transcripts: number;
        gpu?: { cuda_available?: boolean; detail?: string; whisper_backends?: string; slm_gpu_layers?: number };
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

    /* ===== Lifecycle ===== */

    let unsubDownload: (() => void) | null = null;
    let unsubEngineStatus: (() => void) | null = null;

    onMount(async () => {
        // Subscribe to download progress events
        unsubDownload = ws.on("download_progress", (data: DownloadProgressData) => {
            if (data.status === "downloading") {
                downloadMessage = data.message || "Downloading...";
            } else if (data.status === "complete") {
                downloadMessage = "";
                downloadingModel = null;
                downloadErrorAsr = "";
                downloadErrorSlm = "";
                // Refresh model list to update downloaded status
                getModels()
                    .then((m) => (models = m))
                    .catch(() => {});
                showMessage(`${data.model_id} downloaded`, "success");
            } else if (data.status === "error") {
                // Route error to the correct section
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

        // Subscribe to engine status updates (e.g. after restart)
        unsubEngineStatus = ws.on("engine_status", (data: EngineStatusData) => {
            if (data?.asr === "ready") {
                showMessage("Engine restarted — ASR ready", "success");
            } else if (data?.asr === "unavailable") {
                showMessage("Engine restart: ASR model unavailable", "error");
            }
        });

        try {
            const [c, m, h] = await Promise.all([getConfig(), getModels(), getHealth()]);
            config = c;
            originalConfig = JSON.stringify(c);
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

    /* ===== Actions ===== */

    async function saveConfig() {
        saving = true;
        try {
            config = (await updateConfig(config)) as Record<string, any>;
            originalConfig = JSON.stringify(config);
            showMessage("Settings saved", "success");
        } catch (e: any) {
            showMessage(`Error: ${e.message}`, "error");
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

    /* ── History controls ── */
    let clearingHistory = $state(false);

    async function handleExportHistory() {
        try {
            const transcripts = await getTranscripts(99999);
            const blob = new Blob([JSON.stringify(transcripts, null, 2)], { type: "application/json" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `vociferous-export-${new Date().toISOString().slice(0, 10)}.json`;
            a.click();
            URL.revokeObjectURL(url);
            message = `Exported ${transcripts.length} transcript${transcripts.length !== 1 ? "s" : ""}`;
            messageType = "success";
        } catch (e: any) {
            message = e.message || "Export failed";
            messageType = "error";
        }
    }

    async function handleClearHistory() {
        if (!confirm("This will permanently delete ALL transcripts and their variants. Continue?")) return;
        clearingHistory = true;
        try {
            const result = await clearAllTranscripts();
            message = `Cleared ${result.deleted} transcript${result.deleted !== 1 ? "s" : ""}`;
            messageType = "success";
        } catch (e: any) {
            message = e.message || "Clear failed";
            messageType = "error";
        } finally {
            clearingHistory = false;
        }
    }

    async function handleRestartEngine() {
        message = "Restarting engine…";
        messageType = "success";
        try {
            await restartEngine();
        } catch (e: any) {
            message = e.message || "Engine restart failed";
            messageType = "error";
        }
    }
</script>

<div class="flex flex-col h-full overflow-hidden">
    {#if loading}
        <div
            class="flex-1 flex flex-col items-center justify-center gap-[var(--space-2)] text-[var(--text-tertiary)] text-[var(--text-sm)]"
        >
            <Loader2 size={24} class="spin" /><span>Loading settings…</span>
        </div>
    {:else}
        <!-- Scrollable content -->
        <div class="flex-1 overflow-y-auto overflow-x-hidden">
            <div
                class="w-full min-w-[var(--content-min-width)] mx-auto py-[var(--space-5)] px-[var(--space-5)] pb-[var(--space-7)] flex flex-col gap-[var(--space-4)]"
            >
                <!-- System Status -->
                <div
                    class="flex items-center gap-[var(--space-2)] px-[var(--space-4)] py-[var(--space-2)] rounded-[var(--radius-md)] bg-[var(--surface-secondary)] border border-[var(--shell-border)]"
                >
                    <Activity size={14} class="text-[var(--text-tertiary)] shrink-0" />
                    <span
                        class="w-2 h-2 rounded-full shrink-0 transition-[background] duration-[var(--transition-fast)] {health.status ===
                        'ok'
                            ? 'bg-[var(--color-success)]'
                            : 'bg-[var(--color-danger)]'}"
                    ></span>
                    <span class="text-[var(--text-sm)] text-[var(--text-secondary)]">
                        {health.status === "ok" ? "Online" : health.status}
                        {#if health.version}
                            · v{health.version}{/if}
                        · {health.transcripts} transcript{health.transcripts !== 1 ? "s" : ""}
                    </span>
                </div>

                <div class="grid grid-cols-1 xl:grid-cols-2 gap-[var(--space-4)] items-start">
                    <!-- ASR Model Settings -->
                    <div
                        class="bg-[var(--surface-secondary)] border border-[var(--shell-border)] rounded-[var(--radius-lg)] p-[var(--space-4)] xl:col-span-2"
                    >
                        <div
                            class="flex items-center gap-[var(--space-2)] text-[var(--text-base)] font-[var(--weight-emphasis)] text-[var(--text-primary)] mb-[var(--space-4)] pb-[var(--space-2)] border-b border-[var(--shell-border)]"
                        >
                            <Cpu size={18} class="text-[var(--accent)]" /><span>Whisper ASR</span>
                        </div>
                        <div class="flex flex-col gap-[var(--space-3)]">
                            <div class="flex items-start justify-between gap-[var(--space-3)] min-h-[36px]">
                                <label
                                    class="text-[var(--text-base)] text-[var(--text-secondary)] shrink-0 min-w-[160px] pt-2"
                                    for="setting-model">Whisper Architecture</label
                                >
                                <div class="flex flex-col gap-1 flex-1">
                                    <div class="flex items-center gap-[var(--space-2)] flex-1">
                                        <CustomSelect
                                            id="setting-model"
                                            options={Object.entries(models.asr).map(([id, m]) => ({
                                                value: id,
                                                label: `${(m as any).name} (${(m as any).size_mb}MB)${(m as any).downloaded ? "" : " ⬇"}`,
                                            }))}
                                            value={String(getSafe(config, "model.model", ""))}
                                            onchange={(v: string) => setSafe("model.model", v)}
                                            placeholder="Select model…"
                                        />
                                        {#if models.asr[getSafe(config, "model.model")]}
                                            {@const selectedAsr = models.asr[getSafe(config, "model.model")] as any}
                                            {#if !selectedAsr.downloaded}
                                                {#if downloadingModel === getSafe(config, "model.model")}
                                                    <span
                                                        class="inline-flex items-center gap-1 text-[var(--text-xs)] whitespace-nowrap text-[var(--accent)] shrink overflow-hidden"
                                                    >
                                                        <Loader2 size={14} class="spin" />
                                                        <span class="overflow-hidden text-ellipsis whitespace-nowrap"
                                                            >{downloadMessage}</span
                                                        >
                                                    </span>
                                                {:else}
                                                    <button
                                                        class="inline-flex items-center gap-1 py-1.5 px-3 border border-[var(--accent)] rounded-[var(--radius-sm)] bg-transparent text-[var(--accent)] font-[var(--font-family)] text-[var(--text-xs)] font-[var(--weight-emphasis)] cursor-pointer whitespace-nowrap transition-[background,color] duration-[var(--transition-fast)] hover:bg-[var(--accent)] hover:text-[var(--gray-0)]"
                                                        onclick={() =>
                                                            handleDownload("asr", getSafe(config, "model.model"))}
                                                    >
                                                        <Download size={14} /> Download
                                                    </button>
                                                {/if}
                                            {:else}
                                                <span
                                                    class="inline-flex items-center gap-1 text-[var(--text-xs)] whitespace-nowrap text-[var(--color-success)]"
                                                    ><CheckCircle size={14} /></span
                                                >
                                            {/if}
                                        {/if}
                                    </div>
                                    <span class="text-[var(--text-xs)] text-[var(--text-tertiary)] italic"
                                        >Larger models are slower but more accurate. Tiny/Base are fast; Small/Medium
                                        offer better quality.</span
                                    >
                                </div>
                            </div>
                            {#if downloadErrorAsr && !downloadingModel}
                                <div
                                    class="flex items-start gap-1 text-[var(--text-xs)] text-[var(--color-danger)] py-1"
                                >
                                    <AlertCircle size={14} />
                                    <span class="break-words leading-[var(--leading-normal)]">{downloadErrorAsr}</span>
                                </div>
                            {/if}
                            <div class="flex items-start justify-between gap-[var(--space-3)] min-h-[36px]">
                                <div
                                    class="text-[var(--text-base)] text-[var(--text-secondary)] shrink-0 min-w-[160px] pt-2"
                                >
                                    GPU Status
                                </div>
                                <div class="flex flex-col gap-1 flex-1">
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
                                    <span class="text-[var(--text-xs)] text-[var(--text-tertiary)] italic">
                                        ASR GPU requires pywhispercpp compiled with GGML_CUDA=1.
                                        {#if health.gpu?.whisper_backends && health.gpu.whisper_backends !== "unavailable"}
                                            {@const features = health.gpu.whisper_backends
                                                .split("|")
                                                .map((s: string) => s.trim().split(" = "))
                                                .filter((p: string[]) => p.length === 2 && p[1] === "1")
                                                .map((p: string[]) => p[0])}
                                            {#if features.length}
                                                <br />Active backends: {features.join(", ")}
                                            {/if}
                                        {/if}
                                    </span>
                                </div>
                            </div>
                            <div class="flex items-start justify-between gap-[var(--space-3)] min-h-[36px]">
                                <label
                                    class="text-[var(--text-base)] text-[var(--text-secondary)] shrink-0 min-w-[160px] pt-2"
                                    for="setting-threads">ASR Threads</label
                                >
                                <div class="flex flex-col gap-1 flex-1">
                                    <input
                                        id="setting-threads"
                                        class="flex-1 h-10 max-w-[280px] bg-[var(--surface-primary)] border border-[var(--shell-border)] rounded-[var(--radius-sm)] text-[var(--text-primary)] font-[var(--font-family)] text-[var(--text-sm)] px-[var(--space-2)] outline-none transition-[border-color] duration-[var(--transition-fast)] focus:border-[var(--accent)] placeholder:text-[var(--text-tertiary)]"
                                        type="number"
                                        min="1"
                                        max="32"
                                        value={getSafe(config, "model.n_threads", 4)}
                                        oninput={(e) => {
                                            const v = parseInt((e.target as HTMLInputElement).value);
                                            if (!isNaN(v) && v >= 1 && v <= 32) setSafe("model.n_threads", v);
                                        }}
                                    />
                                    <span class="text-[var(--text-xs)] text-[var(--text-tertiary)] italic"
                                        >CPU threads for whisper.cpp inference. Default 4. Higher values use more cores
                                        but may improve speed.</span
                                    >
                                </div>
                            </div>
                            <div class="flex items-start justify-between gap-[var(--space-3)] min-h-[36px]">
                                <label
                                    class="text-[var(--text-base)] text-[var(--text-secondary)] shrink-0 min-w-[160px] pt-2"
                                    for="setting-language">Language</label
                                >
                                <div class="flex flex-col gap-1 flex-1">
                                    <input
                                        id="setting-language"
                                        class="flex-1 h-10 max-w-[280px] bg-[var(--surface-primary)] border border-[var(--shell-border)] rounded-[var(--radius-sm)] text-[var(--text-primary)] font-[var(--font-family)] text-[var(--text-sm)] px-[var(--space-2)] outline-none transition-[border-color] duration-[var(--transition-fast)] focus:border-[var(--accent)] placeholder:text-[var(--text-tertiary)]"
                                        type="text"
                                        value={getSafe(config, "model.language", "en")}
                                        oninput={(e) => setSafe("model.language", (e.target as HTMLInputElement).value)}
                                        placeholder="en"
                                        maxlength="3"
                                    />
                                    <span class="text-[var(--text-xs)] text-[var(--text-tertiary)] italic"
                                        >ISO 639-1 code: "en" for English, "es" for Spanish, "fr" for French, etc.</span
                                    >
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Recording Settings -->
                    <div
                        class="bg-[var(--surface-secondary)] border border-[var(--shell-border)] rounded-[var(--radius-lg)] p-[var(--space-4)]"
                    >
                        <div
                            class="flex items-center gap-[var(--space-2)] text-[var(--text-base)] font-[var(--weight-emphasis)] text-[var(--text-primary)] mb-[var(--space-4)] pb-[var(--space-2)] border-b border-[var(--shell-border)]"
                        >
                            <Mic size={18} class="text-[var(--accent)]" /><span>Recording</span>
                        </div>
                        <div class="flex flex-col gap-[var(--space-3)]">
                            <div class="flex items-start justify-between gap-[var(--space-3)] min-h-[36px]">
                                <label
                                    class="text-[var(--text-base)] text-[var(--text-secondary)] shrink-0 min-w-[160px] pt-2"
                                    for="setting-hotkey">Activation Key</label
                                >
                                <div class="flex flex-col gap-1 flex-1">
                                    <KeyBindCapture
                                        id="setting-hotkey"
                                        value={getSafe(config, "recording.activation_key") ?? ""}
                                        onchange={(combo) => setSafe("recording.activation_key", combo)}
                                    />
                                    <span class="text-[var(--text-xs)] text-[var(--text-tertiary)] italic"
                                        >Left: current binding. Right: click Set Key to capture a new global hotkey.
                                        Works system-wide, even when the app is in the background.</span
                                    >
                                </div>
                            </div>
                            <div class="flex items-start justify-between gap-[var(--space-3)] min-h-[36px]">
                                <label
                                    class="text-[var(--text-base)] text-[var(--text-secondary)] shrink-0 min-w-[160px] pt-2"
                                    for="setting-recmode">Recording Mode</label
                                >
                                <div class="flex flex-col gap-1 flex-1">
                                    <CustomSelect
                                        id="setting-recmode"
                                        options={[
                                            { value: "press_to_toggle", label: "Press to Toggle" },
                                            { value: "hold_to_record", label: "Hold to Record" },
                                            { value: "continuous", label: "Continuous (VAD)" },
                                        ]}
                                        value={getSafe(config, "recording.recording_mode", "press_to_toggle")}
                                        onchange={(v: string) => setSafe("recording.recording_mode", v)}
                                    />
                                    <span class="text-[var(--text-xs)] text-[var(--text-tertiary)] italic"
                                        >Toggle: Press once to start, again to stop. Hold: Hold to record, release to
                                        stop.</span
                                    >
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Appearance -->
                    <div
                        class="bg-[var(--surface-secondary)] border border-[var(--shell-border)] rounded-[var(--radius-lg)] p-[var(--space-4)]"
                    >
                        <div
                            class="flex items-center gap-[var(--space-2)] text-[var(--text-base)] font-[var(--weight-emphasis)] text-[var(--text-primary)] mb-[var(--space-4)] pb-[var(--space-2)] border-b border-[var(--shell-border)]"
                        >
                            <Eye size={18} class="text-[var(--accent)]" /><span>Appearance</span>
                        </div>
                        <div class="flex flex-col gap-[var(--space-3)]">
                            <div class="flex items-start justify-between gap-[var(--space-3)] min-h-[36px]">
                                <label
                                    class="text-[var(--text-base)] text-[var(--text-secondary)] shrink-0 min-w-[160px] pt-2"
                                    for="setting-viztype">Spectrum Type</label
                                >
                                <div class="flex flex-col gap-1 flex-1">
                                    <CustomSelect
                                        id="setting-viztype"
                                        options={[
                                            { value: "bar", label: "Bar Spectrum" },
                                            { value: "none", label: "None" },
                                        ]}
                                        value={getSafe(config, "visualizer.type", "bar")}
                                        onchange={(v: string) => setSafe("visualizer.type", v)}
                                    />
                                    <span class="text-[var(--text-xs)] text-[var(--text-tertiary)] italic"
                                        >Audio visualizer shown during recording. "None" disables it to save CPU.</span
                                    >
                                </div>
                            </div>
                            <div class="flex items-start justify-between gap-[var(--space-3)] min-h-[36px]">
                                <label
                                    class="text-[var(--text-base)] text-[var(--text-secondary)] shrink-0 min-w-[160px] pt-2"
                                    for="setting-uiscale">UI Scale</label
                                >
                                <div class="flex flex-col gap-1 flex-1">
                                    <CustomSelect
                                        id="setting-uiscale"
                                        options={[
                                            { value: "100", label: "100%" },
                                            { value: "125", label: "125%" },
                                            { value: "150", label: "150%" },
                                            { value: "175", label: "175%" },
                                            { value: "200", label: "200%" },
                                        ]}
                                        value={String(getSafe(config, "display.ui_scale", 100))}
                                        onchange={(v: string) => setSafe("display.ui_scale", parseInt(v, 10))}
                                    />
                                    <span class="text-[var(--text-xs)] text-[var(--text-tertiary)] italic"
                                        >Scale the entire interface. Useful for high-DPI displays or accessibility.</span
                                    >
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Output & Processing -->
                    <div
                        class="bg-[var(--surface-secondary)] border border-[var(--shell-border)] rounded-[var(--radius-lg)] p-[var(--space-4)] xl:col-span-2"
                    >
                        <div
                            class="flex items-center gap-[var(--space-2)] text-[var(--text-base)] font-[var(--weight-emphasis)] text-[var(--text-primary)] mb-[var(--space-4)] pb-[var(--space-2)] border-b border-[var(--shell-border)]"
                        >
                            <Sliders size={18} class="text-[var(--accent)]" /><span>Output & Processing</span>
                        </div>
                        <div class="flex flex-col gap-[var(--space-3)]">
                            <div class="flex items-start justify-between gap-[var(--space-3)] min-h-[36px]">
                                <label
                                    class="text-[var(--text-base)] text-[var(--text-secondary)] shrink-0 min-w-[160px] pt-2"
                                    for="setting-trailing">Add Trailing Space</label
                                >
                                <div class="flex flex-col gap-1 flex-1">
                                    <ToggleSwitch
                                        checked={getSafe(config, "output.add_trailing_space", false)}
                                        onChange={() =>
                                            setSafe(
                                                "output.add_trailing_space",
                                                !getSafe(config, "output.add_trailing_space", false),
                                            )}
                                    />
                                    <span class="text-[var(--text-xs)] text-[var(--text-tertiary)] italic"
                                        >Appends a space after each transcription for seamless dictation into text
                                        fields.</span
                                    >
                                </div>
                            </div>
                            <div class="flex items-start justify-between gap-[var(--space-3)] min-h-[36px]">
                                <label
                                    class="text-[var(--text-base)] text-[var(--text-secondary)] shrink-0 min-w-[160px] pt-2"
                                    for="setting-autocopy">Auto-Copy to Clipboard</label
                                >
                                <div class="flex flex-col gap-1 flex-1">
                                    <ToggleSwitch
                                        checked={getSafe(config, "output.auto_copy_to_clipboard", true)}
                                        onChange={() =>
                                            setSafe(
                                                "output.auto_copy_to_clipboard",
                                                !getSafe(config, "output.auto_copy_to_clipboard", true),
                                            )}
                                    />
                                    <span class="text-[var(--text-xs)] text-[var(--text-tertiary)] italic"
                                        >Automatically copies transcription to clipboard when complete. Works even when
                                        the window is not focused.</span
                                    >
                                </div>
                            </div>
                            <div class="flex items-start justify-between gap-[var(--space-3)] min-h-[36px]">
                                <label
                                    class="text-[var(--text-base)] text-[var(--text-secondary)] shrink-0 min-w-[160px] pt-2"
                                    for="setting-refinement">Grammar Refinement</label
                                >
                                <div class="flex flex-col gap-1 flex-1">
                                    <ToggleSwitch
                                        checked={getSafe(config, "refinement.enabled", false)}
                                        onChange={() =>
                                            setSafe(
                                                "refinement.enabled",
                                                !getSafe(config, "refinement.enabled", false),
                                            )}
                                    />
                                    <span class="text-[var(--text-xs)] text-[var(--text-tertiary)] italic"
                                        >Uses a local language model to improve grammar and punctuation after
                                        transcription.</span
                                    >
                                </div>
                            </div>
                            {#if getSafe(config, "refinement.enabled", false)}
                                <div class="flex items-start justify-between gap-[var(--space-3)] min-h-[36px]">
                                    <label
                                        class="text-[var(--text-base)] text-[var(--text-secondary)] shrink-0 min-w-[160px] pt-2"
                                        for="setting-refmodel">Refinement Model</label
                                    >
                                    <div class="flex flex-col gap-1 flex-1">
                                        <div class="flex items-center gap-[var(--space-2)] flex-1">
                                            <CustomSelect
                                                id="setting-refmodel"
                                                options={Object.entries(models.slm).map(([id, m]) => ({
                                                    value: id,
                                                    label: `${(m as any).name} (${(m as any).size_mb}MB)${(m as any).downloaded ? "" : " ⬇"}`,
                                                }))}
                                                value={getSafe(config, "refinement.model_id", "qwen4b")}
                                                onchange={(v: string) => setSafe("refinement.model_id", v)}
                                                placeholder="Select model…"
                                            />
                                            {#if models.slm[getSafe(config, "refinement.model_id", "qwen4b")]}
                                                {@const selectedSlm = models.slm[
                                                    getSafe(config, "refinement.model_id", "qwen4b")
                                                ] as any}
                                                {#if !selectedSlm.downloaded}
                                                    {#if downloadingModel === getSafe(config, "refinement.model_id", "qwen4b")}
                                                        <span
                                                            class="inline-flex items-center gap-1 text-[var(--text-xs)] whitespace-nowrap text-[var(--accent)] shrink overflow-hidden"
                                                        >
                                                            <Loader2 size={14} class="spin" />
                                                            <span
                                                                class="overflow-hidden text-ellipsis whitespace-nowrap"
                                                                >{downloadMessage}</span
                                                            >
                                                        </span>
                                                    {:else}
                                                        <button
                                                            class="inline-flex items-center gap-1 py-1.5 px-3 border border-[var(--accent)] rounded-[var(--radius-sm)] bg-transparent text-[var(--accent)] font-[var(--font-family)] text-[var(--text-xs)] font-[var(--weight-emphasis)] cursor-pointer whitespace-nowrap transition-[background,color] duration-[var(--transition-fast)] hover:bg-[var(--accent)] hover:text-[var(--gray-0)]"
                                                            onclick={() =>
                                                                handleDownload(
                                                                    "slm",
                                                                    getSafe(config, "refinement.model_id", "qwen4b"),
                                                                )}
                                                        >
                                                            <Download size={14} /> Download
                                                        </button>
                                                    {/if}
                                                {:else}
                                                    <span
                                                        class="inline-flex items-center gap-1 text-[var(--text-xs)] whitespace-nowrap text-[var(--color-success)]"
                                                        ><CheckCircle size={14} /></span
                                                    >
                                                {/if}
                                            {/if}
                                        </div>
                                        <span class="text-[var(--text-xs)] text-[var(--text-tertiary)] italic"
                                            >Larger models produce better refinements but use more RAM and are slower.</span
                                        >
                                    </div>
                                </div>
                                {#if downloadErrorSlm && !downloadingModel}
                                    <div
                                        class="flex items-start gap-1 text-[var(--text-xs)] text-[var(--color-danger)] py-1"
                                    >
                                        <AlertCircle size={14} />
                                        <span class="break-words leading-[var(--leading-normal)]"
                                            >{downloadErrorSlm}</span
                                        >
                                    </div>
                                {/if}
                                <div class="flex items-start justify-between gap-[var(--space-3)] min-h-[36px]">
                                    <label
                                        class="text-[var(--text-base)] text-[var(--text-secondary)] shrink-0 min-w-[160px] pt-2"
                                        for="setting-gpu-layers">GPU Layers</label
                                    >
                                    <div class="flex flex-col gap-1 flex-1">
                                        <input
                                            id="setting-gpu-layers"
                                            class="flex-1 h-10 max-w-[280px] bg-[var(--surface-primary)] border border-[var(--shell-border)] rounded-[var(--radius-sm)] text-[var(--text-primary)] font-[var(--font-family)] text-[var(--text-sm)] px-[var(--space-2)] outline-none transition-[border-color] duration-[var(--transition-fast)] focus:border-[var(--accent)] placeholder:text-[var(--text-tertiary)]"
                                            type="number"
                                            min="-1"
                                            max="999"
                                            value={getSafe(config, "refinement.n_gpu_layers", -1)}
                                            oninput={(e) => {
                                                const v = parseInt((e.target as HTMLInputElement).value);
                                                if (!isNaN(v) && v >= -1) setSafe("refinement.n_gpu_layers", v);
                                            }}
                                        />
                                        <span class="text-[var(--text-xs)] text-[var(--text-tertiary)] italic"
                                            >Layers to offload to GPU. -1 = all (fastest), 0 = CPU only. Requires
                                            CUDA-compiled llama-cpp-python.</span
                                        >
                                    </div>
                                </div>
                                <div class="flex items-start justify-between gap-[var(--space-3)] min-h-[36px]">
                                    <label
                                        class="text-[var(--text-base)] text-[var(--text-secondary)] shrink-0 min-w-[160px] pt-2"
                                        for="setting-nctx">Context Size</label
                                    >
                                    <div class="flex flex-col gap-1 flex-1">
                                        <CustomSelect
                                            id="setting-nctx"
                                            options={[
                                                { value: "2048", label: "2048" },
                                                { value: "4096", label: "4096" },
                                                { value: "8192", label: "8192 (default)" },
                                                { value: "16384", label: "16384" },
                                            ]}
                                            value={String(getSafe(config, "refinement.n_ctx", 8192))}
                                            onchange={(v: string) => setSafe("refinement.n_ctx", parseInt(v))}
                                        />
                                        <span class="text-[var(--text-xs)] text-[var(--text-tertiary)] italic"
                                            >Context window for the refinement model. Larger values handle longer texts
                                            but use more VRAM.</span
                                        >
                                    </div>
                                </div>
                            {/if}
                        </div>
                    </div>

                    <!-- Maintenance -->
                    <div
                        class="bg-[var(--surface-secondary)] border border-[var(--shell-border)] rounded-[var(--radius-lg)] p-[var(--space-4)] xl:col-span-2"
                    >
                        <div
                            class="flex items-center gap-[var(--space-2)] text-[var(--text-base)] font-[var(--weight-emphasis)] text-[var(--text-primary)] mb-[var(--space-4)] pb-[var(--space-2)] border-b border-[var(--shell-border)]"
                        >
                            <RotateCcw size={18} class="text-[var(--accent)]" /><span>Maintenance</span>
                        </div>
                        <div class="grid grid-cols-2 gap-[var(--space-4)]">
                            <div class="flex flex-col gap-[var(--space-2)]">
                                <span
                                    class="text-[var(--text-sm)] text-[var(--text-secondary)] font-[var(--weight-emphasis)]"
                                    >History</span
                                >
                                <div class="flex gap-[var(--space-2)] flex-wrap">
                                    <StyledButton variant="secondary" onclick={handleExportHistory}
                                        >Export History</StyledButton
                                    >
                                    <StyledButton variant="destructive" onclick={handleClearHistory}
                                        >{clearingHistory ? "Clearing…" : "Clear All History"}</StyledButton
                                    >
                                </div>
                            </div>
                            <div class="flex flex-col gap-[var(--space-2)]">
                                <span
                                    class="text-[var(--text-sm)] text-[var(--text-secondary)] font-[var(--weight-emphasis)]"
                                    >Engine</span
                                >
                                <div class="flex gap-[var(--space-2)] flex-wrap">
                                    <StyledButton variant="secondary" onclick={handleRestartEngine}
                                        >Restart Engine</StyledButton
                                    >
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
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
                    <button
                        class="inline-flex items-center gap-1.5 h-9 px-[var(--space-3)] border-none rounded-[var(--radius-md)] font-[var(--font-family)] text-[var(--text-sm)] font-[var(--weight-emphasis)] cursor-pointer whitespace-nowrap transition-[background,color] duration-[var(--transition-fast)] bg-transparent text-[var(--text-secondary)] hover:enabled:text-[var(--text-primary)] hover:enabled:bg-[var(--hover-overlay)] disabled:opacity-50 disabled:cursor-not-allowed"
                        onclick={revertConfig}
                        disabled={saving}
                    >
                        <Undo2 size={14} /> Revert
                    </button>
                    <button
                        class="inline-flex items-center gap-1.5 h-9 px-[var(--space-3)] border-none rounded-[var(--radius-md)] font-[var(--font-family)] text-[var(--text-sm)] font-[var(--weight-emphasis)] cursor-pointer whitespace-nowrap transition-[background,color] duration-[var(--transition-fast)] bg-[var(--accent)] text-[var(--gray-0)] hover:enabled:bg-[var(--accent-hover)] disabled:opacity-50 disabled:cursor-not-allowed"
                        onclick={saveConfig}
                        disabled={saving}
                    >
                        {#if saving}<Loader2 size={14} class="spin" /> Saving…{:else}<Save size={14} /> Save Settings{/if}
                    </button>
                {/if}
            </div>
        </div>
    {/if}
</div>

<style>
    .gpu-status-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: var(--text-xs);
        font-weight: 500;
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
