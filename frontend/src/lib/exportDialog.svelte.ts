/**
 * Global state for the export dialog.
 *
 * `show()` opens the modal; `close()` dismisses it. Transcript count is
 * cached so the dialog can display "N transcripts will be included" without
 * fetching twice.
 */

let visible = $state(false);
let transcriptCount = $state(0);

function show(count: number): void {
    transcriptCount = count;
    visible = true;
}

function close(): void {
    visible = false;
}

export const exportDialog = {
    get isOpen(): boolean {
        return visible;
    },
    get transcriptCount(): number {
        return transcriptCount;
    },
    show,
    close,
};
