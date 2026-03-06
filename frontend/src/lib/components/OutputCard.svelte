<script lang="ts">
    /**
     * OutputCard — Output toggles + SLM refinement settings.
     *
     * Manages: trailing space, auto-copy, auto-retitle, grammar refinement,
     * SLM model selection + download, GPU layers, context size.
     */

    import { Sliders, Loader2, Download, CheckCircle, AlertCircle } from "lucide-svelte";
    import ToggleSwitch from "./ToggleSwitch.svelte";
    import CustomSelect from "./CustomSelect.svelte";

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
</script>

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
                for="setting-retitle-refine">Auto-Retitle on Refine</label
            >
            <div class="flex flex-col gap-1 flex-1">
                <ToggleSwitch
                    checked={getSafe(config, "output.auto_retitle_on_refine", true)}
                    onChange={() =>
                        setSafe(
                            "output.auto_retitle_on_refine",
                            !getSafe(config, "output.auto_retitle_on_refine", true),
                        )}
                />
                <span class="text-[var(--text-xs)] text-[var(--text-tertiary)] italic"
                    >Automatically regenerates the transcript title when a refinement completes.
                    Uses the refined text for a more accurate title.</span
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
