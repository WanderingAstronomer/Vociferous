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

    import { getConfig, updateConfig, getModels, getHealth, downloadModel, restartEngine } from "../lib/api";
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
        Trash2,
        RotateCcw,
        Activity,
        Check,
        Download,
        CheckCircle,
        AlertCircle,
        Monitor,
    } from "lucide-svelte";
    import ToggleSwitch from "../lib/components/ToggleSwitch.svelte";
    import StyledButton from "../lib/components/StyledButton.svelte";
    import CustomSelect from "../lib/components/CustomSelect.svelte";
    import KeyBindCapture from "../lib/components/KeyBindCapture.svelte";

    /* ===== State ===== */

    let config: Record<string, any> = $state({});
    let originalConfig = $state("");
    let models: { asr: Record<string, any>; slm: Record<string, any> } = $state({ asr: {}, slm: {} });
    let health: { status: string; version: string; transcripts: number; gpu?: { cuda_available?: boolean; detail?: string; whisper_backends?: string; slm_gpu_layers?: number } } = $state({
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
        unsubDownload = ws.on("download_progress", (data: any) => {
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
        unsubEngineStatus = ws.on("engine_status", (data: any) => {
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

<div class="settings-view">
    {#if loading}
        <div class="loading-state"><Loader2 size={24} class="spin" /><span>Loading settings…</span></div>
    {:else}
        <!-- Scrollable content -->
        <div class="settings-scroll">
            <div class="settings-center">
                <!-- System Health -->
                <div class="settings-card">
                    <div class="card-header"><Activity size={16} /><span>System</span></div>
                    <div class="health-strip">
                        <span class="health-dot" class:online={health.status === "ok"}></span>
                        <span class="health-label">
                            {health.status === "ok" ? "Online" : health.status}
                            {#if health.version}
                                · v{health.version}{/if}
                            · {health.transcripts} transcripts
                        </span>
                    </div>
                </div>

                <div class="settings-divider"></div>

                <!-- ASR Model Settings -->
                <div class="settings-card">
                    <div class="card-header"><Cpu size={16} /><span>Whisper ASR Settings</span></div>
                    <div class="form-grid">
                        <div class="form-row">
                            <label class="form-label" for="setting-model">Whisper Architecture</label>
                            <div class="form-row-help">
                                <div class="model-select-row">
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
                                                <span class="download-indicator downloading">
                                                    <Loader2 size={14} class="spin" />
                                                    <span class="download-msg">{downloadMessage}</span>
                                                </span>
                                            {:else}
                                                <button
                                                    class="download-btn-inline"
                                                    onclick={() => handleDownload("asr", getSafe(config, "model.model"))}
                                                >
                                                    <Download size={14} /> Download
                                                </button>
                                            {/if}
                                        {:else}
                                            <span class="download-indicator ready"><CheckCircle size={14} /></span>
                                        {/if}
                                    {/if}
                                </div>
                                <span class="form-help">Larger models are slower but more accurate. Tiny/Base are fast; Small/Medium offer better quality.</span>
                            </div>
                        </div>
                        {#if downloadErrorAsr && !downloadingModel}
                            <div class="download-error">
                                <AlertCircle size={14} />
                                <span class="download-error-text">{downloadErrorAsr}</span>
                            </div>
                        {/if}
                        <div class="form-row">
                            <label class="form-label">GPU Status</label>
                            <div class="form-row-help">
                                <div class="gpu-status-badge" class:gpu-available={health.gpu?.cuda_available} class:gpu-unavailable={!health.gpu?.cuda_available}>
                                    {#if health.gpu?.cuda_available}
                                        <CheckCircle size={14} />
                                        <span>{health.gpu.detail || 'CUDA available'}</span>
                                    {:else}
                                        <AlertCircle size={14} />
                                        <span>{health.gpu?.detail || 'No GPU detected'}</span>
                                    {/if}
                                </div>
                                <span class="form-help">
                                    ASR GPU requires pywhispercpp compiled with GGML_CUDA=1.
                                    {#if health.gpu?.whisper_backends}
                                        Whisper backends: {health.gpu.whisper_backends}
                                    {/if}
                                </span>
                            </div>
                        </div>
                        <div class="form-row">
                            <label class="form-label" for="setting-threads">ASR Threads</label>
                            <div class="form-row-help">
                                <input
                                    id="setting-threads"
                                    class="form-input small"
                                    type="number"
                                    min="1"
                                    max="32"
                                    value={getSafe(config, "model.n_threads", 4)}
                                    oninput={(e) => {
                                        const v = parseInt((e.target as HTMLInputElement).value);
                                        if (!isNaN(v) && v >= 1 && v <= 32) setSafe("model.n_threads", v);
                                    }}
                                />
                                <span class="form-help">CPU threads for whisper.cpp inference. Default 4. Higher values use more cores but may improve speed.</span>
                            </div>
                        </div>
                        <div class="form-row">
                            <label class="form-label" for="setting-language">Language</label>
                            <div class="form-row-help">
                                <input
                                    id="setting-language"
                                    class="form-input small"
                                    type="text"
                                    value={getSafe(config, "model.language", "en")}
                                    oninput={(e) => setSafe("model.language", (e.target as HTMLInputElement).value)}
                                    placeholder="en"
                                    maxlength="3"
                                />
                                <span class="form-help">ISO 639-1 code: "en" for English, "es" for Spanish, "fr" for French, etc.</span>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="settings-divider"></div>

                <!-- Recording Settings -->
                <div class="settings-card">
                    <div class="card-header"><Mic size={16} /><span>Recording</span></div>
                    <div class="form-grid">
                        <div class="form-row">
                            <label class="form-label" for="setting-hotkey">Activation Key</label>
                            <div class="form-row-help">
                                <KeyBindCapture
                                    id="setting-hotkey"
                                    value={getSafe(config, "recording.activation_key") ?? ""}
                                    onchange={(combo) => setSafe("recording.activation_key", combo)}
                                />
                                <span class="form-help">Click to set a global hotkey. Works system-wide, even when the app is in the background.</span>
                            </div>
                        </div>
                        <div class="form-row">
                            <label class="form-label" for="setting-recmode">Recording Mode</label>
                            <div class="form-row-help">
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
                                <span class="form-help"
                                    >Toggle: Press once to start, again to stop. Hold: Hold to record, release to stop.</span
                                >
                            </div>
                        </div>
                    </div>
                </div>

                <div class="settings-divider"></div>

                <!-- Visualization -->
                <div class="settings-card">
                    <div class="card-header"><Eye size={16} /><span>Visualization</span></div>
                    <div class="form-grid">
                        <div class="form-row">
                            <label class="form-label" for="setting-viztype">Spectrum Type</label>
                            <div class="form-row-help">
                                <CustomSelect
                                    id="setting-viztype"
                                    small
                                    options={[
                                        { value: "bar", label: "Bar Spectrum" },
                                        { value: "wave", label: "Waveform" },
                                        { value: "none", label: "None" },
                                    ]}
                                    value={getSafe(config, "visualizer.type", "bar")}
                                    onchange={(v: string) => setSafe("visualizer.type", v)}
                                />
                                <span class="form-help">Audio visualizer shown during recording. "None" disables it to save CPU.</span>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="settings-divider"></div>

                <!-- Display -->
                <div class="settings-card">
                    <div class="card-header"><Monitor size={16} /><span>Display</span></div>
                    <div class="form-grid">
                        <div class="form-row">
                            <label class="form-label" for="setting-uiscale">UI Scale</label>
                            <div class="form-row-help">
                                <CustomSelect
                                    id="setting-uiscale"
                                    small
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
                                <span class="form-help">Scale the entire interface. Useful for high-DPI displays or accessibility.</span>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="settings-divider"></div>

                <!-- Output & Processing -->
                <div class="settings-card">
                    <div class="card-header"><Sliders size={16} /><span>Output & Processing</span></div>
                    <div class="form-grid">
                        <div class="form-row">
                            <label class="form-label" for="setting-trailing">Add Trailing Space</label>
                            <div class="form-row-help">
                                <ToggleSwitch
                                    checked={getSafe(config, "output.add_trailing_space", false)}
                                    onChange={() =>
                                        setSafe(
                                            "output.add_trailing_space",
                                            !getSafe(config, "output.add_trailing_space", false),
                                        )}
                                />
                                <span class="form-help">Appends a space after each transcription for seamless dictation into text fields.</span>
                            </div>
                        </div>
                        <div class="form-row">
                            <label class="form-label" for="setting-refinement">Grammar Refinement</label>
                            <div class="form-row-help">
                                <ToggleSwitch
                                    checked={getSafe(config, "refinement.enabled", false)}
                                    onChange={() =>
                                        setSafe("refinement.enabled", !getSafe(config, "refinement.enabled", false))}
                                />
                                <span class="form-help">Uses a local language model to improve grammar and punctuation after transcription.</span>
                            </div>
                        </div>
                        {#if getSafe(config, "refinement.enabled", false)}
                            <div class="form-row">
                                <label class="form-label" for="setting-refmodel">Refinement Model</label>
                                <div class="form-row-help">
                                    <div class="model-select-row">
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
                                                    <span class="download-indicator downloading">
                                                        <Loader2 size={14} class="spin" />
                                                        <span class="download-msg">{downloadMessage}</span>
                                                    </span>
                                                {:else}
                                                    <button
                                                        class="download-btn-inline"
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
                                                <span class="download-indicator ready"><CheckCircle size={14} /></span>
                                            {/if}
                                        {/if}
                                    </div>
                                    <span class="form-help">Larger models produce better refinements but use more RAM and are slower.</span>
                                </div>
                            </div>
                            {#if downloadErrorSlm && !downloadingModel}
                                <div class="download-error">
                                    <AlertCircle size={14} />
                                    <span class="download-error-text">{downloadErrorSlm}</span>
                                </div>
                            {/if}
                            <div class="form-row">
                                <label class="form-label" for="setting-gpu-layers">GPU Layers</label>
                                <div class="form-row-help">
                                    <input
                                        id="setting-gpu-layers"
                                        class="form-input small"
                                        type="number"
                                        min="-1"
                                        max="999"
                                        value={getSafe(config, "refinement.n_gpu_layers", -1)}
                                        oninput={(e) => {
                                            const v = parseInt((e.target as HTMLInputElement).value);
                                            if (!isNaN(v) && v >= -1) setSafe("refinement.n_gpu_layers", v);
                                        }}
                                    />
                                    <span class="form-help">Layers to offload to GPU. -1 = all (fastest), 0 = CPU only. Requires CUDA-compiled llama-cpp-python.</span>
                                </div>
                            </div>
                            <div class="form-row">
                                <label class="form-label" for="setting-nctx">Context Size</label>
                                <div class="form-row-help">
                                    <CustomSelect
                                        id="setting-nctx"
                                        small
                                        options={[
                                            { value: "2048", label: "2048" },
                                            { value: "4096", label: "4096" },
                                            { value: "8192", label: "8192 (default)" },
                                            { value: "16384", label: "16384" },
                                        ]}
                                        value={String(getSafe(config, "refinement.n_ctx", 8192))}
                                        onchange={(v: string) => setSafe("refinement.n_ctx", parseInt(v))}
                                    />
                                    <span class="form-help">Context window for the refinement model. Larger values handle longer texts but use more VRAM.</span>
                                </div>
                            </div>
                        {/if}
                    </div>
                </div>

                <div class="settings-divider"></div>

                <!-- History Controls -->
                <div class="settings-card">
                    <div class="card-header"><Trash2 size={16} /><span>History Controls</span></div>
                    <div class="controls-row">
                        <StyledButton variant="secondary" onclick={() => {}}>Export History</StyledButton>
                        <StyledButton variant="destructive" onclick={() => {}}>Clear All History</StyledButton>
                    </div>
                </div>

                <div class="settings-divider"></div>

                <!-- Application Controls -->
                <div class="settings-card">
                    <div class="card-header"><RotateCcw size={16} /><span>Application Controls</span></div>
                    <div class="controls-row">
                        <StyledButton variant="secondary" onclick={handleRestartEngine}>Restart Engine</StyledButton>
                    </div>
                </div>
            </div>
        </div>

        <!-- Save bar -->
        <div class="save-bar" class:visible={isDirty || message}>
            <div class="save-bar-inner">
                {#if message}
                    <span class="save-message" class:error={messageType === "error"}>
                        {#if messageType === "success"}<Check size={14} />{/if}
                        {message}
                    </span>
                {/if}
                <div class="save-bar-spacer"></div>
                {#if isDirty}
                    <button class="action-btn ghost" onclick={revertConfig} disabled={saving}>
                        <Undo2 size={14} /> Revert
                    </button>
                    <button class="action-btn primary" onclick={saveConfig} disabled={saving}>
                        {#if saving}<Loader2 size={14} class="spin" /> Saving…{:else}<Save size={14} /> Save Settings{/if}
                    </button>
                {/if}
            </div>
        </div>
    {/if}
</div>

<style>
    .settings-view {
        display: flex;
        flex-direction: column;
        height: 100%;
        overflow: hidden;
    }

    .loading-state {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: var(--space-2);
        color: var(--text-tertiary);
        font-size: var(--text-sm);
    }

    .settings-scroll {
        flex: 1;
        overflow-y: auto;
        overflow-x: hidden;
    }

    .settings-center {
        max-width: 720px;
        min-width: 400px;
        margin: 0 auto;
        padding: var(--space-3) var(--space-3) var(--space-7);
        display: flex;
        flex-direction: column;
        gap: var(--space-5);
    }

    /* ===== Card ===== */
    .settings-card {
        background: var(--surface-secondary);
        border: 1px solid var(--shell-border);
        border-radius: var(--radius-lg);
        padding: var(--space-3);
    }
    .card-header {
        display: flex;
        align-items: center;
        gap: var(--space-1);
        font-size: var(--text-base);
        font-weight: var(--weight-emphasis);
        color: var(--text-primary);
        margin-bottom: var(--space-3);
        padding-bottom: var(--space-1);
        border-bottom: 1px solid var(--shell-border);
    }

    .settings-divider {
        height: 0;
    }

    /* ===== Health ===== */
    .health-strip {
        display: flex;
        align-items: center;
        gap: var(--space-1);
    }
    .health-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: var(--color-danger);
        transition: background var(--transition-fast);
    }
    .health-dot.online {
        background: var(--color-success);
    }
    .health-label {
        font-size: var(--text-sm);
        color: var(--text-secondary);
    }

    /* ===== Form ===== */
    .form-grid {
        display: flex;
        flex-direction: column;
        gap: var(--space-3);
    }
    .form-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: var(--space-3);
        min-height: 36px;
    }
    .form-label {
        font-size: var(--text-base);
        color: var(--text-secondary);
        flex-shrink: 0;
        min-width: 160px;
    }
    .form-row:has(.form-row-help) {
        align-items: flex-start;
    }
    .form-row:has(.form-row-help) .form-label {
        padding-top: 8px;
    }
    .form-row-help {
        display: flex;
        flex-direction: column;
        gap: 4px;
        flex: 1;
    }
    .form-help {
        font-size: var(--text-xs);
        color: var(--text-tertiary);
        font-style: italic;
    }

    .form-input {
        flex: 1;
        height: 40px;
        background: var(--surface-primary);
        border: 1px solid var(--shell-border);
        border-radius: var(--radius-sm);
        color: var(--text-primary);
        font-family: var(--font-family);
        font-size: var(--text-sm);
        padding: 0 var(--space-2);
        outline: none;
        transition: border-color var(--transition-fast);
    }
    .form-input:focus {
        border-color: var(--accent);
    }
    .form-input.small {
        max-width: 200px;
    }
    .form-input::placeholder {
        color: var(--text-tertiary);
    }

    /* ===== Controls row ===== */
    .controls-row {
        display: flex;
        gap: var(--space-2);
        flex-wrap: wrap;
    }

    /* ===== Save bar ===== */
    .save-bar {
        flex-shrink: 0;
        border-top: 1px solid var(--shell-border);
        background: var(--surface-primary);
        padding: var(--space-2) var(--space-4);
        opacity: 0;
        max-height: 0;
        overflow: hidden;
        transition:
            opacity var(--transition-normal),
            max-height var(--transition-normal);
    }
    .save-bar.visible {
        opacity: 1;
        max-height: 80px;
    }
    .save-bar-inner {
        display: flex;
        align-items: center;
        gap: var(--space-2);
        max-width: 720px;
        margin: 0 auto;
    }
    .save-bar-spacer {
        flex: 1;
    }
    .save-message {
        font-size: var(--text-xs);
        color: var(--color-success);
        display: flex;
        align-items: center;
        gap: 4px;
    }
    .save-message.error {
        color: var(--color-danger);
    }

    .action-btn {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        height: 36px;
        padding: 0 var(--space-3);
        border: none;
        border-radius: var(--radius-md);
        font-family: var(--font-family);
        font-size: var(--text-sm);
        font-weight: var(--weight-emphasis);
        cursor: pointer;
        transition:
            background var(--transition-fast),
            color var(--transition-fast);
        white-space: nowrap;
    }
    .action-btn:disabled {
        opacity: 0.5;
        cursor: not-allowed;
    }
    .action-btn.primary {
        background: var(--accent);
        color: var(--gray-0);
    }
    .action-btn.primary:hover:not(:disabled) {
        background: var(--accent-hover);
    }
    .action-btn.ghost {
        background: transparent;
        color: var(--text-secondary);
    }
    .action-btn.ghost:hover:not(:disabled) {
        color: var(--text-primary);
        background: var(--hover-overlay);
    }

    /* ===== Model download ===== */
    .model-select-row {
        display: flex;
        align-items: center;
        gap: var(--space-2);
        flex: 1;
    }
    .download-btn-inline {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 6px 12px;
        border: 1px solid var(--accent);
        border-radius: var(--radius-sm);
        background: transparent;
        color: var(--accent);
        font-family: var(--font-family);
        font-size: var(--text-xs);
        font-weight: var(--weight-emphasis);
        cursor: pointer;
        white-space: nowrap;
        transition:
            background var(--transition-fast),
            color var(--transition-fast);
    }
    .download-btn-inline:hover {
        background: var(--accent);
        color: var(--gray-0);
    }
    .download-indicator {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        font-size: var(--text-xs);
        white-space: nowrap;
        min-width: 0;
    }
    .download-indicator.ready {
        color: var(--color-success);
    }
    .download-indicator.downloading {
        color: var(--accent);
        min-width: 0;
        white-space: nowrap;
        overflow: hidden;
        flex-shrink: 1;
    }
    .download-msg {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .download-error {
        display: flex;
        align-items: flex-start;
        gap: 4px;
        font-size: var(--text-xs);
        color: var(--color-danger);
        padding: 4px 0;
    }
    .download-error-text {
        word-break: break-word;
        line-height: var(--leading-normal);
    }

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
