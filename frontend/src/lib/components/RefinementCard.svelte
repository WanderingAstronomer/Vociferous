<script lang="ts">
    /**
     * RefinementCard — SLM refinement configuration.
     *
     * Grammar enable toggle, device selection, model picker + download,
     * auto-refine / auto-retitle toggles, and advanced sampling collapsible.
     */

    import { Loader2, CheckCircle, AlertCircle, ChevronDown, Info } from "lucide-svelte";
    import ToggleSwitch from "./ToggleSwitch.svelte";
    import CustomSelect from "./CustomSelect.svelte";
    import DownloadButton from "./DownloadButton.svelte";

    interface Props {
        config: Record<string, any>;
        models: { slm: Record<string, any> };
        downloadingModel: string | null;
        downloadMessage: string;
        downloadErrorSlm: string;
        getSafe: (obj: any, path: string, fallback?: any) => any;
        setSafe: (path: string, value: any) => void;
        handleDownload: (type: "asr" | "slm", modelId: string) => void;
    }

    let {
        config,
        models,
        downloadingModel,
        downloadMessage,
        downloadErrorSlm,
        getSafe,
        setSafe,
        handleDownload,
    }: Props = $props();

    let advancedOpen = $state(false);

    /* Map n_gpu_layers to a sane dropdown value */
    let deviceValue = $derived(getSafe(config, "refinement.n_gpu_layers", -1) === 0 ? "cpu" : "gpu");
    let isCpu = $derived(deviceValue === "cpu");

    /* AWQ + CPU incompatibility check */
    let selectedModelQuant = $derived(
        (models.slm[getSafe(config, "refinement.model_id", "qwen8b")] as any)?.quant ?? "",
    );
    let awqCpuConflict = $derived(isCpu && selectedModelQuant === "awq");

    function setDevice(v: string) {
        setSafe("refinement.n_gpu_layers", v === "cpu" ? 0 : -1);
    }
</script>

<div class="flex flex-col gap-[var(--space-3)]">
    <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
        <label
            class="text-[var(--text-sm)] text-[var(--text-primary)]"
            for="setting-refinement"
            data-tip="Uses a local language model to improve grammar and punctuation after transcription."
            >Grammar Refinement</label
        >
        <ToggleSwitch
            checked={getSafe(config, "refinement.enabled", false)}
            onChange={() => setSafe("refinement.enabled", !getSafe(config, "refinement.enabled", false))}
        />
    </div>

    {#if getSafe(config, "refinement.enabled", false)}
        <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
            <label
                class="text-[var(--text-sm)] text-[var(--text-primary)]"
                for="setting-refdevice"
                data-tip="Where the refinement model runs. GPU is faster but requires CUDA. CPU works everywhere but is slower."
                >Refinement Device</label
            >
            <div class="w-full max-w-[460px]">
                <CustomSelect
                    id="setting-refdevice"
                    options={[
                        { value: "gpu", label: "GPU" },
                        { value: "cpu", label: "CPU" },
                    ]}
                    value={deviceValue}
                    onchange={(v: string) => setDevice(v)}
                />
            </div>
        </div>
        {#if isCpu}
            <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
                <label
                    class="text-[var(--text-sm)] text-[var(--text-primary)]"
                    for="setting-refthreads"
                    data-tip="CPU threads for refinement inference. Higher values use more cores but may improve speed. Default: 4."
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
                            label: `${(m as any).name} (${(m as any).size_mb}MB)${(m as any).downloaded ? "" : " ⬇"}${isCpu && (m as any).quant === "awq" ? " — GPU only" : ""}`,
                        }))}
                        value={getSafe(config, "refinement.model_id", "qwen8b")}
                        onchange={(v: string) => setSafe("refinement.model_id", v)}
                        placeholder="Select model…"
                    />
                </div>
                {#if models.slm[getSafe(config, "refinement.model_id", "qwen8b")]}
                    {@const selectedSlm = models.slm[getSafe(config, "refinement.model_id", "qwen8b")] as any}
                    {#if !selectedSlm.downloaded}
                        {#if downloadingModel === getSafe(config, "refinement.model_id", "qwen8b")}
                            <span
                                class="inline-flex items-center gap-1 text-[var(--text-xs)] whitespace-nowrap text-[var(--accent)] shrink overflow-hidden"
                            >
                                <Loader2 size={14} class="spin" />
                                <span class="overflow-hidden text-ellipsis whitespace-nowrap">{downloadMessage}</span>
                            </span>
                        {:else}
                            <DownloadButton
                                onclick={() => handleDownload("slm", getSafe(config, "refinement.model_id", "qwen8b"))}
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
                    >AWQ models require GPU. Switch to an int8 model for CPU inference.</span
                >
            </div>
        {:else if isCpu}
            <div class="flex items-start gap-1 text-[var(--text-xs)] text-[var(--text-secondary)] py-1">
                <Info size={14} class="shrink-0 mt-px" />
                <span class="leading-[var(--leading-normal)]"
                    >Only the 4B model (int8) supports CPU inference. The 8B and 14B are AWQ-quantized and require a GPU.</span
                >
            </div>
        {/if}
        <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
            <label
                class="text-[var(--text-sm)] text-[var(--text-primary)]"
                for="setting-autorefine"
                data-tip="Automatically refines each transcription with the default refinement level immediately after recording."
                >Auto-Refine After Recording</label
            >
            <ToggleSwitch
                checked={getSafe(config, "output.auto_refine", false)}
                onChange={() => setSafe("output.auto_refine", !getSafe(config, "output.auto_refine", false))}
            />
        </div>
        <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
            <label
                class="text-[var(--text-sm)] text-[var(--text-primary)]"
                for="setting-retitle-refine"
                data-tip="Automatically regenerates the transcript title when a refinement is accepted. Uses the refined text for a more accurate title."
                >Auto-Retitle on Refine</label
            >
            <ToggleSwitch
                checked={getSafe(config, "output.auto_retitle_on_refine", true)}
                onChange={() =>
                    setSafe("output.auto_retitle_on_refine", !getSafe(config, "output.auto_retitle_on_refine", true))}
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
                <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
                    <label
                        class="text-[var(--text-sm)] text-[var(--text-primary)]"
                        for="setting-use-thinking"
                        data-tip="Allow the model to reason internally before producing output. Improves quality on complex edits but uses more tokens and is slower. Only effective on reasoning-capable models."
                        >Enable Thinking Mode</label
                    >
                    <ToggleSwitch
                        checked={getSafe(config, "refinement.use_thinking", false)}
                        onChange={() =>
                            setSafe("refinement.use_thinking", !getSafe(config, "refinement.use_thinking", false))}
                    />
                </div>
            </div>
        {/if}
    {/if}
</div>
