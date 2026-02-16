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
        dispatchIntent,
        getProjects,
        assignProject,
        type Transcript,
        type Project,
    } from "../lib/api";
    import { ws } from "../lib/ws";
    import { onMount } from "svelte";
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
        Save,
        Undo2,
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
    let isEditing = $state(false);
    let editText = $state("");
    let projects: Project[] = $state([]);

    /* ===== Derived ===== */

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

    let selectedText = $derived(selectedEntry ? selectedEntry.text || selectedEntry.normalized_text || selectedEntry.raw_text || "" : "");

    let selectedWordCount = $derived(selectedText ? selectedText.split(/\s+/).filter(Boolean).length : 0);

    /* ===== Collapse tracking ===== */

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

    async function selectEntry(id: number) {
        if (selectedId === id && !isEditing) return;
        isEditing = false;
        editText = "";
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

    /* ===== Actions ===== */

    async function handleDelete() {
        if (selectedId == null) return;
        try {
            await deleteTranscript(selectedId);
            entries = entries.filter((e) => e.id !== selectedId);
            selectedId = null;
            selectedEntry = null;
        } catch (e: any) {
            error = e.message;
        }
    }

    async function handleRefine() {
        if (selectedId == null) return;
        refining = selectedId;
        try {
            await refineTranscript(selectedId, 2);
        } catch (e: any) {
            error = e.message;
            refining = null;
        }
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

    function enterEditMode() {
        if (!selectedEntry || !selectedText) return;
        editText = selectedText;
        isEditing = true;
    }

    async function saveEdits() {
        if (!selectedEntry || !editText.trim()) return;
        try {
            await dispatchIntent("commit_edits", {
                transcript_id: selectedEntry.id,
                content: editText.trim(),
            });
            selectedEntry = await getTranscript(selectedEntry.id);
            isEditing = false;
            editText = "";
            loadHistory();
        } catch (e: any) {
            console.error("Failed to save edits:", e);
        }
    }

    function cancelEdits() {
        isEditing = false;
        editText = "";
    }

    async function handleAssignProject(e: Event) {
        if (!selectedEntry) return;
        const select = e.target as HTMLSelectElement;
        const value = select.value;
        const projectId = value === "" ? null : parseInt(value, 10);
        try {
            await assignProject(selectedEntry.id, projectId);
            selectedEntry = await getTranscript(selectedEntry.id);
            loadHistory();
        } catch (err: any) {
            console.error("Failed to assign project:", err);
        }
    }

    /* ===== WebSocket ===== */

    onMount(() => {
        loadHistory();
        getProjects().then((p) => (projects = p)).catch(() => {});
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
                getProjects().then((p) => (projects = p)).catch(() => {});
            }),
            ws.on("project_deleted", () => {
                getProjects().then((p) => (projects = p)).catch(() => {});
                loadHistory();
            }),
        ];
        return () => unsubs.forEach((fn) => fn());
    });
</script>

<div class="history-view">
    <!-- Master: List Panel -->
    <div class="list-panel">
        <div class="list-header">
            <button class="refresh-btn" onclick={loadHistory} title="Refresh">
                <RefreshCw size={14} />
            </button>
        </div>

        <div class="filter-bar">
            <input type="text" class="filter-input" placeholder="Filter transcripts…" bind:value={filterText} />
        </div>

        <div class="list-content">
            {#if loading}
                <div class="list-empty"><Loader2 size={20} class="spin" /><span>Loading history…</span></div>
            {:else if error}
                <div class="list-empty error">{error}</div>
            {:else if dayGroups.length === 0}
                <div class="list-empty">{filterText ? "No matches found" : "No transcripts yet"}</div>
            {:else}
                {#each dayGroups as group (group.key)}
                    <button class="day-header" onclick={() => toggleDay(group.key)}>
                        <span class="day-chevron">
                            {#if group.collapsed}<ChevronRight size={14} />{:else}<ChevronDown size={14} />{/if}
                        </span>
                        <span class="day-label">{group.label}</span>
                        <span class="day-count">{group.entries.length}</span>
                    </button>
                    {#if !group.collapsed}
                        {#each group.entries as entry (entry.id)}
                            <button
                                class="entry-item"
                                class:selected={selectedId === entry.id}
                                onclick={() => selectEntry(entry.id)}
                            >
                                <div class="entry-indicator" class:active={selectedId === entry.id}></div>
                                <div class="entry-content">
                                    <span class="entry-preview">{truncate(getDisplayText(entry))}</span>
                                    <span class="entry-time">{formatTime(entry.created_at)}</span>
                                </div>
                            </button>
                        {/each}
                    {/if}
                {/each}
            {/if}
        </div>
    </div>

    <!-- Detail: Content Panel -->
    <div class="detail-panel">
        {#if detailLoading}
            <div class="detail-empty"><Loader2 size={24} class="spin" /></div>
        {:else if selectedEntry}
            <div class="detail-content">
                <h2 class="detail-title">{getTitle(selectedEntry)}</h2>
                <div class="detail-separator"></div>

                <div class="detail-metrics">
                    <div class="detail-metric">
                        <Clock size={12} /><span>{formatDuration(selectedEntry.duration_ms)}</span>
                    </div>
                    <div class="detail-metric">
                        <Gauge size={12} /><span>{formatDuration(selectedEntry.speech_duration_ms)}</span>
                    </div>
                    <div class="detail-metric"><Hash size={12} /><span>{selectedWordCount} words</span></div>
                    <div class="detail-metric">
                        <FileText size={12} /><span
                            >{formatWpm(
                                selectedWordCount,
                                selectedEntry.speech_duration_ms || selectedEntry.duration_ms,
                            )}</span
                        >
                    </div>
                    {#if selectedEntry.project_name}
                        <div class="detail-metric accent"><span>📁 {selectedEntry.project_name}</span></div>
                    {/if}
                </div>

                <div class="text-panel-resizable">
                    <WorkspacePanel editing={isEditing}>
                        <div class="detail-text-area">
                            {#if isEditing}
                                <textarea
                                    class="detail-text-edit"
                                    bind:value={editText}
                                ></textarea>
                            {:else}
                                <p class="detail-text">{selectedText}</p>
                            {/if}
                        </div>
                    </WorkspacePanel>
                </div>

                {#if selectedEntry.variants && selectedEntry.variants.length > 0}
                    <div class="variants-section">
                        <h3 class="variants-heading">Variants</h3>
                        {#each selectedEntry.variants as variant (variant.id)}
                            <div class="variant-card">
                                <div class="variant-header">
                                    <span class="variant-kind">{variant.kind}</span>
                                    <span class="variant-date">{formatTime(variant.created_at)}</span>
                                    <button
                                        class="variant-delete"
                                        title="Delete variant"
                                        onclick={() => handleDeleteVariant(selectedEntry!.id, variant.id)}
                                    >
                                        <X size={12} />
                                    </button>
                                </div>
                                <p class="variant-text">{variant.text}</p>
                            </div>
                        {/each}
                    </div>
                {/if}

                <div class="detail-footer">
                    <Calendar size={12} />
                    <span>
                        {formatDayHeader(new Date(selectedEntry.created_at))} · {formatTime(selectedEntry.created_at)}
                        {#if selectedEntry.project_name}
                            · Project: {selectedEntry.project_name}{/if}
                    </span>
                </div>

                <div class="detail-actions">
                    {#if isEditing}
                        <button class="action-btn primary" onclick={saveEdits} title="Save edits">
                            <Save size={14} /> Save
                        </button>
                        <button class="action-btn ghost" onclick={cancelEdits} title="Discard edits">
                            <Undo2 size={14} /> Cancel
                        </button>
                    {:else}
                        <button class="action-btn secondary" onclick={enterEditMode} title="Edit">
                            <Pencil size={14} /> Edit
                        </button>
                        <button class="action-btn secondary" onclick={copyText} title="Copy">
                            {#if copied}<Check size={14} /> Copied{:else}<Copy size={14} /> Copy{/if}
                        </button>
                        <button
                            class="action-btn ghost"
                            onclick={handleRefine}
                            title="Refine"
                            disabled={refining === selectedId}
                        >
                            {#if refining === selectedId}<Loader2 size={14} class="spin" /> Refining…{:else}<Sparkles
                                    size={14}
                                /> Refine{/if}
                        </button>
                        {#if projects.length > 0}
                            <div class="project-assign">
                                <FolderOpen size={14} />
                                <select
                                    class="project-select"
                                    value={selectedEntry?.project_id?.toString() ?? ""}
                                    onchange={handleAssignProject}
                                    title="Assign to project"
                                >
                                    <option value="">No Project</option>
                                    {#each projects as project (project.id)}
                                        <option value={project.id.toString()}>{project.name}</option>
                                    {/each}
                                </select>
                            </div>
                        {/if}
                        <div class="action-spacer"></div>
                        <button class="action-btn destructive" onclick={handleDelete} title="Delete"
                            ><Trash2 size={14} /> Delete</button
                        >
                    {/if}
                </div>
            </div>
        {:else}
            <div class="detail-empty">
                <FileText size={32} strokeWidth={1} />
                <p>Select a transcript</p>
            </div>
        {/if}
    </div>
</div>

<style>
    .history-view {
        display: flex;
        height: 100%;
        overflow: hidden;
    }

    /* ===== List Panel ===== */
    .list-panel {
        width: 40%;
        min-width: 280px;
        display: flex;
        flex-direction: column;
        border-right: 1px solid var(--shell-border);
        background: var(--surface-primary);
    }
    .list-header {
        display: flex;
        align-items: center;
        justify-content: flex-end;
        padding: var(--space-2) var(--space-3);
        flex-shrink: 0;
        height: auto;
    }
    .refresh-btn {
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
        transition:
            color var(--transition-fast),
            background var(--transition-fast);
    }
    .refresh-btn:hover {
        color: var(--text-primary);
        background: var(--hover-overlay);
    }
    .filter-bar {
        padding: var(--space-1) var(--space-3);
        flex-shrink: 0;
    }
    .filter-input {
        width: 100%;
        height: 36px;
        background: var(--surface-secondary);
        border: 1px solid var(--shell-border);
        border-radius: var(--radius-sm);
        color: var(--text-primary);
        font-family: var(--font-family);
        font-size: var(--text-sm);
        padding: 0 var(--space-2);
        outline: none;
        transition: border-color var(--transition-fast);
    }
    .filter-input:focus {
        border-color: var(--accent);
    }
    .filter-input::placeholder {
        color: var(--text-tertiary);
    }
    .list-content {
        flex: 1;
        overflow-y: auto;
        padding-bottom: var(--space-2);
    }
    .list-empty {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: var(--space-1);
        height: 200px;
        color: var(--text-tertiary);
        font-size: var(--text-sm);
    }
    .list-empty.error {
        color: var(--color-danger);
    }

    /* ===== Day Header ===== */
    .day-header {
        display: flex;
        align-items: center;
        gap: var(--space-1);
        width: 100%;
        padding: var(--space-1) var(--space-3);
        border: none;
        background: transparent;
        color: var(--text-secondary);
        font-family: var(--font-family);
        font-size: var(--text-xs);
        font-weight: var(--weight-emphasis);
        text-transform: uppercase;
        letter-spacing: 0.04em;
        cursor: pointer;
        transition: color var(--transition-fast);
        text-align: left;
    }
    .day-header:hover {
        color: var(--text-primary);
    }
    .day-chevron {
        display: flex;
        align-items: center;
        color: var(--text-tertiary);
    }
    .day-label {
        flex: 1;
    }
    .day-count {
        font-size: var(--text-xs);
        color: var(--text-tertiary);
        background: var(--surface-tertiary);
        padding: 1px 6px;
        border-radius: 8px;
    }

    /* ===== Entry Item ===== */
    .entry-item {
        display: flex;
        align-items: stretch;
        width: 100%;
        padding: var(--space-1) var(--space-3);
        padding-left: var(--space-1);
        border: none;
        background: transparent;
        cursor: pointer;
        text-align: left;
        font-family: var(--font-family);
        transition: background var(--transition-fast);
    }
    .entry-item:hover {
        background: var(--hover-overlay);
    }
    .entry-item.selected {
        background: var(--hover-overlay-blue);
    }
    .entry-indicator {
        width: 3px;
        border-radius: 2px;
        flex-shrink: 0;
        margin-right: var(--space-1);
        transition: background var(--transition-fast);
    }
    .entry-indicator.active {
        background: var(--accent);
    }
    .entry-content {
        flex: 1;
        min-width: 0;
        display: flex;
        flex-direction: column;
        gap: 2px;
        padding: 2px 0;
    }
    .entry-preview {
        font-size: var(--text-sm);
        color: var(--text-primary);
        line-height: var(--leading-normal);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .entry-time {
        font-size: var(--text-xs);
        color: var(--text-tertiary);
        font-family: var(--font-mono);
    }

    /* ===== Detail Panel ===== */
    .detail-panel {
        flex: 1;
        display: flex;
        flex-direction: column;
        overflow: hidden;
        background: var(--surface-secondary);
    }
    .detail-empty {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: var(--space-2);
        color: var(--text-tertiary);
        font-size: var(--text-sm);
    }
    .detail-content {
        flex: 1;
        display: flex;
        flex-direction: column;
        padding: var(--space-4) var(--space-4) var(--space-2);
        gap: var(--space-2);
        overflow: hidden;
    }
    .detail-title {
        font-size: var(--text-md);
        font-weight: var(--weight-emphasis);
        color: var(--text-primary);
        margin: 0;
        line-height: var(--leading-tight);
        text-align: center;
    }
    .detail-separator {
        height: 1px;
        background: var(--shell-border);
        flex-shrink: 0;
    }

    .detail-metrics {
        display: flex;
        flex-wrap: wrap;
        justify-content: center;
        gap: var(--space-2);
        flex-shrink: 0;
    }
    .detail-metric {
        display: flex;
        align-items: center;
        gap: 4px;
        font-size: var(--text-sm);
        color: var(--text-secondary);
        font-family: var(--font-mono);
    }
    .detail-metric.accent {
        color: var(--accent);
        font-family: var(--font-family);
    }

    .detail-text-area {
        flex: 1;
        overflow-y: auto;
    }

    .text-panel-resizable {
        flex: 1;
        min-height: 100px;
        max-height: 70vh;
        overflow: hidden;
        resize: vertical;
        display: flex;
        flex-direction: column;
    }
    .text-panel-resizable > :global(.workspace-panel) {
        flex: 1;
        min-height: 0;
    }
    .detail-text {
        font-size: var(--text-base);
        line-height: var(--leading-relaxed);
        color: var(--text-primary);
        white-space: pre-wrap;
        word-break: break-word;
        margin: 0;
    }
    .detail-text-edit {
        width: 100%;
        height: 100%;
        min-height: 120px;
        font-size: var(--text-base);
        line-height: var(--leading-relaxed);
        color: var(--text-primary);
        background: var(--surface-primary);
        border: 1px solid var(--accent);
        border-radius: var(--radius-sm);
        padding: var(--space-2);
        font-family: var(--font-family);
        white-space: pre-wrap;
        word-break: break-word;
        resize: vertical;
        outline: none;
    }

    .variants-section {
        flex-shrink: 0;
        max-height: 200px;
        overflow-y: auto;
    }
    .variants-heading {
        font-size: var(--text-xs);
        font-weight: var(--weight-emphasis);
        color: var(--text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin: 0 0 var(--space-1);
    }
    .variant-card {
        padding: var(--space-1) var(--space-2);
        background: var(--surface-primary);
        border-radius: var(--radius-sm);
        margin-bottom: var(--space-1);
    }
    .variant-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 4px;
    }
    .variant-kind {
        font-size: var(--text-xs);
        font-weight: var(--weight-emphasis);
        color: var(--accent);
        text-transform: uppercase;
        letter-spacing: 0.03em;
    }
    .variant-date {
        font-size: var(--text-xs);
        color: var(--text-tertiary);
        font-family: var(--font-mono);
    }
    .variant-delete {
        background: none;
        border: none;
        color: var(--text-tertiary);
        cursor: pointer;
        padding: 2px;
        border-radius: var(--radius-sm);
        display: flex;
        align-items: center;
        opacity: 0;
        transition:
            opacity 0.15s,
            color 0.15s;
    }
    .variant-card:hover .variant-delete {
        opacity: 1;
    }
    .variant-delete:hover {
        color: var(--danger);
    }
    .variant-text {
        font-size: var(--text-sm);
        line-height: var(--leading-normal);
        color: var(--text-secondary);
        margin: 0;
    }

    .detail-footer {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: var(--text-xs);
        color: var(--text-tertiary);
        flex-shrink: 0;
        padding-top: var(--space-1);
        border-top: 1px solid var(--shell-border);
    }

    .detail-actions {
        display: flex;
        align-items: center;
        gap: var(--space-1);
        flex-shrink: 0;
        padding-top: var(--space-1);
    }
    .action-spacer {
        flex: 1;
    }
    .action-btn {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        height: 36px;
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

    .project-assign {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        color: var(--text-secondary);
    }
    .project-select {
        height: 32px;
        background: var(--surface-tertiary);
        border: 1px solid var(--shell-border);
        border-radius: var(--radius-sm);
        color: var(--text-primary);
        font-family: var(--font-family);
        font-size: var(--text-sm);
        padding: 0 var(--space-2);
        cursor: pointer;
    }
    .project-select:hover {
        border-color: var(--text-tertiary);
    }
</style>
