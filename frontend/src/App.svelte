<script lang="ts">
    import { ws } from "./lib/ws";
    import { onMount, onDestroy } from "svelte";
    import TranscribeView from "./views/TranscribeView.svelte";
    import HistoryView from "./views/HistoryView.svelte";
    import SearchView from "./views/SearchView.svelte";
    import SettingsView from "./views/SettingsView.svelte";

    type View = "transcribe" | "history" | "search" | "settings";
    let currentView: View = $state("transcribe");

    const navItems: { id: View; label: string; icon: string }[] = [
        { id: "transcribe", label: "Transcribe", icon: "🎙" },
        { id: "history", label: "History", icon: "📋" },
        { id: "search", label: "Search", icon: "🔍" },
        { id: "settings", label: "Settings", icon: "⚙" },
    ];

    onMount(() => {
        ws.connect();
    });

    onDestroy(() => {
        ws.disconnect();
    });
</script>

<div class="flex h-screen bg-[var(--color-bg-primary)] text-[var(--color-text-primary)]">
    <!-- Sidebar -->
    <nav
        class="w-14 bg-[var(--color-bg-secondary)] border-r border-[var(--color-border)] flex flex-col items-center py-4 gap-2"
    >
        {#each navItems as item}
            <button
                class="w-10 h-10 rounded-lg flex items-center justify-center text-lg transition-colors duration-[var(--transition-fast)]
          {currentView === item.id
                    ? 'bg-[var(--color-accent)] text-white'
                    : 'text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-tertiary)] hover:text-[var(--color-text-primary)]'}"
                title={item.label}
                onclick={() => (currentView = item.id)}
            >
                {item.icon}
            </button>
        {/each}
    </nav>

    <!-- Main content -->
    <main class="flex-1 overflow-hidden">
        {#if currentView === "transcribe"}
            <TranscribeView />
        {:else if currentView === "history"}
            <HistoryView />
        {:else if currentView === "search"}
            <SearchView />
        {:else if currentView === "settings"}
            <SettingsView />
        {/if}
    </main>
</div>
