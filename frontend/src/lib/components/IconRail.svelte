<script lang="ts">
    import { Mic, ScrollText, FolderOpen, Search, Sparkles, Settings, User } from "lucide-svelte";

    import type { Component } from "svelte";

    export type ViewId = "transcribe" | "history" | "projects" | "search" | "refine" | "settings" | "user";

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
        hiddenViews?: Set<ViewId>;
        onNavigate: (view: ViewId) => void;
    }

    let { currentView, hiddenViews = new Set(), onNavigate }: Props = $props();

    const mainItems = $derived(navItems.filter((i) => i.section === "main" && !hiddenViews.has(i.id)));
    const footerItems = $derived(navItems.filter((i) => i.section === "footer" && !hiddenViews.has(i.id)));

    /* Blink animation state */
    let blinkTarget: ViewId | null = $state(null);

    function handleClick(id: ViewId) {
        if (id === currentView) return;
        blinkTarget = id;
        setTimeout(() => {
            blinkTarget = null;
        }, 200);
        onNavigate(id);
    }
</script>

<nav class="icon-rail">
    <div class="rail-main">
        {#each mainItems as item}
            <button
                class="rail-button"
                class:active={currentView === item.id}
                class:blink={blinkTarget === item.id}
                title={item.label}
                onclick={() => handleClick(item.id)}
            >
                <span class="rail-icon">
                    <item.icon size={32} strokeWidth={1.5} />
                </span>
                <span class="rail-label">{item.label}</span>
            </button>
        {/each}
    </div>

    <div class="rail-separator"></div>

    <div class="rail-footer">
        {#each footerItems as item}
            <button
                class="rail-button"
                class:active={currentView === item.id}
                class:blink={blinkTarget === item.id}
                title={item.label}
                onclick={() => handleClick(item.id)}
            >
                <span class="rail-icon">
                    <item.icon size={32} strokeWidth={1.5} />
                </span>
                <span class="rail-label">{item.label}</span>
            </button>
        {/each}
    </div>
</nav>

<style>
    .icon-rail {
        width: var(--rail-width);
        min-width: var(--rail-width);
        height: 100%;
        background: var(--shell-bg);
        border-right: 1px solid var(--shell-border);
        display: flex;
        flex-direction: column;
        padding: 28px 16px;
        gap: 0;
        user-select: none;
        overflow: hidden;
    }

    .rail-main {
        display: flex;
        flex-direction: column;
        gap: 6px;
        flex: 1;
    }

    .rail-separator {
        height: 1px;
        background: var(--shell-border);
        margin: var(--space-2) 0;
        flex-shrink: 0;
    }

    .rail-footer {
        display: flex;
        flex-direction: column;
        gap: 6px;
    }

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

    .rail-button.blink {
        animation: rail-blink 200ms ease;
    }

    .rail-icon {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 40px;
        height: 40px;
        flex-shrink: 0;
    }

    .rail-label {
        font-size: var(--text-sm);
        font-weight: 500;
        line-height: 1;
        letter-spacing: 0.02em;
        white-space: nowrap;
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
