<script lang="ts">
    import { confirmDialog } from "../confirm.svelte";
    import StyledButton from "./StyledButton.svelte";
    import ToggleSwitch from "./ToggleSwitch.svelte";

    let checkboxChecked = $state(false);
    let selectValue = $state("");
    let dialogEl: HTMLDivElement | undefined = $state();

    $effect(() => {
        const active = confirmDialog.active;
        if (active) {
            checkboxChecked = active.checkboxDefault ?? false;
            selectValue = active.selectDefault ?? active.selectOptions?.[0]?.value ?? "";
        }
    });

    $effect(() => {
        if (confirmDialog.active && dialogEl) dialogEl.focus();
    });

    function resolveWith(id: number, value: boolean, alternative = false): void {
        confirmDialog.setLastCheckboxValue(checkboxChecked);
        confirmDialog.setLastConfirmWasAlternative(alternative);
        confirmDialog.setLastSelectValue(selectValue);
        confirmDialog.resolve(id, value);
    }

    function handleKeydown(event: KeyboardEvent): void {
        const active = confirmDialog.active;
        if (!active) return;
        if (event.key === "Escape") {
            event.preventDefault();
            resolveWith(active.id, false);
        }
    }
</script>

<svelte:window onkeydown={handleKeydown} />

{#if confirmDialog.active}
    {@const active = confirmDialog.active}
    <div class="fixed inset-0 z-[300] flex items-center justify-center bg-black/55 p-[var(--space-4)]" role="presentation">
        <div
            bind:this={dialogEl}
            class="w-full max-w-[520px] rounded-[var(--radius-lg)] border border-[var(--shell-border)] bg-[var(--surface-secondary)] shadow-2xl outline-none"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="confirm-dialog-title"
            aria-describedby="confirm-dialog-message"
            tabindex="-1"
            onclick={(event) => event.stopPropagation()}
            onkeydown={(event) => event.stopPropagation()}
        >
            <div class="flex flex-col gap-[var(--space-3)] p-[var(--space-4)]">
                <div class="flex flex-col gap-[var(--space-1)]">
                    <h3
                        id="confirm-dialog-title"
                        class="m-0 text-[var(--text-base)] font-[var(--weight-emphasis)] text-[var(--text-primary)]"
                    >
                        {active.title}
                    </h3>
                    <p
                        id="confirm-dialog-message"
                        class="m-0 text-[var(--text-sm)] leading-[var(--leading-normal)] text-[var(--text-secondary)]"
                    >
                        {active.message}
                    </p>
                </div>

                {#if active.checkboxLabel}
                    <div class="flex items-center gap-[var(--space-2)] select-none">
                        <ToggleSwitch bind:checked={checkboxChecked} />
                        <span class="text-[var(--text-sm)] text-[var(--text-secondary)]">{active.checkboxLabel}</span>
                    </div>
                {/if}

                {#if active.selectOptions?.length}
                    <label class="flex flex-col gap-[var(--space-1)] text-[var(--text-sm)] text-[var(--text-secondary)]">
                        <span>{active.selectLabel ?? "Choose an option"}</span>
                        <select
                            class="h-9 w-full rounded-[var(--radius-md)] border border-[var(--shell-border)] bg-[var(--surface-primary)] px-[var(--space-2)] text-[var(--text-sm)] text-[var(--text-primary)] outline-none transition-colors focus:border-[var(--accent)]"
                            bind:value={selectValue}
                        >
                            {#each active.selectOptions as option (option.value)}
                                <option value={option.value}>{option.label}</option>
                            {/each}
                        </select>
                    </label>
                {/if}

                <div class="flex justify-end gap-[var(--space-2)] pt-[var(--space-1)]">
                    <StyledButton size="sm" variant="secondary" onclick={() => resolveWith(active.id, false)}>
                        {active.cancelLabel ?? "Cancel"}
                    </StyledButton>
                    {#if active.alternativeLabel}
                        <StyledButton size="sm" variant="secondary" onclick={() => resolveWith(active.id, true, true)}>
                            {active.alternativeLabel}
                        </StyledButton>
                    {/if}
                    <StyledButton
                        size="sm"
                        variant={active.danger ? "destructive" : "primary"}
                        onclick={() => resolveWith(active.id, true)}
                    >
                        {active.confirmLabel ?? "Confirm"}
                    </StyledButton>
                </div>
            </div>
        </div>
    </div>
{/if}
