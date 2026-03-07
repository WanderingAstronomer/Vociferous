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
    import { Mic, Square, Copy, Check, Pencil, Trash2, Save, Undo2, Loader2, Sparkles, Home } from "lucide-svelte";
    import { nav } from "../lib/navigation.svelte";
    import WorkspacePanel from "../lib/components/WorkspacePanel.svelte";
    import StyledButton from "../lib/components/StyledButton.svelte";
    import BarSpectrumVisualizer from "../lib/components/BarSpectrumVisualizer.svelte";
    import ActivityHeatmap from "../lib/components/ActivityHeatmap.svelte";
    import { formatDuration, formatWpm } from "../lib/formatters";
    import { Tag as TagIcon } from "lucide-svelte";
    import {
        deleteTranscript as apiDeleteTranscript,
        dispatchIntent,
        getConfig,
        getHealth,
        getTranscript,
        getTranscripts,
        getMotd,
        getTags,
        assignTags,
    } from "../lib/api";
    import type { Transcript, Tag } from "../lib/api";

    type WorkspaceState = "idle" | "recording" | "transcribing" | "ready" | "viewing" | "editing";

    let viewState = $state<WorkspaceState>("idle");
    let transcriptText = $state("");
    let editText = $state("");
    let transcriptId = $state<number | null>(null);
    let transcriptTitle = $state("");
    let transcriptTimestamp = $state("");
    let durationMs = $state(0);
    let speechDurationMs = $state(0);
    let copied = $state(false);
    let refinementEnabled = $state(true);

    /* ===== Quick-tag state ===== */
    let allTags = $state<Tag[]>([]);
    let assignedTagIds = $state<Set<number>>(new Set());

    function loadTags() {
        getTags()
            .then((tags) => (allTags = tags))
            .catch(() => {});
    }

    async function toggleTag(tagId: number) {
        if (transcriptId == null) return;
        const next = new Set(assignedTagIds);
        if (next.has(tagId)) next.delete(tagId);
        else next.add(tagId);
        assignedTagIds = next;
        try {
            await assignTags(transcriptId, [...next]);
        } catch {
            // revert on failure
            const reverted = new Set(assignedTagIds);
            if (reverted.has(tagId)) reverted.delete(tagId);
            else reverted.add(tagId);
            assignedTagIds = reverted;
        }
    }

    let visualizerRef: BarSpectrumVisualizer | undefined = $state();

    /* ===== SLM insight (header subtitle) ===== */
    let slmInsight = $state("");

    /* ===== Recent sessions (idle panel) ===== */
    let recentSessions = $state<Transcript[]>([]);

    // Recording timer
    let recordingElapsedMs = $state(0);
    let recordingTimerInterval: ReturnType<typeof setInterval> | null = null;

    function startRecordingTimer() {
        recordingElapsedMs = 0;
        recordingTimerInterval = setInterval(() => {
            recordingElapsedMs += 1000;
        }, 1000);
    }

    function stopRecordingTimer() {
        if (recordingTimerInterval !== null) {
            clearInterval(recordingTimerInterval);
            recordingTimerInterval = null;
        }
    }

    function formatElapsed(ms: number): string {
        const totalSec = Math.floor(ms / 1000);
        const m = Math.floor(totalSec / 60);
        const s = totalSec % 60;
        return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
    }

    function loadRecentSessions() {
        getTranscripts({ limit: 500 })
            .then((r) => (recentSessions = r.items))
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
        const todayStr = new Date().toLocaleDateString("sv");
        const wordsPerSession = recentSessions.map(
            (t) => (t.text || t.normalized_text || "").split(/\s+/).filter(Boolean).length,
        );
        const todayWords = recentSessions
            .filter((t) => {
                const ca = t.created_at;
                return ca ? new Date(ca).toLocaleDateString("sv") === todayStr : false;
            })
            .reduce((sum, t) => sum + (t.text || t.normalized_text || "").split(/\s+/).filter(Boolean).length, 0);
        const totalSpeechMs = recentSessions.reduce((s, t) => s + (t.speech_duration_ms ?? 0), 0);
        const avgWpm =
            totalSpeechMs > 0 ? Math.round(wordsPerSession.reduce((a, b) => a + b, 0) / (totalSpeechMs / 60000)) : 0;
        return { todayWords, avgWpm, count: recentSessions.length };
    });

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
            transcriptTitle = t.display_name || "";
            transcriptTimestamp = formatTranscriptTimestamp(t.created_at || t.timestamp || "");
            durationMs = t.duration_ms ?? 0;
            speechDurationMs = t.speech_duration_ms ?? 0;
            assignedTagIds = new Set((t.tags ?? []).map((tag: Tag) => tag.id));
            if (mode === "edit") {
                if (!nav.isNavigationLocked) {
                    nav.beginEditSession({ view: "transcribe", transcriptId: t.id });
                }
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
        loadTags();
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
                transcriptTitle = "";
                transcriptTimestamp = "";
                durationMs = 0;
                speechDurationMs = 0;
                startRecordingTimer();
            }),
            ws.on("recording_stopped", (data) => {
                stopRecordingTimer();
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
                assignedTagIds = new Set();
                loadRecentSessions();
                /* Title generated async by SLM — will arrive via transcript_updated */
                transcriptTitle = "";
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
            ws.on("transcript_updated", async (data: any) => {
                if (data.id != null && data.id === transcriptId) {
                    try {
                        const t = await getTranscript(data.id);
                        transcriptTitle = t.display_name || "";
                        assignedTagIds = new Set((t.tags ?? []).map((tag: Tag) => tag.id));
                    } catch {
                        /* title fetch failed — not critical */
                    }
                }
            }),
            ws.on("tag_created", () => loadTags()),
            ws.on("tag_updated", () => loadTags()),
            ws.on("tag_deleted", (data) => {
                loadTags();
                assignedTagIds = new Set([...assignedTagIds].filter((id) => id !== data.id));
            }),
        ];
        return () => unsubs.forEach((fn) => fn());
    });

    $effect(() => {
        if (nav.current !== "transcribe") return;
        loadRecentSessions();
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
        transcriptTitle = "";
        transcriptTimestamp = "";
        durationMs = 0;
        speechDurationMs = 0;
        ws.send("start_recording");
    }

    function goToRefine() {
        if (transcriptId == null) return;
        nav.navigate("refine", transcriptId);
    }

    function returnToDashboard() {
        transcriptText = "";
        transcriptId = null;
        transcriptTitle = "";
        transcriptTimestamp = "";
        durationMs = 0;
        speechDurationMs = 0;
        viewState = "idle";
    }
</script>

<div class="flex flex-col h-full p-[var(--space-4)] gap-[var(--minor-gap)]">
    <!-- Header -->
    <div class="shrink-0 py-[var(--space-1)]">
        {#if viewState === "idle"}
            <div class="flex flex-col items-center text-center gap-[var(--space-1)]">
                <h1
                    class="text-3xl font-[var(--weight-emphasis)] text-[var(--accent)] m-0 leading-[var(--leading-tight)]"
                >
                    {greeting}
                </h1>
                {#if slmInsight}
                    <p
                        class="text-[var(--text-base)] text-[var(--text-secondary)] italic mb-0 leading-[var(--leading-normal)] opacity-85"
                    >
                        {slmInsight}
                    </p>
                {:else if !refinementEnabled}
                    <p class="text-[var(--text-sm)] text-[var(--text-tertiary)] mb-0">
                        Enable Grammar Refinement in Settings to unlock AI insights.
                    </p>
                {:else}
                    <p class="text-[var(--text-sm)] text-[var(--text-tertiary)] mb-0">
                        Click the mic button or use your hotkey to start recording
                    </p>
                {/if}
                <!-- Stats inline in header -->
                {#if sessionStats && sessionStats.count > 0}
                    <div class="flex items-center gap-[var(--space-4)] mt-[var(--space-1)]">
                        <span class="text-[var(--text-sm)] font-[var(--font-mono)] text-[var(--text-tertiary)]">
                            <span class="text-[var(--text-primary)] font-[var(--weight-emphasis)]"
                                >{sessionStats.todayWords.toLocaleString()}</span
                            > words today
                        </span>
                        <span class="w-px h-4 bg-[var(--shell-border)]"></span>
                        <span class="text-[var(--text-sm)] font-[var(--font-mono)] text-[var(--text-tertiary)]">
                            <span class="text-[var(--text-primary)] font-[var(--weight-emphasis)]"
                                >{sessionStats.avgWpm > 0 ? sessionStats.avgWpm : "\u2014"}</span
                            > wpm avg
                        </span>
                        <span class="w-px h-4 bg-[var(--shell-border)]"></span>
                        <span class="text-[var(--text-sm)] font-[var(--font-mono)] text-[var(--text-tertiary)]">
                            <span class="text-[var(--text-primary)] font-[var(--weight-emphasis)]"
                                >{sessionStats.count}</span
                            > sessions
                        </span>
                    </div>
                {/if}
            </div>
        {:else if viewState === "recording"}
            <!-- empty during recording — status lives in the action bar -->
        {:else if viewState === "transcribing"}
            <!-- empty during transcribing — spinner lives in the panel -->
        {:else}
            <div class="flex flex-col items-center text-center gap-0.5">
                {#if transcriptTitle}
                    <h2
                        class="text-xl font-[var(--weight-emphasis)] text-[var(--accent)] m-0 leading-[var(--leading-tight)]"
                    >
                        {transcriptTitle}
                    </h2>
                {/if}
                {#if transcriptTimestamp}
                    <span class="text-[var(--text-sm)] text-[var(--text-tertiary)] font-[var(--font-mono)]">
                        {transcriptTimestamp}
                    </span>
                {/if}
            </div>
        {/if}
    </div>

    <!-- Metrics strip (visible when transcript loaded) -->
    {#if hasText && durationMs > 0}
        {@const speechPct = durationMs > 0 ? Math.round((speechDurationMs / durationMs) * 100) : 0}
        <div
            class="flex items-center justify-center gap-[var(--space-3)] py-[var(--space-2)] px-[var(--space-3)] bg-[var(--surface-primary)] rounded-[var(--radius-sm)] shrink-0"
        >
            <span class="text-[var(--text-sm)] text-[var(--text-tertiary)]">
                <span class="font-[var(--weight-emphasis)] font-[var(--font-mono)] text-[var(--text-primary)]"
                    >{formatDuration(durationMs)}</span
                > Duration
            </span>
            <span class="w-px h-4 bg-[var(--shell-border)]"></span>
            <span class="text-[var(--text-sm)] text-[var(--text-tertiary)]">
                <span class="font-[var(--weight-emphasis)] font-[var(--font-mono)] text-[var(--text-primary)]"
                    >{formatDuration(speechDurationMs)}</span
                > Speech
            </span>
            <span class="w-px h-4 bg-[var(--shell-border)]"></span>
            <span class="text-[var(--text-sm)] text-[var(--text-tertiary)]">
                <span class="font-[var(--weight-emphasis)] font-[var(--font-mono)] text-[var(--text-primary)]"
                    >{wordCount}</span
                > Words
            </span>
            <span class="w-px h-4 bg-[var(--shell-border)]"></span>
            <span class="text-[var(--text-sm)] text-[var(--text-tertiary)]">
                <span class="font-[var(--weight-emphasis)] font-[var(--font-mono)] text-[var(--text-primary)]"
                    >{formatWpm(wordCount, speechDurationMs || durationMs)}</span
                > Pace
            </span>
            <span class="w-px h-4 bg-[var(--shell-border)]"></span>
            <!-- Active Speech bar -->
            <div class="flex items-center gap-[var(--space-2)] min-w-[100px] max-w-[280px] flex-1">
                <span class="text-[var(--text-sm)] text-[var(--text-tertiary)] shrink-0">Active Speech</span>
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
    {/if}

    <!-- Quick-tag strip (visible when a transcript is loaded) -->
    {#if transcriptId != null && allTags.length > 0 && (viewState === "ready" || viewState === "viewing")}
        <div class="flex items-center gap-[var(--space-1)] py-[var(--space-1)] px-[var(--space-1)] shrink-0 flex-wrap">
            <TagIcon size={14} class="text-[var(--text-tertiary)] shrink-0 mr-1" />
            {#each allTags as tag (tag.id)}
                {@const active = assignedTagIds.has(tag.id)}
                <button
                    class="inline-flex items-center gap-1 h-6 px-2 rounded-full text-[var(--text-xs)] font-[var(--weight-emphasis)] border cursor-pointer transition-all duration-150 {active
                        ? 'border-transparent text-white'
                        : 'border-[var(--shell-border)] text-[var(--text-secondary)] bg-transparent hover:bg-[var(--hover-overlay)]'}"
                    style={active && tag.color ? `background: ${tag.color}` : active ? "background: var(--accent)" : ""}
                    onclick={() => toggleTag(tag.id)}
                    title={active ? `Remove "${tag.name}" tag` : `Add "${tag.name}" tag`}
                >
                    {tag.name}
                </button>
            {/each}
        </div>
    {/if}

    <!-- Content panel -->
    <WorkspacePanel editing={viewState === "editing"} recording={isRecording || isTranscribing}>
        <!-- IDLE: mic CTA centered, heatmap anchored to bottom -->
        {#if viewState === "idle"}
            <div class="flex-1 flex flex-col min-h-0">
                <!-- Upper zone: mic CTA, vertically centered -->
                <div class="flex-1 flex flex-col items-center justify-center">
                    <div class="flex flex-col items-center justify-center gap-[var(--space-4)]">
                        <button
                            class="w-[160px] h-[160px] rounded-full border-2 border-[var(--accent)] bg-transparent text-[var(--accent)] cursor-pointer flex items-center justify-center transition-[background,border-color,color] duration-[var(--transition-fast)] hover:bg-[var(--hover-overlay-blue)] hover:border-[var(--accent-hover)] hover:text-[var(--accent-hover)]"
                            onclick={startRecording}
                            aria-label="Start recording"
                            title="Start recording"
                        >
                            <Mic size={56} strokeWidth={1.5} />
                        </button>
                        <p class="text-[var(--text-base)] text-[var(--text-tertiary)] m-0">Click to record</p>
                    </div>
                </div>

                <!-- Lower zone: activity heatmap -->
                {#if recentSessions.length > 0}
                    <div class="shrink-0 flex flex-col gap-[var(--space-2)] px-[var(--space-1)]">
                        <ActivityHeatmap entries={recentSessions} />
                    </div>
                {/if}
            </div>

            <!-- RECORDING: spectrum fills the full panel, flush to bottom -->
        {:else if viewState === "recording"}
            <div class="flex-1 flex flex-col">
                <!-- Spectrum fills all available space, flush to bottom edge of panel -->
                <div class="flex-1 min-h-[120px]">
                    <BarSpectrumVisualizer bind:this={visualizerRef} active={isRecording} numBars={64} />
                </div>
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
                <!-- Cancel left, status+timer centered, Stop right -->
                <button
                    class="inline-flex items-center gap-1.5 h-9 px-[var(--space-3)] border border-[var(--color-danger)] rounded-[var(--radius-sm)] bg-transparent text-[var(--color-danger)] cursor-pointer whitespace-nowrap transition-[background,color] duration-[var(--transition-fast)] hover:bg-[var(--color-danger-surface)]"
                    onclick={cancelRecording}
                    aria-label="Cancel recording and discard audio"
                    title="Cancel recording and discard captured audio"
                >
                    <Trash2 size={15} /> Cancel
                </button>
                <div class="flex-1 flex items-center justify-center gap-[var(--space-2)]">
                    <span
                        class="w-2 h-2 rounded-full bg-[var(--color-danger)] shrink-0 animate-[pulse-dot_1.2s_ease-in-out_infinite]"
                    ></span>
                    <span class="text-[var(--text-sm)] text-[var(--color-danger)]">Recording in progress…</span>
                    <span class="w-px h-4 bg-[var(--shell-border)]"></span>
                    <span class="text-[var(--text-sm)] font-[var(--font-mono)] text-[var(--text-tertiary)] tabular-nums"
                        >{formatElapsed(recordingElapsedMs)}</span
                    >
                </div>
                <button
                    class="inline-flex items-center gap-1.5 h-9 px-[var(--space-3)] border-none rounded-[var(--radius-sm)] bg-[var(--accent)] text-[var(--gray-0)] cursor-pointer whitespace-nowrap transition-[background,color] duration-[var(--transition-fast)] hover:bg-[var(--accent-hover)]"
                    onclick={stopRecording}
                    aria-label="Stop recording and transcribe"
                    title="Stop recording and transcribe audio"
                >
                    <Square size={15} fill="currentColor" /> Stop & Transcribe
                </button>
            {:else if viewState === "editing"}
                <StyledButton variant="ghost" size="sm" onclick={discardEdits}>
                    <Undo2 size={14} /> Discard
                </StyledButton>
                <div class="flex-1"></div>
                <StyledButton variant="primary" size="sm" onclick={commitEdits}>
                    <Save size={14} /> Save
                </StyledButton>
            {:else}
                <!-- READY / VIEWING: destructive → creative, left → right -->
                <StyledButton variant="destructive" size="sm" onclick={deleteTranscript}>
                    <Trash2 size={14} /> Delete
                </StyledButton>
                <StyledButton variant="ghost" size="sm" onclick={enterEditMode}>
                    <Pencil size={14} /> Edit
                </StyledButton>
                <StyledButton variant="secondary" size="sm" onclick={copyToClipboard}>
                    {#if copied}
                        <Check size={14} /> Copied
                    {:else}
                        <Copy size={14} /> Copy
                    {/if}
                </StyledButton>

                <div class="flex-1"></div>

                {#if refinementEnabled}
                    <StyledButton variant="ghost" size="sm" onclick={goToRefine} disabled={transcriptId == null}>
                        <Sparkles size={14} /> Refine
                    </StyledButton>
                {/if}
                <StyledButton variant="ghost" size="sm" onclick={returnToDashboard}>
                    <Home size={14} /> Dashboard
                </StyledButton>
                <StyledButton variant="primary" size="sm" onclick={startNewRecording}>
                    <Mic size={14} /> New Recording
                </StyledButton>
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
