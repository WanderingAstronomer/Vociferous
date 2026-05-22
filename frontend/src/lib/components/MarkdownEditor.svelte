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
-->
<script lang="ts">
    import { onMount, onDestroy } from "svelte";
    import { Editor } from "@tiptap/core";
    import StarterKit from "@tiptap/starter-kit";
    import { Markdown } from "tiptap-markdown";

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

<div bind:this={element} class="md-editor-root {className}" class:is-readonly={!editable}></div>

<style>
    .md-editor-root {
        width: 100%;
        height: 100%;
        overflow: auto;
    }

    .md-editor-root :global(.md-editor-surface) {
        outline: none;
        min-height: 100%;
        padding: var(--space-3, 0.75rem) var(--space-4, 1rem);
        font-size: var(--text-base, 0.95rem);
        line-height: 1.7;
        color: var(--text-primary, inherit);
        word-break: break-word;
    }

    .md-editor-root :global(.md-editor-surface p.is-editor-empty:first-child::before) {
        content: attr(data-placeholder);
        color: var(--text-muted, #888);
        float: left;
        pointer-events: none;
        height: 0;
    }

    /* Prose-style typography that inherits app tokens. */
    .md-editor-root :global(h1),
    .md-editor-root :global(h2),
    .md-editor-root :global(h3),
    .md-editor-root :global(h4) {
        font-weight: 600;
        line-height: 1.3;
        margin: 1em 0 0.4em;
    }
    .md-editor-root :global(h1) { font-size: 1.6em; }
    .md-editor-root :global(h2) { font-size: 1.35em; }
    .md-editor-root :global(h3) { font-size: 1.15em; }
    .md-editor-root :global(h4) { font-size: 1em; text-transform: uppercase; letter-spacing: 0.04em; opacity: 0.8; }

    .md-editor-root :global(p) {
        margin: 0.6em 0;
    }
    .md-editor-root :global(p:first-child) { margin-top: 0; }
    .md-editor-root :global(p:last-child) { margin-bottom: 0; }

    .md-editor-root :global(ul),
    .md-editor-root :global(ol) {
        padding-left: 1.5em;
        margin: 0.6em 0;
    }
    .md-editor-root :global(li) { margin: 0.2em 0; }
    .md-editor-root :global(li > p) { margin: 0.2em 0; }

    .md-editor-root :global(blockquote) {
        border-left: 3px solid var(--accent, #888);
        padding: 0.2em 0.9em;
        margin: 0.8em 0;
        color: var(--text-secondary, inherit);
        opacity: 0.9;
    }

    .md-editor-root :global(code) {
        background: var(--surface-secondary, rgba(127, 127, 127, 0.15));
        padding: 0.1em 0.35em;
        border-radius: 3px;
        font-size: 0.92em;
        font-family: var(--font-mono, ui-monospace, SFMono-Regular, monospace);
    }
    .md-editor-root :global(pre),
    .md-editor-root :global(.md-codeblock) {
        background: var(--surface-secondary, rgba(127, 127, 127, 0.12));
        padding: 0.8em 1em;
        border-radius: 6px;
        overflow-x: auto;
        margin: 0.8em 0;
    }
    .md-editor-root :global(pre code) {
        background: transparent;
        padding: 0;
    }

    .md-editor-root :global(strong) { font-weight: 600; }
    .md-editor-root :global(em) { font-style: italic; }

    .md-editor-root :global(a) {
        color: var(--accent, #4a9eff);
        text-decoration: underline;
        text-underline-offset: 2px;
    }

    .md-editor-root :global(hr) {
        border: none;
        border-top: 1px solid var(--shell-border, rgba(127, 127, 127, 0.3));
        margin: 1.2em 0;
    }

    .is-readonly :global(.md-editor-surface) {
        cursor: default;
    }

    /* Selection color uses accent for consistency with rest of app. */
    .md-editor-root :global(::selection) {
        background: color-mix(in srgb, var(--accent, #4a9eff) 35%, transparent);
    }
</style>
