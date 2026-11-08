"use client";

/**
 * Modal confirmation dialog for destructive delete actions, used by
 * DataTable-driven CRUD pages before calling `api-client`'s `remove`.
 */

interface DeleteConfirmProps {
  open: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  itemName?: string;
}

export function DeleteConfirm({ open, onConfirm, onCancel, itemName }: DeleteConfirmProps) {
  if (!open) {
    return null;
  }

  const subject = itemName ? `"${itemName}"` : "this item";

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="delete-confirm-title"
      className="fixed inset-0 z-50 flex items-center justify-center"
    >
      <div className="fixed inset-0 bg-black/50" onClick={onCancel} aria-hidden="true" />

      <div className="relative w-full max-w-sm space-y-4 rounded-lg bg-card text-card-foreground p-6 shadow">
        <h2 id="delete-confirm-title" className="text-lg font-semibold">
          Delete {itemName ?? "item"}?
        </h2>
        <p className="text-sm text-muted-foreground">
          This action cannot be undone. Are you sure you want to delete {subject}?
        </p>
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="inline-flex items-center px-4 py-2 rounded-md border border-border bg-secondary text-secondary-foreground text-sm font-medium hover:bg-secondary/90"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className="inline-flex items-center px-4 py-2 rounded-md bg-destructive text-destructive-foreground text-sm font-medium hover:bg-destructive/90 focus:outline-none focus:ring-2 focus:ring-destructive focus:ring-offset-2"
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}
