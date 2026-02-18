<script lang="ts">
    import { Mic, ScrollText, FolderOpen, Search, Sparkles, Settings, User } from "lucide-svelte";

    import type { ViewId } from "../navigation.svelte";

    interface NavItem {
        id: ViewId;
        label: string;
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        icon: any; // Relaxed type for compatibility with lucide-svelte
        section: "main" | "footer";
    }

    const navItems: NavItem[] = [
        { id: "transcribe", label: "Transcribe", icon: Mic, section: "main" },
        { id: "history", label: "History", icon: ScrollText, section: "main" },
        { id: "projects", label: "Projects", icon: FolderOpen, section: "main" },
        { id: "search", label: "Search", icon: Search, section: "main" },
        { id: "refine", label: "Refine", icon: Sparkles, section: "main" },
        { id: "settings", label: "Settings", icon: Settings, section: "footer" },
        { id: "user", label: "User", icon: User, section: "footer" },
    ];

    interface Props {
        currentView: ViewId;
        navigationLocked?: boolean;
        hiddenViews?: Set<ViewId>;
        onNavigate: (view: ViewId) => void;
    }

    let { currentView, navigationLocked = false, hiddenViews = new Set(), onNavigate }: Props = $props();

    const mainItems = $derived(navItems.filter((i) => i.section === "main" && !hiddenViews.has(i.id)));
    const footerItems = $derived(navItems.filter((i) => i.section === "footer" && !hiddenViews.has(i.id)));

    /* Blink animation state */
    let blinkTarget: ViewId | null = $state(null);

    function handleClick(id: ViewId) {
        if (navigationLocked && id !== currentView) return;
        if (id === currentView) return;
        blinkTarget = id;
        setTimeout(() => {
            blinkTarget = null;
        }, 200);
        onNavigate(id);
    }

    function isLockedDestination(id: ViewId): boolean {
        return navigationLocked && id !== currentView;
    }
</script>

<nav class="flex flex-col w-[var(--rail-width)] min-w-[var(--rail-width)] h-full bg-[var(--shell-bg)] border-r border-[var(--shell-border)] py-7 px-4 select-none overflow-hidden">
    <div class="flex flex-col gap-1.5 flex-1">
        {#each mainItems as item}
            <button
                class="rail-button"
                class:active={currentView === item.id}
                class:blink={blinkTarget === item.id}
                class:locked={isLockedDestination(item.id)}
                disabled={isLockedDestination(item.id)}
                title={isLockedDestination(item.id) ? "Finish or discard edits first" : item.label}
                onclick={() => handleClick(item.id)}
            >
                <span class="flex items-center justify-center w-10 h-10 shrink-0">
                    <item.icon size={32} strokeWidth={1.5} />
                </span>
                <span class="text-[var(--text-sm)] font-medium leading-none tracking-wide whitespace-nowrap">{item.label}</span>
            </button>
        {/each}
    </div>

    <div class="h-px bg-[var(--shell-border)] my-[var(--space-2)] shrink-0"></div>

    <div class="flex flex-col gap-1.5">
        {#each footerItems as item}
            <button
                class="rail-button"
                class:active={currentView === item.id}
                class:blink={blinkTarget === item.id}
                class:locked={isLockedDestination(item.id)}
                disabled={isLockedDestination(item.id)}
                title={isLockedDestination(item.id) ? "Finish or discard edits first" : item.label}
                onclick={() => handleClick(item.id)}
            >
                <span class="flex items-center justify-center w-10 h-10 shrink-0">
                    <item.icon size={32} strokeWidth={1.5} />
                </span>
                <span class="text-[var(--text-sm)] font-medium leading-none tracking-wide whitespace-nowrap">{item.label}</span>
            </button>
        {/each}
    </div>
</nav>

<style>
    .rail-button {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 8px;
        width: 100%;
        height: var(--rail-button-height);
        border: none;
        border-radius: var(--radius-md);
        background: transparent;
        color: var(--text-tertiary);
        cursor: pointer;
        position: relative;
        transition:
            color var(--transition-fast),
            background var(--transition-fast);
    }

    .rail-button::before {
        content: "";
        position: absolute;
        left: -16px;
        top: 50%;
        transform: translateY(-50%);
        width: 3px;
        height: 0;
        background: var(--accent);
        border-radius: 0 2px 2px 0;
        transition: height var(--transition-normal);
    }

    .rail-button:hover {
        color: var(--text-secondary);
        background: var(--hover-overlay);
    }

    .rail-button.active {
        color: var(--accent);
        background: var(--hover-overlay-blue);
    }

    .rail-button.active::before {
        height: 32px;
    }

    .rail-button.locked {
        opacity: 0.5;
        cursor: not-allowed;
    }

    .rail-button.blink {
        animation: rail-blink 200ms ease;
    }

    @keyframes rail-blink {
        0%,
        100% {
            opacity: 1;
        }
        50% {
            opacity: 0.4;
        }
    }
</style>
