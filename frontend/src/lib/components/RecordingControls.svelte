<script lang="ts">
    /**
     * RecordingControls — Horizontal mic surface for starting/stopping recording.
     *
     * This is the visible surface; it should not be nested inside another faux
     * recording panel.
     */

    import { Mic } from "lucide-svelte";
    import RecordingPulse from "./RecordingPulse.svelte";

    interface Props {
        isRecording: boolean;
        audioLevel: number;
        onstart: () => void;
        onstop: () => void;
    }

    let { isRecording, audioLevel, onstart, onstop }: Props = $props();

    const idleClasses =
        "border-[var(--accent)] bg-[color-mix(in_srgb,var(--accent)_6%,var(--surface-secondary))] text-[var(--accent)] shadow-[0_0_18px_rgba(90,159,212,0.10)] hover:border-[var(--accent-hover)] hover:bg-[color-mix(in_srgb,var(--accent)_11%,var(--surface-secondary))] hover:text-[var(--accent-hover)]";
    const recordingClasses =
        "border-transparent bg-transparent text-[var(--orange-4)] shadow-[0_0_36px_rgba(255,160,60,0.34)]";
</script>

<button
    class="grid h-full min-h-[156px] max-h-[320px] w-full shrink-0 place-items-center overflow-hidden rounded-[var(--radius-xl)] border p-0 cursor-pointer transition-[background,border-color,color,box-shadow,transform] duration-200 ease-out focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] active:scale-[0.995] {isRecording
        ? recordingClasses
        : idleClasses}"
    onclick={isRecording ? onstop : onstart}
    aria-label={isRecording ? "Stop recording" : "Start recording"}
    title={isRecording ? "Stop recording and transcribe" : "Start recording"}
>
    {#if isRecording}
        <RecordingPulse {audioLevel} />
    {:else}
        <Mic size={44} strokeWidth={1.45} />
    {/if}
</button>
