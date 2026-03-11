<!--
    DiffView — word-level diff renderer.

    Compares two text strings and highlights insertions/deletions using
    the app's accent color. Uses the 'diff' library for word-level diffing.
-->
<script lang="ts">
    import { diffWords } from "diff";

    interface Props {
        original: string;
        revised: string;
        className?: string;
    }

    let { original, revised, className = "" }: Props = $props();

    let parts = $derived(diffWords(original, revised));
</script>

<div class="diff-view {className}">
    {#each parts as part}
        {#if part.removed}
            <span class="diff-removed">{part.value}</span>
        {:else if part.added}
            <span class="diff-added">{part.value}</span>
        {:else}
            <span>{part.value}</span>
        {/if}
    {/each}
</div>

<style>
    .diff-view {
        line-height: 1.7;
        word-break: break-word;
        white-space: pre-wrap;
    }

    .diff-removed {
        background: color-mix(in srgb, var(--color-danger) 15%, transparent);
        color: var(--color-danger);
        text-decoration: line-through;
        border-radius: 2px;
        padding: 0 2px;
    }

    .diff-added {
        background: color-mix(in srgb, var(--accent) 15%, transparent);
        color: var(--accent);
        border-radius: 2px;
        padding: 0 2px;
    }
</style>
