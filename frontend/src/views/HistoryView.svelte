<script lang="ts">
    /**
     * HistoryView — Master-detail transcript browser.
     *
     * Layout: [Day-grouped list (40%)] | [Detail panel (60%)]
     *
     * Ported from PyQt6 HistoryView with:
     * - Day-grouped collapsible sections (newest first)
     * - Selection highlighting with accent indicator bar
     * - Detail panel: full transcript, metadata, variants, actions
     * - Real-time WebSocket updates
     */

    import {
        getTranscripts,
        getTranscript,
        deleteTranscript,
        deleteVariant,
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
    import { onMount, onDestroy } from "svelte";
    import {
        Copy,
        Check,
        Trash2,
        Sparkles,
        RefreshCw,
        ChevronDown,
        ChevronRight,
        FileText,
        Calendar,
        Clock,
        Hash,
        Gauge,
        Loader2,
        X,
        Pencil,
        FolderOpen,
    } from "lucide-svelte";
    import WorkspacePanel from "../lib/components/WorkspacePanel.svelte";

    /* ===== Types ===== */

    interface DayGroup {
        key: string;
        label: string;
        entries: Transcript[];
        collapsed: boolean;
    }

    /* ===== State ===== */

    let entries: Transcript[] = $state([]);
    let loading = $state(true);
    let error = $state("");
    let selectedId = $state<number | null>(null);
    let selectedEntry = $state<Transcript | null>(null);
    let detailLoading = $state(false);
    let copied = $state(false);
    let refining = $state<number | null>(null);
    let filterText = $state("");
    let collapsedDays = $state(new Set<string>());
    let projects: Project[] = $state([]);
    let initialCollapseApplied = $state(false);
    let projectMenuOpen = $state(false);
    let projectMenuX = $state(0);
    let projectMenuY = $state(0);
    let projectMenuTranscriptId = $state<number | null>(null);
    let batchAssigning = $state(false);

    /* ===== Resizable Panel State ===== */

    /** Height of the transcript preview panel in px. null = auto (flex-1). */
    let previewHeight: number | null = $state(null);
    /** Which grab bar is being dragged: null | 'preview' */
    let dragging: "preview" | null = $state(null);
    /** Reference to the detail column container for bounds calculation. */
    let detailColumnEl: HTMLDivElement | undefined = $state(undefined);

    function startDrag(bar: "preview") {
        return (e: PointerEvent) => {
            e.preventDefault();
            dragging = bar;
            const target = e.currentTarget as HTMLElement;
            target.setPointerCapture(e.pointerId);
        };
    }

    function onDragMove(e: PointerEvent) {
        if (!dragging || !detailColumnEl) return;

        // Find the preview panel and variants panel by data attributes
        const previewEl = detailColumnEl.querySelector("[data-panel='preview']") as HTMLElement | null;
        if (dragging === "preview" && previewEl) {
            const rect = previewEl.getBoundingClientRect();
            const newHeight = Math.max(80, Math.min(e.clientY - rect.top, 600));
            previewHeight = newHeight;
        }
    }

    function onDragEnd() {
        dragging = null;
    }

    /* ===== Multi-Selection ===== */

    const selection = new SelectionManager();

    /* ===== Derived ===== */

    /** Fast color lookup by project id */
    let projectById = $derived(new Map(projects.map((p) => [p.id, p])));

    let dayGroups = $derived.by((): DayGroup[] => {
        const filtered = filterText.trim()
            ? entries.filter((e) => {
                  const text = (e.normalized_text || e.raw_text || "").toLowerCase();
                  const name = (e.display_name || "").toLowerCase();
                  const q = filterText.toLowerCase();
                  return text.includes(q) || name.includes(q);
              })
            : entries;

        const groups = new Map<string, Transcript[]>();
        for (const entry of filtered) {
            const dt = new Date(entry.created_at);
            const key = dt.toISOString().slice(0, 10);
            if (!groups.has(key)) groups.set(key, []);
            groups.get(key)!.push(entry);
        }

        const sortedKeys = [...groups.keys()].sort().reverse();
        return sortedKeys.map((key) => ({
            key,
            label: formatDayHeader(new Date(key + "T00:00:00")),
            entries: groups
                .get(key)!
                .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()),
            collapsed: collapsedDays.has(key),
        }));
    });

    /** Flat list of visible transcript IDs in display order, for range selection. */
    let orderedIds = $derived(dayGroups.filter((g) => !g.collapsed).flatMap((g) => g.entries.map((e) => e.id)));

    let selectedText = $derived(
        selectedEntry ? selectedEntry.text || selectedEntry.normalized_text || selectedEntry.raw_text || "" : "",
    );

    let selectedWordCount = $derived(selectedText ? selectedText.split(/\s+/).filter(Boolean).length : 0);

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

    let visibleVariants = $derived(
        (selectedEntry?.variants ?? []).filter((variant) => variant.kind.trim().toLowerCase() !== "raw"),
    );

    /* ===== Collapse tracking ===== */

    /** Auto-collapse older day groups on first load.
     *  Today stays expanded; everything else collapses. */
    $effect(() => {
        if (!initialCollapseApplied && dayGroups.length > 0) {
            const todayKey = new Date().toISOString().slice(0, 10);
            const toCollapse = new Set<string>();
            for (const group of dayGroups) {
                if (group.key !== todayKey) {
                    toCollapse.add(group.key);
                }
            }
            if (toCollapse.size > 0) {
                collapsedDays = toCollapse;
            }
            initialCollapseApplied = true;
        }
    });

    function toggleDay(key: string) {
        const next = new Set(collapsedDays);
        if (next.has(key)) next.delete(key);
        else next.add(key);
        collapsedDays = next;
    }

    /* ===== Formatting ===== */

    function formatDayHeader(dt: Date): string {
        const day = dt.getDate();
        let suffix: string;
        if (day >= 11 && day <= 13) suffix = "th";
        else suffix = ({ 1: "st", 2: "nd", 3: "rd" } as Record<number, string>)[day % 10] ?? "th";
        return dt.toLocaleDateString("en-US", { month: "long" }) + ` ${day}${suffix}`;
    }

    function formatTime(iso: string): string {
        const dt = new Date(iso);
        let h = dt.getHours();
        const m = dt.getMinutes();
        const period = h < 12 ? "a.m." : "p.m.";
        h = h % 12 || 12;
        return `${h}:${m.toString().padStart(2, "0")} ${period}`;
    }

    function formatDuration(ms: number): string {
        if (ms <= 0) return "—";
        const secs = Math.round(ms / 1000);
        const m = Math.floor(secs / 60);
        const s = secs % 60;
        return m > 0 ? `${m}m ${s}s` : `${s}s`;
    }

    function formatWpm(words: number, ms: number): string {
        if (ms <= 0 || words <= 0) return "—";
        return `${Math.round(words / (ms / 60000))} wpm`;
    }

    function truncate(text: string, max = 80): string {
        if (text.length <= max) return text;
        const cut = text.lastIndexOf(" ", max);
        return (cut > 0 ? text.slice(0, cut) : text.slice(0, max)) + "…";
    }

    function getDisplayText(entry: Transcript): string {
        return entry.normalized_text || entry.raw_text || "";
    }

    function getTitle(entry: Transcript): string {
        if (entry.display_name?.trim()) return entry.display_name.trim();
        return truncate(getDisplayText(entry), 40);
    }

    /* ===== Data loading ===== */

    async function loadHistory() {
        loading = entries.length === 0;
        error = "";
        try {
            entries = await getTranscripts(200);
        } catch (e: any) {
            error = e.message;
        } finally {
            loading = false;
        }
    }

    /** Handle click on a transcript row. Uses SelectionManager for multi-select. */
    function handleEntryClick(id: number, event: MouseEvent) {
        selection.handleClick(id, event, orderedIds);

        // If exactly one item is selected, load its detail
        if (selection.count === 1) {
            const singleId = selection.ids[0];
            loadEntryDetail(singleId);
        } else {
            // Multi-select: clear detail pane
            selectedId = null;
            selectedEntry = null;
        }
    }

    async function loadEntryDetail(id: number) {
        if (selectedId === id) return;
        selectedId = id;
        previewHeight = null;
        detailLoading = true;
        try {
            selectedEntry = await getTranscript(id);
        } catch (e: any) {
            error = e.message;
            selectedEntry = null;
        } finally {
            detailLoading = false;
        }
    }

    /** Legacy compat: still used by WS event handlers that reload a specific entry. */
    async function selectEntry(id: number) {
        selection.selectOnly(id);
        await loadEntryDetail(id);
    }

    /* ===== Actions ===== */

    async function handleDelete() {
        if (selection.isMulti) {
            // Batch delete
            const ids = selection.ids;
            try {
                await batchDeleteTranscripts(ids);
                entries = entries.filter((e) => !selection.isSelected(e.id));
                selection.clear();
                selectedId = null;
                selectedEntry = null;
            } catch (e: any) {
                error = e.message;
            }
            return;
        }
        if (selectedId == null) return;
        try {
            await deleteTranscript(selectedId);
            entries = entries.filter((e) => e.id !== selectedId);
            selection.clear();
            selectedId = null;
            selectedEntry = null;
        } catch (e: any) {
            error = e.message;
        }
    }

    async function handleRefine() {
        if (selectedId == null) return;
        nav.navigate("refine", selectedId);
    }

    function copyText() {
        if (!selectedText) return;
        navigator.clipboard.writeText(selectedText);
        copied = true;
        setTimeout(() => (copied = false), 1500);
    }

    async function handleDeleteVariant(transcriptId: number, variantId: number) {
        try {
            await deleteVariant(transcriptId, variantId);
            // Refresh the selected entry to reflect the deletion
            if (selectedEntry && selectedEntry.id === transcriptId) {
                selectedEntry = await getTranscript(transcriptId);
            }
        } catch (e: any) {
            console.error("Failed to delete variant:", e);
        }
    }

    function editSelected() {
        if (!selectedEntry) return;
        nav.navigateToEdit(selectedEntry.id, { view: "history", transcriptId: selectedEntry.id });
    }

    function openProjectMenu(event: MouseEvent, transcriptId: number) {
        event.preventDefault();
        event.stopPropagation();

        // If right-clicking a non-selected item, select it first
        if (!selection.isSelected(transcriptId)) {
            selection.selectOnly(transcriptId);
            loadEntryDetail(transcriptId);
        }

        const menuWidth = 280;
        const menuHeight = Math.min((projectOptions.length + 1) * 34, 360);
        const x = Math.min(event.clientX, window.innerWidth - menuWidth - 8);
        const y = Math.min(event.clientY, window.innerHeight - menuHeight - 8);

        projectMenuX = Math.max(8, x);
        projectMenuY = Math.max(8, y);
        projectMenuTranscriptId = transcriptId;
        projectMenuOpen = true;
    }

    function closeProjectMenu() {
        projectMenuOpen = false;
        projectMenuTranscriptId = null;
    }

    async function assignProjectFromContext(value: string) {
        const projectId = value === "" ? null : parseInt(value, 10);
        closeProjectMenu();

        // Batch assign all selected items
        const ids = selection.ids;
        if (ids.length === 0) return;

        batchAssigning = true;
        try {
            await batchAssignProject(ids, projectId);
            if (selectedEntry && ids.includes(selectedEntry.id)) {
                selectedEntry = await getTranscript(selectedEntry.id);
            }
            loadHistory();
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
                selectedEntry = null;
            }
        }
        // Ctrl+A / Cmd+A: select all visible transcripts
        if ((event.ctrlKey || event.metaKey) && event.key === "a") {
            event.preventDefault();
            selection.selectAll(orderedIds);
            selectedId = null;
            selectedEntry = null;
        }
    }

    /* ===== WebSocket ===== */

    onMount(() => {
        loadHistory().then(() => {
            const pending = nav.consumePendingTranscriptRequest();
            if (pending && pending.id !== selectedId) {
                selectEntry(pending.id);
            }
        });
        getProjects()
            .then((p) => (projects = p))
            .catch(() => {});

        document.addEventListener("pointerdown", handleGlobalPointerDown);
        document.addEventListener("keydown", handleGlobalKeydown);

        const unsubs = [
            ws.on("transcription_complete", () => loadHistory()),
            ws.on("transcript_deleted", (data) => {
                entries = entries.filter((e) => e.id !== data.id);
                if (selectedId === data.id) {
                    selectedId = null;
                    selectedEntry = null;
                }
            }),
            ws.on("refinement_complete", (data) => {
                refining = null;
                if (selectedId === data.transcript_id) selectEntry(data.transcript_id);
                loadHistory();
            }),
            ws.on("refinement_error", () => {
                refining = null;
            }),
            ws.on("transcript_updated", (data) => {
                if (selectedId === data.id) selectEntry(data.id);
                loadHistory();
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
                loadHistory();
            }),
        ];
        return () => {
            unsubs.forEach((fn) => fn());
            document.removeEventListener("pointerdown", handleGlobalPointerDown);
            document.removeEventListener("keydown", handleGlobalKeydown);
        };
    });

    onDestroy(() => {
        document.removeEventListener("pointerdown", handleGlobalPointerDown);
        document.removeEventListener("keydown", handleGlobalKeydown);
    });
</script>

<div class="flex h-full overflow-hidden">
    <!-- Master: List Panel -->
    <div class="w-2/5 min-w-[280px] flex flex-col border-r border-[var(--shell-border)] bg-[var(--surface-primary)]">
        <div class="flex items-center justify-end p-2 px-3 shrink-0 h-auto gap-2">
            {#if selection.isMulti}
                <span class="text-xs text-[var(--accent)] font-semibold mr-auto">{selection.count} selected</span>
                <button
                    class="text-xs text-[var(--text-tertiary)] bg-transparent border-none cursor-pointer hover:text-[var(--text-primary)] transition-colors"
                    onclick={() => {
                        selection.clear();
                        selectedId = null;
                        selectedEntry = null;
                    }}>Clear</button
                >
            {/if}
            <button
                class="w-7 h-7 border-none rounded bg-transparent text-[var(--text-tertiary)] cursor-pointer flex items-center justify-center transition-colors duration-150 hover:text-[var(--text-primary)] hover:bg-[var(--hover-overlay)]"
                onclick={loadHistory}
                title="Refresh"
            >
                <RefreshCw size={14} />
            </button>
        </div>

        <div class="py-1 px-3 shrink-0">
            <input
                type="text"
                class="w-full h-9 bg-[var(--surface-secondary)] border border-[var(--shell-border)] rounded text-[var(--text-primary)] text-sm px-2 outline-none transition-colors duration-150 focus:border-[var(--accent)] placeholder:text-[var(--text-tertiary)]"
                placeholder="Filter transcripts…"
                bind:value={filterText}
            />
        </div>

        <div class="flex-1 overflow-y-auto pb-2">
            {#if loading}
                <div
                    class="flex flex-col items-center justify-center gap-1 h-[200px] text-[var(--text-tertiary)] text-sm"
                >
                    <Loader2 size={20} class="animate-spin" /><span>Loading history…</span>
                </div>
            {:else if error}
                <div
                    class="flex flex-col items-center justify-center gap-1 h-[200px] text-[var(--color-danger)] text-sm"
                >
                    {error}
                </div>
            {:else if dayGroups.length === 0}
                <div
                    class="flex flex-col items-center justify-center gap-1 h-[200px] text-[var(--text-tertiary)] text-sm"
                >
                    {filterText ? "No matches found" : "No transcripts yet"}
                </div>
            {:else}
                {#each dayGroups as group, groupIdx (group.key)}
                    {#if groupIdx > 0}
                        <div class="h-px mx-3 my-1 bg-[var(--accent)]"></div>
                    {/if}
                    <button
                        class="flex items-center gap-1 w-full p-1 px-3 border-none bg-transparent text-[var(--text-secondary)] text-xs font-semibold uppercase tracking-wide cursor-pointer text-left transition-colors duration-150 hover:text-[var(--text-primary)]"
                        onclick={() => toggleDay(group.key)}
                    >
                        <span class="flex items-center text-[var(--text-tertiary)]">
                            {#if group.collapsed}<ChevronRight size={14} />{:else}<ChevronDown size={14} />{/if}
                        </span>
                        <span class="flex-1">{group.label}</span>
                        <span
                            class="text-xs text-[var(--text-tertiary)] bg-[var(--surface-tertiary)] px-1.5 py-px rounded-lg"
                            >{group.entries.length}</span
                        >
                    </button>
                    {#if !group.collapsed}
                        {#each group.entries as entry (entry.id)}
                            <button
                                class="flex items-stretch w-full p-1 px-3 border-none bg-transparent cursor-pointer text-left transition-colors duration-150 hover:bg-[var(--hover-overlay)]"
                                class:bg-[var(--hover-overlay-blue)]={selection.isSelected(entry.id)}
                                onclick={(e) => handleEntryClick(entry.id, e)}
                                oncontextmenu={(e) => openProjectMenu(e, entry.id)}
                            >
                                {#if entry.project_id && projectById.get(entry.project_id)?.color}
                                    <span
                                        class="w-1.5 h-1.5 rounded-full shrink-0 self-center mr-2"
                                        style="background: {projectById.get(entry.project_id)!.color}"
                                        title={projectById.get(entry.project_id)!.name}
                                    ></span>
                                {/if}
                                <div
                                    class="w-0.5 rounded-sm shrink-0 mr-2 transition-colors duration-150"
                                    class:bg-[var(--accent)]={selection.isSelected(entry.id)}
                                ></div>
                                <div class="flex-1 min-w-0 flex flex-col gap-0.5 py-0.5">
                                    <span
                                        class="text-sm text-[var(--text-primary)] leading-normal overflow-hidden text-ellipsis whitespace-nowrap"
                                        >{truncate(getDisplayText(entry))}</span
                                    >
                                    <span class="text-xs text-[var(--text-tertiary)] font-mono"
                                        >{formatTime(entry.created_at)}</span
                                    >
                                </div>
                            </button>
                        {/each}
                    {/if}
                {/each}
            {/if}
        </div>
    </div>

    <!-- Detail: Content Panel -->
    <div class="flex-1 flex flex-col overflow-hidden bg-[var(--surface-secondary)]">
        {#if detailLoading}
            <div class="flex-1 flex flex-col items-center justify-center gap-2 text-[var(--text-tertiary)] text-sm">
                <Loader2 size={24} class="animate-spin" />
            </div>
        {:else if selection.isMulti}
            <!-- Multi-Select Bulk Actions Panel -->
            <div class="flex-1 flex flex-col items-center justify-center gap-[var(--space-4)] p-[var(--space-5)]">
                <div
                    class="w-16 h-16 rounded-2xl bg-[var(--surface-primary)] border border-[var(--accent-muted)] flex items-center justify-center"
                >
                    <FileText size={28} strokeWidth={1.2} class="text-[var(--accent)]" />
                </div>
                <h3 class="m-0 text-[var(--text-primary)] text-lg font-semibold">
                    {selection.count} transcripts selected
                </h3>
                <p class="m-0 text-[var(--text-tertiary)] text-sm">
                    Right-click to assign to project, or use actions below
                </p>

                <div class="flex flex-col gap-[var(--space-2)] w-full max-w-[320px]">
                    <button
                        class="inline-flex items-center justify-center gap-2 h-10 px-4 border-none rounded-[var(--radius-md)] text-sm font-semibold cursor-pointer whitespace-nowrap bg-[var(--surface-primary)] border border-[var(--shell-border)] text-[var(--text-primary)] hover:bg-[var(--hover-overlay)] hover:border-[var(--accent)] transition-colors"
                        onclick={(e) => openProjectMenu(e, selection.ids[0])}
                    >
                        <FolderOpen size={15} /> Assign {selection.count} to Project…
                    </button>
                    <button
                        class="inline-flex items-center justify-center gap-2 h-10 px-4 border border-[var(--shell-border)] rounded-[var(--radius-md)] text-sm font-semibold cursor-pointer whitespace-nowrap bg-transparent text-[var(--text-tertiary)] hover:text-[var(--color-danger)] hover:border-[var(--color-danger)] hover:bg-[var(--color-danger-surface)] transition-colors"
                        onclick={handleDelete}
                    >
                        <Trash2 size={15} /> Delete {selection.count} Transcripts
                    </button>
                </div>

                <div class="text-xs text-[var(--text-tertiary)] mt-[var(--space-2)]">
                    <kbd
                        class="px-1.5 py-0.5 bg-[var(--surface-primary)] border border-[var(--shell-border)] rounded text-[10px] font-mono"
                        >Esc</kbd
                    >
                    to clear selection ·
                    <kbd
                        class="px-1.5 py-0.5 bg-[var(--surface-primary)] border border-[var(--shell-border)] rounded text-[10px] font-mono"
                        >Ctrl+A</kbd
                    > to select all
                </div>
            </div>
        {:else if selectedEntry}
            <div
                class="flex-1 flex flex-col p-4 gap-2 overflow-hidden"
                bind:this={detailColumnEl}
                onpointermove={onDragMove}
                onpointerup={onDragEnd}
                onpointercancel={onDragEnd}
                role="presentation"
            >
                <h2 class="text-xl font-semibold text-[var(--text-primary)] m-0 leading-tight text-center">
                    {getTitle(selectedEntry)}
                </h2>
                <div class="h-px bg-[var(--shell-border)] shrink-0"></div>

                <div class="flex flex-wrap justify-center gap-2 shrink-0">
                    <div class="flex items-center gap-1 text-sm text-[var(--text-secondary)] font-mono">
                        <Clock size={12} /><span>{formatDuration(selectedEntry.duration_ms)}</span>
                    </div>
                    <div class="flex items-center gap-1 text-sm text-[var(--text-secondary)] font-mono">
                        <Gauge size={12} /><span>{formatDuration(selectedEntry.speech_duration_ms)}</span>
                    </div>
                    <div class="flex items-center gap-1 text-sm text-[var(--text-secondary)] font-mono">
                        <Hash size={12} /><span>{selectedWordCount} words</span>
                    </div>
                    <div class="flex items-center gap-1 text-sm text-[var(--text-secondary)] font-mono">
                        <FileText size={12} /><span
                            >{formatWpm(
                                selectedWordCount,
                                selectedEntry.speech_duration_ms || selectedEntry.duration_ms,
                            )}</span
                        >
                    </div>
                    {#if selectedEntry.project_name}
                        <div class="flex items-center gap-1 text-sm text-[var(--accent)]">
                            <span>📁 {selectedEntry.project_name}</span>
                        </div>
                    {/if}
                </div>

                <div
                    class="overflow-hidden flex flex-col relative group"
                    data-panel="preview"
                    style={previewHeight != null
                        ? `height:${previewHeight}px;max-height:${previewHeight}px;flex-shrink:0;`
                        : "flex:1 1 auto;min-height:80px;"}
                >
                    <WorkspacePanel>
                        <div class="overflow-y-auto h-full">
                            <p
                                class="text-base leading-relaxed text-[var(--text-primary)] whitespace-pre-wrap break-words m-0"
                            >
                                {selectedText}
                            </p>
                        </div>
                    </WorkspacePanel>
                </div>

                <!-- Grab bar: between preview and variants/buttons -->
                <div
                    class="h-1.5 shrink-0 cursor-row-resize flex items-center justify-center group/grab rounded
                           hover:bg-[var(--hover-overlay)] transition-colors {dragging === 'preview'
                        ? 'bg-[var(--accent)]'
                        : ''}"
                    onpointerdown={startDrag("preview")}
                    role="separator"
                    aria-orientation="horizontal"
                    title="Drag to resize"
                >
                    <div
                        class="w-8 h-0.5 rounded-full bg-[var(--text-tertiary)] opacity-40 group-hover/grab:opacity-100 transition-opacity {dragging ===
                        'preview'
                            ? 'opacity-100 bg-[var(--accent)]'
                            : ''}"
                    ></div>
                </div>

                {#if visibleVariants.length > 0}
                    <div class="flex-1 min-h-[60px] overflow-y-auto" data-panel="variants">
                        <h3
                            class="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wide mb-2 m-0 mt-2"
                        >
                            Variants
                        </h3>
                        {#each visibleVariants as variant (variant.id)}
                            <div class="p-2 px-3 bg-[var(--surface-primary)] rounded mb-2 group/variant">
                                <div class="flex justify-between items-center mb-1">
                                    <span class="text-xs font-semibold text-[var(--accent)] uppercase tracking-wide"
                                        >{variant.kind}</span
                                    >
                                    <span class="text-xs text-[var(--text-tertiary)] font-mono"
                                        >{formatTime(variant.created_at)}</span
                                    >
                                    <button
                                        class="bg-none border-none text-[var(--text-tertiary)] cursor-pointer p-0.5 rounded flex items-center opacity-0 transition-opacity duration-150 group-hover/variant:opacity-100 hover:text-[var(--color-danger)]"
                                        title="Delete variant"
                                        onclick={() => handleDeleteVariant(selectedEntry!.id, variant.id)}
                                    >
                                        <X size={12} />
                                    </button>
                                </div>
                                <p class="text-sm leading-normal text-[var(--text-secondary)] m-0">{variant.text}</p>
                            </div>
                        {/each}
                    </div>
                {/if}

                <div
                    class="flex items-center gap-1.5 text-xs text-[var(--text-tertiary)] shrink-0 pt-2 border-t border-[var(--shell-border)]"
                >
                    <Calendar size={12} />
                    <span>
                        {formatDayHeader(new Date(selectedEntry.created_at))} · {formatTime(selectedEntry.created_at)}
                        {#if selectedEntry.project_name}
                            · Project: {selectedEntry.project_name}{/if}
                    </span>
                </div>

                <div class="flex items-center gap-2 shrink-0 pt-2">
                    <button
                        class="inline-flex items-center gap-1.5 h-9 px-3 border-none rounded text-sm font-semibold cursor-pointer whitespace-nowrap bg-[var(--surface-tertiary)] text-[var(--text-primary)] hover:bg-[var(--gray-6)] transition-colors"
                        onclick={editSelected}
                        title="Edit"
                    >
                        <Pencil size={14} /> Edit
                    </button>
                    <button
                        class="inline-flex items-center gap-1.5 h-9 px-3 border-none rounded text-sm font-semibold cursor-pointer whitespace-nowrap bg-[var(--surface-tertiary)] text-[var(--text-primary)] hover:bg-[var(--gray-6)] transition-colors"
                        onclick={copyText}
                        title="Copy"
                    >
                        {#if copied}<Check size={14} /> Copied{:else}<Copy size={14} /> Copy{/if}
                    </button>
                    <button
                        class="inline-flex items-center gap-1.5 h-9 px-3 border-none rounded text-sm font-semibold cursor-pointer whitespace-nowrap bg-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--hover-overlay)] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        onclick={handleRefine}
                        title="Refine"
                        disabled={refining === selectedId}
                    >
                        {#if refining === selectedId}<Loader2 size={14} class="animate-spin" /> Refining…{:else}<Sparkles
                                size={14}
                            /> Refine{/if}
                    </button>
                    <span class="text-xs text-[var(--text-tertiary)]">Right-click transcript to assign project</span>
                    <div class="flex-1"></div>
                    <button
                        class="inline-flex items-center gap-1.5 h-9 px-3 border-none rounded text-sm font-semibold cursor-pointer whitespace-nowrap bg-transparent text-[var(--text-tertiary)] hover:text-[var(--color-danger)] hover:bg-[var(--color-danger-surface)] transition-colors"
                        onclick={handleDelete}
                        title="Delete"><Trash2 size={14} /> Delete</button
                    >
                </div>
            </div>
        {:else}
            <div class="flex-1 flex flex-col items-center justify-center gap-2 text-[var(--text-tertiary)] text-sm">
                <FileText size={32} strokeWidth={1} />
                <p>Select a transcript</p>
            </div>
        {/if}
    </div>
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
                class="w-full flex items-center justify-between gap-2 px-3 py-1.5 border-none bg-transparent text-left text-[var(--text-sm)] cursor-pointer transition-colors duration-150 hover:bg-[var(--hover-overlay-blue)] {selectedEntry?.id ===
                    projectMenuTranscriptId && (selectedEntry?.project_id?.toString() ?? '') === option.value
                    ? 'text-[var(--accent)]'
                    : 'text-[var(--text-primary)]'}"
                onclick={() => assignProjectFromContext(option.value)}
                role="menuitem"
            >
                <span class="truncate">{option.label}</span>
                {#if selectedEntry?.id === projectMenuTranscriptId && (selectedEntry?.project_id?.toString() ?? "") === option.value}
                    <Check size={12} />
                {/if}
            </button>
        {/each}
    </div>
{/if}
