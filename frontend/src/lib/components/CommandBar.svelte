<script lang="ts">
    import { MoreHorizontal } from "lucide-svelte";

    import type { CommandNode } from "../actions/command";
    import { commandPlacement, commandTitle, isCommandDisabled, resolveCommandTree } from "../actions/command";
    import CommandMenu from "./CommandMenu.svelte";

    interface Props {
        commands: CommandNode[];
        gap?: string;
        padx?: string;
    }

    let { commands, gap = "gap-2", padx = "px-4" }: Props = $props();

    let menuOpen = $state(false);
    let menuAnchor: HTMLElement | undefined = $state(undefined);
    let resolvedCommands = $derived(resolveCommandTree(commands));
    let barCommands = $derived(resolvedCommands.filter((command) => commandPlacement(command) !== "overflow"));
    let startCommands = $derived(barCommands.filter((command) => command.section === "start"));
    let endCommands = $derived(barCommands.filter((command) => command.section !== "start"));
    let overflowCommands = $derived(resolvedCommands.filter((command) => commandPlacement(command) !== "bar"));

    function run(command: CommandNode, event?: MouseEvent) {
        if (isCommandDisabled(command)) return;
        command.run?.(event);
    }

    function commandButtonClasses(command: CommandNode): string {
        const variant = command.variant ?? "secondary";
        const sizeClasses = command.iconOnly ? "h-8 w-8 px-0 text-xs" : "h-8 px-3 text-xs gap-1.5";
        const baseClasses =
            "inline-flex shrink-0 items-center justify-center font-semibold cursor-pointer transition-all duration-150 whitespace-nowrap select-none rounded-lg disabled:opacity-40 disabled:cursor-not-allowed";
        const variantClasses = {
            primary: "border-none bg-[var(--accent)] text-[var(--gray-0)] hover:not-disabled:bg-[var(--accent-hover)]",
            secondary:
                "border-none bg-[var(--surface-tertiary)] text-[var(--text-primary)] hover:not-disabled:bg-[var(--gray-6)]",
            destructive:
                "border-none bg-[var(--color-danger-surface)] text-[var(--color-danger)] hover:not-disabled:bg-[var(--red-8)]",
            ghost: "border-none bg-transparent text-[var(--text-secondary)] hover:not-disabled:text-[var(--text-primary)] hover:not-disabled:bg-[var(--hover-overlay)]",
            neutral:
                "border border-[var(--shell-border)] bg-[var(--surface-secondary)] text-[var(--text-secondary)] hover:not-disabled:text-[var(--text-primary)] hover:not-disabled:border-[var(--accent)]",
            "danger-outline":
                "border border-[var(--color-danger)] bg-transparent text-[var(--color-danger)] hover:not-disabled:bg-[var(--color-danger-surface)]",
        };
        return `${baseClasses} ${sizeClasses} ${variantClasses[variant]}`;
    }
</script>

<div class="shrink-0 {padx} py-2 overflow-hidden">
    <div class="flex flex-nowrap items-center {gap} overflow-hidden rounded-lg bg-[var(--surface-secondary)] px-3 py-1.5">
        {#each startCommands as command (command.id)}
            {@const Icon = command.icon}
            <button
                type="button"
                class={commandButtonClasses(command)}
                disabled={isCommandDisabled(command)}
                title={commandTitle(command)}
                aria-label={commandTitle(command)}
                onclick={(event) => run(command, event)}
            >
                {#if Icon}<Icon size={13} />{/if}
                {#if !command.iconOnly}<span>{command.label}</span>{/if}
            </button>
        {/each}

        <div class="flex-1 min-w-2"></div>

        {#each endCommands as command (command.id)}
            {@const Icon = command.icon}
            <button
                type="button"
                class={commandButtonClasses(command)}
                disabled={isCommandDisabled(command)}
                title={commandTitle(command)}
                aria-label={commandTitle(command)}
                onclick={(event) => run(command, event)}
            >
                {#if Icon}<Icon size={13} />{/if}
                {#if !command.iconOnly}<span>{command.label}</span>{/if}
            </button>
        {/each}

        {#if overflowCommands.length > 0}
            <div bind:this={menuAnchor}>
                <button
                    type="button"
                    class="inline-flex h-8 w-8 shrink-0 cursor-pointer items-center justify-center rounded-lg border-none bg-[var(--surface-tertiary)] px-0 text-xs font-semibold text-[var(--text-primary)] transition-all duration-150 hover:bg-[var(--gray-6)]"
                    title="More actions"
                    aria-label="More actions"
                    onclick={() => (menuOpen = !menuOpen)}
                >
                    <MoreHorizontal size={14} />
                </button>
            </div>
        {/if}
    </div>
</div>

{#if menuOpen && overflowCommands.length > 0}
    <CommandMenu commands={overflowCommands} anchor={menuAnchor} onclose={() => (menuOpen = false)} />
{/if}