<script lang="ts">
    /**
     * BulkActionsPanel — Multi-select bulk action interface for transcripts.
     *
     * Shown when multiple transcripts are selected. Provides assign-to-project
     * and bulk delete actions with keyboard shortcut hints.
     */

    import { FileText, FolderOpen, Trash2 } from "lucide-svelte";

    interface Props {
        count: number;
        onAssignProject: (event: MouseEvent) => void;
        onDelete: () => void;
    }

    let { count, onAssignProject, onDelete }: Props = $props();
</script>

<div class="flex-1 flex flex-col items-center justify-center gap-[var(--space-4)] p-[var(--space-5)]">
    <div
        class="w-16 h-16 rounded-2xl bg-[var(--surface-primary)] border border-[var(--accent-muted)] flex items-center justify-center"
    >
        <FileText size={28} strokeWidth={1.2} class="text-[var(--accent)]" />
    </div>
    <h3 class="m-0 text-[var(--text-primary)] text-lg font-semibold">
        {count} transcripts selected
    </h3>
    <p class="m-0 text-[var(--text-tertiary)] text-sm">
        Right-click to assign to project, or use actions below
    </p>

    <div class="flex flex-col gap-[var(--space-2)] w-full max-w-[320px]">
        <button
            class="inline-flex items-center justify-center gap-2 h-10 px-4 border-none rounded-[var(--radius-md)] text-sm font-semibold cursor-pointer whitespace-nowrap bg-[var(--surface-primary)] border border-[var(--shell-border)] text-[var(--text-primary)] hover:bg-[var(--hover-overlay)] hover:border-[var(--accent)] transition-colors"
            onclick={onAssignProject}
        >
            <FolderOpen size={15} /> Assign {count} to Project…
        </button>
        <button
            class="inline-flex items-center justify-center gap-2 h-10 px-4 border border-[var(--shell-border)] rounded-[var(--radius-md)] text-sm font-semibold cursor-pointer whitespace-nowrap bg-transparent text-[var(--text-tertiary)] hover:text-[var(--color-danger)] hover:border-[var(--color-danger)] hover:bg-[var(--color-danger-surface)] transition-colors"
            onclick={onDelete}
        >
            <Trash2 size={15} /> Delete {count} Transcripts
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
