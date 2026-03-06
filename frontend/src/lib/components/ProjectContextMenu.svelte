<script lang="ts">
    /**
     * ProjectContextMenu — Floating context menu for project assignment.
     *
     * Purely display + callback. No internal state.
     */

    import { Check } from "lucide-svelte";

    interface Props {
        x: number;
        y: number;
        options: { value: string; label: string }[];
        isMulti: boolean;
        selectionCount: number;
        currentProjectId: string;
        onSelect: (value: string) => void;
    }

    let { x, y, options, isMulti, selectionCount, currentProjectId, onSelect }: Props = $props();
</script>

<div
    class="fixed min-w-[260px] max-w-[340px] max-h-[360px] overflow-y-auto bg-[var(--surface-primary)] border border-[var(--shell-border)] rounded-[var(--radius-md)] shadow-[0_12px_28px_rgba(0,0,0,0.45)] py-1 z-[200]"
    style="left: {x}px; top: {y}px"
    role="menu"
    tabindex="-1"
    onpointerdown={(e) => e.stopPropagation()}
    oncontextmenu={(e) => e.preventDefault()}
>
    <div class="px-3 py-1.5 text-[11px] uppercase tracking-wide text-[var(--text-tertiary)]">
        {#if isMulti}
            Assign {selectionCount} transcripts to project
        {:else}
            Assign to Project
        {/if}
    </div>
    {#each options as option}
        <button
            class="w-full flex items-center justify-between gap-2 px-3 py-1.5 border-none bg-transparent text-left text-[var(--text-sm)] cursor-pointer transition-colors duration-150 hover:bg-[var(--hover-overlay-blue)] {currentProjectId === option.value
                ? 'text-[var(--accent)]'
                : 'text-[var(--text-primary)]'}"
            onclick={() => onSelect(option.value)}
            role="menuitem"
        >
            <span class="truncate">{option.label}</span>
            {#if currentProjectId === option.value}
                <Check size={12} />
            {/if}
        </button>
    {/each}
</div>
