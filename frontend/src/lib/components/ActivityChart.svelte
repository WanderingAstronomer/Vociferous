<script lang="ts">
    /**
     * Activity chart with selectable time periods.
     * Self-contained: receives transcript entries, computes its own bucketing.
     */

    interface DayBucket {
        date: string;
        label: string;
        count: number;
        words: number;
    }

    interface Props {
        entries: Array<{ text: string; timestamp?: string; created_at?: string }>;
    }

    type PeriodKey = "week" | "month" | "quarter" | "half" | "year";

    const PERIODS: { key: PeriodKey; label: string; days: number }[] = [
        { key: "week", label: "Week", days: 7 },
        { key: "month", label: "Month", days: 30 },
        { key: "quarter", label: "Quarter", days: 90 },
        { key: "half", label: "6 Months", days: 182 },
        { key: "year", label: "Year", days: 365 },
    ];

    let { entries }: Props = $props();
    let activePeriod: PeriodKey = $state("month");

    let periodDays = $derived(PERIODS.find((p) => p.key === activePeriod)!.days);

    let buckets: DayBucket[] = $derived.by(() => {
        const days = periodDays;
        const now = new Date();
        const map = new Map<string, { count: number; words: number }>();

        for (let i = days - 1; i >= 0; i--) {
            const d = new Date(now);
            d.setDate(d.getDate() - i);
            map.set(d.toISOString().slice(0, 10), { count: 0, words: 0 });
        }

        for (const e of entries) {
            const key = e.timestamp?.slice(0, 10) ?? e.created_at?.slice(0, 10);
            if (key && map.has(key)) {
                const b = map.get(key)!;
                b.count++;
                b.words += e.text.split(/\s+/).filter(Boolean).length;
            }
        }

        return Array.from(map.entries()).map(([date, data]) => ({
            date,
            label: new Date(date + "T12:00:00").toLocaleDateString(undefined, { month: "short", day: "numeric" }),
            ...data,
        }));
    });

    let maxWords = $derived(Math.max(1, ...buckets.map((d) => d.words)));
    let activeDays = $derived(buckets.filter((d) => d.count > 0).length);
    let periodWords = $derived(buckets.reduce((s, d) => s + d.words, 0));

    let chartTitle = $derived.by(() => {
        switch (activePeriod) {
            case "week":
                return "This Week";
            case "month":
                return "Last 30 Days";
            case "quarter":
                return "Last Quarter";
            case "half":
                return "Last 6 Months";
            case "year":
                return "Past Year";
        }
    });

    /* Bar geometry — adaptive based on period length */
    let barWidth = $derived.by(() => {
        if (periodDays <= 7) return 24;
        if (periodDays <= 30) return 8;
        if (periodDays <= 90) return 4;
        return 2;
    });

    let barGap = $derived.by(() => {
        if (periodDays <= 7) return 8;
        if (periodDays <= 30) return 4;
        if (periodDays <= 90) return 2;
        return 1;
    });

    let cellWidth = $derived(barWidth + barGap);
    let svgWidth = $derived(buckets.length * cellWidth);
    let svgHeight = 100;

    /* Label interval — how often to show date labels */
    let labelInterval = $derived.by(() => {
        if (periodDays <= 7) return 1;
        if (periodDays <= 30) return 7;
        if (periodDays <= 90) return 14;
        if (periodDays <= 182) return 30;
        return 60;
    });

    /**
     * Compute the set of bucket indices that should show a date label.
     * Regular labels fall on multiples of labelInterval. The final bar's
     * label is only added if it's far enough from the previous label to
     * avoid collision — minimum gap is half the label interval.
     */
    let labelIndices = $derived.by(() => {
        const indices: number[] = [];
        for (let i = 0; i < buckets.length; i++) {
            if (i % labelInterval === 0) indices.push(i);
        }
        const last = buckets.length - 1;
        const minGap = Math.ceil(labelInterval / 2);
        const prevLabel = indices.length > 0 ? indices[indices.length - 1] : -1;
        if (last % labelInterval !== 0 && last - prevLabel >= minGap) {
            indices.push(last);
        }
        return new Set(indices);
    });

    function formatCount(n: number): string {
        return n.toLocaleString();
    }
</script>

<section class="flex flex-col gap-[var(--space-3)]">
    <!-- Title + period summary -->
    <div class="flex flex-col items-center gap-[var(--space-1)]">
        <h3
            class="text-[var(--text-xs)] font-[var(--weight-emphasis)] text-[var(--text-tertiary)] text-center uppercase tracking-[1px] m-0"
        >
            Recent Activity — {chartTitle}
        </h3>
        <div class="flex justify-center gap-[var(--space-2)] text-[var(--text-xs)] text-[var(--text-muted)]">
            <span>{activeDays} active day{activeDays !== 1 ? "s" : ""}</span>
            <span class="opacity-40">·</span>
            <span>{formatCount(periodWords)} words</span>
        </div>
    </div>

    <!-- Chart card -->
    <div
        class="relative rounded-[var(--radius-lg)] border border-[var(--shell-border)] bg-[var(--surface-secondary)] p-[var(--space-3)]"
        role="img"
        aria-label="Daily transcription activity bar chart for {chartTitle}"
    >
        <svg
            viewBox="0 0 {svgWidth} {svgHeight + 8}"
            class="w-full"
            style="height: {periodDays <= 30 ? '126px' : '100px'}"
            preserveAspectRatio="none"
        >
            <!-- Guide lines -->
            <line x1="0" y1="25" x2={svgWidth} y2="25" class="stroke-[var(--shell-border)]" stroke-opacity="0.3" />
            <line x1="0" y1="50" x2={svgWidth} y2="50" class="stroke-[var(--shell-border)]" stroke-opacity="0.2" />
            <line x1="0" y1="75" x2={svgWidth} y2="75" class="stroke-[var(--shell-border)]" stroke-opacity="0.15" />

            {#each buckets as day, i}
                {@const barH = day.words > 0 ? Math.max(4, (day.words / maxWords) * (svgHeight - 8)) : 0}
                {@const x = i * cellWidth + barGap / 2}

                {#if day.words > 0}
                    <!-- Active day bar -->
                    <rect
                        {x}
                        y={svgHeight - barH}
                        width={barWidth}
                        height={barH}
                        rx={barWidth > 4 ? 2 : 1}
                        class="fill-[var(--accent)] opacity-85 transition-opacity duration-150 hover:opacity-100"
                    >
                        <title
                            >{day.label}: {day.count} recording{day.count !== 1 ? "s" : ""}, {formatCount(day.words)} words</title
                        >
                    </rect>
                {:else}
                    <!-- Empty day — hairline track -->
                    <rect
                        {x}
                        y={svgHeight - 1}
                        width={barWidth}
                        height="1"
                        rx="0"
                        class="fill-[var(--text-muted)] opacity-20"
                    >
                        <title>{day.label}: no activity</title>
                    </rect>
                {/if}
            {/each}
        </svg>

        <!-- Date labels -->
        <div class="relative h-[18px] mt-[var(--space-1)]">
            {#each buckets as day, i}
                {#if labelIndices.has(i)}
                    <span
                        class="absolute transform -translate-x-1/2 text-[10px] text-[var(--text-muted)] whitespace-nowrap"
                        style="left: {((i * cellWidth + cellWidth / 2) / svgWidth) * 100}%"
                    >
                        {day.label}
                    </span>
                {/if}
            {/each}
        </div>

        <!-- Period selector buttons -->
        <div
            class="flex justify-center gap-[var(--space-1)] mt-[var(--space-3)] pt-[var(--space-3)] border-t border-[var(--shell-border)]"
        >
            {#each PERIODS as period}
                <button
                    class="px-[var(--space-3)] py-[var(--space-1)] rounded-[var(--radius-md)] text-[11px] font-medium border-none cursor-pointer transition-all duration-150 {activePeriod ===
                    period.key
                        ? 'bg-[var(--accent)] text-[var(--gray-0)]'
                        : 'bg-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--hover-overlay)]'}"
                    onclick={() => (activePeriod = period.key)}
                >
                    {period.label}
                </button>
            {/each}
        </div>
    </div>
</section>
