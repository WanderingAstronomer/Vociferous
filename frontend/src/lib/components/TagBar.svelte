<!--
    TagBar — reusable tag chip bar with inline creation and context menu.

    Used by TranscriptsView (filter mode), EditView (assignment mode),
    and TranscribeView (session tag mode). Same component, same behavior,
    different callbacks.
-->
<script lang="ts">
    import type { Tag } from "../api";
    import type { Snippet } from "svelte";
    import { Hammer, Plus, Check, X, Palette, Trash2 } from "lucide-svelte";

    interface Props {
        /** All available tags. */
        tags: Tag[];
        /** IDs of tags currently "active" (filtered, assigned, etc.). */
        activeIds: Set<number>;
        /** Fired when a tag chip is clicked. */
        ontoggle: (tagId: number) => void;
        /** Fired when a new tag is created via the inline form. */
        oncreate: (name: string, color: string) => void;
        /** Fired when a tag is deleted via the context menu. */
        ondelete: (tagId: number) => void;
        /** Fired when a tag color is changed via the context menu. */
        oncolorchange: (tagId: number, color: string) => void;
        /** Notifies parent when the context menu opens/closes (for Escape handling). */
        onmenuchange?: (open: boolean) => void;
        /** Optional extra controls (e.g. filter mode buttons) rendered after chips. */
        children?: Snippet;
    }

    let { tags, activeIds, ontoggle, oncreate, ondelete, oncolorchange, onmenuchange, children }: Props = $props();

    /* ===== Internal State ===== */

    // Inline creation form
    let showCreate = $state(false);
    let newName = $state("");
    let newColor = $state("#5a9fd4");

    // Context menu (right-click on tag chip)
    let menuTagId: number | null = $state(null);
    let menuX = $state(0);
    let menuY = $state(0);
    let menuColor = $state("");

    /* ===== Helpers ===== */

    function tagColor(tag: { color: string | null }): string {
        return tag.color ?? "var(--accent)";
    }

    /* ===== Context Menu ===== */

    function openMenu(tagId: number, event: MouseEvent) {
        event.preventDefault();
        event.stopPropagation();
        const tag = tags.find((t) => t.id === tagId);
        if (!tag || tag.is_system) return;
        menuColor = tag.color ?? "#5a9fd4";
        menuX = Math.min(event.clientX, window.innerWidth - 200);
        menuY = event.clientY;
        menuTagId = tagId;
        onmenuchange?.(true);
    }

    function closeMenu() {
        menuTagId = null;
        onmenuchange?.(false);
    }

    function handleColorChange(tagId: number, color: string) {
        menuColor = color;
        oncolorchange(tagId, color);
    }

    function handleDelete(tagId: number) {
        closeMenu();
        ondelete(tagId);
    }

    /* ===== Inline Creation ===== */

    function handleCreateSubmit() {
        const name = newName.trim();
        if (!name) return;
        oncreate(name, newColor);
        newName = "";
        showCreate = false;
    }
</script>

<!-- Tag chips + extra controls + create form, all in one flex row -->
<div class="flex items-center justify-center gap-1.5 flex-wrap min-h-[28px]">
    {#each tags as tag (tag.id)}
        <button
            class="inline-flex items-center gap-1 h-6 px-2 rounded-full text-xs font-medium border cursor-pointer transition-all duration-150 select-none"
            style={activeIds.has(tag.id)
                ? `background: color-mix(in srgb, ${tagColor(tag)} 30%, transparent); border-color: ${tagColor(tag)}; color: var(--text-primary);`
                : `background: transparent; border-color: var(--shell-border); color: var(--text-tertiary);`}
            onclick={() => ontoggle(tag.id)}
            oncontextmenu={tag.is_system ? undefined : (e) => openMenu(tag.id, e)}
            title={tag.is_system ? tag.name : "Click to toggle · Right-click to edit/delete"}
        >
            {#if tag.is_system}
                <Hammer size={10} class="shrink-0" />
            {:else}
                <span class="w-2 h-2 rounded-full shrink-0" style="background: {tagColor(tag)}"></span>
            {/if}
            {tag.name}
            {#if activeIds.has(tag.id)}
                <X size={10} class="ml-0.5 opacity-60" />
            {/if}
        </button>
    {/each}

    <!-- Extra controls from parent (filter mode, clear, etc.) -->
    {@render children?.()}

    {#if tags.length > 0}
        <div class="w-px h-4 bg-[var(--shell-border)] mx-0.5"></div>
    {/if}

    <!-- Inline tag creation -->
    {#if showCreate}
        <form
            class="inline-flex items-center gap-1"
            onsubmit={(e) => {
                e.preventDefault();
                handleCreateSubmit();
            }}
        >
            <input
                type="color"
                class="w-5 h-5 border-none rounded cursor-pointer p-0 bg-transparent"
                bind:value={newColor}
            />
            <input
                type="text"
                class="h-6 w-24 px-1.5 rounded text-xs bg-[var(--surface-secondary)] border border-[var(--shell-border)] text-[var(--text-primary)] outline-none focus:border-[var(--accent)]"
                placeholder="Tag name"
                bind:value={newName}
            />
            <button
                type="submit"
                class="w-5 h-5 rounded bg-[var(--accent)] text-[var(--gray-0)] border-none cursor-pointer flex items-center justify-center"
                disabled={!newName.trim()}
            >
                <Check size={11} />
            </button>
            <button
                type="button"
                class="w-5 h-5 rounded bg-transparent text-[var(--text-tertiary)] border-none cursor-pointer flex items-center justify-center hover:text-[var(--text-primary)]"
                onclick={() => {
                    showCreate = false;
                    newName = "";
                }}
            >
                <X size={11} />
            </button>
        </form>
    {:else}
        <button
            class="inline-flex items-center gap-1 h-6 px-2 rounded-full text-xs text-[var(--text-tertiary)] bg-transparent border border-dashed border-[var(--shell-border)] cursor-pointer transition-colors hover:text-[var(--accent)] hover:border-[var(--accent)]"
            onclick={() => (showCreate = true)}
            title={tags.length > 0 ? "Create new tag" : "Create your first tag"}
        >
            <Plus size={10} />
            {tags.length > 0 ? "Tag" : "Create a tag"}
        </button>
    {/if}
</div>

<!-- ── Context Menu (right-click on non-system tag chip) ── -->
{#if menuTagId !== null}
    <div
        class="fixed inset-0 z-[249]"
        onclick={closeMenu}
        oncontextmenu={(e) => {
            e.preventDefault();
            closeMenu();
        }}
        role="presentation"
    ></div>
    <div
        class="fixed w-[180px] bg-[var(--surface-primary)] border border-[var(--shell-border)] rounded-lg shadow-[0_12px_28px_rgba(0,0,0,0.45)] py-1 z-[250]"
        style="left: {menuX}px; top: {menuY}px;"
        role="menu"
        tabindex="-1"
        onpointerdown={(e) => e.stopPropagation()}
    >
        <div class="px-3 py-1.5 text-[11px] uppercase tracking-wide text-[var(--text-tertiary)]">Edit tag</div>
        <!-- Color picker row -->
        <div class="flex items-center gap-2 px-3 py-1.5">
            <Palette size={13} class="text-[var(--text-tertiary)] shrink-0" />
            <span class="text-xs text-[var(--text-secondary)]">Color</span>
            <div class="flex-1"></div>
            <input
                type="color"
                class="w-6 h-6 border border-[var(--shell-border)] rounded cursor-pointer p-0 bg-transparent"
                value={menuColor}
                onchange={(e) => {
                    const target = e.currentTarget as HTMLInputElement;
                    if (menuTagId !== null) {
                        handleColorChange(menuTagId, target.value);
                    }
                }}
            />
        </div>
        <!-- Divider -->
        <div class="h-px bg-[var(--shell-border)] mx-2 my-1"></div>
        <!-- Delete -->
        <button
            class="w-full flex items-center gap-2 px-3 py-1.5 border-none bg-transparent text-left text-xs cursor-pointer transition-colors duration-150 hover:bg-[color-mix(in_srgb,var(--color-danger)_15%,transparent)] text-[var(--color-danger)]"
            onclick={() => {
                if (menuTagId !== null) handleDelete(menuTagId);
            }}
            role="menuitem"
        >
            <Trash2 size={13} />
            Delete tag
        </button>
    </div>
{/if}
