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

    import { searchTranscripts, getTranscripts, deleteTranscript, refineTranscript, type Transcript } from "../lib/api";
    import { ws } from "../lib/ws";
    import { onMount } from "svelte";
    import { Search, Copy, Check, Trash2, Sparkles, X, FileText, Loader2, ArrowUpDown } from "lucide-svelte";

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

    function selectRow(id: number) {
        selectedId = selectedId === id ? null : id;
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
        if (selectedId == null) return;
        try {
            await deleteTranscript(selectedId);
            allEntries = allEntries.filter((e) => e.id !== selectedId);
            results = results.filter((e) => e.id !== selectedId);
            selectedId = null;
        } catch (e: any) {
            error = e.message;
        }
    }

    async function refineSelected() {
        if (selectedId == null) return;
        refining = selectedId;
        try {
            await refineTranscript(selectedId, 2);
        } catch (e: any) {
            error = e.message;
            refining = null;
        }
    }

    /* ===== Lifecycle ===== */

    onMount(() => {
        loadAll();
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
        ];
        return () => unsubs.forEach((fn) => fn());
    });
</script>

<div class="search-view">
    <!-- Header -->
    <div class="search-header">
        <form
            class="search-bar"
            onsubmit={(e) => {
                e.preventDefault();
                if (debounceTimer) clearTimeout(debounceTimer);
                handleSearch();
            }}
        >
            <div class="search-input-wrap">
                <Search size={14} />
                <input
                    type="text"
                    class="search-input"
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
                        class="search-clear"
                        onclick={() => {
                            query = "";
                            results = [];
                        }}
                    >
                        <X size={12} />
                    </button>
                {/if}
            </div>
            <button type="submit" class="search-submit" disabled={searching || !query.trim()}>
                {#if searching}<Loader2 size={14} class="spin" />{:else}Search{/if}
            </button>
        </form>
    </div>

    {#if error}
        <div class="search-error">{error}</div>
    {/if}

    <!-- Result count -->
    <div class="result-meta">
        {#if query.trim() && !searching}
            {resultCount} result{resultCount !== 1 ? "s" : ""} for "{query}"
        {:else if !initialLoad}
            {resultCount} transcript{resultCount !== 1 ? "s" : ""}
        {/if}
    </div>

    <!-- Action bar -->
    {#if selectedEntry}
        <div class="action-bar">
            <button class="action-btn secondary" onclick={copySelectedText}>
                {#if copied}<Check size={14} /> Copied{:else}<Copy size={14} /> Copy{/if}
            </button>
            <button class="action-btn ghost" onclick={refineSelected} disabled={refining === selectedId}>
                {#if refining === selectedId}<Loader2 size={14} class="spin" />{:else}<Sparkles size={14} /> Refine{/if}
            </button>
            <div style="flex:1"></div>
            <button class="action-btn destructive" onclick={deleteSelected}><Trash2 size={14} /> Delete</button>
        </div>
    {/if}

    <!-- Table -->
    <div class="table-container">
        {#if initialLoad}
            <div class="table-empty"><Loader2 size={20} class="spin" /></div>
        {:else if displayEntries.length === 0}
            <div class="table-empty">
                <FileText size={24} strokeWidth={1} />
                <span>{query.trim() ? `No results for "${query}"` : "No transcripts yet"}</span>
            </div>
        {:else}
            <table class="search-table">
                <thead>
                    <tr>
                        <th class="col-id" onclick={() => toggleSort("id")}>
                            # <ArrowUpDown size={10} />
                        </th>
                        <th class="col-date" onclick={() => toggleSort("created_at")}>
                            Date <ArrowUpDown size={10} />
                        </th>
                        <th class="col-project" onclick={() => toggleSort("project_name")}>
                            Project <ArrowUpDown size={10} />
                        </th>
                        <th class="col-duration" onclick={() => toggleSort("duration_ms")}>
                            Duration <ArrowUpDown size={10} />
                        </th>
                        <th class="col-text" onclick={() => toggleSort("text")}>
                            Text <ArrowUpDown size={10} />
                        </th>
                    </tr>
                </thead>
                <tbody>
                    {#each displayEntries as entry (entry.id)}
                        <tr
                            class:selected={selectedId === entry.id}
                            onclick={() => selectRow(entry.id)}
                            ondblclick={() => openPreview(entry)}
                        >
                            <td class="col-id mono">{entry.id}</td>
                            <td class="col-date">{formatDate(entry.created_at)}</td>
                            <td class="col-project">{entry.project_name || "—"}</td>
                            <td class="col-duration mono">{formatDuration(entry.duration_ms)}</td>
                            <td class="col-text">
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
        <div class="overlay-backdrop" onclick={closePreview} role="presentation"></div>
        <div class="preview-overlay">
            <div class="preview-header">
                <h3 class="preview-title">Transcript #{previewEntry.id}</h3>
                <button class="preview-close" onclick={closePreview}><X size={16} /></button>
            </div>
            <div class="preview-body">
                <p class="preview-text">{getDisplayText(previewEntry)}</p>
            </div>
            <div class="preview-footer">
                {formatDate(previewEntry.created_at)}
                {#if previewEntry.project_name}
                    · {previewEntry.project_name}{/if}
                · {formatDuration(previewEntry.duration_ms)}
            </div>
        </div>
    {/if}
</div>

<style>
    .search-view {
        display: flex;
        flex-direction: column;
        height: 100%;
        overflow: hidden;
        padding: var(--space-3) var(--space-3) var(--space-2);
        gap: var(--space-2);
    }

    /* ===== Header ===== */
    .search-header {
        flex-shrink: 0;
        display: flex;
        flex-direction: column;
        gap: var(--space-2);
        padding-bottom: var(--space-2);
    }
    .search-bar {
        display: flex;
        gap: var(--space-1);
    }
    .search-input-wrap {
        flex: 1;
        display: flex;
        align-items: center;
        gap: var(--space-1);
        height: 36px;
        background: var(--surface-secondary);
        border: 1px solid var(--text-tertiary);
        border-radius: var(--radius-sm);
        padding: 0 var(--space-2);
        color: var(--text-tertiary);
        transition: border-color var(--transition-fast);
    }
    .search-input-wrap:focus-within {
        border-color: var(--accent);
    }
    .search-input {
        flex: 1;
        background: transparent;
        border: none;
        outline: none;
        color: var(--text-primary);
        font-family: var(--font-family);
        font-size: var(--text-sm);
    }
    .search-input::placeholder {
        color: var(--text-tertiary);
    }
    .search-clear {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 18px;
        height: 18px;
        border: none;
        border-radius: 50%;
        background: var(--surface-tertiary);
        color: var(--text-tertiary);
        cursor: pointer;
        transition: color var(--transition-fast);
    }
    .search-clear:hover {
        color: var(--text-primary);
    }
    .search-submit {
        height: 36px;
        padding: 0 var(--space-3);
        border: none;
        border-radius: var(--radius-sm);
        background: var(--accent);
        color: var(--gray-0);
        font-family: var(--font-family);
        font-size: var(--text-sm);
        font-weight: var(--weight-emphasis);
        cursor: pointer;
        transition: background var(--transition-fast);
        white-space: nowrap;
    }
    .search-submit:hover:not(:disabled) {
        background: var(--accent-hover);
    }
    .search-submit:disabled {
        opacity: 0.5;
        cursor: not-allowed;
    }

    .search-error {
        color: var(--color-danger);
        font-size: var(--text-sm);
        flex-shrink: 0;
    }
    .result-meta {
        font-size: var(--text-sm);
        color: var(--text-tertiary);
        flex-shrink: 0;
    }

    /* ===== Action bar ===== */
    .action-bar {
        display: flex;
        align-items: center;
        gap: var(--space-1);
        flex-shrink: 0;
    }
    .action-btn {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        height: 34px;
        padding: 0 var(--space-2);
        border: none;
        border-radius: var(--radius-sm);
        font-family: var(--font-family);
        font-size: var(--text-sm);
        font-weight: var(--weight-emphasis);
        cursor: pointer;
        transition:
            background var(--transition-fast),
            color var(--transition-fast);
        white-space: nowrap;
    }
    .action-btn:disabled {
        opacity: 0.5;
        cursor: not-allowed;
    }
    .action-btn.secondary {
        background: var(--surface-tertiary);
        color: var(--text-primary);
    }
    .action-btn.secondary:hover:not(:disabled) {
        background: var(--gray-6);
    }
    .action-btn.ghost {
        background: transparent;
        color: var(--text-secondary);
    }
    .action-btn.ghost:hover:not(:disabled) {
        color: var(--text-primary);
        background: var(--hover-overlay);
    }
    .action-btn.destructive {
        background: transparent;
        color: var(--text-tertiary);
    }
    .action-btn.destructive:hover:not(:disabled) {
        color: var(--color-danger);
        background: var(--color-danger-surface);
    }

    /* ===== Table ===== */
    .table-container {
        flex: 1;
        overflow: auto;
        border: 1px solid var(--shell-border);
        border-radius: var(--radius-md);
    }
    .table-empty {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: var(--space-2);
        height: 200px;
        color: var(--text-tertiary);
        font-size: var(--text-sm);
    }

    .search-table {
        width: 100%;
        border-collapse: collapse;
        font-size: var(--text-sm);
    }

    .search-table thead {
        position: sticky;
        top: 0;
        z-index: 1;
    }
    .search-table th {
        background: var(--surface-primary);
        color: var(--text-secondary);
        font-weight: var(--weight-emphasis);
        text-align: center;
        padding: var(--space-1) var(--space-2);
        border-bottom: 1px solid var(--shell-border);
        cursor: pointer;
        user-select: none;
        white-space: nowrap;
        transition: color var(--transition-fast);
    }
    .search-table th:hover {
        color: var(--text-primary);
    }
    .search-table td {
        padding: var(--space-1) var(--space-2);
        border-bottom: 1px solid var(--shell-border);
        color: var(--text-primary);
        vertical-align: top;
    }
    .search-table tr {
        cursor: pointer;
        transition: background var(--transition-fast);
    }
    .search-table tbody tr:hover {
        background: var(--hover-overlay);
    }
    .search-table tr.selected {
        background: var(--hover-overlay-blue);
    }

    .col-id {
        width: 50px;
        text-align: center;
    }
    .col-date {
        width: 140px;
        white-space: nowrap;
        text-align: center;
    }
    .col-project {
        width: 100px;
        text-align: center;
    }
    .col-duration {
        width: 70px;
        text-align: center;
    }
    .col-text {
        text-align: left;
        line-height: var(--leading-normal);
    }
    .mono {
        font-family: var(--font-mono);
    }

    :global(.search-highlight) {
        background: rgba(90, 159, 212, 0.3);
        color: inherit;
        border-radius: 2px;
        padding: 0 1px;
    }

    /* ===== Preview overlay ===== */
    .overlay-backdrop {
        position: fixed;
        inset: 0;
        background: var(--overlay-backdrop);
        z-index: 100;
    }
    .preview-overlay {
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        width: min(85%, 680px);
        max-height: 75vh;
        background: var(--surface-secondary);
        border: 1px solid var(--shell-border);
        border-radius: var(--radius-lg);
        z-index: 101;
        display: flex;
        flex-direction: column;
        overflow: hidden;
    }
    .preview-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: var(--space-2) var(--space-3);
        border-bottom: 1px solid var(--shell-border);
        flex-shrink: 0;
    }
    .preview-title {
        font-size: var(--text-sm);
        font-weight: var(--weight-emphasis);
        color: var(--text-primary);
        margin: 0;
    }
    .preview-close {
        width: 28px;
        height: 28px;
        border: none;
        border-radius: var(--radius-sm);
        background: transparent;
        color: var(--text-tertiary);
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .preview-close:hover {
        color: var(--text-primary);
        background: var(--hover-overlay);
    }
    .preview-body {
        flex: 1;
        overflow-y: auto;
        padding: var(--space-3);
    }
    .preview-text {
        font-size: var(--text-base);
        line-height: var(--leading-relaxed);
        color: var(--text-primary);
        white-space: pre-wrap;
        word-break: break-word;
        margin: 0;
    }
    .preview-footer {
        padding: var(--space-1) var(--space-3);
        border-top: 1px solid var(--shell-border);
        font-size: var(--text-xs);
        color: var(--text-tertiary);
        flex-shrink: 0;
    }
</style>
