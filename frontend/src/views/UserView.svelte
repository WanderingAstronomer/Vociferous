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

<div class="user-view">
    <!-- Scrollable Content -->
    <div class="scroll-container">
        <div class="center-container">
            {#if loading}
                <div class="loading-state">
                    <div class="loading-spinner"></div>
                    <p>Loading your statistics…</p>
                </div>
            {:else if !hasData}
                <!-- Empty State -->
                <div class="empty-state">
                    <User size={40} strokeWidth={1.2} />
                    <h3>No metrics yet</h3>
                    <p>
                        Metrics appear after your first transcription is saved.<br />Try making a recording to see your
                        impact.
                    </p>
                </div>
            {:else}
                <!-- ═══ Statistics ═══ -->
                <section class="stats-section">
                    <h2 class="section-header">Lifetime Statistics</h2>
                    <p class="insight-text">{insight}</p>

                    <!-- Group 1: Productivity Impact -->
                    <div class="metric-group">
                        <span class="group-label">Productivity Impact</span>
                        <div class="metric-row highlight-row">
                            <div class="metric-card highlight">
                                <div class="metric-icon"><Timer size={28} /></div>
                                <div class="metric-value">{formatDuration(timeSavedSeconds)}</div>
                                <div class="metric-title">Time Saved</div>
                                <div class="metric-desc">vs manual typing</div>
                            </div>
                            <div class="metric-card highlight">
                                <div class="metric-icon"><MessageSquareText size={28} /></div>
                                <div class="metric-value">{formatCount(totalWords)}</div>
                                <div class="metric-title">Words Captured</div>
                                <div class="metric-desc">Total transcribed words</div>
                            </div>
                        </div>
                    </div>

                    <!-- Group 2: Usage & Activity -->
                    <div class="metric-group">
                        <span class="group-label">Usage & Activity</span>
                        <div class="metric-row">
                            <div class="metric-card">
                                <div class="metric-icon"><BarChart3 size={24} /></div>
                                <div class="metric-value">{formatCount(count)}</div>
                                <div class="metric-title">Transcriptions</div>
                                <div class="metric-desc">Total recordings</div>
                            </div>
                            <div class="metric-card">
                                <div class="metric-icon"><Clock size={24} /></div>
                                <div class="metric-value">{formatDuration(recordedSeconds)}</div>
                                <div class="metric-title">Time Recorded</div>
                                <div class="metric-desc">Total audio duration</div>
                            </div>
                            <div class="metric-card">
                                <div class="metric-icon"><Gauge size={24} /></div>
                                <div class="metric-value">{formatDuration(avgSeconds)}</div>
                                <div class="metric-title">Avg. Length</div>
                                <div class="metric-desc">Per recording</div>
                            </div>
                            <div class="metric-card">
                                <div class="metric-icon"><PauseCircle size={24} /></div>
                                <div class="metric-value">{totalSilence > 0 ? formatDuration(totalSilence) : "—"}</div>
                                <div class="metric-title">Total Silence</div>
                                <div class="metric-desc">Accumulated pauses</div>
                            </div>
                        </div>
                    </div>

                    <!-- Group 3: Speech Quality -->
                    <div class="metric-group">
                        <span class="group-label">Speech Quality</span>
                        <div class="metric-row">
                            <div class="metric-card">
                                <div class="metric-icon"><BookOpen size={24} /></div>
                                <div class="metric-value">
                                    {lexicalComplexity > 0 ? formatPercent(lexicalComplexity) : "—"}
                                </div>
                                <div class="metric-title">Vocabulary</div>
                                <div class="metric-desc">Unique words ratio</div>
                            </div>
                            <div class="metric-card">
                                <div class="metric-icon"><Volume2 size={24} /></div>
                                <div class="metric-value">{avgSilence > 0 ? formatDuration(avgSilence) : "—"}</div>
                                <div class="metric-title">Avg. Pauses</div>
                                <div class="metric-desc">Silence between speech</div>
                            </div>
                            <div class="metric-card">
                                <div class="metric-icon"><MessageCircle size={24} /></div>
                                <div class="metric-value">{fillerCount > 0 ? formatCount(fillerCount) : "—"}</div>
                                <div class="metric-title">Filler Words</div>
                                <div class="metric-desc">um, uh, like, you know</div>
                            </div>
                        </div>
                    </div>
                </section>

                <div class="section-divider"></div>

                <!-- ═══ Activity Over Time ═══ -->
                {#if count >= 2}
                    <section class="activity-section">
                        <h3 class="section-heading">Activity — Last 30 Days</h3>
                        <div class="activity-summary">
                            <span class="activity-stat">{totalActiveDays} active day{totalActiveDays !== 1 ? "s" : ""}</span>
                            <span class="activity-stat-sep">·</span>
                            <span class="activity-stat">{formatCount(dailyActivity.reduce((s, d) => s + d.words, 0))} words</span>
                        </div>
                        <div class="activity-chart" role="img" aria-label="Daily transcription activity bar chart">
                            <svg viewBox="0 0 {dailyActivity.length * 16} 120" class="chart-svg" preserveAspectRatio="none">
                                {#each dailyActivity as day, i}
                                    {@const barHeight = Math.max(day.words > 0 ? 4 : 0, (day.words / maxDailyWords) * 100)}
                                    <rect
                                        x={i * 16 + 2}
                                        y={110 - barHeight}
                                        width="12"
                                        height={barHeight}
                                        rx="2"
                                        class="chart-bar"
                                        class:chart-bar-empty={day.words === 0}
                                    >
                                        <title>{day.label}: {day.count} recording{day.count !== 1 ? "s" : ""}, {formatCount(day.words)} words</title>
                                    </rect>
                                {/each}
                            </svg>
                            <div class="chart-labels">
                                {#each dailyActivity as day, i}
                                    {#if i % 7 === 0 || i === dailyActivity.length - 1}
                                        <span class="chart-label" style="left: {((i * 16 + 8) / (dailyActivity.length * 16)) * 100}%">
                                            {day.label}
                                        </span>
                                    {/if}
                                {/each}
                            </div>
                        </div>
                    </section>

                    <div class="section-divider"></div>
                {/if}

                <!-- ═══ Calculation Details (Collapsible) ═══ -->
                <section class="explanations-section">
                    <button class="toggle-explanations" onclick={() => (showExplanations = !showExplanations)}>
                        {#if showExplanations}
                            <ChevronDown size={14} />
                            Hide Calculation Details
                        {:else}
                            <ChevronRight size={14} />
                            Show Calculation Details
                        {/if}
                    </button>

                    {#if showExplanations}
                        <div class="explanations-list">
                            {#each explanations as exp}
                                <div class="explanation-item">
                                    <strong>{exp.title}</strong>
                                    <span>{exp.text}</span>
                                </div>
                            {/each}
                        </div>
                    {/if}
                </section>
            {/if}

            <div class="section-divider"></div>

            <!-- ═══ About Section (Always visible) ═══ -->
            <footer class="about-section">
                <h2 class="about-title">Vociferous</h2>
                <p class="about-subtitle">Local AI Speech to Text</p>

                <p class="about-description">
                    Powered by whisper.cpp and GGUF language models. A fully local, privacy-first speech-to-text solution that runs
                    entirely on your machine. No cloud dependencies, no data collection, no internet required.
                </p>

                {#if healthInfo}
                    <p class="about-version">v{healthInfo.version}</p>
                {/if}

                <div class="about-links">
                    <a class="about-link" href="https://www.linkedin.com/in/abrown7521/" target="_blank" rel="noopener">
                        <Linkedin size={15} /> LinkedIn
                    </a>
                    <a
                        class="about-link"
                        href="https://github.com/WanderingAstronomer/Vociferous"
                        target="_blank"
                        rel="noopener"
                    >
                        <Github size={15} /> GitHub
                    </a>
                </div>

                <p class="about-creator">Created by Andrew Brown</p>
            </footer>
        </div>
    </div>
</div>

<style>
    /* ── Layout ── */
    .user-view {
        display: flex;
        flex-direction: column;
        height: 100%;
        background: var(--surface-primary);
    }

    /* ── Scroll Container ── */
    .scroll-container {
        flex: 1;
        overflow-y: auto;
        display: flex;
        justify-content: center;
    }

    .center-container {
        width: 100%;
        min-width: 600px;
        max-width: 960px;
        padding: var(--space-7) var(--space-6);
        display: flex;
        flex-direction: column;
        gap: var(--space-7);
    }

    /* ── Loading / Empty ── */
    .loading-state {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: var(--space-3);
        padding: 96px 0;
        color: var(--text-tertiary);
    }

    .loading-spinner {
        width: 32px;
        height: 32px;
        border: 3px solid var(--shell-border);
        border-top-color: var(--accent);
        border-radius: 50%;
        animation: spin 0.8s linear infinite;
    }

    .empty-state {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: var(--space-3);
        padding: 96px var(--space-6);
        color: var(--text-tertiary);
        text-align: center;
        border: 1px solid var(--shell-border);
        border-radius: var(--radius-lg);
        background: var(--surface-secondary);
    }

    .empty-state h3 {
        margin: 0;
        color: var(--text-primary);
        font-size: var(--text-lg);
    }

    .empty-state p {
        margin: 0;
        font-size: var(--text-sm);
        line-height: 1.6;
    }

    /* ── Statistics Section ── */
    .stats-section {
        display: flex;
        flex-direction: column;
        gap: var(--space-6);
    }

    .section-header {
        font-size: var(--text-xl);
        font-weight: var(--weight-emphasis);
        color: var(--text-primary);
        text-align: center;
        margin: 0;
    }

    .insight-text {
        text-align: center;
        font-size: var(--text-sm);
        color: var(--accent);
        font-style: italic;
        margin: 0;
    }

    /* ── Metric Groups ── */
    .metric-group {
        display: flex;
        flex-direction: column;
        gap: var(--space-3);
    }

    .group-label {
        font-weight: var(--weight-emphasis);
        font-size: var(--text-sm);
        color: var(--text-tertiary);
        text-transform: uppercase;
        letter-spacing: 0.5px;
        text-align: center;
    }

    .metric-row {
        display: flex;
        gap: var(--space-4);
    }

    .highlight-row {
        justify-content: center;
    }

    /* ── Metric Card ── */
    .metric-card {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 4px;
        padding: var(--space-4);
        border: 1px solid var(--shell-border);
        border-radius: var(--radius-lg);
        background: var(--surface-secondary);
        transition: border-color var(--transition-fast);
    }

    .metric-card:hover {
        border-color: var(--accent);
    }

    .metric-card.highlight {
        max-width: 280px;
    }

    .metric-icon {
        color: var(--text-tertiary);
        margin-bottom: 4px;
    }

    .metric-card.highlight .metric-icon {
        color: var(--accent);
    }

    .metric-value {
        font-size: var(--text-lg);
        font-weight: var(--weight-emphasis);
        color: var(--text-primary);
    }

    .metric-card.highlight .metric-value {
        font-size: 2.5rem;
        color: var(--accent);
    }

    .metric-title {
        font-size: var(--text-sm);
        font-weight: var(--weight-emphasis);
        color: var(--text-primary);
    }

    .metric-desc {
        font-size: var(--text-xs);
        color: var(--text-tertiary);
        text-align: center;
    }

    /* ── Activity Chart ── */
    .activity-section {
        display: flex;
        flex-direction: column;
        gap: var(--space-3);
    }

    .section-heading {
        font-size: var(--text-sm);
        font-weight: var(--weight-emphasis);
        color: var(--text-primary);
        text-align: center;
    }

    .activity-summary {
        display: flex;
        justify-content: center;
        gap: var(--space-2);
        font-size: var(--text-xs);
        color: var(--text-muted);
    }

    .activity-stat-sep {
        opacity: 0.4;
    }

    .activity-chart {
        position: relative;
    }

    .chart-svg {
        width: 100%;
        height: 120px;
    }

    .chart-bar {
        fill: var(--accent);
        opacity: 0.85;
        transition: opacity var(--transition-fast);
    }

    .chart-bar:hover {
        opacity: 1;
    }

    .chart-bar-empty {
        fill: var(--surface-overlay);
        opacity: 0.3;
    }

    .chart-labels {
        position: relative;
        height: 18px;
        margin-top: var(--space-1);
    }

    .chart-label {
        position: absolute;
        transform: translateX(-50%);
        font-size: 10px;
        color: var(--text-muted);
        white-space: nowrap;
    }

    /* ── Divider ── */
    .section-divider {
        height: 1px;
        background: var(--shell-border);
    }

    /* ── Explanations ── */
    .explanations-section {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: var(--space-4);
    }

    .toggle-explanations {
        display: flex;
        align-items: center;
        gap: var(--space-2);
        background: none;
        border: none;
        color: var(--text-secondary);
        font-size: var(--text-sm);
        cursor: pointer;
        padding: var(--space-2) var(--space-4);
        border-radius: var(--radius-md);
        transition:
            color var(--transition-fast),
            background var(--transition-fast);
    }

    .toggle-explanations:hover {
        color: var(--accent);
        background: var(--hover-overlay);
    }

    .explanations-list {
        display: flex;
        flex-direction: column;
        gap: var(--space-3);
        width: 100%;
    }

    .explanation-item {
        text-align: center;
        padding: var(--space-2) 0;
        font-size: var(--text-sm);
        line-height: 1.6;
        color: var(--text-secondary);
    }

    .explanation-item strong {
        display: block;
        color: var(--text-primary);
        margin-bottom: 2px;
    }

    /* ── About Section ── */
    .about-section {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: var(--space-3);
        padding-bottom: var(--space-7);
    }

    .about-title {
        font-size: var(--text-xl);
        font-weight: var(--weight-emphasis);
        color: var(--accent);
        margin: 0;
    }

    .about-subtitle {
        font-size: var(--text-base);
        color: var(--text-secondary);
        margin: 0;
    }

    .about-description {
        font-size: var(--text-base);
        color: var(--text-tertiary);
        text-align: center;
        line-height: 1.7;
        max-width: 560px;
        margin: 0;
    }

    .about-version {
        font-size: var(--text-xs);
        color: var(--text-tertiary);
        font-family: monospace;
        margin: 0;
    }

    .about-links {
        display: flex;
        gap: var(--space-4);
    }

    .about-link {
        display: flex;
        align-items: center;
        gap: var(--space-1);
        padding: var(--space-2) var(--space-4);
        border: 1px solid var(--shell-border);
        border-radius: var(--radius-md);
        color: var(--text-secondary);
        font-size: var(--text-sm);
        text-decoration: none;
        transition:
            color var(--transition-fast),
            border-color var(--transition-fast);
    }

    .about-link:hover {
        color: var(--accent);
        border-color: var(--accent);
    }

    .about-creator {
        font-size: var(--text-sm);
        color: var(--accent);
        margin: 0;
    }

    /* ── Spin ── */
    @keyframes spin {
        to {
            transform: rotate(360deg);
        }
    }
</style>
