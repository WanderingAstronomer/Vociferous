<script lang="ts">
    import { ArrowUpDown, ChevronLeft, ChevronRight, Search, X } from "lucide-svelte";

    import type { Tag } from "../../api";
    import TagBar from "../TagBar.svelte";

    type SortDirection = "asc" | "desc";

    interface SortOption {
        value: string;
        label: string;
    }

    interface Props {
        searchQuery: string;
        searching: boolean;
        searchTotal: number;
        filteredCount: number;
        isSearching: boolean;
        allTags: Tag[];
        activeTagIds: Set<number>;
        tagFilterMode: "any" | "all";
        sortBy: string;
        sortDir: SortDirection;
        sortOptions: readonly SortOption[];
        currentPage: number;
        totalPages: number;
        pageSize: number;
        pageSizes: readonly number[];
        onSearchChange: (value: string) => void;
        onClearSearch: () => void;
        onToggleTagFilter: (tagId: number) => void;
        onCreateTag: (name: string, color: string) => void;
        onDeleteTag: (tagId: number) => void;
        onTagColorChange: (tagId: number, color: string) => void;
        onCycleFilterMode: () => void;
        onClearTagFilters: () => void;
        onSetSort: (value: string) => void;
        onGoToPage: (page: number) => void;
        onSetPageSize: (size: number) => void;
    }

    let {
        searchQuery,
        searching,
        searchTotal,
        filteredCount,
        isSearching,
        allTags,
        activeTagIds,
        tagFilterMode,
        sortBy,
        sortDir,
        sortOptions,
        currentPage,
        totalPages,
        pageSize,
        pageSizes,
        onSearchChange,
        onClearSearch,
        onToggleTagFilter,
        onCreateTag,
        onDeleteTag,
        onTagColorChange,
        onCycleFilterMode,
        onClearTagFilters,
        onSetSort,
        onGoToPage,
        onSetPageSize,
    }: Props = $props();
</script>

<div class="shrink-0 px-4 pt-3 pb-2 flex flex-col gap-2 border-b border-[var(--shell-border)]">
    <div class="relative">
        <input
            type="text"
            class="w-full h-9 bg-[var(--surface-secondary)] border border-[var(--shell-border)] rounded-lg text-[var(--text-primary)] text-sm pl-3 pr-8 outline-none transition-colors duration-150 focus:border-[var(--accent)] placeholder:text-[var(--text-tertiary)]"
            placeholder="Search transcripts…"
            value={searchQuery}
            oninput={(event) => onSearchChange((event.currentTarget as HTMLInputElement).value)}
        />
        {#if searchQuery}
            <button
                class="absolute right-2.5 top-1/2 -translate-y-1/2 w-5 h-5 text-[var(--text-tertiary)] hover:text-[var(--text-primary)] bg-transparent border-none cursor-pointer p-0 flex items-center justify-center rounded transition-colors"
                onclick={onClearSearch}
                title="Clear search"
            >
                <X size={13} />
            </button>
        {:else}
            <Search
                size={14}
                class="absolute right-2.5 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)] pointer-events-none"
            />
        {/if}
    </div>

    <TagBar
        tags={allTags}
        activeIds={activeTagIds}
        ontoggle={onToggleTagFilter}
        oncreate={onCreateTag}
        ondelete={onDeleteTag}
        oncolorchange={onTagColorChange}
    >
        {#if activeTagIds.size > 0}
            <button
                class="h-6 px-2 rounded-full text-xs font-semibold border border-[var(--accent-muted)] bg-transparent text-[var(--accent)] cursor-pointer transition-colors hover:bg-[var(--hover-overlay)]"
                onclick={onCycleFilterMode}
                title="Toggle between matching ANY or ALL selected tags"
            >
                {tagFilterMode === "any" ? "ANY" : "ALL"}
            </button>
            <button
                class="h-6 px-1.5 rounded-full text-xs text-[var(--text-tertiary)] bg-transparent border-none cursor-pointer hover:text-[var(--text-primary)] transition-colors"
                onclick={onClearTagFilters}
            >
                Clear
            </button>
        {/if}
    </TagBar>
</div>

<div class="shrink-0 px-4 py-1.5 flex items-center gap-3 text-[13px] text-[var(--text-tertiary)]">
    {#if !isSearching}
        <div class="flex items-center gap-1 shrink-0">
            <ArrowUpDown size={12} class="text-[var(--text-tertiary)]" />
            {#each sortOptions as opt (opt.value)}
                <button
                    class="h-6 px-1.5 rounded text-[11px] border-none cursor-pointer transition-colors"
                    class:bg-[var(--hover-overlay)]={sortBy === opt.value}
                    class:text-[var(--text-primary)]={sortBy === opt.value}
                    class:font-semibold={sortBy === opt.value}
                    class:bg-transparent={sortBy !== opt.value}
                    class:text-[var(--text-tertiary)]={sortBy !== opt.value}
                    class:hover:text-[var(--text-secondary)]={sortBy !== opt.value}
                    onclick={() => onSetSort(opt.value)}
                    title="Sort by {opt.label}{sortBy === opt.value
                        ? sortDir === 'asc'
                            ? ' (ascending)'
                            : ' (descending)'
                        : ''}"
                >
                    {opt.label}{sortBy === opt.value ? (sortDir === "asc" ? " ↑" : " ↓") : ""}
                </button>
            {/each}
        </div>
    {:else}
        <span class="shrink-0">
            {#if !searching}
                {#if searchTotal > filteredCount}
                    Showing {filteredCount} of {searchTotal} results for "{searchQuery}"
                {:else}
                    {filteredCount} result{filteredCount !== 1 ? "s" : ""} for "{searchQuery}"
                {/if}
            {/if}
        </span>
    {/if}

    <div class="flex-1"></div>

    {#if !isSearching && totalPages > 1}
        <div class="flex items-center gap-2 shrink-0">
            <button
                class="flex items-center gap-1 h-6 px-2 rounded text-[var(--text-secondary)] bg-transparent border border-[var(--shell-border)] cursor-pointer transition-colors text-[11px] hover:bg-[var(--hover-overlay)] disabled:opacity-30 disabled:cursor-default"
                onclick={() => onGoToPage(currentPage - 1)}
                disabled={currentPage <= 1}
            >
                <ChevronLeft size={12} /> Prev
            </button>
            <span class="text-[var(--text-tertiary)] tabular-nums text-[11px]">{currentPage} / {totalPages}</span>
            <button
                class="flex items-center gap-1 h-6 px-2 rounded text-[var(--text-secondary)] bg-transparent border border-[var(--shell-border)] cursor-pointer transition-colors text-[11px] hover:bg-[var(--hover-overlay)] disabled:opacity-30 disabled:cursor-default"
                onclick={() => onGoToPage(currentPage + 1)}
                disabled={currentPage >= totalPages}
            >
                Next <ChevronRight size={12} />
            </button>
        </div>
    {/if}

    <div class="flex-1"></div>

    {#if !isSearching}
        <div class="flex items-center gap-0.5 shrink-0">
            {#each pageSizes as size (size)}
                <button
                    class="h-6 px-1.5 rounded text-[11px] border-none cursor-pointer transition-colors"
                    class:bg-[var(--hover-overlay)]={pageSize === size}
                    class:text-[var(--text-primary)]={pageSize === size}
                    class:font-semibold={pageSize === size}
                    class:bg-transparent={pageSize !== size}
                    class:text-[var(--text-tertiary)]={pageSize !== size}
                    class:hover:text-[var(--text-secondary)]={pageSize !== size}
                    onclick={() => onSetPageSize(size)}
                >
                    {size}
                </button>
            {/each}
            <span class="text-[10px] text-[var(--text-tertiary)] ml-0.5">/ page</span>
        </div>
    {/if}
</div>
