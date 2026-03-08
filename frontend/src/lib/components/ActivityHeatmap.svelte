<script lang="ts">
    /**
     * ActivityHeatmap — Month-sectioned activity grid.
     *
     * 7 rows (Mon–Sun) × variable columns per month. Each month section
     * shows calendar-aligned day cells. Cells outside month boundaries
     * are blacked out. Vertical gaps separate months.
     *
     * Data range: first transcript month → today, padded with future months
     * to fill the container. No partial months rendered. Cell size is
     * maximized for readability within the available width.
     */

    interface Props {
        entries: Array<{
            text: string;
            normalized_text?: string;
            timestamp?: string;
            created_at?: string;
        }>;
        title?: string;
    }

    let { entries, title = "Activity Heatmap" }: Props = $props();

    /* ── Layout constants ── */
    const TARGET_CELL = 18;
    const CELL_MIN = 12;
    const CELL_MAX = 28;
    const CELL_GAP = 3;
    const MONTH_GAP = 10;
    const DIVIDER_W = 1;
    const LABEL_W = 36;
    const MONTH_LABEL_H = 22;
    const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

    /* ── Colors ── */
    const EMPTY_COLOR = "var(--surface-tertiary)";
    const BLACKOUT_COLOR = "var(--gray-9)";
    const LEVEL_COLORS = [EMPTY_COLOR, "var(--blue-8)", "var(--blue-6)", "var(--blue-4)", "var(--blue-3)"];

    /* ── Resize tracking ── */
    let containerEl: HTMLDivElement | undefined = $state();
    let containerWidth = $state(0);

    $effect(() => {
        if (!containerEl) return;
        const ro = new ResizeObserver((es) => {
            containerWidth = es[0].contentRect.width;
        });
        ro.observe(containerEl);
        return () => ro.disconnect();
    });

    /* ── Aggregate words per day ── */
    let dailyWords = $derived.by(() => {
        const map = new Map<string, number>();
        for (const e of entries) {
            const raw = e.created_at ?? e.timestamp;
            if (!raw) continue;
            const key = new Date(raw).toLocaleDateString("sv");
            const w = (e.text || (e as any).normalized_text || "").split(/\s+/).filter(Boolean).length;
            map.set(key, (map.get(key) ?? 0) + w);
        }
        return map;
    });

    /* ── Summary stats ── */
    let totalWords = $derived(Array.from(dailyWords.values()).reduce((s, w) => s + w, 0));
    let activeDays = $derived(Array.from(dailyWords.values()).filter((w) => w > 0).length);

    /* ── Month block model ── */
    interface DayCell {
        dateStr: string;
        inMonth: boolean;
        future: boolean;
        words: number;
        level: number;
    }
    interface MonthBlock {
        year: number;
        month: number;
        label: string;
        columns: DayCell[][];
        numCols: number;
    }

    function daysInMonth(y: number, m: number): number {
        return new Date(y, m + 1, 0).getDate();
    }

    function buildMonthBlock(
        year: number,
        month: number,
        today: Date,
        dw: Map<string, number>,
        q: number[],
    ): MonthBlock {
        const first = new Date(year, month, 1);
        const dim = daysInMonth(year, month);
        const firstDow = (first.getDay() + 6) % 7; // Mon=0
        const numCols = Math.ceil((firstDow + dim) / 7);
        const label = first.toLocaleDateString(undefined, { month: "short" });
        const columns: DayCell[][] = [];

        for (let c = 0; c < numCols; c++) {
            const col: DayCell[] = [];
            for (let r = 0; r < 7; r++) {
                const dayIdx = c * 7 + r - firstDow;
                const dom = dayIdx + 1;
                const inMonth = dom >= 1 && dom <= dim;
                if (!inMonth) {
                    col.push({ dateStr: "", inMonth: false, future: false, words: 0, level: 0 });
                } else {
                    const d = new Date(year, month, dom);
                    const ds = d.toLocaleDateString("sv");
                    const isFuture = d > today;
                    const words = isFuture ? 0 : (dw.get(ds) ?? 0);
                    let level = 0;
                    if (!isFuture && words > 0) {
                        if (words <= q[0]) level = 1;
                        else if (words <= q[1]) level = 2;
                        else if (words <= q[2]) level = 3;
                        else level = 4;
                    }
                    col.push({ dateStr: ds, inMonth: true, future: isFuture, words, level });
                }
            }
            columns.push(col);
        }
        return { year, month, label, columns, numCols };
    }

    function computeThresholds(dw: Map<string, number>): number[] {
        const vals = Array.from(dw.values())
            .filter((v) => v > 0)
            .sort((a, b) => a - b);
        if (vals.length === 0) return [1, 2, 3];
        const at = (p: number) => vals[Math.floor(p * (vals.length - 1))];
        return [at(0.25), at(0.5), at(0.75)];
    }

    /* Width of a month section at a given cell size */
    function sectionWidth(numCols: number, cs: number): number {
        return numCols * (cs + CELL_GAP) - CELL_GAP;
    }

    /* ── Grid layout computation ── */
    interface GridLayout {
        blocks: MonthBlock[];
        cellSize: number;
        gridWidth: number;
    }

    let layout = $derived.by((): GridLayout | null => {
        if (containerWidth < 150 || entries.length === 0) return null;

        const today = new Date();
        today.setHours(23, 59, 59, 999);
        const q = computeThresholds(dailyWords);

        const year = today.getFullYear();
        const curM = today.getMonth();

        // Mandatory months: Jan → current month of this year
        const mandatoryKeys: [number, number][] = [];
        for (let m = 0; m <= curM; m++) mandatoryKeys.push([year, m]);

        const availableW = containerWidth - LABEL_W;

        function colCount(y: number, m: number): number {
            return Math.ceil((((new Date(y, m, 1).getDay() + 6) % 7) + daysInMonth(y, m)) / 7);
        }

        function totalW(colCounts: number[], cs: number): number {
            let w = 0;
            for (let i = 0; i < colCounts.length; i++) {
                w += sectionWidth(colCounts[i], cs);
                if (i < colCounts.length - 1) w += MONTH_GAP + DIVIDER_W;
            }
            return w;
        }

        const mandatoryCols = mandatoryKeys.map(([y, m]) => colCount(y, m));

        // Find the largest cell size where all mandatory months fit;
        // if even CELL_MIN is too wide, trim oldest mandatory months from left.
        let cellSize = TARGET_CELL;
        let trimmedKeys = [...mandatoryKeys];
        let trimmedCols = [...mandatoryCols];

        if (totalW(trimmedCols, cellSize) > availableW) {
            // Try shrinking cell size first
            for (let cs = cellSize - 1; cs >= CELL_MIN; cs--) {
                if (totalW(trimmedCols, cs) <= availableW) {
                    cellSize = cs;
                    break;
                }
                cellSize = cs;
            }
            // If still doesn't fit at CELL_MIN, trim from the left
            while (trimmedCols.length > 1 && totalW(trimmedCols, cellSize) > availableW) {
                trimmedKeys.shift();
                trimmedCols.shift();
            }
        }

        // Add remaining year months (current+1 → Dec) if they fit
        const allKeys: [number, number][] = [...trimmedKeys];
        const allColCounts: number[] = [...trimmedCols];
        for (let m = curM + 1; m <= 11; m++) {
            const nc = colCount(year, m);
            if (totalW([...allColCounts, nc], cellSize) > availableW) break;
            allColCounts.push(nc);
            allKeys.push([year, m]);
        }

        // Try to grow cell size now that we have a fixed set of months
        while (cellSize < CELL_MAX) {
            if (totalW(allColCounts, cellSize + 1) > availableW) break;
            cellSize++;
        }

        const gridWidth = LABEL_W + totalW(allColCounts, cellSize);
        const blocks = allKeys.map(([y, m]) => buildMonthBlock(y, m, today, dailyWords, q));

        return { blocks, cellSize, gridWidth };
    });

    function cellBg(cell: DayCell): string {
        if (!cell.inMonth) return BLACKOUT_COLOR;
        if (cell.future) return EMPTY_COLOR;
        return LEVEL_COLORS[cell.level];
    }

    function cellTooltip(cell: DayCell): string {
        if (!cell.inMonth || cell.future) return "";
        const d = new Date(cell.dateStr + "T12:00:00");
        const label = d.toLocaleDateString(undefined, {
            weekday: "short",
            month: "short",
            day: "numeric",
        });
        return cell.words > 0 ? `${label}: ${cell.words.toLocaleString()} words` : `${label}: no activity`;
    }
</script>

<div
    bind:this={containerEl}
    class="w-full select-none"
    role="img"
    aria-label="Activity heatmap showing words transcribed per day"
>
    {#if layout}
        {@const cs = layout.cellSize}
        <div class="mx-auto" style="width: {layout.gridWidth}px;">
            <!-- Title -->
            {#if title}
                <div
                    class="text-[13px] font-medium text-[var(--text-tertiary)] uppercase tracking-widest mb-[var(--space-2)] text-center"
                >
                    {title}
                </div>
            {/if}

            <!-- Month labels row -->
            <div class="flex items-end" style="padding-left: {LABEL_W}px; height: {MONTH_LABEL_H}px;">
                {#each layout.blocks as block, bi}
                    {#if bi > 0}
                        <div style="width: {MONTH_GAP + DIVIDER_W}px; height: 1px;"></div>
                    {/if}
                    <div
                        class="text-[12px] text-[var(--text-secondary)] leading-none text-center shrink-0"
                        style="width: {sectionWidth(block.numCols, cs)}px;"
                    >
                        {block.label}
                    </div>
                {/each}
            </div>

            <!-- Grid body -->
            <div class="flex">
                <!-- Day-of-week labels -->
                <div class="flex flex-col shrink-0" style="width: {LABEL_W}px; gap: {CELL_GAP}px;">
                    {#each DAY_NAMES as name}
                        <div class="flex items-center justify-end pr-[6px]" style="height: {cs}px;">
                            <span class="text-[12px] text-[var(--text-secondary)] leading-none">{name}</span>
                        </div>
                    {/each}
                </div>

                <!-- Month sections with dividers -->
                <div class="flex items-stretch">
                    {#each layout.blocks as block, bi}
                        {#if bi > 0}
                            <div
                                class="shrink-0 flex items-center justify-center"
                                style="width: {MONTH_GAP + DIVIDER_W}px;"
                            >
                                <div class="h-full w-px bg-[var(--shell-border)] opacity-30"></div>
                            </div>
                        {/if}
                        <div class="flex shrink-0" style="gap: {CELL_GAP}px;">
                            {#each block.columns as col}
                                <div class="flex flex-col" style="gap: {CELL_GAP}px;">
                                    {#each col as cell}
                                        <div
                                            class="rounded-[2px]"
                                            style="width: {cs}px; height: {cs}px; background: {cellBg(cell)};"
                                            title={cellTooltip(cell)}
                                        ></div>
                                    {/each}
                                </div>
                            {/each}
                        </div>
                    {/each}
                </div>
            </div>

            <!-- Legend -->
            <div class="flex items-center justify-between mt-[var(--space-2)] w-full">
                <span class="text-[12px] text-[var(--text-tertiary)] whitespace-nowrap pl-[36px]">
                    {activeDays} active day{activeDays !== 1 ? "s" : ""}
                    · {totalWords.toLocaleString()} words
                </span>
                <div class="flex items-center gap-1 shrink-0">
                    <span class="text-[12px] text-[var(--text-tertiary)]">Less</span>
                    {#each LEVEL_COLORS as color}
                        <div class="rounded-[2px] w-[10px] h-[10px]" style="background: {color};"></div>
                    {/each}
                    <span class="text-[12px] text-[var(--text-tertiary)]">More</span>
                </div>
            </div>
        </div>
    {/if}
</div>
