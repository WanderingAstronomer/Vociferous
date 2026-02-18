<script lang="ts">
    /**
     * TranscribeView — State-driven transcription workspace.
     *
     * States (matching old PyQt6 WorkspaceState):
     *   IDLE         — Welcome greeting, ready to record
     *   RECORDING    — Active recording with spectrum visualizer
     *   TRANSCRIBING — Processing audio, spinner shown
     *   READY        — Fresh transcript just arrived
     *   VIEWING      — Viewing a transcript
     *   EDITING      — Editing transcript text
     */

    import { ws } from "../lib/ws";
    import { onMount } from "svelte";
    import { Mic, Square, Copy, Check, Pencil, Trash2, Save, Undo2, Loader2, Sparkles } from "lucide-svelte";
    import { nav } from "../lib/navigation.svelte";
    import WorkspacePanel from "../lib/components/WorkspacePanel.svelte";
    import BarSpectrumVisualizer from "../lib/components/BarSpectrumVisualizer.svelte";
    import {
        deleteTranscript as apiDeleteTranscript,
        dispatchIntent,
        getConfig,
        getHealth,
        getTranscript,
        getTranscripts,
        getMotd,
    } from "../lib/api";
    import type { Transcript } from "../lib/api";

    type WorkspaceState = "idle" | "recording" | "transcribing" | "ready" | "viewing" | "editing";

    let viewState = $state<WorkspaceState>("idle");
    let transcriptText = $state("");
    let editText = $state("");
    let transcriptId = $state<number | null>(null);
    let transcriptTimestamp = $state("");
    let durationMs = $state(0);
    let speechDurationMs = $state(0);
    let copied = $state(false);
    let refinementEnabled = $state(true);

    let visualizerRef: BarSpectrumVisualizer | undefined = $state();

    /* ===== SLM insight (header subtitle) ===== */
    let slmInsight = $state("");

    /* ===== Recent sessions (idle panel) ===== */
    let recentSessions = $state<Transcript[]>([]);

    function loadRecentSessions() {
        getTranscripts(20)
            .then((t) => (recentSessions = t))
            .catch(() => {});
    }

    /* ===== Derived state ===== */
    let wordCount = $derived(
        viewState !== "idle"
            ? (viewState === "editing" ? editText : transcriptText).split(/\s+/).filter(Boolean).length
            : 0,
    );
    let isRecording = $derived(viewState === "recording");
    let isTranscribing = $derived(viewState === "transcribing");
    let hasText = $derived(Boolean(transcriptText) && viewState !== "idle");

    /* ===== Greeting ===== */
    let greeting = $derived.by(() => {
        const hour = new Date().getHours();
        if (hour < 12) return "Good morning";
        if (hour < 17) return "Good afternoon";
        return "Good evening";
    });

    /* ===== Recent session analytics (idle panel) ===== */
    let sessionStats = $derived.by(() => {
        if (!recentSessions.length) return null;
        const todayStr = new Date().toISOString().slice(0, 10);
        const wordsPerSession = recentSessions.map(
            (t) => (t.text || t.normalized_text || "").split(/\s+/).filter(Boolean).length,
        );
        const todayWords = recentSessions
            .filter((t) => (t.created_at || "").slice(0, 10) === todayStr)
            .reduce((sum, t) => sum + (t.text || t.normalized_text || "").split(/\s+/).filter(Boolean).length, 0);
        const totalDurationMs = recentSessions.reduce((s, t) => s + (t.duration_ms ?? 0), 0);
        const totalSpeechMs = recentSessions.reduce((s, t) => s + (t.speech_duration_ms ?? 0), 0);
        const avgWpm =
            totalSpeechMs > 0 ? Math.round(wordsPerSession.reduce((a, b) => a + b, 0) / (totalSpeechMs / 60000)) : 0;
        // Build sparkline bars for up to last 14 sessions, oldest→newest
        const sparkData = [...recentSessions].reverse().slice(-14);
        const sparkWords = sparkData.map(
            (t) => (t.text || t.normalized_text || "").split(/\s+/).filter(Boolean).length,
        );
        const sparkMax = Math.max(...sparkWords, 1);
        return { todayWords, avgWpm, sparkWords, sparkMax, count: recentSessions.length };
    });

    /* ===== Metrics formatting ===== */
    function formatDuration(ms: number): string {
        if (ms <= 0) return "—";
        const secs = Math.round(ms / 1000);
        const m = Math.floor(secs / 60);
        const s = secs % 60;
        return m > 0 ? `${m}m ${s}s` : `${s}s`;
    }

    function formatWpm(words: number, ms: number): string {
        if (ms <= 0 || words <= 0) return "—";
        const minutes = ms / 60000;
        return `${Math.round(words / minutes)} wpm`;
    }

    function formatTranscriptTimestamp(iso: string): string {
        if (!iso) return "";
        const dt = new Date(iso);
        return dt.toLocaleString("en-US", {
            month: "short",
            day: "numeric",
            hour: "numeric",
            minute: "2-digit",
        });
    }

    async function openTranscript(id: number, mode: "view" | "edit" = "view"): Promise<void> {
        try {
            const t = await getTranscript(id);
            transcriptText = t.text || t.normalized_text || t.raw_text || "";
            transcriptId = t.id;
            transcriptTimestamp = formatTranscriptTimestamp(t.created_at || t.timestamp || "");
            durationMs = t.duration_ms ?? 0;
            speechDurationMs = t.speech_duration_ms ?? 0;
            if (mode === "edit") {
                nav.beginEditSession();
                editText = transcriptText;
                viewState = "editing";
            } else {
                viewState = "viewing";
            }
        } catch (e) {
            console.error("Failed to open transcript:", e);
        }
    }

    /* ===== WebSocket handlers ===== */
    onMount(() => {
        getConfig()
            .then((config) => {
                refinementEnabled = (config as any)?.refinement?.enabled ?? true;
            })
            .catch(() => {});

        loadRecentSessions();
        getMotd()
            .then((res) => {
                slmInsight = res.text || "";
            })
            .catch(() => {});
        getHealth()
            .then((health) => {
                if (health.recording_active) {
                    viewState = "recording";
                }
            })
            .catch(() => {
                /* no-op */
            });

        const unsubs = [
            ws.on("recording_started", () => {
                viewState = "recording";
                transcriptText = "";
                transcriptId = null;
                transcriptTimestamp = "";
                durationMs = 0;
                speechDurationMs = 0;
            }),
            ws.on("recording_stopped", (data) => {
                visualizerRef?.reset();
                if (data.cancelled) {
                    viewState = "idle";
                } else {
                    viewState = "transcribing";
                }
            }),
            ws.on("transcription_complete", (data) => {
                transcriptText = data.text;
                transcriptId = data.id;
                durationMs = data.duration_ms ?? 0;
                speechDurationMs = data.speech_duration_ms ?? 0;
                viewState = "ready";
                loadRecentSessions();
            }),
            ws.on("transcription_error", (data) => {
                transcriptText = `Error: ${data.message}`;
                viewState = "ready";
            }),
            ws.on("motd_ready", (data: any) => {
                slmInsight = data.text || "";
            }),
            ws.on("audio_spectrum", (data) => {
                if (viewState === "recording" && visualizerRef) {
                    visualizerRef.addSpectrum(data.bands);
                }
            }),
            ws.on("config_updated", (data) => {
                const refinement = (data as any)?.refinement;
                if (typeof refinement === "object" && refinement !== null && "enabled" in refinement) {
                    refinementEnabled = Boolean((refinement as any).enabled);
                }
            }),
        ];
        return () => unsubs.forEach((fn) => fn());
    });

    $effect(() => {
        if (nav.current !== "transcribe") return;
        const pendingRequest = nav.consumePendingTranscriptRequest();
        if (pendingRequest != null) {
            void openTranscript(pendingRequest.id, pendingRequest.mode);
        }
    });

    /* ===== Actions ===== */
    function startRecording() {
        ws.send("start_recording");
    }

    function stopRecording() {
        ws.send("stop_recording");
    }

    function cancelRecording() {
        ws.send("cancel_recording");
    }

    function toggleRecording() {
        if (isRecording) stopRecording();
        else startRecording();
    }

    function copyToClipboard() {
        const text = viewState === "editing" ? editText : transcriptText;
        if (text) {
            navigator.clipboard.writeText(text);
            copied = true;
            setTimeout(() => (copied = false), 1500);
        }
    }

    function enterEditMode() {
        if (!hasText || isRecording || isTranscribing) return;
        nav.beginEditSession();
        editText = transcriptText;
        viewState = "editing";
    }

    function commitEdits() {
        if (!transcriptId || !editText.trim()) return;
        dispatchIntent("commit_edits", {
            transcript_id: transcriptId,
            content: editText.trim(),
        })
            .then(() => {
                transcriptText = editText;
                viewState = "viewing";
                nav.completeEditSession();
            })
            .catch((e) => console.error("Failed to save edits:", e));
    }

    function discardEdits() {
        editText = "";
        viewState = "viewing";
        nav.completeEditSession();
    }

    async function deleteTranscript() {
        if (transcriptId == null) return;
        try {
            await apiDeleteTranscript(transcriptId);
            transcriptText = "";
            transcriptId = null;
            viewState = "idle";
        } catch (e) {
            console.error("Failed to delete transcript:", e);
        }
    }

    function startNewRecording() {
        transcriptText = "";
        transcriptId = null;
        transcriptTimestamp = "";
        durationMs = 0;
        speechDurationMs = 0;
        ws.send("start_recording");
    }

    function goToRefine() {
        if (transcriptId == null) return;
        nav.navigate("refine", transcriptId);
    }
</script>

<div class="flex flex-col h-full p-[var(--space-4)] gap-[var(--minor-gap)]">
    <!-- Header -->
    <div class="shrink-0 py-[var(--space-1)]">
        {#if viewState === "idle"}
            <div class="flex flex-col items-center text-center">
                <h1
                    class="text-[var(--text-xl)] font-[var(--weight-emphasis)] text-[var(--text-primary)] m-0 leading-[var(--leading-tight)]"
                >
                    {greeting}
                </h1>
                {#if slmInsight}
                    <p
                        class="text-[var(--text-base)] text-[var(--accent)] italic mt-[var(--space-1)] mb-0 leading-[var(--leading-normal)] opacity-85"
                    >
                        {slmInsight}
                    </p>
                {:else}
                    <p class="text-[var(--text-sm)] text-[var(--text-tertiary)] mt-[var(--space-0)] mb-0">
                        Click the mic button or use your hotkey to start recording
                    </p>
                {/if}
            </div>
        {:else if viewState === "recording"}
            <div class="flex items-center gap-[var(--space-1)] text-[var(--text-base)] text-[var(--color-danger)]">
                <span
                    class="w-2 h-2 rounded-full bg-[var(--color-danger)] animate-[pulse-dot_1.2s_ease-in-out_infinite]"
                ></span>
                <span>Recording in progress…</span>
            </div>
        {:else if viewState === "transcribing"}
            <div class="flex items-center gap-[var(--space-1)] text-[var(--text-base)] text-[var(--text-secondary)]">
                <Loader2 size={18} class="spin" />
                <span>Transcribing…</span>
            </div>
        {:else}
            <div class="flex items-center gap-[var(--space-1)] text-[var(--text-base)] text-[var(--text-secondary)]">
                <span class="font-[var(--font-mono)] text-[var(--text-sm)] text-[var(--text-tertiary)]"
                    >{transcriptTimestamp || "Transcript"}</span
                >
            </div>
        {/if}
    </div>

    <!-- Metrics strip (visible when transcript loaded) -->
    {#if hasText && durationMs > 0}
        {@const speechPct = durationMs > 0 ? Math.round((speechDurationMs / durationMs) * 100) : 0}
        <div
            class="flex items-center gap-[var(--space-2)] py-[var(--space-1)] px-[var(--space-2)] bg-[var(--surface-primary)] rounded-[var(--radius-sm)] shrink-0"
        >
            <div class="flex flex-col gap-0.5">
                <span class="text-[var(--text-xs)] text-[var(--text-tertiary)] uppercase tracking-wider">Duration</span>
                <span
                    class="text-[var(--text-sm)] font-[var(--weight-emphasis)] text-[var(--text-primary)] font-[var(--font-mono)]"
                    >{formatDuration(durationMs)}</span
                >
            </div>
            <div class="w-px h-6 bg-[var(--shell-border)] mx-[var(--space-1)]"></div>
            <div class="flex flex-col gap-0.5">
                <span class="text-[var(--text-xs)] text-[var(--text-tertiary)] uppercase tracking-wider">Speech</span>
                <span
                    class="text-[var(--text-sm)] font-[var(--weight-emphasis)] text-[var(--text-primary)] font-[var(--font-mono)]"
                    >{formatDuration(speechDurationMs)}</span
                >
            </div>
            <div class="w-px h-6 bg-[var(--shell-border)] mx-[var(--space-1)]"></div>
            <div class="flex flex-col gap-0.5">
                <span class="text-[var(--text-xs)] text-[var(--text-tertiary)] uppercase tracking-wider">Words</span>
                <span
                    class="text-[var(--text-sm)] font-[var(--weight-emphasis)] text-[var(--text-primary)] font-[var(--font-mono)]"
                    >{wordCount}</span
                >
            </div>
            <div class="w-px h-6 bg-[var(--shell-border)] mx-[var(--space-1)]"></div>
            <div class="flex flex-col gap-0.5">
                <span class="text-[var(--text-xs)] text-[var(--text-tertiary)] uppercase tracking-wider">Pace</span>
                <span
                    class="text-[var(--text-sm)] font-[var(--weight-emphasis)] text-[var(--text-primary)] font-[var(--font-mono)]"
                    >{formatWpm(wordCount, speechDurationMs || durationMs)}</span
                >
            </div>
            <div class="w-px h-6 bg-[var(--shell-border)] mx-[var(--space-1)]"></div>
            <!-- Speech ratio bar -->
            <div class="flex flex-col gap-1 flex-1 min-w-[80px] max-w-[160px]">
                <span class="text-[var(--text-xs)] text-[var(--text-tertiary)] uppercase tracking-wider"
                    >Speech Ratio</span
                >
                <div class="flex items-center gap-[var(--space-1)]">
                    <div class="flex-1 h-1.5 rounded-full bg-[var(--surface-tertiary)] overflow-hidden">
                        <div
                            class="h-full rounded-full bg-[var(--accent)] transition-[width] duration-500"
                            style="width: {speechPct}%"
                        ></div>
                    </div>
                    <span class="text-[var(--text-xs)] font-[var(--font-mono)] text-[var(--text-tertiary)] shrink-0"
                        >{speechPct}%</span
                    >
                </div>
            </div>
        </div>
    {/if}

    <!-- Content panel -->
    <WorkspacePanel editing={viewState === "editing"} recording={isRecording || isTranscribing}>
        <!-- IDLE: mic CTA top, session analytics below -->
        {#if viewState === "idle"}
            <div class="flex-1 flex items-center justify-center min-h-0 overflow-y-auto">
                <div
                    class="flex flex-col items-center gap-[var(--space-6)] w-full max-w-[560px] py-[var(--space-6)] px-[var(--space-5)]"
                >
                    <!-- Record CTA -->
                    <div class="flex flex-col items-center justify-center gap-[var(--space-3)]">
                        <button
                            class="w-[88px] h-[88px] rounded-full border-2 border-[var(--accent)] bg-transparent text-[var(--accent)] cursor-pointer flex items-center justify-center transition-[background,border-color,color] duration-[var(--transition-fast)] hover:bg-[var(--hover-overlay-blue)] hover:border-[var(--accent-hover)] hover:text-[var(--accent-hover)]"
                            onclick={startRecording}
                            aria-label="Start recording"
                            title="Start recording"
                        >
                            <Mic size={32} strokeWidth={1.5} />
                        </button>
                        <p class="text-[var(--text-sm)] text-[var(--text-tertiary)] m-0">Click to record</p>
                    </div>

                    <!-- Session analytics -->
                    <div class="flex flex-col gap-[var(--space-4)] w-full">
                        {#if sessionStats && sessionStats.count > 0}
                            <!-- Divider -->
                            <div class="h-px w-full bg-[var(--shell-border)]"></div>

                            <!-- Quick stats row -->
                            <div class="flex justify-center gap-[var(--space-5)]">
                                <div class="flex flex-col items-center gap-0.5">
                                    <span
                                        class="text-[var(--text-xs)] text-[var(--text-tertiary)] uppercase tracking-wider"
                                        >Today</span
                                    >
                                    <span
                                        class="text-[var(--text-lg)] font-[var(--weight-emphasis)] text-[var(--text-primary)] font-[var(--font-mono)] leading-none"
                                    >
                                        {sessionStats.todayWords.toLocaleString()}
                                        <span class="text-[var(--text-xs)] font-normal text-[var(--text-tertiary)]"
                                            >words</span
                                        >
                                    </span>
                                </div>
                                <div class="w-px bg-[var(--shell-border)] self-stretch"></div>
                                <div class="flex flex-col items-center gap-0.5">
                                    <span
                                        class="text-[var(--text-xs)] text-[var(--text-tertiary)] uppercase tracking-wider"
                                        >Avg Pace</span
                                    >
                                    <span
                                        class="text-[var(--text-lg)] font-[var(--weight-emphasis)] text-[var(--text-primary)] font-[var(--font-mono)] leading-none"
                                    >
                                        {sessionStats.avgWpm > 0 ? sessionStats.avgWpm : "—"}
                                        <span class="text-[var(--text-xs)] font-normal text-[var(--text-tertiary)]"
                                            >wpm</span
                                        >
                                    </span>
                                </div>
                                <div class="w-px bg-[var(--shell-border)] self-stretch"></div>
                                <div class="flex flex-col items-center gap-0.5">
                                    <span
                                        class="text-[var(--text-xs)] text-[var(--text-tertiary)] uppercase tracking-wider"
                                        >Sessions</span
                                    >
                                    <span
                                        class="text-[var(--text-lg)] font-[var(--weight-emphasis)] text-[var(--text-primary)] font-[var(--font-mono)] leading-none"
                                    >
                                        {sessionStats.count}
                                    </span>
                                </div>
                            </div>

                            <!-- Sparkline: word counts per recent session -->
                            <div class="flex flex-col gap-[var(--space-1)]">
                                <span class="text-[var(--text-xs)] text-[var(--text-tertiary)] uppercase tracking-wider"
                                    >Recent Sessions</span
                                >
                                <div class="flex items-end gap-[3px] h-[52px]">
                                    {#each sessionStats.sparkWords as w, i}
                                        {@const pct = Math.max(4, Math.round((w / sessionStats.sparkMax) * 100))}
                                        {@const isLatest = i === sessionStats.sparkWords.length - 1}
                                        <div
                                            class="flex-1 rounded-t-[2px] transition-[height] duration-300 {isLatest
                                                ? 'bg-[var(--accent)]'
                                                : 'bg-[var(--text-tertiary)] opacity-40'}"
                                            style="height: {pct}%"
                                            title="{w} words"
                                        ></div>
                                    {/each}
                                </div>
                            </div>
                        {/if}
                    </div>
                </div>
            </div>

            <!-- RECORDING: visualizer + stop -->
        {:else if viewState === "recording"}
            <div class="flex-1 flex flex-col gap-[var(--space-3)]">
                <div class="flex-1 min-h-[120px]">
                    <BarSpectrumVisualizer bind:this={visualizerRef} active={isRecording} numBars={64} />
                </div>
                <div class="self-center flex items-center gap-[var(--space-1)] shrink-0">
                    <button
                        class="inline-flex items-center gap-1.5 h-10 px-[var(--space-2)] border border-[var(--color-danger)] rounded-[var(--radius-sm)] bg-transparent text-[var(--color-danger)] cursor-pointer whitespace-nowrap transition-[background,color] duration-[var(--transition-fast)] hover:bg-[var(--color-danger-surface)]"
                        onclick={cancelRecording}
                        aria-label="Cancel recording and discard audio"
                        title="Cancel recording and discard captured audio"
                    >
                        <Trash2 size={16} /> Cancel (Discard)
                    </button>
                    <button
                        class="inline-flex items-center gap-1.5 h-10 px-[var(--space-2)] border border-[var(--shell-border)] rounded-[var(--radius-sm)] bg-[var(--surface-primary)] text-[var(--text-primary)] cursor-pointer whitespace-nowrap transition-[background,color] duration-[var(--transition-fast)] hover:bg-[var(--surface-tertiary)]"
                        onclick={stopRecording}
                        aria-label="Stop recording and transcribe"
                        title="Stop recording and transcribe audio"
                    >
                        <Square size={16} fill="currentColor" /> Stop & Transcribe
                    </button>
                </div>
                <p class="self-center text-[var(--text-xs)] text-[var(--text-tertiary)] italic">
                    Cancel discards audio. Stop runs transcription.
                </p>
            </div>

            <!-- TRANSCRIBING: spinner -->
        {:else if viewState === "transcribing"}
            <div class="flex-1 flex flex-col items-center justify-center gap-[var(--space-3)]">
                <Loader2 size={40} strokeWidth={1.5} class="spin" />
                <p class="text-[var(--text-sm)] text-[var(--text-tertiary)]">Transcribing audio…</p>
            </div>

            <!-- EDITING: editable textarea -->
        {:else if viewState === "editing"}
            <div class="flex-1 overflow-y-auto">
                <textarea
                    class="w-full h-full min-h-[200px] bg-transparent text-[var(--text-primary)] border-none outline-none resize-none font-[var(--font-family)] text-[var(--text-base)] leading-[var(--leading-relaxed)] p-0 placeholder:text-[var(--text-tertiary)]"
                    bind:value={editText}
                    spellcheck="true"
                ></textarea>
            </div>

            <!-- READY / VIEWING: display transcript text -->
        {:else}
            <div class="flex-1 overflow-y-auto">
                <p
                    class="text-[var(--text-base)] leading-[var(--leading-relaxed)] text-[var(--text-primary)] whitespace-pre-wrap break-words m-0"
                >
                    {transcriptText}
                </p>
            </div>
        {/if}
    </WorkspacePanel>

    <!-- Action bar (below panel) -->
    {#if viewState !== "idle" && viewState !== "transcribing"}
        <div class="flex items-center gap-[var(--space-1)] py-[var(--space-1)] shrink-0">
            {#if viewState === "recording"}
                <!-- Recording: just the stop is in the panel -->
            {:else if viewState === "editing"}
                <button
                    class="inline-flex items-center gap-1.5 h-8 px-[var(--space-2)] border-none rounded-[var(--radius-sm)] font-[var(--font-family)] text-[var(--text-xs)] font-[var(--weight-emphasis)] cursor-pointer whitespace-nowrap transition-[background,color] duration-[var(--transition-fast)] bg-[var(--accent)] text-[var(--gray-0)] hover:bg-[var(--accent-hover)]"
                    onclick={commitEdits}
                    title="Save edits"
                >
                    <Save size={16} /> Save
                </button>
                <button
                    class="inline-flex items-center gap-1.5 h-8 px-[var(--space-2)] border-none rounded-[var(--radius-sm)] font-[var(--font-family)] text-[var(--text-xs)] font-[var(--weight-emphasis)] cursor-pointer whitespace-nowrap transition-[background,color] duration-[var(--transition-fast)] bg-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--hover-overlay)]"
                    onclick={discardEdits}
                    title="Discard edits"
                >
                    <Undo2 size={16} /> Discard
                </button>
            {:else}
                <!-- READY / VIEWING -->
                <button
                    class="inline-flex items-center gap-1.5 h-8 px-[var(--space-2)] border-none rounded-[var(--radius-sm)] font-[var(--font-family)] text-[var(--text-xs)] font-[var(--weight-emphasis)] cursor-pointer whitespace-nowrap transition-[background,color] duration-[var(--transition-fast)] bg-[var(--surface-tertiary)] text-[var(--text-primary)] hover:bg-[var(--gray-6)]"
                    onclick={copyToClipboard}
                    title="Copy to clipboard"
                >
                    {#if copied}
                        <Check size={16} /> Copied
                    {:else}
                        <Copy size={16} /> Copy
                    {/if}
                </button>
                <button
                    class="inline-flex items-center gap-1.5 h-8 px-[var(--space-2)] border-none rounded-[var(--radius-sm)] font-[var(--font-family)] text-[var(--text-xs)] font-[var(--weight-emphasis)] cursor-pointer whitespace-nowrap transition-[background,color] duration-[var(--transition-fast)] bg-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--hover-overlay)]"
                    onclick={enterEditMode}
                    title="Edit transcript"
                >
                    <Pencil size={16} /> Edit
                </button>
                <button
                    class="inline-flex items-center gap-1.5 h-8 px-[var(--space-2)] border-none rounded-[var(--radius-sm)] font-[var(--font-family)] text-[var(--text-xs)] font-[var(--weight-emphasis)] cursor-pointer whitespace-nowrap transition-[background,color] duration-[var(--transition-fast)] bg-transparent text-[var(--text-tertiary)] hover:text-[var(--color-danger)] hover:bg-[var(--color-danger-surface)]"
                    onclick={deleteTranscript}
                    title="Delete transcript"
                >
                    <Trash2 size={16} /> Delete
                </button>

                {#if refinementEnabled}
                    <button
                        class="inline-flex items-center gap-1.5 h-8 px-[var(--space-2)] border-none rounded-[var(--radius-sm)] font-[var(--font-family)] text-[var(--text-xs)] font-[var(--weight-emphasis)] cursor-pointer whitespace-nowrap transition-[background,color] duration-[var(--transition-fast)] bg-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--hover-overlay)]"
                        onclick={goToRefine}
                        title="Refine transcript"
                        disabled={transcriptId == null}
                    >
                        <Sparkles size={16} /> Refine
                    </button>
                {/if}

                <div class="flex-1"></div>

                <button
                    class="inline-flex items-center gap-1.5 h-8 px-[var(--space-2)] border-none rounded-[var(--radius-sm)] font-[var(--font-family)] text-[var(--text-xs)] font-[var(--weight-emphasis)] cursor-pointer whitespace-nowrap transition-[background,color] duration-[var(--transition-fast)] bg-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--hover-overlay)]"
                    onclick={startNewRecording}
                    title="New recording"
                >
                    <Mic size={16} /> New
                </button>
            {/if}
        </div>
    {/if}
</div>

<style>
    @keyframes pulse-dot {
        0%,
        100% {
            opacity: 1;
        }
        50% {
            opacity: 0.3;
        }
    }

    :global(.spin) {
        animation: spin 1.2s linear infinite;
    }

    @keyframes spin {
        from {
            transform: rotate(0deg);
        }
        to {
            transform: rotate(360deg);
        }
    }
</style>
