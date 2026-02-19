<script lang="ts">
    import { ws } from "./lib/ws";
    import { onMount, onDestroy } from "svelte";
    import { getModels, getConfig } from "./lib/api";
    import { nav } from "./lib/navigation.svelte";
    import type { ViewId } from "./lib/navigation.svelte";
    import IconRail from "./lib/components/IconRail.svelte";
    import TitleBar from "./lib/components/TitleBar.svelte";
    import TranscribeView from "./views/TranscribeView.svelte";
    import TranscriptsView from "./views/TranscriptsView.svelte";
    import SearchView from "./views/SearchView.svelte";
    import SettingsView from "./views/SettingsView.svelte";
    import RefineView from "./views/RefineView.svelte";
    import UserView from "./views/UserView.svelte";
    import type { ConfigUpdatedData } from "./lib/events";

    let appReady = $state(false);
    let refinementEnabled = $state(true);
    let recordingActive = $state(false);

    let hiddenViews: Set<ViewId> = $derived(refinementEnabled ? new Set() : new Set<ViewId>(["refine"]));

    const VALID_SCALES = [100, 125, 150, 175, 200];

    function applyUiScale(scale: number): void {
        const clamped = VALID_SCALES.includes(scale) ? scale : 100;
        document.documentElement.style.zoom = `${clamped}%`;
    }

    function handleNavigate(view: ViewId) {
        nav.navigate(view);
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

<div class="flex flex-col h-screen overflow-hidden">
    <TitleBar isRecording={recordingActive} />
    <div class="flex flex-1 bg-[var(--shell-bg)] text-[var(--text-primary)] overflow-hidden">
        {#if !appReady}
            <!-- Waiting for initial status check -->
        {:else}
            <IconRail
                currentView={nav.current}
                navigationLocked={nav.isNavigationLocked}
                {hiddenViews}
                onNavigate={handleNavigate}
            />

            <main class="flex-1 overflow-hidden bg-[var(--surface-secondary)]">
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

                {#if nav.current === "transcripts"}
                    <TranscriptsView />
                {:else if nav.current === "search"}
                    <SearchView />
                {:else if nav.current === "settings"}
                    <SettingsView />
                {:else if nav.current === "user"}
                    <UserView />
                {/if}
            </main>
        {/if}
    </div>
</div>
