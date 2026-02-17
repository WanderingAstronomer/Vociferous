/**
 * Navigation store — Svelte 5 runes-based view navigation.
 *
 * Allows any view to trigger navigation (e.g., Refine button in History
 * navigates to the RefineView with a pre-selected transcript).
 */

export type ViewId =
    | "transcribe"
    | "history"
    | "search"
    | "settings"
    | "projects"
    | "refine"
    | "user";

class NavigationStore {
    current: ViewId = $state("transcribe");
    /** Transcript ID to pre-select when navigating to a view (e.g., RefineView). */
    pendingTranscriptId: number | null = $state(null);

    navigate(view: ViewId, transcriptId?: number): void {
        this.pendingTranscriptId = transcriptId ?? null;
        this.current = view;
    }

    /** Consume and clear the pending transcript ID (one-shot). */
    consumePendingTranscript(): number | null {
        const id = this.pendingTranscriptId;
        this.pendingTranscriptId = null;
        return id;
    }
}

export const nav = new NavigationStore();
