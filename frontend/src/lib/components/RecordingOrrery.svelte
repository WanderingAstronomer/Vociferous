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

    /* ── Amorphous blob ring geometry ── */
    const BLOB_N = 10; // control points around the circle
    const BLOB_BASE = 54; // base radius in SVG viewBox units (mic circle ≈ 50)
    const BLOB_DEFORM = 3.5; // max ± random deformation per point
    const BLOB_LERP = 0.07; // interpolation speed per frame (~60fps)
    const RETARGET_MS = 280; // new random targets every N ms while speaking

    let blobRadii: number[] = Array.from({ length: BLOB_N }, () => BLOB_BASE);
    let blobTargets: number[] = Array.from({ length: BLOB_N }, () => BLOB_BASE);
    let lastRetarget = 0;
    let blobPathEl: SVGPathElement | undefined = $state();

    function computeBlobPath(radii: number[]): string {
        const n = radii.length;
        const pts: [number, number][] = radii.map((r, i) => {
            const a = (i / n) * Math.PI * 2 - Math.PI / 2; // start from top
            return [50 + Math.cos(a) * r, 50 + Math.sin(a) * r];
        });
        // Catmull-Rom → cubic bezier control points
        const segs: string[] = [`M${pts[0][0].toFixed(2)},${pts[0][1].toFixed(2)}`];
        for (let i = 0; i < n; i++) {
            const p = pts[(i - 1 + n) % n];
            const c = pts[i];
            const nx = pts[(i + 1) % n];
            const nx2 = pts[(i + 2) % n];
            const cp1x = c[0] + (nx[0] - p[0]) / 6;
            const cp1y = c[1] + (nx[1] - p[1]) / 6;
            const cp2x = nx[0] - (nx2[0] - c[0]) / 6;
            const cp2y = nx[1] - (nx2[1] - c[1]) / 6;
            segs.push(
                `C${cp1x.toFixed(2)},${cp1y.toFixed(2)} ${cp2x.toFixed(2)},${cp2y.toFixed(2)} ${nx[0].toFixed(2)},${nx[1].toFixed(2)}`,
            );
        }
        return segs.join("");
    }

    function retargetBlob() {
        for (let i = 0; i < BLOB_N; i++) {
            blobTargets[i] = BLOB_BASE + (Math.random() - 0.5) * 2 * BLOB_DEFORM;
        }
    }

    function tickBlob(now: number, isSpeaking: boolean) {
        if (isSpeaking && now - lastRetarget > RETARGET_MS) {
            retargetBlob();
            lastRetarget = now;
        } else if (!isSpeaking) {
            for (let i = 0; i < BLOB_N; i++) blobTargets[i] = BLOB_BASE;
        }
        let changed = false;
        for (let i = 0; i < BLOB_N; i++) {
            const diff = blobTargets[i] - blobRadii[i];
            if (Math.abs(diff) > 0.01) {
                blobRadii[i] += diff * BLOB_LERP;
                changed = true;
            }
        }
        if (changed) {
            blobPathEl?.setAttribute("d", computeBlobPath(blobRadii));
        }
    }

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
        const now = performance.now();
        const al = audioLevel;
        smooth += (al - smooth) * 0.25;
        if (Math.abs(smooth - al) < 0.001) smooth = al;

        // Outer glow: scale + opacity — increased radiance range
        const s = 0.85 + smooth * 0.8;
        const o = Math.min(1, 0.4 + smooth * 0.8);
        glowEl!.style.transform = `translate3d(-50%, -50%, 0) scale(${s.toFixed(3)})`;
        glowEl!.style.opacity = o.toFixed(3);

        // Mic button: dynamic box-shadow — brighter radiance on voice
        const spread = (8 + smooth * 36).toFixed(1);
        const outerA = (0.16 + smooth * 0.55).toFixed(3);
        const innerA = (0.08 + smooth * 0.2).toFixed(3);
        micBtnEl!.style.boxShadow = `0 0 ${spread}px rgba(255, 160, 60, ${outerA}), inset 0 0 16px rgba(255, 183, 51, ${innerA})`;

        // Blob opacity reacts to voice level
        if (blobPathEl) blobPathEl.style.opacity = (0.45 + smooth * 0.5).toFixed(3);

        // Toggle speaking class (only on actual state change)
        const nowSpeaking = smooth > 0.01;
        if (nowSpeaking !== speaking) speaking = nowSpeaking;

        // Tick blob deformation
        tickBlob(now, nowSpeaking);

        if (smooth > 0.001 || al > 0.001) {
            glowRaf = requestAnimationFrame(glowTick);
        } else {
            glowRaf = undefined;
            if (speaking) speaking = false;
            // Clear inline styles so CSS idle animations take over
            micBtnEl!.style.boxShadow = "";
            glowEl!.style.transform = "";
            glowEl!.style.opacity = "";
            if (blobPathEl) blobPathEl.style.opacity = "";
            // Final blob tick to settle back to circle
            tickBlob(now, false);
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

    /* ── Initial blob path (perfect circle) ── */
    const initialBlobPath = computeBlobPath(blobRadii);
</script>

<div class="recording-display" bind:this={containerEl}>
    <div class="mic-center" style="width: {micSizePx}px; height: {micSizePx}px;">
        <div class="mic-glow" class:speaking bind:this={glowEl}></div>
        <!-- Amorphous blob ring (replaces static border + sonar ripples) -->
        <svg class="blob-svg" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
            <path bind:this={blobPathEl} d={initialBlobPath} class="blob-path" class:speaking />
        </svg>
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

    /* ── Mic button ── */
    .mic-button {
        position: absolute;
        inset: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        color: var(--orange-4);
        border-radius: 50%;
        background-color: var(--surface-primary, #181825);
        border: 2px solid transparent; /* layout preservation; blob is the visual ring */
        box-shadow:
            0 0 20px rgba(255, 160, 60, 0.14),
            inset 0 0 16px rgba(255, 183, 51, 0.06);
        transform: translateZ(0);
    }

    /* Breathing glow overlay — GPU-composited opacity animation (ISS-071) */
    .mic-button::after {
        content: "";
        position: absolute;
        inset: -2px;
        border-radius: 50%;
        box-shadow:
            0 0 30px rgba(255, 160, 60, 0.24),
            inset 0 0 16px rgba(255, 183, 51, 0.12);
        opacity: 0;
        will-change: opacity;
        animation: button-breathe 4s ease-in-out infinite;
        pointer-events: none;
    }

    .mic-button.speaking::after {
        animation: none;
        opacity: 0;
    }

    @keyframes button-breathe {
        0%,
        100% {
            opacity: 0;
        }
        50% {
            opacity: 1;
        }
    }

    /* ── Outer ambient glow ── */
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

    /* ── Amorphous blob ring ── */
    .blob-svg {
        position: absolute;
        inset: 0;
        overflow: visible;
        pointer-events: none;
        filter: drop-shadow(0 0 4px rgba(255, 183, 51, 0.2));
    }

    .blob-path {
        fill: none;
        stroke: var(--orange-4);
        stroke-width: 1.5;
        stroke-linecap: round;
        stroke-linejoin: round;
        opacity: 0.5;
        will-change: opacity;
        animation: blob-breathe 4s ease-in-out infinite;
    }

    .blob-path.speaking {
        animation: none;
    }

    @keyframes blob-breathe {
        0%,
        100% {
            opacity: 0.35;
        }
        50% {
            opacity: 0.65;
        }
    }
</style>
