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
        WandSparkles,
        X,
    } from "lucide-svelte";

    import type { CommandNode } from "../../actions/command";
    import type { Transcript } from "../../api";
    import { SelectionManager } from "../../selection.svelte";
    import ActionBar from "../ActionBar.svelte";
    import CommandBar from "../CommandBar.svelte";
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
        onRetitleSelection: () => void;
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
        onRetitleSelection,
        onExportAnchorChange,
    }: Props = $props();

    let selectionCommands = $derived.by(
        (): CommandNode[] => [
            {
                id: "delete-selection",
                label: selection.isMulti ? `Delete ${selection.count}` : "Delete",
                icon: Trash2,
                variant: "destructive",
                group: "danger",
                section: "start",
                priority: 10,
                run: onDelete,
            },
            {
                id: "continue-selected",
                label: "Continue",
                icon: Mic,
                variant: "secondary",
                group: "capture",
                section: "end",
                priority: 20,
                visibleWhen: () => selection.count === 1,
                title: "Continue recording — append to this transcript",
                run: onContinueRecording,
            },
            {
                id: "edit-selected",
                label: "Edit",
                icon: Pencil,
                variant: "secondary",
                group: "edit",
                section: "end",
                priority: 30,
                iconOnly: true,
                visibleWhen: () => selection.count === 1,
                title: "Edit selected transcript",
                run: onEditSelected,
            },
            {
                id: "copy-selected",
                label: copied ? "Copied" : "Copy",
                icon: copied ? Check : Copy,
                variant: "secondary",
                group: "share",
                section: "end",
                priority: 40,
                iconOnly: true,
                visibleWhen: () => selection.count === 1,
                title: copied ? "Copied" : "Copy selected transcript text",
                run: onCopySelectedText,
            },
            {
                id: "tag-selection",
                label: "Tag",
                icon: TagIcon,
                variant: "secondary",
                group: "organize",
                section: "end",
                priority: 50,
                iconOnly: true,
                title: selection.isMulti ? `Tag ${selection.count} transcripts` : "Tag selected transcript",
                run: onOpenTagAssign,
            },
            {
                id: "export-selection",
                label: exporting ? "Exporting" : selection.isMulti ? `Export ${selection.count}` : "Export",
                icon: Download,
                variant: "secondary",
                group: "share",
                section: "end",
                priority: 60,
                iconOnly: true,
                disabled: () => exporting,
                title: "Export selected transcripts",
                run: (event) => {
                    onExportAnchorChange(event?.currentTarget as HTMLElement | undefined);
                    onToggleExportPopover(event);
                },
            },
            {
                id: "refine-selection",
                label: selection.isMulti ? `Refine ${selection.count}` : "Refine",
                icon: Sparkles,
                variant: "primary",
                group: "edit",
                section: "end",
                priority: 70,
                run: onBulkRefine,
            },
            {
                id: "retranscribe-selected",
                label: "Re-transcribe",
                icon: RefreshCw,
                variant: "secondary",
                group: "edit",
                placement: "overflow",
                priority: 120,
                visibleWhen: () => selection.count === 1 && Boolean(selectedEntry?.has_audio_cached),
                run: onRetranscribeSelected,
            },
            {
                id: "retitle-selection",
                label: selection.isMulti ? `Retitle ${selection.count}` : "Retitle",
                icon: WandSparkles,
                variant: "secondary",
                group: "edit",
                placement: "overflow",
                priority: 125,
                title: selection.isMulti ? `Retitle ${selection.count} transcripts` : "Retitle selected transcript",
                run: onRetitleSelection,
            },
            {
                id: "prompt-actions",
                label: "Prompt",
                icon: Sparkles,
                group: "edit",
                placement: "overflow",
                priority: 130,
                visibleWhen: () => selection.count === 1 && selectedEntryIsPrompt,
                children: [
                    {
                        id: "set-default-prompt",
                        label: "Set Default Prompt",
                        icon: Check,
                        group: "edit",
                        visibleWhen: () => !selectedEntryIsDefaultPrompt,
                        run: onSetSelectedAsDefaultPrompt,
                    },
                    {
                        id: "clear-default-prompt",
                        label: "Clear Default Prompt",
                        icon: X,
                        group: "danger",
                        visibleWhen: () => selectedEntryIsDefaultPrompt,
                        run: onClearDefaultPrompt,
                    },
                ],
            },
        ],
    );
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
    <CommandBar commands={selectionCommands} />
{/if}
