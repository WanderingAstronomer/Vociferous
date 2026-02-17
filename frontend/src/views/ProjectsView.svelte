<script lang="ts">
    import { onMount, onDestroy } from "svelte";
    import {
        getProjects,
        createProject,
        deleteProject,
        getTranscripts,
        deleteTranscript,
        refineTranscript,
        assignProject,
        batchAssignProject,
        batchDeleteTranscripts,
        type Project,
        type Transcript,
    } from "../lib/api";
    import { ws } from "../lib/ws";
    import { SelectionManager } from "../lib/selection.svelte";
    import WorkspacePanel from "../lib/components/WorkspacePanel.svelte";
    import {
        FolderOpen,
        Plus,
        Trash2,
        ChevronDown,
        ChevronRight,
        FileText,
        Copy,
        Check,
        Sparkles,
        Palette,
        Calendar,
        Clock,
        Hash,
        Gauge,
        Loader2,
        ArrowUpDown,
    } from "lucide-svelte";

    /* ── Project Color Palette ── */
    const PROJECT_COLORS = [
        { value: "#2d5a7b", name: "Ocean Blue", css: "var(--project-ocean)" },
        { value: "#3d8b40", name: "Forest Green", css: "var(--project-forest)" },
        { value: "#cc8400", name: "Goldenrod", css: "var(--project-goldenrod)" },
        { value: "#5e1d9b", name: "Amethyst", css: "var(--project-amethyst)" },
        { value: "#7a3535", name: "Brick Red", css: "var(--project-brick)" },
        { value: "#5a9fd4", name: "Teal", css: "var(--project-teal)" },
    ];

    /* ── State ── */
    let projects: Project[] = $state([]);
    let selectedProjectId: number | null = $state(null);
    /** Per-project transcript cache: projectId → transcripts */
    let projectTranscriptMap: Map<number, Transcript[]> = $state(new Map());
    let selectedTranscriptId: number | null = $state(null);
    let selectedTranscript: Transcript | null = $state(null);

    let expandedProjects: Set<number> = $state(new Set());
    let loading = $state(true);
    let loadingProjects: Set<number> = $state(new Set());
    let copied = $state(false);
    let projectMenuOpen = $state(false);
    let projectMenuX = $state(0);
    let projectMenuY = $state(0);
    let projectMenuTranscriptId = $state<number | null>(null);
    let batchAssigning = $state(false);

    /** Sort direction for root projects: asc or desc by name */
    let sortAsc = $state(true);

    /* Create project form */
    let showCreateForm = $state(false);
    let newProjectName = $state("");
    let newProjectColor = $state(PROJECT_COLORS[0].value);
    let creating = $state(false);
    let createParentId: number | null = $state(null);

    /* ── Multi-Selection ── */
    const selection = new SelectionManager();

    /**
     * Get ordered IDs for range-selection within a specific project's transcript list.
     * Returns all transcript IDs across all expanded projects in display order.
     */
    let allVisibleTranscriptIds = $derived.by(() => {
        const ids: number[] = [];
        // Walk root projects in display order
        for (const project of rootProjects) {
            if (expandedProjects.has(project.id)) {
                const transcripts = projectTranscriptMap.get(project.id) ?? [];
                ids.push(...transcripts.map((t) => t.id));
            }
            // Walk children
            const children = childProjectMap.get(project.id) ?? [];
            for (const child of children) {
                if (expandedProjects.has(child.id)) {
                    const transcripts = projectTranscriptMap.get(child.id) ?? [];
                    ids.push(...transcripts.map((t) => t.id));
                }
            }
        }
        return ids;
    });

    /* ── Derived: Tree structure ── */
    let rootProjects = $derived(
        [...projects.filter((p) => !p.parent_id)].sort((a, b) => {
            const cmp = a.name.localeCompare(b.name);
            return sortAsc ? cmp : -cmp;
        }),
    );
    let childProjectMap = $derived(
        projects.reduce((map, p) => {
            if (p.parent_id) {
                if (!map.has(p.parent_id)) map.set(p.parent_id, []);
                map.get(p.parent_id)!.push(p);
            }
            return map;
        }, new Map<number, Project[]>()),
    );

    let projectOptions = $derived.by(() => {
        const byId = new Map(projects.map((p) => [p.id, p]));
        const opts: { value: string; label: string }[] = [{ value: "", label: "No Project" }];
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

    let visibleSelectedVariants = $derived.by(() => {
        if (!selectedTranscript || !selectedTranscript.variants) {
            return [];
        }
        return selectedTranscript.variants.filter(
            (variant: { kind: string }) => variant.kind.trim().toLowerCase() !== "raw",
        );
    });

    /* ── Data fetching ── */
    async function loadProjects() {
        try {
            projects = await getProjects();
        } catch (e) {
            console.error("Failed to load projects:", e);
        } finally {
            loading = false;
        }
    }

    async function loadProjectTranscripts(projectId: number) {
        const nextLoading = new Set(loadingProjects);
        nextLoading.add(projectId);
        loadingProjects = nextLoading;
        try {
            const transcripts = await getTranscripts(200, projectId);
            const nextMap = new Map(projectTranscriptMap);
            nextMap.set(projectId, transcripts);
            projectTranscriptMap = nextMap;
        } catch (e) {
            console.error("Failed to load project transcripts:", e);
            const nextMap = new Map(projectTranscriptMap);
            nextMap.set(projectId, []);
            projectTranscriptMap = nextMap;
        } finally {
            const nextLoading2 = new Set(loadingProjects);
            nextLoading2.delete(projectId);
            loadingProjects = nextLoading2;
        }
    }

    /* ── Actions ── */
    async function handleCreateProject() {
        if (!newProjectName.trim() || creating) return;
        creating = true;
        try {
            await createProject(newProjectName.trim(), newProjectColor, createParentId);
            newProjectName = "";
            newProjectColor = PROJECT_COLORS[0].value;
            createParentId = null;
            showCreateForm = false;
            await loadProjects();
        } catch (e) {
            console.error("Failed to create project:", e);
        } finally {
            creating = false;
        }
    }

    function handleAddSubProject(parentId: number, e: Event) {
        e.stopPropagation();
        createParentId = parentId;
        showCreateForm = true;
    }

    function cancelCreate() {
        showCreateForm = false;
        createParentId = null;
        newProjectName = "";
        newProjectColor = PROJECT_COLORS[0].value;
    }

    async function handleDeleteProject(id: number, e: Event) {
        e.stopPropagation();
        if (!confirm("Delete this project? Transcripts will be unassigned, not deleted.")) return;
        try {
            await deleteProject(id);
            if (selectedProjectId === id) {
                selectedProjectId = null;
                selectedTranscriptId = null;
                selectedTranscript = null;
            }
            const nextMap = new Map(projectTranscriptMap);
            nextMap.delete(id);
            projectTranscriptMap = nextMap;
            await loadProjects();
        } catch (err) {
            console.error("Failed to delete project:", err);
        }
    }

    function toggleProject(id: number) {
        const next = new Set(expandedProjects);
        if (next.has(id)) {
            next.delete(id);
        } else {
            next.add(id);
            // Load transcripts when expanding if not cached
            if (!projectTranscriptMap.has(id)) {
                loadProjectTranscripts(id);
            }
        }
        expandedProjects = next;
    }

    function selectProject(id: number) {
        selectedProjectId = id;
        selectedTranscriptId = null;
        selectedTranscript = null;
        selection.clear();
        if (!expandedProjects.has(id)) {
            toggleProject(id);
        } else if (!projectTranscriptMap.has(id)) {
            loadProjectTranscripts(id);
        }
    }

    /** Handle click on a transcript row. Uses SelectionManager for multi-select. */
    function handleTranscriptClick(t: Transcript, event: MouseEvent) {
        selection.handleClick(t.id, event, allVisibleTranscriptIds);

        if (selection.count === 1) {
            selectedTranscriptId = t.id;
            selectedTranscript = t;
        } else {
            // Multi-select: clear single detail view
            selectedTranscriptId = null;
            selectedTranscript = null;
        }
    }

    async function handleDeleteTranscript(id?: number) {
        try {
            if (selection.isMulti) {
                const count = selection.count;
                if (!confirm(`Delete ${count} transcripts? This cannot be undone.`)) return;
                await batchDeleteTranscripts(selection.ids);
                selection.clear();
                selectedTranscriptId = null;
                selectedTranscript = null;
            } else {
                const targetId = id ?? selectedTranscriptId;
                if (targetId == null) return;
                await deleteTranscript(targetId);
                if (selectedTranscriptId === targetId) {
                    selectedTranscriptId = null;
                    selectedTranscript = null;
                }
                selection.clear();
            }
            // Reload transcripts for all expanded projects
            for (const pid of expandedProjects) {
                loadProjectTranscripts(pid);
            }
        } catch (e) {
            console.error("Failed to delete transcript:", e);
        }
    }

    async function handleRefine(id: number) {
        try {
            await refineTranscript(id, 1);
        } catch (e) {
            console.error("Failed to refine:", e);
        }
    }

    function handleCopy(text: string) {
        navigator.clipboard.writeText(text);
        copied = true;
        setTimeout(() => (copied = false), 2000);
    }

    function openProjectMenu(event: MouseEvent, transcriptId: number) {
        event.preventDefault();
        event.stopPropagation();

        // Auto-select if right-clicked item not already in selection
        if (!selection.isSelected(transcriptId)) {
            selection.selectOnly(transcriptId);
            for (const transcripts of projectTranscriptMap.values()) {
                const found = transcripts.find((t) => t.id === transcriptId);
                if (found) {
                    selectedTranscriptId = found.id;
                    selectedTranscript = found;
                    break;
                }
            }
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

    function getTranscriptProjectValue(transcriptId: number): string {
        if (selectedTranscript?.id === transcriptId) {
            return selectedTranscript.project_id?.toString() ?? "";
        }
        for (const transcripts of projectTranscriptMap.values()) {
            const found = transcripts.find((t) => t.id === transcriptId);
            if (found) return found.project_id?.toString() ?? "";
        }
        return "";
    }

    async function assignProjectFromContext(value: string) {
        const projectId = value === "" ? null : parseInt(value, 10);
        closeProjectMenu();

        const idsToAssign = selection.hasSelection
            ? selection.ids
            : projectMenuTranscriptId != null
              ? [projectMenuTranscriptId]
              : [];
        if (idsToAssign.length === 0) return;

        try {
            batchAssigning = true;
            await batchAssignProject(idsToAssign, projectId);

            if (selectedTranscript && idsToAssign.includes(selectedTranscript.id)) {
                const nextProjectName =
                    projectId != null ? (projects.find((p) => p.id === projectId)?.name ?? null) : null;
                selectedTranscript = {
                    ...selectedTranscript,
                    project_id: projectId,
                    project_name: nextProjectName,
                };
            }

            for (const pid of expandedProjects) {
                loadProjectTranscripts(pid);
            }
            selection.clear();
        } catch (err) {
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
            if (projectMenuOpen) {
                closeProjectMenu();
            } else if (selection.hasSelection) {
                selection.clear();
                selectedTranscriptId = null;
                selectedTranscript = null;
            }
        }
        if ((event.ctrlKey || event.metaKey) && event.key === "a" && allVisibleTranscriptIds.length > 0) {
            event.preventDefault();
            selection.selectAll(allVisibleTranscriptIds);
            selectedTranscriptId = null;
            selectedTranscript = null;
        }
    }

    /* ── Formatting ── */
    function formatDate(iso: string): string {
        const d = new Date(iso);
        const month = d.toLocaleString("en-US", { month: "short" });
        const day = d.getDate();
        const suffix =
            day === 1 || day === 21 || day === 31
                ? "st"
                : day === 2 || day === 22
                  ? "nd"
                  : day === 3 || day === 23
                    ? "rd"
                    : "th";
        return `${month} ${day}${suffix}, ${d.getFullYear()}`;
    }

    function formatTime(iso: string): string {
        const d = new Date(iso);
        let h = d.getHours();
        const m = d.getMinutes().toString().padStart(2, "0");
        const period = h >= 12 ? "p.m." : "a.m.";
        h = h % 12 || 12;
        return `${h}:${m} ${period}`;
    }

    function formatDuration(ms: number): string {
        const s = Math.round(ms / 1000);
        if (s < 60) return `${s}s`;
        const m = Math.floor(s / 60);
        const rem = s % 60;
        return rem > 0 ? `${m}m ${rem}s` : `${m}m`;
    }

    function getProjectColor(project: Project): string {
        if (!project.color) return "var(--accent)";
        const match = PROJECT_COLORS.find((c) => c.value === project.color);
        return match ? match.css : project.color;
    }

    function truncateText(text: string, max = 60): string {
        if (text.length <= max) return text;
        return text.slice(0, max) + "…";
    }

    /* ── Lifecycle ── */
    let unsubTranscriptDeleted: (() => void) | undefined;
    let unsubTranscriptionComplete: (() => void) | undefined;

    onMount(() => {
        loadProjects();
        document.addEventListener("pointerdown", handleGlobalPointerDown);
        document.addEventListener("keydown", handleGlobalKeydown);
        unsubTranscriptDeleted = ws.on("transcript_deleted", () => {
            for (const pid of expandedProjects) loadProjectTranscripts(pid);
        });
        unsubTranscriptionComplete = ws.on("transcription_complete", () => {
            for (const pid of expandedProjects) loadProjectTranscripts(pid);
        });
    });

    onDestroy(() => {
        unsubTranscriptDeleted?.();
        unsubTranscriptionComplete?.();
        document.removeEventListener("pointerdown", handleGlobalPointerDown);
        document.removeEventListener("keydown", handleGlobalKeydown);
    });
</script>

<div class="flex h-full bg-[var(--surface-primary)]">
    <!-- Master Pane: Project Tree -->
    <aside
        class="w-2/5 min-w-[280px] max-w-[420px] flex flex-col border-r border-[var(--shell-border)] bg-[var(--surface-primary)]"
    >
        <div class="flex items-center justify-between p-4 pb-3 border-b border-[var(--shell-border)]">
            <h2 class="text-lg font-semibold text-[var(--accent)] m-0">Projects</h2>
            <div class="flex items-center gap-1">
                <button
                    class="bg-transparent border-none text-[var(--text-secondary)] cursor-pointer p-1 rounded flex items-center transition-colors duration-150 hover:text-[var(--accent)] hover:bg-[var(--hover-overlay)]"
                    title={sortAsc ? "Sort Z→A" : "Sort A→Z"}
                    onclick={() => (sortAsc = !sortAsc)}
                >
                    <ArrowUpDown size={15} />
                </button>
                <button
                    class="bg-transparent border-none text-[var(--text-secondary)] cursor-pointer p-1 rounded flex items-center transition-colors duration-150 hover:text-[var(--accent)] hover:bg-[var(--hover-overlay)]"
                    title="New Project"
                    onclick={() => (showCreateForm = !showCreateForm)}
                >
                    <Plus size={18} />
                </button>
            </div>
        </div>

        <!-- Create Project Form -->
        {#if showCreateForm}
            <form
                class="p-3 px-4 border-b border-[var(--shell-border)] flex flex-col gap-2"
                onsubmit={(e) => {
                    e.preventDefault();
                    handleCreateProject();
                }}
            >
                {#if createParentId}
                    {@const parent = projects.find((p) => p.id === createParentId)}
                    <div
                        class="flex items-center gap-2 p-2 px-3 text-xs text-[var(--text-muted)] bg-[var(--surface-overlay)] rounded mb-2"
                    >
                        <span
                            class="w-2.5 h-2.5 rounded-full shrink-0"
                            style="background: {parent ? getProjectColor(parent) : 'var(--text-muted)'}"
                        ></span>
                        Sub-project of <strong class="text-[var(--text-primary)]">{parent?.name ?? "Unknown"}</strong>
                        <button
                            type="button"
                            class="bg-transparent border-none text-[var(--text-secondary)] cursor-pointer p-1 rounded flex items-center transition-colors duration-150 hover:text-[var(--accent)] hover:bg-[var(--hover-overlay)]"
                            title="Clear parent"
                            onclick={() => (createParentId = null)}>✕</button
                        >
                    </div>
                {/if}
                <input
                    class="w-full p-2 px-3 border border-[var(--shell-border)] rounded bg-[var(--surface-secondary)] text-[var(--text-primary)] text-sm outline-none transition-colors duration-150 focus:border-[var(--accent)]"
                    type="text"
                    placeholder="Project name…"
                    bind:value={newProjectName}
                />
                <div class="flex gap-2 justify-center">
                    {#each PROJECT_COLORS as color}
                        <button
                            type="button"
                            class="w-6 h-6 rounded-full border-2 border-transparent cursor-pointer transition-transform duration-150 hover:scale-115 active:scale-95"
                            class:shadow-[0_0_0_2px_var(--surface-primary)]={newProjectColor === color.value}
                            class:border-[var(--text-primary)]={newProjectColor === color.value}
                            style="background-color: {color.css}"
                            title={color.name}
                            onclick={() => (newProjectColor = color.value)}
                        ></button>
                    {/each}
                </div>
                <div class="flex gap-2">
                    <button
                        type="submit"
                        class="flex-1 p-1 px-3 border-none rounded bg-[var(--accent)] text-[var(--text-primary)] text-sm font-semibold cursor-pointer transition-opacity duration-150 disabled:opacity-50 disabled:cursor-not-allowed"
                        disabled={!newProjectName.trim() || creating}
                    >
                        {creating ? "Creating…" : "Create"}
                    </button>
                    <button
                        type="button"
                        class="p-1 px-3 border border-[var(--shell-border)] rounded bg-transparent text-[var(--text-secondary)] text-sm cursor-pointer transition-colors duration-150 hover:text-[var(--text-primary)]"
                        onclick={cancelCreate}
                    >
                        Cancel
                    </button>
                </div>
            </form>
        {/if}

        <!-- Project List -->
        <div class="flex-1 overflow-y-auto py-2">
            {#if loading}
                <div class="flex flex-col items-center justify-center gap-2 py-16 px-4 text-[var(--text-tertiary)]">
                    <Loader2 size={20} class="animate-spin" />
                    <span>Loading…</span>
                </div>
            {:else if projects.length === 0}
                <div class="flex flex-col items-center justify-center gap-2 py-16 px-4 text-[var(--text-tertiary)]">
                    <FolderOpen size={32} strokeWidth={1.5} />
                    <p>No projects yet</p>
                    <p class="text-xs text-[var(--text-tertiary)] m-0">Create one to organize your transcripts</p>
                </div>
            {:else}
                {#each rootProjects as project (project.id)}
                    <div>
                        <!-- Project Header -->
                        <!-- svelte-ignore a11y_click_events_have_key_events -->
                        <div
                            class="flex items-center gap-2 w-full p-2 px-3 border-none bg-transparent text-[var(--text-primary)] text-base cursor-pointer text-left transition-colors duration-150 hover:bg-[var(--hover-overlay)] group/project"
                            class:bg-[rgba(90,159,212,0.1)]={selectedProjectId === project.id}
                            role="button"
                            tabindex="0"
                            onclick={() => selectProject(project.id)}
                        >
                            <button
                                type="button"
                                class="flex items-center bg-transparent border-none p-0 text-[var(--text-tertiary)] cursor-pointer shrink-0"
                                onclick={(e) => {
                                    e.stopPropagation();
                                    toggleProject(project.id);
                                }}
                            >
                                {#if expandedProjects.has(project.id)}
                                    <ChevronDown size={14} />
                                {:else}
                                    <ChevronRight size={14} />
                                {/if}
                            </button>
                            <span
                                class="w-2.5 h-2.5 rounded-full shrink-0"
                                style="background: {getProjectColor(project)}"
                            ></span>
                            <span class="flex-1 overflow-hidden text-ellipsis whitespace-nowrap font-semibold"
                                >{project.name}</span
                            >
                            <button
                                class="bg-transparent border-none text-[var(--text-secondary)] cursor-pointer p-1 rounded flex items-center transition-colors duration-150 hover:text-[var(--accent)] hover:bg-[var(--hover-overlay)] opacity-0 group-hover/project:opacity-100"
                                title="Add Sub-project"
                                onclick={(e) => handleAddSubProject(project.id, e)}
                            >
                                <Plus size={13} />
                            </button>
                            <button
                                class="bg-transparent border-none text-[var(--text-secondary)] cursor-pointer p-1 rounded flex items-center transition-colors duration-150 hover:text-[var(--accent)] hover:bg-[var(--hover-overlay)] opacity-0 group-hover/project:opacity-100"
                                title="Delete Project"
                                onclick={(e) => handleDeleteProject(project.id, e)}
                            >
                                <Trash2 size={13} />
                            </button>
                        </div>

                        <!-- Nested Transcripts -->
                        {#if expandedProjects.has(project.id)}
                            <div class="pl-12">
                                {#if loadingProjects.has(project.id)}
                                    <div class="p-2 px-3 text-sm text-[var(--text-tertiary)] flex items-center gap-2">
                                        <Loader2 size={14} class="animate-spin" />
                                        <span>Loading…</span>
                                    </div>
                                {:else if (projectTranscriptMap.get(project.id) ?? []).length === 0}
                                    <div class="p-2 px-3 text-sm text-[var(--text-tertiary)] flex items-center gap-2">
                                        No transcripts
                                    </div>
                                {:else}
                                    {#each projectTranscriptMap.get(project.id) ?? [] as t (t.id)}
                                        <button
                                            class="flex items-center gap-2 w-full p-1 px-3 border-none bg-transparent text-[var(--text-secondary)] text-base cursor-pointer text-left transition-colors duration-150 rounded hover:bg-[var(--hover-overlay)] hover:text-[var(--text-primary)]"
                                            class:bg-[rgba(90,159,212,0.12)]={selection.isSelected(t.id)}
                                            class:text-[var(--accent)]={selection.isSelected(t.id)}
                                            onclick={(e) => handleTranscriptClick(t, e)}
                                            oncontextmenu={(e) => openProjectMenu(e, t.id)}
                                        >
                                            <FileText size={13} />
                                            <span class="overflow-hidden text-ellipsis whitespace-nowrap"
                                                >{truncateText(t.text)}</span
                                            >
                                        </button>
                                    {/each}
                                {/if}
                            </div>
                        {/if}

                        <!-- Child Projects -->
                        {#if childProjectMap.has(project.id)}
                            {#each childProjectMap.get(project.id) ?? [] as child (child.id)}
                                <div class="pl-8">
                                    <!-- svelte-ignore a11y_click_events_have_key_events -->
                                    <div
                                        class="flex items-center gap-2 w-full p-2 px-3 border-none bg-transparent text-[var(--text-primary)] text-base cursor-pointer text-left transition-colors duration-150 hover:bg-[var(--hover-overlay)] group/child"
                                        class:bg-[rgba(90,159,212,0.1)]={selectedProjectId === child.id}
                                        role="button"
                                        tabindex="0"
                                        onclick={() => selectProject(child.id)}
                                    >
                                        <button
                                            type="button"
                                            class="flex items-center bg-transparent border-none p-0 text-[var(--text-tertiary)] cursor-pointer shrink-0"
                                            onclick={(e) => {
                                                e.stopPropagation();
                                                toggleProject(child.id);
                                            }}
                                        >
                                            {#if expandedProjects.has(child.id)}
                                                <ChevronDown size={14} />
                                            {:else}
                                                <ChevronRight size={14} />
                                            {/if}
                                        </button>
                                        <span
                                            class="w-2.5 h-2.5 rounded-full shrink-0"
                                            style="background: {getProjectColor(child)}"
                                        ></span>
                                        <span
                                            class="flex-1 overflow-hidden text-ellipsis whitespace-nowrap font-semibold"
                                            >{child.name}</span
                                        >
                                        <button
                                            class="bg-transparent border-none text-[var(--text-secondary)] cursor-pointer p-1 rounded flex items-center transition-colors duration-150 hover:text-[var(--accent)] hover:bg-[var(--hover-overlay)] opacity-0 group-hover/child:opacity-100"
                                            title="Delete Sub-project"
                                            onclick={(e) => handleDeleteProject(child.id, e)}
                                        >
                                            <Trash2 size={13} />
                                        </button>
                                    </div>

                                    {#if expandedProjects.has(child.id)}
                                        <div class="pl-12">
                                            {#if loadingProjects.has(child.id)}
                                                <div
                                                    class="p-2 px-3 text-sm text-[var(--text-tertiary)] flex items-center gap-2"
                                                >
                                                    <Loader2 size={14} class="animate-spin" />
                                                    <span>Loading…</span>
                                                </div>
                                            {:else if (projectTranscriptMap.get(child.id) ?? []).length === 0}
                                                <div
                                                    class="p-2 px-3 text-sm text-[var(--text-tertiary)] flex items-center gap-2"
                                                >
                                                    No transcripts
                                                </div>
                                            {:else}
                                                {#each projectTranscriptMap.get(child.id) ?? [] as t (t.id)}
                                                    <button
                                                        class="flex items-center gap-2 w-full p-1 px-3 border-none bg-transparent text-[var(--text-secondary)] text-base cursor-pointer text-left transition-colors duration-150 rounded hover:bg-[var(--hover-overlay)] hover:text-[var(--text-primary)]"
                                                        class:bg-[rgba(90,159,212,0.12)]={selection.isSelected(t.id)}
                                                        class:text-[var(--accent)]={selection.isSelected(t.id)}
                                                        onclick={(e) => handleTranscriptClick(t, e)}
                                                        oncontextmenu={(e) => openProjectMenu(e, t.id)}
                                                    >
                                                        <FileText size={13} />
                                                        <span class="overflow-hidden text-ellipsis whitespace-nowrap"
                                                            >{truncateText(t.text)}</span
                                                        >
                                                    </button>
                                                {/each}
                                            {/if}
                                        </div>
                                    {/if}
                                </div>
                            {/each}
                        {/if}
                    </div>
                {/each}
            {/if}
        </div>
    </aside>

    <!-- Detail Pane -->
    <section class="flex-1 overflow-y-auto px-[var(--space-5)] py-[var(--space-5)] bg-[var(--surface-secondary)]">
        {#if selectedTranscript}
            <div class="max-w-[var(--content-max-width)]">
                <h3
                    class="text-[var(--text-lg)] font-[var(--weight-emphasis)] text-[var(--text-primary)] m-0 mb-[var(--space-3)]"
                >
                    {selectedTranscript.display_name || `Transcript #${selectedTranscript.id}`}
                </h3>

                <!-- Metrics Strip -->
                <div class="flex flex-wrap gap-[var(--space-1)] mb-[var(--space-4)]">
                    <span
                        class="inline-flex items-center gap-1.5 px-[var(--space-2)] py-1 rounded-[var(--radius-sm)] bg-[var(--surface-primary)] text-[var(--text-xs)] text-[var(--text-secondary)] border border-[var(--shell-border)]"
                        ><Hash size={12} /> #{selectedTranscript.id}</span
                    >
                    <span
                        class="inline-flex items-center gap-1.5 px-[var(--space-2)] py-1 rounded-[var(--radius-sm)] bg-[var(--surface-primary)] text-[var(--text-xs)] text-[var(--text-secondary)] border border-[var(--shell-border)]"
                        ><Calendar size={12} /> {formatDate(selectedTranscript.timestamp)}</span
                    >
                    <span
                        class="inline-flex items-center gap-1.5 px-[var(--space-2)] py-1 rounded-[var(--radius-sm)] bg-[var(--surface-primary)] text-[var(--text-xs)] text-[var(--text-secondary)] border border-[var(--shell-border)]"
                        ><Clock size={12} /> {formatTime(selectedTranscript.timestamp)}</span
                    >
                    {#if selectedTranscript.duration_ms}
                        <span
                            class="inline-flex items-center gap-1.5 px-[var(--space-2)] py-1 rounded-[var(--radius-sm)] bg-[var(--surface-primary)] text-[var(--text-xs)] text-[var(--text-secondary)] border border-[var(--shell-border)]"
                            ><Gauge size={12} /> {formatDuration(selectedTranscript.duration_ms)}</span
                        >
                    {/if}
                </div>

                <!-- Text -->
                <WorkspacePanel>
                    <p class="text-base leading-relaxed text-[var(--text-primary)] m-0 whitespace-pre-wrap">
                        {selectedTranscript.text}
                    </p>
                </WorkspacePanel>
                <p class="mt-[var(--space-2)] text-[var(--text-xs)] text-[var(--text-tertiary)] opacity-50">
                    Tip: Right-click transcript rows to reassign project
                </p>

                <!-- Variants -->
                {#if visibleSelectedVariants.length > 0}
                    <div class="mt-6">
                        <h4 class="text-sm font-semibold text-[var(--text-secondary)] m-0 mb-3 uppercase tracking-wide">
                            Variants
                        </h4>
                        {#each visibleSelectedVariants as v (v.id)}
                            <div
                                class="p-3 pl-4 border-l-2 border-[var(--accent)] mb-2 bg-[rgba(90,159,212,0.04)] rounded-r-md"
                            >
                                <span class="text-xs font-semibold text-[var(--accent)] uppercase">{v.kind}</span>
                                <p class="text-sm text-[var(--text-primary)] mt-1 whitespace-pre-wrap">{v.text}</p>
                            </div>
                        {/each}
                    </div>
                {/if}

                <!-- Actions -->
                <div
                    class="flex items-center gap-[var(--space-2)] mt-[var(--space-5)] pt-[var(--space-4)] border-t border-[var(--shell-border)]"
                >
                    <span class="text-[var(--text-xs)] text-[var(--text-tertiary)] mr-auto">
                        {formatDate(selectedTranscript.timestamp)} · {formatTime(selectedTranscript.timestamp)}
                    </span>
                    <button
                        class="flex items-center gap-2 p-2 px-3 border border-[var(--shell-border)] rounded-md bg-[var(--surface-primary)] text-[var(--text-secondary)] text-sm cursor-pointer transition-colors duration-150 hover:text-[var(--text-primary)] hover:border-[var(--accent)] hover:bg-[var(--hover-overlay)]"
                        onclick={() => handleCopy(selectedTranscript!.text)}
                    >
                        {#if copied}
                            <Check size={15} /> Copied
                        {:else}
                            <Copy size={15} /> Copy
                        {/if}
                    </button>
                    <button
                        class="flex items-center gap-2 p-2 px-3 border border-[var(--shell-border)] rounded-md bg-[var(--surface-primary)] text-[var(--text-secondary)] text-sm cursor-pointer transition-colors duration-150 hover:text-[var(--text-primary)] hover:border-[var(--accent)] hover:bg-[var(--hover-overlay)]"
                        onclick={() => handleRefine(selectedTranscript!.id)}
                    >
                        <Sparkles size={15} /> Refine
                    </button>
                    <button
                        class="flex items-center gap-2 p-2 px-3 border border-[var(--shell-border)] rounded-md bg-[var(--surface-primary)] text-[var(--text-secondary)] text-sm cursor-pointer transition-colors duration-150 hover:text-[var(--red-5)] hover:border-[var(--red-5)] hover:bg-[var(--hover-overlay)]"
                        onclick={() => handleDeleteTranscript(selectedTranscript!.id)}
                    >
                        <Trash2 size={15} /> Delete
                    </button>
                </div>
            </div>
        {:else if selection.isMulti}
            <div class="flex flex-col items-center justify-center h-full gap-4 text-[var(--text-tertiary)]">
                <div
                    class="bg-[var(--accent)] text-white w-14 h-14 rounded-xl flex items-center justify-center text-lg font-bold"
                >
                    {selection.count}
                </div>
                <h3 class="m-0 text-[var(--text-primary)] text-lg">{selection.count} Transcripts Selected</h3>
                <div class="flex items-center gap-2 mt-2">
                    <button
                        class="flex items-center gap-2 p-2 px-4 border border-[var(--shell-border)] rounded-md bg-[var(--surface-primary)] text-[var(--text-secondary)] text-sm cursor-pointer transition-colors duration-150 hover:text-[var(--text-primary)] hover:border-[var(--accent)] hover:bg-[var(--hover-overlay)]"
                        onclick={(e) => openProjectMenu(e, selection.ids[0])}
                        disabled={batchAssigning}
                    >
                        <FolderOpen size={15} />
                        {batchAssigning ? "Assigning…" : "Assign to Project"}
                    </button>
                    <button
                        class="flex items-center gap-2 p-2 px-4 border border-[var(--shell-border)] rounded-md bg-[var(--surface-primary)] text-[var(--text-secondary)] text-sm cursor-pointer transition-colors duration-150 hover:text-[var(--red-5)] hover:border-[var(--red-5)] hover:bg-[var(--hover-overlay)]"
                        onclick={() => handleDeleteTranscript()}
                    >
                        <Trash2 size={15} /> Delete All
                    </button>
                </div>
                <button
                    class="text-xs text-[var(--accent)] bg-transparent border-none cursor-pointer hover:underline"
                    onclick={() => {
                        selection.clear();
                        selectedTranscriptId = null;
                        selectedTranscript = null;
                    }}
                >
                    Clear Selection
                </button>
                <div class="mt-2 text-xs text-[var(--text-tertiary)] space-y-1 text-center">
                    <p class="m-0">Ctrl+Click to toggle · Shift+Click for range</p>
                    <p class="m-0">Ctrl+A to select all · Escape to clear</p>
                </div>
            </div>
        {:else if selectedProjectId}
            {@const proj = projects.find((p) => p.id === selectedProjectId)}
            <div class="flex flex-col items-center justify-center h-full gap-4 text-[var(--text-tertiary)]">
                <div
                    class="w-14 h-14 rounded-xl flex items-center justify-center text-white"
                    style="background: {proj ? getProjectColor(proj) : 'var(--accent)'}"
                >
                    <FolderOpen size={28} />
                </div>
                <h3 class="m-0 text-[var(--text-primary)] text-lg">{proj?.name ?? "Project"}</h3>
                <p class="text-xs text-[var(--text-tertiary)] m-0">
                    {(projectTranscriptMap.get(selectedProjectId!) ?? []).length} transcript{(
                        projectTranscriptMap.get(selectedProjectId!) ?? []
                    ).length !== 1
                        ? "s"
                        : ""}
                </p>
                <p class="text-xs text-[var(--text-tertiary)] m-0">Select a transcript to view details</p>
            </div>
        {:else}
            <div
                class="flex flex-col items-center justify-center h-full gap-[var(--space-3)] text-[var(--text-tertiary)]"
            >
                <div
                    class="w-16 h-16 rounded-2xl bg-[var(--surface-primary)] border border-[var(--shell-border)] flex items-center justify-center mb-[var(--space-1)]"
                >
                    <FolderOpen size={28} strokeWidth={1.2} />
                </div>
                <p class="text-[var(--text-sm)] m-0">Select a project to get started</p>
            </div>
        {/if}
    </section>
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
            {selection.isMulti ? `Assign ${selection.count} transcripts to project` : "Assign to Project"}
        </div>
        {#each projectOptions as option}
            <button
                class="w-full flex items-center justify-between gap-2 px-3 py-1.5 border-none bg-transparent text-left text-[var(--text-sm)] cursor-pointer transition-colors duration-150 hover:bg-[var(--hover-overlay-blue)] {getTranscriptProjectValue(
                    projectMenuTranscriptId ?? -1,
                ) === option.value
                    ? 'text-[var(--accent)]'
                    : 'text-[var(--text-primary)]'}"
                onclick={() => assignProjectFromContext(option.value)}
                role="menuitem"
            >
                <span class="truncate">{option.label}</span>
                {#if getTranscriptProjectValue(projectMenuTranscriptId ?? -1) === option.value}
                    <Check size={12} />
                {/if}
            </button>
        {/each}
    </div>
{/if}
