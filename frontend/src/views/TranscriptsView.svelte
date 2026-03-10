<script lang="ts">
    import {
        getTranscripts,
        getConfig,
        updateConfig,
        updateTag,
        searchTranscripts,
        deleteTranscript,
        batchDeleteTranscripts,
        bulkRefineTranscripts,
        cancelBulkRefinement,
        getTags,
        createTag,
        deleteTag,
        assignTags,
        batchToggleTag,
        type Transcript,
        type Tag,
        type SearchResult,
    } from "../lib/api";
    import { ws } from "../lib/ws";
    import { toast } from "../lib/toast.svelte";
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
        Check,
        Copy,
        ChevronLeft,
        ChevronRight,
        ArrowUpDown,
        Minus,
        Hammer,
    } from "lucide-svelte";
    import StyledButton from "../lib/components/StyledButton.svelte";
    import EmptyState from "../lib/components/EmptyState.svelte";
    import TagBar from "../lib/components/TagBar.svelte";
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

    // Tag assignment popover
    let tagAssignOpen = $state(false);
    let tagAssignX = $state(0);
    let tagAssignY = $state(0);

    // Copy feedback
    let copied = $state(false);

    // Bulk refinement state
    let bulkRefineActive = $state(false);
    let bulkRefineCompleted = $state(0);
    let bulkRefineFailed = $state(0);
    let bulkRefineTotal = $state(0);
    let spotCheckRemaining: number[] | null = $state(null);
    const SPOT_CHECK_SIZE = 10;
    const DEFAULT_REFINEMENT_LEVEL = 2;

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

    async function handleBulkRefine() {
        const ids = selection.ids;
        if (ids.length === 0) return;

        // Single selection → navigate to RefineView for preview
        if (ids.length === 1) {
            refineSelected();
            return;
        }

        const total = ids.length;
        const spotCheckCount = Math.min(SPOT_CHECK_SIZE, total);

        if (total > spotCheckCount) {
            // Offer spot-check gate
            const choice = await toast.confirm({
                title: `Refine ${total} Transcripts`,
                message: `Bulk refinement will auto-commit refined text for each transcript.\n\nRecommended: spot-check the first ${spotCheckCount} to verify quality before processing all ${total}.`,
                confirmLabel: `Spot-Check First ${spotCheckCount}`,
                cancelLabel: "Cancel",
            });

            if (!choice) return;

            // Spot-check: process first batch, stash remainder
            spotCheckRemaining = ids.slice(spotCheckCount);
            await startBulkRefine(ids.slice(0, spotCheckCount));
        } else {
            // Small enough to just do it, but still confirm
            const confirmed = await toast.confirm({
                title: `Refine ${total} Transcripts`,
                message: `This will refine and auto-commit ${total} transcripts. Refined text replaces the current version. Individual transcripts can be reverted from Edit view.`,
                confirmLabel: `Refine All ${total}`,
                cancelLabel: "Cancel",
            });
            if (!confirmed) return;
            spotCheckRemaining = null;
            await startBulkRefine(ids);
        }
    }

    async function startBulkRefine(ids: number[]) {
        bulkRefineActive = true;
        bulkRefineCompleted = 0;
        bulkRefineFailed = 0;
        bulkRefineTotal = ids.length;
        try {
            await bulkRefineTranscripts(ids, DEFAULT_REFINEMENT_LEVEL);
        } catch (e: any) {
            toast.error(`Bulk refine failed: ${e.message}`);
            bulkRefineActive = false;
        }
    }

    async function handleCancelBulkRefine() {
        try {
            await cancelBulkRefinement();
        } catch (e: any) {
            toast.error(`Cancel failed: ${e.message}`);
        }
    }

    async function handleSpotCheckContinue() {
        if (!spotCheckRemaining?.length) return;
        const remaining = spotCheckRemaining;
        const confirmed = await toast.confirm({
            title: `Continue Bulk Refinement`,
            message: `Spot-check complete (${bulkRefineCompleted} refined, ${bulkRefineFailed} failed). Continue with remaining ${remaining.length} transcripts?`,
            confirmLabel: `Refine Remaining ${remaining.length}`,
            cancelLabel: "Stop Here",
        });
        spotCheckRemaining = null;
        if (!confirmed) return;
        await startBulkRefine(remaining);
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
                toast.success(`Deleted ${ids.length} transcripts`);
            } catch (e: any) {
                error = e.message;
                toast.error(`Delete failed: ${e.message}`);
            }
            return;
        }
        if (!selectedEntry) return;
        try {
            await deleteTranscript(selectedEntry.id);
            entries = entries.filter((e) => e.id !== selectedEntry!.id);
            searchResults = searchResults.filter((e) => e.id !== selectedEntry!.id);
            selection.clear();
            toast.success("Transcript deleted");
        } catch (e: any) {
            error = e.message;
            toast.error(`Delete failed: ${e.message}`);
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

    async function handleCreateTag(name: string, color: string) {
        try {
            await createTag(name, color);
            await loadTags();
            toast.success(`Tag "${name}" created`);
        } catch (e: any) {
            error = e.message;
            toast.error(`Tag creation failed: ${e.message}`);
        }
    }

    async function handleDeleteTag(tagId: number) {
        try {
            await deleteTag(tagId);
            const next = new Set(activeTagIds);
            next.delete(tagId);
            activeTagIds = next;
            await loadTags();
            await loadTranscripts();
            toast.success("Tag deleted");
        } catch (e: any) {
            error = e.message;
            toast.error(`Tag deletion failed: ${e.message}`);
        }
    }

    /* ===== Tag Context Menu ===== */

    async function handleTagColorChange(tagId: number, color: string) {
        try {
            await updateTag(tagId, { color });
            await loadTags();
            await loadTranscripts();
        } catch (e: any) {
            error = e.message;
            toast.error(`Failed to update tag color: ${e.message}`);
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

        try {
            if (ids.length === 1) {
                // Single-select: replace the full tag set via existing endpoint
                const entry = filteredEntries.find((e) => e.id === ids[0]);
                if (!entry) return;
                const currentTagIds = entry.tags.map((t) => t.id);
                const newTagIds = currentTagIds.includes(tagId)
                    ? currentTagIds.filter((id) => id !== tagId)
                    : [...currentTagIds, tagId];
                await assignTags(ids[0], newTagIds);
            } else {
                // Multi-select: add if not all selected have the tag; remove if all do.
                // Preserves every other tag on each transcript.
                const selectedTranscripts = ids
                    .map((id) => filteredEntries.find((e) => e.id === id))
                    .filter(Boolean) as Transcript[];
                const allHave = selectedTranscripts.every((t) => t.tags.some((tag) => tag.id === tagId));
                await batchToggleTag(ids, tagId, !allHave);
            }
            await loadTranscripts();
        } catch (e: any) {
            toast.error(`Tag update failed: ${e.message}`);
        }
    }

    /* ===== Keyboard ===== */

    function handleGlobalPointerDown() {
        if (tagAssignOpen) closeTagAssign();
    }

    function handleGlobalKeydown(event: KeyboardEvent) {
        if (event.key === "Escape") {
            if (tagAssignOpen) {
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
            ws.on("transcript_updated", () => loadTranscripts()),
            ws.on("bulk_refinement_progress", (data) => {
                bulkRefineCompleted = data.completed;
                bulkRefineFailed = data.failed;
            }),
            ws.on("bulk_refinement_complete", (data) => {
                bulkRefineActive = false;
                const msg = data.cancelled
                    ? `Bulk refinement cancelled (${data.completed}/${data.total} done)`
                    : data.failed > 0
                      ? `Refined ${data.completed} of ${data.total} (${data.failed} failed)`
                      : `Refined ${data.completed} transcripts`;
                if (data.cancelled || data.failed > 0) toast.warning(msg);
                else toast.success(msg);
                loadTranscripts();
                if (spotCheckRemaining?.length && !data.cancelled) {
                    handleSpotCheckContinue();
                } else {
                    spotCheckRemaining = null;
                    selection.clear();
                }
            }),
            ws.on("bulk_refinement_error", (data) => {
                bulkRefineActive = false;
                spotCheckRemaining = null;
                toast.error(`Bulk refinement error: ${data.message}`);
            }),
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
    <div class="w-full h-full mx-auto lg:max-w-[80%] flex flex-col overflow-hidden">
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
            <TagBar
                tags={allTags}
                activeIds={activeTagIds}
                ontoggle={toggleTagFilter}
                oncreate={handleCreateTag}
                ondelete={handleDeleteTag}
                oncolorchange={handleTagColorChange}
            >
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
            </TagBar>
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
            {#if selection.hasSelection}
                <span class="text-xs font-semibold text-[var(--accent)]">{selection.count} selected</span>
            {/if}

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
        <div class="flex-1 overflow-y-auto px-4 pb-2" style="scrollbar-gutter: stable">
            {#if loading}
                <EmptyState icon={Loader2} message="Loading…" height="fixed" spinning />
            {:else if error}
                <EmptyState message={error} height="fixed" />
            {:else if filteredEntries.length === 0}
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
                                        {#if tag.is_system}
                                            <Hammer size={9} class="shrink-0" />
                                        {:else}
                                            <span class="w-1.5 h-1.5 rounded-full" style="background: {tagColor(tag)}"
                                            ></span>
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
        {#if bulkRefineActive}
            <div class="shrink-0 px-4 py-2 overflow-y-auto" style="scrollbar-gutter: stable">
                <div class="flex items-center gap-3 bg-[var(--surface-secondary)] rounded-lg px-3 py-1.5">
                    <Loader2 size={14} class="animate-spin text-[var(--accent)] shrink-0" />
                    <span class="text-sm text-[var(--text-secondary)]">
                        Refining {bulkRefineCompleted} of {bulkRefineTotal}…
                        {#if bulkRefineFailed > 0}
                            <span class="text-[var(--text-warning)]">({bulkRefineFailed} failed)</span>
                        {/if}
                    </span>
                    <div class="flex-1 h-1.5 rounded-full bg-[var(--shell-border)] overflow-hidden">
                        <div
                            class="h-full rounded-full bg-[var(--accent)] transition-all duration-300"
                            style="width: {bulkRefineTotal > 0
                                ? ((bulkRefineCompleted + bulkRefineFailed) / bulkRefineTotal) * 100
                                : 0}%"
                        ></div>
                    </div>
                    <StyledButton size="sm" variant="secondary" onclick={handleCancelBulkRefine}>
                        <X size={13} /> Cancel
                    </StyledButton>
                </div>
            </div>
        {:else if selection.hasSelection}
            <div class="shrink-0 px-4 py-2 overflow-y-auto" style="scrollbar-gutter: stable">
                <div class="flex items-center gap-2 bg-[var(--surface-secondary)] rounded-lg px-3 py-1.5">
                    <StyledButton size="sm" variant="destructive" onclick={handleDelete}>
                        <Trash2 size={13} />
                        {selection.isMulti ? `Delete ${selection.count}` : "Delete"}
                    </StyledButton>

                    <div class="flex-1"></div>

                    {#if selection.count === 1}
                        <StyledButton size="sm" variant="secondary" onclick={editSelected}>
                            <Pencil size={13} /> Edit
                        </StyledButton>
                        <StyledButton size="sm" variant="secondary" onclick={copySelectedText}>
                            {#if copied}<Check size={13} /> Copied{:else}<Copy size={13} /> Copy{/if}
                        </StyledButton>
                    {/if}

                    <StyledButton size="sm" variant="secondary" onclick={openTagAssign}>
                        <TagIcon size={13} /> Tag
                    </StyledButton>

                    <StyledButton size="sm" variant="primary" onclick={handleBulkRefine}>
                        <Sparkles size={13} />
                        {selection.isMulti ? `Refine ${selection.count}` : "Refine"}
                    </StyledButton>
                </div>
            </div>
        {/if}
    </div>
</div>

<!-- === Tag Assignment Popover === -->
{#if tagAssignOpen}
    <div class="fixed inset-0 z-[199]" onclick={closeTagAssign} role="presentation"></div>
    <div
        class="fixed min-w-[220px] max-w-[300px] max-h-[320px] overflow-y-auto bg-[var(--surface-primary)] border border-[var(--shell-border)] rounded-lg shadow-[0_12px_28px_rgba(0,0,0,0.45)] py-1 z-[200] -translate-y-full"
        style="left: {tagAssignX}px; top: {tagAssignY}px"
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
            {#each allTags.filter((t) => !t.is_system) as tag (tag.id)}
                {@const isOn = selectedEntry ? selectedEntry.tags.some((t) => t.id === tag.id) : false}
                {@const multiSelected = selection.isMulti
                    ? (selection.ids
                          .map((id) => filteredEntries.find((e) => e.id === id))
                          .filter(Boolean) as Transcript[])
                    : []}
                {@const allHave =
                    selection.isMulti && multiSelected.every((t) => t.tags.some((tt) => tt.id === tag.id))}
                {@const someHave =
                    selection.isMulti && !allHave && multiSelected.some((t) => t.tags.some((tt) => tt.id === tag.id))}
                <button
                    class="w-full flex items-center gap-2 px-3 py-1.5 border-none bg-transparent text-left text-sm cursor-pointer transition-colors duration-150 hover:bg-[var(--hover-overlay)] text-[var(--text-primary)]"
                    onclick={() => toggleTagOnSelected(tag.id)}
                    role="menuitem"
                >
                    <span class="w-2.5 h-2.5 rounded-full shrink-0" style="background: {tagColor(tag)}"></span>
                    <span class="flex-1 truncate">{tag.name}</span>
                    {#if isOn || allHave}
                        <Check size={13} class="text-[var(--accent)] shrink-0" />
                    {:else if someHave}
                        <Minus size={13} class="text-[var(--text-tertiary)] shrink-0" />
                    {/if}
                </button>
            {/each}
        {/if}
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
