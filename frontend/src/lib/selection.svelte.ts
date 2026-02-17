/**
 * SelectionManager — Reusable file-explorer-style multi-selection with Svelte 5 runes.
 *
 * Supports:
 * - Click: Select single item (replaces selection)
 * - Ctrl/Cmd+Click: Toggle individual item
 * - Shift+Click: Range select from anchor to target (replaces selection)
 * - Ctrl/Cmd+Shift+Click: Add range to existing selection
 *
 * Uses metaKey for macOS Cmd support alongside ctrlKey.
 */

export class SelectionManager {
    selectedIds: Set<number> = $state(new Set());
    /** Anchor point for shift-click range selection. */
    lastClickedId: number | null = $state(null);

    get count(): number {
        return this.selectedIds.size;
    }

    get ids(): number[] {
        return [...this.selectedIds];
    }

    isSelected(id: number): boolean {
        return this.selectedIds.has(id);
    }

    /**
     * Handle a click event with modifier key detection.
     * @param id        The ID of the clicked item.
     * @param event     The mouse event (for modifier key detection).
     * @param orderedIds All visible item IDs in display order (for range selection).
     */
    handleClick(id: number, event: MouseEvent, orderedIds: number[]): void {
        const ctrl = event.ctrlKey || event.metaKey;
        const shift = event.shiftKey;

        if (ctrl && shift) {
            this.addRange(id, orderedIds);
        } else if (shift) {
            this.selectRange(id, orderedIds);
        } else if (ctrl) {
            this.toggle(id);
        } else {
            this.selectOnly(id);
        }
        this.lastClickedId = id;
    }

    /** Select exactly one item. */
    selectOnly(id: number): void {
        this.selectedIds = new Set([id]);
    }

    /** Toggle an item in/out of the current selection. */
    toggle(id: number): void {
        const next = new Set(this.selectedIds);
        if (next.has(id)) next.delete(id);
        else next.add(id);
        this.selectedIds = next;
    }

    /** Replace selection with a range from anchor to target. */
    selectRange(targetId: number, orderedIds: number[]): void {
        const anchor = this.lastClickedId;
        if (anchor == null) {
            this.selectOnly(targetId);
            return;
        }
        const range = this.getRange(anchor, targetId, orderedIds);
        if (!range) {
            this.selectOnly(targetId);
            return;
        }
        this.selectedIds = new Set(range);
    }

    /** Add a range to the existing selection (Ctrl+Shift). */
    addRange(targetId: number, orderedIds: number[]): void {
        const anchor = this.lastClickedId;
        if (anchor == null) {
            this.toggle(targetId);
            return;
        }
        const range = this.getRange(anchor, targetId, orderedIds);
        if (!range) {
            this.toggle(targetId);
            return;
        }
        const next = new Set(this.selectedIds);
        for (const id of range) next.add(id);
        this.selectedIds = next;
    }

    /** Select all provided IDs. */
    selectAll(ids: number[]): void {
        this.selectedIds = new Set(ids);
    }

    /** Clear selection entirely. */
    clear(): void {
        this.selectedIds = new Set();
        this.lastClickedId = null;
    }

    /** Has any selection at all. */
    get hasSelection(): boolean {
        return this.selectedIds.size > 0;
    }

    /** Has more than one item selected (for showing bulk UI). */
    get isMulti(): boolean {
        return this.selectedIds.size > 1;
    }

    private getRange(anchorId: number, targetId: number, orderedIds: number[]): number[] | null {
        const start = orderedIds.indexOf(anchorId);
        const end = orderedIds.indexOf(targetId);
        if (start === -1 || end === -1) return null;
        const [lo, hi] = start <= end ? [start, end] : [end, start];
        return orderedIds.slice(lo, hi + 1);
    }
}
