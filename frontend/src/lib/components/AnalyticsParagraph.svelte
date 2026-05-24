<!--
  AnalyticsParagraph — SLM-generated analytics insight display.

    The backend owns the structured daily/lifetime insight cache. The `segment`
    prop selects which field to render so model-output formatting never becomes
    a frontend parsing contract.
-->
<script lang="ts">
    import { RefreshCw } from "lucide-svelte";
    import { onMount } from "svelte";
    import { getInsight, refreshInsight, type InsightPayload } from "../api";
    import { ws } from "../ws";

    type Segment = "daily" | "lifetime" | "all";

    let { class: className = "", segment = "all" as Segment }: { class?: string; segment?: Segment } = $props();

    let insight: InsightPayload | null = $state(null);
    let refreshing = $state(false);

    onMount(() => {
        getInsight()
            .then((res) => {
                insight = res;
            })
            .catch(() => {});

        const unsub = ws.on("insight_ready", (data) => {
            insight = data;
        });
        return unsub;
    });

    let displayText = $derived.by(() => {
        if (!insight) return "";
        if (segment === "daily") return insight.daily_text || "";
        if (segment === "lifetime") return insight.lifetime_text || "";
        return insight.text || [insight.daily_text, insight.lifetime_text].filter(Boolean).join("\n\n");
    });

    async function handleRefresh() {
        if (refreshing) return;
        refreshing = true;
        try {
            insight = await refreshInsight();
        } catch {
        } finally {
            refreshing = false;
        }
    }
</script>

{#if displayText}
    <div class="flex w-full items-start justify-center gap-2">
        <p
            class="text-[var(--text-base)] text-[var(--text-secondary)] italic mb-0 leading-[var(--leading-normal)] opacity-85 max-w-[var(--content-max-width)] px-[var(--space-4)] [overflow-wrap:anywhere] whitespace-pre-line {className}"
        >
            {displayText}
        </p>
        <button
            type="button"
            class="mt-0.5 grid size-7 shrink-0 place-items-center rounded-md text-[var(--text-muted)] opacity-70 transition hover:bg-[var(--surface-hover)] hover:text-[var(--text-base)] hover:opacity-100 disabled:pointer-events-none disabled:opacity-40"
            aria-label="Refresh insight"
            title="Refresh insight"
            disabled={refreshing}
            onclick={handleRefresh}
        >
            <RefreshCw size={14} class={refreshing ? "animate-spin" : ""} />
        </button>
    </div>
{/if}
