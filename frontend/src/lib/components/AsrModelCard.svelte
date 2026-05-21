<script lang="ts">
    /**
     * AsrModelCard — Whisper ASR model selection, device, threads, language.
     *
     * Extracted from SettingsView. All config mutations flow through
     * parent-supplied `setSafe`.
     */

    import { Loader2, CheckCircle, AlertCircle } from "lucide-svelte";
    import type { ModelInfo } from "../api";
    import type { GetConfigValue, SetConfigValue, VociferousConfig } from "../config.svelte";
    import CustomSelect from "./CustomSelect.svelte";
    import DownloadButton from "./DownloadButton.svelte";

    interface Props {
        config: VociferousConfig;
        models: { asr: Record<string, ModelInfo> };
        downloadingModel: string | null;
        downloadMessage: string;
        downloadErrorAsr: string;
        getSafe: GetConfigValue;
        setSafe: SetConfigValue;
        handleDownload: (type: "asr" | "slm", modelId: string) => void;
    }

    let {
        config,
        models,
        downloadingModel,
        downloadMessage,
        downloadErrorAsr,
        getSafe,
        setSafe,
        handleDownload,
    }: Props = $props();

</script>

<div class="flex flex-col gap-[var(--space-3)]">
    <!-- Whisper Architecture -->
    <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
        <label
            class="text-[var(--text-sm)] text-[var(--text-primary)]"
            for="setting-model"
            data-tip="Larger models are slower but more accurate. Tiny/Base are fast; Small/Medium offer better quality."
            >Whisper Architecture</label
        >
        <div class="flex items-center gap-[var(--space-2)]">
            <div class="w-full max-w-[460px]">
                <CustomSelect
                    id="setting-model"
                    options={Object.entries(models.asr).map(([id, m]) => ({
                        value: id,
                        label: `${m.name} (${m.size_mb}MB)${m.downloaded ? "" : " ⬇"}`,
                    }))}
                    value={String(getSafe(config, "model.model", ""))}
                    onchange={(v: string) => setSafe("model.model", v)}
                    placeholder="Select model…"
                />
            </div>
            {#if models.asr[getSafe(config, "model.model", "")]}
                {@const selectedAsr = models.asr[getSafe(config, "model.model", "")]}
                {#if !selectedAsr.downloaded}
                    {#if downloadingModel === getSafe(config, "model.model", "")}
                        <span
                            class="inline-flex items-center gap-1 text-[var(--text-xs)] whitespace-nowrap text-[var(--accent)] shrink overflow-hidden"
                        >
                            <Loader2 size={14} class="spin" />
                            <span class="overflow-hidden text-ellipsis whitespace-nowrap">{downloadMessage}</span>
                        </span>
                    {:else}
                        <DownloadButton onclick={() => handleDownload("asr", getSafe(config, "model.model", ""))} />
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

    <!-- ASR Device -->
    <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
        <label
            class="text-[var(--text-sm)] text-[var(--text-primary)]"
            for="setting-device"
            data-tip="Preference for ASR backend selection. Requires engine restart after saving.">ASR Device</label
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
            data-tip="CPU threads for Whisper inference. Higher values use more cores but may improve speed. Default: 4."
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
            data-tip="Auto-detect works but is slower and slightly less accurate than specifying a language explicitly."
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
