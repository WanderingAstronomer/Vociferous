<script lang="ts">
    import { onMount, onDestroy } from "svelte";
    import { getTranscripts, getHealth, getConfig, type Transcript } from "../lib/api";
    import { ws } from "../lib/ws";
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
        ExternalLink,
        Github,
        Linkedin,
        User,
    } from "lucide-svelte";

    /* ── Constants ── */
    const SPEAKING_SPEED_WPM = 150;
    const TYPING_SPEED_WPM = 40;
    const HISTORY_EXPORT_LIMIT = 10000;

    const FILLER_SINGLE = new Set([
        "um",
        "uh",
        "uhm",
        "umm",
        "er",
        "err",
        "like",
        "basically",
        "literally",
        "actually",
        "so",
        "well",
        "right",
        "okay",
    ]);
    const FILLER_MULTI = ["you know", "i mean", "kind of", "sort of"];

    /* ── State ── */
    let entries: Transcript[] = $state([]);
    let loading = $state(true);
    let userName = $state("");
    let showExplanations = $state(false);
    let healthInfo: { version: string; transcripts: number } | null = $state(null);

    /* ── Derived Metrics ── */
    let hasData = $derived(entries.length > 0);
    let count = $derived(entries.length);
    let totalWords = $derived(entries.reduce((s, e) => s + e.text.split(/\s+/).filter(Boolean).length, 0));

    let recordedSeconds = $derived.by(() => {
        const dur = entries.reduce((s, e) => s + (e.duration_ms || 0), 0) / 1000;
        if (dur > 0) return dur;
        if (totalWords > 0) return (totalWords / SPEAKING_SPEED_WPM) * 60;
        return 0;
    });

    let typingSeconds = $derived((totalWords / TYPING_SPEED_WPM) * 60);
    let timeSavedSeconds = $derived(Math.max(0, typingSeconds - recordedSeconds));
    let avgSeconds = $derived(count > 0 ? recordedSeconds / count : 0);

    let lexicalComplexity = $derived.by(() => {
        const allWords: string[] = [];
        for (const e of entries) {
            const words = e.text.toLowerCase().split(/\s+/);
            for (const w of words) {
                const c = w.replace(/^[.,!?;:'"()\[\]{}]+|[.,!?;:'"()\[\]{}]+$/g, "");
                if (c) allWords.push(c);
            }
        }
        if (allWords.length === 0) return 0;
        return new Set(allWords).size / allWords.length;
    });

    let totalSilence = $derived.by(() => {
        let total = 0;
        for (const e of entries) {
            if (e.duration_ms && e.duration_ms > 0) {
                const dur = e.duration_ms / 1000;
                const expected = (e.text.split(/\s+/).filter(Boolean).length / SPEAKING_SPEED_WPM) * 60;
                total += Math.max(0, dur - expected);
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
                const expected = (e.text.split(/\s+/).filter(Boolean).length / SPEAKING_SPEED_WPM) * 60;
                total += Math.max(0, dur - expected);
                withDuration++;
            }
        }
        return withDuration > 0 ? total / withDuration : 0;
    });

    let fillerCount = $derived.by(() => {
        let total = 0;
        for (const e of entries) {
            const lower = e.text.toLowerCase();
            for (const f of FILLER_MULTI) {
                let idx = 0;
                while ((idx = lower.indexOf(f, idx)) !== -1) {
                    total++;
                    idx += f.length;
                }
            }
            const words = lower.split(/\s+/);
            for (const w of words) {
                const c = w.replace(/^[.,!?;:'"()\[\]{}]+|[.,!?;:'"()\[\]{}]+$/g, "");
                if (FILLER_SINGLE.has(c)) total++;
            }
        }
        return total;
    });

    /* ── Derived: Daily Activity (last 30 days) ── */
    let dailyActivity = $derived.by(() => {
        const DAYS = 30;
        const now = new Date();
        const buckets = new Map<string, { count: number; words: number }>();

        // Initialize all 30 days
        for (let i = DAYS - 1; i >= 0; i--) {
            const d = new Date(now);
            d.setDate(d.getDate() - i);
            const key = d.toISOString().slice(0, 10);
            buckets.set(key, { count: 0, words: 0 });
        }

        // Fill from entries
        for (const e of entries) {
            const key = e.timestamp?.slice(0, 10) ?? e.created_at?.slice(0, 10);
            if (key && buckets.has(key)) {
                const b = buckets.get(key)!;
                b.count++;
                b.words += e.text.split(/\s+/).filter(Boolean).length;
            }
        }

        return Array.from(buckets.entries()).map(([date, data]) => ({
            date,
            label: new Date(date + "T12:00:00").toLocaleDateString(undefined, { month: "short", day: "numeric" }),
            ...data,
        }));
    });

    let maxDailyWords = $derived(Math.max(1, ...dailyActivity.map((d) => d.words)));
    let totalActiveDays = $derived(dailyActivity.filter((d) => d.count > 0).length);

    let insight = $derived.by(() => {
        if (count < 3) return "Don't be shy! Record a bit more to see your Vociferous metrics!";
        const ratio = recordedSeconds > 0 ? typingSeconds / recordedSeconds : 0;
        if (ratio > 2.5) return `Speaking ${ratio.toFixed(1)}x faster than typing—voice is your superpower!`;
        if (ratio > 1.5) return "Dictation is significantly faster than typing for you! You're a certified yapper~";
        if (avgSeconds < 15) return "Quick-capture style: rapid-fire notes and thoughts. Keep that momentum going!";
        if (avgSeconds > 60)
            return "Deep-work style: long-form dictation sessions. Now that's what I'd call elite comms!";
        return "Consistent dictation is key—keep up the great work!";
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

    function formatCount(n: number): string {
        return n.toLocaleString();
    }

    /* ── Data loading ── */
    async function loadData() {
        loading = true;
        try {
            const [transcripts, health, config] = await Promise.all([
                getTranscripts(HISTORY_EXPORT_LIMIT),
                getHealth().catch(() => null),
                getConfig().catch(() => ({})),
            ]);
            entries = transcripts;
            healthInfo = health;
            // Extract user name from config
            const u = config as Record<string, unknown>;
            const userSection = u?.user as Record<string, unknown> | undefined;
            userName = (userSection?.name as string) ?? "";
        } catch (e) {
            console.error("Failed to load user data:", e);
        } finally {
            loading = false;
        }
    }

    /* ── Lifecycle ── */
    let unsubComplete: (() => void) | undefined;
    let unsubDeleted: (() => void) | undefined;

    onMount(() => {
        loadData();
        unsubComplete = ws.on("transcription_complete", () => loadData());
        unsubDeleted = ws.on("transcript_deleted", () => loadData());
    });

    onDestroy(() => {
        unsubComplete?.();
        unsubDeleted?.();
    });

    /* ── Explanations content ── */
    const explanations = [
        { title: "Transcriptions", text: "Total count of all transcription entries stored in your history database." },
        {
            title: "Words Captured",
            text: "Sum of word counts across all transcriptions. Each entry's words are counted individually.",
        },
        {
            title: "Time Recording",
            text: `Total recording duration in seconds. If duration is unavailable, estimated as: words ÷ ${SPEAKING_SPEED_WPM} WPM × 60 = seconds`,
        },
        {
            title: "Time Saved",
            text: `Productivity gain vs. manual typing. Calculated as: (words ÷ ${TYPING_SPEED_WPM} WPM × 60) − recording_time = time_saved. Based on average typing speed of ${TYPING_SPEED_WPM} WPM.`,
        },
        { title: "Average Length", text: "Mean duration per transcription: total_time ÷ transcription_count" },
        {
            title: "Total Silence",
            text: `Total accumulated silence (pauses) across all recordings. Calculated by summing the difference between actual recording duration and expected speech time for each entry.`,
        },
        {
            title: "Vocabulary",
            text: "Lexical complexity calculated as the ratio of unique words to total words across all transcriptions. Higher percentages indicate more diverse vocabulary usage.",
        },
        {
            title: "Average Pauses",
            text: `Estimated average silence per recording based on word density. Calculated by comparing actual recording duration against expected speech time (based on ${SPEAKING_SPEED_WPM} WPM).`,
        },
        {
            title: "Filler Words",
            text: "Total count of common filler words and phrases detected across all transcriptions. Includes patterns like 'um', 'uh', 'like', 'you know', 'basically', 'literally', 'actually', etc.",
        },
    ];
</script>

<div class="flex flex-col h-full bg-[var(--surface-primary)]">
    <!-- Scrollable Content -->
    <div class="flex-1 overflow-y-auto flex justify-center">
        <div
            class="w-full min-w-[var(--content-min-width)] py-[var(--space-5)] px-[var(--space-5)] flex flex-col gap-[var(--space-5)]"
        >
            {#if loading}
                <div class="flex flex-col items-center gap-[var(--space-3)] py-[96px] text-[var(--text-tertiary)]">
                    <div
                        class="w-8 h-8 border-[3px] border-[var(--shell-border)] border-t-[var(--accent)] rounded-full animate-spin"
                    ></div>
                    <p>Loading your statistics…</p>
                </div>
            {:else if !hasData}
                <!-- Empty State -->
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
                <!-- ═══ Statistics ═══ -->
                <section class="flex flex-col gap-[var(--space-5)]">
                    <div class="flex flex-col items-center gap-[var(--space-2)]">
                        <h2
                            class="text-[var(--text-xl)] font-[var(--weight-emphasis)] text-[var(--text-primary)] text-center m-0"
                        >
                            {titleText}
                        </h2>
                        <div class="w-12 h-[2px] rounded-full bg-[var(--accent)]"></div>
                        <p class="text-center text-[var(--text-sm)] text-[var(--accent)] italic m-0 max-w-[480px]">
                            {insight}
                        </p>
                    </div>

                    <!-- Group 1: Productivity Impact -->
                    <div class="flex flex-col gap-[var(--space-3)]">
                        <span
                            class="font-[var(--weight-emphasis)] text-[var(--text-xs)] text-[var(--text-tertiary)] uppercase tracking-[1px] text-center"
                            >Productivity Impact</span
                        >
                        <div class="grid grid-cols-2 gap-[var(--space-4)]">
                            <div
                                class="flex flex-col items-center gap-[var(--space-1)] p-[var(--space-5)] border border-[var(--accent-muted)] rounded-[var(--radius-lg)] bg-[var(--surface-secondary)] transition-[border-color] duration-[var(--transition-fast)] hover:border-[var(--accent)]"
                            >
                                <div class="text-[var(--accent)] mb-[var(--space-1)]"><Timer size={28} /></div>
                                <div
                                    class="text-[2.5rem] font-[var(--weight-emphasis)] text-[var(--accent)] leading-[var(--leading-tight)]"
                                >
                                    {formatDuration(timeSavedSeconds)}
                                </div>
                                <div
                                    class="text-[var(--text-sm)] font-[var(--weight-emphasis)] text-[var(--text-primary)]"
                                >
                                    Time Saved
                                </div>
                                <div class="text-[var(--text-xs)] text-[var(--text-tertiary)] text-center">
                                    vs manual typing
                                </div>
                            </div>
                            <div
                                class="flex flex-col items-center gap-[var(--space-1)] p-[var(--space-5)] border border-[var(--accent-muted)] rounded-[var(--radius-lg)] bg-[var(--surface-secondary)] transition-[border-color] duration-[var(--transition-fast)] hover:border-[var(--accent)]"
                            >
                                <div class="text-[var(--accent)] mb-[var(--space-1)]">
                                    <MessageSquareText size={28} />
                                </div>
                                <div
                                    class="text-[2.5rem] font-[var(--weight-emphasis)] text-[var(--accent)] leading-[var(--leading-tight)]"
                                >
                                    {formatCount(totalWords)}
                                </div>
                                <div
                                    class="text-[var(--text-sm)] font-[var(--weight-emphasis)] text-[var(--text-primary)]"
                                >
                                    Words Captured
                                </div>
                                <div class="text-[var(--text-xs)] text-[var(--text-tertiary)] text-center">
                                    Total transcribed words
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Group 2: Usage & Activity -->
                    <div class="flex flex-col gap-[var(--space-3)]">
                        <span
                            class="font-[var(--weight-emphasis)] text-[var(--text-xs)] text-[var(--text-tertiary)] uppercase tracking-[1px] text-center"
                            >Usage & Activity</span
                        >
                        <div class="grid grid-cols-4 gap-[var(--space-3)]">
                            <div
                                class="flex-1 flex flex-col items-center gap-1 p-[var(--space-4)] border border-[var(--shell-border)] rounded-[var(--radius-lg)] bg-[var(--surface-secondary)] transition-[border-color] duration-[var(--transition-fast)] hover:border-[var(--accent)]"
                            >
                                <div class="text-[var(--text-tertiary)] mb-1"><BarChart3 size={24} /></div>
                                <div
                                    class="text-[var(--text-lg)] font-[var(--weight-emphasis)] text-[var(--text-primary)]"
                                >
                                    {formatCount(count)}
                                </div>
                                <div
                                    class="text-[var(--text-sm)] font-[var(--weight-emphasis)] text-[var(--text-primary)]"
                                >
                                    Transcriptions
                                </div>
                                <div class="text-[var(--text-xs)] text-[var(--text-tertiary)] text-center">
                                    Total recordings
                                </div>
                            </div>
                            <div
                                class="flex-1 flex flex-col items-center gap-1 p-[var(--space-4)] border border-[var(--shell-border)] rounded-[var(--radius-lg)] bg-[var(--surface-secondary)] transition-[border-color] duration-[var(--transition-fast)] hover:border-[var(--accent)]"
                            >
                                <div class="text-[var(--text-tertiary)] mb-1"><Clock size={24} /></div>
                                <div
                                    class="text-[var(--text-lg)] font-[var(--weight-emphasis)] text-[var(--text-primary)]"
                                >
                                    {formatDuration(recordedSeconds)}
                                </div>
                                <div
                                    class="text-[var(--text-sm)] font-[var(--weight-emphasis)] text-[var(--text-primary)]"
                                >
                                    Time Recorded
                                </div>
                                <div class="text-[var(--text-xs)] text-[var(--text-tertiary)] text-center">
                                    Total audio duration
                                </div>
                            </div>
                            <div
                                class="flex-1 flex flex-col items-center gap-1 p-[var(--space-4)] border border-[var(--shell-border)] rounded-[var(--radius-lg)] bg-[var(--surface-secondary)] transition-[border-color] duration-[var(--transition-fast)] hover:border-[var(--accent)]"
                            >
                                <div class="text-[var(--text-tertiary)] mb-1"><Gauge size={24} /></div>
                                <div
                                    class="text-[var(--text-lg)] font-[var(--weight-emphasis)] text-[var(--text-primary)]"
                                >
                                    {formatDuration(avgSeconds)}
                                </div>
                                <div
                                    class="text-[var(--text-sm)] font-[var(--weight-emphasis)] text-[var(--text-primary)]"
                                >
                                    Avg. Length
                                </div>
                                <div class="text-[var(--text-xs)] text-[var(--text-tertiary)] text-center">
                                    Per recording
                                </div>
                            </div>
                            <div
                                class="flex-1 flex flex-col items-center gap-1 p-[var(--space-4)] border border-[var(--shell-border)] rounded-[var(--radius-lg)] bg-[var(--surface-secondary)] transition-[border-color] duration-[var(--transition-fast)] hover:border-[var(--accent)]"
                            >
                                <div class="text-[var(--text-tertiary)] mb-1"><PauseCircle size={24} /></div>
                                <div
                                    class="text-[var(--text-lg)] font-[var(--weight-emphasis)] text-[var(--text-primary)]"
                                >
                                    {totalSilence > 0 ? formatDuration(totalSilence) : "—"}
                                </div>
                                <div
                                    class="text-[var(--text-sm)] font-[var(--weight-emphasis)] text-[var(--text-primary)]"
                                >
                                    Total Silence
                                </div>
                                <div class="text-[var(--text-xs)] text-[var(--text-tertiary)] text-center">
                                    Accumulated pauses
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Group 3: Speech Quality -->
                    <div class="flex flex-col gap-[var(--space-3)]">
                        <span
                            class="font-[var(--weight-emphasis)] text-[var(--text-xs)] text-[var(--text-tertiary)] uppercase tracking-[1px] text-center"
                            >Speech Quality</span
                        >
                        <div class="grid grid-cols-3 gap-[var(--space-3)]">
                            <div
                                class="flex-1 flex flex-col items-center gap-1 p-[var(--space-4)] border border-[var(--shell-border)] rounded-[var(--radius-lg)] bg-[var(--surface-secondary)] transition-[border-color] duration-[var(--transition-fast)] hover:border-[var(--accent)]"
                            >
                                <div class="text-[var(--text-tertiary)] mb-1"><BookOpen size={24} /></div>
                                <div
                                    class="text-[var(--text-lg)] font-[var(--weight-emphasis)] text-[var(--text-primary)]"
                                >
                                    {lexicalComplexity > 0 ? formatPercent(lexicalComplexity) : "—"}
                                </div>
                                <div
                                    class="text-[var(--text-sm)] font-[var(--weight-emphasis)] text-[var(--text-primary)]"
                                >
                                    Vocabulary
                                </div>
                                <div class="text-[var(--text-xs)] text-[var(--text-tertiary)] text-center">
                                    Unique words ratio
                                </div>
                            </div>
                            <div
                                class="flex-1 flex flex-col items-center gap-1 p-[var(--space-4)] border border-[var(--shell-border)] rounded-[var(--radius-lg)] bg-[var(--surface-secondary)] transition-[border-color] duration-[var(--transition-fast)] hover:border-[var(--accent)]"
                            >
                                <div class="text-[var(--text-tertiary)] mb-1"><Volume2 size={24} /></div>
                                <div
                                    class="text-[var(--text-lg)] font-[var(--weight-emphasis)] text-[var(--text-primary)]"
                                >
                                    {avgSilence > 0 ? formatDuration(avgSilence) : "—"}
                                </div>
                                <div
                                    class="text-[var(--text-sm)] font-[var(--weight-emphasis)] text-[var(--text-primary)]"
                                >
                                    Avg. Pauses
                                </div>
                                <div class="text-[var(--text-xs)] text-[var(--text-tertiary)] text-center">
                                    Silence between speech
                                </div>
                            </div>
                            <div
                                class="flex-1 flex flex-col items-center gap-1 p-[var(--space-4)] border border-[var(--shell-border)] rounded-[var(--radius-lg)] bg-[var(--surface-secondary)] transition-[border-color] duration-[var(--transition-fast)] hover:border-[var(--accent)]"
                            >
                                <div class="text-[var(--text-tertiary)] mb-1"><MessageCircle size={24} /></div>
                                <div
                                    class="text-[var(--text-lg)] font-[var(--weight-emphasis)] text-[var(--text-primary)]"
                                >
                                    {fillerCount > 0 ? formatCount(fillerCount) : "—"}
                                </div>
                                <div
                                    class="text-[var(--text-sm)] font-[var(--weight-emphasis)] text-[var(--text-primary)]"
                                >
                                    Filler Words
                                </div>
                                <div class="text-[var(--text-xs)] text-[var(--text-tertiary)] text-center">
                                    um, uh, like, you know
                                </div>
                            </div>
                        </div>
                    </div>
                </section>

                <div class="h-px bg-[var(--shell-border)]"></div>

                <!-- ═══ Activity Over Time ═══ -->
                {#if count >= 2}
                    <section class="flex flex-col gap-[var(--space-3)]">
                        <h3
                            class="text-[var(--text-xs)] font-[var(--weight-emphasis)] text-[var(--text-tertiary)] text-center uppercase tracking-[1px] m-0"
                        >
                            Activity — Last 30 Days
                        </h3>
                        <div
                            class="flex justify-center gap-[var(--space-2)] text-[var(--text-xs)] text-[var(--text-muted)]"
                        >
                            <span class="font-[var(--weight-normal)]"
                                >{totalActiveDays} active day{totalActiveDays !== 1 ? "s" : ""}</span
                            >
                            <span class="opacity-40">·</span>
                            <span class="font-[var(--weight-normal)]"
                                >{formatCount(dailyActivity.reduce((s, d) => s + d.words, 0))} words</span
                            >
                        </div>
                        <div class="relative" role="img" aria-label="Daily transcription activity bar chart">
                            <svg
                                viewBox="0 0 {dailyActivity.length * 16} 120"
                                class="w-full h-[120px]"
                                preserveAspectRatio="none"
                            >
                                {#each dailyActivity as day, i}
                                    {@const barHeight = Math.max(
                                        day.words > 0 ? 4 : 0,
                                        (day.words / maxDailyWords) * 100,
                                    )}
                                    <rect
                                        x={i * 16 + 2}
                                        y={110 - barHeight}
                                        width="12"
                                        height={barHeight}
                                        rx="2"
                                        class="transition-opacity duration-[var(--transition-fast)] hover:opacity-100 {day.words ===
                                        0
                                            ? 'fill-[var(--surface-overlay)] opacity-30'
                                            : 'fill-[var(--accent)] opacity-85'}"
                                    >
                                        <title
                                            >{day.label}: {day.count} recording{day.count !== 1 ? "s" : ""}, {formatCount(
                                                day.words,
                                            )} words</title
                                        >
                                    </rect>
                                {/each}
                            </svg>
                            <div class="relative h-[18px] mt-[var(--space-1)]">
                                {#each dailyActivity as day, i}
                                    {#if i % 7 === 0 || i === dailyActivity.length - 1}
                                        <span
                                            class="absolute transform -translate-x-1/2 text-[10px] text-[var(--text-muted)] whitespace-nowrap"
                                            style="left: {((i * 16 + 8) / (dailyActivity.length * 16)) * 100}%"
                                        >
                                            {day.label}
                                        </span>
                                    {/if}
                                {/each}
                            </div>
                        </div>
                    </section>

                    <div class="h-px bg-[var(--shell-border)]"></div>
                {/if}

                <!-- ═══ Calculation Details (Collapsible) ═══ -->
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
                        <div class="flex flex-col gap-[var(--space-3)] w-full">
                            {#each explanations as exp}
                                <div
                                    class="text-center py-[var(--space-2)] px-0 text-[var(--text-sm)] leading-[1.6] text-[var(--text-secondary)]"
                                >
                                    <strong class="block text-[var(--text-primary)] mb-0.5">{exp.title}</strong>
                                    <span>{exp.text}</span>
                                </div>
                            {/each}
                        </div>
                    {/if}
                </section>
            {/if}

            <div class="h-px bg-[var(--shell-border)]"></div>

            <!-- ═══ About ═══ -->
            <footer
                class="rounded-[var(--radius-lg)] border border-[var(--shell-border)] bg-[var(--surface-secondary)] p-[var(--space-5)] flex flex-col items-center gap-[var(--space-3)] mb-[var(--space-4)]"
            >
                <h2 class="text-[var(--text-lg)] font-[var(--weight-emphasis)] text-[var(--accent)] m-0">Vociferous</h2>
                <p class="text-[var(--text-sm)] text-[var(--text-secondary)] m-0">Local AI Speech to Text</p>

                <p
                    class="text-[var(--text-sm)] text-[var(--text-tertiary)] text-center leading-[var(--leading-relaxed)] max-w-[520px] m-0"
                >
                    Powered by whisper.cpp and GGUF language models. Fully local, privacy-first speech-to-text that runs
                    entirely on your machine. No cloud, no data collection, no internet.
                </p>

                {#if healthInfo}
                    <p class="text-[var(--text-xs)] text-[var(--text-tertiary)] font-mono m-0">v{healthInfo.version}</p>
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
        </div>
    </div>
</div>
