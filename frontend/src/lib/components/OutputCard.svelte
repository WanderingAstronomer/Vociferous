<script lang="ts">
    /**
     * OutputCard — Output behavior toggles.
     *
     * Manages: trailing space, auto-copy.
     */

    import ToggleSwitch from "./ToggleSwitch.svelte";
    import type { GetConfigValue, SetConfigValue, VociferousConfig } from "../config.svelte";

    interface Props {
        config: VociferousConfig;
        getSafe: GetConfigValue;
        setSafe: SetConfigValue;
    }

    let { config, getSafe, setSafe }: Props = $props();
</script>

<div class="flex flex-col gap-[var(--space-3)]">
    <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
        <label
            id="setting-trailing-label"
            class="text-[var(--text-sm)] text-[var(--text-primary)]"
            for="setting-trailing"
            data-tip="Appends a space after each transcription for seamless dictation into text fields."
            >Add Trailing Space</label
        >
        <ToggleSwitch
            id="setting-trailing"
            ariaLabelledby="setting-trailing-label"
            bind:checked={
                () => getSafe(config, "output.add_trailing_space", false),
                (checked: boolean) => setSafe("output.add_trailing_space", checked)
            }
        />
    </div>
    <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
        <label
            id="setting-autocopy-label"
            class="text-[var(--text-sm)] text-[var(--text-primary)]"
            for="setting-autocopy"
            data-tip="Automatically copies transcription to clipboard when complete. Works even when the window is not focused."
            >Auto-Copy to Clipboard</label
        >
        <ToggleSwitch
            id="setting-autocopy"
            ariaLabelledby="setting-autocopy-label"
            bind:checked={
                () => getSafe(config, "output.auto_copy_to_clipboard", true),
                (checked: boolean) => setSafe("output.auto_copy_to_clipboard", checked)
            }
        />
    </div>
</div>
