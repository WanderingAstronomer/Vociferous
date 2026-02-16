<script lang="ts">
    /**
     * Animated toggle switch — ported from PyQt6 ToggleSwitch widget.
     * Pill-shaped track with sliding circle, smooth CSS transitions.
     */

    let {
        checked = false,
        disabled = false,
        onChange = undefined as ((checked: boolean) => void) | undefined,
    } = $props();

    function toggle() {
        if (disabled) return;
        checked = !checked;
        onChange?.(checked);
    }
</script>

<button
    class="toggle"
    class:checked
    class:disabled
    role="switch"
    aria-label="Toggle"
    aria-checked={checked}
    {disabled}
    onclick={toggle}
>
    <span class="toggle-circle"></span>
</button>

<style>
    .toggle {
        position: relative;
        width: var(--toggle-width);
        height: var(--toggle-height);
        border-radius: var(--toggle-radius);
        border: none;
        background: var(--gray-6);
        cursor: pointer;
        padding: 0;
        transition: background var(--transition-normal);
        flex-shrink: 0;
    }

    .toggle.checked {
        background: var(--accent);
    }

    .toggle.disabled {
        opacity: 0.4;
        cursor: not-allowed;
    }

    .toggle-circle {
        position: absolute;
        top: var(--toggle-circle-margin);
        left: var(--toggle-circle-margin);
        width: var(--toggle-circle);
        height: var(--toggle-circle);
        border-radius: 50%;
        background: var(--gray-0);
        transition: transform var(--transition-normal);
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
    }

    .toggle.checked .toggle-circle {
        transform: translateX(calc(var(--toggle-width) - var(--toggle-circle) - var(--toggle-circle-margin) * 2));
    }
</style>
