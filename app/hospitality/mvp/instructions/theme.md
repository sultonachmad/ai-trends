<!-- Prefab: theme-ttest v0.2.0 -->

# Theme: Ttest

This project uses the **Ttest** visual theme — an indigo/violet color palette with modern gradient accents and the Space Grotesk typeface.

## Design System

All colors are defined as CSS custom properties in `styles/globals.css` and mapped to Tailwind utility classes in `tailwind.config.ts`. Use semantic class names, never raw color values:

| Semantic class | Purpose |
|---|---|
| `bg-background` / `text-foreground` | Page background and default text |
| `bg-primary` / `text-primary-foreground` | Primary actions (buttons, links) |
| `bg-secondary` / `text-secondary-foreground` | Secondary actions, muted buttons |
| `bg-muted` / `text-muted-foreground` | Subdued surfaces, helper text |
| `bg-accent` / `text-accent-foreground` | Hover/active highlight tint only — low contrast, never a surface for body text (use `bg-card`/`bg-muted` for that) |
| `bg-card` / `text-card-foreground` | Card surfaces |
| `border-border` | All borders |
| `bg-destructive` / `text-destructive-foreground` | Danger buttons (fill + readable text); use `text-destructive` on its own for inline error text |

## Rules

- **Never hardcode color values** — always use the semantic Tailwind classes above.
- **Colours come from the style file** — `frontend/styles/screen-style.css` sets the `--sd-*` values the variables above read. Ttest writes it; do not edit it, and never hard-code colours.
- **Light or dark is set by the style, not by you** — the theme is applied via the `.ttest` class on `<html>` (see `app/layout.tsx`), and the screen style adds `dark` there when it asks for a dark appearance; the variables then carry the dark values.
- The primary colour is indigo/violet unless the project's screen style sets another (`--primary-color`). Use `bg-primary` for CTAs.
- Use `hover:bg-primary/90` for hover states on primary buttons (opacity modifier).

## Dialog Pattern

Dialogs (modals, confirmations, detail panels) **must** render an opaque panel over a dimmed page — never a bare panel that lets the page show through. Use the shared `Dialog` component (`components/Dialog.tsx`, registered in `components-fe.yaml`):

```tsx
import { Dialog } from "@/components/Dialog";

<Dialog open={open} onClose={onClose} title="Upload file">
  {/* body */}
  <div className="mt-4 flex justify-end gap-2">
    <button className="rounded-md px-4 py-2 bg-secondary text-secondary-foreground" onClick={onClose}>Cancel</button>
    <button className="rounded-md px-4 py-2 bg-primary text-primary-foreground hover:bg-primary/90">Save</button>
  </div>
</Dialog>
```

If you build a dialog by hand instead of using the component, keep the same two layers:

- **Overlay** — `fixed inset-0 z-50 bg-black/50` to dim the page (fills the viewport, closes on click).
- **Panel** — an **opaque** surface: `bg-card text-card-foreground` (or `bg-background`), `rounded-xl p-6 shadow-lg`, centered over the overlay. Never leave the panel without a background class.
