/** Shared class lists for the public booking page, following DESIGN.md components. */

export const stayFocus =
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-stay-ink";

export const stayPrimaryButton = `min-h-12 rounded-stay-sm bg-stay-primary px-6 py-3 text-type-button text-stay-on-primary transition-colors hover:bg-stay-primary-active active:bg-stay-primary-active disabled:cursor-not-allowed disabled:bg-stay-primary-disabled ${stayFocus}`;

export const staySecondaryButton = `min-h-11 rounded-stay-sm border border-stay-ink bg-stay-canvas px-4 py-2 text-type-caption text-stay-ink transition-colors hover:bg-stay-surface-soft active:bg-stay-surface-strong disabled:cursor-not-allowed disabled:border-stay-border-strong disabled:text-stay-muted-soft ${stayFocus}`;

export const stayInput =
  "h-14 w-full rounded-stay-sm border border-stay-hairline bg-stay-canvas px-3 text-type-body text-stay-ink placeholder:text-stay-muted focus:outline-2 focus:-outline-offset-2 focus:outline-stay-ink";

export const stayLabel = "mb-2 block text-type-caption text-stay-muted";

export const staySectionTitle = "text-type-display-md text-stay-ink";
