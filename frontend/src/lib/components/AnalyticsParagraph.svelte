<!--
  AnalyticsParagraph — Reusable SLM-generated analytics insight display.

  Shared by UserView and TranscribeView. Fetches the cached insight on mount
  and subscribes to the `insight_ready` WebSocket event for live updates.
-->
<script lang="ts">
    import { onMount } from "svelte";
    import { getInsight } from "../api";
    import { ws } from "../ws";

    /** Optional extra CSS classes applied to the outermost wrapper. */
    let { class: className = "" }: { class?: string } = $props();

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
</script>

{#if text}
    <p
        class="text-[var(--text-base)] text-[var(--text-secondary)] italic mb-0 leading-[var(--leading-normal)] opacity-85 max-w-[var(--content-max-width)] px-[var(--space-4)] [overflow-wrap:anywhere] whitespace-pre-line {className}"
    >
        {text}
    </p>
{/if}
