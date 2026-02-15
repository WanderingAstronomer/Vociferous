<script lang="ts">
  import { getConfig, updateConfig, getModels, getHealth } from '../lib/api';
  import { onMount } from 'svelte';

  let config: Record<string, any> = $state({
    model: { model: '' },
    recording: { activation_key: '', recording_mode: 'press_to_toggle' },
    refinement: { model_id: '' },
  });
  let models: { asr: Record<string, any>; slm: Record<string, any> } = $state({ asr: {}, slm: {} });
  let health: { status: string; version: string } = $state({ status: 'unknown', version: '' });
  let loading = $state(true);
  let saving = $state(false);
  let message = $state('');

  onMount(async () => {
    try {
      [config, models, health] = await Promise.all([getConfig(), getModels(), getHealth()]);
    } catch (e: any) {
      message = `Failed to load: ${e.message}`;
    } finally {
      loading = false;
    }
  });

  async function saveConfig() {
    saving = true;
    message = '';
    try {
      config = await updateConfig(config) as Record<string, any>;
      message = 'Settings saved.';
      setTimeout(() => message = '', 3000);
    } catch (e: any) {
      message = `Error: ${e.message}`;
    } finally {
      saving = false;
    }
  }
</script>

<div class="flex flex-col h-full p-6 overflow-y-auto">
  <h1 class="text-2xl font-semibold mb-6">Settings</h1>

  {#if loading}
    <p class="text-[var(--color-text-muted)]">Loading...</p>
  {:else}
    <!-- Health -->
    <section class="mb-8">
      <h2 class="text-lg font-medium mb-3 text-[var(--color-text-secondary)]">System</h2>
      <div class="p-4 bg-[var(--color-bg-secondary)] rounded-lg border border-[var(--color-border)]">
        <p class="text-sm">
          Status: <span class="text-[var(--color-success)]">{health.status}</span>
          {#if health.version} · v{health.version}{/if}
        </p>
      </div>
    </section>

    <!-- Model Selection -->
    <section class="mb-8">
      <h2 class="text-lg font-medium mb-3 text-[var(--color-text-secondary)]">Models</h2>
      <div class="space-y-3">
        <label class="block">
          <span class="text-sm text-[var(--color-text-secondary)]">ASR Model</span>
          <select
            class="mt-1 block w-full bg-[var(--color-bg-tertiary)] border border-[var(--color-border)] rounded-[var(--radius)] px-3 py-2 text-sm"
            bind:value={config.model.model}
          >
            {#each Object.entries(models.asr) as [id, m]}
              <option value={id}>{(m as any).name} ({(m as any).size_mb}MB)</option>
            {/each}
          </select>
        </label>

        <label class="block">
          <span class="text-sm text-[var(--color-text-secondary)]">SLM Model</span>
          <select
            class="mt-1 block w-full bg-[var(--color-bg-tertiary)] border border-[var(--color-border)] rounded-[var(--radius)] px-3 py-2 text-sm"
            bind:value={config.refinement.model_id}
          >
            {#each Object.entries(models.slm) as [id, m]}
              <option value={id}>{(m as any).name} ({(m as any).size_mb}MB)</option>
            {/each}
          </select>
        </label>
      </div>
    </section>

    <!-- Recording -->
    <section class="mb-8">
      <h2 class="text-lg font-medium mb-3 text-[var(--color-text-secondary)]">Recording</h2>
      <div class="space-y-3">
        <label class="block">
          <span class="text-sm text-[var(--color-text-secondary)]">Activation Key</span>
          <input
            type="text"
            class="mt-1 block w-full bg-[var(--color-bg-tertiary)] border border-[var(--color-border)] rounded-[var(--radius)] px-3 py-2 text-sm"
            bind:value={config.recording.activation_key}
          />
        </label>
        <label class="block">
          <span class="text-sm text-[var(--color-text-secondary)]">Recording Mode</span>
          <select
            class="mt-1 block w-full bg-[var(--color-bg-tertiary)] border border-[var(--color-border)] rounded-[var(--radius)] px-3 py-2 text-sm"
            bind:value={config.recording.recording_mode}
          >
            <option value="press_to_toggle">Press to Toggle</option>
            <option value="hold_to_record">Hold to Record</option>
            <option value="continuous">Continuous (VAD)</option>
          </select>
        </label>
      </div>
    </section>

    <!-- Save -->
    <div class="flex items-center gap-4">
      <button
        class="px-4 py-2 bg-[var(--color-accent)] hover:bg-[var(--color-accent-hover)] text-white rounded-[var(--radius)] text-sm font-medium transition-colors disabled:opacity-50"
        onclick={saveConfig}
        disabled={saving}
      >
        {saving ? 'Saving...' : 'Save Settings'}
      </button>
      {#if message}
        <span class="text-sm {message.startsWith('Error') ? 'text-[var(--color-danger)]' : 'text-[var(--color-success)]'}">
          {message}
        </span>
      {/if}
    </div>
  {/if}
</div>
