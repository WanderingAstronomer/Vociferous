<script lang="ts">
    /**
     * RecordingPulse — Fills the record button with a horizontal pulse treatment.
     *
     * Sizing is intrinsic: `width: 100%; height: 100%`. The mic icon scales with
     * the button's smaller dimension. Glow intensity and border vividness track
     * the smoothed audio level.
     */

    import { Mic } from "lucide-svelte";

    interface Props {
        audioLevel?: number;
        /** Legacy prop, ignored — the pulse now fills its container intrinsically. */
        size?: number;
    }

    let { audioLevel = 0 }: Props = $props();

    let containerEl: HTMLDivElement | undefined = $state();
    let micIconSize = $state(30);

    $effect(() => {
        if (!containerEl) return;
        const ro = new ResizeObserver(([e]) => {
            const side = Math.min(e.contentRect.width, e.contentRect.height);
            micIconSize = Math.max(26, Math.min(34, Math.round(side * 0.48)));
        });
        ro.observe(containerEl);
        return () => ro.disconnect();
    });

    /* ── Audio-reactive smoothing (low-pass on raw audioLevel) ── */
    let smooth = $state(0);
    let rafId: number | undefined;

    function tick() {
        smooth += (audioLevel - smooth) * 0.25;
        if (Math.abs(smooth - audioLevel) < 0.001) smooth = audioLevel;
        if (smooth > 0.001 || audioLevel > 0.001) {
            rafId = requestAnimationFrame(tick);
        } else {
            rafId = undefined;
        }
    }

    $effect(() => {
        if (audioLevel > 0.001 && rafId === undefined) {
            rafId = requestAnimationFrame(tick);
        }
    });

    $effect(() => () => {
        if (rafId !== undefined) {
            cancelAnimationFrame(rafId);
            rafId = undefined;
        }
    });

    let speaking = $derived(smooth > 0.05);
</script>

<div bind:this={containerEl} class="recording-display" class:speaking style:--recording-intensity={smooth.toFixed(3)}>
    <Mic class="recording-mic" size={micIconSize} strokeWidth={1.5} />
</div>

<style>
    .recording-display {
        position: relative;
        width: 100%;
        height: 100%;
        display: flex;
        align-items: center;
        justify-content: center;
        color: var(--orange-4);
        border-radius: var(--radius-xl);
        border: 2px solid var(--orange-4);
        box-shadow:
            0 0 calc(14px + var(--recording-intensity, 0) * 28px)
                rgba(255, 160, 60, calc(0.2 + var(--recording-intensity, 0) * 0.48)),
            inset 0 0 calc(12px + var(--recording-intensity, 0) * 22px)
                rgba(255, 183, 51, calc(0.06 + var(--recording-intensity, 0) * 0.18));
        transition: box-shadow 120ms ease-out;
        animation: recording-breathe 4s ease-in-out infinite;
        will-change: box-shadow, border-color;
    }

    /* When speaking, freeze the idle breath and let the reactive box-shadow drive. */
    .recording-display.speaking {
        animation: none;
    }

    @keyframes recording-breathe {
        0%,
        100% {
            border-color: var(--orange-4);
            box-shadow:
                0 0 14px rgba(255, 160, 60, 0.2),
                inset 0 0 12px rgba(255, 183, 51, 0.06);
        }
        50% {
            border-color: rgba(255, 183, 51, 0.65);
            box-shadow:
                0 0 24px rgba(255, 160, 60, 0.32),
                inset 0 0 20px rgba(255, 183, 51, 0.14);
        }
    }

    :global(.recording-mic) {
        display: block;
        filter: drop-shadow(0 0 8px rgba(255, 183, 51, 0.55));
    }
</style>
