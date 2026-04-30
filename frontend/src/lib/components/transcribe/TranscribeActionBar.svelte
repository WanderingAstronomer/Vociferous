<script lang="ts">
    import {
        Check,
        Copy,
        Mic,
        Pencil,
        PlusCircle,
        RefreshCw,
        Save,
        Sparkles,
        Trash2,
        Undo2,
    } from "lucide-svelte";

    import ActionBar from "../ActionBar.svelte";
    import StyledButton from "../StyledButton.svelte";

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
</script>

{#if viewState !== "idle" && viewState !== "transcribing" && viewState !== "recording"}
    {#if viewState === "editing"}
        <div class="flex flex-wrap items-center gap-[var(--space-1)] py-[var(--space-1)] shrink-0">
            <StyledButton variant="ghost" size="sm" onclick={onDiscardEdits}>
                <Undo2 size={14} /> Discard
            </StyledButton>
            <div class="flex-1"></div>
            <StyledButton variant="primary" size="sm" onclick={onCommitEdits}>
                <Save size={14} /> Save
            </StyledButton>
        </div>
    {:else}
        <ActionBar>
            <StyledButton variant="destructive" size="sm" onclick={onDeleteTranscript}>
                <Trash2 size={14} /> Delete
            </StyledButton>
            <StyledButton variant="secondary" size="sm" onclick={onEnterEditMode}>
                <Pencil size={14} /> Edit
            </StyledButton>
            <StyledButton variant="secondary" size="sm" onclick={onCopyToClipboard}>
                {#if copied}
                    <Check size={14} /> Copied
                {:else}
                    <Copy size={14} /> Copy
                {/if}
            </StyledButton>

            {#if hasAudioCached}
                <StyledButton variant="secondary" size="sm" onclick={onRetranscribe}>
                    <RefreshCw size={14} /> Re-transcribe
                </StyledButton>
            {/if}

            <div class="flex-1"></div>

            {#if viewState === "ready" && hasPreviousTranscript}
                <StyledButton variant="secondary" size="sm" onclick={onAppendToPrevious}>
                    <PlusCircle size={14} /> Append to Previous
                </StyledButton>
            {/if}
            {#if viewState === "ready" || viewState === "viewing"}
                <StyledButton variant="secondary" size="sm" onclick={onQueueContinueMode}>
                    <Mic size={14} /> Continue
                </StyledButton>
            {/if}
            {#if refinementEnabled}
                <StyledButton variant="primary" size="sm" onclick={onGoToRefine} disabled={transcriptId == null}>
                    <Sparkles size={14} /> Refine
                </StyledButton>
            {/if}
            <StyledButton variant="secondary" size="sm" onclick={onStartNewRecording}>
                <Mic size={14} /> New Recording
            </StyledButton>
        </ActionBar>
    {/if}
{/if}
