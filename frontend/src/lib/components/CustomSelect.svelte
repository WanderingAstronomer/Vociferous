<script lang="ts">
    /**
     * CustomSelect — Dark-themed dropdown replacement for native <select>.
     *
     * Native <select> on GTK+WebKit ignores CSS on the popup/option elements,
     * resulting in jarring white backgrounds. This component renders a fully
     * custom dropdown using a button + floating listbox pattern.
     */
    import { ChevronDown, Check } from "lucide-svelte";

    interface Option {
        value: string;
        label: string;
    }

    let {
        options = [] as Option[],
        value = "",
        onchange = (_value: string) => {},
        id = undefined as string | undefined,
        small = false,
        placeholder = "Select…",
    } = $props();

    let open = $state(false);
    let containerEl: HTMLDivElement | undefined = $state(undefined);

    let selectedLabel = $derived(options.find((o) => o.value === value)?.label ?? placeholder);

    function toggle() {
        open = !open;
    }

    function select(optValue: string) {
        onchange(optValue);
        open = false;
    }

    function handleKeydown(e: KeyboardEvent) {
        if (e.key === "Escape") {
            open = false;
        } else if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            toggle();
        } else if (e.key === "ArrowDown" && open) {
            e.preventDefault();
            const idx = options.findIndex((o) => o.value === value);
            if (idx < options.length - 1) select(options[idx + 1].value);
        } else if (e.key === "ArrowUp" && open) {
            e.preventDefault();
            const idx = options.findIndex((o) => o.value === value);
            if (idx > 0) select(options[idx - 1].value);
        }
    }

    function handleClickOutside(e: MouseEvent) {
        if (containerEl && !containerEl.contains(e.target as Node)) {
            open = false;
        }
    }

    $effect(() => {
        if (open) {
            document.addEventListener("click", handleClickOutside, true);
            return () => document.removeEventListener("click", handleClickOutside, true);
        }
    });
</script>

<div class="custom-select" class:small bind:this={containerEl}>
    <button
        type="button"
        class="select-trigger"
        {id}
        onclick={toggle}
        onkeydown={handleKeydown}
        aria-haspopup="listbox"
        aria-expanded={open}
    >
        <span class="select-value">{selectedLabel}</span>
        <ChevronDown size={14} class="select-chevron {open ? 'rotated' : ''}" />
    </button>

    {#if open}
        <ul class="select-dropdown" role="listbox">
            {#each options as opt}
                <li
                    class="select-option"
                    class:selected={opt.value === value}
                    role="option"
                    aria-selected={opt.value === value}
                    onclick={() => select(opt.value)}
                    onkeydown={(e) => e.key === "Enter" && select(opt.value)}
                >
                    <span class="option-label">{opt.label}</span>
                    {#if opt.value === value}
                        <Check size={12} />
                    {/if}
                </li>
            {/each}
        </ul>
    {/if}
</div>

<style>
    .custom-select {
        position: relative;
        flex: 1;
    }
    .custom-select.small {
        max-width: 200px;
    }

    .select-trigger {
        display: flex;
        align-items: center;
        justify-content: space-between;
        width: 100%;
        height: 40px;
        padding: 0 var(--space-2);
        background: var(--surface-primary);
        border: 1px solid var(--shell-border);
        border-radius: var(--radius-sm);
        color: var(--text-primary);
        font-family: var(--font-family);
        font-size: var(--text-sm);
        cursor: pointer;
        outline: none;
        transition: border-color var(--transition-fast);
    }
    .select-trigger:hover,
    .select-trigger:focus {
        border-color: var(--accent);
    }

    .select-value {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        flex: 1;
        text-align: left;
    }

    :global(.select-chevron) {
        flex-shrink: 0;
        color: var(--text-tertiary);
        transition: transform var(--transition-fast);
    }
    :global(.select-chevron.rotated) {
        transform: rotate(180deg);
    }

    .select-dropdown {
        position: absolute;
        top: calc(100% + 4px);
        left: 0;
        right: 0;
        max-height: 240px;
        overflow-y: auto;
        background: var(--surface-primary);
        border: 1px solid var(--accent-muted);
        border-radius: var(--radius-sm);
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
        z-index: 100;
        list-style: none;
        margin: 0;
        padding: 4px 0;
    }

    .select-option {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 8px var(--space-2);
        font-size: var(--text-sm);
        color: var(--text-primary);
        cursor: pointer;
        transition: background var(--transition-fast);
    }
    .select-option:hover {
        background: var(--hover-overlay-blue);
    }
    .select-option.selected {
        color: var(--accent);
    }

    .option-label {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        flex: 1;
    }
</style>
