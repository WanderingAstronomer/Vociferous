<script lang="ts">
  /**
   * MiniWidget — Compact recording indicator.
   *
   * Displayed in a separate pywebview window (on_top, frameless, transparent).
   * Shows a pulsing record indicator + elapsed time when recording.
   * Clicking it dispatches toggle_recording via the API.
   */

  import { onMount, onDestroy } from 'svelte';

  let isRecording = $state(false);
  let elapsed = $state(0);
  let timer: ReturnType<typeof setInterval> | null = null;
  let ws: WebSocket | null = null;

  function startTimer() {
    elapsed = 0;
    timer = setInterval(() => elapsed++, 1000);
  }

  function stopTimer() {
    if (timer) {
      clearInterval(timer);
      timer = null;
    }
    elapsed = 0;
  }

  function formatTime(seconds: number): string {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  }

  async function toggleRecording() {
    try {
      await fetch('/api/intents', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type: 'toggle_recording' }),
      });
    } catch (e) {
      console.error('Failed to toggle recording:', e);
    }
  }

  function connectWS() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${location.host}/ws`);

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'recording_started') {
          isRecording = true;
          startTimer();
        } else if (msg.type === 'recording_stopped') {
          isRecording = false;
          stopTimer();
        }
      } catch {}
    };

    ws.onclose = () => {
      setTimeout(connectWS, 2000);
    };
  }

  onMount(() => connectWS());
  onDestroy(() => {
    ws?.close();
    stopTimer();
  });
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
  class="widget"
  class:recording={isRecording}
  onclick={toggleRecording}
  onkeydown={(e) => e.key === 'Enter' && toggleRecording()}
  role="button"
  tabindex="0"
  title={isRecording ? 'Stop recording' : 'Start recording'}
>
  <div class="indicator" class:pulse={isRecording}></div>
  {#if isRecording}
    <span class="time">{formatTime(elapsed)}</span>
  {/if}
</div>

<style>
  :global(body) {
    margin: 0;
    padding: 0;
    background: transparent;
    overflow: hidden;
    user-select: none;
    -webkit-app-region: drag;
  }

  .widget {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 16px;
    border-radius: 24px;
    background: rgba(24, 24, 27, 0.85);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    cursor: pointer;
    transition: all 0.2s ease;
    min-width: 40px;
    min-height: 40px;
    justify-content: center;
    -webkit-app-region: no-drag;
  }

  .widget:hover {
    background: rgba(24, 24, 27, 0.95);
    border-color: rgba(255, 255, 255, 0.15);
  }

  .widget.recording {
    background: rgba(220, 38, 38, 0.15);
    border-color: rgba(220, 38, 38, 0.4);
  }

  .indicator {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: #71717a;
    transition: background 0.2s ease;
    flex-shrink: 0;
  }

  .indicator.pulse {
    background: #ef4444;
    animation: pulse 1.5s ease-in-out infinite;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.5); }
    50% { opacity: 0.7; box-shadow: 0 0 0 8px rgba(239, 68, 68, 0); }
  }

  .time {
    font-family: 'JetBrains Mono', 'SF Mono', monospace;
    font-size: 14px;
    color: #ef4444;
    font-variant-numeric: tabular-nums;
    letter-spacing: 0.05em;
  }
</style>
