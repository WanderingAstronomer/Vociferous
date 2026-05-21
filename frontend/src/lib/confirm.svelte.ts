export interface ConfirmOptions {
    title: string;
    message: string;
    confirmLabel?: string;
    cancelLabel?: string;
    danger?: boolean;
    checkboxLabel?: string;
    checkboxDefault?: boolean;
    alternativeLabel?: string;
}

export interface ConfirmItem extends ConfirmOptions {
    id: number;
    resolve: (value: boolean) => void;
}

let nextId = 0;
let queue = $state<ConfirmItem[]>([]);
let lastCheckboxValue = $state(false);
let lastConfirmWasAlternative = $state(false);

function confirm(options: ConfirmOptions): Promise<boolean> {
    return new Promise<boolean>((resolve) => {
        const id = ++nextId;
        queue = [...queue, { ...options, id, resolve }];
    });
}

function resolve(id: number, value: boolean): void {
    const item = queue.find((candidate) => candidate.id === id);
    if (!item) return;
    item.resolve(value);
    queue = queue.filter((candidate) => candidate.id !== id);
}

export const confirmDialog = {
    get active(): ConfirmItem | null {
        return queue.length > 0 ? queue[0] : null;
    },
    get lastCheckboxValue(): boolean {
        return lastCheckboxValue;
    },
    setLastCheckboxValue(value: boolean): void {
        lastCheckboxValue = value;
    },
    get lastConfirmWasAlternative(): boolean {
        return lastConfirmWasAlternative;
    },
    setLastConfirmWasAlternative(value: boolean): void {
        lastConfirmWasAlternative = value;
    },
    confirm,
    resolve,
};
