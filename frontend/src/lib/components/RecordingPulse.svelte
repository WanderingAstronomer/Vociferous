<script lang="ts">
    /**
     * RecordingPulse — cheap EQ display for active recording.
     *
     * The bars update at roughly 10fps from the latest backend audio level.
     * CSS transitions handle the in-between frames without a JS animation loop.
     */

    interface Props {
        audioLevel?: number;
        /** Legacy prop, ignored — the pulse now fills its container intrinsically. */
        size?: number;
    }

    let { audioLevel = 0 }: Props = $props();

    const barShape = [
        0.18, 0.34, 0.52, 0.74, 0.48, 0.86, 0.62, 0.96, 0.58, 0.82, 0.45, 0.7, 0.36, 0.54, 0.28, 0.42, 0.5,
        0.78, 0.42, 0.66, 0.3, 0.56, 0.24, 0.44,
    ];

    let displayedLevel = $state(0);
    let lastDisplayUpdate = 0;

    $effect(() => {
        const now = performance.now();
        if (now - lastDisplayUpdate >= 100 || Math.abs(audioLevel - displayedLevel) >= 0.18) {
            displayedLevel = Math.max(0, Math.min(1, audioLevel));
            lastDisplayUpdate = now;
        }
    });

    let barHeights = $derived(
        barShape.map((shape, index) => {
            const floor = 10 + ((index * 7) % 8);
            const gain = displayedLevel * (42 + shape * 48);
            return Math.round(Math.min(96, floor + gain));
        }),
    );

    let borderMix = $derived(`${(50 + displayedLevel * 28).toFixed(1)}%`);
    let backgroundMix = $derived(`${(3 + displayedLevel * 10).toFixed(1)}%`);
    let barMix = $derived(`${(64 + displayedLevel * 28).toFixed(1)}%`);
    let eqOpacity = $derived((0.46 + displayedLevel * 0.54).toFixed(3));
    let glowSize = $derived(`${(displayedLevel * 12).toFixed(2)}px`);
    let glowMix = $derived(`${(displayedLevel * 55).toFixed(1)}%`);
    let hintOpacity = $derived((0.62 + displayedLevel * 0.2).toFixed(3));
</script>

<div
    class="recording-display"
    style:--recording-border-mix={borderMix}
    style:--recording-background-mix={backgroundMix}
    style:--recording-bar-mix={barMix}
    style:--recording-eq-opacity={eqOpacity}
    style:--recording-glow-size={glowSize}
    style:--recording-glow-mix={glowMix}
    style:--recording-hint-opacity={hintOpacity}
>
    <div class="eq-wrap" aria-hidden="true">
        {#each barHeights as height, index (index)}
            <span class="eq-bar" style:height="{height}%"></span>
        {/each}
    </div>
    <div class="recording-hint">click to stop recording and transcribe</div>
</div>

<style>
    .recording-display {
        position: relative;
        width: 100%;
        height: 100%;
        display: grid;
        align-items: center;
        justify-content: center;
        color: var(--accent);
        border-radius: var(--radius-xl);
        border: 2px solid color-mix(in srgb, var(--accent) var(--recording-border-mix), var(--shell-border));
        background: color-mix(in srgb, var(--accent) var(--recording-background-mix), var(--surface-secondary));
        box-shadow: none;
        transition: background 120ms linear, border-color 120ms linear;
    }

    .eq-wrap {
        width: min(88%, 940px);
        height: clamp(48px, 54%, 124px);
        display: grid;
        grid-template-columns: repeat(24, minmax(4px, 1fr));
        align-items: center;
        gap: clamp(5px, 1vw, 12px);
        opacity: var(--recording-eq-opacity);
    }

    .eq-bar {
        display: block;
        min-height: 10px;
        max-height: 100%;
        border-radius: 999px;
        background: color-mix(in srgb, var(--accent) var(--recording-bar-mix), white 8%);
        box-shadow: 0 0 var(--recording-glow-size)
            color-mix(in srgb, var(--accent) var(--recording-glow-mix), transparent);
        transition: height 100ms linear, opacity 100ms linear;
        will-change: height;
    }

    .recording-hint {
        position: absolute;
        bottom: 16px;
        left: 50%;
        transform: translateX(-50%);
        color: var(--text-tertiary);
        font-size: 12px;
        font-style: italic;
        letter-spacing: 0;
        white-space: nowrap;
        opacity: var(--recording-hint-opacity);
    }
</style>
