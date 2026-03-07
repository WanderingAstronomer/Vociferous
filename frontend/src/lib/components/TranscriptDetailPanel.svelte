<script lang="ts">
    /**
     * TranscriptDetailPanel — Single-transcript detail view.
     *
     * Handles: title display/editing, stats, text display, variants, action bar.
     * Owns: editingTitle, editTitleValue, retitling, copied states.
     * Delegates: delete, refine, edit navigation, variant deletion, project menu via callbacks.
     */

    import { renameTranscript, retitleTranscript, deleteVariant } from "../api";
    import type { Transcript } from "../api";
    import { formatDayHeader, formatTime, formatDuration, formatWpm, wordCount } from "../formatters";
    import { Copy, Check, Trash2, Sparkles, RefreshCw, Calendar, Loader2, X, Pencil } from "lucide-svelte";
    import WorkspacePanel from "./WorkspacePanel.svelte";
    import MarkdownBody from "./MarkdownBody.svelte";

    interface Props {
        entry: Transcript;
        refining: number | null;
        onEdit: () => void;
        onRefine: () => void;
        onDelete: () => void;
        onTitleRenamed: (id: number, newTitle: string) => void;
        onVariantDeleted: () => void;
    }

    let { entry, refining, onEdit, onRefine, onDelete, onTitleRenamed, onVariantDeleted }: Props = $props();

    /* ===== Internal state ===== */

    let editingTitle = $state(false);
    let editTitleValue = $state("");
    let retitling = $state(false);
    let copied = $state(false);

    /* Reset transient state only when navigating to a DIFFERENT transcript (ID changes).
     * Refreshing the same entry via WebSocket (new object, same ID) must NOT cancel
     * any in-progress title edit. */
    let _lastEntryId: number | null = null;
    $effect(() => {
        const id = entry.id;
        if (_lastEntryId === null) {
            _lastEntryId = id;
            return;
        }
        if (id !== _lastEntryId) {
            _lastEntryId = id;
            editingTitle = false;
            copied = false;
        }
    });

    /* ===== Derived ===== */

    let displayText = $derived(entry.text || entry.normalized_text || entry.raw_text || "");
    let displayWordCount = $derived(wordCount(displayText));
    let title = $derived(entry.display_name?.trim() || `Transcript #${entry.id}`);
    let visibleVariants = $derived((entry.variants ?? []).filter((v) => v.kind.trim().toLowerCase() !== "raw"));

    /* ===== Title editing ===== */

    function startEditTitle() {
        editTitleValue = title;
        editingTitle = true;
    }

    let commitTitleInFlight = false;
    async function commitTitle() {
        if (commitTitleInFlight) return;
        if (!editTitleValue.trim()) {
            editingTitle = false;
            return;
        }
        const newTitle = editTitleValue.trim();
        const entryId = entry.id;
        commitTitleInFlight = true;
        editingTitle = false;
        try {
            await renameTranscript(entryId, newTitle);
            onTitleRenamed(entryId, newTitle);
        } catch (e: any) {
            console.error("Failed to rename transcript:", e);
        } finally {
            commitTitleInFlight = false;
        }
    }

    function cancelEditTitle() {
        editingTitle = false;
    }

    async function handleRetitle() {
        if (retitling) return;
        retitling = true;
        try {
            await retitleTranscript(entry.id);
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

    /* ===== Actions ===== */

    function copyText() {
        if (!displayText) return;
        navigator.clipboard.writeText(displayText);
        copied = true;
        setTimeout(() => (copied = false), 1500);
    }

    async function handleDeleteVariant(variantId: number) {
        try {
            await deleteVariant(entry.id, variantId);
            onVariantDeleted();
        } catch (e: any) {
            console.error("Failed to delete variant:", e);
        }
    }
</script>

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
        <h2 class="flex-1 text-xl font-semibold text-[var(--text-primary)] m-0 leading-tight text-center truncate">
            {#if editingTitle}
                <input
                    type="text"
                    class="w-full text-xl font-semibold text-[var(--text-primary)] bg-[var(--surface-primary)] border border-[var(--accent)] rounded px-2 py-1 text-center outline-none"
                    bind:value={editTitleValue}
                    onkeydown={handleTitleKeydown}
                    onblur={commitTitle}
                />
            {:else}
                {title}
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

    <!-- Stats row -->
    <div
        class="flex flex-wrap justify-center items-center gap-1 shrink-0 text-sm text-[var(--text-secondary)] font-mono"
    >
        <span>{formatDuration(entry.duration_ms)}</span>
        <span class="text-[var(--text-tertiary)]">|</span>
        <span>{formatDuration(entry.speech_duration_ms)}</span>
        <span class="text-[var(--text-tertiary)]">|</span>
        <span>{displayWordCount} words</span>
        <span class="text-[var(--text-tertiary)]">|</span>
        <span>{formatWpm(displayWordCount, entry.speech_duration_ms || entry.duration_ms)}</span>
    </div>

    <!-- Transcript text -->
    <div class="overflow-hidden flex flex-col relative group flex-1 min-h-[80px]">
        <WorkspacePanel>
            <div class="overflow-y-auto h-full">
                <MarkdownBody text={displayText} class="text-base text-[var(--text-primary)]" />
            </div>
        </WorkspacePanel>
    </div>

    <!-- Variants -->
    {#if visibleVariants.length > 0}
        <div class="flex-1 min-h-[60px] overflow-y-auto">
            <h3 class="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wide mb-2 m-0 mt-2">
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
                            onclick={() => handleDeleteVariant(variant.id)}
                        >
                            <X size={12} />
                        </button>
                    </div>
                    <MarkdownBody text={variant.text} class="text-sm text-[var(--text-secondary)]" />
                </div>
            {/each}
        </div>
    {/if}

    <!-- Date footer -->
    <div
        class="flex items-center gap-1.5 text-xs text-[var(--text-tertiary)] shrink-0 pt-2 border-t border-[var(--shell-border)]"
    >
        <Calendar size={12} />
        <span>
            {formatDayHeader(new Date(entry.created_at))} · {formatTime(entry.created_at)}
            {#if entry.project_name}
                · Project: {entry.project_name}{/if}
        </span>
    </div>

    <!-- Action bar -->
    <div class="flex items-center gap-2 shrink-0 pt-2">
        <button
            class="inline-flex items-center gap-1.5 h-9 px-3 border-none rounded text-sm font-semibold cursor-pointer whitespace-nowrap bg-[var(--surface-tertiary)] text-[var(--text-primary)] hover:bg-[var(--gray-6)] transition-colors"
            onclick={onEdit}
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
            onclick={onRefine}
            title="Refine"
            disabled={refining === entry.id}
        >
            {#if refining === entry.id}<Loader2 size={14} class="animate-spin" /> Refining…{:else}<Sparkles size={14} /> Refine{/if}
        </button>
        <span class="text-xs text-[var(--text-tertiary)]">Right-click transcript to assign project</span>
        <div class="flex-1"></div>
        <button
            class="inline-flex items-center gap-1.5 h-9 px-3 border-none rounded text-sm font-semibold cursor-pointer whitespace-nowrap bg-transparent text-[var(--text-tertiary)] hover:text-[var(--color-danger)] hover:bg-[var(--color-danger-surface)] transition-colors"
            onclick={onDelete}
            title="Delete"><Trash2 size={14} /> Delete</button
        >
    </div>
</div>
