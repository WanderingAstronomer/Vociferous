<script lang="ts">
  import { getTranscripts, deleteTranscript, type HistoryEntry } from '../lib/api';
  import { onMount } from 'svelte';

  let entries: HistoryEntry[] = $state([]);
  let loading = $state(true);
  let error = $state('');

  onMount(async () => {
    await loadHistory();
  });

  async function loadHistory() {
    loading = true;
    error = '';
    try {
      entries = await getTranscripts();
    } catch (e: any) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  async function handleDelete(id: number) {
    try {
      await deleteTranscript(id);
      entries = entries.filter(e => e.id !== id);
    } catch (e: any) {
      error = e.message;
    }
  }

  function formatDate(iso: string): string {
    return new Date(iso).toLocaleString();
  }

  function truncate(text: string, max = 120): string {
    return text.length > max ? text.slice(0, max) + '…' : text;
  }
</script>

<div class="flex flex-col h-full p-6">
  <div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-semibold">History</h1>
    <button
      class="text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] transition-colors"
      onclick={loadHistory}
    >
      Refresh
    </button>
  </div>

  {#if loading}
    <p class="text-[var(--color-text-muted)]">Loading...</p>
  {:else if error}
    <p class="text-[var(--color-danger)]">{error}</p>
  {:else if entries.length === 0}
    <p class="text-[var(--color-text-muted)]">No transcripts yet.</p>
  {:else}
    <div class="flex-1 overflow-y-auto space-y-2">
      {#each entries as entry (entry.id)}
        <div class="p-4 bg-[var(--color-bg-secondary)] rounded-lg border border-[var(--color-border)] hover:border-[var(--color-accent)]/50 transition-colors group">
          <div class="flex items-start justify-between gap-4">
            <div class="flex-1 min-w-0">
              <p class="text-sm leading-relaxed">{truncate(entry.display_text)}</p>
              <p class="text-xs text-[var(--color-text-muted)] mt-2">
                {formatDate(entry.created_at)} · {entry.model_id} · {entry.language}
              </p>
            </div>
            <button
              class="text-[var(--color-text-muted)] hover:text-[var(--color-danger)] opacity-0 group-hover:opacity-100 transition-all text-sm"
              onclick={() => handleDelete(entry.id)}
              title="Delete"
            >
              ✕
            </button>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>
