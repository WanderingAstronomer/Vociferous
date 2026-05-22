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
        border: 3px solid var(--orange-4);
        background: rgba(255, 128, 32, calc(0.05 + var(--recording-intensity, 0) * 0.08));
        box-shadow:
            0 0 0 calc(5px + var(--recording-intensity, 0) * 11px)
                rgba(255, 196, 88, calc(0.18 + var(--recording-intensity, 0) * 0.2)),
            0 0 calc(34px + var(--recording-intensity, 0) * 76px)
                rgba(255, 160, 60, calc(0.42 + var(--recording-intensity, 0) * 0.46)),
            0 0 calc(86px + var(--recording-intensity, 0) * 116px)
                rgba(255, 96, 40, calc(0.2 + var(--recording-intensity, 0) * 0.3));
        transition: background 120ms ease-out, box-shadow 120ms ease-out;
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
                0 0 0 5px rgba(255, 196, 88, 0.18),
                0 0 34px rgba(255, 160, 60, 0.42),
                0 0 86px rgba(255, 96, 40, 0.2);
        }
        50% {
            border-color: rgba(255, 210, 96, 0.92);
            box-shadow:
                0 0 0 14px rgba(255, 196, 88, 0.28),
                0 0 64px rgba(255, 160, 60, 0.7),
                0 0 126px rgba(255, 96, 40, 0.36);
        }
    }

    :global(.recording-mic) {
        display: block;
        filter: drop-shadow(0 0 14px rgba(255, 210, 96, 0.86));
    }
</style>
