<script lang="ts">
    import {
        Check,
        Copy,
        Download,
        Loader2,
        Mic,
        Pencil,
        RefreshCw,
        Sparkles,
        Tag as TagIcon,
        Trash2,
        X,
    } from "lucide-svelte";

    import type { Transcript } from "../../api";
    import { SelectionManager } from "../../selection.svelte";
    import ActionBar from "../ActionBar.svelte";
    import StyledButton from "../StyledButton.svelte";

    interface Props {
        bulkRefineActive: boolean;
        bulkRefineCompleted: number;
        bulkRefineFailed: number;
        bulkRefineTotal: number;
        selection: SelectionManager;
        copied: boolean;
        exporting: boolean;
        selectedEntry: Transcript | null;
        selectedEntryIsPrompt: boolean;
        selectedEntryIsDefaultPrompt: boolean;
        onCancelBulkRefine: () => void;
        onDelete: () => void;
        onContinueRecording: () => void;
        onEditSelected: () => void;
        onCopySelectedText: () => void;
        onRetranscribeSelected: () => void;
        onClearDefaultPrompt: () => void;
        onSetSelectedAsDefaultPrompt: () => void;
        onOpenTagAssign: (event?: MouseEvent) => void;
        onToggleExportPopover: (event?: MouseEvent) => void;
        onBulkRefine: () => void;
        onExportAnchorChange: (element: HTMLElement | undefined) => void;
    }

    let {
        bulkRefineActive,
        bulkRefineCompleted,
        bulkRefineFailed,
        bulkRefineTotal,
        selection,
        copied,
        exporting,
        selectedEntry,
        selectedEntryIsPrompt,
        selectedEntryIsDefaultPrompt,
        onCancelBulkRefine,
        onDelete,
        onContinueRecording,
        onEditSelected,
        onCopySelectedText,
        onRetranscribeSelected,
        onClearDefaultPrompt,
        onSetSelectedAsDefaultPrompt,
        onOpenTagAssign,
        onToggleExportPopover,
        onBulkRefine,
        onExportAnchorChange,
    }: Props = $props();

    let exportAnchor: HTMLElement | undefined = $state(undefined);

    $effect(() => {
        onExportAnchorChange(exportAnchor);
    });
</script>

{#if bulkRefineActive}
    <ActionBar gap="gap-3">
        <Loader2 size={14} class="animate-spin text-[var(--accent)] shrink-0" />
        <span class="text-sm text-[var(--text-secondary)]">
            Refining {bulkRefineCompleted} of {bulkRefineTotal}…
            {#if bulkRefineFailed > 0}
                <span class="text-[var(--text-warning)]">({bulkRefineFailed} failed)</span>
            {/if}
        </span>
        <div class="flex-1 h-1.5 rounded-full bg-[var(--shell-border)] overflow-hidden">
            <div
                class="h-full rounded-full bg-[var(--accent)] transition-all duration-300"
                style="width: {bulkRefineTotal > 0
                    ? ((bulkRefineCompleted + bulkRefineFailed) / bulkRefineTotal) * 100
                    : 0}%"
            ></div>
        </div>
        <StyledButton size="sm" variant="secondary" onclick={onCancelBulkRefine}>
            <X size={13} /> Cancel
        </StyledButton>
    </ActionBar>
{:else if selection.hasSelection}
    <ActionBar>
        <StyledButton size="sm" variant="destructive" onclick={onDelete}>
            <Trash2 size={13} />
            {selection.isMulti ? `Delete ${selection.count}` : "Delete"}
        </StyledButton>

        <div class="flex-1"></div>

        {#if selection.count === 1}
            <StyledButton
                size="sm"
                variant="secondary"
                onclick={onContinueRecording}
                title="Continue recording — append to this transcript"
            >
                <Mic size={13} /> Continue
            </StyledButton>
            <StyledButton size="sm" variant="secondary" onclick={onEditSelected}>
                <Pencil size={13} /> Edit
            </StyledButton>
            <StyledButton size="sm" variant="secondary" onclick={onCopySelectedText}>
                {#if copied}
                    <Check size={13} /> Copied
                {:else}
                    <Copy size={13} /> Copy
                {/if}
            </StyledButton>
            {#if selectedEntry?.has_audio_cached}
                <StyledButton size="sm" variant="secondary" onclick={onRetranscribeSelected}>
                    <RefreshCw size={13} /> Re-transcribe
                </StyledButton>
            {/if}
            {#if selectedEntryIsPrompt}
                {#if selectedEntryIsDefaultPrompt}
                    <StyledButton size="sm" variant="ghost" onclick={onClearDefaultPrompt}>
                        <X size={13} /> Clear Default Prompt
                    </StyledButton>
                {:else}
                    <StyledButton size="sm" variant="neutral" onclick={onSetSelectedAsDefaultPrompt}>
                        <Check size={13} /> Set Default Prompt
                    </StyledButton>
                {/if}
            {/if}
        {/if}

        <StyledButton size="sm" variant="secondary" onclick={onOpenTagAssign}>
            <TagIcon size={13} /> Tag
        </StyledButton>

        <div class="relative" bind:this={exportAnchor}>
            <StyledButton
                size="sm"
                variant="secondary"
                onclick={onToggleExportPopover}
                disabled={exporting}
                title="Export selected transcripts"
            >
                <Download size={13} />
                {exporting ? "Exporting…" : selection.isMulti ? `Export ${selection.count}` : "Export"}
            </StyledButton>
        </div>

        <StyledButton size="sm" variant="primary" onclick={onBulkRefine}>
            <Sparkles size={13} />
            {selection.isMulti ? `Refine ${selection.count}` : "Refine"}
        </StyledButton>
    </ActionBar>
{/if}
