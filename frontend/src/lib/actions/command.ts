export type CommandGroup = "capture" | "edit" | "organize" | "share" | "danger" | "status";
export type CommandPlacement = "bar" | "overflow" | "both";
export type CommandSection = "start" | "end";
export type CommandVariant = "primary" | "secondary" | "ghost" | "neutral" | "destructive" | "danger-outline";
export type CommandState = boolean | (() => boolean);

export type CommandIcon = typeof import("lucide-svelte").Icon;

export interface CommandNode {
    id: string;
    label: string;
    icon?: CommandIcon;
    variant?: CommandVariant;
    group?: CommandGroup;
    placement?: CommandPlacement;
    section?: CommandSection;
    priority?: number;
    disabled?: CommandState;
    visibleWhen?: () => boolean;
    title?: string;
    iconOnly?: boolean;
    checked?: CommandState;
    children?: CommandNode[];
    run?: (event?: MouseEvent) => void | Promise<void>;
}

function readState(state: CommandState | undefined): boolean {
    if (typeof state === "function") return state();
    return state ?? false;
}

export function isCommandVisible(command: CommandNode): boolean {
    return command.visibleWhen?.() ?? true;
}

export function isCommandDisabled(command: CommandNode): boolean {
    return readState(command.disabled);
}

export function isCommandChecked(command: CommandNode): boolean {
    return readState(command.checked);
}

export function commandSort(a: CommandNode, b: CommandNode): number {
    return (a.priority ?? 100) - (b.priority ?? 100) || a.label.localeCompare(b.label);
}

export function resolveCommandTree(commands: CommandNode[]): CommandNode[] {
    return commands
        .filter(isCommandVisible)
        .map((command) => {
            const children = command.children ? resolveCommandTree(command.children) : undefined;
            return { ...command, children };
        })
        .filter((command) => Boolean(command.run) || Boolean(command.children?.length))
        .sort(commandSort);
}

export function commandPlacement(command: CommandNode): CommandPlacement {
    return command.placement ?? "bar";
}

export function commandTitle(command: CommandNode): string {
    return command.title ?? command.label;
}