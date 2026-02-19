<script lang="ts">
    /**
     * ProjectModal — Focused modal for create / rename / delete project actions.
     *
     * Modes:
     *   "create"  — name input + color picker + optional parent select.
     *   "rename"  — same fields, pre-filled from target project.
     *   "delete"  — confirmation prompt.
     */

    import type { Project } from "../api";
    import { X } from "lucide-svelte";
    import ColorPicker, { ChromeVariant } from "svelte-awesome-color-picker";

    type ModalMode = "create" | "rename" | "delete";

    interface CreateResult {
        mode: "create";
        name: string;
        color: string;
        parentId: number | null;
    }
    interface RenameResult {
        mode: "rename";
        id: number;
        name: string;
        color: string;
    }
    interface DeleteResult {
        mode: "delete";
        id: number;
    }
    export type ProjectModalResult = CreateResult | RenameResult | DeleteResult;

    interface Props {
        mode: ModalMode;
        target?: Project | null;
        projects?: Project[];
        onconfirm: (result: ProjectModalResult) => void;
        oncancel: () => void;
    }

    /** Curated palette swatches — broad coverage, dark-UI friendly. */
    const SWATCHES = [
        // Blues / Cyans
        "#1e3a5f", "#1d4ed8", "#0284c7", "#0891b2", "#0d9488",
        // Greens
        "#14532d", "#15803d", "#4d7c0f", "#065f46", "#166534",
        // Purples / Violets
        "#3b0764", "#6d28d9", "#7c3aed", "#9333ea", "#be185d",
        // Reds / Pinks / Roses
        "#7f1d1d", "#b91c1c", "#9f1239", "#c2410c", "#e11d48",
        // Ambers / Oranges
        "#78350f", "#92400e", "#b45309", "#d97706", "#ea580c",
        // Neutrals / Slates
        "#1e293b", "#374151", "#475569", "#6b7280", "#71717a",
    ];

    const DEFAULT_COLOR = "#2d5a7b";

    let { mode, target = null, projects = [], onconfirm, oncancel }: Props = $props();

    let name = $state(mode === "rename" && target ? target.name : "");
    let color = $state<string | null>(mode === "rename" && target?.color ? target.color : DEFAULT_COLOR);
    let colorSafe = $derived(color ?? DEFAULT_COLOR);
    let parentId = $state<number | null>(mode === "create" ? null : null);

    /** Top-level projects available as parents (excluding target when renaming). */
    let parentOptions = $derived(projects.filter((p) => !p.parent_id && (target ? p.id !== target.id : true)));

    function handleConfirm() {
        if (mode === "create") {
            if (!name.trim()) return;
            onconfirm({ mode: "create", name: name.trim(), color: colorSafe, parentId });
        } else if (mode === "rename") {
            if (!name.trim() || !target) return;
            onconfirm({ mode: "rename", id: target.id, name: name.trim(), color: colorSafe });
        } else if (mode === "delete") {
            if (!target) return;
            onconfirm({ mode: "delete", id: target.id });
        }
    }

    function handleKeydown(e: KeyboardEvent) {
        if (e.key === "Escape") oncancel();
        if (e.key === "Enter" && mode !== "delete") handleConfirm();
    }

    function handleBackdropClick(e: MouseEvent) {
        if (e.target === e.currentTarget) oncancel();
    }

    const heading = mode === "create" ? "New Project" : mode === "rename" ? "Rename Project" : "Delete Project";
</script>

<!-- svelte-ignore a11y_no_noninteractive_element_interactions a11y_interactive_supports_focus -->
<div
    class="fixed inset-0 z-[300] flex items-center justify-center bg-black/50"
    role="dialog"
    aria-modal="true"
    aria-label={heading}
    onclick={handleBackdropClick}
    onkeydown={handleKeydown}
>
    <div
        class="w-full max-w-[440px] bg-[var(--surface-secondary)] border border-[var(--shell-border)] rounded-[var(--radius-lg)] p-[var(--space-4)] flex flex-col gap-[var(--space-3)] shadow-[0_12px_28px_rgba(0,0,0,0.45)]"
    >
        <!-- Header -->
        <div class="flex items-center justify-between">
            <h3 class="m-0 text-[var(--text-base)] font-semibold text-[var(--text-primary)]">{heading}</h3>
            <button
                class="w-7 h-7 border-none rounded bg-transparent text-[var(--text-tertiary)] cursor-pointer flex items-center justify-center hover:text-[var(--text-primary)] hover:bg-[var(--hover-overlay)] transition-colors"
                onclick={oncancel}
            >
                <X size={16} />
            </button>
        </div>

        {#if mode === "delete"}
            <!-- Delete confirmation -->
            <p class="m-0 text-sm text-[var(--text-secondary)]">
                Delete project <strong class="text-[var(--text-primary)]">"{target?.name}"</strong>? Its transcripts
                will be unassigned, not deleted.
            </p>
            <div class="flex justify-end gap-[var(--space-2)] pt-[var(--space-1)]">
                <button
                    class="h-9 px-4 border border-[var(--shell-border)] rounded text-sm font-semibold cursor-pointer bg-transparent text-[var(--text-secondary)] hover:bg-[var(--hover-overlay)] transition-colors"
                    onclick={oncancel}>Cancel</button
                >
                <button
                    class="h-9 px-4 border-none rounded text-sm font-semibold cursor-pointer bg-[var(--color-danger)] text-white hover:opacity-90 transition-opacity"
                    onclick={handleConfirm}>Delete</button
                >
            </div>
        {:else}
            <!-- Create / Rename form -->
            <div class="flex flex-col gap-[var(--space-2)]">
                <label for="pm-name" class="text-xs text-[var(--text-tertiary)] uppercase tracking-wide">Name</label>
                <input
                    id="pm-name"
                    type="text"
                    class="h-9 bg-[var(--surface-primary)] border border-[var(--shell-border)] rounded text-[var(--text-primary)] text-sm px-3 outline-none focus:border-[var(--accent)] placeholder:text-[var(--text-tertiary)] transition-colors"
                    placeholder="Project name"
                    bind:value={name}
                />
            </div>

            <div class="flex flex-col gap-[var(--space-2)]">
                <span class="text-xs text-[var(--text-tertiary)] uppercase tracking-wide">Color</span>
                <div
                    class="color-picker-wrap"
                    style:--cp-bg-color="var(--surface-primary)"
                    style:--cp-border-color="var(--shell-border)"
                    style:--cp-text-color="var(--text-primary)"
                    style:--cp-input-color="var(--surface-secondary)"
                    style:--cp-button-hover-color="var(--hover-overlay)"
                    style:--picker-height="150px"
                    style:--picker-width="100%"
                    style:--slider-width="22px"
                    style:--input-size="22px"
                    style:--focus-color="var(--accent)"
                >
                    <ColorPicker
                        bind:hex={color}
                        components={ChromeVariant}
                        sliderDirection="horizontal"
                        isDialog={false}
                        isAlpha={false}
                        swatches={SWATCHES}
                        textInputModes={['hex']}
                    />
                </div>
            </div>

            {#if mode === "create" && parentOptions.length > 0}
                <div class="flex flex-col gap-[var(--space-2)]">
                    <label for="pm-parent" class="text-xs text-[var(--text-tertiary)] uppercase tracking-wide"
                        >Parent (optional)</label
                    >
                    <select
                        id="pm-parent"
                        class="h-9 bg-[var(--surface-primary)] border border-[var(--shell-border)] rounded text-[var(--text-primary)] text-sm px-2 outline-none focus:border-[var(--accent)] transition-colors"
                        value={parentId == null ? "" : String(parentId)}
                        onchange={(e) => {
                            const v = (e.currentTarget as HTMLSelectElement).value;
                            parentId = v === "" ? null : parseInt(v, 10);
                        }}
                    >
                        <option value="">None (top-level)</option>
                        {#each parentOptions as p}
                            <option value={String(p.id)}>{p.name}</option>
                        {/each}
                    </select>
                </div>
            {/if}

            <div class="flex justify-end gap-[var(--space-2)] pt-[var(--space-1)]">
                <button
                    class="h-9 px-4 border border-[var(--shell-border)] rounded text-sm font-semibold cursor-pointer bg-transparent text-[var(--text-secondary)] hover:bg-[var(--hover-overlay)] transition-colors"
                    onclick={oncancel}>Cancel</button
                >
                <button
                    class="h-9 px-4 border-none rounded text-sm font-semibold cursor-pointer bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    disabled={!name.trim()}
                    onclick={handleConfirm}>{mode === "create" ? "Create" : "Save"}</button
                >
            </div>
        {/if}
    </div>
</div>
