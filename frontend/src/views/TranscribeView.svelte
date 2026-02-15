<script lang="ts">
  import { ws } from '../lib/ws';
  import { onMount } from 'svelte';

  let isRecording = $state(false);
  let statusText = $state('Ready');
  let transcription = $state('');

  onMount(() => {
    const unsubs = [
      ws.on('recording_started', () => {
        isRecording = true;
        statusText = 'Recording...';
      }),
      ws.on('recording_stopped', () => {
        isRecording = false;
        statusText = 'Transcribing...';
      }),
      ws.on('transcription_complete', (data: any) => {
        transcription = data.text;
        statusText = 'Done';
      }),
      ws.on('transcription_error', (data: any) => {
        statusText = `Error: ${data.message}`;
      }),
    ];
    return () => unsubs.forEach(fn => fn());
  });

  function toggleRecording() {
    if (isRecording) {
      ws.send('stop_recording');
    } else {
      ws.send('start_recording');
    }
  }
</script>

<div class="flex flex-col h-full p-6">
  <h1 class="text-2xl font-semibold mb-6">Transcribe</h1>

  <!-- Status -->
  <div class="text-sm text-[var(--color-text-secondary)] mb-4">
    {statusText}
  </div>

  <!-- Record button -->
  <div class="flex-1 flex items-center justify-center">
    <button
      class="w-32 h-32 rounded-full border-4 transition-all duration-300 flex items-center justify-center text-4xl
        {isRecording
          ? 'border-[var(--color-danger)] bg-[var(--color-danger)]/10 animate-pulse'
          : 'border-[var(--color-accent)] bg-[var(--color-accent)]/10 hover:bg-[var(--color-accent)]/20'
        }"
      onclick={toggleRecording}
    >
      {isRecording ? '⏹' : '🎙'}
    </button>
  </div>

  <!-- Transcription output -->
  {#if transcription}
    <div class="mt-6 p-4 bg-[var(--color-bg-secondary)] rounded-lg border border-[var(--color-border)]">
      <p class="text-sm leading-relaxed">{transcription}</p>
    </div>
  {/if}
</div>
