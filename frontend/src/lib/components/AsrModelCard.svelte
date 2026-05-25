<script lang="ts">
    /**
     * AsrModelCard — Whisper ASR model selection, device, threads, language.
     *
     * Extracted from SettingsView. All config mutations flow through
     * parent-supplied `setSafe`.
     */

    import { Loader2, CheckCircle, AlertCircle, RefreshCw, PlugZap } from "lucide-svelte";
    import {
        deleteRefinementProviderApiKey,
        getRefinementProviderApiKeyStatus,
        getTranscriptionProviderModels,
        saveRefinementProviderApiKey,
        testTranscriptionProvider,
        type ExternalProviderModel,
        type ModelInfo,
        type RefinementProviderApiKeyStatus,
        type TranscriptionProviderId,
    } from "../api";
    import type { ConfigPath, GetConfigValue, SetConfigValue, VociferousConfig } from "../config.svelte";
    import { toast } from "../toast.svelte";
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

    let provider = $derived(getSafe(config, "model.provider", "local_faster_whisper"));
    let externalModels: ExternalProviderModel[] = $state([]);
    let externalModelsLoading = $state(false);
    let providerTestMessage = $state("");
    let providerTestOk = $state<boolean | null>(null);
    let apiKeyDraft = $state("");
    let apiKeyBusy = $state(false);
    let apiKeyStatus = $state<RefinementProviderApiKeyStatus | null>(null);
    let apiKeyStatusProvider = $state("");

    function isExternalProvider(value: string): value is TranscriptionProviderId {
        return value === "groq";
    }

    function setProvider(value: string) {
        setSafe("model.provider", value as "local_faster_whisper" | "groq");
        externalModels = [];
        providerTestMessage = "";
        providerTestOk = null;
        apiKeyDraft = "";
    }

    type TranscriptionProviderConfigKey =
        | "base_url"
        | "model_id"
        | "api_key_env"
        | "timeout_seconds"
        | "model_list_enabled";
    type TranscriptionProviderPath<Key extends TranscriptionProviderConfigKey> = Extract<
        ConfigPath,
        `model.${TranscriptionProviderId}.${Key}`
    >;

    function providerPath<Key extends TranscriptionProviderConfigKey>(
        providerId: TranscriptionProviderId,
        key: Key,
    ): TranscriptionProviderPath<Key> {
        return `model.${providerId}.${key}` as TranscriptionProviderPath<Key>;
    }

    function providerPayload(providerId: TranscriptionProviderId) {
        return {
            base_url: getSafe(config, providerPath(providerId, "base_url"), ""),
            model_id: getSafe(config, providerPath(providerId, "model_id"), ""),
            api_key_env: getSafe(config, providerPath(providerId, "api_key_env"), null),
            api_key: apiKeyDraft.trim() || undefined,
            timeout_seconds: getSafe(config, providerPath(providerId, "timeout_seconds"), 120),
            model_list_enabled: getSafe(config, providerPath(providerId, "model_list_enabled"), true),
            max_retries: providerId === "groq" ? getSafe(config, "model.groq.max_retries", 2) : undefined,
            retry_backoff_seconds:
                providerId === "groq" ? getSafe(config, "model.groq.retry_backoff_seconds", 1) : undefined,
        };
    }

    function setApiKeyEnv(providerId: TranscriptionProviderId, value: string) {
        const trimmed = value.trim();
        if (providerId === "groq" && trimmed.startsWith("gsk_")) {
            apiKeyDraft = trimmed;
            setSafe("model.groq.api_key_env", "GROQ_API_KEY");
            toast.error("Paste Groq key values into Stored API Key, not API Key Env Var");
            return;
        }
        setSafe(providerPath(providerId, "api_key_env"), trimmed || null);
    }

    $effect(() => {
        const currentProvider = provider;
        if (isExternalProvider(currentProvider) && currentProvider !== apiKeyStatusProvider) {
            apiKeyStatusProvider = currentProvider;
            void refreshApiKeyStatus(currentProvider);
        }
    });

    async function refreshApiKeyStatus(providerId: TranscriptionProviderId) {
        try {
            apiKeyStatus = await getRefinementProviderApiKeyStatus(providerId);
        } catch {
            apiKeyStatus = null;
        }
    }

    function providerHasUsableApiKey(providerId: TranscriptionProviderId): boolean {
        return Boolean(apiKeyDraft.trim() || apiKeyStatus?.source_valid);
    }

    function apiKeyStatusText(providerId: TranscriptionProviderId): string {
        if (apiKeyStatus?.source === "stored" && apiKeyStatus.source_valid)
            return `Stored local key available via ${apiKeyStatus.backend}.`;
        if (apiKeyStatus?.source === "stored")
            return "Stored Groq key looks invalid. Replace it with the full key from Groq.";
        if (apiKeyStatus?.source === "environment" && apiKeyStatus.source_valid)
            return `Using ${apiKeyStatus.api_key_env ?? "environment"} from the process environment.`;
        if (apiKeyStatus?.source === "environment")
            return `${apiKeyStatus.api_key_env ?? "Environment key"} is set but does not look like a valid Groq key.`;
        if (apiKeyStatus?.backend === "unavailable")
            return "No local secret backend is available; use an environment variable instead.";
        return "No Groq API key configured.";
    }

    function providerHasStoredKey(providerId: TranscriptionProviderId): boolean {
        return apiKeyStatusProvider === providerId && Boolean(apiKeyStatus?.has_stored_key);
    }

    async function saveApiKey(providerId: TranscriptionProviderId) {
        const apiKey = apiKeyDraft.trim();
        if (!apiKey) {
            toast.error("Paste an API key before saving it");
            return;
        }
        apiKeyBusy = true;
        try {
            await saveRefinementProviderApiKey(providerId, apiKey);
            apiKeyDraft = "";
            await refreshApiKeyStatus(providerId);
            toast.success("Provider API key saved locally");
        } catch (e) {
            toast.error(e instanceof Error ? e.message : String(e));
        } finally {
            apiKeyBusy = false;
        }
    }

    async function removeApiKey(providerId: TranscriptionProviderId) {
        apiKeyBusy = true;
        try {
            await deleteRefinementProviderApiKey(providerId);
            await refreshApiKeyStatus(providerId);
            toast.success("Stored provider API key removed");
        } catch (e) {
            toast.error(e instanceof Error ? e.message : String(e));
        } finally {
            apiKeyBusy = false;
        }
    }

    async function refreshExternalModels(providerId: TranscriptionProviderId) {
        externalModelsLoading = true;
        providerTestMessage = "";
        providerTestOk = null;
        if (!providerHasUsableApiKey(providerId)) {
            externalModelsLoading = false;
            providerTestOk = false;
            providerTestMessage = "API key required";
            toast.error("Groq requires an API key before models can be listed");
            return;
        }
        try {
            const result = await getTranscriptionProviderModels(providerId);
            externalModels = result.models;
            providerTestOk = true;
            providerTestMessage = `${result.models.length} models found`;
            toast.success(providerTestMessage);
        } catch (e) {
            providerTestOk = false;
            providerTestMessage = e instanceof Error ? e.message : String(e);
            toast.error(providerTestMessage);
        } finally {
            externalModelsLoading = false;
        }
    }

    async function testExternalConnection(providerId: TranscriptionProviderId) {
        externalModelsLoading = true;
        providerTestMessage = "";
        providerTestOk = null;
        if (!providerHasUsableApiKey(providerId)) {
            externalModelsLoading = false;
            providerTestOk = false;
            providerTestMessage = "API key required";
            toast.error("Groq requires an API key before testing transcription");
            return;
        }
        try {
            const result = await testTranscriptionProvider(providerId, providerPayload(providerId));
            providerTestOk = result.ok;
            providerTestMessage = result.ok ? "Connection ready" : result.error || "Connection failed";
            if (result.models) externalModels = result.models;
            result.ok ? toast.success(providerTestMessage) : toast.error(providerTestMessage);
        } catch (e) {
            providerTestOk = false;
            providerTestMessage = e instanceof Error ? e.message : String(e);
            toast.error(providerTestMessage);
        } finally {
            externalModelsLoading = false;
        }
    }
</script>

<div class="flex flex-col gap-[var(--space-3)]">
    <!-- ASR Provider -->
    <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
        <label
            class="text-[var(--text-sm)] text-[var(--text-primary)]"
            for="setting-asr-provider"
            data-tip="Choose where speech recognition inference runs. Groq sends audio to Groq; local faster-whisper stays on this machine."
            >ASR Provider</label
        >
        <div class="w-full max-w-[460px]">
            <CustomSelect
                id="setting-asr-provider"
                options={[
                    { value: "local_faster_whisper", label: "Local faster-whisper" },
                    { value: "groq", label: "Groq" },
                ]}
                value={String(provider)}
                onchange={setProvider}
            />
        </div>
    </div>

    {#if provider === "local_faster_whisper"}
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
    {:else if isExternalProvider(provider)}
        {@const providerId = provider}
        <!-- Provider Base URL -->
        <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
            <label
                class="text-[var(--text-sm)] text-[var(--text-primary)]"
                for="setting-asr-provider-base-url"
                data-tip="OpenAI-compatible base URL for speech-to-text requests.">Provider Base URL</label
            >
            <input
                id="setting-asr-provider-base-url"
                class="h-9 w-full max-w-[460px] rounded-[var(--radius-md)] border border-[var(--shell-border)] bg-[var(--surface-primary)] px-[var(--space-2)] text-[var(--text-sm)] text-[var(--text-primary)]"
                type="text"
                value={getSafe(config, providerPath(providerId, "base_url"), "")}
                oninput={(e) => setSafe(providerPath(providerId, "base_url"), (e.target as HTMLInputElement).value)}
            />
        </div>

        <!-- Provider Model -->
        <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
            <label
                class="text-[var(--text-sm)] text-[var(--text-primary)]"
                for="setting-asr-provider-model"
                data-tip="Speech-to-text model id sent to the provider.">Provider Model</label
            >
            <div class="flex items-center gap-[var(--space-2)] max-w-[480px]">
                <input
                    id="setting-asr-provider-model"
                    class="h-9 flex-1 rounded-[var(--radius-md)] border border-[var(--shell-border)] bg-[var(--surface-primary)] px-[var(--space-2)] text-[var(--text-sm)] text-[var(--text-primary)]"
                    type="text"
                    value={getSafe(config, providerPath(providerId, "model_id"), "")}
                    oninput={(e) => setSafe(providerPath(providerId, "model_id"), (e.target as HTMLInputElement).value)}
                />
                <button
                    type="button"
                    class="h-9 w-9 inline-flex items-center justify-center rounded-[var(--radius-md)] border border-[var(--shell-border)] bg-[var(--surface-primary)] text-[var(--accent)] hover:bg-[var(--hover-overlay-blue)] disabled:opacity-50"
                    title="Refresh available models"
                    disabled={externalModelsLoading || !providerHasUsableApiKey(providerId)}
                    onclick={() => refreshExternalModels(providerId)}
                >
                    <RefreshCw size={15} class={externalModelsLoading ? "spin" : ""} />
                </button>
            </div>
        </div>

        {#if externalModels.length > 0}
            <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
                <label class="text-[var(--text-sm)] text-[var(--text-primary)]" for="setting-asr-provider-model-list"
                    >Available Models</label
                >
                <div class="w-full max-w-[460px]">
                    <CustomSelect
                        id="setting-asr-provider-model-list"
                        options={externalModels.map((m) => ({ value: m.id, label: m.id }))}
                        value={getSafe(config, providerPath(providerId, "model_id"), "")}
                        onchange={(v: string) => setSafe(providerPath(providerId, "model_id"), v)}
                    />
                </div>
            </div>
        {/if}

        {#if !providerHasStoredKey(providerId)}
            <!-- API Key Env Var -->
            <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
                <label class="text-[var(--text-sm)] text-[var(--text-primary)]" for="setting-asr-api-key-env"
                    >API Key Env Var</label
                >
                <input
                    id="setting-asr-api-key-env"
                    class="h-9 w-56 rounded-[var(--radius-md)] border border-[var(--shell-border)] bg-[var(--surface-primary)] px-[var(--space-2)] text-[var(--text-sm)] text-[var(--text-primary)]"
                    type="text"
                    value={getSafe(config, providerPath(providerId, "api_key_env"), null) ?? ""}
                    oninput={(e) => setApiKeyEnv(providerId, (e.target as HTMLInputElement).value)}
                />
            </div>
        {/if}

        <!-- Stored API Key -->
        <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
            <label class="text-[var(--text-sm)] text-[var(--text-primary)]" for="setting-asr-provider-api-key"
                >Stored API Key</label
            >
            <div class="flex items-center gap-[var(--space-2)] max-w-[480px]">
                <input
                    id="setting-asr-provider-api-key"
                    class="h-9 flex-1 rounded-[var(--radius-md)] border border-[var(--shell-border)] bg-[var(--surface-primary)] px-[var(--space-2)] text-[var(--text-sm)] text-[var(--text-primary)]"
                    type="password"
                    autocomplete="off"
                    placeholder={apiKeyStatus?.has_stored_key ? "Stored locally" : "Optional"}
                    value={apiKeyDraft}
                    oninput={(e) => (apiKeyDraft = (e.target as HTMLInputElement).value)}
                />
                <button
                    type="button"
                    class="h-9 px-[var(--space-3)] rounded-[var(--radius-md)] border border-[var(--shell-border)] bg-[var(--surface-primary)] text-[var(--text-sm)] text-[var(--text-primary)] hover:bg-[var(--hover-overlay-blue)] disabled:opacity-50"
                    disabled={apiKeyBusy || !apiKeyDraft.trim()}
                    onclick={() => saveApiKey(providerId)}>Save</button
                >
                <button
                    type="button"
                    class="h-9 px-[var(--space-3)] rounded-[var(--radius-md)] border border-[var(--shell-border)] bg-[var(--surface-primary)] text-[var(--text-sm)] text-[var(--text-secondary)] hover:bg-[var(--hover-overlay-blue)] disabled:opacity-50"
                    disabled={apiKeyBusy || !apiKeyStatus?.has_stored_key}
                    onclick={() => removeApiKey(providerId)}>Remove</button
                >
            </div>
        </div>

        <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[24px]">
            <div></div>
            <div class="text-[var(--text-xs)] text-[var(--text-tertiary)]">{apiKeyStatusText(providerId)}</div>
        </div>

        <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
            <label class="text-[var(--text-sm)] text-[var(--text-primary)]" for="setting-asr-provider-timeout"
                >Timeout Seconds</label
            >
            <input
                id="setting-asr-provider-timeout"
                class="h-9 w-24 rounded-[var(--radius-md)] border border-[var(--shell-border)] bg-[var(--surface-primary)] px-[var(--space-2)] text-[var(--text-sm)] text-[var(--text-primary)] [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
                type="number"
                min="5"
                max="600"
                value={getSafe(config, providerPath(providerId, "timeout_seconds"), 120)}
                oninput={(e) => {
                    const value = parseFloat((e.target as HTMLInputElement).value);
                    if (!isNaN(value) && value >= 5 && value <= 600)
                        setSafe(providerPath(providerId, "timeout_seconds"), value);
                }}
            />
        </div>

        <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
            <div></div>
            <div class="flex items-center gap-[var(--space-2)]">
                <button
                    type="button"
                    class="h-9 inline-flex items-center gap-[var(--space-2)] px-[var(--space-3)] rounded-[var(--radius-md)] border border-[var(--shell-border)] bg-[var(--surface-primary)] text-[var(--text-sm)] text-[var(--text-primary)] hover:bg-[var(--hover-overlay-blue)] disabled:opacity-50"
                    disabled={externalModelsLoading || !providerHasUsableApiKey(providerId)}
                    onclick={() => testExternalConnection(providerId)}
                >
                    <PlugZap size={15} />
                    Test Connection
                </button>
                {#if providerTestMessage}
                    <span
                        class="text-[var(--text-xs)] {providerTestOk
                            ? 'text-[var(--color-success)]'
                            : 'text-[var(--color-danger)]'}"
                    >
                        {providerTestMessage}
                    </span>
                {/if}
            </div>
        </div>
    {/if}

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
