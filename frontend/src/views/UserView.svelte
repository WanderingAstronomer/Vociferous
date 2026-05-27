<script lang="ts">
    import { onMount } from "svelte";
    import {
        getHealth,
        getUserMetrics,
        type DailyWordBucket,
        type HealthInfo,
        type UserMetricsPayload,
    } from "../lib/api";
    import { ws } from "../lib/ws";
    import { formatCount } from "../lib/formatters";
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
    const DEFAULT_TYPING_WPM = 40;

    /* ── Tabs ── */
    type UserTab = "dashboard" | "deep-dive";
    const TABS: { id: UserTab; label: string }[] = [
        { id: "dashboard", label: "Dashboard" },
        { id: "deep-dive", label: "Deep Dive" },
    ];

    /* ── State ── */
    let userMetrics = $state<UserMetricsPayload | null>(null);
    let loading = $state(true);
    let showExplanations = $state(false);
    let activeTab = $state<UserTab>("dashboard");
    let healthInfo = $state<HealthInfo | null>(null);

    /* ── Derived Metrics ── */
    let hasData = $derived((userMetrics?.count ?? 0) > 0);
    let count = $derived(userMetrics?.count ?? 0);
    let userName = $derived(userMetrics?.user_name ?? "");
    let typingWpm = $derived(userMetrics?.typing_wpm ?? DEFAULT_TYPING_WPM);
    let totalWords = $derived(userMetrics?.total_words ?? 0);
    let recordedSeconds = $derived(userMetrics?.total_recorded_seconds ?? 0);
    let timeSavedSeconds = $derived(userMetrics?.time_saved_seconds ?? 0);
    let avgSeconds = $derived(userMetrics?.avg_seconds ?? 0);

    /* ── Speech time & WPM (using VAD speech_duration_ms) ── */
    let avgWpm = $derived(userMetrics?.avg_wpm ?? 0);
    let totalSilence = $derived(userMetrics?.total_silence_seconds ?? 0);
    let avgSilence = $derived(userMetrics?.avg_silence_seconds ?? 0);
    let fillerCount = $derived(userMetrics?.filler_count ?? 0);

    /* ── Filler breakdown (top 5 per-word counts) ── */
    let fillerBreakdown = $derived(
        (userMetrics?.filler_breakdown ?? []).map((entry) => [entry.label, entry.count] as [string, number]),
    );
    let fillerBreakdownMax = $derived(fillerBreakdown.length > 0 ? fillerBreakdown[0][1] : 0);

    /* ── Vocabulary diversity ── */
    let vocabRatio = $derived(userMetrics?.vocabulary_ratio ?? 0);

    /* ── Streaks (consecutive active days) ── */
    let streaks = $derived({
        current: userMetrics?.current_streak ?? 0,
        longest: userMetrics?.longest_streak ?? 0,
    });

    /* ── Activity buckets ── */
    let dailyWordBuckets: DailyWordBucket[] = $derived(userMetrics?.daily_word_buckets ?? []);

    /* ── Verbatim vs Refined Metrics ── */
    let refinedCount = $derived(userMetrics?.refined_count ?? 0);
    let hasRefinements = $derived(refinedCount > 0);
    let fillersRemoved = $derived(userMetrics?.fillers_removed ?? 0);

    /* FK Grade — overall verbatim average (all transcripts) */
    let verbatimAvgFkGrade = $derived(userMetrics?.verbatim_avg_fk_grade ?? 0);

    /* FK Grade — refined average (refined transcripts' normalized text) */
    let refinedAvgFkGrade = $derived(userMetrics?.refined_avg_fk_grade ?? 0);

    /* FK delta — compare same population: raw vs refined for refined transcripts only */
    let verbatimFkForRefined = $derived(userMetrics?.verbatim_fk_for_refined ?? 0);
    let fkGradeDelta = $derived(userMetrics?.fk_grade_delta ?? 0);

    /* ── Processing Performance (transcription + refinement timing) ── */
    let totalTranscriptionTime = $derived(userMetrics?.total_transcription_seconds ?? 0);
    let totalRefinementTime = $derived(userMetrics?.total_refinement_seconds ?? 0);
    let hasTimingData = $derived(userMetrics?.has_timing_data ?? false);
    let avgTranscriptionSpeedX = $derived(userMetrics?.avg_transcription_speed_x ?? 0);
    let avgRefinementWpm = $derived(userMetrics?.avg_refinement_wpm ?? 0);
    let refinementTimeSaved = $derived(userMetrics?.refinement_time_saved_seconds ?? 0);

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
            const [metricsPayload, health] = await Promise.all([getUserMetrics(), getHealth().catch(() => null)]);
            if (gen !== loadGeneration) return; // stale response
            userMetrics = metricsPayload;
            healthInfo = health;
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
            ws.on("transcript_updated", () => loadData()),
            ws.on("transcript_deleted", () => loadData()),
            ws.on("transcripts_batch_deleted", () => loadData()),
            ws.on("transcripts_cleared", () => loadData()),
            ws.on("bulk_refinement_complete", () => loadData()),
            ws.on("config_updated", () => loadData()),
        ];
        return () => unsubs.forEach((fn) => fn());
    });

    /* ── Explanations content ── */
    let explanations = $derived([
        { title: "Transcriptions", text: "Total count of all transcription entries stored in your database." },
        {
            title: "Words Captured",
            text: "Sum of raw ASR word counts across analytics-included transcriptions. Edited and refined text does not rewrite this speech metric.",
        },
        {
            title: "Avg Speed",
            text: "Words per minute of actual speech time, computed from VAD (voice activity detection) segments. Excludes pauses and silence. If VAD data is unavailable, estimated from word count at 150 WPM.",
        },
        {
            title: "Time Saved",
            text: `Productivity gain vs. manual typing raw captured speech. Calculated per analytics population as: (raw_words ÷ ${typingWpm} WPM × 60) − resolved_recording_time = time_saved.`,
        },
        {
            title: "Streaks",
            text: "Consecutive days with at least one transcription. Current streak counts backward from today; longest streak is the all-time record.",
        },
        { title: "Average Length", text: "Mean duration per transcription: total_time ÷ transcription_count." },
        {
            title: "Total Silence",
            text: "Accumulated silence across recordings with duration metadata. Uses VAD speech duration when available; otherwise estimates speech time per transcript before subtracting.",
        },
        {
            title: "Vocabulary",
            text: "Ratio of unique cleaned words to total cleaned words across raw ASR output. Higher = more diverse vocabulary.",
        },
        {
            title: "Filler Words",
            text: "Approximate count of common filler words and phrases detected in raw ASR output. Single-word fillers are matched token-by-token; multi-word fillers are matched by phrase pattern.",
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
            text: `Estimated time saved by using SLM refinement vs. manual editing, using only refined transcripts with recorded SLM processing time. Manual editing speed is ${Math.round(typingWpm / 2)} WPM.`,
        },
        {
            title: "Transcription Speed",
            text: "Realtime multiplier for ASR inference. Computed only from transcripts with matching transcription processing time metadata.",
        },
        {
            title: "Refinement Throughput",
            text: "Words processed per minute by the SLM during refinement. Computed only from refined transcripts with matching SLM processing time metadata.",
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
                    <AnalyticsParagraph
                        segment="lifetime"
                        class="text-center text-[var(--text-sm)] text-[var(--accent)]"
                    />
                </div>

                <!-- ═══ Activity Heatmap (shared, above tabs) ═══ -->
                {#if count >= 2}
                    <ActivityHeatmap {dailyWordBuckets} />
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
                            {#if refinementTimeSaved > 0}
                                <div class="grid grid-cols-1 gap-[var(--space-3)]">
                                    <StatCard
                                        icon={Timer}
                                        value={formatDuration(refinementTimeSaved)}
                                        label="Est. Editing Time Saved"
                                        sublabel="vs manual proofreading at {Math.round(typingWpm / 2)} WPM"
                                        variant="featured"
                                    />
                                </div>
                            {/if}
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
                                href="https://www.linkedin.com/in/wanderingastronomer/"
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
