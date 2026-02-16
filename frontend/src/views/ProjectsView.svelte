<script lang="ts">
    import { onMount, onDestroy } from "svelte";
    import {
        getProjects,
        createProject,
        deleteProject,
        getTranscripts,
        deleteTranscript,
        refineTranscript,
        type Project,
        type Transcript,
    } from "../lib/api";
    import { ws } from "../lib/ws";
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
    let projectTranscripts: Transcript[] = $state([]);
    let selectedTranscriptId: number | null = $state(null);
    let selectedTranscript: Transcript | null = $state(null);

    let expandedProjects: Set<number> = $state(new Set());
    let loading = $state(true);
    let loadingTranscripts = $state(false);
    let copied = $state(false);

    /* Create project form */
    let showCreateForm = $state(false);
    let newProjectName = $state("");
    let newProjectColor = $state(PROJECT_COLORS[0].value);
    let creating = $state(false);
    let createParentId: number | null = $state(null);

    /* ── Derived: Tree structure ── */
    let rootProjects = $derived(projects.filter((p) => !p.parent_id));
    let childProjectMap = $derived(
        projects.reduce(
            (map, p) => {
                if (p.parent_id) {
                    if (!map.has(p.parent_id)) map.set(p.parent_id, []);
                    map.get(p.parent_id)!.push(p);
                }
                return map;
            },
            new Map<number, Project[]>(),
        ),
    );

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
        loadingTranscripts = true;
        try {
            projectTranscripts = await getTranscripts(200, projectId);
        } catch (e) {
            console.error("Failed to load project transcripts:", e);
            projectTranscripts = [];
        } finally {
            loadingTranscripts = false;
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
                projectTranscripts = [];
                selectedTranscriptId = null;
                selectedTranscript = null;
            }
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
        }
        expandedProjects = next;
    }

    function selectProject(id: number) {
        selectedProjectId = id;
        selectedTranscriptId = null;
        selectedTranscript = null;
        if (!expandedProjects.has(id)) {
            toggleProject(id);
        }
        loadProjectTranscripts(id);
    }

    function selectTranscript(t: Transcript) {
        selectedTranscriptId = t.id;
        selectedTranscript = t;
    }

    async function handleDeleteTranscript(id: number) {
        try {
            await deleteTranscript(id);
            if (selectedTranscriptId === id) {
                selectedTranscriptId = null;
                selectedTranscript = null;
            }
            if (selectedProjectId) {
                await loadProjectTranscripts(selectedProjectId);
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
        unsubTranscriptDeleted = ws.on("transcript_deleted", () => {
            if (selectedProjectId) loadProjectTranscripts(selectedProjectId);
        });
        unsubTranscriptionComplete = ws.on("transcription_complete", () => {
            if (selectedProjectId) loadProjectTranscripts(selectedProjectId);
        });
    });

    onDestroy(() => {
        unsubTranscriptDeleted?.();
        unsubTranscriptionComplete?.();
    });
</script>

<div class="projects-view">
    <!-- Master Pane: Project Tree -->
    <aside class="master-pane">
        <div class="master-header">
            <h2 class="master-title">Projects</h2>
            <button class="icon-btn create-btn" title="New Project" onclick={() => (showCreateForm = !showCreateForm)}>
                <Plus size={18} />
            </button>
        </div>

        <!-- Create Project Form -->
        {#if showCreateForm}
            <form
                class="create-form"
                onsubmit={(e) => {
                    e.preventDefault();
                    handleCreateProject();
                }}
            >
                {#if createParentId}
                    {@const parent = projects.find((p) => p.id === createParentId)}
                    <div class="create-parent-hint">
                        <span class="project-color-dot" style="background: {parent ? getProjectColor(parent) : 'var(--text-muted)'}"></span>
                        Sub-project of <strong>{parent?.name ?? "Unknown"}</strong>
                        <button type="button" class="icon-btn" title="Clear parent" onclick={() => (createParentId = null)}>✕</button>
                    </div>
                {/if}
                <input
                    class="create-input"
                    type="text"
                    placeholder="Project name…"
                    bind:value={newProjectName}
                />
                <div class="color-palette">
                    {#each PROJECT_COLORS as color}
                        <button
                            type="button"
                            class="color-swatch"
                            class:selected={newProjectColor === color.value}
                            style="--swatch-color: {color.css}"
                            title={color.name}
                            onclick={() => (newProjectColor = color.value)}
                        ></button>
                    {/each}
                </div>
                <div class="create-actions">
                    <button type="submit" class="create-confirm" disabled={!newProjectName.trim() || creating}>
                        {creating ? "Creating…" : "Create"}
                    </button>
                    <button type="button" class="create-cancel" onclick={cancelCreate}>
                        Cancel
                    </button>
                </div>
            </form>
        {/if}

        <!-- Project List -->
        <div class="project-list">
            {#if loading}
                <div class="loading-state">
                    <Loader2 size={20} class="spin" />
                    <span>Loading…</span>
                </div>
            {:else if projects.length === 0}
                <div class="empty-tree">
                    <FolderOpen size={32} strokeWidth={1.5} />
                    <p>No projects yet</p>
                    <p class="text-hint">Create one to organize your transcripts</p>
                </div>
            {:else}
                {#each rootProjects as project (project.id)}
                    <div class="project-node">
                        <!-- Project Header -->
                        <div
                            class="project-header"
                            class:active={selectedProjectId === project.id}
                            role="button"
                            tabindex="0"
                            onclick={() => selectProject(project.id)}
                            onkeydown={(e) => {
                                if (e.key === "Enter" || e.key === " ") selectProject(project.id);
                            }}
                        >
                            <button
                                type="button"
                                class="chevron-btn"
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
                            <span class="project-color-dot" style="background: {getProjectColor(project)}"></span>
                            <span class="project-name">{project.name}</span>
                            <button
                                class="icon-btn sub-project-btn"
                                title="Add Sub-project"
                                onclick={(e) => handleAddSubProject(project.id, e)}
                            >
                                <Plus size={13} />
                            </button>
                            <button
                                class="icon-btn delete-project-btn"
                                title="Delete Project"
                                onclick={(e) => handleDeleteProject(project.id, e)}
                            >
                                <Trash2 size={13} />
                            </button>
                        </div>

                        <!-- Nested Transcripts -->
                        {#if expandedProjects.has(project.id) && selectedProjectId === project.id}
                            <div class="transcript-children">
                                {#if loadingTranscripts}
                                    <div class="child-loading">
                                        <Loader2 size={14} class="spin" />
                                        <span>Loading…</span>
                                    </div>
                                {:else if projectTranscripts.length === 0}
                                    <div class="child-empty">No transcripts</div>
                                {:else}
                                    {#each projectTranscripts as t (t.id)}
                                        <button
                                            class="transcript-child"
                                            class:active={selectedTranscriptId === t.id}
                                            onclick={() => selectTranscript(t)}
                                        >
                                            <FileText size={13} />
                                            <span class="child-text">{truncateText(t.text)}</span>
                                        </button>
                                    {/each}
                                {/if}
                            </div>
                        {/if}

                        <!-- Child Projects -->
                        {#if childProjectMap.has(project.id)}
                            {#each childProjectMap.get(project.id) ?? [] as child (child.id)}
                                <div class="project-node child-project">
                                    <div
                                        class="project-header"
                                        class:active={selectedProjectId === child.id}
                                        role="button"
                                        tabindex="0"
                                        onclick={() => selectProject(child.id)}
                                        onkeydown={(e) => {
                                            if (e.key === "Enter" || e.key === " ") selectProject(child.id);
                                        }}
                                    >
                                        <button
                                            type="button"
                                            class="chevron-btn"
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
                                        <span class="project-color-dot" style="background: {getProjectColor(child)}"></span>
                                        <span class="project-name">{child.name}</span>
                                        <button
                                            class="icon-btn delete-project-btn"
                                            title="Delete Sub-project"
                                            onclick={(e) => handleDeleteProject(child.id, e)}
                                        >
                                            <Trash2 size={13} />
                                        </button>
                                    </div>

                                    {#if expandedProjects.has(child.id) && selectedProjectId === child.id}
                                        <div class="transcript-children">
                                            {#if loadingTranscripts}
                                                <div class="child-loading">
                                                    <Loader2 size={14} class="spin" />
                                                    <span>Loading…</span>
                                                </div>
                                            {:else if projectTranscripts.length === 0}
                                                <div class="child-empty">No transcripts</div>
                                            {:else}
                                                {#each projectTranscripts as t (t.id)}
                                                    <button
                                                        class="transcript-child"
                                                        class:active={selectedTranscriptId === t.id}
                                                        onclick={() => selectTranscript(t)}
                                                    >
                                                        <FileText size={13} />
                                                        <span class="child-text">{truncateText(t.text)}</span>
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
    <section class="detail-pane">
        {#if selectedTranscript}
            <div class="detail-content">
                <h3 class="detail-title">
                    {selectedTranscript.display_name || `Transcript #${selectedTranscript.id}`}
                </h3>

                <div class="detail-separator"></div>

                <!-- Metrics Strip -->
                <div class="metrics-strip">
                    <span class="metric"><Hash size={13} /> #{selectedTranscript.id}</span>
                    <span class="metric"><Calendar size={13} /> {formatDate(selectedTranscript.timestamp)}</span>
                    <span class="metric"><Clock size={13} /> {formatTime(selectedTranscript.timestamp)}</span>
                    {#if selectedTranscript.duration_ms}
                        <span class="metric"><Gauge size={13} /> {formatDuration(selectedTranscript.duration_ms)}</span>
                    {/if}
                </div>

                <!-- Text -->
                <WorkspacePanel>
                    <p class="detail-text">{selectedTranscript.text}</p>
                </WorkspacePanel>

                <!-- Variants -->
                {#if selectedTranscript.variants && selectedTranscript.variants.length > 0}
                    <div class="variants-section">
                        <h4 class="variants-heading">Variants</h4>
                        {#each selectedTranscript.variants as v (v.id)}
                            <div class="variant-item">
                                <span class="variant-kind">{v.kind}</span>
                                <p class="variant-text">{v.text}</p>
                            </div>
                        {/each}
                    </div>
                {/if}

                <!-- Footer -->
                <div class="detail-footer">
                    <span class="footer-timestamp">
                        {formatDate(selectedTranscript.timestamp)} at {formatTime(selectedTranscript.timestamp)}
                    </span>
                </div>

                <!-- Actions -->
                <div class="action-bar">
                    <button class="action-btn" onclick={() => handleCopy(selectedTranscript!.text)}>
                        {#if copied}
                            <Check size={15} /> Copied
                        {:else}
                            <Copy size={15} /> Copy
                        {/if}
                    </button>
                    <button class="action-btn" onclick={() => handleRefine(selectedTranscript!.id)}>
                        <Sparkles size={15} /> Refine
                    </button>
                    <button class="action-btn danger" onclick={() => handleDeleteTranscript(selectedTranscript!.id)}>
                        <Trash2 size={15} /> Delete
                    </button>
                </div>
            </div>
        {:else if selectedProjectId}
            {@const proj = projects.find((p) => p.id === selectedProjectId)}
            <div class="detail-empty-project">
                <div class="project-badge" style="background: {proj ? getProjectColor(proj) : 'var(--accent)'}">
                    <FolderOpen size={28} />
                </div>
                <h3>{proj?.name ?? "Project"}</h3>
                <p class="text-hint">
                    {projectTranscripts.length} transcript{projectTranscripts.length !== 1 ? "s" : ""}
                </p>
                <p class="text-hint">Select a transcript to view details</p>
            </div>
        {:else}
            <div class="detail-empty">
                <FolderOpen size={40} strokeWidth={1.2} />
                <p>Select a project to get started</p>
            </div>
        {/if}
    </section>
</div>

<style>
    /* ── Layout ── */
    .projects-view {
        display: flex;
        height: 100%;
        background: var(--surface-primary);
    }

    .master-pane {
        width: 40%;
        min-width: 280px;
        max-width: 420px;
        display: flex;
        flex-direction: column;
        border-right: 1px solid var(--shell-border);
        background: var(--surface-primary);
    }

    .detail-pane {
        flex: 1;
        overflow-y: auto;
        padding: var(--space-6);
        background: var(--surface-secondary);
    }

    /* ── Master Header ── */
    .master-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: var(--space-4) var(--space-4) var(--space-3);
        border-bottom: 1px solid var(--shell-border);
    }

    .master-title {
        font-size: var(--text-lg);
        font-weight: var(--weight-emphasis);
        color: var(--accent);
        margin: 0;
    }

    .icon-btn {
        background: none;
        border: none;
        color: var(--text-secondary);
        cursor: pointer;
        padding: var(--space-1);
        border-radius: var(--radius-sm);
        display: flex;
        align-items: center;
        transition:
            color var(--transition-fast),
            background var(--transition-fast);
    }

    .icon-btn:hover {
        color: var(--accent);
        background: var(--hover-overlay);
    }

    /* ── Create Form ── */
    .create-form {
        padding: var(--space-3) var(--space-4);
        border-bottom: 1px solid var(--shell-border);
        display: flex;
        flex-direction: column;
        gap: var(--space-2);
    }

    .create-input {
        width: 100%;
        padding: var(--space-2) var(--space-3);
        border: 1px solid var(--shell-border);
        border-radius: var(--radius-sm);
        background: var(--surface-secondary);
        color: var(--text-primary);
        font-size: var(--text-sm);
        outline: none;
        transition: border-color var(--transition-fast);
    }

    .create-input:focus {
        border-color: var(--accent);
    }

    .color-palette {
        display: flex;
        gap: var(--space-2);
        justify-content: center;
    }

    .color-swatch {
        width: 24px;
        height: 24px;
        border-radius: 50%;
        border: 2px solid transparent;
        background: var(--swatch-color);
        cursor: pointer;
        transition:
            border-color var(--transition-fast),
            transform var(--transition-fast);
    }

    .color-swatch:hover {
        transform: scale(1.15);
    }

    .color-swatch.selected {
        border-color: var(--text-primary);
        box-shadow: 0 0 0 2px var(--surface-primary);
    }

    .create-actions {
        display: flex;
        gap: var(--space-2);
    }

    .create-confirm {
        flex: 1;
        padding: var(--space-1) var(--space-3);
        border: none;
        border-radius: var(--radius-sm);
        background: var(--accent);
        color: var(--text-primary);
        font-size: var(--text-sm);
        font-weight: var(--weight-emphasis);
        cursor: pointer;
        transition: opacity var(--transition-fast);
    }

    .create-confirm:disabled {
        opacity: 0.5;
        cursor: not-allowed;
    }

    .create-cancel {
        padding: var(--space-1) var(--space-3);
        border: 1px solid var(--shell-border);
        border-radius: var(--radius-sm);
        background: transparent;
        color: var(--text-secondary);
        font-size: var(--text-sm);
        cursor: pointer;
        transition: color var(--transition-fast);
    }

    .create-cancel:hover {
        color: var(--text-primary);
    }

    /* ── Project List ── */
    .project-list {
        flex: 1;
        overflow-y: auto;
        padding: var(--space-2) 0;
    }

    .loading-state,
    .empty-tree {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: var(--space-2);
        padding: var(--space-7) var(--space-4);
        color: var(--text-tertiary);
    }

    .text-hint {
        font-size: var(--text-xs);
        color: var(--text-tertiary);
        margin: 0;
    }

    /* ── Project Node ── */
    .project-header {
        display: flex;
        align-items: center;
        gap: var(--space-2);
        width: 100%;
        padding: var(--space-2) var(--space-3);
        border: none;
        background: transparent;
        color: var(--text-primary);
        font-size: var(--text-base);
        cursor: pointer;
        text-align: left;
        transition: background var(--transition-fast);
    }

    .project-header:hover {
        background: var(--hover-overlay);
    }

    .project-header.active {
        background: rgba(90, 159, 212, 0.1);
    }

    .chevron-btn {
        display: flex;
        align-items: center;
        background: none;
        border: none;
        padding: 0;
        color: var(--text-tertiary);
        cursor: pointer;
        flex-shrink: 0;
    }

    .project-color-dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        flex-shrink: 0;
    }

    .project-name {
        flex: 1;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        font-weight: var(--weight-emphasis);
    }

    .delete-project-btn,
    .sub-project-btn {
        opacity: 0;
        transition: opacity var(--transition-fast);
    }

    .project-header:hover .delete-project-btn,
    .project-header:hover .sub-project-btn {
        opacity: 1;
    }

    /* ── Child Projects ── */
    .child-project {
        padding-left: var(--space-5);
    }

    .create-parent-hint {
        display: flex;
        align-items: center;
        gap: var(--space-2);
        padding: var(--space-2) var(--space-3);
        font-size: var(--text-xs);
        color: var(--text-muted);
        background: var(--surface-overlay);
        border-radius: var(--radius-sm);
        margin-bottom: var(--space-2);
    }

    .create-parent-hint strong {
        color: var(--text-primary);
    }

    /* ── Transcript Children ── */
    .transcript-children {
        padding-left: var(--space-6);
    }

    .child-loading,
    .child-empty {
        padding: var(--space-2) var(--space-3);
        font-size: var(--text-sm);
        color: var(--text-tertiary);
        display: flex;
        align-items: center;
        gap: var(--space-2);
    }

    .transcript-child {
        display: flex;
        align-items: center;
        gap: var(--space-2);
        width: 100%;
        padding: var(--space-1) var(--space-3);
        border: none;
        background: transparent;
        color: var(--text-secondary);
        font-size: var(--text-base);
        cursor: pointer;
        text-align: left;
        transition:
            background var(--transition-fast),
            color var(--transition-fast);
        border-radius: var(--radius-sm);
    }

    .transcript-child:hover {
        background: var(--hover-overlay);
        color: var(--text-primary);
    }

    .transcript-child.active {
        background: rgba(90, 159, 212, 0.12);
        color: var(--accent);
    }

    .child-text {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    /* ── Detail Pane ── */
    .detail-content {
        max-width: 720px;
    }

    .detail-title {
        font-size: var(--text-xl);
        font-weight: var(--weight-emphasis);
        color: var(--text-primary);
        margin: 0 0 var(--space-3);
    }

    .detail-separator {
        height: 1px;
        background: var(--shell-border);
        margin-bottom: var(--space-3);
    }

    .metrics-strip {
        display: flex;
        flex-wrap: wrap;
        gap: var(--space-4);
        margin-bottom: var(--space-4);
    }

    .metric {
        display: flex;
        align-items: center;
        gap: var(--space-1);
        font-size: var(--text-base);
        color: var(--text-secondary);
    }

    .detail-text {
        font-size: var(--text-base);
        line-height: 1.7;
        color: var(--text-primary);
        margin: 0;
        white-space: pre-wrap;
    }

    /* ── Variants ── */
    .variants-section {
        margin-top: var(--space-4);
    }

    .variants-heading {
        font-size: var(--text-sm);
        font-weight: var(--weight-emphasis);
        color: var(--text-secondary);
        margin: 0 0 var(--space-2);
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    .variant-item {
        padding: var(--space-2) var(--space-3);
        border-left: 2px solid var(--accent);
        margin-bottom: var(--space-2);
        background: rgba(90, 159, 212, 0.04);
        border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
    }

    .variant-kind {
        font-size: var(--text-xs);
        font-weight: var(--weight-emphasis);
        color: var(--accent);
        text-transform: uppercase;
    }

    .variant-text {
        font-size: var(--text-sm);
        color: var(--text-primary);
        margin: var(--space-1) 0 0;
        white-space: pre-wrap;
    }

    /* ── Footer ── */
    .detail-footer {
        margin-top: var(--space-4);
        padding-top: var(--space-3);
        border-top: 1px solid var(--shell-border);
    }

    .footer-timestamp {
        font-size: var(--text-xs);
        color: var(--text-tertiary);
    }

    /* ── Action Bar ── */
    .action-bar {
        display: flex;
        gap: var(--space-2);
        margin-top: var(--space-4);
    }

    .action-btn {
        display: flex;
        align-items: center;
        gap: var(--space-1);
        padding: var(--space-2) var(--space-3);
        border: 1px solid var(--shell-border);
        border-radius: var(--radius-md);
        background: var(--surface-primary);
        color: var(--text-secondary);
        font-size: var(--text-sm);
        cursor: pointer;
        transition:
            color var(--transition-fast),
            border-color var(--transition-fast),
            background var(--transition-fast);
    }

    .action-btn:hover {
        color: var(--text-primary);
        border-color: var(--accent);
        background: var(--hover-overlay);
    }

    .action-btn.danger:hover {
        color: var(--red-5);
        border-color: var(--red-5);
    }

    /* ── Empty Detail States ── */
    .detail-empty,
    .detail-empty-project {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        height: 100%;
        gap: var(--space-3);
        color: var(--text-tertiary);
    }

    .project-badge {
        width: 56px;
        height: 56px;
        border-radius: var(--radius-lg);
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
    }

    .detail-empty-project h3 {
        margin: 0;
        color: var(--text-primary);
        font-size: var(--text-lg);
    }

    /* ── Spin animation ── */
    :global(.spin) {
        animation: spin 1s linear infinite;
    }

    @keyframes spin {
        to {
            transform: rotate(360deg);
        }
    }
</style>
