<script lang="ts">
    /**
     * TranscriptsView — Full-width card-based transcript browser.
     *
     * Replaces the old split-panel project-tree layout with a flat,
     * tag-filtered, searchable card list. Clicking a card navigates
     * to the detail/edit view. Multi-select + bottom action bar.
     */

    import {
        getTranscripts,
        getConfig,
        updateConfig,
        updateTag,
        searchTranscripts,
        deleteTranscript,
        batchDeleteTranscripts,
        getTags,
        createTag,
        deleteTag,
        assignTags,
        batchAssignTags,
        type Transcript,
        type Tag,
        type SearchResult,
    } from "../lib/api";
    import { ws } from "../lib/ws";
    import { nav } from "../lib/navigation.svelte";
    import { SelectionManager } from "../lib/selection.svelte";
    import { onMount } from "svelte";
    import {
        Search,
        X,
        Loader2,
        FileText,
        Trash2,
        Pencil,
        Sparkles,
        Tag as TagIcon,
        Plus,
        Check,
        Copy,
        ChevronLeft,
        ChevronRight,
        ArrowUpDown,
        Palette,
    } from "lucide-svelte";
    import StyledButton from "../lib/components/StyledButton.svelte";
    import { formatDuration, wordCount, formatRelativeDate } from "../lib/formatters";

    /* ===== State ===== */

    let entries: Transcript[] = $state([]);
    let totalCount = $state(0);
    let loading = $state(true);
    let error = $state("");

    // Pagination & Sort
    let pageSize = $state(50);
    let currentPage = $state(1);
    let sortBy = $state("created_at");
    let sortDir: "asc" | "desc" = $state("desc");

    const PAGE_SIZES = [25, 50, 100] as const;
    const SORT_OPTIONS = [
        { value: "created_at", label: "Date" },
        { value: "duration_ms", label: "Duration" },
        { value: "words", label: "Words" },
        { value: "silence", label: "Silence" },
        { value: "display_name", label: "Title" },
    ] as const;

    // Search (FTS)
    let searchQuery = $state("");
    let searchResults: Transcript[] = $state([]);
    let searchTotal = $state(0);
    let searching = $state(false);
    let debounceTimer: ReturnType<typeof setTimeout> | null = null;
    const SEARCH_PAGE_SIZE = 100;

    // Tags
    let allTags: Tag[] = $state([]);
    let activeTagIds: Set<number> = $state(new Set());
    let tagFilterMode: "any" | "all" = $state("any");

    // Tag creation inline
    let showTagCreate = $state(false);
    let newTagName = $state("");
    let newTagColor = $state("#5a9fd4");

    // Tag context menu (right-click: edit color + delete)
    let tagMenuId: number | null = $state(null);
    let tagMenuX = $state(0);
    let tagMenuY = $state(0);
    let tagMenuColor = $state("");

    // Tag assignment popover
    let tagAssignOpen = $state(false);
    let tagAssignX = $state(0);
    let tagAssignY = $state(0);

    // Copy feedback
    let copied = $state(false);

    /* ===== Multi-Selection ===== */

    const selection = new SelectionManager();

    /* ===== Derived ===== */

    /** Are we in search mode? */
    let isSearching = $derived(searchQuery.trim().length > 0);

    /** Source entries: search results (client-filtered by tags) or server-paginated list. */
    let filteredEntries = $derived.by((): Transcript[] => {
        if (isSearching) {
            // Search doesn't support server-side tag filtering — filter client-side
            if (activeTagIds.size === 0) return searchResults;
            return searchResults.filter((e) => {
                const entryTagIds = new Set(e.tags.map((t) => t.id));
                if (tagFilterMode === "all") {
                    return [...activeTagIds].every((id) => entryTagIds.has(id));
                }
                return [...activeTagIds].some((id) => entryTagIds.has(id));
            });
        }
        // Browse mode: entries already filtered/sorted/paginated server-side
        return entries;
    });

    /** Pagination derived */
    let totalPages = $derived(Math.max(1, Math.ceil(totalCount / pageSize)));
    let displayTotal = $derived(isSearching ? searchTotal : totalCount);

    /** Has more search results to load? */
    let hasMore = $derived(isSearching && searchResults.length < searchTotal);

    /** Ordered IDs for range selection. */
    let orderedIds = $derived(filteredEntries.map((e) => e.id));

    /** The single selected entry (for single-select actions). */
    let selectedEntry = $derived(
        selection.count === 1 ? (filteredEntries.find((e) => e.id === selection.ids[0]) ?? null) : null,
    );

    /* ===== Formatting ===== */

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

    function highlight(text: string, q: string): string {
        if (!q) return escapeHtml(text);
        const escaped = q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        return escapeHtml(text).replace(new RegExp(`(${escaped})`, "gi"), '<mark class="search-hl">$1</mark>');
    }

    function escapeHtml(text: string): string {
        return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    /** Default tag color when none is set. */
    function tagColor(tag: Tag): string {
        return tag.color ?? "var(--accent)";
    }

    /* ===== Data Loading ===== */

    let loadGeneration = 0; // debounce guard for rapid param changes

    async function loadTranscripts() {
        const gen = ++loadGeneration;
        loading = entries.length === 0;
        error = "";
        try {
            const tagIds = activeTagIds.size > 0 ? [...activeTagIds] : undefined;
            const result = await getTranscripts({
                limit: pageSize,
                offset: (currentPage - 1) * pageSize,
                sort_by: sortBy,
                sort_dir: sortDir,
                tag_ids: tagIds,
                tag_mode: tagFilterMode,
            });
            if (gen !== loadGeneration) return; // stale response
            entries = result.items;
            totalCount = result.total;
        } catch (e: any) {
            if (gen === loadGeneration) error = e.message;
        } finally {
            if (gen === loadGeneration) loading = false;
        }
    }

    async function loadTags() {
        try {
            allTags = await getTags();
        } catch {
            /* ignore */
        }
    }

    async function doSearch() {
        if (!searchQuery.trim()) {
            searchResults = [];
            searchTotal = 0;
            return;
        }
        searching = true;
        error = "";
        try {
            const res: SearchResult = await searchTranscripts(searchQuery.trim(), SEARCH_PAGE_SIZE, 0);
            searchResults = res.items;
            searchTotal = res.total;
        } catch (e: any) {
            error = e.message;
        } finally {
            searching = false;
        }
    }

    async function loadMore() {
        if (!isSearching || !hasMore) return;
        searching = true;
        try {
            const res: SearchResult = await searchTranscripts(
                searchQuery.trim(),
                SEARCH_PAGE_SIZE,
                searchResults.length,
            );
            searchResults = [...searchResults, ...res.items];
            searchTotal = res.total;
        } catch (e: any) {
            error = e.message;
        } finally {
            searching = false;
        }
    }

    function handleSearchInput() {
        if (debounceTimer) clearTimeout(debounceTimer);
        if (!searchQuery.trim()) {
            searchResults = [];
            searchTotal = 0;
            return;
        }
        debounceTimer = setTimeout(() => doSearch(), 250);
    }

    /* ===== Card Click ===== */

    function handleCardClick(id: number, event: MouseEvent) {
        selection.handleClick(id, event, orderedIds);
    }

    function handleCardDblClick(id: number) {
        nav.navigateToEdit(id, { view: "transcripts", transcriptId: id });
    }

    /* ===== Actions ===== */

    function editSelected() {
        if (!selectedEntry) return;
        nav.navigateToEdit(selectedEntry.id, { view: "transcripts", transcriptId: selectedEntry.id });
    }

    function refineSelected() {
        if (!selectedEntry) return;
        nav.navigate("refine", selectedEntry.id);
    }

    function copySelectedText() {
        if (!selectedEntry) return;
        navigator.clipboard.writeText(getDisplayText(selectedEntry));
        copied = true;
        setTimeout(() => (copied = false), 1500);
    }

    async function handleDelete() {
        if (selection.isMulti) {
            const ids = selection.ids;
            try {
                await batchDeleteTranscripts(ids);
                entries = entries.filter((e) => !selection.isSelected(e.id));
                searchResults = searchResults.filter((e) => !selection.isSelected(e.id));
                selection.clear();
            } catch (e: any) {
                error = e.message;
            }
            return;
        }
        if (!selectedEntry) return;
        try {
            await deleteTranscript(selectedEntry.id);
            entries = entries.filter((e) => e.id !== selectedEntry!.id);
            searchResults = searchResults.filter((e) => e.id !== selectedEntry!.id);
            selection.clear();
        } catch (e: any) {
            error = e.message;
        }
    }

    /* ===== Tag Filter ===== */

    function toggleTagFilter(tagId: number) {
        const next = new Set(activeTagIds);
        if (next.has(tagId)) next.delete(tagId);
        else next.add(tagId);
        activeTagIds = next;
        currentPage = 1;
        loadTranscripts();
    }

    function clearTagFilters() {
        activeTagIds = new Set();
        currentPage = 1;
        loadTranscripts();
    }

    function cycleFilterMode() {
        tagFilterMode = tagFilterMode === "any" ? "all" : "any";
        currentPage = 1;
        loadTranscripts();
    }

    /* ===== Pagination & Sort Controls ===== */

    function setPageSize(size: number) {
        pageSize = size;
        currentPage = 1;
        loadTranscripts();
        // Persist to settings (fire-and-forget)
        updateConfig({ user: { page_size: size } }).catch(() => {});
    }

    function setSort(by: string) {
        if (sortBy === by) {
            sortDir = sortDir === "desc" ? "asc" : "desc";
        } else {
            sortBy = by;
            sortDir = "desc";
        }
        currentPage = 1;
        loadTranscripts();
    }

    function goToPage(page: number) {
        if (page < 1 || page > totalPages) return;
        currentPage = page;
        loadTranscripts();
    }

    /* ===== Tag Create ===== */

    async function handleCreateTag() {
        const name = newTagName.trim();
        if (!name) return;
        try {
            await createTag(name, newTagColor);
            newTagName = "";
            showTagCreate = false;
            await loadTags();
        } catch (e: any) {
            error = e.message;
        }
    }

    async function handleDeleteTag(tagId: number) {
        tagMenuId = null;
        try {
            await deleteTag(tagId);
            const next = new Set(activeTagIds);
            next.delete(tagId);
            activeTagIds = next;
            await loadTags();
            await loadTranscripts();
        } catch (e: any) {
            error = e.message;
        }
    }

    /* ===== Tag Context Menu ===== */

    function openTagMenu(tagId: number, event: MouseEvent) {
        event.preventDefault();
        event.stopPropagation();
        const tag = allTags.find((t) => t.id === tagId);
        if (!tag) return;
        tagMenuColor = tag.color ?? "#5a9fd4";
        tagMenuX = Math.min(event.clientX, window.innerWidth - 200);
        tagMenuY = event.clientY;
        tagMenuId = tagId;
    }

    function closeTagMenu() {
        tagMenuId = null;
    }

    async function handleTagColorChange(tagId: number, color: string) {
        try {
            await updateTag(tagId, { color });
            await loadTags();
            await loadTranscripts();
        } catch (e: any) {
            error = e.message;
        }
    }

    /* ===== Tag Assignment Popover ===== */

    function openTagAssign(event?: MouseEvent) {
        event?.stopPropagation();
        if (event?.currentTarget) {
            const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
            tagAssignX = Math.min(rect.left, window.innerWidth - 280);
            tagAssignY = rect.top - 8;
        }
        tagAssignOpen = true;
    }

    function closeTagAssign() {
        tagAssignOpen = false;
    }

    async function toggleTagOnSelected(tagId: number) {
        const ids = selection.ids;
        if (ids.length === 0) return;

        if (ids.length === 1) {
            const entry = filteredEntries.find((e) => e.id === ids[0]);
            if (!entry) return;
            const currentTagIds = entry.tags.map((t) => t.id);
            const newTagIds = currentTagIds.includes(tagId)
                ? currentTagIds.filter((id) => id !== tagId)
                : [...currentTagIds, tagId];
            await assignTags(ids[0], newTagIds);
        } else {
            await batchAssignTags(ids, [tagId]);
        }
        await loadTranscripts();
    }

    /* ===== Keyboard ===== */

    function handleGlobalPointerDown() {
        if (tagAssignOpen) closeTagAssign();
        if (tagMenuId !== null) closeTagMenu();
    }

    function handleGlobalKeydown(event: KeyboardEvent) {
        if (event.key === "Escape") {
            if (tagMenuId !== null) {
                closeTagMenu();
            } else if (tagAssignOpen) {
                closeTagAssign();
            } else if (selection.hasSelection) {
                selection.clear();
            }
        }
        if ((event.ctrlKey || event.metaKey) && event.key === "a") {
            const el = event.target as HTMLElement;
            if (el?.tagName === "INPUT" || el?.tagName === "TEXTAREA") return;
            event.preventDefault();
            selection.selectAll(orderedIds);
        }
    }

    /* ===== Lifecycle ===== */

    onMount(() => {
        // Load page_size from user settings, then load data
        getConfig()
            .then((cfg) => {
                const userCfg = cfg?.user as Record<string, unknown> | undefined;
                const savedSize = Number(userCfg?.page_size);
                if ([25, 50, 100].includes(savedSize)) pageSize = savedSize;
            })
            .catch(() => {})
            .finally(() => {
                Promise.all([loadTranscripts(), loadTags()]).then(() => {
                    const pending = nav.consumePendingTranscriptRequest();
                    if (pending) {
                        selection.selectOnly(pending.id);
                    }
                });
            });

        document.addEventListener("pointerdown", handleGlobalPointerDown);
        document.addEventListener("keydown", handleGlobalKeydown);

        const unsubs = [
            ws.on("transcription_complete", () => loadTranscripts()),
            ws.on("transcript_deleted", (data) => {
                entries = entries.filter((e) => e.id !== data.id);
                searchResults = searchResults.filter((e) => e.id !== data.id);
                if (selection.isSelected(data.id)) selection.clear();
            }),
            ws.on("transcripts_batch_deleted", (data) => {
                const deleted = new Set(data.ids);
                entries = entries.filter((e) => !deleted.has(e.id));
                searchResults = searchResults.filter((e) => !deleted.has(e.id));
            }),
            ws.on("refinement_complete", () => loadTranscripts()),
            ws.on("refinement_error", () => {}),
            ws.on("transcript_updated", () => loadTranscripts()),
            ws.on("tag_created", () => loadTags()),
            ws.on("tag_updated", () => loadTags()),
            ws.on("tag_deleted", () => {
                loadTags();
                loadTranscripts();
            }),
        ];

        return () => {
            unsubs.forEach((fn) => fn());
            document.removeEventListener("pointerdown", handleGlobalPointerDown);
            document.removeEventListener("keydown", handleGlobalKeydown);
            if (debounceTimer) clearTimeout(debounceTimer);
        };
    });
</script>

<!-- ========= TEMPLATE ========= -->

<div class="flex flex-col h-full overflow-hidden bg-[var(--surface-primary)]">
    <!-- === Header: Search + Actions === -->
    <div class="shrink-0 px-4 pt-3 pb-2 flex flex-col gap-2 border-b border-[var(--shell-border)]">
        <!-- Row 1: Search bar -->
        <div class="relative">
            <input
                type="text"
                class="w-full h-9 bg-[var(--surface-secondary)] border border-[var(--shell-border)] rounded-lg text-[var(--text-primary)] text-sm pl-3 pr-8 outline-none transition-colors duration-150 focus:border-[var(--accent)] placeholder:text-[var(--text-tertiary)]"
                placeholder="Search transcripts…"
                bind:value={searchQuery}
                oninput={handleSearchInput}
            />
            {#if searchQuery}
                <button
                    class="absolute right-2.5 top-1/2 -translate-y-1/2 w-5 h-5 text-[var(--text-tertiary)] hover:text-[var(--text-primary)] bg-transparent border-none cursor-pointer p-0 flex items-center justify-center rounded transition-colors"
                    onclick={() => {
                        searchQuery = "";
                        searchResults = [];
                        searchTotal = 0;
                    }}
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

        <!-- Row 2: Tag filter chips -->
        <div class="flex items-center justify-center gap-1.5 flex-wrap min-h-[28px]">
            {#each allTags as tag (tag.id)}
                <button
                    class="inline-flex items-center gap-1 h-6 px-2 rounded-full text-xs font-medium border cursor-pointer transition-all duration-150 select-none"
                    style={activeTagIds.has(tag.id)
                        ? `background: color-mix(in srgb, ${tagColor(tag)} 30%, transparent); border-color: ${tagColor(tag)}; color: var(--text-primary);`
                        : `background: transparent; border-color: var(--shell-border); color: var(--text-tertiary);`}
                    onclick={() => toggleTagFilter(tag.id)}
                    oncontextmenu={(e) => openTagMenu(tag.id, e)}
                    title="Click to filter · Right-click to edit/delete"
                >
                    <span class="w-2 h-2 rounded-full shrink-0" style="background: {tagColor(tag)}"></span>
                    {tag.name}
                    {#if activeTagIds.has(tag.id)}
                        <X size={10} class="ml-0.5 opacity-60" />
                    {/if}
                </button>
            {/each}

            {#if activeTagIds.size > 0}
                <button
                    class="h-6 px-2 rounded-full text-xs font-semibold border border-[var(--accent-muted)] bg-transparent text-[var(--accent)] cursor-pointer transition-colors hover:bg-[var(--hover-overlay)]"
                    onclick={cycleFilterMode}
                    title="Toggle between matching ANY or ALL selected tags"
                >
                    {tagFilterMode === "any" ? "ANY" : "ALL"}
                </button>
                <button
                    class="h-6 px-1.5 rounded-full text-xs text-[var(--text-tertiary)] bg-transparent border-none cursor-pointer hover:text-[var(--text-primary)] transition-colors"
                    onclick={clearTagFilters}
                >
                    Clear
                </button>
            {/if}

            {#if allTags.length > 0}
                <div class="w-px h-4 bg-[var(--shell-border)] mx-0.5"></div>
            {/if}

            <!-- Inline tag creation -->
            {#if showTagCreate}
                <form
                    class="inline-flex items-center gap-1"
                    onsubmit={(e) => {
                        e.preventDefault();
                        handleCreateTag();
                    }}
                >
                    <input
                        type="color"
                        class="w-5 h-5 border-none rounded cursor-pointer p-0 bg-transparent"
                        bind:value={newTagColor}
                    />
                    <input
                        type="text"
                        class="h-6 w-24 px-1.5 rounded text-xs bg-[var(--surface-secondary)] border border-[var(--shell-border)] text-[var(--text-primary)] outline-none focus:border-[var(--accent)]"
                        placeholder="Tag name"
                        bind:value={newTagName}
                    />
                    <button
                        type="submit"
                        class="w-5 h-5 rounded bg-[var(--accent)] text-[var(--gray-0)] border-none cursor-pointer flex items-center justify-center"
                        disabled={!newTagName.trim()}
                    >
                        <Check size={11} />
                    </button>
                    <button
                        type="button"
                        class="w-5 h-5 rounded bg-transparent text-[var(--text-tertiary)] border-none cursor-pointer flex items-center justify-center hover:text-[var(--text-primary)]"
                        onclick={() => {
                            showTagCreate = false;
                            newTagName = "";
                        }}
                    >
                        <X size={11} />
                    </button>
                </form>
            {:else}
                <button
                    class="inline-flex items-center gap-1 h-6 px-2 rounded-full text-xs text-[var(--text-tertiary)] bg-transparent border border-dashed border-[var(--shell-border)] cursor-pointer transition-colors hover:text-[var(--accent)] hover:border-[var(--accent)]"
                    onclick={() => (showTagCreate = true)}
                    title={allTags.length > 0 ? "Create new tag" : "Create your first tag"}
                >
                    <Plus size={10} />
                    {allTags.length > 0 ? "Tag" : "Create a tag"}
                </button>
            {/if}
        </div>
    </div>

    <!-- === Controls row: result count + sort + per-page === -->
    <div class="shrink-0 px-4 py-1.5 flex items-center gap-3 text-[13px] text-[var(--text-tertiary)]">
        <!-- Result count (left) -->
        <span class="shrink-0">
            {#if isSearching && !searching}
                {#if searchTotal > filteredEntries.length}
                    Showing {filteredEntries.length} of {searchTotal} results for "{searchQuery}"
                {:else}
                    {filteredEntries.length} result{filteredEntries.length !== 1 ? "s" : ""} for "{searchQuery}"
                {/if}
            {:else if !loading}
                {displayTotal} transcript{displayTotal !== 1 ? "s" : ""}
                {#if activeTagIds.size > 0}
                    <span class="text-[var(--accent)]">(filtered)</span>
                {/if}
            {/if}
        </span>

        <div class="flex-1"></div>

        <!-- Sort control (right, browse mode only) -->
        {#if !isSearching}
            <div class="flex items-center gap-1 shrink-0">
                <ArrowUpDown size={12} class="text-[var(--text-tertiary)]" />
                {#each SORT_OPTIONS as opt (opt.value)}
                    <button
                        class="h-6 px-1.5 rounded text-[11px] border-none cursor-pointer transition-colors"
                        class:bg-[var(--hover-overlay)]={sortBy === opt.value}
                        class:text-[var(--text-primary)]={sortBy === opt.value}
                        class:font-semibold={sortBy === opt.value}
                        class:bg-transparent={sortBy !== opt.value}
                        class:text-[var(--text-tertiary)]={sortBy !== opt.value}
                        class:hover:text-[var(--text-secondary)]={sortBy !== opt.value}
                        onclick={() => setSort(opt.value)}
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

            <!-- Per-page selector -->
            <div class="flex items-center gap-0.5 shrink-0 border-l border-[var(--shell-border)] pl-3">
                {#each PAGE_SIZES as size (size)}
                    <button
                        class="h-6 px-1.5 rounded text-[11px] border-none cursor-pointer transition-colors"
                        class:bg-[var(--hover-overlay)]={pageSize === size}
                        class:text-[var(--text-primary)]={pageSize === size}
                        class:font-semibold={pageSize === size}
                        class:bg-transparent={pageSize !== size}
                        class:text-[var(--text-tertiary)]={pageSize !== size}
                        class:hover:text-[var(--text-secondary)]={pageSize !== size}
                        onclick={() => setPageSize(size)}
                    >
                        {size}
                    </button>
                {/each}
                <span class="text-[10px] text-[var(--text-tertiary)] ml-0.5">/ page</span>
            </div>
        {/if}
    </div>

    <!-- === Card List === -->
    <div class="flex-1 overflow-y-auto px-4 pb-2">
        {#if loading}
            <div class="flex flex-col items-center justify-center gap-2 h-[200px] text-[var(--text-tertiary)] text-sm">
                <Loader2 size={20} class="animate-spin" /><span>Loading…</span>
            </div>
        {:else if error}
            <div class="flex flex-col items-center justify-center gap-2 h-[200px] text-[var(--color-danger)] text-sm">
                {error}
            </div>
        {:else if filteredEntries.length === 0}
            <div class="flex flex-col items-center justify-center gap-3 h-[200px] text-[var(--text-tertiary)] text-sm">
                <FileText size={32} strokeWidth={1} />
                <span>
                    {#if isSearching}
                        No results for "{searchQuery}"
                    {:else if activeTagIds.size > 0}
                        No transcripts match selected tags
                    {:else}
                        No transcripts yet
                    {/if}
                </span>
            </div>
        {:else}
            <div class="flex flex-col gap-1.5 pt-1">
                {#each filteredEntries as entry (entry.id)}
                    <button
                        class="w-full text-left p-3 rounded-lg border cursor-pointer transition-all duration-150 group/card"
                        class:bg-[var(--hover-overlay-blue)]={selection.isSelected(entry.id)}
                        class:border-[var(--accent)]={selection.isSelected(entry.id)}
                        class:bg-[var(--surface-secondary)]={!selection.isSelected(entry.id)}
                        class:border-[var(--shell-border)]={!selection.isSelected(entry.id)}
                        class:hover:border-[var(--accent-muted)]={!selection.isSelected(entry.id)}
                        class:hover:bg-[var(--hover-overlay)]={!selection.isSelected(entry.id)}
                        onclick={(e) => handleCardClick(entry.id, e)}
                        ondblclick={() => handleCardDblClick(entry.id)}
                    >
                        <!-- Title row -->
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

                        <!-- Text preview -->
                        <p class="text-[15px] text-[var(--text-secondary)] leading-relaxed m-0 mb-2 line-clamp-2">
                            {#if isSearching}
                                {@html highlight(truncate(getDisplayText(entry)), searchQuery)}
                            {:else}
                                {truncate(getDisplayText(entry))}
                            {/if}
                        </p>

                        <!-- Bottom row: tags + metadata -->
                        <div class="flex items-center gap-2 flex-wrap pt-1.5 mt-0.5">
                            {#each entry.tags as tag (tag.id)}
                                <span
                                    class="inline-flex items-center gap-1 h-5 px-1.5 rounded-full text-[10px] font-medium"
                                    style="background: color-mix(in srgb, {tagColor(
                                        tag,
                                    )} 25%, transparent); color: var(--text-primary);"
                                >
                                    <span class="w-1.5 h-1.5 rounded-full" style="background: {tagColor(tag)}"></span>
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
                    <StyledButton size="sm" variant="secondary" onclick={loadMore} disabled={searching}>
                        {#if searching}<Loader2 size={14} class="animate-spin" /> Loading…{:else}Load More ({searchTotal -
                                searchResults.length} remaining){/if}
                    </StyledButton>
                </div>
            {:else if !isSearching && totalPages > 1}
                <div class="flex items-center justify-center gap-3 py-3 text-[13px]">
                    <button
                        class="flex items-center gap-1 h-7 px-2 rounded text-[var(--text-secondary)] bg-transparent border border-[var(--shell-border)] cursor-pointer transition-colors hover:bg-[var(--hover-overlay)] disabled:opacity-30 disabled:cursor-default"
                        onclick={() => goToPage(currentPage - 1)}
                        disabled={currentPage <= 1}
                    >
                        <ChevronLeft size={14} /> Prev
                    </button>
                    <span class="text-[var(--text-tertiary)] tabular-nums">
                        Page {currentPage} of {totalPages}
                    </span>
                    <button
                        class="flex items-center gap-1 h-7 px-2 rounded text-[var(--text-secondary)] bg-transparent border border-[var(--shell-border)] cursor-pointer transition-colors hover:bg-[var(--hover-overlay)] disabled:opacity-30 disabled:cursor-default"
                        onclick={() => goToPage(currentPage + 1)}
                        disabled={currentPage >= totalPages}
                    >
                        Next <ChevronRight size={14} />
                    </button>
                </div>
            {/if}
        {/if}
    </div>

    <!-- === Bottom Action Bar === -->
    {#if selection.hasSelection}
        <div
            class="shrink-0 flex items-center gap-2 px-4 py-2.5 border-t border-[var(--shell-border)] bg-[var(--surface-secondary)]"
        >
            <span class="text-xs font-semibold text-[var(--accent)]">
                {selection.count} selected
            </span>

            {#if selection.count === 1}
                <StyledButton size="sm" variant="secondary" onclick={editSelected}>
                    <Pencil size={13} /> Edit
                </StyledButton>
                <StyledButton size="sm" variant="secondary" onclick={refineSelected}>
                    <Sparkles size={13} /> Refine
                </StyledButton>
                <StyledButton size="sm" variant="secondary" onclick={copySelectedText}>
                    {#if copied}<Check size={13} /> Copied{:else}<Copy size={13} /> Copy{/if}
                </StyledButton>
            {/if}

            <StyledButton size="sm" variant="secondary" onclick={openTagAssign}>
                <TagIcon size={13} /> Tag{selection.isMulti ? ` ${selection.count}` : ""}
            </StyledButton>

            <div class="flex-1"></div>

            <button
                class="text-xs text-[var(--text-tertiary)] bg-transparent border-none cursor-pointer hover:text-[var(--text-primary)] transition-colors"
                onclick={() => selection.clear()}
            >
                Clear
            </button>

            <StyledButton size="sm" variant="destructive" onclick={handleDelete}>
                <Trash2 size={13} />
                {selection.isMulti ? `Delete ${selection.count}` : "Delete"}
            </StyledButton>
        </div>
    {/if}
</div>

<!-- === Tag Assignment Popover === -->
{#if tagAssignOpen}
    <div class="fixed inset-0 z-[199]" onclick={closeTagAssign} role="presentation"></div>
    <div
        class="fixed min-w-[220px] max-w-[300px] max-h-[320px] overflow-y-auto bg-[var(--surface-primary)] border border-[var(--shell-border)] rounded-lg shadow-[0_12px_28px_rgba(0,0,0,0.45)] py-1 z-[200]"
        style="left: {tagAssignX}px; bottom: {window.innerHeight - tagAssignY}px"
        role="menu"
        tabindex="-1"
        onpointerdown={(e) => e.stopPropagation()}
    >
        <div class="px-3 py-1.5 text-[11px] uppercase tracking-wide text-[var(--text-tertiary)]">
            {selection.isMulti ? `Tag ${selection.count} transcripts` : "Toggle tags"}
        </div>
        {#if allTags.length === 0}
            <div class="px-3 py-2 text-xs text-[var(--text-tertiary)]">No tags yet. Create one above.</div>
        {:else}
            {#each allTags as tag (tag.id)}
                {@const isOn = selectedEntry ? selectedEntry.tags.some((t) => t.id === tag.id) : false}
                <button
                    class="w-full flex items-center gap-2 px-3 py-1.5 border-none bg-transparent text-left text-sm cursor-pointer transition-colors duration-150 hover:bg-[var(--hover-overlay)] text-[var(--text-primary)]"
                    onclick={() => toggleTagOnSelected(tag.id)}
                    role="menuitem"
                >
                    <span class="w-2.5 h-2.5 rounded-full shrink-0" style="background: {tagColor(tag)}"></span>
                    <span class="flex-1 truncate">{tag.name}</span>
                    {#if isOn}
                        <Check size={13} class="text-[var(--accent)] shrink-0" />
                    {/if}
                </button>
            {/each}
        {/if}
    </div>
{/if}

<!-- === Tag Context Menu (right-click on tag chip) === -->
{#if tagMenuId !== null}
    <div
        class="fixed inset-0 z-[249]"
        onclick={closeTagMenu}
        oncontextmenu={(e) => {
            e.preventDefault();
            closeTagMenu();
        }}
        role="presentation"
    ></div>
    <div
        class="fixed w-[180px] bg-[var(--surface-primary)] border border-[var(--shell-border)] rounded-lg shadow-[0_12px_28px_rgba(0,0,0,0.45)] py-1 z-[250]"
        style="left: {tagMenuX}px; top: {tagMenuY}px;"
        role="menu"
        tabindex="-1"
        onpointerdown={(e) => e.stopPropagation()}
    >
        <div class="px-3 py-1.5 text-[11px] uppercase tracking-wide text-[var(--text-tertiary)]">Edit tag</div>
        <!-- Color picker row -->
        <div class="flex items-center gap-2 px-3 py-1.5">
            <Palette size={13} class="text-[var(--text-tertiary)] shrink-0" />
            <span class="text-xs text-[var(--text-secondary)]">Color</span>
            <div class="flex-1"></div>
            <input
                type="color"
                class="w-6 h-6 border border-[var(--shell-border)] rounded cursor-pointer p-0 bg-transparent"
                value={tagMenuColor}
                onchange={(e) => {
                    const target = e.currentTarget as HTMLInputElement;
                    if (tagMenuId !== null) {
                        tagMenuColor = target.value;
                        handleTagColorChange(tagMenuId, target.value);
                    }
                }}
            />
        </div>
        <!-- Divider -->
        <div class="h-px bg-[var(--shell-border)] mx-2 my-1"></div>
        <!-- Delete -->
        <button
            class="w-full flex items-center gap-2 px-3 py-1.5 border-none bg-transparent text-left text-xs cursor-pointer transition-colors duration-150 hover:bg-[color-mix(in_srgb,var(--color-danger)_15%,transparent)] text-[var(--color-danger)]"
            onclick={() => {
                if (tagMenuId !== null) handleDeleteTag(tagMenuId);
            }}
            role="menuitem"
        >
            <Trash2 size={13} />
            Delete tag
        </button>
    </div>
{/if}

<style>
    :global(.search-hl) {
        background: rgba(90, 159, 212, 0.3);
        color: inherit;
        border-radius: 2px;
        padding: 0 1px;
    }
</style>
