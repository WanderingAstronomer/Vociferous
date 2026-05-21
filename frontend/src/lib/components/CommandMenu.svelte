<script lang="ts">
    import { Check, ChevronRight } from "lucide-svelte";

    import type { CommandNode } from "../actions/command";
    import { commandTitle, isCommandChecked, isCommandDisabled, resolveCommandTree } from "../actions/command";
    import { getZoomFactor } from "../zoom";

    interface Props {
        commands: CommandNode[];
        anchor?: HTMLElement;
        x?: number;
        y?: number;
        placement?: "above" | "below";
        onclose: () => void;
    }

    let { commands, anchor, x, y, placement = "above", onclose }: Props = $props();

    const MENU_WIDTH = 236;
    let resolvedCommands = $derived(resolveCommandTree(commands));
    let menuX = $derived.by(() => {
        if (x !== undefined) return x;
        if (!anchor) return 0;
        const z = getZoomFactor();
        return Math.min(anchor.getBoundingClientRect().left / z, window.innerWidth / z - MENU_WIDTH - 8);
    });
    let menuY = $derived.by(() => {
        if (y !== undefined) return y;
        if (!anchor) return 0;
        const z = getZoomFactor();
        const rect = anchor.getBoundingClientRect();
        return placement === "below" ? rect.bottom / z + 8 : rect.top / z - 8;
    });

    function shouldSeparate(items: CommandNode[], index: number): boolean {
        if (index === 0) return false;
        return items[index - 1].group !== items[index].group;
    }

    function run(command: CommandNode, event: MouseEvent) {
        if (isCommandDisabled(command)) return;
        if (!command.run) return;
        command.run(event);
        onclose();
    }

    function handleKeydown(event: KeyboardEvent) {
        if (event.key === "Escape") onclose();
    }

    $effect(() => {
        document.addEventListener("keydown", handleKeydown);
        return () => document.removeEventListener("keydown", handleKeydown);
    });
</script>

{#snippet menuItems(items: CommandNode[], depth: number)}
    {#each items as command, index (command.id)}
        {@const Icon = command.icon}
        {@const children = command.children ?? []}
        {@const disabled = isCommandDisabled(command)}
        {#if shouldSeparate(items, index)}
            <div class="my-1 h-px bg-[var(--shell-border)]"></div>
        {/if}
        <div class="group/menuitem relative">
            <button
                type="button"
                class="flex w-full items-center gap-2 border-none bg-transparent px-3 py-2 text-left text-sm text-[var(--text-primary)] transition-colors duration-150 hover:bg-[var(--hover-overlay)] disabled:cursor-not-allowed disabled:opacity-45"
                class:text-[var(--color-danger)]={command.group === "danger"}
                {disabled}
                title={commandTitle(command)}
                aria-label={commandTitle(command)}
                aria-haspopup={children.length > 0 ? "menu" : undefined}
                onclick={(event) => run(command, event)}
            >
                <span class="flex h-4 w-4 shrink-0 items-center justify-center">
                    {#if Icon}
                        <Icon size={14} />
                    {:else if isCommandChecked(command)}
                        <Check size={14} />
                    {/if}
                </span>
                <span class="min-w-0 flex-1 truncate">{command.label}</span>
                {#if isCommandChecked(command) && Icon}
                    <Check size={13} class="shrink-0 text-[var(--accent)]" />
                {/if}
                {#if children.length > 0}
                    <ChevronRight size={13} class="shrink-0 text-[var(--text-tertiary)]" />
                {/if}
            </button>

            {#if children.length > 0}
                <div
                    class="absolute top-0 hidden min-w-[220px] rounded-lg border border-[var(--shell-border)] bg-[var(--surface-primary)] py-1 shadow-[0_12px_28px_rgba(0,0,0,0.45)] group-hover/menuitem:block group-focus-within/menuitem:block"
                    class:left-full={depth % 2 === 0}
                    class:right-full={depth % 2 === 1}
                    role="menu"
                >
                    {@render menuItems(children, depth + 1)}
                </div>
            {/if}
        </div>
    {/each}
{/snippet}

<div class="fixed inset-0 z-[199]" onclick={onclose} role="presentation"></div>
<div
    class="fixed z-[200] min-w-[236px] max-w-[320px] rounded-lg border border-[var(--shell-border)] bg-[var(--surface-primary)] py-1 shadow-[0_12px_28px_rgba(0,0,0,0.45)]"
    class:-translate-y-full={placement === "above"}
    style="left: {menuX}px; top: {menuY}px;"
    role="menu"
    tabindex="-1"
    onpointerdown={(event) => event.stopPropagation()}
>
    {@render menuItems(resolvedCommands, 0)}
</div>