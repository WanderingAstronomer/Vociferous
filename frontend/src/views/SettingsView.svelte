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
        exportFile,
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
    let exportFormat = $state<"json" | "csv" | "txt">("json");
    let preferSaveDialog = $state(true);

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
            // Coerce stale/removed config values so the UI is never in an
            // invalid state after a setting option is removed.
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
    let showClearHistoryConfirm = $state(false);
    let showGpuDetails = $state(false);

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

    function buildExportPayload(transcripts: Record<string, unknown>[], format: "json" | "csv" | "txt") {
        const datePart = new Date().toISOString().slice(0, 10);
        if (format === "csv") {
            const content = transcriptsToCsv(transcripts);
            return { filename: `vociferous-export-${datePart}.csv`, content };
        }
        if (format === "txt") {
            const content = transcriptsToTxt(transcripts);
            return { filename: `vociferous-export-${datePart}.txt`, content };
        }
        const content = JSON.stringify(transcripts, null, 2);
        return { filename: `vociferous-export-${datePart}.json`, content };
    }

    async function handleExportHistory() {
        try {
            const transcripts = await getTranscripts(99999);
            const { filename, content } = buildExportPayload(
                transcripts as unknown as Record<string, unknown>[],
                exportFormat,
            );

            if (preferSaveDialog) {
                // Backend opens the native GNOME/GTK save dialog and writes the file.
                const result = await exportFile(content, filename);
                message = `Exported ${transcripts.length} transcript${transcripts.length !== 1 ? "s" : ""} to ${result.path}`;
                messageType = "success";
                return;
            }

            // Fallback: browser download (shouldn't be needed in pywebview, but keeps the toggle useful)
            const blob = new Blob([content], { type: "application/octet-stream" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = filename;
            a.click();
            URL.revokeObjectURL(url);
            message = `Exported ${transcripts.length} transcript${transcripts.length !== 1 ? "s" : ""} to default download location`;
            messageType = "success";
        } catch (e: any) {
            if ((e as any)?.error === "cancelled" || e?.message?.includes("cancelled")) {
                message = "Export cancelled";
                messageType = "error";
                return;
            }
            message = (e as any).message || "Export failed";
            messageType = "error";
        }
    }

    async function handleClearHistory() {
        showClearHistoryConfirm = true;
    }

    async function confirmClearHistory() {
        showClearHistoryConfirm = false;
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
                            <div
                                class="grid grid-cols-[200px_minmax(0,1fr)] items-start gap-x-[var(--space-4)] min-h-[36px]"
                            >
                                <label
                                    class="text-[var(--text-base)] text-[var(--text-secondary)] pt-2"
                                    for="setting-model">Whisper Architecture</label
                                >
                                <div class="flex flex-col gap-1 flex-1">
                                    <div class="flex items-center gap-[var(--space-2)]">
                                        <div class="w-full max-w-[460px]">
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
                                        </div>
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
                            <div
                                class="grid grid-cols-[200px_minmax(0,1fr)] items-start gap-x-[var(--space-4)] min-h-[36px]"
                            >
                                <div class="text-[var(--text-base)] text-[var(--text-secondary)] pt-2">GPU Status</div>
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
                                        ASR GPU acceleration requires pywhispercpp compiled with GGML_CUDA=1.
                                    </span>
                                    {#if health.gpu?.whisper_backends && health.gpu.whisper_backends !== "unavailable"}
                                        <button
                                            class="w-fit mt-1 text-[var(--text-xs)] text-[var(--text-tertiary)] bg-transparent border-none p-0 cursor-pointer transition-[color] duration-[var(--transition-fast)] hover:text-[var(--accent)]"
                                            onclick={() => (showGpuDetails = !showGpuDetails)}
                                        >
                                            {showGpuDetails ? "Hide backend details" : "Show backend details"}
                                        </button>
                                        {#if showGpuDetails}
                                            {@const features = health.gpu.whisper_backends
                                                .split("|")
                                                .map((s: string) => s.trim().split(" = "))
                                                .filter((p: string[]) => p.length === 2 && p[1] === "1")
                                                .map((p: string[]) => p[0])}
                                            {#if features.length}
                                                <span class="text-[var(--text-xs)] text-[var(--text-tertiary)] italic"
                                                    >Active backends: {features.join(", ")}</span
                                                >
                                            {/if}
                                        {/if}
                                    {/if}
                                </div>
                            </div>
                            <div
                                class="grid grid-cols-[200px_minmax(0,1fr)] items-start gap-x-[var(--space-4)] min-h-[36px]"
                            >
                                <label
                                    class="text-[var(--text-base)] text-[var(--text-secondary)] pt-2"
                                    for="setting-device">ASR Device</label
                                >
                                <div class="flex flex-col gap-1 flex-1">
                                    <div class="w-full max-w-[460px]">
                                        <CustomSelect
                                            id="setting-device"
                                            options={[
                                                { value: "auto", label: "Automatic" },
                                                { value: "gpu", label: "Prefer GPU" },
                                                { value: "cpu", label: "Force CPU" },
                                            ]}
                                            value={String(getSafe(config, "model.device", "auto"))}
                                            onchange={(v: string) => setSafe("model.device", v)}
                                        />
                                    </div>
                                    <span class="text-[var(--text-xs)] text-[var(--text-tertiary)] italic"
                                        >Preference for ASR backend selection. Requires engine restart after saving; if
                                        unsupported by your whisper build, automatic fallback is used.</span
                                    >
                                </div>
                            </div>
                            <div
                                class="grid grid-cols-[200px_minmax(0,1fr)] items-start gap-x-[var(--space-4)] min-h-[36px]"
                            >
                                <label
                                    class="text-[var(--text-base)] text-[var(--text-secondary)] pt-2"
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
                                        >CPU threads for whisper.cpp inference. Used when running on CPU paths. Default
                                        4. Higher values use more cores but may improve speed.</span
                                    >
                                </div>
                            </div>
                            <div
                                class="grid grid-cols-[200px_minmax(0,1fr)] items-start gap-x-[var(--space-4)] min-h-[36px]"
                            >
                                <label
                                    class="text-[var(--text-base)] text-[var(--text-secondary)] pt-2"
                                    for="setting-language">Language</label
                                >
                                <div class="flex flex-col gap-1 flex-1">
                                    <div class="w-full max-w-[460px]">
                                        <CustomSelect
                                            id="setting-language"
                                            options={[
                                                { value: "", label: "Auto-detect" },
                                                { value: "af", label: "Afrikaans" },
                                                { value: "ar", label: "Arabic" },
                                                { value: "hy", label: "Armenian" },
                                                { value: "az", label: "Azerbaijani" },
                                                { value: "be", label: "Belarusian" },
                                                { value: "bs", label: "Bosnian" },
                                                { value: "bg", label: "Bulgarian" },
                                                { value: "ca", label: "Catalan" },
                                                { value: "zh", label: "Chinese" },
                                                { value: "hr", label: "Croatian" },
                                                { value: "cs", label: "Czech" },
                                                { value: "da", label: "Danish" },
                                                { value: "nl", label: "Dutch" },
                                                { value: "en", label: "English" },
                                                { value: "et", label: "Estonian" },
                                                { value: "fi", label: "Finnish" },
                                                { value: "fr", label: "French" },
                                                { value: "gl", label: "Galician" },
                                                { value: "de", label: "German" },
                                                { value: "el", label: "Greek" },
                                                { value: "he", label: "Hebrew" },
                                                { value: "hi", label: "Hindi" },
                                                { value: "hu", label: "Hungarian" },
                                                { value: "id", label: "Indonesian" },
                                                { value: "it", label: "Italian" },
                                                { value: "ja", label: "Japanese" },
                                                { value: "kn", label: "Kannada" },
                                                { value: "kk", label: "Kazakh" },
                                                { value: "ko", label: "Korean" },
                                                { value: "lv", label: "Latvian" },
                                                { value: "lt", label: "Lithuanian" },
                                                { value: "mk", label: "Macedonian" },
                                                { value: "ms", label: "Malay" },
                                                { value: "mr", label: "Marathi" },
                                                { value: "mi", label: "Māori" },
                                                { value: "ne", label: "Nepali" },
                                                { value: "no", label: "Norwegian" },
                                                { value: "fa", label: "Persian" },
                                                { value: "pl", label: "Polish" },
                                                { value: "pt", label: "Portuguese" },
                                                { value: "ro", label: "Romanian" },
                                                { value: "ru", label: "Russian" },
                                                { value: "sr", label: "Serbian" },
                                                { value: "sk", label: "Slovak" },
                                                { value: "sl", label: "Slovenian" },
                                                { value: "es", label: "Spanish" },
                                                { value: "sw", label: "Swahili" },
                                                { value: "sv", label: "Swedish" },
                                                { value: "tl", label: "Tagalog" },
                                                { value: "ta", label: "Tamil" },
                                                { value: "th", label: "Thai" },
                                                { value: "tr", label: "Turkish" },
                                                { value: "uk", label: "Ukrainian" },
                                                { value: "ur", label: "Urdu" },
                                                { value: "vi", label: "Vietnamese" },
                                                { value: "cy", label: "Welsh" },
                                            ]}
                                            value={getSafe(config, "model.language", "en")}
                                            onchange={(v: string) => setSafe("model.language", v)}
                                        />
                                    </div>
                                    <span class="text-[var(--text-xs)] text-[var(--text-tertiary)] italic"
                                        >Transcription language. Auto-detect works but is slower and slightly less
                                        accurate than specifying explicitly.</span
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
                            <div
                                class="grid grid-cols-[200px_minmax(0,1fr)] items-start gap-x-[var(--space-4)] min-h-[36px]"
                            >
                                <label
                                    class="text-[var(--text-base)] text-[var(--text-secondary)] pt-2"
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
                            <div
                                class="grid grid-cols-[200px_minmax(0,1fr)] items-start gap-x-[var(--space-4)] min-h-[36px]"
                            >
                                <label
                                    class="text-[var(--text-base)] text-[var(--text-secondary)] pt-2"
                                    for="setting-recmode">Recording Mode</label
                                >
                                <div class="flex flex-col gap-1 flex-1">
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
                                    <span class="text-[var(--text-xs)] text-[var(--text-tertiary)] italic"
                                        >Toggle: Press once to start, again to stop. Hold: Hold key to record, release
                                        to stop.</span
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
                            <div
                                class="grid grid-cols-[200px_minmax(0,1fr)] items-start gap-x-[var(--space-4)] min-h-[36px]"
                            >
                                <label
                                    class="text-[var(--text-base)] text-[var(--text-secondary)] pt-2"
                                    for="setting-viztype">Spectrum Type</label
                                >
                                <div class="flex flex-col gap-1 flex-1">
                                    <div class="w-full max-w-[460px]">
                                        <CustomSelect
                                            id="setting-viztype"
                                            options={[
                                                { value: "bar", label: "Bar Spectrum" },
                                                { value: "none", label: "None" },
                                            ]}
                                            value={getSafe(config, "visualizer.type", "bar")}
                                            onchange={(v: string) => setSafe("visualizer.type", v)}
                                        />
                                    </div>
                                    <span class="text-[var(--text-xs)] text-[var(--text-tertiary)] italic"
                                        >Audio visualizer shown during recording. "None" disables it to save CPU.</span
                                    >
                                </div>
                            </div>
                            <div
                                class="grid grid-cols-[200px_minmax(0,1fr)] items-start gap-x-[var(--space-4)] min-h-[36px]"
                            >
                                <label
                                    class="text-[var(--text-base)] text-[var(--text-secondary)] pt-2"
                                    for="setting-uiscale">UI Scale</label
                                >
                                <div class="flex flex-col gap-1 flex-1">
                                    <div class="w-full max-w-[460px]">
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
                                    </div>
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
                            <div
                                class="grid grid-cols-[200px_minmax(0,1fr)] items-start gap-x-[var(--space-4)] min-h-[36px]"
                            >
                                <label
                                    class="text-[var(--text-base)] text-[var(--text-secondary)] pt-2"
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
                            <div
                                class="grid grid-cols-[200px_minmax(0,1fr)] items-start gap-x-[var(--space-4)] min-h-[36px]"
                            >
                                <label
                                    class="text-[var(--text-base)] text-[var(--text-secondary)] pt-2"
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
                            <div
                                class="grid grid-cols-[200px_minmax(0,1fr)] items-start gap-x-[var(--space-4)] min-h-[36px]"
                            >
                                <label
                                    class="text-[var(--text-base)] text-[var(--text-secondary)] pt-2"
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
                                <div
                                    class="grid grid-cols-[200px_minmax(0,1fr)] items-start gap-x-[var(--space-4)] min-h-[36px]"
                                >
                                    <label
                                        class="text-[var(--text-base)] text-[var(--text-secondary)] pt-2"
                                        for="setting-refmodel">Refinement Model</label
                                    >
                                    <div class="flex flex-col gap-1 flex-1">
                                        <div class="flex items-center gap-[var(--space-2)]">
                                            <div class="w-full max-w-[460px]">
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
                                            </div>
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
                                <div
                                    class="grid grid-cols-[200px_minmax(0,1fr)] items-start gap-x-[var(--space-4)] min-h-[36px]"
                                >
                                    <label
                                        class="text-[var(--text-base)] text-[var(--text-secondary)] pt-2"
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
                                <div
                                    class="grid grid-cols-[200px_minmax(0,1fr)] items-start gap-x-[var(--space-4)] min-h-[36px]"
                                >
                                    <label
                                        class="text-[var(--text-base)] text-[var(--text-secondary)] pt-2"
                                        for="setting-nctx">Context Size</label
                                    >
                                    <div class="flex flex-col gap-1 flex-1">
                                        <div class="w-full max-w-[460px]">
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
                                        </div>
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
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-[var(--space-3)]">
                            <div
                                class="flex flex-col gap-[var(--space-2)] border border-[var(--shell-border)] rounded-[var(--radius-md)] p-[var(--space-3)]"
                            >
                                <span
                                    class="text-[var(--text-sm)] text-[var(--text-secondary)] font-[var(--weight-emphasis)]"
                                    >History</span
                                >
                                <div class="flex flex-col gap-[var(--space-2)] mb-[var(--space-1)]">
                                    <div class="flex items-center justify-between gap-[var(--space-3)]">
                                        <span class="text-[var(--text-xs)] text-[var(--text-tertiary)] uppercase"
                                            >Format</span
                                        >
                                        <div class="w-full max-w-[180px]">
                                            <CustomSelect
                                                id="history-export-format"
                                                options={[
                                                    { value: "json", label: "JSON" },
                                                    { value: "csv", label: "CSV" },
                                                    { value: "txt", label: "Plain Text" },
                                                ]}
                                                value={exportFormat}
                                                onchange={(v: string) => {
                                                    if (v === "json" || v === "csv" || v === "txt") {
                                                        exportFormat = v;
                                                    }
                                                }}
                                            />
                                        </div>
                                    </div>
                                    <div class="flex items-center justify-between gap-[var(--space-3)]">
                                        <span class="text-[var(--text-xs)] text-[var(--text-tertiary)] uppercase"
                                            >Choose Location</span
                                        >
                                        <ToggleSwitch
                                            checked={preferSaveDialog}
                                            onChange={() => (preferSaveDialog = !preferSaveDialog)}
                                        />
                                    </div>
                                    <span class="text-[var(--text-xs)] text-[var(--text-tertiary)] italic"
                                        >Uses native save dialog when supported; otherwise downloads to your default
                                        location.</span
                                    >
                                </div>
                                <div class="flex gap-[var(--space-2)] flex-wrap">
                                    <StyledButton variant="secondary" onclick={handleExportHistory}
                                        >Export History</StyledButton
                                    >
                                    <StyledButton
                                        variant="destructive"
                                        onclick={handleClearHistory}
                                        disabled={clearingHistory}
                                    >
                                        {clearingHistory ? "Clearing…" : "Clear All History"}</StyledButton
                                    >
                                </div>
                            </div>
                            <div
                                class="flex flex-col gap-[var(--space-2)] border border-[var(--shell-border)] rounded-[var(--radius-md)] p-[var(--space-3)]"
                            >
                                <span
                                    class="text-[var(--text-sm)] text-[var(--text-secondary)] font-[var(--weight-emphasis)]"
                                    >Engine</span
                                >
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

        {#if showClearHistoryConfirm}
            <div
                class="fixed inset-0 z-[120] bg-black/50 flex items-center justify-center p-[var(--space-4)]"
                role="presentation"
                onclick={(e) => {
                    if (e.target === e.currentTarget) showClearHistoryConfirm = false;
                }}
            >
                <div
                    class="w-full max-w-[520px] bg-[var(--surface-secondary)] border border-[var(--shell-border)] rounded-[var(--radius-lg)] p-[var(--space-4)] flex flex-col gap-[var(--space-3)]"
                    role="dialog"
                    aria-modal="true"
                    aria-labelledby="clear-history-title"
                    aria-describedby="clear-history-description"
                >
                    <h3
                        id="clear-history-title"
                        class="m-0 text-[var(--text-base)] font-[var(--weight-emphasis)] text-[var(--text-primary)]"
                    >
                        Clear all history?
                    </h3>
                    <p id="clear-history-description" class="m-0 text-[var(--text-sm)] text-[var(--text-secondary)]">
                        This permanently deletes all transcripts and their variants. This action cannot be undone.
                    </p>
                    <div class="flex justify-end gap-[var(--space-2)] pt-[var(--space-1)]">
                        <StyledButton
                            variant="secondary"
                            onclick={() => (showClearHistoryConfirm = false)}
                            disabled={clearingHistory}>Cancel</StyledButton
                        >
                        <StyledButton variant="destructive" onclick={confirmClearHistory} disabled={clearingHistory}
                            >{clearingHistory ? "Clearing…" : "Delete Everything"}</StyledButton
                        >
                    </div>
                </div>
            </div>
        {/if}

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
