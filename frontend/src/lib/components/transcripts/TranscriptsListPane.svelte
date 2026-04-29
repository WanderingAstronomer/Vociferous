<script lang="ts">
    import { FileText, Hammer, Loader2 } from "lucide-svelte";

    import type { Transcript, Tag } from "../../api";
    import { SelectionManager } from "../../selection.svelte";
    import { formatDuration, formatRelativeDate, wordCount } from "../../formatters";
    import EmptyState from "../EmptyState.svelte";
    import MarkdownBody from "../MarkdownBody.svelte";
    import StyledButton from "../StyledButton.svelte";

    interface Props {
        entries: Transcript[];
        loading: boolean;
        error: string;
        isSearching: boolean;
        searchQuery: string;
        activeTagIds: Set<number>;
        selection: SelectionManager;
        defaultPromptId: number | null;
        hasMore: boolean;
        searching: boolean;
        remainingSearchCount: number;
        displayTotal: number;
        onCardClick: (id: number, event: MouseEvent) => void;
        onCardDoubleClick: (id: number) => void;
        onLoadMore: () => void;
    }

    let {
        entries,
        loading,
        error,
        isSearching,
        searchQuery,
        activeTagIds,
        selection,
        defaultPromptId,
        hasMore,
        searching,
        remainingSearchCount,
        displayTotal,
        onCardClick,
        onCardDoubleClick,
        onLoadMore,
    }: Props = $props();

    function getDisplayText(entry: Transcript): string {
        return entry.normalized_text || entry.raw_text || "";
    }

    function getTitle(entry: Transcript): string {
        if (entry.display_name?.trim()) return entry.display_name.trim();
        return `Transcript #${entry.id}`;
    }

    function truncate(text: string, max = 240): string {
        if (text.length <= max) return text;
        const cut = text.lastIndexOf(" ", max);
        return (cut > 0 ? text.slice(0, cut) : text.slice(0, max)) + "…";
    }

    function highlight(text: string, query: string): string {
        if (!query) return escapeHtml(text);
        const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        return escapeHtml(text).replace(new RegExp(`(${escaped})`, "gi"), '<mark class="search-hl">$1</mark>');
    }

    function escapeHtml(text: string): string {
        return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    function tagColor(tag: Tag): string {
        return tag.color ?? "var(--accent)";
    }
</script>

<div class="flex-1 overflow-y-auto px-4 pb-2" style="scrollbar-gutter: stable">
    {#if loading}
        <EmptyState icon={Loader2} message="Loading…" height="fixed" spinning />
    {:else if error}
        <EmptyState message={error} height="fixed" />
    {:else if entries.length === 0}
        <EmptyState icon={FileText} height="fixed">
            <span>
                {#if isSearching}
                    No results for "{searchQuery}"
                {:else if activeTagIds.size > 0}
                    No transcripts match selected tags
                {:else}
                    No transcripts yet
                {/if}
            </span>
        </EmptyState>
    {:else}
        <div class="flex flex-col gap-1.5 pt-1">
            {#each entries as entry (entry.id)}
                <button
                    class="w-full text-left p-3 rounded-lg border cursor-pointer transition-all duration-150 group/card"
                    class:bg-[var(--hover-overlay-blue)]={selection.isSelected(entry.id)}
                    class:border-[var(--accent)]={selection.isSelected(entry.id)}
                    class:bg-[var(--surface-secondary)]={!selection.isSelected(entry.id)}
                    class:border-[var(--shell-border)]={!selection.isSelected(entry.id)}
                    class:hover:border-[var(--accent-muted)]={!selection.isSelected(entry.id)}
                    class:hover:bg-[var(--hover-overlay)]={!selection.isSelected(entry.id)}
                    onclick={(event) => onCardClick(entry.id, event)}
                    ondblclick={() => onCardDoubleClick(entry.id)}
                >
                    <div class="flex items-start justify-between gap-2 mb-1">
                        <h3
                            class="text-[18px] font-semibold text-[var(--text-primary)] leading-snug m-0 truncate flex-1"
                        >
                            {getTitle(entry)}
                        </h3>
                        <span class="text-[12px] text-[var(--text-tertiary)] font-mono shrink-0 pt-0.5">
                            {formatRelativeDate(entry.created_at)}
                        </span>
                    </div>

                    {#if isSearching}
                        <p class="text-[15px] text-[var(--text-secondary)] leading-relaxed m-0 mb-2 line-clamp-2">
                            {@html highlight(truncate(getDisplayText(entry)), searchQuery)}
                        </p>
                    {:else}
                        <div
                            class="text-[15px] text-[var(--text-secondary)] leading-relaxed mb-2 max-h-[3.25em] overflow-hidden"
                        >
                            <MarkdownBody text={getDisplayText(entry)} className="[&>*:first-child]:mt-0" />
                        </div>
                    {/if}

                    <div class="flex items-center gap-2 flex-wrap pt-1.5 mt-0.5">
                        {#if entry.id === defaultPromptId}
                            <span
                                class="inline-flex items-center gap-1 h-5 px-1.5 rounded-full text-[10px] font-medium bg-[color-mix(in_srgb,var(--accent)_18%,transparent)] text-[var(--text-primary)]"
                            >
                                Default Prompt
                            </span>
                        {/if}
                        {#each entry.tags as tag (tag.id)}
                            <span
                                class="inline-flex items-center gap-1 h-5 px-1.5 rounded-full text-[10px] font-medium"
                                style="background: color-mix(in srgb, {tagColor(
                                    tag,
                                )} 25%, transparent); color: var(--text-primary);"
                            >
                                {#if tag.is_system}
                                    <Hammer size={9} class="shrink-0" />
                                {:else}
                                    <span class="w-1.5 h-1.5 rounded-full" style="background: {tagColor(tag)}"></span>
                                {/if}
                                {tag.name}
                            </span>
                        {/each}

                        <div class="flex-1"></div>

                        <span class="text-[11px] text-[var(--text-tertiary)] font-mono">
                            {formatDuration(entry.duration_ms)}
                        </span>
                        <span class="text-[11px] text-[var(--text-tertiary)] font-mono">
                            {wordCount(getDisplayText(entry)).toLocaleString()} words
                        </span>
                    </div>
                </button>
            {/each}
        </div>

        {#if isSearching && hasMore}
            <div class="flex justify-center py-3">
                <StyledButton size="sm" variant="secondary" onclick={onLoadMore} disabled={searching}>
                    {#if searching}
                        <Loader2 size={14} class="animate-spin" /> Loading…
                    {:else}
                        Load More ({remainingSearchCount} remaining)
                    {/if}
                </StyledButton>
            </div>
        {/if}

        {#if !loading}
            <div class="flex items-center justify-center gap-2 py-3 text-[13px]">
                <span class="text-[var(--accent)] font-semibold tabular-nums">
                    {displayTotal} transcript{displayTotal !== 1 ? "s" : ""}
                    {#if activeTagIds.size > 0}
                        <span class="text-[var(--accent)]/70">(filtered)</span>
                    {/if}
                </span>
                {#if selection.hasSelection}
                    <span class="text-[var(--accent)] font-semibold">· {selection.count} selected</span>
                {/if}
            </div>
        {/if}
    {/if}
</div>
