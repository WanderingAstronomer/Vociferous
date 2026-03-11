<script lang="ts">
    /**
     * Animated toggle switch. Pill-shaped track with sliding circle.
     */

    let {
        checked = $bindable(false),
        disabled = false,
        size = "md" as "sm" | "md",
        onChange = undefined as ((val: boolean) => void) | undefined,
    } = $props();

    const isSmall = $derived(size === "sm");

    function toggle() {
        if (disabled) return;
        checked = !checked;
        onChange?.(checked);
    }
</script>

<button
    class="relative border-none cursor-pointer p-0 transition-colors duration-250 flex-shrink-0 disabled:opacity-40 disabled:cursor-not-allowed"
    class:w-[50px]={!isSmall}
    class:h-[24px]={!isSmall}
    class:rounded-[12px]={!isSmall}
    class:w-[42px]={isSmall}
    class:h-[20px]={isSmall}
    class:rounded-[10px]={isSmall}
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
        class="absolute rounded-full bg-white shadow transition-transform duration-250"
        class:top-[3px]={!isSmall}
        class:left-[3px]={!isSmall}
        class:w-[18px]={!isSmall}
        class:h-[18px]={!isSmall}
        class:translate-x-[26px]={checked && !isSmall}
        class:top-[2px]={isSmall}
        class:left-[2px]={isSmall}
        class:w-[16px]={isSmall}
        class:h-[16px]={isSmall}
        class:translate-x-[22px]={checked && isSmall}
    ></span>
</button>
