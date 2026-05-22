<!--
    MarkdownEditor — Svelte 5 wrapper around TipTap with markdown I/O.

    WYSIWYG editor (Obsidian-style: see formatted output, edit inline).
    Source-of-truth value is a markdown string; component handles parse on
    init/external-update and serialize on every change.

    Two-way binding via `bind:value` — parent owns the markdown string,
    component edits it in place. External changes (e.g. new transcript
    loaded) reset the editor content; internal user edits propagate up.

    Uses tiptap-markdown for parse/serialize. StarterKit gives us
    headings, bold/italic, lists, blockquote, code, etc. — the core
    set Whisper/SLM output uses.

    When editable=true a formatting toolbar is shown above the content
    area. Toolbar state tracks the active marks/nodes at the cursor via
    TipTap's onTransaction hook. All toolbar commands use the chain API
    so focus is always returned to the editor after a button click.
-->
<script lang="ts">
    import { onMount, onDestroy } from "svelte";
    import { Editor } from "@tiptap/core";
    import StarterKit from "@tiptap/starter-kit";
    import { Markdown } from "tiptap-markdown";
    import {
        Bold, Italic, Strikethrough, Code, CodeXml,
        Heading1, Heading2, Heading3,
        List, ListOrdered, Quote,
    } from "lucide-svelte";

    interface Props {
        value: string;
        editable?: boolean;
        placeholder?: string;
        className?: string;
        onFocus?: () => void;
        onBlur?: () => void;
    }

    let {
        value = $bindable(""),
        editable = true,
        placeholder = "",
        className = "",
        onFocus,
        onBlur,
    }: Props = $props();

    let element: HTMLDivElement | undefined = $state();
    let editor: Editor | null = null;
    /** Guard so external `value` writes don't fight in-flight typing. */
    let applyingExternal = false;

    /** Active formatting at the current cursor/selection — refreshed on every transaction. */
    let fmt = $state({
        bold: false,
        italic: false,
        strike: false,
        code: false,
        h1: false,
        h2: false,
        h3: false,
        bullet: false,
        ordered: false,
        blockquote: false,
        codeBlock: false,
    });

    function refreshFmt(ed: Editor) {
        fmt = {
            bold: ed.isActive("bold"),
            italic: ed.isActive("italic"),
            strike: ed.isActive("strike"),
            code: ed.isActive("code"),
            h1: ed.isActive("heading", { level: 1 }),
            h2: ed.isActive("heading", { level: 2 }),
            h3: ed.isActive("heading", { level: 3 }),
            bullet: ed.isActive("bulletList"),
            ordered: ed.isActive("orderedList"),
            blockquote: ed.isActive("blockquote"),
            codeBlock: ed.isActive("codeBlock"),
        };
    }

    onMount(() => {
        if (!element) return;
        editor = new Editor({
            element,
            extensions: [
                StarterKit.configure({
                    // Markdown extension provides its own; avoid double-load.
                    codeBlock: { HTMLAttributes: { class: "md-codeblock" } },
                }),
                Markdown.configure({
                    html: false,
                    tightLists: true,
                    bulletListMarker: "-",
                    linkify: true,
                    breaks: true,
                    transformPastedText: true,
                    transformCopiedText: false,
                }),
            ],
            content: "",
            editable,
            editorProps: {
                attributes: {
                    class: "md-editor-surface",
                    "data-placeholder": placeholder,
                },
            },
            onUpdate: ({ editor: ed }) => {
                if (applyingExternal) return;
                // @ts-expect-error tiptap-markdown augments storage
                const md = ed.storage.markdown.getMarkdown() as string;
                if (md !== value) value = md;
            },
            onTransaction: ({ editor: ed }) => {
                refreshFmt(ed);
            },
            onFocus: () => onFocus?.(),
            onBlur: () => onBlur?.(),
        });
        // Seed initial content (parse the markdown string into the doc).
        if (value) {
            applyingExternal = true;
            editor.commands.setContent(value, { emitUpdate: false });
            applyingExternal = false;
        }
    });

    onDestroy(() => {
        editor?.destroy();
        editor = null;
    });

    // React to external value changes (parent swapped transcripts, etc.)
    // without clobbering mid-edit cursor position when the value already
    // matches what the editor currently holds.
    $effect(() => {
        if (!editor) return;
        // @ts-expect-error tiptap-markdown augments storage
        const current = editor.storage.markdown.getMarkdown() as string;
        if (value !== current) {
            applyingExternal = true;
            editor.commands.setContent(value || "", { emitUpdate: false });
            applyingExternal = false;
        }
    });

    $effect(() => {
        editor?.setEditable(editable);
    });
</script>

<div class="md-editor-wrapper {className}" class:is-readonly={!editable}>
    {#if editable}
        <div class="md-toolbar" role="toolbar" aria-label="Text formatting">
            <button
                class="tb-btn" class:is-active={fmt.bold}
                aria-pressed={fmt.bold}
                aria-label="Bold"
                onclick={() => editor?.chain().focus().toggleBold().run()}
                title="Bold (Ctrl+B)"
                type="button"
            ><Bold size={14} /></button>
            <button
                class="tb-btn" class:is-active={fmt.italic}
                aria-pressed={fmt.italic}
                aria-label="Italic"
                onclick={() => editor?.chain().focus().toggleItalic().run()}
                title="Italic (Ctrl+I)"
                type="button"
            ><Italic size={14} /></button>
            <button
                class="tb-btn" class:is-active={fmt.strike}
                aria-pressed={fmt.strike}
                aria-label="Strikethrough"
                onclick={() => editor?.chain().focus().toggleStrike().run()}
                title="Strikethrough (Ctrl+Shift+X)"
                type="button"
            ><Strikethrough size={14} /></button>
            <button
                class="tb-btn" class:is-active={fmt.code}
                aria-pressed={fmt.code}
                aria-label="Inline code"
                onclick={() => editor?.chain().focus().toggleCode().run()}
                title="Inline code (Ctrl+E)"
                type="button"
            ><Code size={14} /></button>

            <span class="tb-sep" aria-hidden="true"></span>

            <button
                class="tb-btn" class:is-active={fmt.h1}
                aria-pressed={fmt.h1}
                aria-label="Heading 1"
                onclick={() => editor?.chain().focus().toggleHeading({ level: 1 }).run()}
                title="Heading 1 (Ctrl+Alt+1)"
                type="button"
            ><Heading1 size={14} /></button>
            <button
                class="tb-btn" class:is-active={fmt.h2}
                aria-pressed={fmt.h2}
                aria-label="Heading 2"
                onclick={() => editor?.chain().focus().toggleHeading({ level: 2 }).run()}
                title="Heading 2 (Ctrl+Alt+2)"
                type="button"
            ><Heading2 size={14} /></button>
            <button
                class="tb-btn" class:is-active={fmt.h3}
                aria-pressed={fmt.h3}
                aria-label="Heading 3"
                onclick={() => editor?.chain().focus().toggleHeading({ level: 3 }).run()}
                title="Heading 3 (Ctrl+Alt+3)"
                type="button"
            ><Heading3 size={14} /></button>

            <span class="tb-sep" aria-hidden="true"></span>

            <button
                class="tb-btn" class:is-active={fmt.bullet}
                aria-pressed={fmt.bullet}
                aria-label="Bullet list"
                onclick={() => editor?.chain().focus().toggleBulletList().run()}
                title="Bullet list (Ctrl+Shift+8)"
                type="button"
            ><List size={14} /></button>
            <button
                class="tb-btn" class:is-active={fmt.ordered}
                aria-pressed={fmt.ordered}
                aria-label="Numbered list"
                onclick={() => editor?.chain().focus().toggleOrderedList().run()}
                title="Numbered list (Ctrl+Shift+7)"
                type="button"
            ><ListOrdered size={14} /></button>
            <button
                class="tb-btn" class:is-active={fmt.blockquote}
                aria-pressed={fmt.blockquote}
                aria-label="Blockquote"
                onclick={() => editor?.chain().focus().toggleBlockquote().run()}
                title="Blockquote (Ctrl+Shift+B)"
                type="button"
            ><Quote size={14} /></button>
            <button
                class="tb-btn" class:is-active={fmt.codeBlock}
                aria-pressed={fmt.codeBlock}
                aria-label="Code block"
                onclick={() => editor?.chain().focus().toggleCodeBlock().run()}
                title="Code block (Ctrl+Alt+C)"
                type="button"
            ><CodeXml size={14} /></button>
        </div>
    {/if}
    <div bind:this={element} class="md-editor-root"></div>
</div>

<style>
    .md-editor-wrapper {
        display: flex;
        flex-direction: column;
        width: 100%;
        height: 100%;
    }

    /* ── Toolbar ── */
    .md-toolbar {
        display: flex;
        align-items: center;
        flex-shrink: 0;
        gap: 1px;
        padding: 3px 6px;
        background: var(--surface-secondary);
        border-bottom: 1px solid var(--shell-border);
    }

    .tb-btn {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 26px;
        height: 26px;
        border: none;
        border-radius: 4px;
        background: transparent;
        color: var(--text-muted, #aaa);
        cursor: pointer;
        transition: background 0.1s, color 0.1s;
        flex-shrink: 0;
    }
    .tb-btn:hover {
        background: var(--surface-tertiary, rgba(127, 127, 127, 0.15));
        color: var(--text-primary, #eee);
    }
    .tb-btn.is-active {
        background: color-mix(in srgb, var(--accent, #4a9eff) 20%, transparent);
        color: var(--accent, #4a9eff);
    }

    .tb-sep {
        width: 1px;
        height: 18px;
        background: var(--shell-border);
        margin: 0 4px;
        flex-shrink: 0;
    }

    /* ── Editor surface ── */
    .md-editor-root {
        width: 100%;
        flex: 1;
        min-height: 0;
        overflow: auto;
    }
    .is-readonly .md-editor-root {
        height: 100%;
    }

    .md-editor-wrapper :global(.md-editor-surface) {
        outline: none;
        min-height: 100%;
        padding: var(--space-3, 0.75rem) var(--space-4, 1rem);
        font-size: var(--text-base, 0.95rem);
        line-height: 1.7;
        color: var(--text-primary, inherit);
        word-break: break-word;
    }

    .md-editor-wrapper :global(.md-editor-surface p.is-editor-empty:first-child::before) {
        content: attr(data-placeholder);
        color: var(--text-muted, #888);
        float: left;
        pointer-events: none;
        height: 0;
    }

    /* ── Prose typography ── */
    .md-editor-wrapper :global(h1),
    .md-editor-wrapper :global(h2),
    .md-editor-wrapper :global(h3),
    .md-editor-wrapper :global(h4) {
        font-weight: 600;
        line-height: 1.3;
        margin: 1em 0 0.4em;
    }
    .md-editor-wrapper :global(h1) { font-size: 1.6em; }
    .md-editor-wrapper :global(h2) { font-size: 1.35em; }
    .md-editor-wrapper :global(h3) { font-size: 1.15em; }
    .md-editor-wrapper :global(h4) { font-size: 1em; text-transform: uppercase; letter-spacing: 0.04em; opacity: 0.8; }

    .md-editor-wrapper :global(p) { margin: 0.6em 0; }
    .md-editor-wrapper :global(p:first-child) { margin-top: 0; }
    .md-editor-wrapper :global(p:last-child) { margin-bottom: 0; }

    /* Tailwind Preflight resets list-style to none — restore it explicitly. */
    .md-editor-wrapper :global(ul) {
        list-style-type: disc;
        padding-left: 1.5em;
        margin: 0.6em 0;
    }
    .md-editor-wrapper :global(ol) {
        list-style-type: decimal;
        padding-left: 1.5em;
        margin: 0.6em 0;
    }
    .md-editor-wrapper :global(ul ul)   { list-style-type: circle; }
    .md-editor-wrapper :global(ul ul ul) { list-style-type: square; }
    .md-editor-wrapper :global(li) { margin: 0.2em 0; }
    .md-editor-wrapper :global(li > p) { margin: 0.2em 0; }

    .md-editor-wrapper :global(blockquote) {
        border-left: 3px solid var(--accent, #888);
        padding: 0.2em 0.9em;
        margin: 0.8em 0;
        color: var(--text-secondary, inherit);
        opacity: 0.9;
    }

    .md-editor-wrapper :global(code) {
        background: var(--surface-secondary, rgba(127, 127, 127, 0.15));
        padding: 0.1em 0.35em;
        border-radius: 3px;
        font-size: 0.92em;
        font-family: var(--font-mono, ui-monospace, SFMono-Regular, monospace);
    }
    .md-editor-wrapper :global(pre),
    .md-editor-wrapper :global(.md-codeblock) {
        background: var(--surface-secondary, rgba(127, 127, 127, 0.12));
        padding: 0.8em 1em;
        border-radius: 6px;
        overflow-x: auto;
        margin: 0.8em 0;
    }
    .md-editor-wrapper :global(pre code) {
        background: transparent;
        padding: 0;
    }

    .md-editor-wrapper :global(strong) { font-weight: 600; }
    .md-editor-wrapper :global(em) { font-style: italic; }

    .md-editor-wrapper :global(a) {
        color: var(--accent, #4a9eff);
        text-decoration: underline;
        text-underline-offset: 2px;
    }

    .md-editor-wrapper :global(hr) {
        border: none;
        border-top: 1px solid var(--shell-border, rgba(127, 127, 127, 0.3));
        margin: 1.2em 0;
    }

    .is-readonly :global(.md-editor-surface) {
        cursor: default;
    }

    .md-editor-wrapper :global(::selection) {
        background: color-mix(in srgb, var(--accent, #4a9eff) 35%, transparent);
    }
</style>
