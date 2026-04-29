<script lang="ts">
    import { formatDuration, formatWpm } from "../../formatters";

    interface Props {
        hasText: boolean;
        durationMs: number;
        speechDurationMs: number;
        wordCount: number;
    }

    let { hasText, durationMs, speechDurationMs, wordCount }: Props = $props();

    const speechPct = $derived(durationMs > 0 ? Math.round((speechDurationMs / durationMs) * 100) : 0);
</script>

{#if hasText && durationMs > 0}
    <div
        class="flex items-center justify-center gap-[var(--space-3)] py-[var(--space-2)] px-[var(--space-3)] bg-[var(--surface-primary)] rounded-[var(--radius-sm)] shrink-0"
    >
        <span class="text-[var(--text-sm)] text-[var(--text-tertiary)]">
            <span class="font-[var(--weight-emphasis)] font-[var(--font-mono)] text-[var(--text-primary)]"
                >{formatDuration(durationMs)}</span
            > Duration
        </span>
        <span class="w-px h-4 bg-[var(--shell-border)]"></span>
        <span class="text-[var(--text-sm)] text-[var(--text-tertiary)]">
            <span class="font-[var(--weight-emphasis)] font-[var(--font-mono)] text-[var(--text-primary)]"
                >{formatDuration(speechDurationMs)}</span
            > Speech
        </span>
        <span class="w-px h-4 bg-[var(--shell-border)]"></span>
        <span class="text-[var(--text-sm)] text-[var(--text-tertiary)]">
            <span class="font-[var(--weight-emphasis)] font-[var(--font-mono)] text-[var(--text-primary)]"
                >{wordCount}</span
            > Words
        </span>
        <span class="w-px h-4 bg-[var(--shell-border)]"></span>
        <span class="text-[var(--text-sm)] text-[var(--text-tertiary)]">
            <span class="font-[var(--weight-emphasis)] font-[var(--font-mono)] text-[var(--text-primary)]"
                >{formatWpm(wordCount, speechDurationMs || durationMs)}</span
            > Pace
        </span>
        <span class="w-px h-4 bg-[var(--shell-border)]"></span>
        <div class="flex items-center gap-[var(--space-2)] min-w-[100px] max-w-[280px] flex-1">
            <span class="text-[var(--text-sm)] text-[var(--text-tertiary)] shrink-0">Active Speech</span>
            <div class="flex-1 h-1.5 rounded-full bg-[var(--surface-tertiary)] overflow-hidden">
                <div
                    class="h-full rounded-full bg-[var(--accent)] transition-[width] duration-500"
                    style="width: {speechPct}%"
                ></div>
            </div>
            <span class="text-[var(--text-xs)] font-[var(--font-mono)] text-[var(--text-tertiary)] shrink-0"
                >{speechPct}%</span
            >
        </div>
    </div>
{/if}
