<script lang="ts">
    /**
     * SearchView — Table-based search interface.
     *
     * Ported from PyQt6 SearchView with:
     * - Header banner with search input
     * - Table results with columns: ID, Date, Project, Duration, Text
     * - Sortable columns, row selection
     * - Preview overlay for full transcript
     * - Copy/delete/refine actions
     */

    import {
        searchTranscripts,
        getTranscripts,
        deleteTranscript,
        refineTranscript,
        getProjects,
        batchAssignProject,
        batchDeleteTranscripts,
        type Transcript,
        type Project,
    } from "../lib/api";
    import { ws } from "../lib/ws";
    import { nav } from "../lib/navigation.svelte";
    import { SelectionManager } from "../lib/selection.svelte";
    import { onMount } from "svelte";
    import { Search, Copy, Check, Trash2, Sparkles, Pencil, X, FileText, Loader2, FolderOpen } from "lucide-svelte";

    /* ===== State ===== */

    let query = $state("");
    let allEntries: Transcript[] = $state([]);
    let results: Transcript[] = $state([]);
    let searching = $state(false);
    let initialLoad = $state(true);
    let error = $state("");
    let selectedId = $state<number | null>(null);
    let copied = $state(false);
    let refining = $state<number | null>(null);
    let debounceTimer: ReturnType<typeof setTimeout> | null = null;

    // Preview overlay
    let previewEntry = $state<Transcript | null>(null);

    // Project assignment
    let projects: Project[] = $state([]);
    let projectMenuOpen = $state(false);
    let projectMenuX = $state(0);
    let projectMenuY = $state(0);
    let batchAssigning = $state(false);

    // Multi-selection
    const selection = new SelectionManager();

    // Sorting
    type SortKey = "id" | "created_at" | "project_name" | "duration_ms" | "text";
    let sortKey = $state<SortKey>("created_at");
    let sortAsc = $state(false);

    /* ===== Derived ===== */

    let displayEntries = $derived.by(() => {
        const source = query.trim() ? results : allEntries;
        const sorted = [...source].sort((a, b) => {
            let cmp = 0;
            switch (sortKey) {
                case "id":
                    cmp = a.id - b.id;
                    break;
                case "created_at":
                    cmp = a.created_at.localeCompare(b.created_at);
                    break;
                case "project_name":
                    cmp = (a.project_name || "").localeCompare(b.project_name || "");
                    break;
                case "duration_ms":
                    cmp = a.duration_ms - b.duration_ms;
                    break;
                case "text":
                    cmp = getDisplayText(a).localeCompare(getDisplayText(b));
                    break;
            }
            return sortAsc ? cmp : -cmp;
        });
        return sorted;
    });

    let selectedEntry = $derived(displayEntries.find((e) => e.id === selectedId) ?? null);
    let resultCount = $derived(displayEntries.length);
    let orderedIds = $derived(displayEntries.map((e) => e.id));

    /** Build flat project options with parent names for sub-project disambiguation. */
    let projectOptions = $derived.by(() => {
        const opts: { value: string; label: string }[] = [{ value: "", label: "No Project" }];
        const byId = new Map(projects.map((p) => [p.id, p]));
        for (const p of projects) {
            if (p.parent_id) {
                const parent = byId.get(p.parent_id);
                opts.push({ value: String(p.id), label: parent ? `${parent.name} / ${p.name}` : p.name });
            } else {
                opts.push({ value: String(p.id), label: p.name });
            }
        }
        return opts;
    });

    /* ===== Formatting ===== */

    function getDisplayText(entry: Transcript): string {
        return entry.normalized_text || entry.raw_text || "";
    }

    function truncate(text: string, max = 120): string {
        if (text.length <= max) return text;
        const cut = text.lastIndexOf(" ", max);
        return (cut > 0 ? text.slice(0, cut) : text.slice(0, max)) + "…";
    }

    function formatDate(iso: string): string {
        const dt = new Date(iso);
        return (
            dt.toLocaleDateString("en-US", { month: "short", day: "numeric" }) +
            " " +
            dt.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })
        );
    }

    function formatDuration(ms: number): string {
        if (ms <= 0) return "—";
        const secs = Math.round(ms / 1000);
        const m = Math.floor(secs / 60);
        const s = secs % 60;
        return m > 0 ? `${m}:${s.toString().padStart(2, "0")}` : `${s}s`;
    }

    function highlight(text: string, q: string): string {
        if (!q) return escapeHtml(text);
        const escaped = q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        return escapeHtml(text).replace(new RegExp(`(${escaped})`, "gi"), '<mark class="search-highlight">$1</mark>');
    }

    function escapeHtml(text: string): string {
        return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    /* ===== Sorting ===== */

    function toggleSort(key: SortKey) {
        if (sortKey === key) sortAsc = !sortAsc;
        else {
            sortKey = key;
            sortAsc = key === "text";
        }
    }

    /* ===== Data ===== */

    async function loadAll() {
        try {
            allEntries = await getTranscripts(200);
        } catch (e: any) {
            error = e.message;
        } finally {
            initialLoad = false;
        }
    }

    async function handleSearch() {
        if (!query.trim()) {
            results = [];
            return;
        }
        searching = true;
        error = "";
        try {
            results = await searchTranscripts(query.trim(), 100);
        } catch (e: any) {
            error = e.message;
        } finally {
            searching = false;
        }
    }

    /* ===== Actions ===== */

    function handleRowClick(id: number, event: MouseEvent) {
        selection.handleClick(id, event, orderedIds);
        // Sync single-select for the action bar / preview
        selectedId = selection.count === 1 ? selection.ids[0] : null;
    }

    function openPreview(entry: Transcript) {
        previewEntry = entry;
    }

    function closePreview() {
        previewEntry = null;
    }

    function copySelectedText() {
        if (!selectedEntry) return;
        navigator.clipboard.writeText(getDisplayText(selectedEntry));
        copied = true;
        setTimeout(() => (copied = false), 1500);
    }

    async function deleteSelected() {
        if (selection.isMulti) {
            const ids = selection.ids;
            try {
                await batchDeleteTranscripts(ids);
                allEntries = allEntries.filter((e) => !selection.isSelected(e.id));
                results = results.filter((e) => !selection.isSelected(e.id));
                selection.clear();
                selectedId = null;
            } catch (e: any) {
                error = e.message;
            }
            return;
        }
        if (selectedId == null) return;
        try {
            await deleteTranscript(selectedId);
            allEntries = allEntries.filter((e) => e.id !== selectedId);
            results = results.filter((e) => e.id !== selectedId);
            selection.clear();
            selectedId = null;
        } catch (e: any) {
            error = e.message;
        }
    }

    async function refineSelected() {
        if (selectedId == null) return;
        nav.navigate("refine", selectedId);
    }

    function editSelected() {
        if (selectedId == null) return;
        nav.navigateToEdit(selectedId, { view: "search", transcriptId: selectedId });
    }

    /* ===== Project Menu ===== */

    function openProjectMenu(event: MouseEvent) {
        event.preventDefault();
        event.stopPropagation();

        const menuWidth = 280;
        const menuHeight = Math.min((projectOptions.length + 1) * 34, 360);
        const x = Math.min(event.clientX, window.innerWidth - menuWidth - 8);
        const y = Math.min(event.clientY, window.innerHeight - menuHeight - 8);

        projectMenuX = Math.max(8, x);
        projectMenuY = Math.max(8, y);
        projectMenuOpen = true;
    }

    function closeProjectMenu() {
        projectMenuOpen = false;
    }

    async function assignProjectFromContext(value: string) {
        const projectId = value === "" ? null : parseInt(value, 10);
        closeProjectMenu();

        const ids = selection.ids;
        if (ids.length === 0) return;

        batchAssigning = true;
        try {
            await batchAssignProject(ids, projectId);
            loadAll();
            if (query.trim()) handleSearch();
        } catch (err: any) {
            console.error("Failed to assign project:", err);
        } finally {
            batchAssigning = false;
        }
    }

    function handleGlobalPointerDown() {
        if (projectMenuOpen) closeProjectMenu();
    }

    function handleGlobalKeydown(event: KeyboardEvent) {
        if (event.key === "Escape") {
            if (projectMenuOpen) closeProjectMenu();
            else if (selection.isMulti) {
                selection.clear();
                selectedId = null;
            }
        }
        if ((event.ctrlKey || event.metaKey) && event.key === "a" && !previewEntry) {
            event.preventDefault();
            selection.selectAll(orderedIds);
            selectedId = null;
        }
    }

    /* ===== Lifecycle ===== */

    onMount(() => {
        loadAll();
        getProjects()
            .then((p) => (projects = p))
            .catch(() => {});

        document.addEventListener("pointerdown", handleGlobalPointerDown);
        document.addEventListener("keydown", handleGlobalKeydown);

        const unsubs = [
            ws.on("transcription_complete", () => loadAll()),
            ws.on("transcript_deleted", (data) => {
                allEntries = allEntries.filter((e) => e.id !== data.id);
                results = results.filter((e) => e.id !== data.id);
            }),
            ws.on("refinement_complete", () => {
                refining = null;
                loadAll();
            }),
            ws.on("refinement_error", () => {
                refining = null;
            }),
            ws.on("project_created", () => {
                getProjects()
                    .then((p) => (projects = p))
                    .catch(() => {});
            }),
            ws.on("project_deleted", () => {
                getProjects()
                    .then((p) => (projects = p))
                    .catch(() => {});
            }),
        ];
        return () => {
            unsubs.forEach((fn) => fn());
            document.removeEventListener("pointerdown", handleGlobalPointerDown);
            document.removeEventListener("keydown", handleGlobalKeydown);
        };
    });
</script>

<div class="flex flex-col h-full overflow-hidden p-[var(--space-3)] pb-[var(--space-2)] gap-[var(--space-2)]">
    <!-- Header -->
    <div class="shrink-0 flex flex-col gap-[var(--space-2)] pb-[var(--space-2)]">
        <form
            class="flex gap-[var(--space-1)]"
            onsubmit={(e) => {
                e.preventDefault();
                if (debounceTimer) clearTimeout(debounceTimer);
                handleSearch();
            }}
        >
            <div
                class="flex-1 flex items-center gap-[var(--space-1)] h-9 bg-[var(--surface-secondary)] border border-[var(--text-tertiary)] rounded-[var(--radius-sm)] px-[var(--space-2)] text-[var(--text-tertiary)] transition-[border-color] duration-[var(--transition-fast)] focus-within:border-[var(--accent)]"
            >
                <Search size={14} />
                <input
                    type="text"
                    class="flex-1 bg-transparent border-none outline-none text-[var(--text-primary)] font-[var(--font-family)] text-[var(--text-sm)] placeholder:text-[var(--text-tertiary)]"
                    placeholder="Filter…"
                    bind:value={query}
                    oninput={() => {
                        if (debounceTimer) clearTimeout(debounceTimer);
                        if (!query.trim()) {
                            results = [];
                            return;
                        }
                        debounceTimer = setTimeout(() => handleSearch(), 250);
                    }}
                />
                {#if query}
                    <button
                        type="button"
                        class="flex items-center justify-center w-[18px] h-[18px] border-none rounded-full bg-[var(--surface-tertiary)] text-[var(--text-tertiary)] cursor-pointer transition-colors duration-[var(--transition-fast)] hover:text-[var(--text-primary)]"
                        onclick={() => {
                            query = "";
                            results = [];
                        }}
                    >
                        <X size={12} />
                    </button>
                {/if}
            </div>
            <button
                type="submit"
                class="h-9 px-[var(--space-3)] border-none rounded-[var(--radius-sm)] bg-[var(--accent)] text-[var(--gray-0)] font-[var(--font-family)] text-[var(--text-sm)] font-[var(--weight-emphasis)] cursor-pointer transition-[background] duration-[var(--transition-fast)] whitespace-nowrap hover:enabled:bg-[var(--accent-hover)] disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={searching || !query.trim()}
            >
                {#if searching}<Loader2 size={14} class="spin" />{:else}Search{/if}
            </button>
        </form>
    </div>

    {#if error}
        <div class="text-[var(--color-danger)] text-[var(--text-sm)] shrink-0">{error}</div>
    {/if}

    <!-- Result count -->
    <div class="text-[var(--text-sm)] text-[var(--text-tertiary)] shrink-0">
        {#if query.trim() && !searching}
            {resultCount} result{resultCount !== 1 ? "s" : ""} for "{query}"
        {:else if !initialLoad}
            {resultCount} transcript{resultCount !== 1 ? "s" : ""}
        {/if}
    </div>

    <!-- Action bar -->
    {#if selection.hasSelection}
        <div class="flex items-center gap-[var(--space-1)] shrink-0">
            {#if selection.isMulti}
                <span class="text-xs text-[var(--accent)] font-semibold">{selection.count} selected</span>
                <button
                    class="inline-flex items-center gap-1.5 h-[34px] px-[var(--space-2)] border-none rounded-[var(--radius-sm)] font-[var(--font-family)] text-[var(--text-sm)] font-[var(--weight-emphasis)] cursor-pointer whitespace-nowrap transition-[background,color] duration-[var(--transition-fast)] bg-[var(--surface-tertiary)] text-[var(--text-primary)] hover:enabled:bg-[var(--gray-6)]"
                    onclick={(e) => openProjectMenu(e)}
                >
                    <FolderOpen size={14} /> Assign to Project…
                </button>
            {:else}
                <button
                    class="inline-flex items-center gap-1.5 h-[34px] px-[var(--space-2)] border-none rounded-[var(--radius-sm)] font-[var(--font-family)] text-[var(--text-sm)] font-[var(--weight-emphasis)] cursor-pointer whitespace-nowrap transition-[background,color] duration-[var(--transition-fast)] bg-[var(--surface-tertiary)] text-[var(--text-primary)] hover:enabled:bg-[var(--gray-6)] disabled:opacity-50 disabled:cursor-not-allowed"
                    onclick={copySelectedText}
                >
                    {#if copied}<Check size={14} /> Copied{:else}<Copy size={14} /> Copy{/if}
                </button>
                <button
                    class="inline-flex items-center gap-1.5 h-[34px] px-[var(--space-2)] border-none rounded-[var(--radius-sm)] font-[var(--font-family)] text-[var(--text-sm)] font-[var(--weight-emphasis)] cursor-pointer whitespace-nowrap transition-[background,color] duration-[var(--transition-fast)] bg-transparent text-[var(--text-secondary)] hover:enabled:text-[var(--text-primary)] hover:enabled:bg-[var(--hover-overlay)] disabled:opacity-50 disabled:cursor-not-allowed"
                    onclick={editSelected}
                >
                    <Pencil size={14} /> Edit
                </button>
                <button
                    class="inline-flex items-center gap-1.5 h-[34px] px-[var(--space-2)] border-none rounded-[var(--radius-sm)] font-[var(--font-family)] text-[var(--text-sm)] font-[var(--weight-emphasis)] cursor-pointer whitespace-nowrap transition-[background,color] duration-[var(--transition-fast)] bg-transparent text-[var(--text-secondary)] hover:enabled:text-[var(--text-primary)] hover:enabled:bg-[var(--hover-overlay)] disabled:opacity-50 disabled:cursor-not-allowed"
                    onclick={refineSelected}
                    disabled={refining === selectedId}
                >
                    {#if refining === selectedId}<Loader2 size={14} class="spin" />{:else}<Sparkles size={14} /> Refine{/if}
                </button>
                <button
                    class="inline-flex items-center gap-1.5 h-[34px] px-[var(--space-2)] border-none rounded-[var(--radius-sm)] font-[var(--font-family)] text-[var(--text-sm)] font-[var(--weight-emphasis)] cursor-pointer whitespace-nowrap transition-[background,color] duration-[var(--transition-fast)] bg-[var(--surface-tertiary)] text-[var(--text-primary)] hover:enabled:bg-[var(--gray-6)]"
                    onclick={(e) => openProjectMenu(e)}
                >
                    <FolderOpen size={14} /> Assign…
                </button>
            {/if}
            <div class="flex-1"></div>
            <button
                class="inline-flex items-center gap-1.5 h-[34px] px-[var(--space-2)] border-none rounded-[var(--radius-sm)] font-[var(--font-family)] text-[var(--text-sm)] font-[var(--weight-emphasis)] cursor-pointer whitespace-nowrap transition-[background,color] duration-[var(--transition-fast)] bg-transparent text-[var(--text-tertiary)] hover:enabled:text-[var(--color-danger)] hover:enabled:bg-[var(--color-danger-surface)] disabled:opacity-50 disabled:cursor-not-allowed"
                onclick={deleteSelected}
            >
                <Trash2 size={14} />
                {selection.isMulti ? `Delete ${selection.count}` : "Delete"}
            </button>
        </div>
    {/if}

    <!-- Table -->
    <div class="flex-1 overflow-auto border border-[var(--shell-border)] rounded-[var(--radius-md)]">
        {#if initialLoad}
            <div
                class="flex flex-col items-center justify-center gap-[var(--space-2)] h-[200px] text-[var(--text-tertiary)] text-[var(--text-sm)]"
            >
                <Loader2 size={20} class="spin" />
            </div>
        {:else if displayEntries.length === 0}
            <div
                class="flex flex-col items-center justify-center gap-[var(--space-2)] h-[200px] text-[var(--text-tertiary)] text-[var(--text-sm)]"
            >
                <FileText size={24} strokeWidth={1} />
                <span>{query.trim() ? `No results for "${query}"` : "No transcripts yet"}</span>
            </div>
        {:else}
            <table class="w-full border-collapse text-[var(--text-sm)]">
                <thead class="sticky top-0 z-[1]">
                    <tr>
                        <th
                            class="w-[50px] text-center bg-[var(--surface-primary)] text-[var(--text-secondary)] font-[var(--weight-emphasis)] py-[var(--space-1)] px-[var(--space-2)] border-b border-[var(--shell-border)] cursor-pointer select-none whitespace-nowrap transition-colors duration-[var(--transition-fast)] hover:text-[var(--text-primary)]"
                            onclick={() => toggleSort("id")}
                        >
                            #
                        </th>
                        <th
                            class="w-[140px] text-center whitespace-nowrap bg-[var(--surface-primary)] text-[var(--text-secondary)] font-[var(--weight-emphasis)] py-[var(--space-1)] px-[var(--space-2)] border-b border-[var(--shell-border)] cursor-pointer select-none transition-colors duration-[var(--transition-fast)] hover:text-[var(--text-primary)]"
                            onclick={() => toggleSort("created_at")}
                        >
                            Date
                        </th>
                        <th
                            class="w-[100px] text-center bg-[var(--surface-primary)] text-[var(--text-secondary)] font-[var(--weight-emphasis)] py-[var(--space-1)] px-[var(--space-2)] border-b border-[var(--shell-border)] cursor-pointer select-none whitespace-nowrap transition-colors duration-[var(--transition-fast)] hover:text-[var(--text-primary)]"
                            onclick={() => toggleSort("project_name")}
                        >
                            Project
                        </th>
                        <th
                            class="w-[70px] text-center bg-[var(--surface-primary)] text-[var(--text-secondary)] font-[var(--weight-emphasis)] py-[var(--space-1)] px-[var(--space-2)] border-b border-[var(--shell-border)] cursor-pointer select-none whitespace-nowrap transition-colors duration-[var(--transition-fast)] hover:text-[var(--text-primary)]"
                            onclick={() => toggleSort("duration_ms")}
                        >
                            Duration
                        </th>
                        <th
                            class="text-left bg-[var(--surface-primary)] text-[var(--text-secondary)] font-[var(--weight-emphasis)] py-[var(--space-1)] px-[var(--space-2)] border-b border-[var(--shell-border)] cursor-pointer select-none whitespace-nowrap transition-colors duration-[var(--transition-fast)] hover:text-[var(--text-primary)] leading-[var(--leading-normal)]"
                            onclick={() => toggleSort("text")}
                        >
                            Text
                        </th>
                    </tr>
                </thead>
                <tbody>
                    {#each displayEntries as entry (entry.id)}
                        <tr
                            class="cursor-pointer transition-[background] duration-[var(--transition-fast)] hover:bg-[var(--hover-overlay)] {selection.isSelected(
                                entry.id,
                            )
                                ? 'bg-[var(--hover-overlay-blue)]'
                                : ''}"
                            onclick={(e) => handleRowClick(entry.id, e)}
                            ondblclick={() => openPreview(entry)}
                            oncontextmenu={(e) => {
                                if (!selection.isSelected(entry.id)) {
                                    selection.selectOnly(entry.id);
                                    selectedId = entry.id;
                                }
                                openProjectMenu(e);
                            }}
                        >
                            <td
                                class="w-[50px] text-center font-[var(--font-mono)] py-[var(--space-1)] px-[var(--space-2)] border-b border-[var(--shell-border)] text-[var(--text-primary)] align-top"
                                >{entry.id}</td
                            >
                            <td
                                class="w-[140px] text-center whitespace-nowrap py-[var(--space-1)] px-[var(--space-2)] border-b border-[var(--shell-border)] text-[var(--text-primary)] align-top"
                                >{formatDate(entry.created_at)}</td
                            >
                            <td
                                class="w-[100px] text-center py-[var(--space-1)] px-[var(--space-2)] border-b border-[var(--shell-border)] text-[var(--text-primary)] align-top"
                                >{entry.project_name || "—"}</td
                            >
                            <td
                                class="w-[70px] text-center font-[var(--font-mono)] py-[var(--space-1)] px-[var(--space-2)] border-b border-[var(--shell-border)] text-[var(--text-primary)] align-top"
                                >{formatDuration(entry.duration_ms)}</td
                            >
                            <td
                                class="text-left leading-[var(--leading-normal)] py-[var(--space-1)] px-[var(--space-2)] border-b border-[var(--shell-border)] text-[var(--text-primary)] align-top"
                            >
                                {#if query.trim()}
                                    {@html highlight(truncate(getDisplayText(entry)), query)}
                                {:else}
                                    {truncate(getDisplayText(entry))}
                                {/if}
                            </td>
                        </tr>
                    {/each}
                </tbody>
            </table>
        {/if}
    </div>

    <!-- Preview overlay -->
    {#if previewEntry}
        <div
            class="fixed inset-0 bg-[var(--overlay-backdrop)] z-[100]"
            onclick={closePreview}
            role="presentation"
        ></div>
        <div
            class="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[min(85%,680px)] max-h-[75vh] bg-[var(--surface-secondary)] border border-[var(--shell-border)] rounded-[var(--radius-lg)] z-[101] flex flex-col overflow-hidden"
        >
            <div
                class="flex items-center justify-between py-[var(--space-2)] px-[var(--space-3)] border-b border-[var(--shell-border)] shrink-0"
            >
                <h3 class="text-[var(--text-sm)] font-[var(--weight-emphasis)] text-[var(--text-primary)] m-0">
                    Transcript #{previewEntry.id}
                </h3>
                <button
                    class="w-7 h-7 border-none rounded-[var(--radius-sm)] bg-transparent text-[var(--text-tertiary)] cursor-pointer flex items-center justify-center hover:text-[var(--text-primary)] hover:bg-[var(--hover-overlay)]"
                    onclick={closePreview}><X size={16} /></button
                >
            </div>
            <div class="flex-1 overflow-y-auto p-[var(--space-3)]">
                <p
                    class="text-[var(--text-base)] leading-[var(--leading-relaxed)] text-[var(--text-primary)] whitespace-pre-wrap break-words m-0"
                >
                    {getDisplayText(previewEntry)}
                </p>
            </div>
            <div
                class="py-[var(--space-1)] px-[var(--space-3)] border-t border-[var(--shell-border)] text-[var(--text-xs)] text-[var(--text-tertiary)] shrink-0"
            >
                {formatDate(previewEntry.created_at)}
                {#if previewEntry.project_name}
                    · {previewEntry.project_name}{/if}
                · {formatDuration(previewEntry.duration_ms)}
            </div>
        </div>
    {/if}
</div>

{#if projectMenuOpen}
    <div
        class="fixed min-w-[260px] max-w-[340px] max-h-[360px] overflow-y-auto bg-[var(--surface-primary)] border border-[var(--shell-border)] rounded-[var(--radius-md)] shadow-[0_12px_28px_rgba(0,0,0,0.45)] py-1 z-[200]"
        style="left: {projectMenuX}px; top: {projectMenuY}px"
        role="menu"
        tabindex="-1"
        onpointerdown={(e) => e.stopPropagation()}
        oncontextmenu={(e) => e.preventDefault()}
    >
        <div class="px-3 py-1.5 text-[11px] uppercase tracking-wide text-[var(--text-tertiary)]">
            {#if selection.isMulti}
                Assign {selection.count} transcripts to project
            {:else}
                Assign to Project
            {/if}
        </div>
        {#each projectOptions as option}
            <button
                class="w-full flex items-center justify-between gap-2 px-3 py-1.5 border-none bg-transparent text-left text-[var(--text-sm)] cursor-pointer transition-colors duration-150 hover:bg-[var(--hover-overlay-blue)] text-[var(--text-primary)]"
                onclick={() => assignProjectFromContext(option.value)}
                role="menuitem"
            >
                <span class="truncate">{option.label}</span>
            </button>
        {/each}
    </div>
{/if}

<style>
    :global(.search-highlight) {
        background: rgba(90, 159, 212, 0.3);
        color: inherit;
        border-radius: 2px;
        padding: 0 1px;
    }
</style>
