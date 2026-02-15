<script lang="ts">
  import { getTranscripts, deleteTranscript, refineTranscript, type Transcript } from '../lib/api';
  import { ws } from '../lib/ws';
  import { onMount } from 'svelte';

  let entries: Transcript[] = $state([]);
  let loading = $state(true);
  let error = $state('');
  let selectedId = $state<number | null>(null);
  let refining = $state<number | null>(null);

  onMount(async () => {
    await loadHistory();

    const unsubs = [
      ws.on('transcription_complete', () => {
        loadHistory();
      }),
      ws.on('transcript_deleted', (data: any) => {
        entries = entries.filter(e => e.id !== data.id);
      }),
      ws.on('refinement_complete', (data: any) => {
        refining = null;
        loadHistory();
      }),
      ws.on('refinement_error', (data: any) => {
        refining = null;
        error = `Refinement error: ${data.message}`;
      }),
    ];
    return () => unsubs.forEach(fn => fn());
  });

  async function loadHistory() {
    loading = entries.length === 0;
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
      if (selectedId === id) selectedId = null;
    } catch (e: any) {
      error = e.message;
    }
  }

  async function handleRefine(id: number, level: number) {
    refining = id;
    try {
      await refineTranscript(id, level);
    } catch (e: any) {
      error = e.message;
      refining = null;
    }
  }

  function formatDate(iso: string): string {
    return new Date(iso).toLocaleString();
  }

  function truncate(text: string, max = 120): string {
    return text.length > max ? text.slice(0, max) + '…' : text;
  }

  function getDisplayText(entry: Transcript): string {
    return entry.normalized_text || entry.raw_text || '';
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
        <div
          class="p-4 bg-[var(--color-bg-secondary)] rounded-lg border transition-colors group cursor-pointer
            {selectedId === entry.id
              ? 'border-[var(--color-accent)]'
              : 'border-[var(--color-border)] hover:border-[var(--color-accent)]/50'
            }"
          role="button"
          tabindex="0"
          onclick={() => selectedId = selectedId === entry.id ? null : entry.id}
          onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); selectedId = selectedId === entry.id ? null : entry.id; }}}
        >
          <div class="flex items-start justify-between gap-4">
            <div class="flex-1 min-w-0">
              <p class="text-sm leading-relaxed">
                {selectedId === entry.id ? getDisplayText(entry) : truncate(getDisplayText(entry))}
              </p>
              <p class="text-xs text-[var(--color-text-muted)] mt-2">
                {formatDate(entry.created_at)} · {entry.duration_ms}ms
              </p>
            </div>
            <div class="flex gap-1 opacity-0 group-hover:opacity-100 transition-all">
              {#if refining === entry.id}
                <span class="text-xs text-[var(--color-accent)] animate-pulse">Refining...</span>
              {:else}
                <button
                  class="text-xs text-[var(--color-text-muted)] hover:text-[var(--color-accent)] px-1"
                  onclick={(e) => { e.stopPropagation(); handleRefine(entry.id, 2); }}
                  title="Refine"
                >
                  ✨
                </button>
              {/if}
              <button
                class="text-xs text-[var(--color-text-muted)] hover:text-[var(--color-danger)] px-1"
                onclick={(e) => { e.stopPropagation(); handleDelete(entry.id); }}
                title="Delete"
              >
                ✕
              </button>
            </div>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>
