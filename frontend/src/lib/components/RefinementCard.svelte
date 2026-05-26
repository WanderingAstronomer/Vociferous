<script lang="ts">
    /**
     * RefinementCard — SLM refinement configuration.
     *
     * Grammar enable toggle, device selection, model picker + download,
     * auto-refine / auto-retitle toggles, and advanced sampling collapsible.
     */

    import { Loader2, CheckCircle, AlertCircle, ChevronDown, Info, RefreshCw, PlugZap } from "lucide-svelte";
    import {
        deleteRefinementProviderApiKey,
        getRefinementProviderApiKeyStatus,
        getRefinementProviderModels,
        saveRefinementProviderApiKey,
        testRefinementProvider,
        type ExternalProviderModel,
        type HealthInfo,
        type ModelInfo,
        type RefinementProviderApiKeyStatus,
        type RefinementProviderId,
    } from "../api";
    import type { ConfigPath, GetConfigValue, SetConfigValue, VociferousConfig } from "../config.svelte";
    import { toast } from "../toast.svelte";
    import ToggleSwitch from "./ToggleSwitch.svelte";
    import CustomSelect from "./CustomSelect.svelte";
    import DownloadButton from "./DownloadButton.svelte";

    interface Props {
        config: VociferousConfig;
        models: { slm: Record<string, ModelInfo> };
        health: HealthInfo;
        downloadingModel: string | null;
        downloadMessage: string;
        downloadErrorSlm: string;
        getSafe: GetConfigValue;
        setSafe: SetConfigValue;
        handleDownload: (type: "asr" | "slm", modelId: string) => void;
    }

    const DEFAULT_SLM_MODEL_ID = "qwen4b";

    let {
        config,
        models,
        health,
        downloadingModel,
        downloadMessage,
        downloadErrorSlm,
        getSafe,
        setSafe,
        handleDownload,
    }: Props = $props();

    let advancedOpen = $state(false);
    let externalModels: ExternalProviderModel[] = $state([]);
    let externalModelsLoading = $state(false);
    let providerTestMessage = $state("");
    let providerTestOk = $state<boolean | null>(null);
    let apiKeyDraft = $state("");
    let apiKeyBusy = $state(false);
    let apiKeyStatus = $state<RefinementProviderApiKeyStatus | null>(null);
    let apiKeyStatusProvider = $state("");

    let provider = $derived(getSafe(config, "refinement.provider", "local_ct2"));
    /* n_gpu_layers is the stored runtime preference: -1 means prefer GPU with CPU fallback, 0 means force CPU. */
    let deviceValue = $derived(getSafe(config, "refinement.n_gpu_layers", -1) === 0 ? "cpu" : "gpu");
    let isCpu = $derived(deviceValue === "cpu");
    let gpuWillFallbackToCpu = $derived(deviceValue === "gpu" && !health.gpu?.cuda_available);
    let showsCpuRuntimeControls = $derived(isCpu || gpuWillFallbackToCpu);

    /* AWQ + CPU incompatibility check */
    let selectedModelQuant = $derived(
        models.slm[getSafe(config, "refinement.model_id", DEFAULT_SLM_MODEL_ID)]?.quant ?? "",
    );
    let awqCpuConflict = $derived(isCpu && selectedModelQuant === "awq");
    let awqAutoFallback = $derived(gpuWillFallbackToCpu && selectedModelQuant === "awq");

    function setDevice(v: string) {
        setSafe("refinement.n_gpu_layers", v === "cpu" ? 0 : -1);
    }

    function setProvider(v: string) {
        setSafe("refinement.provider", v as "local_ct2" | "lm_studio" | "groq");
        providerTestMessage = "";
        providerTestOk = null;
        externalModels = [];
        apiKeyDraft = "";
    }

    function isExternalProvider(value: string): value is RefinementProviderId {
        return value === "lm_studio" || value === "groq";
    }

    type RefinementProviderConfigKey =
        | "base_url"
        | "model_id"
        | "api_key_env"
        | "timeout_seconds"
        | "max_output_tokens"
        | "model_list_enabled";
    type RefinementProviderPath<Key extends RefinementProviderConfigKey> = Extract<
        ConfigPath,
        `refinement.${RefinementProviderId}.${Key}`
    >;

    function providerPath<Key extends RefinementProviderConfigKey>(
        providerId: RefinementProviderId,
        key: Key,
    ): RefinementProviderPath<Key> {
        return `refinement.${providerId}.${key}` as RefinementProviderPath<Key>;
    }

    function providerPayload(providerId: RefinementProviderId) {
        return {
            base_url: getSafe(config, providerPath(providerId, "base_url"), ""),
            model_id: getSafe(config, providerPath(providerId, "model_id"), ""),
            api_key_env: getSafe(config, providerPath(providerId, "api_key_env"), null),
            api_key: apiKeyDraft.trim() || undefined,
            timeout_seconds: getSafe(config, providerPath(providerId, "timeout_seconds"), 120),
            max_output_tokens: getSafe(config, providerPath(providerId, "max_output_tokens"), 1024),
            model_list_enabled: getSafe(config, providerPath(providerId, "model_list_enabled"), true),
            max_retries: providerId === "groq" ? getSafe(config, "refinement.groq.max_retries", 2) : undefined,
            retry_backoff_seconds:
                providerId === "groq" ? getSafe(config, "refinement.groq.retry_backoff_seconds", 1) : undefined,
        };
    }

    function setApiKeyEnv(providerId: RefinementProviderId, value: string) {
        const trimmed = value.trim();
        if (providerId === "groq" && trimmed.startsWith("gsk_")) {
            apiKeyDraft = trimmed;
            setSafe("refinement.groq.api_key_env", "GROQ_API_KEY");
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

    async function refreshApiKeyStatus(providerId: RefinementProviderId) {
        try {
            apiKeyStatus = await getRefinementProviderApiKeyStatus(providerId);
        } catch {
            apiKeyStatus = null;
        }
    }

    function providerHasUsableApiKey(providerId: RefinementProviderId): boolean {
        if (providerId === "lm_studio") return true;
        return Boolean(apiKeyDraft.trim() || apiKeyStatus?.source_valid);
    }

    function apiKeyStatusText(providerId: RefinementProviderId): string {
        if (providerId === "lm_studio") return "LM Studio usually does not require an API key.";
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

    function providerHasStoredKey(providerId: RefinementProviderId): boolean {
        return apiKeyStatusProvider === providerId && Boolean(apiKeyStatus?.has_stored_key);
    }

    async function saveApiKey(providerId: RefinementProviderId) {
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

    async function removeApiKey(providerId: RefinementProviderId) {
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

    async function refreshExternalModels(providerId: RefinementProviderId) {
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
            const result = await getRefinementProviderModels(providerId);
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

    async function testExternalConnection(providerId: RefinementProviderId) {
        externalModelsLoading = true;
        providerTestMessage = "";
        providerTestOk = null;
        if (!providerHasUsableApiKey(providerId)) {
            externalModelsLoading = false;
            providerTestOk = false;
            providerTestMessage = "API key required";
            toast.error("Groq requires an API key before testing the connection");
            return;
        }
        try {
            const result = await testRefinementProvider(providerId, providerPayload(providerId));
            externalModels = result.models ?? externalModels;
            providerTestOk = result.ok;
            providerTestMessage = result.ok ? "Connection ready" : result.error || "Connection failed";
            if (result.ok) toast.success(providerTestMessage);
            else toast.error(providerTestMessage);
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
    <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
        <label
            id="setting-refinement-label"
            class="text-[var(--text-sm)] text-[var(--text-primary)]"
            for="setting-refinement"
            data-tip="Uses a local language model to improve grammar and punctuation after transcription."
            >Grammar Refinement</label
        >
        <ToggleSwitch
            id="setting-refinement"
            ariaLabelledby="setting-refinement-label"
            bind:checked={
                () => getSafe(config, "refinement.enabled", false),
                (checked: boolean) => setSafe("refinement.enabled", checked)
            }
        />
    </div>

    {#if getSafe(config, "refinement.enabled", false)}
        <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
            <label
                class="text-[var(--text-sm)] text-[var(--text-primary)]"
                for="setting-refprovider"
                data-tip="Choose where refinement inference runs. Local keeps text on this machine; Groq sends text to Groq's cloud API."
                >Refinement Provider</label
            >
            <div class="w-full max-w-[460px]">
                <CustomSelect
                    id="setting-refprovider"
                    options={[
                        { value: "local_ct2", label: "Local CTranslate2" },
                        { value: "lm_studio", label: "LM Studio" },
                        { value: "groq", label: "Groq" },
                    ]}
                    value={provider}
                    onchange={setProvider}
                />
            </div>
        </div>

        {#if provider === "local_ct2"}
            <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
                <label
                    class="text-[var(--text-sm)] text-[var(--text-primary)]"
                    for="setting-refdevice"
                    data-tip="Auto uses CUDA when available and falls back to CPU when it is not. Force CPU ignores CUDA."
                    >Refinement Device</label
                >
                <div class="w-full max-w-[460px]">
                    <CustomSelect
                        id="setting-refdevice"
                        options={[
                            { value: "gpu", label: "Auto (GPU if available)" },
                            { value: "cpu", label: "CPU only" },
                        ]}
                        value={deviceValue}
                        onchange={(v: string) => setDevice(v)}
                    />
                </div>
            </div>
            {#if showsCpuRuntimeControls}
                <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
                    <label
                        class="text-[var(--text-sm)] text-[var(--text-primary)]"
                        for="setting-refthreads"
                        data-tip="CPU threads for refinement inference. Higher values use more cores but may improve speed. Default: automatic logical cores divided by 3, clamped between 2 and 10."
                        >Refinement Threads</label
                    >
                    <input
                        id="setting-refthreads"
                        class="h-9 w-24 rounded-[var(--radius-md)] border border-[var(--shell-border)] bg-[var(--surface-primary)] px-[var(--space-2)] text-[var(--text-sm)] text-[var(--text-primary)] [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
                        type="number"
                        min="1"
                        max="32"
                        value={getSafe(config, "refinement.n_threads", 4)}
                        oninput={(e) => {
                            const v = parseInt((e.target as HTMLInputElement).value);
                            if (!isNaN(v) && v >= 1 && v <= 32) setSafe("refinement.n_threads", v);
                        }}
                    />
                </div>
            {/if}
            <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
                <label
                    class="text-[var(--text-sm)] text-[var(--text-primary)]"
                    for="setting-refmodel"
                    data-tip="Larger models produce better refinements but use more RAM and are slower."
                    >Refinement Model</label
                >
                <div class="flex items-center gap-[var(--space-2)]">
                    <div class="w-full max-w-[460px]">
                        <CustomSelect
                            id="setting-refmodel"
                            options={Object.entries(models.slm).map(([id, m]) => ({
                                value: id,
                                label: `${m.name} (${m.size_mb}MB)${m.downloaded ? "" : " ⬇"}${showsCpuRuntimeControls && m.quant === "awq" ? " — GPU only" : ""}`,
                            }))}
                            value={getSafe(config, "refinement.model_id", DEFAULT_SLM_MODEL_ID)}
                            onchange={(v: string) => setSafe("refinement.model_id", v)}
                            placeholder="Select model…"
                        />
                    </div>
                    {#if models.slm[getSafe(config, "refinement.model_id", DEFAULT_SLM_MODEL_ID)]}
                        {@const selectedSlm = models.slm[getSafe(config, "refinement.model_id", DEFAULT_SLM_MODEL_ID)]}
                        {#if !selectedSlm.downloaded}
                            {#if downloadingModel === getSafe(config, "refinement.model_id", DEFAULT_SLM_MODEL_ID)}
                                <span
                                    class="inline-flex items-center gap-1 text-[var(--text-xs)] whitespace-nowrap text-[var(--accent)] shrink overflow-hidden"
                                >
                                    <Loader2 size={14} class="spin" />
                                    <span class="overflow-hidden text-ellipsis whitespace-nowrap"
                                        >{downloadMessage}</span
                                    >
                                </span>
                            {:else}
                                <DownloadButton
                                    onclick={() =>
                                        handleDownload(
                                            "slm",
                                            getSafe(config, "refinement.model_id", DEFAULT_SLM_MODEL_ID),
                                        )}
                                />
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
            {#if downloadErrorSlm && !downloadingModel}
                <div class="flex items-start gap-1 text-[var(--text-xs)] text-[var(--color-danger)] py-1">
                    <AlertCircle size={14} />
                    <span class="break-words leading-[var(--leading-normal)]">{downloadErrorSlm}</span>
                </div>
            {/if}
            {#if awqCpuConflict}
                <div class="flex items-start gap-1 text-[var(--text-xs)] text-[var(--color-warning, #e5a00d)] py-1">
                    <AlertCircle size={14} />
                    <span class="leading-[var(--leading-normal)]"
                        >AWQ models require GPU. Switch to Auto or choose the 4B int8 model for CPU inference.</span
                    >
                </div>
            {:else if awqAutoFallback}
                <div class="flex items-start gap-1 text-[var(--text-xs)] text-[var(--text-secondary)] py-1">
                    <Info size={14} class="shrink-0 mt-px" />
                    <span class="leading-[var(--leading-normal)]"
                        >CUDA is not usable, so refinement will run on CPU. AWQ models cannot run on CPU; Vociferous
                        will use the 4B int8 model if it is downloaded.</span
                    >
                </div>
            {:else if showsCpuRuntimeControls}
                <div class="flex items-start gap-1 text-[var(--text-xs)] text-[var(--text-secondary)] py-1">
                    <Info size={14} class="shrink-0 mt-px" />
                    <span class="leading-[var(--leading-normal)]"
                        >CPU refinement uses the int8 model path. AWQ models require CUDA and will use the 4B int8 CPU
                        fallback when Auto cannot use GPU.</span
                    >
                </div>
            {/if}
        {:else if isExternalProvider(provider)}
            <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
                <label
                    class="text-[var(--text-sm)] text-[var(--text-primary)]"
                    for="setting-provider-url"
                    data-tip="OpenAI-compatible base URL. LM Studio usually uses http://localhost:1234/v1; Groq uses https://api.groq.com/openai/v1."
                    >Provider Base URL</label
                >
                <input
                    id="setting-provider-url"
                    class="h-9 w-full max-w-[460px] rounded-[var(--radius-md)] border border-[var(--shell-border)] bg-[var(--surface-primary)] px-[var(--space-2)] text-[var(--text-sm)] text-[var(--text-primary)]"
                    type="text"
                    value={getSafe(config, providerPath(provider, "base_url"), "")}
                    oninput={(e) => setSafe(providerPath(provider, "base_url"), (e.target as HTMLInputElement).value)}
                />
            </div>
            <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
                <label
                    class="text-[var(--text-sm)] text-[var(--text-primary)]"
                    for="setting-provider-model"
                    data-tip="Model identifier sent to the provider's chat completions endpoint.">Provider Model</label
                >
                <div class="flex items-center gap-[var(--space-2)]">
                    <input
                        id="setting-provider-model"
                        class="h-9 w-full max-w-[460px] rounded-[var(--radius-md)] border border-[var(--shell-border)] bg-[var(--surface-primary)] px-[var(--space-2)] text-[var(--text-sm)] text-[var(--text-primary)]"
                        type="text"
                        value={getSafe(config, providerPath(provider, "model_id"), "")}
                        oninput={(e) =>
                            setSafe(providerPath(provider, "model_id"), (e.target as HTMLInputElement).value)}
                    />
                    <button
                        type="button"
                        class="inline-flex h-9 w-9 items-center justify-center rounded-[var(--radius-md)] border border-[var(--shell-border)] bg-[var(--surface-primary)] text-[var(--accent)] hover:bg-[var(--hover-overlay-blue)] disabled:opacity-50"
                        aria-label="Refresh provider models"
                        disabled={externalModelsLoading || !providerHasUsableApiKey(provider)}
                        onclick={() => refreshExternalModels(provider)}
                    >
                        {#if externalModelsLoading}
                            <Loader2 size={15} class="spin" />
                        {:else}
                            <RefreshCw size={15} />
                        {/if}
                    </button>
                </div>
            </div>
            {#if externalModels.length > 0}
                <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
                    <label
                        class="text-[var(--text-sm)] text-[var(--text-primary)]"
                        for="setting-provider-model-list"
                        data-tip="Models returned by the provider's /models endpoint.">Available Models</label
                    >
                    <div class="w-full max-w-[460px]">
                        <CustomSelect
                            id="setting-provider-model-list"
                            options={externalModels.map((model) => ({ value: model.id, label: model.id }))}
                            value={getSafe(config, providerPath(provider, "model_id"), "")}
                            onchange={(v: string) => setSafe(providerPath(provider, "model_id"), v)}
                        />
                    </div>
                </div>
            {/if}
            {#if provider !== "lm_studio" && !providerHasStoredKey(provider)}
                <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
                    <label
                        class="text-[var(--text-sm)] text-[var(--text-primary)]"
                        for="setting-provider-key-env"
                        data-tip="Environment variable containing the provider API key. Groq defaults to GROQ_API_KEY. The key value itself is never stored in normal settings."
                        >API Key Env Var</label
                    >
                    <input
                        id="setting-provider-key-env"
                        class="h-9 w-56 rounded-[var(--radius-md)] border border-[var(--shell-border)] bg-[var(--surface-primary)] px-[var(--space-2)] text-[var(--text-sm)] text-[var(--text-primary)]"
                        type="text"
                        value={getSafe(config, providerPath(provider, "api_key_env"), null) ?? ""}
                        oninput={(e) => setApiKeyEnv(provider, (e.target as HTMLInputElement).value)}
                    />
                </div>
            {/if}
            <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
                <label
                    class="text-[var(--text-sm)] text-[var(--text-primary)]"
                    for="setting-provider-api-key"
                    data-tip="Paste a provider API key to test it or save it into the local OS-backed secret store. The key is not written to settings.json."
                    >Stored API Key</label
                >
                <div class="flex min-w-0 flex-wrap items-center gap-[var(--space-2)]">
                    <input
                        id="setting-provider-api-key"
                        class="h-9 w-full max-w-[320px] rounded-[var(--radius-md)] border border-[var(--shell-border)] bg-[var(--surface-primary)] px-[var(--space-2)] text-[var(--text-sm)] text-[var(--text-primary)]"
                        type="password"
                        autocomplete="off"
                        placeholder={apiKeyStatus?.has_stored_key
                            ? "Saved key present"
                            : provider === "groq"
                              ? "Paste Groq key"
                              : "Optional local-server key"}
                        value={apiKeyDraft}
                        oninput={(e) => (apiKeyDraft = (e.target as HTMLInputElement).value)}
                    />
                    <button
                        type="button"
                        class="inline-flex h-9 items-center gap-2 rounded-[var(--radius-md)] border border-[var(--shell-border)] bg-[var(--surface-primary)] px-[var(--space-3)] text-[var(--text-sm)] text-[var(--accent)] hover:bg-[var(--hover-overlay-blue)] disabled:opacity-50"
                        disabled={apiKeyBusy || !apiKeyDraft.trim()}
                        onclick={() => saveApiKey(provider)}
                    >
                        {#if apiKeyBusy}<Loader2 size={15} class="spin" />{/if}
                        Save Key
                    </button>
                    <button
                        type="button"
                        class="inline-flex h-9 items-center gap-2 rounded-[var(--radius-md)] border border-[var(--shell-border)] bg-[var(--surface-primary)] px-[var(--space-3)] text-[var(--text-sm)] text-[var(--text-secondary)] hover:bg-[var(--hover-overlay-blue)] disabled:opacity-50"
                        disabled={apiKeyBusy || !apiKeyStatus?.has_stored_key}
                        onclick={() => removeApiKey(provider)}
                    >
                        Remove
                    </button>
                </div>
            </div>
            <div class="grid grid-cols-[200px_minmax(0,1fr)] items-start gap-x-[var(--space-4)] min-h-[24px]">
                <span></span>
                <span class="text-[var(--text-xs)] text-[var(--text-tertiary)] leading-[var(--leading-normal)]">
                    {apiKeyStatusText(provider)}
                </span>
            </div>
            <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
                <span
                    class="text-[var(--text-sm)] text-[var(--text-primary)]"
                    data-tip="Checks provider connectivity and authentication using the current draft settings."
                    >Provider Check</span
                >
                <div class="flex items-center gap-[var(--space-2)]">
                    <button
                        type="button"
                        class="inline-flex h-9 items-center gap-2 rounded-[var(--radius-md)] border border-[var(--shell-border)] bg-[var(--surface-primary)] px-[var(--space-3)] text-[var(--text-sm)] text-[var(--accent)] hover:bg-[var(--hover-overlay-blue)] disabled:opacity-50"
                        disabled={externalModelsLoading || !providerHasUsableApiKey(provider)}
                        onclick={() => testExternalConnection(provider)}
                    >
                        {#if externalModelsLoading}<Loader2 size={15} class="spin" />{:else}<PlugZap size={15} />{/if}
                        Test
                    </button>
                    {#if providerTestMessage}
                        <span
                            class="text-[var(--text-xs)] {providerTestOk
                                ? 'text-[var(--color-success)]'
                                : 'text-[var(--color-danger)]'}">{providerTestMessage}</span
                        >
                    {/if}
                </div>
            </div>
            {#if provider === "groq"}
                <div class="flex items-start gap-1 text-[var(--text-xs)] text-[var(--color-warning, #e5a00d)] py-1">
                    <AlertCircle size={14} />
                    <span class="leading-[var(--leading-normal)]"
                        >Groq refinement sends transcript text to Groq's cloud API for inference.</span
                    >
                </div>
            {:else}
                <div class="flex items-start gap-1 text-[var(--text-xs)] text-[var(--text-secondary)] py-1">
                    <Info size={14} class="shrink-0 mt-px" />
                    <span class="leading-[var(--leading-normal)]"
                        >LM Studio must be running its local server, usually from the Developer tab or lms server start.</span
                    >
                </div>
            {/if}
        {/if}
        <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
            <label
                id="setting-autorefine-label"
                class="text-[var(--text-sm)] text-[var(--text-primary)]"
                for="setting-autorefine"
                data-tip="Automatically refines each transcription with the default refinement level immediately after recording."
                >Auto-Refine After Recording</label
            >
            <ToggleSwitch
                id="setting-autorefine"
                ariaLabelledby="setting-autorefine-label"
                bind:checked={
                    () => getSafe(config, "output.auto_refine", false),
                    (checked: boolean) => setSafe("output.auto_refine", checked)
                }
            />
        </div>
        <div class="grid grid-cols-[200px_minmax(0,1fr)] items-start gap-x-[var(--space-4)] min-h-[36px]">
            <label
                id="setting-smart-refinement-label"
                class="text-[var(--text-sm)] text-[var(--text-primary)]"
                for="setting-smart-refinement"
                data-tip="Enable to intelligently skip refinement for transcripts with minimal errors."
                >Smart Refinement</label
            >
            <div class="flex flex-col gap-1">
                <ToggleSwitch
                    id="setting-smart-refinement"
                    ariaLabelledby="setting-smart-refinement-label"
                    bind:checked={
                        () => getSafe(config, "refinement.smart_refinement", false),
                        (checked: boolean) => setSafe("refinement.smart_refinement", checked)
                    }
                />
                <span class="text-[var(--text-xs)] text-[var(--text-tertiary)] leading-[var(--leading-normal)]">
                    Enable to intelligently skip refinement for transcripts with minimal errors.
                </span>
            </div>
        </div>
        <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
            <label
                id="setting-retitle-refine-label"
                class="text-[var(--text-sm)] text-[var(--text-primary)]"
                for="setting-retitle-refine"
                data-tip="Automatically regenerates the transcript title when a refinement is accepted. Uses the refined text for a more accurate title."
                >Auto-Retitle on Refine</label
            >
            <ToggleSwitch
                id="setting-retitle-refine"
                ariaLabelledby="setting-retitle-refine-label"
                bind:checked={
                    () => getSafe(config, "output.auto_retitle_on_refine", true),
                    (checked: boolean) => setSafe("output.auto_retitle_on_refine", checked)
                }
            />
        </div>

        <!-- Advanced Sampling Parameters -->
        <button
            class="flex items-center gap-[var(--space-2)] mt-[var(--space-2)] py-[var(--space-2)] px-0 text-[var(--text-sm)] text-[var(--text-tertiary)] bg-transparent border-none cursor-pointer transition-colors duration-[var(--transition-fast)] hover:text-[var(--text-primary)]"
            onclick={() => (advancedOpen = !advancedOpen)}
        >
            <ChevronDown
                size={14}
                class="transition-transform duration-[var(--transition-fast)] {advancedOpen
                    ? 'rotate-0'
                    : '-rotate-90'}"
            />
            Advanced Sampling
        </button>
        {#if advancedOpen}
            <div class="flex flex-col gap-[var(--space-3)] pl-[var(--space-3)] border-l-2 border-[var(--shell-border)]">
                <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
                    <label
                        class="text-[var(--text-sm)] text-[var(--text-primary)]"
                        for="setting-temperature"
                        data-tip="Controls randomness. Lower = more deterministic, higher = more creative. Default: 0.3"
                        >Temperature</label
                    >
                    <input
                        id="setting-temperature"
                        class="h-9 w-24 rounded-[var(--radius-md)] border border-[var(--shell-border)] bg-[var(--surface-primary)] px-[var(--space-2)] text-[var(--text-sm)] text-[var(--text-primary)] [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
                        type="number"
                        min="0.01"
                        max="2.0"
                        step="0.05"
                        value={getSafe(config, "refinement.temperature", 0.3)}
                        oninput={(e) => {
                            const v = parseFloat((e.target as HTMLInputElement).value);
                            if (!isNaN(v) && v >= 0.01 && v <= 2.0) setSafe("refinement.temperature", v);
                        }}
                    />
                </div>
                <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
                    <label
                        class="text-[var(--text-sm)] text-[var(--text-primary)]"
                        for="setting-top-p"
                        data-tip="Nucleus sampling. Only tokens with cumulative probability ≤ this value are considered. Default: 0.9"
                        >Top-P</label
                    >
                    <input
                        id="setting-top-p"
                        class="h-9 w-24 rounded-[var(--radius-md)] border border-[var(--shell-border)] bg-[var(--surface-primary)] px-[var(--space-2)] text-[var(--text-sm)] text-[var(--text-primary)] [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
                        type="number"
                        min="0.01"
                        max="1.0"
                        step="0.05"
                        value={getSafe(config, "refinement.top_p", 0.9)}
                        oninput={(e) => {
                            const v = parseFloat((e.target as HTMLInputElement).value);
                            if (!isNaN(v) && v >= 0.01 && v <= 1.0) setSafe("refinement.top_p", v);
                        }}
                    />
                </div>
                {#if provider === "local_ct2" || provider === "lm_studio"}
                    <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
                        <label
                            class="text-[var(--text-sm)] text-[var(--text-primary)]"
                            for="setting-top-k"
                            data-tip="Only the top-k most probable tokens are considered at each step. Default: 20"
                            >Top-K</label
                        >
                        <input
                            id="setting-top-k"
                            class="h-9 w-24 rounded-[var(--radius-md)] border border-[var(--shell-border)] bg-[var(--surface-primary)] px-[var(--space-2)] text-[var(--text-sm)] text-[var(--text-primary)] [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
                            type="number"
                            min="1"
                            max="200"
                            step="1"
                            value={getSafe(config, "refinement.top_k", 20)}
                            oninput={(e) => {
                                const v = parseInt((e.target as HTMLInputElement).value);
                                if (!isNaN(v) && v >= 1 && v <= 200) setSafe("refinement.top_k", v);
                            }}
                        />
                    </div>
                    <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
                        <label
                            class="text-[var(--text-sm)] text-[var(--text-primary)]"
                            for="setting-repetition-penalty"
                            data-tip="Penalizes tokens that already appeared. 1.0 = no penalty, higher = less repetition. Default: 1.0"
                            >Repetition Penalty</label
                        >
                        <input
                            id="setting-repetition-penalty"
                            class="h-9 w-24 rounded-[var(--radius-md)] border border-[var(--shell-border)] bg-[var(--surface-primary)] px-[var(--space-2)] text-[var(--text-sm)] text-[var(--text-primary)] [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
                            type="number"
                            min="1.0"
                            max="2.0"
                            step="0.05"
                            value={getSafe(config, "refinement.repetition_penalty", 1.0)}
                            oninput={(e) => {
                                const v = parseFloat((e.target as HTMLInputElement).value);
                                if (!isNaN(v) && v >= 1.0 && v <= 2.0) setSafe("refinement.repetition_penalty", v);
                            }}
                        />
                    </div>
                {/if}
                {#if provider === "local_ct2"}
                    <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
                        <label
                            id="setting-use-thinking-label"
                            class="text-[var(--text-sm)] text-[var(--text-primary)]"
                            for="setting-use-thinking"
                            data-tip="Allow the model to reason internally before producing output. Improves quality on complex edits but uses more tokens and is slower. Only effective on reasoning-capable models."
                            >Enable Thinking Mode</label
                        >
                        <ToggleSwitch
                            id="setting-use-thinking"
                            ariaLabelledby="setting-use-thinking-label"
                            bind:checked={
                                () => getSafe(config, "refinement.use_thinking", false),
                                (checked: boolean) => setSafe("refinement.use_thinking", checked)
                            }
                        />
                    </div>
                {/if}
            </div>
        {/if}
    {/if}
</div>
