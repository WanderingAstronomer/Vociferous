<script lang="ts">
    import { onMount } from "svelte";
    import { getTranscripts, getHealth, getConfig, getInsight, type Transcript } from "../lib/api";
    import { ws } from "../lib/ws";
    import StatCard from "../lib/components/StatCard.svelte";
    import ActivityChart from "../lib/components/ActivityChart.svelte";
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
    let slmInsight = $state("");

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

    let insight = $derived.by(() => {
        if (slmInsight) return slmInsight;
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
            const [transcripts, health, config, insightRes] = await Promise.all([
                getTranscripts(HISTORY_EXPORT_LIMIT),
                getHealth().catch(() => null),
                getConfig().catch(() => ({})),
                getInsight().catch(() => ({ text: "" })),
            ]);
            entries = transcripts;
            healthInfo = health;
            slmInsight = insightRes.text || "";
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
    onMount(() => {
        loadData();
        const unsubs = [
            ws.on("transcription_complete", () => loadData()),
            ws.on("transcript_deleted", () => loadData()),
            ws.on("insight_ready", (data) => {
                slmInsight = data.text || "";
            }),
        ];
        return () => unsubs.forEach((fn) => fn());
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
    <div class="flex-1 overflow-y-auto">
        <div
            class="w-full min-w-[var(--content-min-width)] mx-auto pt-[var(--space-5)] px-[var(--space-5)] flex flex-col gap-[var(--space-5)]"
        >
            {#if loading}
                <div class="flex flex-col items-center gap-[var(--space-3)] py-[96px] text-[var(--text-tertiary)]">
                    <div
                        class="w-8 h-8 border-[3px] border-[var(--shell-border)] border-t-[var(--accent)] rounded-full animate-spin"
                    ></div>
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

                <!-- ═══ 1. Activity Chart (period-selectable) ═══ -->
                {#if count >= 2}
                    <ActivityChart {entries} />
                {/if}

                <!-- ═══ 2. Productivity Impact (lifetime) ═══ -->
                <div class="flex flex-col gap-[var(--space-3)]">
                    <span
                        class="font-[var(--weight-emphasis)] text-[var(--text-xs)] text-[var(--text-tertiary)] uppercase tracking-[1px] text-center"
                        >Productivity Impact</span
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
                </div>

                <!-- ═══ 3. Usage & Activity (lifetime) ═══ -->
                <div class="flex flex-col gap-[var(--space-3)]">
                    <span
                        class="font-[var(--weight-emphasis)] text-[var(--text-xs)] text-[var(--text-tertiary)] uppercase tracking-[1px] text-center"
                        >Usage & Activity</span
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

                <!-- ═══ 4. Speech Quality (lifetime) ═══ -->
                <div class="flex flex-col gap-[var(--space-3)]">
                    <span
                        class="font-[var(--weight-emphasis)] text-[var(--text-xs)] text-[var(--text-tertiary)] uppercase tracking-[1px] text-center"
                        >Speech Quality</span
                    >
                    <div class="grid grid-cols-3 gap-[var(--space-3)]">
                        <StatCard
                            icon={BookOpen}
                            value={lexicalComplexity > 0 ? formatPercent(lexicalComplexity) : "—"}
                            label="Vocabulary"
                            sublabel="Unique words ratio"
                        />
                        <StatCard
                            icon={Volume2}
                            value={avgSilence > 0 ? formatDuration(avgSilence) : "—"}
                            label="Avg. Pauses"
                            sublabel="Silence between speech"
                        />
                        <StatCard
                            icon={MessageCircle}
                            value={fillerCount > 0 ? formatCount(fillerCount) : "—"}
                            label="Filler Words"
                            sublabel="um, uh, like, you know"
                        />
                    </div>
                </div>

                <div class="h-px bg-[var(--shell-border)]"></div>

                <!-- ═══ 5. Calculation Details (collapsible) ═══ -->
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

            <div class="h-px bg-[var(--shell-border)]"></div>

            <!-- ═══ 6. About ═══ -->
            <footer
                class="rounded-[var(--radius-lg)] border border-[var(--shell-border)] bg-[var(--surface-secondary)] p-[var(--space-5)] flex flex-col items-center gap-[var(--space-3)]"
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

            <div class="h-32"></div>
        </div>
    </div>
</div>
