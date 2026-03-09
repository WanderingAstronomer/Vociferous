<script lang="ts">
    /**
     * OutputCard — Output toggles + SLM refinement settings.
     *
     * Manages: trailing space, auto-copy, auto-retitle, grammar refinement,
     * SLM model selection + download, GPU layers, context size.
     */

    import { Sliders, Loader2, CheckCircle, AlertCircle } from "lucide-svelte";
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
</script>

<div class="flex flex-col gap-[var(--space-3)]">
    <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
        <label
            class="text-[var(--text-sm)] text-[var(--text-primary)]"
            for="setting-trailing"
            title="Appends a space after each transcription for seamless dictation into text fields."
            >Add Trailing Space</label
        >
        <ToggleSwitch
            checked={getSafe(config, "output.add_trailing_space", false)}
            onChange={() => setSafe("output.add_trailing_space", !getSafe(config, "output.add_trailing_space", false))}
        />
    </div>
    <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
        <label
            class="text-[var(--text-sm)] text-[var(--text-primary)]"
            for="setting-autocopy"
            title="Automatically copies transcription to clipboard when complete. Works even when the window is not focused."
            >Auto-Copy to Clipboard</label
        >
        <ToggleSwitch
            checked={getSafe(config, "output.auto_copy_to_clipboard", true)}
            onChange={() =>
                setSafe("output.auto_copy_to_clipboard", !getSafe(config, "output.auto_copy_to_clipboard", true))}
        />
    </div>
    <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
        <label
            class="text-[var(--text-sm)] text-[var(--text-primary)]"
            for="setting-retitle-refine"
            title="Automatically regenerates the transcript title when a refinement is accepted. Uses the refined text for a more accurate title."
            >Auto-Retitle on Refine</label
        >
        <ToggleSwitch
            checked={getSafe(config, "output.auto_retitle_on_refine", true)}
            onChange={() =>
                setSafe("output.auto_retitle_on_refine", !getSafe(config, "output.auto_retitle_on_refine", true))}
        />
    </div>
    <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
        <label
            class="text-[var(--text-sm)] text-[var(--text-primary)]"
            for="setting-refinement"
            title="Uses a local language model to improve grammar and punctuation after transcription."
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
                for="setting-refmodel"
                title="Larger models produce better refinements but use more RAM and are slower."
                >Refinement Model</label
            >
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
                    {@const selectedSlm = models.slm[getSafe(config, "refinement.model_id", "qwen4b")] as any}
                    {#if !selectedSlm.downloaded}
                        {#if downloadingModel === getSafe(config, "refinement.model_id", "qwen4b")}
                            <span
                                class="inline-flex items-center gap-1 text-[var(--text-xs)] whitespace-nowrap text-[var(--accent)] shrink overflow-hidden"
                            >
                                <Loader2 size={14} class="spin" />
                                <span class="overflow-hidden text-ellipsis whitespace-nowrap">{downloadMessage}</span>
                            </span>
                        {:else}
                            <DownloadButton
                                onclick={() => handleDownload("slm", getSafe(config, "refinement.model_id", "qwen4b"))}
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
        <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
            <label
                class="text-[var(--text-sm)] text-[var(--text-primary)]"
                for="setting-gpu-layers"
                title="Layers to offload to GPU. -1 = all (fastest), 0 = CPU only. Requires CUDA-compiled CTranslate2."
                >GPU Layers</label
            >
            <input
                id="setting-gpu-layers"
                class="h-9 w-24 rounded-[var(--radius-md)] border border-[var(--shell-border)] bg-[var(--surface-primary)] px-[var(--space-2)] text-[var(--text-sm)] text-[var(--text-primary)] [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
                type="number"
                min="-1"
                max="999"
                value={getSafe(config, "refinement.n_gpu_layers", -1)}
                oninput={(e) => {
                    const v = parseInt((e.target as HTMLInputElement).value);
                    if (!isNaN(v) && v >= -1) setSafe("refinement.n_gpu_layers", v);
                }}
            />
        </div>
    {/if}
</div>
