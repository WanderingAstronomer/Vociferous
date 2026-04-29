<script lang="ts">
    import {
        clearDefaultRefinementPrompt,
        setDefaultRefinementPrompt,
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
        retranscribeTranscript,
        exportFile,
        type Transcript,
        type Tag,
        type SearchResult,
    } from "../lib/api";
    import { buildExportPayload, type ExportFormat } from "../lib/exportUtils";
    import { ws } from "../lib/ws";
    import { toast } from "../lib/toast.svelte";
    import { nav } from "../lib/navigation.svelte";
    import { SelectionManager } from "../lib/selection.svelte";
    import { onMount } from "svelte";
    import {
        X,
        Loader2,
        FileText,
        Trash2,
        Pencil,
        Sparkles,
        Tag as TagIcon,
        Check,
        Copy,
        Minus,
        Hammer,
        Mic,
        RefreshCw,
        Download,
    } from "lucide-svelte";
    import StyledButton from "../lib/components/StyledButton.svelte";
    import { getZoomFactor } from "../lib/zoom";
    import TranscriptsHeader from "../lib/components/transcripts/TranscriptsHeader.svelte";
    import TranscriptsListPane from "../lib/components/transcripts/TranscriptsListPane.svelte";
    import TranscriptsSelectionBar from "../lib/components/transcripts/TranscriptsSelectionBar.svelte";

    /* ===== State ===== */

    let entries: Transcript[] = $state([]);
    let totalCount = $state(0);
    let loading = $state(true);
    let error = $state("");

    // Pagination & Sort
    let pageSize = $state(25);
    let currentPage = $state(1);
    let sortBy = $state("created_at");
    let sortDir: "asc" | "desc" = $state("desc");

    const PAGE_SIZES = [10, 25, 50] as const;
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

    // Export
    let exportOpen = $state(false);
    let exporting = $state(false);
    let exportBtnEl: HTMLElement | undefined = $state(undefined);

    // Bulk refinement state
    let bulkRefineActive = $state(false);
    let bulkRefineCompleted = $state(0);
    let bulkRefineFailed = $state(0);
    let bulkRefineTotal = $state(0);
    let bulkSkipRefined = $state(true);
    let spotCheckRemaining: number[] | null = $state(null);
    const SPOT_CHECK_SIZE = 10;
    const DEFAULT_REFINEMENT_LEVEL = 2;
    let defaultPromptId: number | null = $state(null);

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
    let selectedEntryIsPrompt = $derived(selectedEntry?.tags.some((tag) => tag.name === "Prompt") ?? false);
    let selectedEntryIsDefaultPrompt = $derived(selectedEntry?.id === defaultPromptId);

    function getDisplayText(entry: Transcript): string {
        return entry.normalized_text || entry.raw_text || "";
    }

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

    function handleSearchQueryChange(value: string) {
        searchQuery = value;
        handleSearchInput();
    }

    function clearSearchQuery() {
        searchQuery = "";
        searchResults = [];
        searchTotal = 0;
    }

    function handleExportAnchorChange(element: HTMLElement | undefined) {
        exportBtnEl = element;
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

    function continueRecording() {
        if (!selectedEntry) return;
        nav.navigateToAppendMode(selectedEntry.id);
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
        const offerSpotCheck = total > spotCheckCount;

        const confirmed = await toast.confirm({
            title: `Refine ${total} Transcripts`,
            message: `This will refine and auto-commit ${total} transcripts. Refined text replaces the current version. Individual transcripts can be reverted from Edit view.`,
            confirmLabel: `Refine All ${total}`,
            cancelLabel: "Cancel",
            alternativeLabel: offerSpotCheck ? `Spot-Check First ${spotCheckCount}` : undefined,
            checkboxLabel: "Skip already-refined transcripts",
            checkboxDefault: true,
        });

        if (!confirmed) return;
        bulkSkipRefined = toast.lastCheckboxValue;

        if (offerSpotCheck && toast.lastConfirmWasAlternative) {
            // Spot-check path: process first batch, stash remainder
            spotCheckRemaining = ids.slice(spotCheckCount);
            await startBulkRefine(ids.slice(0, spotCheckCount));
        } else {
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
            await bulkRefineTranscripts(ids, DEFAULT_REFINEMENT_LEVEL, "", bulkSkipRefined);
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
        navigator.clipboard.writeText(getDisplayText(selectedEntry)).catch(() => {});
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

    async function handleSetSelectedAsDefaultPrompt() {
        if (!selectedEntry) return;
        try {
            await setDefaultRefinementPrompt(selectedEntry.id);
            defaultPromptId = selectedEntry.id;
            toast.success("Default refinement prompt updated");
        } catch (e: any) {
            toast.error(`Failed to set default prompt: ${e.message}`);
        }
    }

    async function handleClearDefaultPrompt() {
        try {
            await clearDefaultRefinementPrompt();
            defaultPromptId = null;
            toast.success("Default refinement prompt cleared");
        } catch (e: any) {
            toast.error(`Failed to clear default prompt: ${e.message}`);
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
            const z = getZoomFactor();
            const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
            tagAssignX = Math.min(rect.left / z, window.innerWidth / z - 280);
            tagAssignY = Math.max(rect.top / z - 8, 328);
        }
        tagAssignOpen = true;
    }

    function closeTagAssign() {
        tagAssignOpen = false;
    }

    /* ===== Export ===== */

    async function handleExport(format: ExportFormat) {
        exportOpen = false;
        exporting = true;
        try {
            // Gather transcripts: selected IDs from in-memory data
            const selectedIds = new Set(selection.ids);
            const selected = filteredEntries.filter((e) => selectedIds.has(e.id));

            if (selected.length === 0) {
                toast.error("No transcripts selected");
                return;
            }

            const { filename, content } = buildExportPayload(selected, format);
            const result = await exportFile(content, filename);
            toast.success(
                `Exported ${selected.length} transcript${selected.length !== 1 ? "s" : ""} to ${result.path}`,
            );
        } catch (e: any) {
            if (e?.error === "cancelled" || e?.message?.includes("cancelled")) {
                toast.info("Export cancelled");
                return;
            }
            toast.error(e?.message || "Export failed");
        } finally {
            exporting = false;
        }
    }

    function toggleExportPopover(event?: MouseEvent) {
        event?.stopPropagation();
        exportOpen = !exportOpen;
    }

    function closeExportPopover() {
        exportOpen = false;
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
        if (exportOpen) closeExportPopover();
    }

    function handleGlobalKeydown(event: KeyboardEvent) {
        if (event.key === "Escape") {
            if (exportOpen) {
                closeExportPopover();
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
                const refinementCfg = cfg?.refinement as Record<string, unknown> | undefined;
                const savedSize = Number(userCfg?.page_size);
                if ([25, 50, 100].includes(savedSize)) pageSize = savedSize;
                defaultPromptId =
                    typeof refinementCfg?.default_prompt_transcript_id === "number"
                        ? refinementCfg.default_prompt_transcript_id
                        : null;
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
            ws.on("bulk_refinement_started", (data) => {
                bulkRefineTotal = data.total;
            }),
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
            ws.on("config_updated", (data) => {
                const refinement = data.refinement as Record<string, unknown> | undefined;
                defaultPromptId =
                    typeof refinement?.default_prompt_transcript_id === "number"
                        ? refinement.default_prompt_transcript_id
                        : null;
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
        <TranscriptsHeader
            {searchQuery}
            {searching}
            {searchTotal}
            filteredCount={filteredEntries.length}
            {isSearching}
            {allTags}
            {activeTagIds}
            {tagFilterMode}
            {sortBy}
            {sortDir}
            sortOptions={SORT_OPTIONS}
            {currentPage}
            {totalPages}
            {pageSize}
            pageSizes={PAGE_SIZES}
            onSearchChange={handleSearchQueryChange}
            onClearSearch={clearSearchQuery}
            onToggleTagFilter={toggleTagFilter}
            onCreateTag={handleCreateTag}
            onDeleteTag={handleDeleteTag}
            onTagColorChange={handleTagColorChange}
            onCycleFilterMode={cycleFilterMode}
            onClearTagFilters={clearTagFilters}
            onSetSort={setSort}
            onGoToPage={goToPage}
            onSetPageSize={setPageSize}
        />

        <TranscriptsListPane
            entries={filteredEntries}
            {loading}
            {error}
            {isSearching}
            {searchQuery}
            {activeTagIds}
            {selection}
            {defaultPromptId}
            {hasMore}
            {searching}
            remainingSearchCount={searchTotal - searchResults.length}
            {displayTotal}
            onCardClick={handleCardClick}
            onCardDoubleClick={handleCardDblClick}
            onLoadMore={loadMore}
        />

        <TranscriptsSelectionBar
            {bulkRefineActive}
            {bulkRefineCompleted}
            {bulkRefineFailed}
            {bulkRefineTotal}
            {selection}
            {copied}
            {exporting}
            {selectedEntry}
            {selectedEntryIsPrompt}
            {selectedEntryIsDefaultPrompt}
            onCancelBulkRefine={handleCancelBulkRefine}
            onDelete={handleDelete}
            onContinueRecording={continueRecording}
            onEditSelected={editSelected}
            onCopySelectedText={copySelectedText}
            onRetranscribeSelected={async () => {
                if (!selectedEntry) return;
                try {
                    await retranscribeTranscript(selectedEntry.id);
                    toast.info("Re-transcription queued");
                } catch {
                    toast.error("Failed to queue re-transcription");
                }
            }}
            onClearDefaultPrompt={handleClearDefaultPrompt}
            onSetSelectedAsDefaultPrompt={handleSetSelectedAsDefaultPrompt}
            onOpenTagAssign={openTagAssign}
            onToggleExportPopover={toggleExportPopover}
            onBulkRefine={handleBulkRefine}
            onExportAnchorChange={handleExportAnchorChange}
        />
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
            {#each allTags.filter((t) => !t.is_system || t.name === "Prompt") as tag (tag.id)}
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

<!-- === Export Format Picker === -->
{#if exportOpen}
    <div class="fixed inset-0 z-[199]" onclick={closeExportPopover} role="presentation"></div>
    <div
        class="fixed min-w-[260px] bg-[var(--surface-primary)] border border-[var(--shell-border)] rounded-lg shadow-[0_12px_28px_rgba(0,0,0,0.45)] py-1 z-[200] -translate-y-full"
        style="left: {exportBtnEl
            ? Math.min(
                  exportBtnEl.getBoundingClientRect().left / getZoomFactor(),
                  window.innerWidth / getZoomFactor() - 280,
              )
            : 0}px; top: {exportBtnEl ? exportBtnEl.getBoundingClientRect().top / getZoomFactor() - 8 : 0}px"
        role="menu"
        tabindex="-1"
        onpointerdown={(e) => e.stopPropagation()}
    >
        <div class="px-3 py-1.5 text-[11px] uppercase tracking-wide text-[var(--text-tertiary)]">Export as</div>
        {#each [{ format: "md" as ExportFormat, label: "Markdown", desc: "Readable document" }, { format: "json" as ExportFormat, label: "JSON", desc: "Structured data" }, { format: "csv" as ExportFormat, label: "CSV", desc: "Spreadsheet" }, { format: "txt" as ExportFormat, label: "Plain Text", desc: "Simple text" }] as opt (opt.format)}
            <button
                class="w-full flex items-center justify-between gap-4 px-3 py-2 border-none bg-transparent text-left cursor-pointer transition-colors duration-150 hover:bg-[var(--hover-overlay)] text-[var(--text-primary)]"
                onclick={() => handleExport(opt.format)}
                role="menuitem"
            >
                <span class="text-sm font-medium">{opt.label}</span>
                <span class="text-[11px] text-[var(--text-tertiary)] shrink-0">{opt.desc}</span>
            </button>
        {/each}
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
