<script lang="ts">
    import { onMount, onDestroy } from "svelte";

    interface Props {
        /** Number of display bars */
        numBars?: number;
        /** Gap between bars in px */
        barGap?: number;
        /** Visual intensity multiplier */
        intensity?: number;
        /** Neighbor-spread smoothing factor (higher = less spread) */
        spreadFactor?: number;
        /** Legacy alias for spreadFactor; kept for backward compatibility */
        monstercat?: number;
        /** Noise reduction / temporal memory (0-1) */
        noiseReduction?: number;
        /** Peak hold duration in ms */
        peakHoldMs?: number;
        /** Peak fall rate per frame */
        peakFallRate?: number;
        /** Whether the visualizer is active */
        active?: boolean;
        /** Voice calibration frequency mean (0-1 normalized) */
        freqMean?: number;
        /** Voice calibration frequency std (0-1 normalized) */
        freqStd?: number;
        /** Filter profile: classic spread or Vociferous fast-math */
        shape?: "classic" | "vociferous";
    }

    let {
        numBars = 64,
        barGap = 2,
        intensity = 1.0,
        spreadFactor,
        monstercat,
        noiseReduction = 0.85,
        peakHoldMs = 800,
        peakFallRate = 0.015,
        active = false,
        freqMean = 0.35,
        freqStd = 0.2,
        shape = "classic",
    }: Props = $props();

    let canvas: HTMLCanvasElement;
    let ctx: CanvasRenderingContext2D | null = null;
    let animFrameId: number | null = null;

    const SPREAD_NEIGHBORS = 10;
    const VO_KERNEL = [0.08, 0.22, 0.4, 0.22, 0.08] as const;
    const VO_DRIVE = 1.9;
    const VO_DIRECTIONAL_GAIN = 0.06;
    const VO_DENOM = Math.tanh(VO_DRIVE);

    let spectrum = $state(new Float32Array(0));
    let prevSpectrum = new Float32Array(0);
    let inputSpectrum = new Float32Array(0);
    let cavaMem = new Float32Array(0);
    let cavaFall = new Float32Array(0);
    let peaks = new Float32Array(0);
    let peakTimes = new Float64Array(0);
    let emphasisWeights = new Float32Array(0);

    let rawBuffer = new Float32Array(0);
    let spreadBuffer = new Float32Array(0);
    let spreadAttenuation = new Float32Array(SPREAD_NEIGHBORS + 1);

    let lastUpdateTime = 0;
    let lastDrawTime = 0;
    const FRAME_INTERVAL = 33.33; // ~30fps cap

    /* ===== Colors (from design tokens) ===== */
    const BLUE_9 = "#1a252e";
    const BLUE_6 = "#3d4f5f";
    const BLUE_3 = "#6db3e8";
    const BLUE_4 = "#5a9fd4";

    let cachedGradient: CanvasGradient | null = null;
    let cachedGradientHeight = 0;

    function reinitializeBuffers(): void {
        spectrum = new Float32Array(numBars);
        prevSpectrum = new Float32Array(numBars);
        inputSpectrum = new Float32Array(numBars);
        cavaMem = new Float32Array(numBars);
        cavaFall = new Float32Array(numBars);
        peaks = new Float32Array(numBars);
        peakTimes = new Float64Array(numBars);
        emphasisWeights = new Float32Array(numBars);
        rawBuffer = new Float32Array(numBars);
        spreadBuffer = new Float32Array(numBars);
    }

    function effectiveSpreadFactor(): number {
        if (spreadFactor !== undefined) return spreadFactor;
        if (monstercat !== undefined) return monstercat;
        return 1.5;
    }

    function recomputeSpreadAttenuation(): void {
        spreadAttenuation[0] = 1;
        const spread = effectiveSpreadFactor();
        if (spread <= 0) {
            for (let j = 1; j <= SPREAD_NEIGHBORS; j++) spreadAttenuation[j] = 0;
            return;
        }

        for (let j = 1; j <= SPREAD_NEIGHBORS; j++) {
            spreadAttenuation[j] = 1 / (spread * j * 1.5);
        }
    }

    function computeEmphasisWeights(): void {
        const center = freqMean * numBars;
        const sigma = Math.max(freqStd * numBars, 1);
        for (let i = 0; i < numBars; i++) {
            const z = (i - center) / sigma;
            emphasisWeights[i] = Math.max(0.5, Math.min(1.0, Math.exp(-0.5 * z * z)));
        }
    }

    function applySpreadFilter(source: Float32Array, target: Float32Array): void {
        target.set(source);
        for (let i = 0; i < source.length; i++) {
            const current = source[i];
            for (let j = 1; j <= SPREAD_NEIGHBORS; j++) {
                const attenuated = current * spreadAttenuation[j];
                if (attenuated <= 0) break;
                const left = i - j;
                const right = i + j;
                if (left >= 0 && attenuated > target[left]) target[left] = attenuated;
                if (right < source.length && attenuated > target[right]) target[right] = attenuated;
            }
        }
    }

    function applyVociferousFilter(source: Float32Array, target: Float32Array): void {
        const n = source.length;
        if (n === 0) return;

        for (let i = 0; i < n; i++) {
            const i0 = i > 1 ? i - 2 : 0;
            const i1 = i > 0 ? i - 1 : 0;
            const i2 = i;
            const i3 = i + 1 < n ? i + 1 : n - 1;
            const i4 = i + 2 < n ? i + 2 : n - 1;

            const linear =
                source[i0] * VO_KERNEL[0] +
                source[i1] * VO_KERNEL[1] +
                source[i2] * VO_KERNEL[2] +
                source[i3] * VO_KERNEL[3] +
                source[i4] * VO_KERNEL[4];

            target[i] = Math.tanh(linear * VO_DRIVE) / VO_DENOM;
        }

        for (let i = 1; i < n - 1; i++) {
            const slope = target[i + 1] - target[i - 1];
            const shaped = target[i] + slope * VO_DIRECTIONAL_GAIN;
            target[i] = Math.max(0, Math.min(1, shaped));
        }
    }

    function resampleInto(source: number[], target: Float32Array): void {
        if (source.length === 0) {
            target.fill(0);
            return;
        }

        if (source.length === target.length) {
            for (let i = 0; i < source.length; i++) target[i] = source[i];
            return;
        }

        const maxSrcIndex = source.length - 1;
        const maxDstIndex = Math.max(target.length - 1, 1);
        for (let i = 0; i < target.length; i++) {
            const t = (i / maxDstIndex) * maxSrcIndex;
            const lo = Math.floor(t);
            const hi = Math.min(lo + 1, maxSrcIndex);
            const frac = t - lo;
            target[i] = source[lo] * (1 - frac) + source[hi] * frac;
        }
    }

    export function addSpectrum(bands: number[]): void {
        resampleInto(bands, rawBuffer);

        for (let i = 0; i < numBars; i++) {
            rawBuffer[i] *= intensity;
        }

        if (shape === "vociferous") {
            applyVociferousFilter(rawBuffer, spreadBuffer);
        } else {
            applySpreadFilter(rawBuffer, spreadBuffer);
        }

        const damping = 1.0 - noiseReduction;
        for (let i = 0; i < numBars; i++) {
            cavaMem[i] = cavaMem[i] * noiseReduction + spreadBuffer[i];
        }

        for (let i = 0; i < numBars; i++) {
            const value = cavaMem[i] * damping;
            inputSpectrum[i] = Math.max(0, Math.min(1, value));
        }

        const now = performance.now();
        for (let i = 0; i < numBars; i++) {
            if (inputSpectrum[i] > peaks[i]) {
                peaks[i] = inputSpectrum[i];
                peakTimes[i] = now;
            }
        }
    }

    function tick(): void {
        if (!canvas || !ctx) return;

        const now = performance.now();

        // Throttle to ~30fps
        if (now - lastDrawTime < FRAME_INTERVAL) {
            animFrameId = requestAnimationFrame(tick);
            return;
        }
        lastDrawTime = now;

        const dt = now - lastUpdateTime;
        lastUpdateTime = now;
        const fs = dt / 16.66;

        const gMod = 1.5 / Math.max(0.1, noiseReduction);

        for (let i = 0; i < numBars; i++) {
            const target = inputSpectrum[i];
            const prev = prevSpectrum[i];

            if (target < prev) {
                const val = prev * (1.0 - cavaFall[i] * cavaFall[i] * gMod);
                spectrum[i] = Math.max(target, val);
                cavaFall[i] += 0.02 * fs;
            } else {
                spectrum[i] = target;
                cavaFall[i] = 0;
            }
            prevSpectrum[i] = spectrum[i];
        }

        for (let i = 0; i < numBars; i++) {
            if (now - peakTimes[i] > peakHoldMs) {
                peaks[i] -= peakFallRate * fs;
                if (peaks[i] < spectrum[i]) peaks[i] = spectrum[i];
            }
        }

        draw();
        animFrameId = requestAnimationFrame(tick);
    }

    function draw(): void {
        if (!ctx) return;
        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        const width = canvas.clientWidth;
        const height = canvas.clientHeight;

        const nextBufferWidth = Math.floor(width * dpr);
        const nextBufferHeight = Math.floor(height * dpr);
        if (canvas.width !== nextBufferWidth || canvas.height !== nextBufferHeight) {
            canvas.width = nextBufferWidth;
            canvas.height = nextBufferHeight;
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
            cachedGradient = null; // invalidate gradient cache on resize
        }

        // Cache the bar gradient (reuse across all bars per frame)
        if (!cachedGradient || cachedGradientHeight !== height) {
            cachedGradient = ctx.createLinearGradient(0, height, 0, 0);
            cachedGradient.addColorStop(0, BLUE_9);
            cachedGradient.addColorStop(0.5, BLUE_6);
            cachedGradient.addColorStop(1, BLUE_3);
            cachedGradientHeight = height;
        }

        ctx.clearRect(0, 0, width, height);

        const gap = numBars < 48 ? barGap : 1;
        const barWidth = (width - (numBars - 1) * gap) / numBars;

        ctx.fillStyle = cachedGradient;
        for (let i = 0; i < numBars; i++) {
            const x = i * (barWidth + gap);
            const weighted = spectrum[i] * emphasisWeights[i];
            const barH = weighted * height;

            if (barH < 1) continue;

            const radius = Math.min(barWidth / 2, 6);
            ctx.beginPath();
            ctx.moveTo(x, height);
            ctx.lineTo(x, height - barH + radius);
            ctx.arcTo(x, height - barH, x + radius, height - barH, radius);
            ctx.arcTo(x + barWidth, height - barH, x + barWidth, height - barH + radius, radius);
            ctx.lineTo(x + barWidth, height);
            ctx.closePath();
            ctx.fill();

            const peakWeighted = peaks[i] * emphasisWeights[i];
            if (peakWeighted > weighted + 0.02) {
                const peakY = height - peakWeighted * height;
                ctx.beginPath();
                ctx.moveTo(x, peakY);
                ctx.lineTo(x + barWidth, peakY);
                ctx.strokeStyle = BLUE_4;
                ctx.lineWidth = 1;
                ctx.stroke();
            }
        }
    }

    function start(): void {
        if (animFrameId !== null) return;
        lastUpdateTime = performance.now();
        animFrameId = requestAnimationFrame(tick);
    }

    function stop(): void {
        if (animFrameId !== null) {
            cancelAnimationFrame(animFrameId);
            animFrameId = null;
        }
    }

    export function reset(): void {
        spectrum.fill(0);
        prevSpectrum.fill(0);
        inputSpectrum.fill(0);
        cavaMem.fill(0);
        cavaFall.fill(0);
        peaks.fill(0);
        peakTimes.fill(0);
    }

    onMount(() => {
        ctx = canvas.getContext("2d");
        recomputeSpreadAttenuation();
        computeEmphasisWeights();
        if (active) start();
    });

    onDestroy(() => {
        stop();
        ctx = null;
    });

    $effect(() => {
        numBars;
        reinitializeBuffers();
    });

    $effect(() => {
        recomputeSpreadAttenuation();
    });

    $effect(() => {
        computeEmphasisWeights();
    });

    $effect(() => {
        if (active) {
            start();
        } else {
            stop();
        }
    });
</script>

<canvas class="spectrum-canvas" bind:this={canvas}></canvas>

<style>
    .spectrum-canvas {
        width: 100%;
        height: 100%;
        display: block;
    }
</style>
