<script lang="ts">
    import { onMount } from "svelte";
    import { getTranscripts, getHealth, getConfig, type Transcript } from "../lib/api";
    import { toast } from "../lib/toast.svelte";
    import { ws } from "../lib/ws";
    import { formatCount } from "../lib/formatters";
    import { computeTextMetrics, fleschKincaidGrade, countFillers, countFillersByWord } from "../lib/textAnalysis";
    import StatCard from "../lib/components/StatCard.svelte";
    import ActivityHeatmap from "../lib/components/ActivityHeatmap.svelte";
    import AnalyticsParagraph from "../lib/components/AnalyticsParagraph.svelte";
    import {
        Timer,
        MessageSquareText,
        BarChart3,
        Clock,
        Gauge,
        PauseCircle,
        BookOpen,
        Volume2,
        MessageCircle,
        ChevronDown,
        ChevronRight,
        Github,
        Linkedin,
        User,
        Loader2,
        Sparkles,
        GraduationCap,
        Eraser,
        FileCheck2,
        Flame,
        Mic,
        Zap,
        Cpu,
    } from "lucide-svelte";

    /* ── Constants ── */
    const SPEAKING_SPEED_WPM = 150;
    const DEFAULT_TYPING_WPM = 40;
    const TRANSCRIPT_EXPORT_LIMIT = 10000;

    /* ── Tabs ── */
    type UserTab = "dashboard" | "deep-dive";
    const TABS: { id: UserTab; label: string }[] = [
        { id: "dashboard", label: "Dashboard" },
        { id: "deep-dive", label: "Deep Dive" },
    ];

    /* ── State ── */
    let entries: Transcript[] = $state([]);
    let loading = $state(true);
    let userName = $state("");
    let typingWpm = $state(DEFAULT_TYPING_WPM);
    let showExplanations = $state(false);
    let activeTab = $state<UserTab>("dashboard");
    let healthInfo: { version: string; transcripts: number } | null = $state(null);

    /* ── Derived Metrics ── */
    function safeText(e: { text: string }): string {
        return e.text || "";
    }

    let hasData = $derived(entries.length > 0);
    let count = $derived(entries.length);
    let totalWords = $derived(entries.reduce((s, e) => s + safeText(e).split(/\s+/).filter(Boolean).length, 0));

    let recordedSeconds = $derived.by(() => {
        const dur = entries.reduce((s, e) => s + (e.duration_ms || 0), 0) / 1000;
        if (dur > 0) return dur;
        if (totalWords > 0) return (totalWords / SPEAKING_SPEED_WPM) * 60;
        return 0;
    });

    let typingSeconds = $derived((totalWords / typingWpm) * 60);
    let timeSavedSeconds = $derived(Math.max(0, typingSeconds - recordedSeconds));
    let avgSeconds = $derived(count > 0 ? recordedSeconds / count : 0);

    /* ── Speech time & WPM (using VAD speech_duration_ms) ── */
    let totalSpeechSeconds = $derived.by(() => {
        let total = 0;
        for (const e of entries) {
            if (e.speech_duration_ms > 0) {
                total += e.speech_duration_ms / 1000;
            } else if (e.duration_ms > 0) {
                const words = safeText(e).split(/\s+/).filter(Boolean).length;
                total += Math.min((words / SPEAKING_SPEED_WPM) * 60, e.duration_ms / 1000);
            }
        }
        return total;
    });

    let avgWpm = $derived(totalSpeechSeconds > 0 ? Math.round((totalWords / totalSpeechSeconds) * 60) : 0);

    let totalSilence = $derived.by(() => {
        let total = 0;
        for (const e of entries) {
            if (e.duration_ms && e.duration_ms > 0) {
                const dur = e.duration_ms / 1000;
                const speech = (e.speech_duration_ms || 0) / 1000;
                total += Math.max(0, dur - speech);
            }
        }
        return total;
    });

    let avgSilence = $derived.by(() => {
        let total = 0;
        let withDuration = 0;
        for (const e of entries) {
            if (e.duration_ms && e.duration_ms > 0) {
                const dur = e.duration_ms / 1000;
                const speech = (e.speech_duration_ms || 0) / 1000;
                total += Math.max(0, dur - speech);
                withDuration++;
            }
        }
        return withDuration > 0 ? total / withDuration : 0;
    });

    let fillerCount = $derived.by(() => {
        let total = 0;
        for (const e of entries) {
            total += countFillers(safeText(e));
        }
        return total;
    });

    /* ── Filler breakdown (top 5 per-word counts) ── */
    let fillerBreakdown = $derived.by(() => {
        const agg: Record<string, number> = {};
        for (const e of entries) {
            for (const [word, wc] of Object.entries(countFillersByWord(safeText(e)))) {
                agg[word] = (agg[word] || 0) + wc;
            }
        }
        return Object.entries(agg)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 5);
    });

    let fillerBreakdownMax = $derived(fillerBreakdown.length > 0 ? fillerBreakdown[0][1] : 0);

    /* ── Vocabulary diversity ── */
    let vocabRatio = $derived.by(() => {
        const allWords: string[] = [];
        for (const e of entries) {
            for (const w of safeText(e).toLowerCase().split(/\s+/)) {
                const c = w.replace(/^[.,!?;:'"()\[\]{}]+|[.,!?;:'"()\[\]{}]+$/g, "");
                if (c) allWords.push(c);
            }
        }
        if (allWords.length === 0) return 0;
        return new Set(allWords).size / allWords.length;
    });

    /* ── Streaks (consecutive active days) ── */
    let streaks = $derived.by(() => {
        const dates = new Set<number>();
        for (const e of entries) {
            try {
                const d = new Date(e.created_at);
                if (!isNaN(d.getTime())) {
                    // Days since epoch (UTC)
                    dates.add(Math.floor(d.getTime() / 86400000));
                }
            } catch {
                /* skip */
            }
        }

        let current = 0;
        let longest = 0;

        if (dates.size > 0) {
            const today = Math.floor(Date.now() / 86400000);
            let d = today;
            while (dates.has(d)) {
                current++;
                d--;
            }

            const sorted = [...dates].sort((a, b) => a - b);
            let run = 1;
            for (let i = 1; i < sorted.length; i++) {
                if (sorted[i] === sorted[i - 1] + 1) {
                    run++;
                } else {
                    longest = Math.max(longest, run);
                    run = 1;
                }
            }
            longest = Math.max(longest, run);
        }

        return { current, longest };
    });

    /* ── Verbatim vs Refined Metrics ── */
    let refinedEntries = $derived(entries.filter((e) => e.normalized_text && e.normalized_text !== e.raw_text));
    let refinedCount = $derived(refinedEntries.length);
    let hasRefinements = $derived(refinedCount > 0);

    /* Filler count across ALL transcripts (for Speech Quality section) */
    let verbatimFillerCount = $derived.by(() => {
        let total = 0;
        for (const e of entries) {
            total += countFillers(e.raw_text || "");
        }
        return total;
    });

    /* Refinement Impact — compare the SAME transcripts before/after */
    let rawFillersInRefined = $derived.by(() => {
        let total = 0;
        for (const e of refinedEntries) {
            total += countFillers(e.raw_text || "");
        }
        return total;
    });

    let refinedFillerCount = $derived.by(() => {
        let total = 0;
        for (const e of refinedEntries) {
            total += countFillers(e.normalized_text || "");
        }
        return total;
    });

    let fillersRemoved = $derived(rawFillersInRefined - refinedFillerCount);

    /* FK Grade — overall verbatim average (all transcripts) */
    let verbatimAvgFkGrade = $derived.by(() => {
        const grades = entries.map((e) => fleschKincaidGrade(e.raw_text || "")).filter((g) => g > 0);
        if (!grades.length) return 0;
        return Math.round((grades.reduce((s, g) => s + g, 0) / grades.length) * 10) / 10;
    });

    /* FK Grade — refined average (refined transcripts' normalized text) */
    let refinedAvgFkGrade = $derived.by(() => {
        const grades = refinedEntries.map((e) => fleschKincaidGrade(e.normalized_text || "")).filter((g) => g > 0);
        if (!grades.length) return 0;
        return Math.round((grades.reduce((s, g) => s + g, 0) / grades.length) * 10) / 10;
    });

    /* FK delta — compare same population: raw vs refined for refined transcripts only */
    let verbatimFkForRefined = $derived.by(() => {
        const grades = refinedEntries.map((e) => fleschKincaidGrade(e.raw_text || "")).filter((g) => g > 0);
        if (!grades.length) return 0;
        return Math.round((grades.reduce((s, g) => s + g, 0) / grades.length) * 10) / 10;
    });

    let fkGradeDelta = $derived(hasRefinements ? Math.round((refinedAvgFkGrade - verbatimFkForRefined) * 10) / 10 : 0);

    /* ── Processing Performance (transcription + refinement timing) ── */
    let totalTranscriptionTime = $derived.by(() => {
        let total = 0;
        for (const e of entries) total += e.transcription_time_ms || 0;
        return total / 1000; // seconds
    });

    let totalRefinementTime = $derived.by(() => {
        let total = 0;
        for (const e of entries) total += e.refinement_time_ms || 0;
        return total / 1000; // seconds
    });

    let hasTimingData = $derived(totalTranscriptionTime > 0 || totalRefinementTime > 0);

    let avgTranscriptionSpeedX = $derived(
        totalTranscriptionTime > 0 && recordedSeconds > 0
            ? Math.round((recordedSeconds / totalTranscriptionTime) * 10) / 10
            : 0,
    );

    let avgRefinementWpm = $derived.by(() => {
        if (totalRefinementTime <= 0) return 0;
        const refinedWords = refinedEntries.reduce((s, e) => s + safeText(e).split(/\s+/).filter(Boolean).length, 0);
        return Math.round(refinedWords / (totalRefinementTime / 60));
    });

    /* Refinement time saved: manual editing time minus actual SLM time.
       Manual editing speed ≈ typing_wpm / 2 (reading + restructuring). */
    let refinementTimeSaved = $derived.by(() => {
        if (!hasRefinements) return 0;
        const refinedWords = refinedEntries.reduce((s, e) => s + safeText(e).split(/\s+/).filter(Boolean).length, 0);
        if (refinedWords === 0) return 0;
        const manualEditWpm = Math.max(1, typingWpm / 2);
        const manualSeconds = (refinedWords / manualEditWpm) * 60;
        return Math.max(0, manualSeconds - totalRefinementTime);
    });

    let titleText = $derived(userName.trim() ? `${userName.trim()}'s Vociferous Journey` : "Your Vociferous Journey");

    /* ── Formatting ── */
    function formatDuration(seconds: number): string {
        if (seconds < 60) return `${Math.round(seconds)}s`;
        const m = Math.floor(seconds / 60);
        if (m < 60) return `${m}m`;
        const h = Math.floor(m / 60);
        const rm = m % 60;
        return rm === 0 ? `${h}h` : `${h}h ${rm}m`;
    }

    function formatPercent(v: number): string {
        return `${Math.round(v * 100)}%`;
    }

    /* ── Data loading ── */
    let loadGeneration = 0;

    async function loadData() {
        const gen = ++loadGeneration;
        loading = true;
        try {
            const [transcriptResult, health, config] = await Promise.all([
                getTranscripts({ limit: TRANSCRIPT_EXPORT_LIMIT }),
                getHealth().catch(() => null),
                getConfig().catch(() => ({})),
            ]);
            if (gen !== loadGeneration) return; // stale response
            entries = transcriptResult.items.filter((t) => t.include_in_analytics);
            healthInfo = health;
            // Extract user name and typing WPM from config
            const u = config as Record<string, unknown>;
            const userSection = u?.user as Record<string, unknown> | undefined;
            userName = (userSection?.name as string) ?? "";
            const wpm = Number(userSection?.typing_wpm);
            if (wpm > 0) typingWpm = wpm;
        } catch (e) {
            if (gen !== loadGeneration) return;
            console.error("Failed to load user data:", e);
        } finally {
            if (gen === loadGeneration) loading = false;
        }
    }

    /* ── Lifecycle ── */
    onMount(() => {
        loadData();
        const unsubs = [
            ws.on("transcription_complete", () => loadData()),
            ws.on("transcript_deleted", () => loadData()),
            ws.on("transcripts_batch_deleted", () => loadData()),
        ];
        return () => unsubs.forEach((fn) => fn());
    });

    /* ── Explanations content ── */
    let explanations = $derived([
        { title: "Transcriptions", text: "Total count of all transcription entries stored in your database." },
        {
            title: "Words Captured",
            text: "Sum of word counts across all transcriptions. Each entry's words are counted individually.",
        },
        {
            title: "Avg Speed",
            text: "Words per minute of actual speech time, computed from VAD (voice activity detection) segments. Excludes pauses and silence. If VAD data is unavailable, estimated from word count at 150 WPM.",
        },
        {
            title: "Time Saved",
            text: `Productivity gain vs. manual typing. Calculated as: (words ÷ ${typingWpm} WPM × 60) − recording_time = time_saved. Based on typing speed of ${typingWpm} WPM.`,
        },
        {
            title: "Streaks",
            text: "Consecutive days with at least one transcription. Current streak counts backward from today; longest streak is the all-time record.",
        },
        { title: "Average Length", text: "Mean duration per transcription: total_time ÷ transcription_count." },
        {
            title: "Total Silence",
            text: "Accumulated silence across all recordings. Calculated as: recording_duration − VAD_speech_duration for each entry.",
        },
        {
            title: "Vocabulary",
            text: "Ratio of unique words to total words across all transcriptions. Higher = more diverse vocabulary.",
        },
        {
            title: "Filler Words",
            text: "Approximate count of common filler words and phrases detected across all transcriptions. Single-word fillers (um, uh, like, etc.) are matched token-by-token; multi-word fillers (you know, I mean, etc.) are matched by substring, which may overcount in some contexts.",
        },
        {
            title: "Transcripts Refined",
            text: "Number of transcripts processed by the SLM refinement pipeline. A transcript counts as refined when its normalized text differs from the raw ASR output.",
        },
        {
            title: "Fillers Removed",
            text: "Difference in filler word count between verbatim (raw ASR) and refined (post-SLM) text across refined transcripts.",
        },
        {
            title: "FK Grade",
            text: "Flesch-Kincaid Grade Level measures sentence structure complexity. Lower = more readable. Hemingway ~4; newspaper ~8; Harvard Law Review ~18. Raw speech scores high because Whisper produces long unpunctuated runs; refinement breaks these into proper sentences.",
        },
        {
            title: "Est. Editing Time Saved",
            text: `Estimated time saved by using SLM refinement vs. manual editing. Manual editing speed assumed at ${Math.round(typingWpm / 2)} WPM (half your ${typingWpm} WPM typing speed — editing requires reading, restructuring, and proofreading). Formula: (refined_words ÷ editing_WPM × 60) − actual_SLM_time.`,
        },
        {
            title: "Transcription Speed",
            text: "Realtime multiplier for ASR inference. A value of 45× means 30 minutes of audio was transcribed in ~40 seconds. Computed as: total_recording_duration ÷ total_Whisper_processing_time.",
        },
        {
            title: "Refinement Throughput",
            text: "Words processed per minute by the SLM during refinement. Computed as: total_refined_words ÷ total_SLM_processing_minutes.",
        },
    ]);
</script>

<div class="flex flex-col h-full overflow-hidden bg-[var(--surface-primary)]">
    <div class="flex-1 overflow-y-auto">
        <div
            class="w-full max-w-6xl mx-auto pt-[var(--space-5)] px-[var(--space-5)] pb-32 flex flex-col gap-[var(--space-5)]"
        >
            {#if loading}
                <div class="flex flex-col items-center gap-[var(--space-3)] py-[96px] text-[var(--text-tertiary)]">
                    <Loader2 size={32} class="spin" />
                    <p>Loading your statistics…</p>
                </div>
            {:else if !hasData}
                <div
                    class="flex flex-col items-center gap-[var(--space-3)] py-[96px] px-[var(--space-6)] text-[var(--text-tertiary)] text-center border border-[var(--shell-border)] rounded-[var(--radius-lg)] bg-[var(--surface-secondary)]"
                >
                    <User size={40} strokeWidth={1.2} />
                    <h3 class="m-0 text-[var(--text-primary)] text-[var(--text-lg)]">No metrics yet</h3>
                    <p class="m-0 text-[var(--text-sm)] leading-[1.6]">
                        Metrics appear after your first transcription is saved.<br />Try making a recording to see your
                        impact.
                    </p>
                </div>
            {:else}
                <!-- ═══ Header ═══ -->
                <div class="flex flex-col items-center gap-[var(--space-2)]">
                    <h2 class="text-3xl font-[var(--weight-emphasis)] text-[var(--accent)] text-center m-0">
                        {titleText}
                    </h2>
                    <div class="w-12 h-[2px] rounded-full bg-[var(--accent)]"></div>
                    <AnalyticsParagraph class="text-center text-[var(--text-sm)] text-[var(--accent)]" />
                </div>

                <!-- ═══ Activity Heatmap (shared, above tabs) ═══ -->
                {#if count >= 2}
                    <ActivityHeatmap {entries} />
                {/if}

                <!-- ═══ Tab Bar ═══ -->
                <div
                    class="sticky top-0 z-10 flex gap-[var(--space-2)] border-b border-[var(--shell-border)] bg-[var(--surface-primary)] -mx-[var(--space-5)] px-[var(--space-5)] overflow-x-auto"
                >
                    {#each TABS as tab}
                        <button
                            class="px-[var(--space-3)] py-[var(--space-2)] text-[var(--text-sm)] font-[var(--weight-medium)] border-b-2 transition-colors duration-[var(--transition-fast)] whitespace-nowrap cursor-pointer bg-transparent {activeTab ===
                            tab.id
                                ? 'border-[var(--accent)] text-[var(--accent)]'
                                : 'border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]'}"
                            onclick={() => (activeTab = tab.id)}
                        >
                            {tab.label}
                        </button>
                    {/each}
                </div>

                <!-- ═══ Dashboard Tab ═══ -->
                {#if activeTab === "dashboard"}
                    <!-- ═══ Your Voice ═══ -->
                    <div class="flex flex-col gap-[var(--space-3)]">
                        <span
                            class="font-[var(--weight-emphasis)] text-[var(--text-xs)] text-[var(--text-tertiary)] uppercase tracking-[1px] text-center"
                            >Your Voice</span
                        >
                        <div class="grid grid-cols-2 gap-[var(--space-4)]">
                            <StatCard
                                icon={Timer}
                                value={formatDuration(timeSavedSeconds)}
                                label="Time Saved"
                                sublabel="vs manual typing"
                                variant="featured"
                            />
                            <StatCard
                                icon={MessageSquareText}
                                value={formatCount(totalWords)}
                                label="Words Captured"
                                sublabel="Total transcribed words"
                                variant="featured"
                            />
                        </div>
                        <div class="grid grid-cols-2 gap-[var(--space-3)]">
                            <StatCard
                                icon={Mic}
                                value={avgWpm > 0 ? `${avgWpm} WPM` : "—"}
                                label="Avg Speed"
                                sublabel="Speech time only"
                            />
                            <StatCard
                                icon={Flame}
                                value={streaks.current > 0
                                    ? `${streaks.current} day${streaks.current !== 1 ? "s" : ""}`
                                    : "—"}
                                label="Current Streak"
                                sublabel={streaks.longest > 0
                                    ? `Best: ${streaks.longest} day${streaks.longest !== 1 ? "s" : ""}`
                                    : "Start your streak!"}
                            />
                        </div>
                    </div>

                    <!-- ═══ Refinement Impact (only shown if refinements exist) ═══ -->
                    {#if hasRefinements}
                        <div class="flex flex-col gap-[var(--space-3)]">
                            <span
                                class="font-[var(--weight-emphasis)] text-[var(--text-xs)] text-[var(--text-tertiary)] uppercase tracking-[1px] text-center"
                                >Refinement Impact</span
                            >
                            <div class="grid grid-cols-3 gap-[var(--space-3)]">
                                <StatCard
                                    icon={FileCheck2}
                                    value={formatCount(refinedCount)}
                                    label="Transcripts Refined"
                                    sublabel="{Math.round((refinedCount / count) * 100)}% of total"
                                />
                                <StatCard
                                    icon={Eraser}
                                    value={formatCount(fillersRemoved)}
                                    label="Fillers Removed"
                                    sublabel="by refinement"
                                />
                                <StatCard
                                    icon={GraduationCap}
                                    value="{verbatimFkForRefined} → {refinedAvgFkGrade}"
                                    label="Reading Level"
                                    sublabel="Verbatim → Refined ({fkGradeDelta > 0 ? '+' : ''}{fkGradeDelta})"
                                />
                            </div>
                            {#if refinementTimeSaved > 0}
                                <div class="grid grid-cols-1 gap-[var(--space-3)]">
                                    <StatCard
                                        icon={Timer}
                                        value={formatDuration(refinementTimeSaved)}
                                        label="Est. Editing Time Saved"
                                        sublabel="vs manual proofreading at {Math.round(typingWpm / 2)} WPM"
                                    />
                                </div>
                            {/if}
                        </div>
                    {/if}

                    <div class="h-px bg-[var(--shell-border)]"></div>

                    <!-- ═══ About ═══ -->
                    <footer
                        class="rounded-[var(--radius-lg)] border border-[var(--shell-border)] bg-[var(--surface-secondary)] p-[var(--space-5)] flex flex-col items-center gap-[var(--space-3)]"
                    >
                        <h2 class="text-2xl font-[var(--weight-emphasis)] text-[var(--accent)] m-0">Vociferous</h2>
                        <p class="text-[var(--text-sm)] text-[var(--text-secondary)] m-0">Local AI Dictation Suite</p>

                        <p
                            class="text-[var(--text-sm)] text-[var(--text-tertiary)] text-center leading-[var(--leading-relaxed)] max-w-[520px] m-0"
                        >
                            From voice to polished text — speech recognition, intelligent refinement, and document
                            export in one privacy-first pipeline. Runs entirely on your machine with no cloud, no data
                            collection, and no internet required.
                        </p>

                        {#if healthInfo}
                            <p class="text-[var(--text-xs)] text-[var(--text-tertiary)] font-mono m-0">
                                v{healthInfo.version}
                            </p>
                        {/if}

                        <div class="flex gap-[var(--space-3)]">
                            <a
                                class="flex items-center gap-[var(--space-1)] py-[var(--space-1)] px-[var(--space-3)] border border-[var(--shell-border)] rounded-[var(--radius-md)] text-[var(--text-secondary)] text-[var(--text-sm)] no-underline transition-[color,border-color] duration-[var(--transition-fast)] hover:text-[var(--accent)] hover:border-[var(--accent)]"
                                href="https://www.linkedin.com/in/abrown7521/"
                                target="_blank"
                                rel="noopener"
                            >
                                <Linkedin size={15} /> LinkedIn
                            </a>
                            <a
                                class="flex items-center gap-[var(--space-1)] py-[var(--space-1)] px-[var(--space-3)] border border-[var(--shell-border)] rounded-[var(--radius-md)] text-[var(--text-secondary)] text-[var(--text-sm)] no-underline transition-[color,border-color] duration-[var(--transition-fast)] hover:text-[var(--accent)] hover:border-[var(--accent)]"
                                href="https://github.com/WanderingAstronomer/Vociferous"
                                target="_blank"
                                rel="noopener"
                            >
                                <Github size={15} /> GitHub
                            </a>
                        </div>

                        <p class="text-[var(--text-xs)] text-[var(--accent)] m-0">Created by Andrew Brown</p>
                    </footer>

                    <!-- ═══ Deep Dive Tab ═══ -->
                {:else if activeTab === "deep-dive"}
                    <!-- ═══ Productivity ═══ -->
                    <div class="flex flex-col gap-[var(--space-3)]">
                        <span
                            class="font-[var(--weight-emphasis)] text-[var(--text-xs)] text-[var(--text-tertiary)] uppercase tracking-[1px] text-center"
                            >Productivity</span
                        >
                        <div class="grid grid-cols-4 gap-[var(--space-3)]">
                            <StatCard
                                icon={BarChart3}
                                value={formatCount(count)}
                                label="Transcriptions"
                                sublabel="Total recordings"
                            />
                            <StatCard
                                icon={Clock}
                                value={formatDuration(recordedSeconds)}
                                label="Time Recorded"
                                sublabel="Total audio duration"
                            />
                            <StatCard
                                icon={Gauge}
                                value={formatDuration(avgSeconds)}
                                label="Avg. Length"
                                sublabel="Per recording"
                            />
                            <StatCard
                                icon={PauseCircle}
                                value={totalSilence > 0 ? formatDuration(totalSilence) : "—"}
                                label="Total Silence"
                                sublabel="Accumulated pauses"
                            />
                        </div>
                    </div>

                    <!-- ═══ Speech Quality ═══ -->
                    <div class="flex flex-col gap-[var(--space-3)]">
                        <span
                            class="font-[var(--weight-emphasis)] text-[var(--text-xs)] text-[var(--text-tertiary)] uppercase tracking-[1px] text-center"
                            >Speech Quality</span
                        >
                        <div class="grid grid-cols-3 gap-[var(--space-3)]">
                            <StatCard
                                icon={BookOpen}
                                value={vocabRatio > 0 ? formatPercent(vocabRatio) : "—"}
                                label="Vocabulary"
                                sublabel="Unique words ratio"
                            />
                            <StatCard
                                icon={Volume2}
                                value={avgSilence > 0 ? formatDuration(avgSilence) : "—"}
                                label="Avg. Pauses"
                                sublabel="VAD-estimated silence"
                            />
                            <StatCard
                                icon={MessageCircle}
                                value={fillerCount > 0 ? formatCount(fillerCount) : "—"}
                                label="Filler Words"
                                sublabel="≈ um, uh, like, you know"
                            />
                        </div>

                        <!-- Filler Breakdown -->
                        {#if fillerBreakdown.length > 0}
                            <div
                                class="rounded-[var(--radius-md)] border border-[var(--shell-border)] bg-[var(--surface-secondary)] p-[var(--space-4)]"
                            >
                                <p
                                    class="text-[var(--text-xs)] text-[var(--text-tertiary)] uppercase tracking-[1px] font-[var(--weight-emphasis)] m-0 mb-[var(--space-3)]"
                                >
                                    Top Fillers
                                </p>
                                <div class="flex flex-col gap-[var(--space-2)]">
                                    {#each fillerBreakdown as [word, wcount]}
                                        <div class="flex items-center gap-[var(--space-3)]">
                                            <span
                                                class="text-[var(--text-sm)] text-[var(--text-secondary)] w-20 text-right shrink-0 font-mono"
                                                >{word}</span
                                            >
                                            <div
                                                class="flex-1 h-5 rounded-[var(--radius-sm)] bg-[var(--surface-primary)] overflow-hidden"
                                            >
                                                <div
                                                    class="h-full rounded-[var(--radius-sm)] bg-[var(--accent)] transition-all duration-[var(--transition-fast)]"
                                                    style="width: {fillerBreakdownMax > 0
                                                        ? (wcount / fillerBreakdownMax) * 100
                                                        : 0}%"
                                                ></div>
                                            </div>
                                            <span
                                                class="text-[var(--text-xs)] text-[var(--text-tertiary)] w-10 shrink-0 tabular-nums"
                                                >{formatCount(wcount)}</span
                                            >
                                        </div>
                                    {/each}
                                </div>
                            </div>
                        {/if}
                    </div>

                    <!-- ═══ Readability ═══ -->
                    <div class="flex flex-col gap-[var(--space-3)]">
                        <span
                            class="font-[var(--weight-emphasis)] text-[var(--text-xs)] text-[var(--text-tertiary)] uppercase tracking-[1px] text-center"
                            >Readability</span
                        >
                        <div class="grid grid-cols-2 gap-[var(--space-3)]">
                            <StatCard
                                icon={GraduationCap}
                                value="Grade {hasRefinements ? verbatimFkForRefined : verbatimAvgFkGrade}"
                                label="FK Grade"
                                sublabel={hasRefinements ? "Verbatim · lower = more readable" : "Lower = more readable"}
                            />
                            {#if hasRefinements}
                                <StatCard
                                    icon={Sparkles}
                                    value="Grade {refinedAvgFkGrade}"
                                    label="FK Grade"
                                    sublabel="Refined · {fkGradeDelta > 0 ? '+' : ''}{fkGradeDelta} from verbatim"
                                />
                            {/if}
                        </div>
                    </div>

                    <!-- ═══ Processing Performance (only shown if timing data exists) ═══ -->
                    {#if hasTimingData}
                        <div class="flex flex-col gap-[var(--space-3)]">
                            <span
                                class="font-[var(--weight-emphasis)] text-[var(--text-xs)] text-[var(--text-tertiary)] uppercase tracking-[1px] text-center"
                                >Processing Performance</span
                            >
                            <div class="grid grid-cols-2 gap-[var(--space-3)]">
                                {#if avgTranscriptionSpeedX > 0}
                                    <StatCard
                                        icon={Zap}
                                        value="{avgTranscriptionSpeedX}×"
                                        label="Transcription Speed"
                                        sublabel="realtime multiplier"
                                    />
                                {/if}
                                {#if avgRefinementWpm > 0}
                                    <StatCard
                                        icon={Cpu}
                                        value="{formatCount(avgRefinementWpm)} WPM"
                                        label="Refinement Throughput"
                                        sublabel="SLM processing speed"
                                    />
                                {/if}
                            </div>
                            <div class="grid grid-cols-2 gap-[var(--space-3)]">
                                {#if totalTranscriptionTime > 0}
                                    <StatCard
                                        icon={Clock}
                                        value={formatDuration(totalTranscriptionTime)}
                                        label="ASR Processing"
                                        sublabel="Total transcription time"
                                    />
                                {/if}
                                {#if totalRefinementTime > 0}
                                    <StatCard
                                        icon={Clock}
                                        value={formatDuration(totalRefinementTime)}
                                        label="SLM Processing"
                                        sublabel="Total refinement time"
                                    />
                                {/if}
                            </div>
                        </div>
                    {/if}

                    <div class="h-px bg-[var(--shell-border)]"></div>

                    <!-- ═══ Calculation Details (collapsible) ═══ -->
                    <section class="flex flex-col items-center gap-[var(--space-4)]">
                        <button
                            class="flex items-center gap-[var(--space-2)] bg-none border-none text-[var(--text-secondary)] text-[var(--text-sm)] cursor-pointer py-[var(--space-2)] px-[var(--space-4)] rounded-[var(--radius-md)] transition-[color,background] duration-[var(--transition-fast)] hover:text-[var(--accent)] hover:bg-[var(--hover-overlay)]"
                            onclick={() => (showExplanations = !showExplanations)}
                        >
                            {#if showExplanations}
                                <ChevronDown size={14} />
                                Hide Calculation Details
                            {:else}
                                <ChevronRight size={14} />
                                Show Calculation Details
                            {/if}
                        </button>

                        {#if showExplanations}
                            <div class="flex flex-col gap-[var(--space-2)] w-full">
                                {#each explanations as exp}
                                    <div
                                        class="w-full rounded-[var(--radius-md)] border border-[var(--shell-border)] bg-[var(--surface-secondary)] px-[var(--space-4)] py-[var(--space-3)] flex items-start gap-[var(--space-4)]"
                                    >
                                        <strong
                                            class="min-w-[160px] text-[var(--text-sm)] text-accent font-semibold leading-[var(--leading-normal)]"
                                            >{exp.title}</strong
                                        >
                                        <span
                                            class="text-[var(--text-sm)] text-[var(--text-secondary)] leading-[var(--leading-relaxed)] text-left"
                                            >{exp.text}</span
                                        >
                                    </div>
                                {/each}
                            </div>
                        {/if}
                    </section>
                {/if}
            {/if}
        </div>
    </div>
</div>
