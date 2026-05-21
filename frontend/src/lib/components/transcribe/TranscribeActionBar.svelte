<script lang="ts">
    import { Check, Copy, Mic, Pencil, PlusCircle, RefreshCw, Save, Sparkles, Trash2, Undo2 } from "lucide-svelte";

    import type { CommandNode } from "../../actions/command";
    import CommandBar from "../CommandBar.svelte";

    type WorkspaceState = "idle" | "recording" | "transcribing" | "ready" | "viewing" | "editing";

    interface Props {
        viewState: WorkspaceState;
        copied: boolean;
        hasAudioCached: boolean;
        hasPreviousTranscript: boolean;
        refinementEnabled: boolean;
        transcriptId: number | null;
        onDiscardEdits: () => void;
        onCommitEdits: () => void;
        onDeleteTranscript: () => void;
        onEnterEditMode: () => void;
        onCopyToClipboard: () => void;
        onRetranscribe: () => void;
        onAppendToPrevious: () => void;
        onQueueContinueMode: () => void;
        onGoToRefine: () => void;
        onStartNewRecording: () => void;
    }

    let {
        viewState,
        copied,
        hasAudioCached,
        hasPreviousTranscript,
        refinementEnabled,
        transcriptId,
        onDiscardEdits,
        onCommitEdits,
        onDeleteTranscript,
        onEnterEditMode,
        onCopyToClipboard,
        onRetranscribe,
        onAppendToPrevious,
        onQueueContinueMode,
        onGoToRefine,
        onStartNewRecording,
    }: Props = $props();

    let editCommands = $derived.by(
        (): CommandNode[] => [
            {
                id: "discard-edits",
                label: "Discard",
                icon: Undo2,
                variant: "ghost",
                group: "danger",
                section: "start",
                priority: 10,
                run: onDiscardEdits,
            },
            {
                id: "save-edits",
                label: "Save",
                icon: Save,
                variant: "primary",
                group: "edit",
                section: "end",
                priority: 20,
                run: onCommitEdits,
            },
        ],
    );

    let transcriptCommands = $derived.by(
        (): CommandNode[] => [
            {
                id: "delete-transcript",
                label: "Delete",
                icon: Trash2,
                variant: "destructive",
                group: "danger",
                section: "start",
                priority: 10,
                run: onDeleteTranscript,
            },
            {
                id: "copy-transcript",
                label: copied ? "Copied" : "Copy",
                icon: copied ? Check : Copy,
                variant: "secondary",
                group: "share",
                section: "end",
                priority: 20,
                iconOnly: true,
                title: copied ? "Copied" : "Copy transcript text",
                run: onCopyToClipboard,
            },
            {
                id: "continue-recording",
                label: "Continue",
                icon: Mic,
                variant: "secondary",
                group: "capture",
                section: "end",
                priority: 30,
                visibleWhen: () => viewState === "ready" || viewState === "viewing",
                title: "Continue recording from this transcript",
                run: onQueueContinueMode,
            },
            {
                id: "refine-transcript",
                label: "Refine",
                icon: Sparkles,
                variant: "primary",
                group: "edit",
                section: "end",
                priority: 40,
                visibleWhen: () => refinementEnabled,
                disabled: () => transcriptId == null,
                run: onGoToRefine,
            },
            {
                id: "new-recording",
                label: "New Recording",
                icon: Mic,
                variant: "secondary",
                group: "capture",
                section: "end",
                priority: 50,
                run: onStartNewRecording,
            },
            {
                id: "edit-transcript",
                label: "Edit",
                icon: Pencil,
                variant: "secondary",
                group: "edit",
                placement: "overflow",
                priority: 110,
                run: onEnterEditMode,
            },
            {
                id: "retranscribe-transcript",
                label: "Re-transcribe",
                icon: RefreshCw,
                variant: "secondary",
                group: "edit",
                placement: "overflow",
                priority: 120,
                visibleWhen: () => hasAudioCached,
                run: onRetranscribe,
            },
            {
                id: "append-to-previous",
                label: "Append to Previous",
                icon: PlusCircle,
                variant: "secondary",
                group: "capture",
                placement: "overflow",
                priority: 130,
                visibleWhen: () => viewState === "ready" && hasPreviousTranscript,
                run: onAppendToPrevious,
            },
        ],
    );
</script>

{#if viewState !== "idle" && viewState !== "transcribing" && viewState !== "recording"}
    {#if viewState === "editing"}
        <CommandBar commands={editCommands} />
    {:else}
        <CommandBar commands={transcriptCommands} />
    {/if}
{/if}
