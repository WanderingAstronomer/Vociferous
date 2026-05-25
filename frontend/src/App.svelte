<script lang="ts">
    import { ws } from "./lib/ws";
    import { onMount, onDestroy } from "svelte";
    import { getModels, getHealth, getRecoverableRecordings } from "./lib/api";
    import { appConfig } from "./lib/config.svelte";
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
    import ConfirmDialog from "./lib/components/ConfirmDialog.svelte";
    import ExportDialog from "./lib/components/ExportDialog.svelte";
    import { toast } from "./lib/toast.svelte";

    let appReady = $state(false);
    let recordingActive = $state(false);

    let refinementEnabled = $derived(appConfig.current?.refinement?.enabled ?? true);
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

    let unsubRecordingStarted: (() => void) | null = null;
    let unsubRecordingStopped: (() => void) | null = null;

    $effect(() => {
        applyUiScale(appConfig.current?.display?.ui_scale ?? 100);
    });

    $effect(() => {
        if (!refinementEnabled && nav.current === "refine") {
            nav.navigate("transcribe");
        }
    });

    onMount(async () => {
        ws.connect();

        // Check ASR model availability + refinement toggle + UI scale
        try {
            const [models] = await Promise.all([getModels(), appConfig.ensureLoaded()]);
            const hasAsr = Object.values(models.asr).some((m: any) => m.downloaded);
            if (!hasAsr) {
                nav.navigate("settings");
            }
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

        try {
            const recoverable = await getRecoverableRecordings();
            if (recoverable.total > 0) {
                toast.warning(
                    `${recoverable.total} recoverable recording${recoverable.total === 1 ? "" : "s"} found. Manage them in Settings > Recording.`,
                    9000,
                );
            }
        } catch {
            // Recovery inventory is advisory; startup should not block on it.
        }

        unsubRecordingStarted = ws.on("recording_started", () => {
            recordingActive = true;
        });
        unsubRecordingStopped = ws.on("recording_stopped", () => {
            recordingActive = false;
        });

        appReady = true;
    });

    onDestroy(() => {
        ws.disconnect();
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
    <ConfirmDialog />
    <ExportDialog />
</div>
