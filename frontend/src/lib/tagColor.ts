const HEX_COLOR = /^#[0-9a-fA-F]{6}$/;

export function safeTagColor(color: string | null | undefined, fallback = "var(--accent)"): string {
    if (!color) return fallback;
    return HEX_COLOR.test(color.trim()) ? color.trim() : fallback;
}
