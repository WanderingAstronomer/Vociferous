<script lang="ts">
    /**
     * AsrModelCard — Whisper ASR model selection, GPU status, device, threads, language.
     *
     * Extracted from SettingsView. Owns `showGpuDetails` toggle internally.
     * All config mutations flow through parent-supplied `setSafe`.
     */

    import { Loader2, Cpu, CheckCircle, AlertCircle } from "lucide-svelte";
    import CustomSelect from "./CustomSelect.svelte";
    import DownloadButton from "./DownloadButton.svelte";

    interface Props {
        config: Record<string, any>;
        models: { asr: Record<string, any>; slm: Record<string, any> };
        health: {
            status: string;
            version: string;
            transcripts: number;
            gpu?: {
                cuda_available?: boolean;
                detail?: string;
                whisper_backends?: string;
                slm_gpu_layers?: number;
            };
        };
        downloadingModel: string | null;
        downloadMessage: string;
        downloadErrorAsr: string;
        getSafe: (obj: any, path: string, fallback?: any) => any;
        setSafe: (path: string, value: any) => void;
        handleDownload: (type: "asr" | "slm", modelId: string) => void;
    }

    let {
        config,
        models,
        health,
        downloadingModel,
        downloadMessage,
        downloadErrorAsr,
        getSafe,
        setSafe,
        handleDownload,
    }: Props = $props();

    /* ===== Internal state ===== */
    let showGpuDetails = $state(false);
</script>

<div
    class="bg-[var(--surface-secondary)] border border-[var(--shell-border)] rounded-[var(--radius-lg)] p-[var(--space-4)] xl:col-span-2"
>
    <div
        class="flex items-center gap-[var(--space-2)] text-[var(--text-base)] font-[var(--weight-emphasis)] text-[var(--text-primary)] mb-[var(--space-4)] pb-[var(--space-2)] border-b border-[var(--shell-border)]"
    >
        <Cpu size={18} class="text-[var(--accent)]" /><span>Whisper ASR</span>
    </div>
    <div class="flex flex-col gap-[var(--space-3)]">
        <!-- Whisper Architecture -->
        <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
            <label
                class="text-[var(--text-sm)] text-[var(--text-primary)]"
                for="setting-model"
                title="Larger models are slower but more accurate. Tiny/Base are fast; Small/Medium offer better quality."
                >Whisper Architecture</label
            >
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
                            <DownloadButton onclick={() => handleDownload("asr", getSafe(config, "model.model"))} />
                        {/if}
                    {:else}
                        <span
                            class="inline-flex items-center gap-1 text-[var(--text-xs)] whitespace-nowrap text-[var(--color-success)]"
                            ><CheckCircle size={14} /></span
                        >
                    {/if}
                {/if}
            </div>
        </div>

        <!-- ASR download error -->
        {#if downloadErrorAsr && !downloadingModel}
            <div class="flex items-start gap-1 text-[var(--text-xs)] text-[var(--color-danger)] py-1">
                <AlertCircle size={14} />
                <span class="break-words leading-[var(--leading-normal)]">{downloadErrorAsr}</span>
            </div>
        {/if}

        <!-- GPU Status -->
        <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
            <div
                class="text-[var(--text-sm)] text-[var(--text-primary)]"
                title="ASR GPU acceleration requires CTranslate2 with CUDA support."
            >GPU Status</div>
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
                {#if health.gpu?.whisper_backends && health.gpu.whisper_backends !== "unavailable"}
                    <button
                        class="w-fit text-[var(--text-xs)] text-[var(--text-tertiary)] bg-transparent border-none p-0 cursor-pointer transition-[color] duration-[var(--transition-fast)] hover:text-[var(--accent)]"
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
                            <span class="text-[var(--text-xs)] text-[var(--text-tertiary)]"
                                >Active backends: {features.join(", ")}</span
                            >
                        {/if}
                    {/if}
                {/if}
            </div>
        </div>

        <!-- ASR Device -->
        <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
            <label
                class="text-[var(--text-sm)] text-[var(--text-primary)]"
                for="setting-device"
                title="Preference for ASR backend selection. Requires engine restart after saving."
                >ASR Device</label
            >
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
        </div>

        <!-- ASR Threads -->
        <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
            <label
                class="text-[var(--text-sm)] text-[var(--text-primary)]"
                for="setting-threads"
                title="CPU threads for Whisper inference. Higher values use more cores but may improve speed. Default: 4."
                >ASR Threads</label
            >
            <input
                id="setting-threads"
                class="h-9 w-24 rounded-[var(--radius-md)] border border-[var(--shell-border)] bg-[var(--surface-primary)] px-[var(--space-2)] text-[var(--text-sm)] text-[var(--text-primary)] [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
                type="number"
                min="1"
                max="32"
                value={getSafe(config, "model.n_threads", 4)}
                oninput={(e) => {
                    const v = parseInt((e.target as HTMLInputElement).value);
                    if (!isNaN(v) && v >= 1 && v <= 32) setSafe("model.n_threads", v);
                }}
            />
        </div>

        <!-- Language -->
        <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
            <label
                class="text-[var(--text-sm)] text-[var(--text-primary)]"
                for="setting-language"
                title="Auto-detect works but is slower and slightly less accurate than specifying a language explicitly."
                >Language</label
            >
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
        </div>
    </div>
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
