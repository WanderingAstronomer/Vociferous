<script lang="ts">
    /**
     * RecordingControls — Single button that IS the visual surface.
     *
     * Click target equals the visual rounded-rect (no oversized invisible wrapper).
     * Idle and recording share the same rounded-rect at 60% of the parent's width
     * and height so the surface doesn't shift when you click record. The label
     * "Click to record" is gone — the hover tooltip carries the affordance.
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

    let btnEl: HTMLButtonElement | undefined = $state();
    let micIconSize = $state(80);

    $effect(() => {
        if (!btnEl) return;
        const ro = new ResizeObserver(([e]) => {
            const side = Math.min(e.contentRect.width, e.contentRect.height);
            micIconSize = Math.max(56, Math.min(180, Math.round(side * 0.35)));
        });
        ro.observe(btnEl);
        return () => ro.disconnect();
    });
</script>

<button
    bind:this={btnEl}
    class="w-3/5 h-3/5 shrink-0 p-0 border-none bg-transparent cursor-pointer rounded-[var(--radius-lg)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
    onclick={isRecording ? onstop : onstart}
    aria-label={isRecording ? "Stop recording" : "Start recording"}
    title={isRecording ? "Stop recording and transcribe" : "Start recording"}
>
    {#if isRecording}
        <RecordingPulse {audioLevel} />
    {:else}
        <div
            class="flex items-center justify-center w-full h-full rounded-[var(--radius-lg)] border-2 border-[var(--accent)] text-[var(--accent)] transition-colors duration-300 hover:bg-[var(--hover-overlay-blue)] hover:border-[var(--accent-hover)] hover:text-[var(--accent-hover)]"
        >
            <Mic size={micIconSize} strokeWidth={1.5} />
        </div>
    {/if}
</button>
