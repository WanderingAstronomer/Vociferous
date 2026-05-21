import { appConfig } from "./config.svelte";
import { confirmDialog } from "./confirm.svelte";
import { toast } from "./toast.svelte";

interface DeleteConfirmOptions {
    title: string;
    message: string;
    confirmLabel?: string;
    cancelLabel?: string;
}

async function ensureDeletePolicyLoaded(): Promise<boolean> {
    try {
        const config = await appConfig.ensureLoaded();
        return config.safety?.confirm_delete ?? true;
    } catch (error) {
        console.warn("Falling back to delete confirmations after config load failed", error);
        return true;
    }
}

async function persistDeletePolicy(value: boolean): Promise<void> {
    await appConfig.update({ safety: { confirm_delete: value } });
}

export async function confirmDeleteAction(options: DeleteConfirmOptions): Promise<boolean> {
    const shouldConfirm = await ensureDeletePolicyLoaded();
    if (!shouldConfirm) return true;

    const confirmed = await confirmDialog.confirm({
        title: options.title,
        message: options.message,
        confirmLabel: options.confirmLabel ?? "Delete",
        cancelLabel: options.cancelLabel ?? "Cancel",
        danger: true,
        checkboxLabel: "Never ask again",
    });

    if (!confirmed) return false;

    if (confirmDialog.lastCheckboxValue) {
        try {
            await persistDeletePolicy(false);
            toast.info("Delete confirmations disabled. Re-enable them in Settings.");
        } catch (error) {
            console.warn("Failed to persist delete confirmation preference", error);
            toast.warning("Delete completed, but the confirmation preference could not be saved.");
        }
    }

    return true;
}