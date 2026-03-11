<script lang="ts">
    /**
     * EditView — Dedicated transcript editor.
     *
     * A focused, single-purpose editing surface with tag management,
     * statistics, and revert-to-raw. Navigated to via nav.navigateToEdit();
     * returns to origin on save/discard.
     */

    import { onMount, onDestroy } from "svelte";
    import { nav } from "../lib/navigation.svelte";
    import {
        getTranscript,
        getTags,
        createTag,
        deleteTag,
        updateTag,
        assignTags,
        dispatchIntent,
        renameTranscript,
        retranscribeTranscript,
        type Transcript,
        type Tag,
    } from "../lib/api";
    import { ws } from "../lib/ws";
    import { toast } from "../lib/toast.svelte";
    import { formatRelativeDate, formatDuration, wordCount, formatWpm } from "../lib/formatters";
    import { countFillers, fleschKincaidGrade } from "../lib/textAnalysis";
    import StyledButton from "../lib/components/StyledButton.svelte";
    import TagBar from "../lib/components/TagBar.svelte";
    import ActionBar from "../lib/components/ActionBar.svelte";
    import ToggleSwitch from "../lib/components/ToggleSwitch.svelte";
    import MarkdownBody from "../lib/components/MarkdownBody.svelte";
    import { getConfig } from "../lib/api";
    import { ArrowLeft, Check, X, Hammer, RotateCcw, Pencil, Copy, RefreshCw } from "lucide-svelte";

    /* ===== State ===== */

    let transcript = $state<Transcript | null>(null);
    let editText = $state("");
    let loading = $state(true);
    let saving = $state(false);
    let error = $state("");
    let copied = $state(false);
    let allTags: Tag[] = $state([]);
    let tagMenuOpen = $state(false);
    let editingTitle = $state(false);
    let titleDraft = $state("");
    let showMarkdownPreview = $state(false);

    /* ===== Derived ===== */

    let originalText = $derived(transcript ? transcript.normalized_text || transcript.raw_text || "" : "");
    let isDirty = $derived(editText !== originalText);
    let wc = $derived(wordCount(editText));
    let fillerCount = $derived(editText ? countFillers(editText) : 0);
    let fkGrade = $derived(wc >= 3 ? fleschKincaidGrade(editText) : null);
    let speechPct = $derived.by(() => {
        const d = transcript?.duration_ms;
        const s = transcript?.speech_duration_ms;
        if (!d || !s || d <= 0) return null;
        return Math.round((s / d) * 100);
    });
    let assignedTagIds = $derived(new Set(transcript?.tags.map((t) => t.id) ?? []));
    let isRefined = $derived(transcript?.tags.some((t) => t.is_system && t.name === "Refined") ?? false);

    /* ===== Helpers ===== */

    function getTitle(t: Transcript): string {
        return t.display_name?.trim() || `Transcript #${t.id}`;
    }

    /* ===== Actions ===== */

    function startTitleEdit() {
        if (!transcript) return;
        titleDraft = transcript.display_name?.trim() || "";
        editingTitle = true;
    }

    async function commitTitleEdit() {
        if (!transcript?.id) return;
        const trimmed = titleDraft.trim();
        if (!trimmed) {
            editingTitle = false;
            return;
        }
        try {
            await renameTranscript(transcript.id, trimmed);
            transcript = await getTranscript(transcript.id);
            toast.success("Title updated");
        } catch (e: any) {
            toast.error(`Rename failed: ${e.message}`);
        } finally {
            editingTitle = false;
        }
    }

    function cancelTitleEdit() {
        editingTitle = false;
    }

    function handleTitleKeydown(e: KeyboardEvent) {
        if (e.key === "Enter") {
            e.preventDefault();
            commitTitleEdit();
        } else if (e.key === "Escape") {
            e.preventDefault();
            e.stopPropagation();
            cancelTitleEdit();
        }
    }

    async function load(id: number) {
        loading = true;
        error = "";
        try {
            const [t, tags] = await Promise.all([getTranscript(id), getTags()]);
            transcript = t;
            allTags = tags;
            editText = t.normalized_text || t.raw_text || "";
        } catch (e: any) {
            error = e.message;
        } finally {
            loading = false;
        }
    }

    async function save() {
        if (!transcript?.id || !editText.trim() || saving) return;
        saving = true;
        error = "";
        try {
            await dispatchIntent("commit_edits", {
                transcript_id: transcript.id,
                content: editText.trim(),
            });
            toast.success("Changes saved");
            nav.completeEditSession();
        } catch (e: any) {
            error = e.message;
            toast.error(`Save failed: ${e.message}`);
            saving = false;
        }
    }

    function discard() {
        nav.completeEditSession();
    }

    async function revertToRaw() {
        if (!transcript?.id || !isRefined) return;
        const confirmed = await toast.confirm({
            title: "Revert to original text?",
            message:
                "This will discard the refined version and restore the original captured text. The Refined tag will be removed.",
            confirmLabel: "Revert",
            cancelLabel: "Keep refined",
            danger: true,
        });
        if (!confirmed) return;
        try {
            await dispatchIntent("revert_to_raw", {
                transcript_id: transcript.id,
            });
            // Reload to reflect changes
            transcript = await getTranscript(transcript.id);
            editText = transcript.normalized_text || transcript.raw_text || "";
            toast.success("Reverted to original text");
        } catch (e: any) {
            toast.error(`Revert failed: ${e.message}`);
        }
    }

    async function toggleAnalyticsInclusion() {
        if (!transcript?.id) return;
        const newValue = !transcript.include_in_analytics;
        // Optimistic update
        transcript = { ...transcript, include_in_analytics: newValue };
        try {
            await dispatchIntent("set_analytics_inclusion", {
                transcript_id: transcript.id,
                include: newValue,
            });
        } catch (e: any) {
            // Rollback
            transcript = { ...transcript, include_in_analytics: !newValue };
            toast.error(`Failed to update analytics setting: ${e.message}`);
        }
    }

    /* ===== Tag Actions ===== */

    async function handleTagToggle(tagId: number) {
        if (!transcript?.id) return;
        const currentIds = transcript.tags.map((t) => t.id);
        const newIds = currentIds.includes(tagId) ? currentIds.filter((id) => id !== tagId) : [...currentIds, tagId];
        try {
            await assignTags(transcript.id, newIds);
            transcript = await getTranscript(transcript.id);
        } catch (e: any) {
            toast.error(`Tag update failed: ${e.message}`);
        }
    }

    async function handleTagCreate(name: string, color: string) {
        try {
            await createTag(name, color);
            allTags = await getTags();
            toast.success(`Tag "${name}" created`);
        } catch (e: any) {
            toast.error(`Tag creation failed: ${e.message}`);
        }
    }

    async function handleTagDelete(tagId: number) {
        try {
            await deleteTag(tagId);
            allTags = await getTags();
            if (transcript?.id) transcript = await getTranscript(transcript.id);
            toast.success("Tag deleted");
        } catch (e: any) {
            toast.error(`Tag deletion failed: ${e.message}`);
        }
    }

    async function handleTagColorChange(tagId: number, color: string) {
        try {
            await updateTag(tagId, { color });
            allTags = await getTags();
            if (transcript?.id) transcript = await getTranscript(transcript.id);
        } catch (e: any) {
            toast.error(`Failed to update tag color: ${e.message}`);
        }
    }

    /* ===== Keyboard ===== */

    function handleKeydown(e: KeyboardEvent) {
        if ((e.ctrlKey || e.metaKey) && e.key === "s") {
            e.preventDefault();
            save();
        }
        if (e.key === "Escape") {
            if (tagMenuOpen) return;
            discard();
        }
    }

    /* ===== Lifecycle & WebSocket ===== */

    let unsubs: (() => void)[] = [];

    onMount(async () => {
        try {
            const cfg = await getConfig();
            const display = cfg.display as Record<string, unknown> | undefined;
            showMarkdownPreview = Boolean(display?.render_markdown_in_editor);
        } catch {
            /* fall back to default false */
        }

        const id = nav.consumePendingTranscript();
        if (id !== null) {
            load(id);
        } else {
            nav.completeEditSession();
        }

        unsubs = [
            ws.on("tag_created", async () => {
                allTags = await getTags();
            }),
            ws.on("tag_updated", async () => {
                allTags = await getTags();
            }),
            ws.on("tag_deleted", async () => {
                allTags = await getTags();
                if (transcript?.id) transcript = await getTranscript(transcript.id);
            }),
            ws.on("transcript_updated", async (data) => {
                if (transcript?.id && data.id === transcript.id) {
                    transcript = await getTranscript(transcript.id);
                }
            }),
        ];
    });

    onDestroy(() => {
        unsubs.forEach((fn) => fn());
    });
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="flex flex-col h-full overflow-hidden bg-[var(--surface-primary)]">
    <!-- ── Header ── -->
    <div class="shrink-0 flex items-start gap-3 px-5 pt-4 pb-3 border-b border-[var(--shell-border)]">
        <button
            class="mt-0.5 shrink-0 w-7 h-7 rounded-lg flex items-center justify-center bg-transparent border-none text-[var(--text-tertiary)] hover:text-[var(--text-primary)] hover:bg-[var(--hover-overlay)] cursor-pointer transition-colors"
            onclick={discard}
            title="Discard and go back (Esc)"
        >
            <ArrowLeft size={16} />
        </button>

        <div class="flex-1 min-w-0">
            {#if transcript}
                {#if editingTitle}
                    <div class="flex items-center gap-2 min-w-0">
                        <!-- svelte-ignore a11y_autofocus -->
                        <input
                            type="text"
                            class="flex-1 min-w-0 h-8 text-[18px] font-semibold text-[var(--text-primary)] bg-[var(--surface-secondary)] border border-[var(--shell-border)] rounded-[var(--radius-md)] px-2 outline-none focus:border-[var(--accent)]"
                            maxlength="120"
                            bind:value={titleDraft}
                            onkeydown={handleTitleKeydown}
                            onblur={commitTitleEdit}
                            autofocus
                        />
                        <button
                            class="shrink-0 w-7 h-7 rounded-lg flex items-center justify-center bg-transparent border-none text-[var(--accent)] hover:bg-[var(--hover-overlay)] cursor-pointer"
                            onmousedown={(e: MouseEvent) => {
                                e.preventDefault();
                                commitTitleEdit();
                            }}
                            title="Confirm rename"
                        >
                            <Check size={14} />
                        </button>
                        <button
                            class="shrink-0 w-7 h-7 rounded-lg flex items-center justify-center bg-transparent border-none text-[var(--text-tertiary)] hover:bg-[var(--hover-overlay)] cursor-pointer"
                            onmousedown={(e: MouseEvent) => {
                                e.preventDefault();
                                cancelTitleEdit();
                            }}
                            title="Cancel rename"
                        >
                            <X size={14} />
                        </button>
                    </div>
                {:else}
                    <button
                        class="group/title flex items-center gap-1.5 bg-transparent border-none p-0 cursor-pointer text-left min-w-0 max-w-full"
                        onclick={startTitleEdit}
                        title="Click to rename"
                    >
                        <h1 class="text-[18px] font-semibold text-[var(--text-primary)] leading-snug truncate m-0">
                            {getTitle(transcript)}
                        </h1>
                        <Pencil
                            size={13}
                            class="shrink-0 text-[var(--text-tertiary)] opacity-0 group-hover/title:opacity-100 transition-opacity"
                        />
                    </button>
                {/if}
                <div class="flex items-center gap-3 mt-1 flex-wrap">
                    <span class="text-[13px] text-[var(--text-tertiary)]">
                        {formatRelativeDate(transcript.created_at)}
                    </span>
                    <span class="text-[13px] text-[var(--text-tertiary)]">
                        {formatDuration(transcript.duration_ms)}
                    </span>
                </div>
            {:else if loading}
                <div class="h-7 w-48 bg-[var(--hover-overlay)] rounded animate-pulse"></div>
            {/if}
        </div>

        {#if transcript}
            <div class="shrink-0 flex items-center gap-3 mt-0.5">
                <div class="flex items-center gap-1.5" title="Render transcript text as markdown">
                    <span class="text-[12px] text-[var(--text-tertiary)] whitespace-nowrap select-none">Markdown</span>
                    <ToggleSwitch
                        size="sm"
                        checked={showMarkdownPreview}
                        onChange={() => (showMarkdownPreview = !showMarkdownPreview)}
                    />
                </div>
                <div class="flex items-center gap-1.5" title="Toggle analytics inclusion">
                    <span class="text-[12px] text-[var(--text-tertiary)] whitespace-nowrap select-none"
                        >Include in analytics</span
                    >
                    <ToggleSwitch
                        size="sm"
                        checked={transcript.include_in_analytics}
                        onChange={toggleAnalyticsInclusion}
                    />
                </div>
            </div>
        {/if}
    </div>

    <!-- ── Refined Banner ── -->
    {#if isRefined}
        <div
            class="shrink-0 flex items-center gap-2 px-5 py-2 bg-[color-mix(in_srgb,var(--accent)_8%,transparent)] border-b border-[var(--shell-border)]"
        >
            <Hammer size={13} class="text-[var(--accent)] shrink-0" />
            <span class="text-[13px] text-[var(--text-secondary)]">
                This transcript has been refined. Original text is preserved.
            </span>
            <div class="flex-1"></div>
            <StyledButton size="sm" variant="secondary" onclick={revertToRaw}>
                <RotateCcw size={12} /> Revert to original
            </StyledButton>
        </div>
    {/if}

    <!-- ── Tag Bar ── -->
    {#if !loading && transcript}
        <div class="shrink-0 px-5 py-2 border-b border-[var(--shell-border)]">
            <TagBar
                tags={allTags}
                activeIds={assignedTagIds}
                ontoggle={handleTagToggle}
                oncreate={handleTagCreate}
                ondelete={handleTagDelete}
                oncolorchange={handleTagColorChange}
                onmenuchange={(open) => (tagMenuOpen = open)}
            />
        </div>
    {/if}

    <!-- ── Editor ── -->
    <div class="flex-1 overflow-hidden px-5 py-3">
        {#if loading}
            <div class="flex items-center justify-center h-full text-[var(--text-tertiary)] text-sm">Loading…</div>
        {:else if error}
            <div class="flex items-center justify-center h-full text-[var(--color-danger)] text-sm">
                {error}
            </div>
        {:else if showMarkdownPreview}
            <div
                class="w-full h-full overflow-y-auto bg-[var(--surface-secondary)] border border-[var(--shell-border)] rounded-lg p-4"
            >
                <MarkdownBody text={editText} className="text-[15px] text-[var(--text-primary)]" />
            </div>
        {:else}
            <textarea
                class="w-full h-full resize-none bg-[var(--surface-secondary)] border border-[var(--shell-border)] rounded-lg text-[var(--text-primary)] text-[15px] leading-relaxed p-4 outline-none transition-colors focus:border-[var(--accent)] font-sans"
                bind:value={editText}
                spellcheck={true}
                placeholder="Transcript text…"
            ></textarea>
        {/if}
    </div>

    <!-- ── Footer ── -->
    <ActionBar>
        <StyledButton size="sm" variant="destructive" onclick={discard}>
            <X size={13} /> Discard
        </StyledButton>

        <StyledButton
            size="sm"
            variant="secondary"
            disabled={!transcript?.has_audio_cached}
            title={transcript?.has_audio_cached
                ? "Re-run transcription using this transcript's cached audio"
                : "Re-transcribe unavailable: no cached audio for this transcript"}
            onclick={async () => {
                if (!transcript?.has_audio_cached) return;
                try {
                    await retranscribeTranscript(transcript.id);
                    toast.info("Re-transcription queued");
                } catch {
                    toast.error("Failed to queue re-transcription");
                }
            }}
        >
            <RefreshCw size={13} /> Re-transcribe
        </StyledButton>

        <div class="flex-1"></div>

        <!-- Statistics strip -->
        <span class="text-[13px] text-[var(--text-tertiary)] tabular-nums">
            {wc.toLocaleString()} word{wc !== 1 ? "s" : ""}
        </span>

        {#if transcript?.duration_ms}
            <span class="text-[11px] text-[var(--text-tertiary)]">·</span>
            <span class="text-[13px] text-[var(--text-tertiary)] tabular-nums">
                {formatDuration(transcript.duration_ms)}
            </span>
            <span class="text-[11px] text-[var(--text-tertiary)]">·</span>
            <span class="text-[13px] text-[var(--text-tertiary)] tabular-nums">
                {formatWpm(wc, transcript.duration_ms)}
            </span>
        {/if}

        {#if speechPct !== null}
            <span class="text-[11px] text-[var(--text-tertiary)]">·</span>
            <span class="text-[13px] text-[var(--text-tertiary)] tabular-nums">{speechPct}% speech</span>
        {/if}

        {#if fkGrade !== null}
            <span class="text-[11px] text-[var(--text-tertiary)]">·</span>
            <span class="text-[13px] text-[var(--text-tertiary)] tabular-nums">Grade {fkGrade}</span>
        {/if}

        {#if fillerCount > 0}
            <span class="text-[11px] text-[var(--text-tertiary)]">·</span>
            <span class="text-[13px] text-[var(--text-tertiary)] tabular-nums">
                {fillerCount} filler{fillerCount !== 1 ? "s" : ""}{wc > 0
                    ? ` (${((fillerCount / wc) * 100).toFixed(1)}%)`
                    : ""}
            </span>
        {/if}

        {#if isDirty}
            <span class="text-[12px] text-[var(--accent)] ml-1">● edited</span>
        {/if}

        {#if error}
            <span class="text-[12px] text-[var(--color-danger)] ml-1">{error}</span>
        {/if}

        <div class="flex-1"></div>

        <StyledButton
            size="sm"
            variant="secondary"
            onclick={() => {
                if (editText) {
                    navigator.clipboard.writeText(editText);
                    copied = true;
                    setTimeout(() => (copied = false), 1500);
                }
            }}
        >
            {#if copied}
                <Check size={13} /> Copied
            {:else}
                <Copy size={13} /> Copy
            {/if}
        </StyledButton>

        <StyledButton size="sm" variant="primary" onclick={save} disabled={!isDirty || saving}>
            <Check size={13} />
            {saving ? "Saving…" : "Save"}
        </StyledButton>
    </ActionBar>
</div>
