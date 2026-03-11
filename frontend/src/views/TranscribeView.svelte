<script lang="ts">
    /**
     * TranscribeView — State-driven transcription workspace.
     *
     * States:
     *   IDLE         — Welcome greeting, ready to record
     *   RECORDING    — Active recording with pulse animation
     *   TRANSCRIBING — Processing audio, spinner shown
     *   READY        — Fresh transcript just arrived
     *   VIEWING      — Viewing a transcript
     *   EDITING      — Editing transcript text
     */

    import { ws } from "../lib/ws";
    import { onMount } from "svelte";
    import RecordingControls from "../lib/components/RecordingControls.svelte";
    import {
        Mic,
        Copy,
        Check,
        Pencil,
        Trash2,
        Save,
        Undo2,
        Loader2,
        Sparkles,
        Home,
        X,
        FileAudio,
        RefreshCw,
    } from "lucide-svelte";
    import { nav } from "../lib/navigation.svelte";
    import WorkspacePanel from "../lib/components/WorkspacePanel.svelte";
    import MarkdownBody from "../lib/components/MarkdownBody.svelte";
    import StyledButton from "../lib/components/StyledButton.svelte";
    import ActivityHeatmap from "../lib/components/ActivityHeatmap.svelte";
    import { formatDuration, formatElapsed, formatWpm } from "../lib/formatters";
    import { Tag as TagIcon, Bookmark } from "lucide-svelte";
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
        createTag,
        deleteTag,
        updateTag,
        refineTranscript,
        commitRefinement,
        importAudioFile,
        retranscribeTranscript,
    } from "../lib/api";
    import { PlusCircle } from "lucide-svelte";
    import type { Transcript, Tag } from "../lib/api";
    import TagBar from "../lib/components/TagBar.svelte";
    import { toast } from "../lib/toast.svelte";

    type WorkspaceState = "idle" | "recording" | "transcribing" | "ready" | "viewing" | "editing";

    let viewState = $state<WorkspaceState>("idle");
    let transcriptText = $state("");
    let editText = $state("");
    let transcriptId = $state<number | null>(null);
    let transcriptTitle = $state("");
    let transcriptTimestamp = $state("");
    let durationMs = $state(0);
    let speechDurationMs = $state(0);
    let hasAudioCached = $state(false);
    let copied = $state(false);
    let refinementEnabled = $state(true);
    let autoRefine = $state(false);
    let username = $state("");

    /* ===== Audio file import ===== */
    const AUDIO_ACCEPT = ".wav,.mp3,.m4a,.flac,.ogg,.webm,.wma,.aac,.opus";
    let fileInput: HTMLInputElement | undefined = $state();

    /* ===== Quick-tag state ===== */
    let allTags = $state<Tag[]>([]);
    let assignedTagIds = $state<Set<number>>(new Set());

    function loadTags() {
        getTags()
            .then((tags) => (allTags = tags))
            .catch(() => {});
    }

    /* ===== Session tag state (persisted via localStorage) ===== */
    const SESSION_TAGS_STORAGE_KEY = "vociferous_session_tag_ids";

    function loadSessionTagIdsFromStorage(): Set<number> {
        try {
            const raw = localStorage.getItem(SESSION_TAGS_STORAGE_KEY);
            if (!raw) return new Set();
            const parsed = JSON.parse(raw);
            if (!Array.isArray(parsed)) return new Set();
            return new Set(parsed.filter((x: unknown) => typeof x === "number"));
        } catch {
            return new Set();
        }
    }

    let sessionTagIds = $state<Set<number>>(loadSessionTagIdsFromStorage());

    $effect(() => {
        try {
            localStorage.setItem(SESSION_TAGS_STORAGE_KEY, JSON.stringify([...sessionTagIds]));
        } catch {
            /* localStorage unavailable in some WebKitGTK contexts */
        }
    });

    function toggleSessionTag(tagId: number) {
        const next = new Set(sessionTagIds);
        if (next.has(tagId)) next.delete(tagId);
        else next.add(tagId);
        sessionTagIds = next;
    }

    async function handleSessionTagCreate(name: string, color: string) {
        try {
            await createTag(name, color);
            await loadTags();
            toast.success(`Tag "${name}" created`);
        } catch (e: any) {
            toast.error(`Tag creation failed: ${e.message}`);
        }
    }

    async function handleSessionTagDelete(tagId: number) {
        try {
            await deleteTag(tagId);
            const next = new Set(sessionTagIds);
            next.delete(tagId);
            sessionTagIds = next;
            await loadTags();
            toast.success("Tag deleted");
        } catch (e: any) {
            toast.error(`Tag deletion failed: ${e.message}`);
        }
    }

    async function handleSessionTagColorChange(tagId: number, color: string) {
        try {
            await updateTag(tagId, { color });
            await loadTags();
        } catch (e: any) {
            toast.error(`Failed to update tag color: ${e.message}`);
        }
    }

    /* ===== SLM insight (header subtitle) ===== */
    let slmInsight = $state("");

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

    /* ===== Append mode ===== */
    let appendTargetId = $state<number | null>(null);
    let appendTargetTitle = $state("");

    function cancelAppendMode() {
        appendTargetId = null;
        appendTargetTitle = "";
    }

    /* ===== Audio level (voice reactivity) ===== */
    let audioLevel = $state(0);

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

    function loadRecentSessions() {
        getTranscripts({ limit: 500 })
            .then((r) => (recentSessions = r.items))
            .catch(() => {});
    }

    /* ===== Derived state ===== */
    /** Most recent transcript that is not the current one (for append-to-previous). */
    let prevTranscript = $derived(recentSessions.find((t) => t.id !== transcriptId) ?? null);

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
        const time = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
        return username ? `${time}, ${username}!` : `${time}!`;
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
            hasAudioCached = t.has_audio_cached ?? false;
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
                autoRefine = (config as any)?.output?.auto_refine ?? false;
                username = (config as any)?.user?.name ?? "";
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
                if (data.cancelled) {
                    viewState = "idle";
                } else {
                    viewState = "transcribing";
                }
            }),
            ws.on("transcription_complete", async (data) => {
                /* ── Append mode: merge into target transcript ── */
                if (appendTargetId !== null) {
                    const targetId = appendTargetId;
                    appendTargetId = null;
                    appendTargetTitle = "";
                    try {
                        await dispatchIntent("append_to_transcript", {
                            transcript_id: targetId,
                            raw_text: data.text,
                            duration_ms: data.duration_ms ?? 0,
                            speech_duration_ms: data.speech_duration_ms ?? 0,
                        });
                        /* Clean up the temporary transcript the ASR pipeline created */
                        if (data.id) await apiDeleteTranscript(data.id);
                        toast.success("Recording appended");
                        
                        /* Auto-refine the combined transcript if enabled */
                        if (autoRefine && refinementEnabled) {
                            const DEFAULT_LEVEL = 2;
                            refineTranscript(targetId, DEFAULT_LEVEL).catch((e) =>
                                console.warn("Auto-refine after append failed:", e),
                            );
                        }
                    } catch (e: any) {
                        toast.error(`Append failed: ${e.message}`);
                    }
                    await openTranscript(targetId, "view");
                    loadRecentSessions();
                    return;
                }

                /* ── Normal flow ── */
                transcriptText = data.text;
                transcriptId = data.id;
                durationMs = data.duration_ms ?? 0;
                speechDurationMs = data.speech_duration_ms ?? 0;
                hasAudioCached = true;
                viewState = "ready";
                /* Apply session tags first, then overlay any already-assigned tags */
                if (sessionTagIds.size > 0 && data.id) {
                    const ids = [...sessionTagIds];
                    assignedTagIds = new Set(ids);
                    assignTags(data.id, ids).catch((e) => console.warn("Session tag auto-assign failed:", e));
                } else {
                    assignedTagIds = new Set();
                }
                loadRecentSessions();
                /* Title generated async by SLM — will arrive via transcript_updated */
                transcriptTitle = "";

                /* Auto-refine: fire-and-forget if enabled */
                if (autoRefine && refinementEnabled && data.id) {
                    const DEFAULT_LEVEL = 2;
                    refineTranscript(data.id, DEFAULT_LEVEL).catch((e) =>
                        console.warn("Auto-refine dispatch failed:", e),
                    );
                }
            }),
            ws.on("transcription_error", (data) => {
                transcriptText = `Error: ${data.message}`;
                viewState = "ready";
            }),
            ws.on("motd_ready", (data) => {
                slmInsight = data.text || "";
            }),
            ws.on("audio_level", (data) => {
                audioLevel = data.level;
            }),
            ws.on("config_updated", (data) => {
                const refinement = (data as any)?.refinement;
                if (typeof refinement === "object" && refinement !== null && "enabled" in refinement) {
                    refinementEnabled = Boolean((refinement as any).enabled);
                }
                const output = (data as any)?.output;
                if (typeof output === "object" && output !== null && "auto_refine" in output) {
                    autoRefine = Boolean((output as any).auto_refine);
                }
                const user = (data as any)?.user;
                if (typeof user === "object" && user !== null && "name" in user) {
                    username = String((user as any).name ?? "");
                }
            }),
            ws.on("refinement_complete", async (data) => {
                /* Auto-commit: if this transcript is the current one and auto-refine triggered it */
                if (autoRefine && data.transcript_id === transcriptId && data.text) {
                    try {
                        await commitRefinement(data.transcript_id, data.text);
                        transcriptText = data.text;
                    } catch (e) {
                        console.warn("Auto-refine commit failed:", e);
                    }
                }
            }),
            ws.on("transcript_updated", async (data) => {
                if (data.id === transcriptId) {
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
                sessionTagIds = new Set([...sessionTagIds].filter((id) => id !== data.id));
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
        const appendTarget = nav.consumeAppendTarget();
        if (appendTarget != null) {
            viewState = "idle";
            transcriptText = "";
            transcriptId = null;
            transcriptTitle = "";
            transcriptTimestamp = "";
            durationMs = 0;
            speechDurationMs = 0;
            assignedTagIds = new Set();
            appendTargetId = appendTarget;
            appendTargetTitle = "";
            getTranscript(appendTarget)
                .then((t) => {
                    appendTargetTitle = t.display_name?.trim() || `Transcript #${t.id}`;
                })
                .catch(() => {
                    appendTargetTitle = `Transcript #${appendTarget}`;
                });
            startRecording();
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

    function importAudio() {
        fileInput?.click();
    }

    async function submitAudioFile(file: File) {
        try {
            const result = await importAudioFile(file);
            if (result.status === "importing") {
                viewState = "transcribing";
            }
        } catch (e) {
            toast.error(`Import failed: ${e instanceof Error ? e.message : "unknown error"}`);
        }
    }

    function handleFileSelected(e: Event) {
        const input = e.target as HTMLInputElement;
        const file = input.files?.[0];
        if (file) submitAudioFile(file);
        input.value = "";
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

    async function appendToPrevious() {
        if (!transcriptId || !transcriptText || !prevTranscript) return;
        const targetTitle = prevTranscript.display_name?.trim() || `Transcript #${prevTranscript.id}`;
        const confirmed = await toast.confirm({
            title: "Append to previous recording?",
            message: `This will append the current recording to "${targetTitle}". The current standalone entry will be removed.`,
            confirmLabel: "Append",
            cancelLabel: "Keep separate",
        });
        if (!confirmed) return;
        const currentId = transcriptId;
        const targetId = prevTranscript.id;
        try {
            await dispatchIntent("append_to_transcript", {
                transcript_id: targetId,
                raw_text: transcriptText,
                duration_ms: durationMs,
                speech_duration_ms: speechDurationMs,
            });
            await apiDeleteTranscript(currentId);
            toast.success("Appended to previous recording");
            
            /* Auto-refine the combined transcript if enabled */
            if (autoRefine && refinementEnabled) {
                const DEFAULT_LEVEL = 2;
                refineTranscript(targetId, DEFAULT_LEVEL).catch((e) =>
                    console.warn("Auto-refine after append failed:", e),
                );
            }
            
            await openTranscript(targetId, "view");
            loadRecentSessions();
        } catch (e: any) {
            toast.error(`Append failed: ${e.message}`);
        }
    }

    function queueContinueMode() {
        if (!transcriptId) return;
        nav.navigateToAppendMode(transcriptId);
        toast.info("Continue mode active — next recording will be appended");
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
                        class="text-[var(--text-base)] text-[var(--text-secondary)] italic mb-0 leading-[var(--leading-normal)] opacity-85 max-w-prose px-[var(--space-4)] [overflow-wrap:anywhere]"
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
                <!-- Stats card -->
                {#if sessionStats && sessionStats.count > 0}
                    <div
                        class="inline-flex items-stretch bg-[var(--surface-secondary)] border border-[var(--shell-border)] rounded-[var(--radius-md)] mt-[var(--space-2)]"
                    >
                        <div class="flex flex-col items-center justify-center px-5 py-2">
                            <span class="text-[11px] text-[var(--text-tertiary)] leading-none mb-1.5"
                                >Today's Words</span
                            >
                            <span
                                class="text-base font-[var(--weight-emphasis)] text-[var(--text-primary)] font-[var(--font-mono)] leading-none"
                                >{sessionStats.todayWords.toLocaleString()}</span
                            >
                        </div>
                        <div class="w-px self-stretch my-2 bg-[var(--shell-border)]"></div>
                        <div class="flex flex-col items-center justify-center px-5 py-2">
                            <span class="text-[11px] text-[var(--text-tertiary)] leading-none mb-1.5">Avg WPM</span>
                            <span
                                class="text-base font-[var(--weight-emphasis)] text-[var(--text-primary)] font-[var(--font-mono)] leading-none"
                                >{sessionStats.avgWpm > 0 ? sessionStats.avgWpm : "\u2014"}</span
                            >
                        </div>
                        <div class="w-px self-stretch my-2 bg-[var(--shell-border)]"></div>
                        <div class="flex flex-col items-center justify-center px-5 py-2">
                            <span class="text-[11px] text-[var(--text-tertiary)] leading-none mb-1.5">Sessions</span>
                            <span
                                class="text-base font-[var(--weight-emphasis)] text-[var(--text-primary)] font-[var(--font-mono)] leading-none"
                                >{sessionStats.count}</span
                            >
                        </div>
                    </div>
                {/if}
            </div>
        {:else if viewState === "recording"}
            <div class="flex flex-col items-center text-center gap-[var(--space-1)]">
                <h1
                    class="text-3xl font-[var(--weight-emphasis)] text-[var(--accent)] m-0 leading-[var(--leading-tight)]"
                >
                    {greeting}
                </h1>
                {#if slmInsight}
                    <p
                        class="text-[var(--text-base)] text-[var(--text-secondary)] italic mb-0 leading-[var(--leading-normal)] opacity-85 max-w-prose px-[var(--space-4)] [overflow-wrap:anywhere]"
                    >
                        {slmInsight}
                    </p>
                {:else}
                    <p class="text-[var(--text-sm)] text-[var(--text-tertiary)] mb-0">Recording in progress</p>
                {/if}
                {#if sessionStats && sessionStats.count > 0}
                    <div
                        class="inline-flex items-stretch bg-[var(--surface-secondary)] border border-[var(--shell-border)] rounded-[var(--radius-md)] mt-[var(--space-2)]"
                    >
                        <div class="flex flex-col items-center justify-center px-5 py-2">
                            <span class="text-[11px] text-[var(--text-tertiary)] leading-none mb-1.5"
                                >Today's Words</span
                            >
                            <span
                                class="text-base font-[var(--weight-emphasis)] text-[var(--text-primary)] font-[var(--font-mono)] leading-none"
                                >{sessionStats.todayWords.toLocaleString()}</span
                            >
                        </div>
                        <div class="w-px self-stretch my-2 bg-[var(--shell-border)]"></div>
                        <div class="flex flex-col items-center justify-center px-5 py-2">
                            <span class="text-[11px] text-[var(--text-tertiary)] leading-none mb-1.5">Avg WPM</span>
                            <span
                                class="text-base font-[var(--weight-emphasis)] text-[var(--text-primary)] font-[var(--font-mono)] leading-none"
                                >{sessionStats.avgWpm > 0 ? sessionStats.avgWpm : "\u2014"}</span
                            >
                        </div>
                        <div class="w-px self-stretch my-2 bg-[var(--shell-border)]"></div>
                        <div class="flex flex-col items-center justify-center px-5 py-2">
                            <span class="text-[11px] text-[var(--text-tertiary)] leading-none mb-1.5">Sessions</span>
                            <span
                                class="text-base font-[var(--weight-emphasis)] text-[var(--text-primary)] font-[var(--font-mono)] leading-none"
                                >{sessionStats.count}</span
                            >
                        </div>
                    </div>
                {/if}
            </div>
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

    <!-- Append mode banner -->
    {#if appendTargetId !== null && (viewState === "idle" || viewState === "recording")}
        <div
            class="shrink-0 flex items-center gap-[var(--space-2)] px-[var(--space-2)] py-[var(--space-1)] rounded-[var(--radius-md)] bg-[color-mix(in_srgb,var(--accent)_10%,transparent)] border border-[var(--accent-muted)]"
        >
            <PlusCircle size={13} class="text-[var(--accent)] shrink-0" />
            <span class="text-[var(--text-sm)] text-[var(--text-secondary)] flex-1 truncate">
                Appending to: <span class="font-semibold text-[var(--text-primary)]"
                    >{appendTargetTitle || `Transcript #${appendTargetId}`}</span
                >
            </span>
            <button
                class="text-[var(--text-tertiary)] hover:text-[var(--text-primary)] bg-transparent border-none cursor-pointer p-0 leading-none transition-colors"
                onclick={cancelAppendMode}
                title="Cancel append mode"
            >
                <X size={13} />
            </button>
        </div>
    {/if}

    <!-- Session tag bar (idle/recording — selects tags auto-applied to every new transcript) -->
    {#if (viewState === "idle" || viewState === "recording") && allTags.filter((t) => !t.is_system).length > 0}
        <div
            class="shrink-0 flex flex-col items-center gap-[var(--space-1)] py-[var(--space-1)] px-[var(--space-1)]"
            title="Selected tags are auto-applied to every new recording until cleared"
        >
            <div class="flex items-center gap-[var(--space-1)]">
                <Bookmark
                    size={13}
                    class={sessionTagIds.size > 0
                        ? "text-[var(--accent)] shrink-0"
                        : "text-[var(--text-tertiary)] shrink-0"}
                />
                <span class="text-[var(--text-xs)] text-[var(--text-tertiary)] shrink-0 select-none">Session tags</span>
            </div>
            <TagBar
                tags={allTags.filter((t) => !t.is_system)}
                activeIds={sessionTagIds}
                ontoggle={toggleSessionTag}
                oncreate={handleSessionTagCreate}
                ondelete={handleSessionTagDelete}
                oncolorchange={handleSessionTagColorChange}
            />
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
        <!-- IDLE + RECORDING: shared composition with heatmap anchored at the bottom -->
        {#if viewState === "idle" || viewState === "recording"}
            <div class="flex-1 flex flex-col min-h-0">
                <div class="flex-1 min-h-0 flex flex-col items-center justify-center gap-[var(--space-4)]">
                    <RecordingControls {isRecording} {audioLevel} onstart={startRecording} onstop={stopRecording} />
                    {#if viewState === "idle"}
                        <input
                            bind:this={fileInput}
                            type="file"
                            accept={AUDIO_ACCEPT}
                            class="hidden"
                            onchange={handleFileSelected}
                        />
                        <StyledButton variant="ghost" size="sm" onclick={importAudio}>
                            <FileAudio size={14} /> Import Audio File
                        </StyledButton>
                    {/if}
                </div>

                {#if recentSessions.length > 0}
                    <div class="shrink-0 flex flex-col gap-[var(--space-2)] px-[var(--space-1)]">
                        <ActivityHeatmap entries={recentSessions} />
                    </div>
                {/if}
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
                <MarkdownBody text={transcriptText} className="text-[var(--text-base)] text-[var(--text-primary)]" />
            </div>
        {/if}
    </WorkspacePanel>

    <!-- Recording status bar (cancel + timer) — below the panel during active recording -->
    {#if isRecording}
        <div class="flex items-center gap-[var(--space-1)] py-[var(--space-1)] shrink-0">
            <StyledButton
                variant="danger-outline"
                size="sm"
                onclick={cancelRecording}
                ariaLabel="Cancel recording and discard audio"
                title="Cancel recording and discard captured audio"
            >
                <Trash2 size={15} /> Cancel
            </StyledButton>

            <div class="flex-1 flex items-center justify-center gap-[var(--space-2)]">
                <span
                    class="w-2 h-2 rounded-full bg-[var(--color-danger)] shrink-0 animate-[pulse-dot_1.2s_ease-in-out_infinite]"
                ></span>
                <span class="text-[var(--text-sm)] text-[var(--color-danger)] whitespace-nowrap"
                    >Recording in progress…</span
                >
            </div>

            <span
                class="text-[var(--text-sm)] font-[var(--font-mono)] text-[var(--text-tertiary)] tabular-nums whitespace-nowrap"
                >{formatElapsed(recordingElapsedMs)}</span
            >
        </div>
    {/if}

    <!-- Session tags applied confirmation (ready state only) -->
    {#if viewState === "ready" && sessionTagIds.size > 0}
        {@const appliedTags = allTags.filter((t) => sessionTagIds.has(t.id))}
        {#if appliedTags.length > 0}
            <div class="flex items-center gap-[var(--space-1)] py-[var(--space-1)] px-[var(--space-1)] shrink-0">
                <Bookmark size={12} class="text-[var(--accent)] shrink-0" />
                <span class="text-[var(--text-xs)] text-[var(--text-tertiary)]">Session tags applied:</span>
                {#each appliedTags as tag (tag.id)}
                    <span
                        class="inline-flex items-center h-5 px-1.5 rounded-full text-[10px] font-medium"
                        style="background: color-mix(in srgb, {tag.color ??
                            'var(--accent)'} 25%, transparent); color: var(--text-primary);">{tag.name}</span
                    >
                {/each}
            </div>
        {/if}
    {/if}

    <!-- Action bar (below panel) -->
    {#if viewState !== "idle" && viewState !== "transcribing" && viewState !== "recording"}
        <div class="flex items-center gap-[var(--space-1)] py-[var(--space-1)] shrink-0">
            {#if viewState === "editing"}
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

                {#if hasAudioCached}
                    <StyledButton
                        variant="ghost"
                        size="sm"
                        onclick={async () => {
                            if (transcriptId == null) return;
                            try {
                                await retranscribeTranscript(transcriptId);
                                toast.info("Re-transcription queued");
                            } catch {
                                toast.error("Failed to queue re-transcription");
                            }
                        }}
                    >
                        <RefreshCw size={14} /> Re-transcribe
                    </StyledButton>
                {/if}

                <div class="flex-1"></div>

                {#if viewState === "ready" && prevTranscript}
                    <StyledButton variant="ghost" size="sm" onclick={appendToPrevious}>
                        <PlusCircle size={14} /> Append to Previous
                    </StyledButton>
                {/if}
                {#if viewState === "ready" || viewState === "viewing"}
                    <StyledButton variant="ghost" size="sm" onclick={queueContinueMode}>
                        <Mic size={14} /> Continue
                    </StyledButton>
                {/if}
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
