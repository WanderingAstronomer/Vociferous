<script lang="ts">
    /**
     * CustomSelect — Dark-themed dropdown replacement for native <select>.
     *
     * Native <select> on GTK+WebKit ignores CSS on the popup/option elements,
     * resulting in jarring white backgrounds. This component renders a fully
     * custom dropdown using a button + absolutely-positioned floating listbox.
     *
     * position:absolute keeps the dropdown in the normal document tree so there
     * are no coordinate-space mismatches with CSS zoom, no portal lifecycle
     * conflicts with Svelte 5, and no overflow-clip containing-block surprises.
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
        placeholder = "Select…",
    } = $props();

    let open = $state(false);
    let containerEl: HTMLDivElement | undefined = $state(undefined);
    let triggerEl: HTMLButtonElement | undefined = $state(undefined);
    let flipUp = $state(false);

    let selectedLabel = $derived(options.find((o) => o.value === value)?.label ?? placeholder);

    const DROP_GAP = 4;     // px gap between trigger edge and dropdown
    const MAX_DROP_H = 240; // max-h-60 = 15rem = 240px

    function checkFlip() {
        if (!triggerEl) return;
        const rect = triggerEl.getBoundingClientRect();
        const spaceBelow = window.innerHeight - rect.bottom;
        flipUp = spaceBelow < MAX_DROP_H + DROP_GAP && rect.top > spaceBelow;
    }

    function toggle() {
        if (!open) {
            checkFlip();
        }
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
            document.addEventListener("scroll", closeOnScroll, true);
            return () => {
                document.removeEventListener("click", handleClickOutside, true);
                document.removeEventListener("scroll", closeOnScroll, true);
            };
        }
    });

    function closeOnScroll(e: Event) {
        if (e.target instanceof HTMLElement && e.target.closest("[data-custom-select-dropdown]")) return;
        open = false;
    }

    const triggerClasses =
        "flex items-center justify-between w-full h-10 px-3 bg-[var(--surface-primary)] border border-[var(--shell-border)] rounded text-[var(--text-primary)] text-sm cursor-pointer outline-none transition-colors duration-150 hover:border-[var(--accent)] focus:border-[var(--accent)]";
    const optionClasses =
        "flex items-center justify-between px-3 py-2 text-sm text-[var(--text-primary)] cursor-pointer transition-colors duration-150 hover:bg-[var(--hover-overlay-blue)]";
</script>

<div class="relative flex-1" bind:this={containerEl}>
    <button
        bind:this={triggerEl}
        type="button"
        class={triggerClasses}
        {id}
        onclick={toggle}
        onkeydown={handleKeydown}
        aria-haspopup="listbox"
        aria-expanded={open}
    >
        <span class="overflow-hidden text-ellipsis whitespace-nowrap flex-1 text-left">{selectedLabel}</span>
        <div class="shrink-0 text-[var(--text-tertiary)] transition-transform duration-150" class:rotate-180={open}>
            <ChevronDown size={14} />
        </div>
    </button>

    {#if open}
        <ul
            data-custom-select-dropdown
            class="absolute left-0 w-full max-h-60 overflow-y-auto bg-[var(--surface-primary)] border border-[var(--accent-muted)] rounded shadow-[0_8px_24px_rgba(0,0,0,0.4)] z-[9999] list-none m-0 py-1"
            class:top-full={!flipUp}
            class:bottom-full={flipUp}
            style="margin-{flipUp ? 'bottom' : 'top'}: {DROP_GAP}px;"
            role="listbox"
        >
            {#each options as opt}
                <li
                    class={optionClasses}
                    class:text-[var(--accent)]={opt.value === value}
                    role="option"
                    tabindex="0"
                    aria-selected={opt.value === value}
                    onclick={() => select(opt.value)}
                    onkeydown={(e) => e.key === "Enter" && select(opt.value)}
                >
                    <span class="overflow-hidden text-ellipsis whitespace-nowrap flex-1">{opt.label}</span>
                    {#if opt.value === value}
                        <Check size={12} />
                    {/if}
                </li>
            {/each}
        </ul>
    {/if}
</div>
