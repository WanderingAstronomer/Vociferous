<script lang="ts">
    /**
     * Animated toggle switch — ported from PyQt6 ToggleSwitch widget.
     * Pill-shaped track with sliding circle, smooth CSS transitions.
     */

    let {
        checked = $bindable(false),
        disabled = false,
        onChange = undefined as ((val: boolean) => void) | undefined,
    } = $props();

    function toggle() {
        if (disabled) return;
        checked = !checked;
        onChange?.(checked);
    }
</script>

<button
    class="relative w-[50px] h-[24px] rounded-[12px] border-none cursor-pointer p-0 transition-colors duration-250 flex-shrink-0 disabled:opacity-40 disabled:cursor-not-allowed"
    class:bg-[var(--accent)]={checked}
    class:bg-[var(--gray-6)]={!checked}
    role="switch"
    aria-label="Toggle"
    aria-checked={checked}
    {disabled}
    onclick={toggle}
>
    <!-- Circle -->
    <span
        class="absolute top-[3px] left-[3px] w-[18px] h-[18px] rounded-full bg-white shadow transition-transform duration-250"
        class:translate-x-[26px]={checked}
    ></span>
</button>
