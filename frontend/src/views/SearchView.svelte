<script lang="ts">
    import { searchTranscripts, type Transcript } from "../lib/api";

    let query = $state("");
    let results: Transcript[] = $state([]);
    let searching = $state(false);
    let searched = $state(false);
    let error = $state("");

    async function handleSearch() {
        if (!query.trim()) return;
        searching = true;
        error = "";
        searched = true;
        try {
            results = await searchTranscripts(query.trim());
        } catch (e: any) {
            error = e.message;
        } finally {
            searching = false;
        }
    }

    function formatDate(iso: string): string {
        return new Date(iso).toLocaleString();
    }

    function highlight(text: string, q: string): string {
        if (!q) return text;
        const escaped = q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        return text.replace(
            new RegExp(`(${escaped})`, "gi"),
            '<mark class="bg-[var(--color-accent)]/30 text-inherit rounded">$1</mark>',
        );
    }
</script>

<div class="flex flex-col h-full p-6">
    <h1 class="text-2xl font-semibold mb-4">Search</h1>

    <!-- Search bar -->
    <form
        class="flex gap-2 mb-6"
        onsubmit={(e) => {
            e.preventDefault();
            handleSearch();
        }}
    >
        <input
            type="text"
            bind:value={query}
            placeholder="Search transcripts..."
            class="flex-1 bg-[var(--color-bg-tertiary)] border border-[var(--color-border)] rounded-[var(--radius)] px-3 py-2 text-sm focus:outline-none focus:border-[var(--color-accent)]"
        />
        <button
            type="submit"
            class="px-4 py-2 bg-[var(--color-accent)] hover:bg-[var(--color-accent-hover)] text-white rounded-[var(--radius)] text-sm font-medium transition-colors disabled:opacity-50"
            disabled={searching || !query.trim()}
        >
            {searching ? "..." : "Search"}
        </button>
    </form>

    <!-- Results -->
    {#if error}
        <p class="text-[var(--color-danger)]">{error}</p>
    {:else if searching}
        <p class="text-[var(--color-text-muted)]">Searching...</p>
    {:else if searched && results.length === 0}
        <p class="text-[var(--color-text-muted)]">No results for "{query}"</p>
    {:else if results.length > 0}
        <div class="text-xs text-[var(--color-text-muted)] mb-3">
            {results.length} result{results.length !== 1 ? "s" : ""}
        </div>
        <div class="flex-1 overflow-y-auto space-y-2">
            {#each results as entry (entry.id)}
                <div
                    class="p-4 bg-[var(--color-bg-secondary)] rounded-lg border border-[var(--color-border)] hover:border-[var(--color-accent)]/50 transition-colors"
                >
                    <p class="text-sm leading-relaxed">
                        {@html highlight(entry.text || entry.raw_text, query)}
                    </p>
                    <p class="text-xs text-[var(--color-text-muted)] mt-2">
                        {formatDate(entry.created_at)} · {entry.duration_ms}ms
                    </p>
                </div>
            {/each}
        </div>
    {/if}
</div>
