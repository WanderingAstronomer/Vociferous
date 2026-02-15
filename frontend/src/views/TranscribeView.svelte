<script lang="ts">
  import { ws } from '../lib/ws';
  import { onMount } from 'svelte';

  let isRecording = $state(false);
  let statusText = $state('Ready');
  let transcription = $state('');
  let transcriptionId = $state<number | null>(null);
  let audioLevel = $state(0);
  let audioBands = $state<number[]>(new Array(64).fill(0));

  onMount(() => {
    const unsubs = [
      ws.on('recording_started', () => {
        isRecording = true;
        statusText = 'Recording...';
        transcription = '';
      }),
      ws.on('recording_stopped', (data: any) => {
        isRecording = false;
        audioLevel = 0;
        audioBands = new Array(64).fill(0);
        if (data.cancelled) {
          statusText = 'Cancelled';
        } else {
          statusText = 'Transcribing...';
        }
      }),
      ws.on('transcription_complete', (data: any) => {
        transcription = data.text;
        transcriptionId = data.id;
        statusText = 'Done';
      }),
      ws.on('transcription_error', (data: any) => {
        statusText = `Error: ${data.message}`;
      }),
      ws.on('audio_level', (data: any) => {
        audioLevel = data.level;
      }),
      ws.on('audio_spectrum', (data: any) => {
        audioBands = data.bands;
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

  function copyToClipboard() {
    if (transcription) {
      navigator.clipboard.writeText(transcription);
      statusText = 'Copied!';
      setTimeout(() => { statusText = 'Done'; }, 1500);
    }
  }
</script>

<div class="flex flex-col h-full p-6">
  <h1 class="text-2xl font-semibold mb-4">Transcribe</h1>

  <!-- Status -->
  <div class="text-sm text-[var(--color-text-secondary)] mb-4">
    {statusText}
  </div>

  <!-- Audio Visualizer — CAVA-style spectrum bars -->
  {#if isRecording}
    <div class="flex items-end justify-center gap-[2px] h-24 mb-6 px-4">
      {#each audioBands as band, i}
        <div
          class="flex-1 max-w-[6px] rounded-t-sm transition-all duration-75"
          style="height: {Math.max(2, band * 100)}%; background: var(--color-accent); opacity: {0.4 + band * 0.6};"
        ></div>
      {/each}
    </div>
  {/if}

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
      <div class="flex items-start justify-between gap-2 mb-2">
        <span class="text-xs text-[var(--color-text-muted)]">Result</span>
        <button
          class="text-xs text-[var(--color-text-secondary)] hover:text-[var(--color-accent)] transition-colors"
          onclick={copyToClipboard}
          title="Copy to clipboard"
        >
          📋 Copy
        </button>
      </div>
      <p class="text-sm leading-relaxed">{transcription}</p>
    </div>
  {/if}
</div>
