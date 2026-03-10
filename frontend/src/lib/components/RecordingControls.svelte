<script lang="ts">
    /**
     * RecordingControls — Mic button and recording orrery visualizer.
     *
     * Extracted from TranscribeView to reduce its line count. This component owns
     * the visual recording controls but delegates state transitions to the parent
     * via callbacks and bound props. The recording status bar lives in TranscribeView.
     */

    import { Mic } from "lucide-svelte";
    import RecordingOrrery from "./RecordingOrrery.svelte";

    interface Props {
        /** Whether a recording is currently active. */
        isRecording: boolean;
        /** Current audio level (0–1) for the orrery visualizer. */
        audioLevel: number;
        /** Called when the user clicks the idle mic button. */
        onstart: () => void;
        /** Called when the user clicks the orrery (stop recording). */
        onstop: () => void;
    }

    let { isRecording, audioLevel, onstart, onstop }: Props = $props();
</script>

<!-- Mic / Orrery button -->
<div class="flex flex-col items-center justify-center gap-[var(--space-4)]">
    {#if isRecording}
        <button
            class="w-[160px] h-[160px] rounded-full cursor-pointer p-0 bg-transparent border-none focus:outline-none"
            onclick={onstop}
            aria-label="Stop recording"
            title="Stop recording and transcribe"
        >
            <RecordingOrrery {audioLevel} size={160} />
        </button>
    {:else}
        <button
            class="w-[160px] h-[160px] rounded-full border-2 border-[var(--accent)] bg-transparent text-[var(--accent)] cursor-pointer flex items-center justify-center transition-[background,border-color,color] duration-[var(--transition-fast)] hover:bg-[var(--hover-overlay-blue)] hover:border-[var(--accent-hover)] hover:text-[var(--accent-hover)]"
            onclick={onstart}
            aria-label="Start recording"
            title="Start recording"
        >
            <Mic size={56} strokeWidth={1.5} />
        </button>
        <p class="text-[var(--text-base)] text-[var(--text-tertiary)] m-0">Click to record</p>
    {/if}
</div>
