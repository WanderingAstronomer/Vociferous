<script lang="ts">
    import { ws } from "./lib/ws";
    import { onMount, onDestroy } from "svelte";
    import { getModels, getConfig, getHealth } from "./lib/api";
    import { nav } from "./lib/navigation.svelte";
    import type { ViewId } from "./lib/navigation.svelte";
    import IconRail from "./lib/components/IconRail.svelte";
    import TranscribeView from "./views/TranscribeView.svelte";
    import TranscriptsView from "./views/TranscriptsView.svelte";
    import SettingsView from "./views/SettingsView.svelte";
    import RefineView from "./views/RefineView.svelte";
    import UserView from "./views/UserView.svelte";
    import EditView from "./views/EditView.svelte";
    import ToastContainer from "./lib/components/ToastContainer.svelte";
    import { toast } from "./lib/toast.svelte";
    import type { ConfigUpdatedData } from "./lib/events";

    let appReady = $state(false);
    let refinementEnabled = $state(true);
    let recordingActive = $state(false);

    let hiddenViews: Set<ViewId> = $derived(refinementEnabled ? new Set() : new Set<ViewId>(["refine"]));

    const VALID_SCALES = [75, 90, 100, 125, 150, 175, 200];

    function applyUiScale(scale: number): void {
        const clamped = VALID_SCALES.includes(scale) ? scale : 100;
        // Zoom lives on #app (not <html>) so percentage heights chain
        // correctly through the viewport. 100vh is never used under zoom —
        // the root div uses h-full so it inherits #app's zoomed height.
        const appEl = document.getElementById("app");
        if (appEl) appEl.style.zoom = clamped === 100 ? "" : `${clamped}%`;
    }

    let unsubConfigUpdated: (() => void) | null = null;
    let unsubRecordingStarted: (() => void) | null = null;
    let unsubRecordingStopped: (() => void) | null = null;

    onMount(async () => {
        ws.connect();

        // Check ASR model availability + refinement toggle + UI scale
        try {
            const [models, config] = await Promise.all([getModels(), getConfig()]);
            const hasAsr = Object.values(models.asr).some((m: any) => m.downloaded);
            if (!hasAsr) {
                nav.navigate("settings");
            }
            refinementEnabled = (config as any)?.refinement?.enabled ?? true;
            applyUiScale((config as any)?.display?.ui_scale ?? 100);
        } catch {
            console.warn("Could not check initial status");
        }

        // One-shot VRAM warning — fires once on startup, not on every health poll
        const VRAM_WARNING_MB = 1500;
        try {
            const health = await getHealth();
            const gpu = health.gpu;
            if (gpu?.cuda_available && gpu.vram_free_mb > 0 && gpu.vram_free_mb < VRAM_WARNING_MB) {
                toast.warning(
                    `Low VRAM: ${gpu.vram_free_mb} MB free of ${gpu.vram_total_mb} MB. ` +
                        `Inference may be slow or fail. Close other GPU apps or reduce GPU layers in Settings.`,
                    8000,
                );
            }
        } catch {
            // Health check failed — not critical, skip VRAM warning
        }

        unsubRecordingStarted = ws.on("recording_started", () => {
            recordingActive = true;
        });
        unsubRecordingStopped = ws.on("recording_stopped", () => {
            recordingActive = false;
        });

        // Stay in sync when settings change
        unsubConfigUpdated = ws.on("config_updated", (data: ConfigUpdatedData) => {
            const refinement = data.refinement;
            if (typeof refinement === "object" && refinement !== null && "enabled" in refinement) {
                refinementEnabled = Boolean(refinement.enabled);
                // If user is on refine view but just disabled it, bounce to transcribe
                if (!refinementEnabled && nav.current === "refine") {
                    nav.navigate("transcribe");
                }
            }

            const display = data.display;
            if (
                typeof display === "object" &&
                display !== null &&
                "ui_scale" in display &&
                typeof display.ui_scale === "number"
            ) {
                applyUiScale(display.ui_scale);
            }
        });

        appReady = true;
    });

    onDestroy(() => {
        ws.disconnect();
        unsubConfigUpdated?.();
        unsubRecordingStarted?.();
        unsubRecordingStopped?.();
    });
</script>

<div class="flex flex-col h-full overflow-hidden">
    <div class="flex flex-1 min-h-0 bg-[var(--shell-bg)] text-[var(--text-primary)] overflow-clip">
        {#if !appReady}
            <!-- Waiting for initial status check -->
        {:else}
            <IconRail
                currentView={nav.current}
                navigationLocked={nav.isNavigationLocked}
                {hiddenViews}
                isRecording={recordingActive}
                onNavigate={(view) => nav.navigate(view)}
            />

            <main class="flex-1 min-w-0 overflow-clip bg-[var(--surface-secondary)]">
                <!-- TranscribeView stays mounted to preserve recording/visualizer state -->
                <div class="h-full" style:display={nav.current === "transcribe" ? "block" : "none"}>
                    <TranscribeView />
                </div>

                {#if refinementEnabled}
                    <!-- RefineView stays mounted to preserve picker/instruction/result state -->
                    <div class="h-full" style:display={nav.current === "refine" ? "block" : "none"}>
                        <RefineView />
                    </div>
                {/if}

                <!-- TranscriptsView stays mounted to preserve pagination/filter/selection state -->
                <div class="h-full" style:display={nav.current === "transcripts" ? "block" : "none"}>
                    <TranscriptsView />
                </div>

                {#if nav.current === "settings"}
                    <SettingsView />
                {:else if nav.current === "user"}
                    <UserView />
                {:else if nav.current === "edit"}
                    <EditView />
                {/if}
            </main>
        {/if}
    </div>
    <ToastContainer />
</div>
