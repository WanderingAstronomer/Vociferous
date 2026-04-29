<script lang="ts">
    import AnalyticsParagraph from "../AnalyticsParagraph.svelte";

    type WorkspaceState = "idle" | "recording" | "transcribing" | "ready" | "viewing" | "editing";

    interface SessionStats {
        todayWords: number;
        avgWpm: number;
        count: number;
    }

    interface Props {
        viewState: WorkspaceState;
        greeting: string;
        refinementEnabled: boolean;
        sessionStats: SessionStats | null;
        transcriptTitle: string;
        transcriptTimestamp: string;
    }

    let { viewState, greeting, refinementEnabled, sessionStats, transcriptTitle, transcriptTimestamp }: Props =
        $props();

    const showsGreeting = $derived(viewState === "idle" || viewState === "recording");
</script>

<div class="shrink-0 py-[var(--space-1)]">
    {#if showsGreeting}
        <div class="flex flex-col items-center text-center gap-[var(--space-1)]">
            <h1 class="text-3xl font-[var(--weight-emphasis)] text-[var(--accent)] m-0 leading-[var(--leading-tight)]">
                {greeting}
            </h1>
            <AnalyticsParagraph />
            {#if !refinementEnabled && viewState === "idle"}
                <p class="text-[var(--text-sm)] text-[var(--text-tertiary)] mb-0">
                    Enable Grammar Refinement in Settings to unlock AI insights.
                </p>
            {/if}
            {#if sessionStats && sessionStats.count > 0}
                <div
                    class="inline-flex items-stretch bg-[var(--surface-secondary)] border border-[var(--shell-border)] rounded-[var(--radius-md)] mt-[var(--space-2)]"
                >
                    <div class="flex flex-col items-center justify-center px-5 py-2">
                        <span class="text-[11px] text-[var(--text-tertiary)] leading-none mb-1.5">Today's Words</span>
                        <span
                            class="text-base font-[var(--weight-emphasis)] text-[var(--text-primary)] font-[var(--font-mono)] leading-none"
                        >
                            {sessionStats.todayWords.toLocaleString()}
                        </span>
                    </div>
                    <div class="w-px self-stretch my-2 bg-[var(--shell-border)]"></div>
                    <div class="flex flex-col items-center justify-center px-5 py-2">
                        <span class="text-[11px] text-[var(--text-tertiary)] leading-none mb-1.5">Avg WPM</span>
                        <span
                            class="text-base font-[var(--weight-emphasis)] text-[var(--text-primary)] font-[var(--font-mono)] leading-none"
                        >
                            {sessionStats.avgWpm > 0 ? sessionStats.avgWpm : "—"}
                        </span>
                    </div>
                    <div class="w-px self-stretch my-2 bg-[var(--shell-border)]"></div>
                    <div class="flex flex-col items-center justify-center px-5 py-2">
                        <span class="text-[11px] text-[var(--text-tertiary)] leading-none mb-1.5">Sessions</span>
                        <span
                            class="text-base font-[var(--weight-emphasis)] text-[var(--text-primary)] font-[var(--font-mono)] leading-none"
                        >
                            {sessionStats.count}
                        </span>
                    </div>
                </div>
            {/if}
        </div>
    {:else if viewState !== "transcribing"}
        <div class="flex flex-col items-center text-center gap-0.5">
            {#if transcriptTitle}
                <h2
                    class="text-xl font-[var(--weight-emphasis)] text-[var(--accent)] m-0 leading-[var(--leading-tight)]"
                >
                    {transcriptTitle}
                </h2>
            {/if}
            {#if transcriptTimestamp}
                <span class="text-[var(--text-sm)] text-[var(--text-tertiary)] font-[var(--font-mono)]">
                    {transcriptTimestamp}
                </span>
            {/if}
        </div>
    {/if}
</div>
