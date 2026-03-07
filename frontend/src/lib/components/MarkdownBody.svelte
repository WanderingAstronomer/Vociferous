<!--
    MarkdownBody — renders a markdown string as styled HTML.

    Uses `marked` for parsing + `{@html}` for injection. All content
    originates from the local ASR/SLM pipeline, never from untrusted
    user input, so we skip a full DOMPurify dependency.

    Clipboard copies should always use the raw markdown string directly
    (handled by the caller), NOT the rendered HTML.
-->
<script lang="ts">
    import { marked } from "marked";

    interface Props {
        text: string;
        class?: string;
    }

    let { text, class: className = "" }: Props = $props();

    // marked config: no async, no mangle, GFM enabled (tables, strikethrough, etc.)
    marked.use({ async: false, gfm: true, breaks: true });

    let rendered = $derived(marked.parse(text) as string);
</script>

<div class="markdown-body {className}">
    {@html rendered}
</div>

<style>
    /* Minimal markdown prose styling that inherits the app's design tokens */
    .markdown-body {
        line-height: 1.7;
        word-break: break-word;
    }

    .markdown-body :global(h1),
    .markdown-body :global(h2),
    .markdown-body :global(h3),
    .markdown-body :global(h4) {
        margin: 0.75em 0 0.25em;
        font-weight: var(--weight-emphasis, 600);
        color: var(--text-primary);
    }

    .markdown-body :global(h1) {
        font-size: 1.4em;
    }
    .markdown-body :global(h2) {
        font-size: 1.2em;
    }
    .markdown-body :global(h3) {
        font-size: 1.05em;
    }

    .markdown-body :global(p) {
        margin: 0.5em 0;
    }

    .markdown-body :global(ul),
    .markdown-body :global(ol) {
        margin: 0.4em 0;
        padding-left: 1.5em;
    }

    .markdown-body :global(li) {
        margin: 0.15em 0;
    }

    .markdown-body :global(blockquote) {
        margin: 0.5em 0;
        padding: 0.25em 0.75em;
        border-left: 3px solid var(--accent, #6366f1);
        color: var(--text-secondary);
        background: var(--surface-tertiary, transparent);
        border-radius: 0 var(--radius-sm, 4px) var(--radius-sm, 4px) 0;
    }

    .markdown-body :global(code) {
        font-size: 0.9em;
        padding: 0.1em 0.35em;
        border-radius: var(--radius-sm, 4px);
        background: var(--surface-tertiary, rgba(0, 0, 0, 0.1));
    }

    .markdown-body :global(pre) {
        margin: 0.5em 0;
        padding: 0.75em;
        border-radius: var(--radius-md, 8px);
        background: var(--surface-tertiary, rgba(0, 0, 0, 0.1));
        overflow-x: auto;
    }

    .markdown-body :global(pre code) {
        padding: 0;
        background: none;
    }

    .markdown-body :global(hr) {
        border: none;
        border-top: 1px solid var(--shell-border, #333);
        margin: 0.75em 0;
    }

    .markdown-body :global(table) {
        border-collapse: collapse;
        width: 100%;
        margin: 0.5em 0;
    }

    .markdown-body :global(th),
    .markdown-body :global(td) {
        padding: 0.35em 0.75em;
        border: 1px solid var(--shell-border, #333);
        text-align: left;
    }

    .markdown-body :global(th) {
        font-weight: var(--weight-emphasis, 600);
        background: var(--surface-tertiary, transparent);
    }

    .markdown-body :global(strong) {
        font-weight: var(--weight-emphasis, 600);
    }

    .markdown-body :global(a) {
        color: var(--accent, #6366f1);
        text-decoration: underline;
    }

    /* First child no top margin, last child no bottom margin */
    .markdown-body :global(> :first-child) {
        margin-top: 0;
    }
    .markdown-body :global(> :last-child) {
        margin-bottom: 0;
    }
</style>
