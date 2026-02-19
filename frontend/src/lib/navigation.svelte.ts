/**
 * Navigation store — Svelte 5 runes-based view navigation.
 *
 * Allows any view to trigger navigation (e.g., Refine button in Transcriptions
 * navigates to the RefineView with a pre-selected transcript).
 */

export type ViewId =
    | "transcribe"
    | "history"
    | "search"
    | "settings"
    | "refine"
    | "user";

export type PendingTranscriptMode = "view" | "edit";

export interface EditReturnTarget {
    view: ViewId;
    transcriptId: number | null;
}

interface NavigateOptions {
    force?: boolean;
}

class NavigationStore {
    current: ViewId = $state("transcribe");
    /** Transcript ID to pre-select when navigating to a view (e.g., RefineView). */
    pendingTranscriptId: number | null = $state(null);
    pendingTranscriptMode: PendingTranscriptMode = $state("view");
    editReturnTarget: EditReturnTarget | null = $state(null);
    isNavigationLocked: boolean = $state(false);

    navigate(
        view: ViewId,
        transcriptId?: number,
        transcriptMode: PendingTranscriptMode = "view",
        options?: NavigateOptions,
    ): void {
        if (this.isNavigationLocked && !options?.force) {
            return;
        }
        this.pendingTranscriptId = transcriptId ?? null;
        this.pendingTranscriptMode = transcriptMode;
        this.current = view;
    }

    beginEditSession(returnTarget?: EditReturnTarget): void {
        if (returnTarget) {
            this.editReturnTarget = returnTarget;
        }
        this.isNavigationLocked = true;
    }

    completeEditSession(): void {
        const target = this.editReturnTarget;
        this.editReturnTarget = null;
        this.isNavigationLocked = false;

        if (target) {
            this.navigate(target.view, target.transcriptId ?? undefined, "view", { force: true });
        }
    }

    navigateToEdit(transcriptId: number, returnTarget?: EditReturnTarget): void {
        const resolvedReturnTarget =
            returnTarget ??
            this.editReturnTarget ?? {
                view: this.current,
                transcriptId,
            };
        this.beginEditSession(resolvedReturnTarget);
        this.navigate("transcribe", transcriptId, "edit", { force: true });
    }

    /** Consume and clear the pending transcript ID (one-shot). */
    consumePendingTranscript(): number | null {
        const id = this.pendingTranscriptId;
        this.pendingTranscriptId = null;
        this.pendingTranscriptMode = "view";
        return id;
    }

    /** Consume transcript navigation request including desired mode. */
    consumePendingTranscriptRequest(): { id: number; mode: PendingTranscriptMode } | null {
        if (this.pendingTranscriptId == null) {
            this.pendingTranscriptMode = "view";
            return null;
        }
        const request = {
            id: this.pendingTranscriptId,
            mode: this.pendingTranscriptMode,
        };
        this.pendingTranscriptId = null;
        this.pendingTranscriptMode = "view";
        return request;
    }

    consumeEditReturnTarget(): EditReturnTarget | null {
        const target = this.editReturnTarget;
        this.editReturnTarget = null;
        return target;
    }
}

export const nav = new NavigationStore();
