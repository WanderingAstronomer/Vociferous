<script lang="ts">
    /**
     * SettingsView — sidebar navigation + section content.
     *
     * Sidebar lists category sections. Banners (GPU runtime warning,
     * restart-required) sit above the active section so they apply
     * regardless of which section is showing. The save bar pins to the
     * bottom and is dedicated to Settings transactions only — non-settings
     * actions (export, cleanup, restart) emit toasts instead.
     */

    import { getConfig, updateConfig, getModels, getHealth, getEngineStatus, downloadModel, restartEngine } from "../lib/api";
    import type { EngineStatusInfo, HealthInfo, ModelInfo } from "../lib/api";
    import { appConfig } from "../lib/config.svelte";
    import type { ConfigPath, ConfigValue, VociferousConfig } from "../lib/config.svelte";
    import { confirmDialog } from "../lib/confirm.svelte";
    import { nav, type NavigationRequest } from "../lib/navigation.svelte";
    import { toast } from "../lib/toast.svelte";
    import { ws } from "../lib/ws";
    import { onMount, onDestroy } from "svelte";
    import {
        Save,
        Undo2,
        Loader2,
        Cpu,
        Mic,
        Sliders,
        UserCog,
        Activity,
        Check,
        Sparkles,
        TriangleAlert,
        ShieldCheck,
    } from "lucide-svelte";
    import CustomSelect from "../lib/components/CustomSelect.svelte";
    import KeyBindCapture from "../lib/components/KeyBindCapture.svelte";
    import DiagnosticsCard from "../lib/components/DiagnosticsCard.svelte";
    import SafetyDataCard from "../lib/components/SafetyDataCard.svelte";
    import OutputCard from "../lib/components/OutputCard.svelte";
    import AsrModelCard from "../lib/components/AsrModelCard.svelte";
    import RefinementCard from "../lib/components/RefinementCard.svelte";
    import StyledButton from "../lib/components/StyledButton.svelte";
    import EmptyState from "../lib/components/EmptyState.svelte";
    import ToggleSwitch from "../lib/components/ToggleSwitch.svelte";
    import type { DownloadProgressData, EngineStatusData } from "../lib/events";

    /* ===== Sections ===== */

    type SettingsSection =
        | "profile"
        | "recording"
        | "asr"
        | "refinement"
        | "output"
        | "safety"
        | "diagnostics";

    const sections: { id: SettingsSection; label: string; icon: typeof Cpu }[] = [
        { id: "profile", label: "Profile & Interface", icon: UserCog },
        { id: "recording", label: "Recording", icon: Mic },
        { id: "asr", label: "Speech Recognition", icon: Cpu },
        { id: "refinement", label: "Refinement", icon: Sparkles },
        { id: "output", label: "Output", icon: Sliders },
        { id: "safety", label: "Safety & Data", icon: ShieldCheck },
        { id: "diagnostics", label: "Diagnostics", icon: Activity },
    ];

    let activeSection = $state<SettingsSection>("asr");
    let activeLabel = $derived(sections.find((s) => s.id === activeSection)?.label ?? "");

    /* ===== State ===== */

    let config = $state<VociferousConfig>({});
    let originalConfig = $state("");
    let models: { asr: Record<string, ModelInfo>; slm: Record<string, ModelInfo> } = $state({ asr: {}, slm: {} });
    let health: HealthInfo = $state({
        status: "unknown",
        version: "",
        transcripts: 0,
    });
    let engineStatus: EngineStatusInfo | null = $state(null);
    let loading = $state(true);
    let saving = $state(false);
    let restartPending = $state(false);
    let confirmingNavigation = $state(false);
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

    let restartReasons = $derived(detectRestartRequired(JSON.parse(originalConfig || "{}"), engineStatus));
    let restartRequired = $derived(restartReasons.length > 0);

    /* ===== Lifecycle ===== */

    let unsubDownload: (() => void) | null = null;
    let unsubEngineStatus: (() => void) | null = null;
    let unregisterNavigationBlocker: (() => void) | null = null;

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
                getEngineStatus()
                    .then((s) => (engineStatus = s))
                    .catch(() => {});
                toast.success(`${data.model_id} downloaded`);
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
            void handleEngineStatusEvent(data);
        });

        try {
            const [c, m, h, s] = await Promise.all([getConfig(), getModels(), getHealth(), getEngineStatus()]);
            appConfig.apply(c);
            config = cloneConfig(c);
            const validRecordingModes = ["press_to_toggle", "hold_to_record"];
            if (!validRecordingModes.includes(getSafe(config, "recording.recording_mode", ""))) {
                setSafe("recording.recording_mode", "press_to_toggle");
            }
            originalConfig = JSON.stringify(config);
            models = m;
            health = h;
            engineStatus = s;
        } catch (e: unknown) {
            toast.error(`Failed to load settings: ${errorMessage(e)}`);
            originalConfig = JSON.stringify(config);
        } finally {
            loading = false;
        }

        unregisterNavigationBlocker = nav.registerBlocker(confirmSettingsNavigation);
    });

    onDestroy(() => {
        unsubDownload?.();
        unsubEngineStatus?.();
        unregisterNavigationBlocker?.();
    });

    // Re-fetch health when switching to the Diagnostics section so mic/GPU status stays current
    $effect(() => {
        if (activeSection === "diagnostics") {
            void refreshRuntimeState();
        }
    });

    /* ===== Actions ===== */

    async function refreshRuntimeState(): Promise<void> {
        try {
            const [h, s] = await Promise.all([getHealth(), getEngineStatus()]);
            health = h;
            engineStatus = s;
        } catch {
            // best-effort
        }
    }

    async function handleEngineStatusEvent(data: EngineStatusData): Promise<void> {
        if (!data?.asr && !data?.slm) return;
        try {
            const [h, s] = await Promise.all([getHealth(), getEngineStatus()]);
            health = h;
            engineStatus = s;
            if (!restartPending) return;

            const reasons = detectRestartRequired(JSON.parse(originalConfig || "{}"), s);
            if (reasons.length === 0) {
                toast.success("Engine restarted");
                restartPending = false;
                return;
            }

            const failed = data.asr === "unavailable" || data.slm === "Error";
            if (failed) {
                toast.error(`Engine restart still needs attention: ${reasons.join(", ")}`);
                restartPending = false;
            }
        } catch (e: unknown) {
            if (restartPending) {
                toast.error(errorMessage(e) || "Engine status refresh failed");
                restartPending = false;
            }
        }
    }

    async function saveConfig(): Promise<boolean> {
        saving = true;
        try {
            const updated = await updateConfig(config);
            appConfig.apply(updated);
            config = cloneConfig(updated);
            originalConfig = JSON.stringify(config);
            showMessage("Settings saved", "success");
            return true;
        } catch (e: unknown) {
            showMessage(`Error: ${errorMessage(e)}`, "error");
            return false;
        } finally {
            saving = false;
        }
    }

    async function handleRestartEngine() {
        restartPending = true;
        try {
            await restartEngine();
            // success/failure is delivered via the engine_status WS handler
        } catch (e: unknown) {
            toast.error(errorMessage(e) || "Engine restart failed");
            restartPending = false;
        }
    }

    async function confirmSettingsNavigation(request: NavigationRequest): Promise<boolean> {
        if (request.from !== "settings" || request.to === "settings" || !isDirty) {
            return true;
        }
        if (confirmingNavigation) {
            return false;
        }

        confirmingNavigation = true;
        try {
            const shouldLeave = await confirmDialog.confirm({
                title: "Apply settings changes?",
                message: "You have unapplied settings changes. Apply them before leaving, discard them, or stay in Settings.",
                confirmLabel: "Apply and Leave",
                alternativeLabel: "Discard and Leave",
                cancelLabel: "Stay",
            });

            if (!shouldLeave) {
                return false;
            }

            if (confirmDialog.lastConfirmWasAlternative) {
                discardConfig(false);
                return true;
            }

            return saveConfig();
        } finally {
            confirmingNavigation = false;
        }
    }

    function discardConfig(showNotice = true) {
        config = JSON.parse(originalConfig) as VociferousConfig;
        if (showNotice) showMessage("Changes reverted", "success");
    }

    function showMessage(msg: string, type: "success" | "error") {
        message = msg;
        messageType = type;
        if (type === "success") setTimeout(() => (message = ""), 3000);
    }

    /* ===== Restart-required detector ===== */

    function detectRestartRequired(saved: VociferousConfig, engine: EngineStatusInfo | null): string[] {
        if (!engine) return [];
        const reasons: string[] = [];

        const runtimeAsr = engine.asr.runtime as Record<string, unknown> | undefined;
        const cfgAsrProvider = saved.model?.provider ?? "local_faster_whisper";
        const loadedAsrProvider = (runtimeAsr?.provider ?? "local_faster_whisper") as string;
        if (cfgAsrProvider !== loadedAsrProvider) reasons.push("ASR provider");

        if (cfgAsrProvider === "local_faster_whisper") {
            const cfgAsrModel = saved.model?.model ?? "";
            const loadedAsrModel = engine.asr.model_id ?? "";
            if (cfgAsrModel && loadedAsrModel && cfgAsrModel !== loadedAsrModel) {
                reasons.push("ASR model");
            }

            const cfgAsrDevice = (saved.model?.device ?? "auto").toLowerCase();
            const loadedAsrDevice = (engine.asr.device ?? "").toLowerCase();
            if (loadedAsrDevice && engine.asr.ready) {
                const loadedIsCpu = loadedAsrDevice.includes("cpu");
                if (cfgAsrDevice === "cpu" && !loadedIsCpu) reasons.push("ASR device");
                else if (cfgAsrDevice === "gpu" && loadedIsCpu) reasons.push("ASR device");
            }

            const cfgAsrThreads = saved.model?.n_threads;
            const runtimeThreadsRaw = engine.asr.runtime?.n_threads;
            const loadedAsrThreads = typeof runtimeThreadsRaw === "number" ? runtimeThreadsRaw : undefined;
            if (cfgAsrThreads !== undefined && loadedAsrThreads !== undefined && cfgAsrThreads !== loadedAsrThreads) {
                reasons.push("ASR threads");
            }
        } else if (cfgAsrProvider === "groq") {
            if ((saved.model?.groq?.model_id ?? "") !== (runtimeAsr?.model_id as string | undefined)) {
                reasons.push("Groq ASR model");
            }
            if ((saved.model?.groq?.base_url ?? "") !== (runtimeAsr?.base_url as string | undefined)) {
                reasons.push("Groq ASR base URL");
            }
        }

        const cfgSlmEnabled = saved.refinement?.enabled ?? false;
        const loadedSlmState = engine.slm.state;
        const loadedSlmActive = loadedSlmState !== "disabled" && loadedSlmState !== "unavailable";
        if (cfgSlmEnabled !== loadedSlmActive) {
            reasons.push(cfgSlmEnabled ? "Refinement enabled" : "Refinement disabled");
        }

        if (cfgSlmEnabled && loadedSlmActive) {
            const runtime = engine.slm.runtime as Record<string, unknown> | undefined;
            const cfgSlmProvider = saved.refinement?.provider ?? "local_ct2";
            const loadedProvider = (runtime?.provider ?? "local_ct2") as string;
            if (cfgSlmProvider !== loadedProvider) reasons.push("Refinement provider");

            if (cfgSlmProvider === "local_ct2") {
                const cfgSlmModel = saved.refinement?.model_id ?? "";
                const loadedSlmModel = engine.slm.model_id ?? "";
                if (cfgSlmModel && loadedSlmModel && cfgSlmModel !== loadedSlmModel) {
                    reasons.push("Refinement model");
                }
                const cfgSlmCpu = (saved.refinement?.n_gpu_layers ?? -1) === 0;
                const loadedSlmDevice = (engine.slm.device ?? "").toLowerCase();
                if (loadedSlmDevice && engine.slm.ready) {
                    const loadedSlmCpu = loadedSlmDevice.includes("cpu");
                    if (cfgSlmCpu && !loadedSlmCpu) reasons.push("Refinement device");
                    else if (!cfgSlmCpu && loadedSlmCpu && health.gpu?.cuda_available) reasons.push("Refinement device");
                }
            } else if (cfgSlmProvider === "lm_studio") {
                if ((saved.refinement?.lm_studio?.model_id ?? "") !== (runtime?.model_id as string | undefined)) {
                    reasons.push("LM Studio model");
                }
                if ((saved.refinement?.lm_studio?.base_url ?? "") !== (runtime?.base_url as string | undefined)) {
                    reasons.push("LM Studio base URL");
                }
            } else if (cfgSlmProvider === "groq") {
                if ((saved.refinement?.groq?.model_id ?? "") !== (runtime?.model_id as string | undefined)) {
                    reasons.push("Groq model");
                }
                if ((saved.refinement?.groq?.base_url ?? "") !== (runtime?.base_url as string | undefined)) {
                    reasons.push("Groq base URL");
                }
            }
        }

        return [...new Set(reasons)];
    }

    /* ===== Helpers ===== */

    type ConfigRecord = Record<string, unknown>;

    function getSafe<Path extends ConfigPath>(obj: VociferousConfig, path: Path): ConfigValue<Path> | undefined;
    function getSafe<Path extends ConfigPath>(obj: VociferousConfig, path: Path, fallback: ConfigValue<Path>): ConfigValue<Path>;
    function getSafe<Path extends ConfigPath>(
        obj: VociferousConfig,
        path: Path,
        fallback?: ConfigValue<Path>,
    ): ConfigValue<Path> | undefined {
        const value = path
            .split(".")
            .reduce<unknown>((current, key) => (isRecord(current) ? current[key] : undefined), obj);
        return (value ?? fallback) as ConfigValue<Path> | undefined;
    }

    function setSafe<Path extends ConfigPath>(path: Path, value: ConfigValue<Path>) {
        config = withConfigValue(config, path, value);
    }

    function cloneConfig(source: Record<string, unknown> | VociferousConfig): VociferousConfig {
        return JSON.parse(JSON.stringify(source)) as VociferousConfig;
    }

    function withConfigValue<Path extends ConfigPath>(
        source: VociferousConfig,
        path: Path,
        value: ConfigValue<Path>,
    ): VociferousConfig {
        const keys = path.split(".");
        const next = cloneConfig(source);
        let obj: ConfigRecord = next;
        for (let i = 0; i < keys.length - 1; i++) {
            const key = keys[i];
            if (!isRecord(obj[key])) obj[key] = {};
            obj = obj[key] as ConfigRecord;
        }
        obj[keys[keys.length - 1]] = value;
        return next;
    }

    function isRecord(value: unknown): value is ConfigRecord {
        return typeof value === "object" && value !== null && !Array.isArray(value);
    }

    function errorMessage(error: unknown): string {
        return error instanceof Error ? error.message : String(error);
    }

    /* ===== Tip bar ===== */

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
        } catch (e: unknown) {
            const msg = errorMessage(e);
            if (type === "asr") downloadErrorAsr = msg;
            else downloadErrorSlm = msg;
            downloadingModel = null;
            downloadMessage = "";
        }
    }
</script>

<div class="flex h-full">
    {#if loading}
        <EmptyState icon={Loader2} message="Loading settings…" spinning />
    {:else}
        <!-- ===== Sidebar ===== -->
        <aside
            class="w-[220px] shrink-0 border-r border-[var(--shell-border)] bg-[var(--surface-tertiary)] overflow-y-auto py-[var(--space-4)] px-[var(--space-2)]"
        >
            <nav class="flex flex-col gap-[2px]" aria-label="Settings sections">
                {#each sections as section (section.id)}
                    <button
                        type="button"
                        class="flex items-center gap-[var(--space-2)] px-[var(--space-3)] py-[var(--space-2)] rounded-[var(--radius-md)] text-[var(--text-sm)] text-left border-none cursor-pointer transition-colors duration-[var(--transition-fast)]
                            {activeSection === section.id
                            ? 'bg-[var(--hover-overlay-blue)] text-[var(--accent)] font-[var(--weight-emphasis)]'
                            : 'bg-transparent text-[var(--text-secondary)] hover:bg-[var(--hover-overlay-blue)] hover:text-[var(--text-primary)]'}"
                        aria-current={activeSection === section.id ? "page" : undefined}
                        onclick={() => (activeSection = section.id)}
                    >
                        <section.icon size={15} />
                        <span>{section.label}</span>
                    </button>
                {/each}
            </nav>
        </aside>

        <!-- ===== Main panel ===== -->
        <div class="flex-1 min-w-0 flex flex-col">
            <!-- svelte-ignore a11y_mouse_events_have_key_events -->
            <div
                class="flex-1 overflow-y-auto"
                role="presentation"
                onmouseover={handleTipOver}
                onmouseleave={() => (hoveredTip = "")}
                onfocusin={handleTipOver}
                onfocusout={() => (hoveredTip = "")}
            >
                <div class="w-full max-w-3xl mx-auto py-[var(--space-5)] px-[var(--space-5)] pb-[var(--space-7)]">
                    <h2
                        class="m-0 mb-[var(--space-4)] text-[var(--text-lg)] font-[var(--weight-emphasis)] text-[var(--text-primary)]"
                    >
                        {activeLabel}
                    </h2>

                    <!-- Banners (always visible across sections) -->
                    {#if showGpuRuntimeWarning}
                        <div
                            class="mb-[var(--space-4)] rounded-[var(--radius-lg)] border border-[var(--color-warning)]/40 bg-[color:rgba(255,165,0,0.08)] px-[var(--space-4)] py-[var(--space-3)]"
                        >
                            <div class="flex items-start gap-[var(--space-2)]">
                                <TriangleAlert size={18} class="mt-[2px] shrink-0 text-[var(--color-warning)]" />
                                <div class="min-w-0">
                                    <div
                                        class="text-[var(--text-sm)] font-[var(--weight-emphasis)] text-[var(--text-primary)]"
                                    >
                                        NVIDIA driver detected, but CUDA inference is not ready.
                                    </div>
                                    <div
                                        class="mt-[var(--space-1)] text-[var(--text-sm)] text-[var(--text-secondary)] leading-[var(--leading-normal)]"
                                    >
                                        {health.gpu?.gpu_name || "Detected GPU"} is visible to the driver, but
                                        CTranslate2 cannot use CUDA yet. Vociferous will fall back to CPU until you
                                        install a usable CUDA 12 runtime. CUDA 13 toolchains are not supported by this
                                        build.
                                    </div>
                                    {#if health.gpu?.detail}
                                        <div
                                            class="mt-[var(--space-1)] text-[var(--text-xs)] text-[var(--text-tertiary)] break-words"
                                        >
                                            Probe detail: {health.gpu.detail}
                                        </div>
                                    {/if}
                                </div>
                            </div>
                        </div>
                    {/if}

                    {#if restartRequired && !restartPending}
                        <div
                            class="mb-[var(--space-4)] rounded-[var(--radius-lg)] border border-[var(--accent)]/40 bg-[color:rgba(64,128,255,0.06)] px-[var(--space-4)] py-[var(--space-3)]"
                        >
                            <div class="flex items-start gap-[var(--space-2)]">
                                <TriangleAlert size={18} class="mt-[2px] shrink-0 text-[var(--accent)]" />
                                <div class="min-w-0 flex-1">
                                    <div
                                        class="text-[var(--text-sm)] font-[var(--weight-emphasis)] text-[var(--text-primary)]"
                                    >
                                        Restart required to apply runtime changes
                                    </div>
                                    <div
                                        class="mt-[var(--space-1)] text-[var(--text-sm)] text-[var(--text-secondary)] leading-[var(--leading-normal)]"
                                    >
                                        The engine is still running with the previously loaded {restartReasons.join(
                                            ", ",
                                        )}. Restart the engine to apply your saved changes.
                                    </div>
                                </div>
                                <StyledButton variant="primary" size="sm" onclick={handleRestartEngine}>
                                    Restart Engine
                                </StyledButton>
                            </div>
                        </div>
                    {/if}

                    {#if activeSection === "profile"}
                        <div class="flex flex-col gap-[var(--space-5)]">
                            <section class="flex flex-col gap-[var(--space-3)]">
                                <h3
                                    class="m-0 text-[var(--text-xs)] uppercase tracking-wider font-[var(--weight-emphasis)] text-[var(--text-tertiary)]"
                                >
                                    Profile
                                </h3>
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
                                    class="grid grid-cols-[200px_minmax(0,1fr)] items-start gap-x-[var(--space-4)] min-h-[36px]"
                                >
                                    <label
                                        id="setting-exclude-imported-label"
                                        class="text-[var(--text-sm)] text-[var(--text-primary)]"
                                        for="setting-exclude-imported"
                                        data-tip="Automatically excludes imported audio file transcriptions from analytics calculations."
                                        >Exclude Imports from Analytics</label
                                    >
                                    <ToggleSwitch
                                        id="setting-exclude-imported"
                                        ariaLabelledby="setting-exclude-imported-label"
                                        bind:checked={
                                            () => getSafe(config, "output.exclude_imported_from_analytics", false),
                                            (checked: boolean) =>
                                                setSafe("output.exclude_imported_from_analytics", checked)
                                        }
                                    />
                                </div>
                            </section>

                            <section class="flex flex-col gap-[var(--space-3)]">
                                <h3
                                    class="m-0 text-[var(--text-xs)] uppercase tracking-wider font-[var(--weight-emphasis)] text-[var(--text-tertiary)]"
                                >
                                    Interface
                                </h3>
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
                                            onchange={(v: string) =>
                                                setSafe("display.ui_scale", parseInt(v, 10))}
                                        />
                                    </div>
                                </div>
                            </section>
                        </div>
                    {:else if activeSection === "recording"}
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
                                            if (cur > 1)
                                                setSafe("recording.max_recording_minutes", Math.max(1, cur - 5));
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
                                            if (cur > 0)
                                                setSafe("recording.audio_cache_minutes", Math.max(0, cur - 15));
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
                    {:else if activeSection === "output"}
                        <OutputCard {config} {getSafe} {setSafe} />
                    {:else if activeSection === "refinement"}
                        <RefinementCard
                            {config}
                            {models}
                            {health}
                            {downloadingModel}
                            {downloadMessage}
                            {downloadErrorSlm}
                            {getSafe}
                            {setSafe}
                            {handleDownload}
                        />
                    {:else if activeSection === "asr"}
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
                    {:else if activeSection === "safety"}
                        <SafetyDataCard
                            {config}
                            {health}
                            {getSafe}
                            {setSafe}
                            onTranscriptsCleared={refreshRuntimeState}
                        />
                    {:else if activeSection === "diagnostics"}
                        <DiagnosticsCard
                            {config}
                            {health}
                            {engineStatus}
                            {restartPending}
                            {getSafe}
                            {setSafe}
                            onRestartEngine={handleRestartEngine}
                            onStatusChanged={refreshRuntimeState}
                        />
                    {/if}
                </div>
            </div>

            <!-- Tip bar -->
            <div
                class="shrink-0 h-7 flex items-center justify-center px-[var(--space-4)] text-[11px] text-[var(--text-tertiary)] italic overflow-hidden transition-opacity duration-150 {hoveredTip
                    ? 'opacity-100'
                    : 'opacity-0'}"
            >
                {hoveredTip}
            </div>

            <!-- Save bar — Settings transactions only -->
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
                        <StyledButton variant="ghost" size="sm" onclick={() => discardConfig()} disabled={saving}>
                            <Undo2 size={14} /> Revert
                        </StyledButton>
                        <StyledButton variant="primary" size="sm" onclick={saveConfig} disabled={saving}>
                            {#if saving}<Loader2 size={14} class="spin" /> Saving…{:else}<Save size={14} /> Save and Apply Settings{/if}
                        </StyledButton>
                    {/if}
                </div>
            </div>
        </div>
    {/if}
</div>
