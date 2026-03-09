<script lang="ts">
    /**
     * SettingsView — Card-based configuration surface.
     */

    import { getConfig, updateConfig, getModels, getHealth, downloadModel } from "../lib/api";
    import { ws } from "../lib/ws";
    import { onMount, onDestroy } from "svelte";
    import { Save, Undo2, Loader2, Mic, Eye, Check } from "lucide-svelte";
    import CustomSelect from "../lib/components/CustomSelect.svelte";
    import KeyBindCapture from "../lib/components/KeyBindCapture.svelte";
    import MaintenanceCard from "../lib/components/MaintenanceCard.svelte";
    import OutputCard from "../lib/components/OutputCard.svelte";
    import AsrModelCard from "../lib/components/AsrModelCard.svelte";
    import StyledButton from "../lib/components/StyledButton.svelte";
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
                class="w-full max-w-6xl min-w-[var(--content-min-width)] mx-auto py-[var(--space-5)] px-[var(--space-5)] pb-[var(--space-7)] flex flex-col gap-[var(--space-4)]"
            >
                <div class="grid grid-cols-1 xl:grid-cols-2 gap-[var(--space-4)] items-start">
                    <!-- ASR Model Settings -->
                    <AsrModelCard
                        {config}
                        {models}
                        {health}
                        {downloadingModel}
                        {downloadMessage}
                        {downloadErrorAsr}
                        {getSafe}
                        {setSafe}
                        {handleDownload}
                    />

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
                                class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]"
                            >
                                <label
                                    class="text-[var(--text-sm)] text-[var(--text-primary)]"
                                    for="setting-hotkey"
                                    title="Click Set Key to capture a new global hotkey. Works system-wide, even when the app is in the background."
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
                                    title="Toggle: press once to start, again to stop. Hold: hold key to record, release to stop."
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
                                    for="setting-typing-wpm"
                                    title="Your manual typing speed. Used to calculate Time Saved on the dashboard. Default: 40 WPM."
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
                                class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]"
                            >
                                <label
                                    class="text-[var(--text-sm)] text-[var(--text-primary)]"
                                    for="setting-uiscale"
                                    title="Scale the entire interface. Useful for high-DPI displays or accessibility."
                                    >UI Scale</label
                                >
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
                            </div>
                        </div>
                    </div>

                    <!-- Output & Processing -->
                    <OutputCard
                        {config}
                        {models}
                        {downloadingModel}
                        {downloadMessage}
                        {downloadErrorSlm}
                        {getSafe}
                        {setSafe}
                        {handleDownload}
                    />

                    <!-- Maintenance -->
                    <MaintenanceCard {config} {models} {health} {getSafe} {showMessage} />
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
