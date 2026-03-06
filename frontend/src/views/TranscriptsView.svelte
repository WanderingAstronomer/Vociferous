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
    import { onMount } from "svelte";
    import {
        Trash2,
        RefreshCw,
        ChevronDown,
        ChevronRight,
        FileText,
        Loader2,
        Pencil,
        Plus,
    } from "lucide-svelte";
    import ProjectModal from "../lib/components/ProjectModal.svelte";
    import type { ProjectModalResult } from "../lib/components/ProjectModal.svelte";
    import TranscriptDetailPanel from "../lib/components/TranscriptDetailPanel.svelte";
    import BulkActionsPanel from "../lib/components/BulkActionsPanel.svelte";
    import ProjectContextMenu from "../lib/components/ProjectContextMenu.svelte";
    import { formatDayHeader, formatTime, formatDuration, formatWpm, wordCount } from "../lib/formatters";

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
    let refining = $state<number | null>(null);
    let filterText = $state("");
    let sectionCollapsed = $state(new Map<string, boolean>());
    let projects: Project[] = $state([]);
    let projectMenuOpen = $state(false);
    let projectMenuX = $state(0);
    let projectMenuY = $state(0);

    let batchAssigning = $state(false);

    /* ===== Project Modal State ===== */

    let showProjectModal = $state(false);
    let projectModalMode = $state<"create" | "edit" | "delete">("create");
    let projectModalTarget = $state<Project | null>(null);

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
            const collapsed = isSectionCollapsed(key);

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
            const collapsed = isSectionCollapsed(key);
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
                    const dateKey = bk;
                    const dateCollapsed = isSectionCollapsed(dateKey);
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

    /* ===== Section collapse ===== */

    /** Returns the default collapsed state for a section key. Prior-day dates default collapsed; everything else defaults expanded. */
    function defaultCollapsed(key: string): boolean {
        return key.startsWith("date-") && key !== "date-today";
    }

    /** Returns whether a section is currently collapsed, respecting user overrides and defaults. */
    function isSectionCollapsed(key: string): boolean {
        const explicit = sectionCollapsed.get(key);
        return explicit !== undefined ? explicit : defaultCollapsed(key);
    }

    function toggleSection(key: string) {
        const next = new Map(sectionCollapsed);
        next.set(key, !isSectionCollapsed(key));
        sectionCollapsed = next;
    }

    /* ===== Formatting ===== */

    function getDisplayText(entry: Transcript): string {
        return entry.normalized_text || entry.raw_text || "";
    }

    function getTitle(entry: Transcript): string {
        if (entry.display_name?.trim()) return entry.display_name.trim();
        return `Transcript #${entry.id}`;
    }

    /* ===== Data loading ===== */

    async function loadTranscripts() {
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

    async function loadEntryDetail(id: number, force = false) {
        if (selectedId === id && !force) return;
        selectedId = id;
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

    function editSelected() {
        if (!selectedEntry) return;
        nav.navigateToEdit(selectedEntry.id, { view: "transcripts", transcriptId: selectedEntry.id });
    }

    /** Called by TranscriptDetailPanel when a title is renamed inline. */
    function handleTitleRenamed(id: number, newTitle: string) {
        if (selectedEntry && selectedEntry.id === id) {
            selectedEntry.display_name = newTitle;
        }
        const idx = entries.findIndex((e) => e.id === id);
        if (idx >= 0) entries[idx].display_name = newTitle;
        entries = [...entries];
    }

    /** Called by TranscriptDetailPanel after a variant is deleted. */
    function handleVariantDeleted() {
        if (selectedEntry) loadEntryDetail(selectedEntry.id, true);
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
            if (selectedEntry && ids.includes(selectedEntry.id)) {
                selectedEntry = await getTranscript(selectedEntry.id);
            }
            loadTranscripts();
        } catch (err: any) {
            console.error("Failed to assign project:", err);
        } finally {
            batchAssigning = false;
        }
    }

    /* ===== Project Modal ===== */

    function openProjectModal(mode: "create" | "edit" | "delete", target: Project | null = null) {
        projectModalMode = mode;
        projectModalTarget = target;
        showProjectModal = true;
    }

    async function handleProjectModalConfirm(result: ProjectModalResult) {
        showProjectModal = false;
        try {
            if (result.mode === "create") {
                await createProject(result.name, result.color, result.parentId);
            } else if (result.mode === "edit") {
                await updateProject(result.id, { name: result.name, color: result.color, parent_id: result.parentId });
            } else if (result.mode === "delete") {
                await deleteProject(result.id, {
                    deleteTranscripts: result.deleteTranscripts,
                    promoteSubprojects: result.promoteSubprojects,
                    deleteSubprojectTranscripts: result.deleteSubprojectTranscripts,
                });
            }
            projects = await getProjects();
            await loadTranscripts();
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
            const tag = (event.target as HTMLElement)?.tagName;
            if (tag === "INPUT" || tag === "TEXTAREA") return;
            event.preventDefault();
            selection.selectAll(orderedIds);
            selectedId = null;
            selectedEntry = null;
        }
    }

    /* ===== WebSocket ===== */

    onMount(() => {
        loadTranscripts().then(() => {
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
            ws.on("transcription_complete", () => loadTranscripts()),
            ws.on("transcript_deleted", (data) => {
                entries = entries.filter((e) => e.id !== data.id);
                if (selectedId === data.id) {
                    selectedId = null;
                    selectedEntry = null;
                }
            }),
            ws.on("refinement_complete", (data) => {
                refining = null;
                if (selectedId === data.transcript_id) loadEntryDetail(data.transcript_id, true);
                loadTranscripts();
            }),
            ws.on("refinement_error", () => {
                refining = null;
            }),
            ws.on("transcript_updated", (data) => {
                if (selectedId === data.id) loadEntryDetail(data.id, true);
                loadTranscripts();
            }),
            ws.on("project_created", () => {
                getProjects()
                    .then((p) => (projects = p))
                    .catch(() => {});
            }),
            ws.on("project_updated", () => {
                getProjects()
                    .then((p) => (projects = p))
                    .catch(() => {});
            }),
            ws.on("project_deleted", () => {
                getProjects()
                    .then((p) => (projects = p))
                    .catch(() => {});
                loadTranscripts();
            }),
        ];
        return () => {
            unsubs.forEach((fn) => fn());
            document.removeEventListener("pointerdown", handleGlobalPointerDown);
            document.removeEventListener("keydown", handleGlobalKeydown);
        };
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
                onclick={loadTranscripts}
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
                        <!-- Divider before each top-level project except the first node -->
                        {#if node.depth === 0 && nodeIdx > 0}
                            <div class="h-px mx-3 my-3 bg-[var(--accent)] opacity-60"></div>
                        {/if}
                        <!-- Project header row -->
                        <div
                            class="group/hdr flex items-center gap-1.5 pl-3 pr-1.5 rounded-md cursor-pointer text-left transition-colors duration-150 hover:brightness-110 {node.depth ===
                            0
                                ? 'py-2'
                                : 'py-1.5'}"
                            style="margin-left: calc({node.depth * 16}px + 4px); width: calc(100% - {node.depth *
                                16}px - 12px); background: {node.project.color
                                ? `color-mix(in srgb, ${node.project.color} 35%, transparent)`
                                : 'var(--surface-secondary)'}; {node.depth === 0
                                ? `border-left: 3px solid ${node.project.color ?? 'var(--accent-muted)'};`
                                : ''}"
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
                            {#if node.depth > 0 && node.project.color}
                                <span
                                    class="shrink-0 rounded-full"
                                    style="width: 7px; height: 7px; background: {node.project.color}; opacity: 0.85;"
                                ></span>
                            {/if}
                            <span
                                class="flex-1 text-xs font-semibold {node.depth === 0
                                    ? 'text-[var(--text-primary)]'
                                    : 'text-[var(--text-secondary)]'} uppercase tracking-wide truncate {node.depth > 0
                                    ? 'text-left'
                                    : 'text-center'}"
                            >
                                {node.project.name}
                            </span>
                            <!-- Hover actions: edit / delete (left of count) -->
                            <button
                                class="w-5 h-5 border-none rounded bg-transparent text-[var(--text-tertiary)] cursor-pointer flex items-center justify-center opacity-0 group-hover/hdr:opacity-100 hover:text-[var(--accent)] transition-all shrink-0"
                                onclick={(e) => {
                                    e.stopPropagation();
                                    openProjectModal("edit", node.project);
                                }}
                                title="Edit project"
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
                            <!-- Count badge (always rightmost) -->
                            <span
                                class="text-xs font-semibold px-1.5 py-px rounded-lg shrink-0"
                                style={node.project.color
                                    ? `background: color-mix(in srgb, ${node.project.color} 25%, var(--surface-tertiary)); color: var(--text-primary);`
                                    : "background: var(--surface-tertiary); color: var(--text-primary);"}
                            >
                                {node.count}
                            </span>
                        </div>
                    {:else if node.type === "unassigned-header"}
                        <!-- Unassigned section header -->
                        {#if nodeIdx > 0}
                            <div class="h-px mx-3 my-3 bg-[var(--accent)] opacity-60"></div>
                        {/if}
                        <button
                            class="flex items-center gap-1.5 p-1.5 px-3 border-none rounded-md bg-[var(--surface-secondary)] cursor-pointer text-left transition-colors duration-150 hover:brightness-110"
                            style="margin-left: 4px; width: calc(100% - 12px);"
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
                                class="text-xs font-semibold text-[var(--text-primary)] bg-[var(--surface-tertiary)] px-1.5 py-px rounded-lg shrink-0"
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
                            <!-- Selection accent bar (always shown) -->
                            <div
                                class="w-0.5 rounded-sm shrink-0 mr-1 transition-colors duration-150"
                                class:bg-[var(--accent)]={selection.isSelected(node.entry.id)}
                            ></div>
                            <!-- Tree connecting line (project-assigned only) -->
                            {#if node.parentColor}
                                <div class="relative w-4 shrink-0 mr-1">
                                    <!-- Vertical line -->
                                    <div
                                        class="absolute left-1 top-0 w-px"
                                        style="background: {node.parentColor}; opacity: 0.6; height: {node.isLastChild
                                            ? '50%'
                                            : '100%'}"
                                    ></div>
                                    <!-- Horizontal connector -->
                                    <div
                                        class="absolute left-1 top-1/2 h-px w-2.5"
                                        style="background: {node.parentColor}; opacity: 0.6"
                                    ></div>
                                </div>
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
            <BulkActionsPanel
                count={selection.count}
                onAssignProject={(e) => openProjectMenu(e, selection.ids[0])}
                onDelete={handleDelete}
            />
        {:else if selectedEntry}
            <TranscriptDetailPanel
                entry={selectedEntry}
                {refining}
                onEdit={editSelected}
                onRefine={handleRefine}
                onDelete={handleDelete}
                onTitleRenamed={handleTitleRenamed}
                onVariantDeleted={handleVariantDeleted}
            />
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
    <ProjectContextMenu
        x={projectMenuX}
        y={projectMenuY}
        options={projectOptions}
        isMulti={selection.isMulti}
        selectionCount={selection.count}
        currentProjectId={selectedEntry?.project_id?.toString() ?? ""}
        onSelect={assignProjectFromContext}
    />
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
