/** Navigation store — Svelte 5 runes-based view navigation. */

export type ViewId =
    | "transcribe"
    | "transcripts"
    | "settings"
    | "refine"
    | "user"
    | "edit";

export type PendingTranscriptMode = "view" | "edit";

export interface EditReturnTarget {
    view: ViewId;
    transcriptId: number | null;
}

interface NavigateOptions {
    force?: boolean;
}

export interface NavigationRequest {
    from: ViewId;
    to: ViewId;
    transcriptId: number | null;
    transcriptMode: PendingTranscriptMode;
}

export type NavigationBlocker = (request: NavigationRequest) => boolean | Promise<boolean>;

class NavigationStore {
    current: ViewId = $state("transcribe");
    /** Transcript ID to pre-select when navigating to a view (e.g., RefineView). */
    pendingTranscriptId: number | null = $state(null);
    pendingTranscriptMode: PendingTranscriptMode = $state("view");
    editReturnTarget: EditReturnTarget | null = $state(null);
    isNavigationLocked: boolean = $state(false);
    /** Transcript ID to append subsequent recordings to (append/continue mode). */
    appendTargetId: number | null = $state(null);
    private blockers = new Set<NavigationBlocker>();

    async navigate(
        view: ViewId,
        transcriptId?: number,
        transcriptMode: PendingTranscriptMode = "view",
        options?: NavigateOptions,
    ): Promise<boolean> {
        if (this.isNavigationLocked && !options?.force) {
            return false;
        }

        const request: NavigationRequest = {
            from: this.current,
            to: view,
            transcriptId: transcriptId ?? null,
            transcriptMode,
        };

        if (!options?.force) {
            for (const blocker of this.blockers) {
                const allowed = await blocker(request);
                if (!allowed) {
                    return false;
                }
            }
        }

        this.pendingTranscriptId = transcriptId ?? null;
        this.pendingTranscriptMode = transcriptMode;
        this.current = view;
        return true;
    }

    registerBlocker(blocker: NavigationBlocker): () => void {
        this.blockers.add(blocker);
        return () => {
            this.blockers.delete(blocker);
        };
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
        this.navigate("edit", transcriptId, "edit", { force: true });
    }

    /** Navigate to TranscribeView in append mode targeting the given transcript. */
    navigateToAppendMode(targetId: number): void {
        if (this.isNavigationLocked) return;
        this.appendTargetId = targetId;
        this.navigate("transcribe");
    }

    /** Consume and clear the pending append target ID (one-shot). */
    consumeAppendTarget(): number | null {
        const id = this.appendTargetId;
        this.appendTargetId = null;
        return id;
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

}

export const nav = new NavigationStore();
