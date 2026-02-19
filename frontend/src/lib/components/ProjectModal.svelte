<script lang="ts">
    /**
     * ProjectModal — Focused modal for create / edit / delete project actions.
     *
     * Modes:
     *   "create"  — name input + color picker + optional parent select.
     *   "edit"    — same fields, pre-filled from target project.
     *   "delete"  — confirmation prompt.
     */

    import type { Project } from "../api";
    import { X } from "lucide-svelte";
    import ColorPicker, { ChromeVariant } from "svelte-awesome-color-picker";
    import CustomSelect from "./CustomSelect.svelte";

    type ModalMode = "create" | "edit" | "delete";

    interface CreateResult {
        mode: "create";
        name: string;
        color: string;
        parentId: number | null;
    }
    interface EditResult {
        mode: "edit";
        id: number;
        name: string;
        color: string;
        parentId: number | null;
    }
    interface DeleteResult {
        mode: "delete";
        id: number;
        /** Delete transcripts directly assigned to this project (vs. unassign). */
        deleteTranscripts: boolean;
        /** For top-level projects with subprojects: true = promote subprojects to top-level, false = delete them. */
        promoteSubprojects: boolean;
        /** For top-level projects: delete transcripts in subprojects (vs. unassign). Only relevant when subprojects are deleted. */
        deleteSubprojectTranscripts: boolean;
    }
    export type ProjectModalResult = CreateResult | EditResult | DeleteResult;

    interface Props {
        mode: ModalMode;
        target?: Project | null;
        projects?: Project[];
        onconfirm: (result: ProjectModalResult) => void;
        oncancel: () => void;
    }

    /** Curated palette swatches — vibrant, dark-UI readable. 6 columns × 6 rows = 36 perfect grid. */
    const SWATCHES = [
        // Blues / Cyans / Teals
        "#3b82f6",
        "#2563eb",
        "#0ea5e9",
        "#06b6d4",
        "#14b8a6",
        "#6366f1",
        // Greens / Limes
        "#22c55e",
        "#10b981",
        "#84cc16",
        "#4ade80",
        "#a3e635",
        "#16a34a",
        // Purples / Violets / Fuchsia
        "#a855f7",
        "#8b5cf6",
        "#d946ef",
        "#c084fc",
        "#818cf8",
        "#7c3aed",
        // Pinks / Roses
        "#ec4899",
        "#f43f5e",
        "#fb7185",
        "#f472b6",
        "#e879f9",
        "#db2777",
        // Reds / Oranges / Yellows
        "#ef4444",
        "#f97316",
        "#fb923c",
        "#fbbf24",
        "#f59e0b",
        "#eab308",
        // Neutrals / Warm grays
        "#f97066",
        "#64748b",
        "#6b7280",
        "#71717a",
        "#475569",
        "#334155",
    ];

    const DEFAULT_COLOR = "#3b82f6";

    let { mode, target = null, projects = [], onconfirm, oncancel }: Props = $props();

    let name = $state("");
    let color = $state<string | null>(DEFAULT_COLOR);

    /** Color value used for output — just the raw hex, no muting. */
    let colorOut = $derived(color && color.length >= 4 ? color : DEFAULT_COLOR);

    let parentId = $state<number | null>(null);

    /** Whether the target project has subprojects (if so, it cannot become a child). */
    let targetHasChildren = $derived(target ? projects.some((p) => p.parent_id === target!.id) : false);

    /** Top-level projects available as parents (excluding target when editing). */
    let parentOptions = $derived(projects.filter((p) => !p.parent_id && (target ? p.id !== target.id : true)));

    /** Build options for CustomSelect. */
    let parentSelectOptions = $derived([
        { value: "", label: "None (top-level)" },
        ...parentOptions.map((p) => ({ value: String(p.id), label: p.name })),
    ]);

    /* ── Delete mode state ── */
    let deleteTranscripts = $state(false);
    let promoteSubprojects = $state(true);
    let deleteSubprojectTranscripts = $state(false);

    /** Is the target a subproject? */
    let isSubproject = $derived(target ? target.parent_id != null : false);

    /** Subprojects of the target project. */
    let childProjects = $derived(target ? projects.filter((p) => p.parent_id === target!.id) : []);
    let hasChildren = $derived(childProjects.length > 0);

    $effect(() => {
        if (mode === "edit" && target) {
            name = target.name;
            color = target.color ?? DEFAULT_COLOR;
            parentId = target.parent_id ?? null;
        } else {
            name = "";
            color = DEFAULT_COLOR;
            parentId = null;
        }

        deleteTranscripts = false;
        promoteSubprojects = true;
        deleteSubprojectTranscripts = false;
    });

    function handleConfirm() {
        if (mode === "create") {
            if (!name.trim()) return;
            onconfirm({ mode: "create", name: name.trim(), color: colorOut, parentId });
        } else if (mode === "edit") {
            if (!name.trim() || !target) return;
            onconfirm({ mode: "edit", id: target.id, name: name.trim(), color: colorOut, parentId });
        } else if (mode === "delete") {
            if (!target) return;
            onconfirm({
                mode: "delete",
                id: target.id,
                deleteTranscripts,
                promoteSubprojects,
                deleteSubprojectTranscripts,
            });
        }
    }

    function handleKeydown(e: KeyboardEvent) {
        if (e.key === "Escape") oncancel();
        if (e.key === "Enter" && mode !== "delete") handleConfirm();
    }

    function handleBackdropClick(e: MouseEvent) {
        if (e.target === e.currentTarget) oncancel();
    }

    const heading = $derived(mode === "create" ? "New Project" : mode === "edit" ? "Edit Project" : "Delete Project");
</script>

<!-- svelte-ignore a11y_no_noninteractive_element_interactions a11y_interactive_supports_focus -->
<div
    class="fixed inset-0 z-[300] flex items-center justify-center bg-black/50"
    role="dialog"
    tabindex="-1"
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
            <!-- Delete confirmation with conditional options -->
            <p class="m-0 text-sm text-[var(--text-secondary)]">
                Delete project <strong class="text-[var(--text-primary)]">"{target?.name}"</strong>?
            </p>

            <div class="flex flex-col gap-[var(--space-2)]">
                <!-- Transcript fate checkbox (always shown) -->
                <label class="flex items-start gap-2 cursor-pointer text-sm text-[var(--text-secondary)] select-none">
                    <input
                        type="checkbox"
                        class="mt-0.5 accent-[var(--color-danger)] cursor-pointer"
                        bind:checked={deleteTranscripts}
                    />
                    <span
                        >Delete transcripts assigned to this project
                        <span class="text-[var(--text-tertiary)]">(unchecked = unassign them)</span>
                    </span>
                </label>

                {#if !isSubproject && hasChildren}
                    <!-- Top-level project with subprojects -->
                    <label
                        class="flex items-start gap-2 cursor-pointer text-sm text-[var(--text-secondary)] select-none"
                    >
                        <input
                            type="checkbox"
                            class="mt-0.5 accent-[var(--accent)] cursor-pointer"
                            bind:checked={promoteSubprojects}
                        />
                        <span
                            >Promote subprojects to top-level
                            <span class="text-[var(--text-tertiary)]">(unchecked = delete subprojects too)</span>
                        </span>
                    </label>

                    {#if !promoteSubprojects}
                        <label
                            class="flex items-start gap-2 cursor-pointer text-sm text-[var(--text-secondary)] select-none pl-6"
                        >
                            <input
                                type="checkbox"
                                class="mt-0.5 accent-[var(--color-danger)] cursor-pointer"
                                bind:checked={deleteSubprojectTranscripts}
                            />
                            <span
                                >Also delete transcripts in subprojects
                                <span class="text-[var(--text-tertiary)]">(unchecked = unassign them)</span>
                            </span>
                        </label>
                    {/if}
                {/if}
            </div>

            <div class="flex justify-between gap-[var(--space-2)] pt-[var(--space-1)]">
                <button
                    class="h-9 px-4 border-none rounded text-sm font-semibold cursor-pointer bg-[var(--color-danger)] text-white hover:opacity-90 transition-opacity"
                    onclick={handleConfirm}>Delete</button
                >
                <button
                    class="h-9 px-4 border border-[var(--shell-border)] rounded text-sm font-semibold cursor-pointer bg-transparent text-[var(--text-secondary)] hover:bg-[var(--hover-overlay)] transition-colors"
                    onclick={oncancel}>Cancel</button
                >
            </div>
        {:else}
            <!-- Create / Edit form -->
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
                    class="color-picker-wrap w-full flex justify-center"
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
                        textInputModes={["hex"]}
                    />
                </div>
            </div>

            {#if parentSelectOptions.length > 1 && !(mode === "edit" && targetHasChildren)}
                <div class="flex flex-col gap-[var(--space-2)]">
                    <label for="pm-parent" class="text-xs text-[var(--text-tertiary)] uppercase tracking-wide"
                        >Parent (optional)</label
                    >
                    <CustomSelect
                        id="pm-parent"
                        options={parentSelectOptions}
                        value={parentId == null ? "" : String(parentId)}
                        onchange={(v: string) => {
                            parentId = v === "" ? null : parseInt(v, 10);
                        }}
                        placeholder="None (top-level)"
                    />
                </div>
            {/if}

            <div class="flex justify-between gap-[var(--space-2)] pt-[var(--space-1)]">
                <button
                    class="h-9 px-4 border-none rounded text-sm font-semibold cursor-pointer bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    disabled={!name.trim()}
                    onclick={handleConfirm}>{mode === "create" ? "Create" : "Save"}</button
                >
                <button
                    class="h-9 px-4 border border-[var(--shell-border)] rounded text-sm font-semibold cursor-pointer bg-transparent text-[var(--text-secondary)] hover:bg-[var(--hover-overlay)] transition-colors"
                    onclick={oncancel}>Cancel</button
                >
            </div>
        {/if}
    </div>
</div>
