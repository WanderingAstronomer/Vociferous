<script lang="ts">
    import { Mic, Library, Sparkles, Settings, User } from "lucide-svelte";

    import type { ViewId } from "../navigation.svelte";

    interface NavItem {
        id: ViewId;
        label: string;
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        icon: any;
        section: "main" | "footer";
    }

    const navItems: NavItem[] = [
        { id: "transcribe", label: "Transcribe", icon: Mic, section: "main" },
        { id: "transcripts", label: "Transcriptions", icon: Library, section: "main" },
        { id: "refine", label: "Refine", icon: Sparkles, section: "main" },
        { id: "user", label: "User", icon: User, section: "footer" },
        { id: "settings", label: "Settings", icon: Settings, section: "footer" },
    ];

    interface Props {
        currentView: ViewId;
        navigationLocked?: boolean;
        hiddenViews?: Set<ViewId>;
        isRecording?: boolean;
        onNavigate: (view: ViewId) => void;
    }

    let {
        currentView,
        navigationLocked = false,
        hiddenViews = new Set(),
        isRecording = false,
        onNavigate,
    }: Props = $props();

    const mainItems = $derived(navItems.filter((i) => i.section === "main" && !hiddenViews.has(i.id)));
    const footerItems = $derived(navItems.filter((i) => i.section === "footer" && !hiddenViews.has(i.id)));

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

    function getTitle(item: NavItem): string {
        if (isLockedDestination(item.id)) return "Finish or discard edits first";
        if (isRecording && item.id === "transcribe") return "Recording in progress";
        return item.label;
    }
</script>

<nav
    class="flex flex-col w-[var(--rail-width)] min-w-[var(--rail-width)] h-full bg-[var(--shell-bg)] border-r border-[var(--shell-border)] py-5 px-[var(--rail-px)] select-none overflow-hidden"
>
    <div class="flex flex-col gap-1 flex-1">
        {#each mainItems as item}
            <button
                class="rail-button"
                class:active={currentView === item.id}
                class:recording={isRecording && item.id === "transcribe"}
                class:blink={blinkTarget === item.id}
                class:locked={isLockedDestination(item.id)}
                disabled={isLockedDestination(item.id)}
                title={getTitle(item)}
                aria-label={getTitle(item)}
                aria-current={currentView === item.id ? "page" : undefined}
                onclick={() => handleClick(item.id)}
            >
                <item.icon size={22} strokeWidth={1.5} />
            </button>
        {/each}
    </div>

    <div class="h-px bg-[var(--shell-border)] my-[var(--space-2)] shrink-0"></div>

    <div class="flex flex-col gap-1">
        {#each footerItems as item}
            <button
                class="rail-button"
                class:active={currentView === item.id}
                class:blink={blinkTarget === item.id}
                class:locked={isLockedDestination(item.id)}
                disabled={isLockedDestination(item.id)}
                title={getTitle(item)}
                aria-label={getTitle(item)}
                aria-current={currentView === item.id ? "page" : undefined}
                onclick={() => handleClick(item.id)}
            >
                <item.icon size={22} strokeWidth={1.5} />
            </button>
        {/each}
    </div>
</nav>

<style>
    .rail-button {
        display: flex;
        align-items: center;
        justify-content: center;
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
        left: calc(-1 * var(--rail-px));
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
        height: 24px;
    }

    .rail-button.locked {
        opacity: 0.5;
        cursor: not-allowed;
    }

    /* Recording-in-progress is a system state, not a navigation state — it gets a
       dedicated color (red) that overrides the active-view styling when both apply.
       Recording is conventionally red across DAWs, dashcams, video conferencing,
       and OBS; the association is learned and worth honoring. The pulse animation
       differentiates a static red icon from the live recording cue. */
    .rail-button.recording {
        color: var(--color-danger);
        animation: recording-pulse 2s ease-in-out infinite;
    }

    .rail-button.recording::before {
        height: 24px;
        background: var(--color-danger);
    }

    @keyframes recording-pulse {
        0%,
        100% {
            opacity: 1;
        }
        50% {
            opacity: 0.5;
        }
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
