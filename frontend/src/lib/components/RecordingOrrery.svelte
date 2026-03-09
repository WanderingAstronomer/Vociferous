<script lang="ts">
    import { Mic } from "lucide-svelte";

    interface Props {
        audioLevel?: number;
        size?: number; // Fixed size override — skips ResizeObserver when provided
    }

    let { audioLevel = 0, size = undefined }: Props = $props();

    /* ── Mic sizing: fixed when size prop is set, responsive otherwise ── */
    let containerEl: HTMLDivElement | undefined = $state();
    let micSizePx = $state(96);

    $effect(() => {
        if (size !== undefined) {
            micSizePx = size;
            return;
        }
        if (!containerEl) return;
        const ro = new ResizeObserver(([e]) => {
            const side = Math.min(e.contentRect.width, e.contentRect.height);
            micSizePx = Math.max(64, Math.min(140, side * 0.2));
        });
        ro.observe(containerEl);
        return () => ro.disconnect();
    });

    /* ── Icon size scales with mic circle (35% of diameter, matching idle button) ── */
    let micIconSizePx = $derived(Math.max(28, Math.round(micSizePx * 0.35)));

    /* ── Audio-reactive glow + dynamic button ── */
    let glowEl: HTMLDivElement | undefined = $state();
    let micBtnEl: HTMLDivElement | undefined = $state();
    let glowRaf: number | undefined;
    let smooth = 0;
    let speaking = $state(false);

    function glowTick() {
        if (document.hidden) {
            glowRaf = undefined;
            return;
        }
        const al = audioLevel;
        smooth += (al - smooth) * 0.25;
        if (Math.abs(smooth - al) < 0.001) smooth = al;

        // Outer glow: scale + opacity
        const s = 0.85 + smooth * 0.6;
        const o = 0.4 + smooth * 0.6;
        glowEl!.style.transform = `translate3d(-50%, -50%, 0) scale(${s.toFixed(3)})`;
        glowEl!.style.opacity = o.toFixed(3);

        // Mic button: dynamic box-shadow that brightens with voice
        const spread = (8 + smooth * 24).toFixed(1);
        const outerA = (0.16 + smooth * 0.4).toFixed(3);
        const innerA = (0.08 + smooth * 0.15).toFixed(3);
        micBtnEl!.style.boxShadow = `0 0 ${spread}px rgba(255, 160, 60, ${outerA}), inset 0 0 16px rgba(255, 183, 51, ${innerA})`;

        // Toggle speaking class (only on actual state change)
        const nowSpeaking = smooth > 0.01;
        if (nowSpeaking !== speaking) speaking = nowSpeaking;

        if (smooth > 0.001 || al > 0.001) {
            glowRaf = requestAnimationFrame(glowTick);
        } else {
            glowRaf = undefined;
            if (speaking) speaking = false;
            // Clear inline styles so CSS idle animations take over
            micBtnEl!.style.boxShadow = "";
            glowEl!.style.transform = "";
            glowEl!.style.opacity = "";
        }
    }

    $effect(() => {
        if (audioLevel > 0.001 && glowRaf === undefined && glowEl) {
            glowRaf = requestAnimationFrame(glowTick);
        }
    });

    $effect(() => {
        void glowEl;
        return () => {
            if (glowRaf !== undefined) {
                cancelAnimationFrame(glowRaf);
                glowRaf = undefined;
            }
        };
    });
</script>

<div class="recording-display" bind:this={containerEl}>
    <div class="mic-center" style="width: {micSizePx}px; height: {micSizePx}px;">
        <div class="mic-glow" class:speaking bind:this={glowEl}></div>
        <div class="ripple-ring" class:active={speaking}></div>
        <div class="ripple-ring staggered" class:active={speaking}></div>
        <div class="mic-button" class:speaking bind:this={micBtnEl}>
            <Mic size={micIconSizePx} strokeWidth={1.5} />
        </div>
    </div>
</div>

<style>
    .recording-display {
        position: relative;
        width: 100%;
        height: 100%;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .mic-center {
        position: relative;
    }

    /* ── Mic button with idle breathing ── */
    .mic-button {
        position: absolute;
        inset: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        color: var(--orange-4);
        border-radius: 50%;
        background-color: var(--surface-primary, #181825);
        border: 2px solid color-mix(in srgb, var(--orange-4) 70%, transparent);
        box-shadow:
            0 0 24px rgba(255, 160, 60, 0.16),
            inset 0 0 16px rgba(255, 183, 51, 0.08);
        animation: button-breathe 4s ease-in-out infinite;
    }

    .mic-button.speaking {
        animation: none;
    }

    @keyframes button-breathe {
        0%,
        100% {
            box-shadow:
                0 0 20px rgba(255, 160, 60, 0.14),
                inset 0 0 16px rgba(255, 183, 51, 0.06);
        }
        50% {
            box-shadow:
                0 0 30px rgba(255, 160, 60, 0.24),
                inset 0 0 16px rgba(255, 183, 51, 0.12);
        }
    }

    /* ── Outer ambient glow with idle breathing ── */
    .mic-glow {
        position: absolute;
        top: 50%;
        left: 50%;
        width: 260%;
        height: 260%;
        border-radius: 50%;
        background: radial-gradient(
            circle,
            rgba(255, 183, 51, 0.22) 0%,
            rgba(255, 183, 51, 0.06) 45%,
            rgba(255, 183, 51, 0) 70%
        );
        pointer-events: none;
        will-change: transform, opacity;
        transform: translate3d(-50%, -50%, 0) scale(0.85);
        opacity: 0.4;
        animation: glow-breathe 4s ease-in-out infinite;
    }

    .mic-glow.speaking {
        animation: none;
    }

    @keyframes glow-breathe {
        0%,
        100% {
            transform: translate3d(-50%, -50%, 0) scale(0.85);
            opacity: 0.3;
        }
        50% {
            transform: translate3d(-50%, -50%, 0) scale(0.95);
            opacity: 0.5;
        }
    }

    /* ── Sonar ripple rings (active when speaking) ── */
    .ripple-ring {
        position: absolute;
        top: 50%;
        left: 50%;
        width: 100%;
        height: 100%;
        border-radius: 50%;
        border: 1.5px solid rgba(255, 183, 51, 0.35);
        transform: translate(-50%, -50%) scale(1);
        opacity: 0;
        pointer-events: none;
    }

    .ripple-ring.active {
        animation: ripple-expand 4.5s ease-out infinite;
    }

    .ripple-ring.staggered.active {
        animation-delay: 2.25s;
    }

    @keyframes ripple-expand {
        0% {
            transform: translate(-50%, -50%) scale(1);
            opacity: 0.35;
        }
        100% {
            transform: translate(-50%, -50%) scale(3.2);
            opacity: 0;
        }
    }
</style>
