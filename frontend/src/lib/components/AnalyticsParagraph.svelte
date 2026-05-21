<!--
  AnalyticsParagraph — SLM-generated analytics insight display.

  The SLM produces a single insight string with a paragraph break between the
  daily summary and the lifetime/big-picture summary. The `segment` prop selects
  which portion to render so the daily insight can live on the Transcribe
  dashboard while the lifetime insight lives on the User view, without forcing
  two backend calls or duplicating the same text in two places.
-->
<script lang="ts">
    import { onMount } from "svelte";
    import { getInsight } from "../api";
    import { ws } from "../ws";

    type Segment = "daily" | "lifetime" | "all";

    let {
        class: className = "",
        segment = "all" as Segment,
    }: { class?: string; segment?: Segment } = $props();

    let text = $state("");

    onMount(() => {
        getInsight()
            .then((res) => {
                text = res.text || "";
            })
            .catch(() => {});

        const unsub = ws.on("insight_ready", (data) => {
            text = data.text || "";
        });
        return unsub;
    });

    let displayText = $derived.by(() => {
        if (!text) return "";
        if (segment === "all") return text;
        const parts = text.split(/\n\s*\n/);
        if (segment === "daily") return parts[0] ?? "";
        return parts.slice(1).join("\n\n");
    });
</script>

{#if displayText}
    <p
        class="text-[var(--text-base)] text-[var(--text-secondary)] italic mb-0 leading-[var(--leading-normal)] opacity-85 max-w-[var(--content-max-width)] px-[var(--space-4)] [overflow-wrap:anywhere] whitespace-pre-line {className}"
    >
        {displayText}
    </p>
{/if}
