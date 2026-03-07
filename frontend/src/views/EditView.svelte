<script lang="ts">
    /**
     * EditView — Dedicated transcript editor.
     *
     * A focused, single-purpose editing surface. No recording machinery.
     * Navigated to via nav.navigateToEdit(); returns to origin on save/discard.
     */

    import { onMount } from "svelte";
    import { nav } from "../lib/navigation.svelte";
    import { getTranscript, dispatchIntent, type Transcript } from "../lib/api";
    import { formatRelativeDate, formatDuration, wordCount } from "../lib/formatters";
    import StyledButton from "../lib/components/StyledButton.svelte";
    import { ArrowLeft, Check, X } from "lucide-svelte";

    /* ===== State ===== */

    let transcript = $state<Transcript | null>(null);
    let editText = $state("");
    let loading = $state(true);
    let saving = $state(false);
    let error = $state("");

    /* ===== Derived ===== */

    let originalText = $derived(transcript ? transcript.normalized_text || transcript.raw_text || "" : "");
    let isDirty = $derived(editText !== originalText);
    let wc = $derived(wordCount(editText));

    /* ===== Helpers ===== */

    function getTitle(t: Transcript): string {
        return t.display_name?.trim() || `Transcript #${t.id}`;
    }

    function tagColor(tag: { color: string | null }): string {
        return tag.color ?? "var(--accent)";
    }

    /* ===== Actions ===== */

    async function load(id: number) {
        loading = true;
        error = "";
        try {
            transcript = await getTranscript(id);
            editText = transcript.normalized_text || transcript.raw_text || "";
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
            nav.completeEditSession();
        } catch (e: any) {
            error = e.message;
            saving = false;
        }
    }

    function discard() {
        nav.completeEditSession();
    }

    function handleKeydown(e: KeyboardEvent) {
        if ((e.ctrlKey || e.metaKey) && e.key === "s") {
            e.preventDefault();
            save();
        }
        if (e.key === "Escape") {
            discard();
        }
    }

    /* ===== Lifecycle ===== */

    onMount(() => {
        const id = nav.consumePendingTranscript();
        if (id !== null) {
            load(id);
        } else {
            // Nothing to edit — bail
            nav.completeEditSession();
        }
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
                <h1 class="text-[18px] font-semibold text-[var(--text-primary)] leading-snug truncate m-0">
                    {getTitle(transcript)}
                </h1>
                <div class="flex items-center gap-3 mt-1 flex-wrap">
                    <span class="text-[13px] text-[var(--text-tertiary)]">
                        {formatRelativeDate(transcript.created_at)}
                    </span>
                    <span class="text-[13px] text-[var(--text-tertiary)]">
                        {formatDuration(transcript.duration_ms)}
                    </span>
                    {#each transcript.tags as tag (tag.id)}
                        <span
                            class="inline-flex items-center gap-1 h-5 px-1.5 rounded-full text-[11px] font-medium"
                            style="background: color-mix(in srgb, {tagColor(
                                tag,
                            )} 25%, transparent); color: var(--text-primary);"
                        >
                            <span class="w-1.5 h-1.5 rounded-full" style="background: {tagColor(tag)}"></span>
                            {tag.name}
                        </span>
                    {/each}
                </div>
            {:else if loading}
                <div class="h-7 w-48 bg-[var(--hover-overlay)] rounded animate-pulse"></div>
            {/if}
        </div>
    </div>

    <!-- ── Editor ── -->
    <div class="flex-1 overflow-hidden px-5 py-3">
        {#if loading}
            <div class="flex items-center justify-center h-full text-[var(--text-tertiary)] text-sm">Loading…</div>
        {:else if error}
            <div class="flex items-center justify-center h-full text-[var(--color-danger)] text-sm">
                {error}
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
    <div
        class="shrink-0 flex items-center gap-2 px-5 py-3 border-t border-[var(--shell-border)] bg-[var(--surface-secondary)]"
    >
        <!-- Word count -->
        <span class="text-[13px] text-[var(--text-tertiary)] tabular-nums">
            {wc.toLocaleString()} word{wc !== 1 ? "s" : ""}
        </span>

        {#if isDirty}
            <span class="text-[12px] text-[var(--accent)] ml-1">● edited</span>
        {/if}

        {#if error}
            <span class="text-[12px] text-[var(--color-danger)] ml-1">{error}</span>
        {/if}

        <div class="flex-1"></div>

        <StyledButton size="sm" variant="secondary" onclick={discard}>
            <X size={13} /> Discard
        </StyledButton>

        <StyledButton size="sm" variant="primary" onclick={save} disabled={!isDirty || saving}>
            <Check size={13} />
            {saving ? "Saving…" : "Save"}
        </StyledButton>
    </div>
</div>
