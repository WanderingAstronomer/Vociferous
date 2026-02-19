<script lang="ts">
    /**
     * TranscriptionsView — Hierarchical project-tree transcript browser.
     *
     * Layout: [Project tree list (50%)] | [Detail panel (50%)]
     *
     * Transcripts are grouped under their parent project/subproject headers
     * in a collapsible tree. Unassigned transcripts live at the bottom.
     * Project management (create/rename/delete) uses a focused modal.
     */

    import {
        getTranscripts,
        getTranscript,
        deleteTranscript,
        deleteVariant,
        renameTranscript,
        retitleTranscript,
        getProjects,
        createProject,
        updateProject,
        deleteProject,
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
        Loader2,
        X,
        Pencil,
        FolderOpen,
        Plus,
    } from "lucide-svelte";
    import WorkspacePanel from "../lib/components/WorkspacePanel.svelte";
    import ProjectModal from "../lib/components/ProjectModal.svelte";
    import type { ProjectModalResult } from "../lib/components/ProjectModal.svelte";

    /* ===== Tree Node Types ===== */

    type TreeNode = ProjectHeaderNode | TranscriptNode | UnassignedHeaderNode | DateHeaderNode;

    interface ProjectHeaderNode {
        type: "project-header";
        key: string;
        project: Project;
        depth: number;
        collapsed: boolean;
        count: number;
    }

    interface TranscriptNode {
        type: "transcript";
        entry: Transcript;
        depth: number;
        parentColor: string | null;
        isLastChild: boolean;
    }

    interface UnassignedHeaderNode {
        type: "unassigned-header";
        key: string;
        collapsed: boolean;
        count: number;
    }

    interface DateHeaderNode {
        type: "date-header";
        key: string;
        label: string;
        collapsed: boolean;
        count: number;
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
    let collapsedSections = $state(new Set<string>());
    let projects: Project[] = $state([]);
    let projectMenuOpen = $state(false);
    let projectMenuX = $state(0);
    let projectMenuY = $state(0);
    let projectMenuTranscriptId = $state<number | null>(null);
    let batchAssigning = $state(false);

    /* ===== Project Modal State ===== */

    let showProjectModal = $state(false);
    let projectModalMode = $state<"create" | "rename" | "delete">("create");
    let projectModalTarget = $state<Project | null>(null);

    /* ===== Title Editing State ===== */

    let editingTitle = $state(false);
    let editTitleValue = $state("");
    let retitling = $state(false);

    /* ===== Multi-Selection ===== */

    const selection = new SelectionManager();

    /* ===== Derived ===== */

    /** Filter entries by search text. */
    let filteredEntries = $derived.by((): Transcript[] => {
        if (!filterText.trim()) return entries;
        const q = filterText.toLowerCase();
        return entries.filter((e) => {
            const text = (e.normalized_text || e.raw_text || "").toLowerCase();
            const name = (e.display_name || "").toLowerCase();
            return text.includes(q) || name.includes(q);
        });
    });

    /** Build the hierarchical tree: project headers → transcripts → unassigned (date-grouped). */
    let treeNodes = $derived.by((): TreeNode[] => {
        const nodes: TreeNode[] = [];
        const byProject = new Map<number, Transcript[]>();
        const unassigned: Transcript[] = [];

        for (const e of filteredEntries) {
            if (e.project_id != null) {
                if (!byProject.has(e.project_id)) byProject.set(e.project_id, []);
                byProject.get(e.project_id)!.push(e);
            } else {
                unassigned.push(e);
            }
        }

        const sortDesc = (a: Transcript, b: Transcript) =>
            new Date(b.created_at).getTime() - new Date(a.created_at).getTime();

        // Top-level projects sorted alphabetically
        const topLevel = projects.filter((p) => !p.parent_id).sort((a, b) => a.name.localeCompare(b.name));

        function addProject(project: Project, depth: number) {
            const children = projects
                .filter((p) => p.parent_id === project.id)
                .sort((a, b) => a.name.localeCompare(b.name));

            // Count transcripts belonging to this project + its sub-projects
            const directTranscripts = byProject.get(project.id) ?? [];
            let totalCount = directTranscripts.length;
            for (const child of children) {
                totalCount += (byProject.get(child.id) ?? []).length;
            }

            // Skip empty project sections when filtering
            if (filterText.trim() && totalCount === 0) return;

            const key = `project-${project.id}`;
            const collapsed = collapsedSections.has(key);

            nodes.push({
                type: "project-header",
                key,
                project,
                depth,
                collapsed,
                count: totalCount,
            });

            if (!collapsed) {
                const sorted = directTranscripts.sort(sortDesc);
                const lastDirectIdx = sorted.length - 1;
                const hasSubProjects = children.length > 0;
                // Direct transcripts under this project
                for (let i = 0; i < sorted.length; i++) {
                    nodes.push({
                        type: "transcript",
                        entry: sorted[i],
                        depth: depth + 1,
                        parentColor: project.color ?? null,
                        isLastChild: i === lastDirectIdx && !hasSubProjects,
                    });
                }
                // Sub-projects
                for (const child of children) {
                    addProject(child, depth + 1);
                }
            }
        }

        for (const p of topLevel) {
            addProject(p, 0);
        }

        // --- Unassigned section: date-grouped ---
        if (!filterText.trim() || unassigned.length > 0) {
            const key = "unassigned";
            const collapsed = collapsedSections.has(key);
            nodes.push({
                type: "unassigned-header",
                key,
                collapsed,
                count: unassigned.length,
            });
            if (!collapsed) {
                const sorted = unassigned.sort(sortDesc);
                // Group by date bucket
                const now = new Date();
                const todayStr = now.toDateString();
                const yesterday = new Date(now);
                yesterday.setDate(yesterday.getDate() - 1);
                const yesterdayStr = yesterday.toDateString();

                const buckets = new Map<string, { label: string; entries: Transcript[] }>();
                const bucketOrder: string[] = [];

                for (const e of sorted) {
                    const dt = new Date(e.created_at);
                    const ds = dt.toDateString();
                    let bucketKey: string;
                    let label: string;
                    if (ds === todayStr) {
                        bucketKey = "date-today";
                        label = "Today";
                    } else if (ds === yesterdayStr) {
                        bucketKey = "date-yesterday";
                        label = "Yesterday";
                    } else {
                        bucketKey = `date-${ds}`;
                        label = formatDayHeader(dt);
                    }
                    if (!buckets.has(bucketKey)) {
                        buckets.set(bucketKey, { label, entries: [] });
                        bucketOrder.push(bucketKey);
                    }
                    buckets.get(bucketKey)!.entries.push(e);
                }

                for (const bk of bucketOrder) {
                    const bucket = buckets.get(bk)!;
                    // Auto-expand Today on first render, collapse others by default
                    const dateKey = bk;
                    const dateCollapsed =
                        collapsedSections.has(dateKey) ||
                        (!collapsedSections.has(`_init_${dateKey}`) && bk !== "date-today");
                    nodes.push({
                        type: "date-header",
                        key: dateKey,
                        label: bucket.label,
                        collapsed: dateCollapsed,
                        count: bucket.entries.length,
                    });
                    if (!dateCollapsed) {
                        for (const e of bucket.entries) {
                            nodes.push({
                                type: "transcript",
                                entry: e,
                                depth: 2,
                                parentColor: null,
                                isLastChild: false,
                            });
                        }
                    }
                }
            }
        }

        return nodes;
    });

    /** Flat list of visible transcript IDs in display order, for range selection. */
    let orderedIds = $derived(
        treeNodes.filter((n): n is TranscriptNode => n.type === "transcript").map((n) => n.entry.id),
    );

    let selectedText = $derived(
        selectedEntry ? selectedEntry.text || selectedEntry.normalized_text || selectedEntry.raw_text || "" : "",
    );

    let selectedWordCount = $derived(selectedText ? selectedText.split(/\s+/).filter(Boolean).length : 0);

    /** Build flat project options for context menu (with parent name prefix). */
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

    /* ===== Section collapse ===== */

    function toggleSection(key: string) {
        const next = new Set(collapsedSections);
        if (next.has(key)) next.delete(key);
        else next.add(key);
        collapsedSections = next;
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

    function getDisplayText(entry: Transcript): string {
        return entry.normalized_text || entry.raw_text || "";
    }

    function getTitle(entry: Transcript): string {
        if (entry.display_name?.trim()) return entry.display_name.trim();
        return `Transcript #${entry.id}`;
    }

    function wordCount(text: string): number {
        return text ? text.split(/\s+/).filter(Boolean).length : 0;
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

        if (selection.count === 1) {
            const singleId = selection.ids[0];
            loadEntryDetail(singleId);
        } else {
            selectedId = null;
            selectedEntry = null;
        }
    }

    async function loadEntryDetail(id: number) {
        if (selectedId === id) return;
        selectedId = id;
        editingTitle = false;
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

    async function selectEntry(id: number) {
        selection.selectOnly(id);
        await loadEntryDetail(id);
    }

    /* ===== Actions ===== */

    async function handleDelete() {
        if (selection.isMulti) {
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

    function startEditTitle() {
        if (!selectedEntry) return;
        editTitleValue = getTitle(selectedEntry);
        editingTitle = true;
    }

    async function commitTitle() {
        if (!selectedEntry || !editTitleValue.trim()) {
            editingTitle = false;
            return;
        }
        const newTitle = editTitleValue.trim();
        editingTitle = false;
        try {
            await renameTranscript(selectedEntry.id, newTitle);
        } catch (e: any) {
            console.error("Failed to rename transcript:", e);
        }
    }

    function cancelEditTitle() {
        editingTitle = false;
    }

    async function handleRetitle() {
        if (!selectedEntry || retitling) return;
        retitling = true;
        try {
            await retitleTranscript(selectedEntry.id);
        } catch (e: any) {
            console.error("Failed to retitle transcript:", e);
        } finally {
            retitling = false;
        }
    }

    function handleTitleKeydown(e: KeyboardEvent) {
        if (e.key === "Enter") {
            e.preventDefault();
            commitTitle();
        } else if (e.key === "Escape") {
            e.preventDefault();
            cancelEditTitle();
        }
    }

    /* ===== Context Menu (project assignment) ===== */

    function openProjectMenu(event: MouseEvent, transcriptId: number) {
        event.preventDefault();
        event.stopPropagation();

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

    /* ===== Project Modal ===== */

    function openProjectModal(mode: "create" | "rename" | "delete", target: Project | null = null) {
        projectModalMode = mode;
        projectModalTarget = target;
        showProjectModal = true;
    }

    async function handleProjectModalConfirm(result: ProjectModalResult) {
        showProjectModal = false;
        try {
            if (result.mode === "create") {
                await createProject(result.name, result.color, result.parentId);
            } else if (result.mode === "rename") {
                await updateProject(result.id, { name: result.name, color: result.color });
            } else if (result.mode === "delete") {
                await deleteProject(result.id);
            }
            projects = await getProjects();
            await loadHistory();
        } catch (e: any) {
            console.error(`Project ${result.mode} failed:`, e);
        }
    }

    function handleProjectModalCancel() {
        showProjectModal = false;
    }

    /* ===== Globals ===== */

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
    <!-- Master: List Panel (50%) -->
    <div class="w-1/2 min-w-[280px] flex flex-col border-r border-[var(--shell-border)] bg-[var(--surface-primary)]">
        <!-- Toolbar: selection info / refresh / new project / filter -->
        <div class="flex items-center gap-2 p-2 px-3 shrink-0">
            <button
                class="inline-flex items-center gap-1 h-7 px-2.5 border-none rounded text-xs font-semibold text-[var(--text-tertiary)] bg-transparent cursor-pointer transition-colors duration-150 hover:text-[var(--accent)] hover:bg-[var(--hover-overlay)]"
                onclick={() => openProjectModal("create")}
            >
                <Plus size={12} /> Create Project
            </button>
            {#if selection.isMulti}
                <span class="text-xs text-[var(--accent)] font-semibold">{selection.count} selected</span>
                <button
                    class="text-xs text-[var(--text-tertiary)] bg-transparent border-none cursor-pointer hover:text-[var(--text-primary)] transition-colors"
                    onclick={() => {
                        selection.clear();
                        selectedId = null;
                        selectedEntry = null;
                    }}>Clear</button
                >
            {/if}
            <div class="flex-1"></div>
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

        <!-- Tree list -->
        <div class="flex-1 overflow-y-auto pb-2">
            {#if loading}
                <div
                    class="flex flex-col items-center justify-center gap-1 h-[200px] text-[var(--text-tertiary)] text-sm"
                >
                    <Loader2 size={20} class="animate-spin" /><span>Loading transcriptions…</span>
                </div>
            {:else if error}
                <div
                    class="flex flex-col items-center justify-center gap-1 h-[200px] text-[var(--color-danger)] text-sm"
                >
                    {error}
                </div>
            {:else if treeNodes.length === 0}
                <div
                    class="flex flex-col items-center justify-center gap-1 h-[200px] text-[var(--text-tertiary)] text-sm"
                >
                    {filterText ? "No matches found" : "No transcripts yet"}
                </div>
            {:else}
                {#each treeNodes as node, nodeIdx (node.type === "transcript" ? `t-${node.entry.id}` : node.type === "project-header" ? node.key : node.type === "date-header" ? node.key : "unassigned")}
                    {#if node.type === "project-header"}
                        <!-- Project header row -->
                        <div
                            class="group/hdr flex items-center gap-1.5 w-full p-1.5 border-none rounded-md cursor-pointer text-left transition-colors duration-150 hover:brightness-110"
                            style="padding-left: {12 + node.depth * 16}px; background: {node.project.color
                                ? `color-mix(in srgb, ${node.project.color} 18%, transparent)`
                                : 'var(--surface-secondary)'}"
                            role="button"
                            tabindex="0"
                            onclick={() => toggleSection(node.key)}
                            onkeydown={(e) => {
                                if (e.key === "Enter" || e.key === " ") {
                                    e.preventDefault();
                                    toggleSection(node.key);
                                }
                            }}
                        >
                            <span class="flex items-center text-[var(--text-tertiary)] shrink-0">
                                {#if node.collapsed}<ChevronRight size={14} />{:else}<ChevronDown size={14} />{/if}
                            </span>
                            <span
                                class="flex-1 text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wide truncate {node.depth > 0 ? 'text-left' : 'text-center'}"
                            >
                                {node.project.name}
                            </span>
                            <span
                                class="text-xs text-[var(--text-tertiary)] bg-[var(--surface-tertiary)] px-1.5 py-px rounded-lg shrink-0"
                            >
                                {node.count}
                            </span>
                            <!-- Hover actions: rename / delete -->
                            <button
                                class="w-5 h-5 border-none rounded bg-transparent text-[var(--text-tertiary)] cursor-pointer flex items-center justify-center opacity-0 group-hover/hdr:opacity-100 hover:text-[var(--accent)] transition-all shrink-0"
                                onclick={(e) => {
                                    e.stopPropagation();
                                    openProjectModal("rename", node.project);
                                }}
                                title="Rename project"
                            >
                                <Pencil size={11} />
                            </button>
                            <button
                                class="w-5 h-5 border-none rounded bg-transparent text-[var(--text-tertiary)] cursor-pointer flex items-center justify-center opacity-0 group-hover/hdr:opacity-100 hover:text-[var(--color-danger)] transition-all shrink-0"
                                onclick={(e) => {
                                    e.stopPropagation();
                                    openProjectModal("delete", node.project);
                                }}
                                title="Delete project"
                            >
                                <Trash2 size={11} />
                            </button>
                        </div>
                    {:else if node.type === "unassigned-header"}
                        <!-- Unassigned section header -->
                        {#if nodeIdx > 0}
                            <div class="h-px mx-3 my-2 bg-[var(--accent)] opacity-40"></div>
                        {/if}
                        <button
                            class="flex items-center gap-1.5 w-full p-1.5 px-3 border-none rounded-md bg-[var(--surface-secondary)] cursor-pointer text-left transition-colors duration-150 hover:brightness-110"
                            onclick={() => toggleSection(node.key)}
                        >
                            <span class="flex items-center text-[var(--text-tertiary)] shrink-0">
                                {#if node.collapsed}<ChevronRight size={14} />{:else}<ChevronDown size={14} />{/if}
                            </span>
                            <span
                                class="flex-1 text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wide text-center"
                            >
                                Unassigned
                            </span>
                            <span
                                class="text-xs text-[var(--text-tertiary)] bg-[var(--surface-tertiary)] px-1.5 py-px rounded-lg shrink-0"
                            >
                                {node.count}
                            </span>
                        </button>
                    {:else if node.type === "date-header"}
                        <!-- Date group header (under Unassigned) -->
                        <button
                            class="flex items-center gap-1.5 w-full p-1 px-3 border-none bg-transparent cursor-pointer text-left transition-colors duration-150 hover:bg-[var(--hover-overlay)]"
                            style="padding-left: 28px"
                            onclick={() => toggleSection(node.key)}
                        >
                            <span class="flex items-center text-[var(--text-tertiary)] shrink-0">
                                {#if node.collapsed}<ChevronRight size={12} />{:else}<ChevronDown size={12} />{/if}
                            </span>
                            <span class="flex-1 text-xs font-semibold text-[var(--accent)] tracking-wide text-center">
                                {node.label}
                            </span>
                            <span
                                class="text-[10px] text-[var(--text-tertiary)] bg-[var(--surface-tertiary)] px-1 py-px rounded-lg shrink-0"
                            >
                                {node.count}
                            </span>
                        </button>
                    {:else}
                        <!-- Transcript row -->
                        <button
                            class="flex items-stretch w-full p-1 border-none bg-transparent cursor-pointer text-left transition-colors duration-150 hover:bg-[var(--hover-overlay)]"
                            class:bg-[var(--hover-overlay-blue)]={selection.isSelected(node.entry.id)}
                            style="padding-left: {12 + node.depth * 16}px"
                            onclick={(e) => handleEntryClick(node.entry.id, e)}
                            oncontextmenu={(e) => openProjectMenu(e, node.entry.id)}
                        >
                            <!-- Tree connecting line -->
                            {#if node.parentColor}
                                <div class="relative w-4 shrink-0 mr-1">
                                    <!-- Vertical line -->
                                    <div
                                        class="absolute left-1 top-0 w-px"
                                        style="background: {node.parentColor}; opacity: 0.35; height: {node.isLastChild
                                            ? '50%'
                                            : '100%'}"
                                    ></div>
                                    <!-- Horizontal connector -->
                                    <div
                                        class="absolute left-1 top-1/2 h-px w-2.5"
                                        style="background: {node.parentColor}; opacity: 0.35"
                                    ></div>
                                </div>
                            {:else}
                                <div
                                    class="w-0.5 rounded-sm shrink-0 mr-2 transition-colors duration-150"
                                    class:bg-[var(--accent)]={selection.isSelected(node.entry.id)}
                                ></div>
                            {/if}
                            <div class="flex-1 min-w-0 flex flex-col gap-0.5 py-0.5">
                                <span
                                    class="text-sm font-semibold text-[var(--text-primary)] leading-normal overflow-hidden text-ellipsis whitespace-nowrap"
                                >
                                    {getTitle(node.entry)}
                                </span>
                                <span
                                    class="text-xs text-[var(--text-secondary)] leading-snug overflow-hidden text-ellipsis whitespace-nowrap"
                                >
                                    {getDisplayText(node.entry)}
                                </span>
                                <span
                                    class="flex items-center justify-between text-xs text-[var(--text-tertiary)] font-mono"
                                >
                                    <span>{formatTime(node.entry.created_at)}</span>
                                    <span>{wordCount(getDisplayText(node.entry)).toLocaleString()} words</span>
                                </span>
                            </div>
                        </button>
                    {/if}
                {/each}
            {/if}
        </div>
    </div>

    <!-- Detail: Content Panel (50%) -->
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
            <div class="flex-1 flex flex-col p-4 gap-2 overflow-hidden group/detail">
                <!-- Title row: [Generate Title] — Title — [Edit Pencil] -->
                <div class="flex items-center gap-2 shrink-0">
                    <button
                        class="w-7 h-7 shrink-0 border-none rounded bg-transparent text-[var(--text-tertiary)] cursor-pointer flex items-center justify-center transition-colors duration-150 hover:text-[var(--accent)] hover:bg-[var(--hover-overlay)] disabled:opacity-40 disabled:cursor-not-allowed"
                        onclick={handleRetitle}
                        disabled={retitling}
                        title="Generate title"
                    >
                        {#if retitling}
                            <Loader2 size={14} class="animate-spin" />
                        {:else}
                            <RefreshCw size={14} />
                        {/if}
                    </button>
                    <h2
                        class="flex-1 text-xl font-semibold text-[var(--text-primary)] m-0 leading-tight text-center truncate"
                    >
                        {#if editingTitle}
                            <input
                                type="text"
                                class="w-full text-xl font-semibold text-[var(--text-primary)] bg-[var(--surface-primary)] border border-[var(--accent)] rounded px-2 py-1 text-center outline-none"
                                bind:value={editTitleValue}
                                onkeydown={handleTitleKeydown}
                                onblur={commitTitle}
                            />
                        {:else}
                            {getTitle(selectedEntry)}
                        {/if}
                    </h2>
                    {#if !editingTitle}
                        <button
                            class="w-7 h-7 shrink-0 border-none rounded bg-transparent text-[var(--text-tertiary)] cursor-pointer flex items-center justify-center opacity-0 group-hover/detail:opacity-100 transition-all duration-150 hover:text-[var(--accent)] hover:bg-[var(--hover-overlay)]"
                            onclick={startEditTitle}
                            title="Rename transcript"
                        >
                            <Pencil size={14} />
                        </button>
                    {:else}
                        <div class="w-7 shrink-0"></div>
                    {/if}
                </div>
                <div class="h-px bg-[var(--shell-border)] shrink-0"></div>

                <div
                    class="flex flex-wrap justify-center items-center gap-1 shrink-0 text-sm text-[var(--text-secondary)] font-mono"
                >
                    <span>{formatDuration(selectedEntry.duration_ms)}</span>
                    <span class="text-[var(--text-tertiary)]">|</span>
                    <span>{formatDuration(selectedEntry.speech_duration_ms)}</span>
                    <span class="text-[var(--text-tertiary)]">|</span>
                    <span>{selectedWordCount} words</span>
                    <span class="text-[var(--text-tertiary)]">|</span>
                    <span
                        >{formatWpm(
                            selectedWordCount,
                            selectedEntry.speech_duration_ms || selectedEntry.duration_ms,
                        )}</span
                    >
                </div>

                <div class="overflow-hidden flex flex-col relative group flex-1 min-h-[80px]">
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

                {#if visibleVariants.length > 0}
                    <div class="flex-1 min-h-[60px] overflow-y-auto">
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

<!-- Context menu: project assignment -->
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

<!-- Project modal: create / rename / delete -->
{#if showProjectModal}
    <ProjectModal
        mode={projectModalMode}
        target={projectModalTarget}
        {projects}
        onconfirm={handleProjectModalConfirm}
        oncancel={handleProjectModalCancel}
    />
{/if}
