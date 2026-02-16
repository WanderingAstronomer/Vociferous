<script lang="ts">
    import { ws } from "./lib/ws";
    import { onMount, onDestroy } from "svelte";
    import { getModels, getConfig } from "./lib/api";
    import IconRail from "./lib/components/IconRail.svelte";
    import TitleBar from "./lib/components/TitleBar.svelte";
    import type { ViewId } from "./lib/components/IconRail.svelte";
    import TranscribeView from "./views/TranscribeView.svelte";
    import HistoryView from "./views/HistoryView.svelte";
    import SearchView from "./views/SearchView.svelte";
    import SettingsView from "./views/SettingsView.svelte";
    import ProjectsView from "./views/ProjectsView.svelte";
    import RefineView from "./views/RefineView.svelte";
    import UserView from "./views/UserView.svelte";

    let currentView: ViewId = $state("transcribe");
    let appReady = $state(false);
    let refinementEnabled = $state(true);

    let hiddenViews: Set<ViewId> = $derived(refinementEnabled ? new Set() : new Set<ViewId>(["refine"]));

    const VALID_SCALES = [100, 125, 150, 175, 200];

    function applyUiScale(scale: number): void {
        const clamped = VALID_SCALES.includes(scale) ? scale : 100;
        document.documentElement.style.zoom = `${clamped}%`;
    }

    function handleNavigate(view: ViewId) {
        currentView = view;
    }

    let unsubConfigUpdated: (() => void) | null = null;

    onMount(async () => {
        ws.connect();

        // Check ASR model availability + refinement toggle + UI scale
        try {
            const [models, config] = await Promise.all([getModels(), getConfig()]);
            const hasAsr = Object.values(models.asr).some((m: any) => m.downloaded);
            if (!hasAsr) {
                currentView = "settings";
            }
            refinementEnabled = (config as any)?.refinement?.enabled ?? true;
            applyUiScale((config as any)?.display?.ui_scale ?? 100);
        } catch {
            console.warn("Could not check initial status");
        }

        // Stay in sync when settings change
        unsubConfigUpdated = ws.on("config_updated", (data: any) => {
            if (data?.refinement?.enabled !== undefined) {
                refinementEnabled = data.refinement.enabled;
                // If user is on refine view but just disabled it, bounce to transcribe
                if (!refinementEnabled && currentView === "refine") {
                    currentView = "transcribe";
                }
            }
            if (data?.display?.ui_scale !== undefined) {
                applyUiScale(data.display.ui_scale);
            }
        });

        appReady = true;
    });

    onDestroy(() => {
        ws.disconnect();
        unsubConfigUpdated?.();
    });
</script>

<div class="app-root">
    <TitleBar />
    <div class="app-shell">
        {#if !appReady}
            <!-- Waiting for initial status check -->
        {:else}
            <IconRail {currentView} {hiddenViews} onNavigate={handleNavigate} />

            <main class="app-content">
                {#if currentView === "transcribe"}
                    <TranscribeView />
                {:else if currentView === "history"}
                    <HistoryView />
                {:else if currentView === "search"}
                    <SearchView />
                {:else if currentView === "settings"}
                    <SettingsView />
                {:else if currentView === "projects"}
                    <ProjectsView />
                {:else if currentView === "refine"}
                    <RefineView />
                {:else if currentView === "user"}
                    <UserView />
                {/if}
            </main>
        {/if}
    </div>
</div>

<style>
    .app-root {
        display: flex;
        flex-direction: column;
        height: 100vh;
        overflow: hidden;
    }

    .app-shell {
        display: flex;
        flex: 1;
        background: var(--shell-bg);
        color: var(--text-primary);
        overflow: hidden;
    }

    .app-content {
        flex: 1;
        overflow: hidden;
        background: var(--surface-secondary);
    }
</style>
