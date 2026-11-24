---
version: 1.0
name: direct-booking-design
description: A warm, generous guest-facing booking design on a clean white canvas, with one deep teal accent for the primary action and the property name. Type runs Inter at modest weights, soft radii keep every control friendly, and pictures and whitespace carry the visual weight instead of heavy type.
scope: Public booking page at /book/[slug]. Staff screens keep the Ttest theme.

colors:
  primary: "#0f766e"
  primary-active: "#115e59"
  primary-disabled: "#a7d5cf"
  error: "#c13515"
  ink: "#222222"
  body: "#3f3f3f"
  muted: "#6a6a6a"
  muted-soft: "#929292"
  hairline: "#dddddd"
  hairline-soft: "#ebebeb"
  border-strong: "#c1c1c1"
  canvas: "#ffffff"
  surface-soft: "#f7f7f7"
  surface-strong: "#f2f2f2"
  on-primary: "#ffffff"

typography:
  fontFamily: "Inter, -apple-system, system-ui, Roboto, sans-serif"
  type-display-xl: { fontSize: 28px, fontWeight: 700, lineHeight: 1.4 }
  type-display-lg: { fontSize: 22px, fontWeight: 500, lineHeight: 1.16, letterSpacing: -0.44px }
  type-display-md: { fontSize: 21px, fontWeight: 700, lineHeight: 1.4 }
  type-display-sm: { fontSize: 20px, fontWeight: 600, lineHeight: 1.18, letterSpacing: -0.18px }
  type-title: { fontSize: 16px, fontWeight: 600, lineHeight: 1.25 }
  type-body: { fontSize: 16px, fontWeight: 400, lineHeight: 1.5 }
  type-body-sm: { fontSize: 14px, fontWeight: 400, lineHeight: 1.43 }
  type-caption: { fontSize: 14px, fontWeight: 500, lineHeight: 1.29 }
  type-caption-sm: { fontSize: 13px, fontWeight: 400, lineHeight: 1.23 }
  type-micro: { fontSize: 12px, fontWeight: 700, lineHeight: 1.33 }
  type-badge: { fontSize: 11px, fontWeight: 600, lineHeight: 1.18 }
  type-button: { fontSize: 16px, fontWeight: 500, lineHeight: 1.25 }

rounded:
  stay-sm: 8px
  stay-md: 14px
  full: 9999px

shadow:
  stay: "rgba(0, 0, 0, 0.02) 0 0 0 1px, rgba(0, 0, 0, 0.04) 0 2px 6px 0, rgba(0, 0, 0, 0.1) 0 4px 8px 0"

layout:
  container: 1128px
  gutter-phone: 16px
  gutter-tablet-up: 24px
  rail-tablet: 320px
  rail-desktop: 372px
  breakpoint-rail: 744px
  breakpoint-desktop: 1024px
---

# Direct Booking Design

## Overview

This is the design language for the page a guest uses to book directly with a property. It should feel like a calm, trustworthy place to book, and the property should feel like the brand. The property name is the wordmark, and the product never brands itself on this page.

**Key characteristics:**

- One accent color. Teal marks the single main action in a view and the property name. Most of the page is white and ink.
- Modest type. Headings stay between 20 and 28px, so room pictures carry the visual weight.
- Soft shapes. Buttons and inputs use 8px corners, cards and pictures use 14px, and day cells, steppers and badges are fully round.
- Nearly flat. There is one shadow, used only for floating cards and badges.
- Real data only. Never show a rating, review, host profile or discount that the product does not actually have.

## Implementation

Tokens live in `frontend/tailwind.config.ts`, and shared class lists live in `frontend/components/booking-page/stay-classes.ts`. The page font and full-bleed canvas are set in `frontend/app/book/[slug]/layout.tsx`.

| Token group | Tailwind usage |
|---|---|
| Colors | `bg-stay-primary`, `text-stay-ink`, `border-stay-hairline` |
| Type | `text-type-title`, `text-type-body-sm` |
| Radius | `rounded-stay-sm`, `rounded-stay-md`, `rounded-full` |
| Shadow | `shadow-stay` |
| Font | `font-stay` |

Rules for working on this page:

- Use the tokens above. Do not add raw colors to components.
- Keep `stay-*` tokens on guest-facing booking screens, so staff screens are not restyled by accident.
- Do not use an `<aside>` inside the page. The root layout treats any `aside` as the staff sidebar and adds phone padding.
- Add every new string to both languages in `frontend/lib/i18n.ts`.

## Colors

### Accent

- **Primary** (`#0f766e`): main action buttons and the property name. White text on it has 5.47:1 contrast.
- **Primary Active** (`#115e59`): hover and pressed state of the main action.
- **Primary Disabled** (`#a7d5cf`): a main action that cannot be used yet.

Use one primary button per view. Repeated actions, such as **Choose** on each room, use the secondary button.

### Text

- **Ink** (`#222222`): headings, labels, prices and default text. Never use pure black.
- **Body** (`#3f3f3f`): longer running text, such as terms.
- **Muted** (`#6a6a6a`): supporting lines, such as guest limits, dates and calendar prices.
- **Muted Soft** (`#929292`): unavailable dates and disabled text only.
- **Error** (`#c13515`): inline errors. It must stay visually distinct from the accent.

### Surfaces and lines

- **Canvas** (`#ffffff`): the page and card background. This page has no dark mode.
- **Surface Soft** (`#f7f7f7`): notices, selected payment option, the calendar range and the picture wall.
- **Surface Strong** (`#f2f2f2`): pressed fills and the picture floor.
- **Hairline** (`#dddddd`): default borders and section dividers.
- **Hairline Soft** (`#ebebeb`): light dividers inside room cards.
- **Border Strong** (`#c1c1c1`): the date field outline and stepper buttons.

## Typography

Inter carries the whole scale through `next/font`.

| Token | Size / weight | Use |
|---|---|---|
| `type-display-xl` | 28 / 700 | Page title, checkout title |
| `type-display-lg` | 22 / 500 | Quiet page title, when a picture leads |
| `type-display-md` | 21 / 700 | Section headings |
| `type-display-sm` | 20 / 600 | Card titles, property name on tablet and up |
| `type-title` | 16 / 600 | Room names, prices, month, property name on phones |
| `type-body` | 16 / 400 | Default text and inputs |
| `type-body-sm` | 14 / 400 | Card details, terms, dates |
| `type-caption` | 14 / 500 | Field labels, rate names, secondary buttons |
| `type-caption-sm` | 13 / 400 | Hints, weekday names, footer |
| `type-micro` | 12 / 700 | Check-in and check-out field labels |
| `type-badge` | 11 / 600 | Picture badges, calendar prices at weight 400 |
| `type-button` | 16 / 500 | Primary button labels |

## Layout

- The content container is 1128px wide and centered, with 16px gutters on phones and 24px from 744px up.
- From 744px, the page has a flexible main column and a sticky 320px reservation rail. From 1024px, the rail is 372px.
- Spacing follows a 4px base. Major sections use 32px vertical padding with a hairline between them, and cards use 24px padding.
- Room cards sit close together, with a 16px column gap and 32px row gap.

| Width | Behavior |
|---|---|
| Below 480px | Room cards in one column, one hero tile, fixed bottom action bar |
| 480 to 743px | Room cards in two columns, one hero tile, fixed bottom action bar |
| 744 to 1023px | Sticky rail, room cards in one column, full hero mosaic |
| 1024px and up | Wider rail, room cards in two columns |

Reduce columns as the page narrows, and never allow horizontal scrolling. Keep bottom padding on phones so the fixed bar never covers content.

## Elevation

Only two levels exist:

- **Flat:** the page, sections, room cards and footer.
- **Floating (`shadow-stay`):** the reservation card, the checkout summary and badges over pictures.

Do not add other shadows. Use borders and spacing to separate everything else.

## Components

### Buttons

- **Primary** (`stayPrimaryButton`): teal fill, white label, 8px radius, at least 48px tall. Used for **See available rooms** and **Continue to pay**.
- **Secondary** (`staySecondaryButton`): white fill, 1px ink border, 8px radius, at least 44px tall. Used for **Choose**, WhatsApp contact and recovery actions.
- **Text button:** ink text, underlined on hover. Used for **Back**.
- **Round icon button:** white, 40 to 44px, with a border. Used for steppers and month navigation.

All interactive elements show a 2px ink focus outline on keyboard focus.

### Page header

White, 80px tall, with a bottom hairline. The property name sits on the left and the language switch on the right, with the active language in an ink fill.

### Room pictures

- `StayHero` shows up to three rooms: one large tile and two stacked beside it. Phones show the first tile only.
- `RoomPlate` draws a neutral room scene while the product has no room photos. Rooms get different drawings according to their order.
- Replace plates with real photos when photo data exists, keeping the same tile sizes and 14px corners.

### Calendar

`AvailabilityMonth` uses 40px circular days with the lowest price underneath.

- **Available:** ink number, with a thin ink ring on hover.
- **Selected:** ink circle with white text.
- **In range:** a Surface Soft band connecting check-in and check-out.
- **Unavailable:** Muted Soft text with a strikethrough.

### Reservation card

`StayPlanner` holds the stay summary, a two-part date field, guest steppers and the main action. It is sticky in the rail. On phones, the action moves to a fixed bottom bar with the stay summary.

Steppers use `aria-disabled` at their limits, so a keyboard user keeps focus on the button.

### Room card

`RoomResults` shows a square picture, an optional **Free cancellation** badge, the room name and guest limit. Each rate then shows its name, terms, deposit, all-in total and a secondary **Choose** button.

### Checkout

`GuestDetailsForm` puts the guest's details, payment choice, terms and consent in the main column. The rail shows a summary with room, dates, total and amount due. On phones, the pay button stays in a fixed bottom bar.

Payment options are bordered rows. The selected row gets an ink outline and a Surface Soft fill.

### Inputs

White, 56px tall, with a 1px hairline border and 8px radius. The label sits above in `type-caption`. On focus, a 2px ink outline appears with no glow.

### Things to know

`ThingsToKnow` lists the property's real times, deposit, payment hold and maximum stay as icon rows. If the property has a WhatsApp number, a contact card follows.

### Footer

A plain white band with a top hairline and the copyright line in `type-caption-sm`.

## Accessibility

- White text on the primary color must stay at or above 4.5:1.
- Touch targets are at least 40px, and main actions are at least 48px.
- After a search, and when returning from checkout, focus moves to the room results.
- Do not rely on color alone. Unavailable days also use a strikethrough, and errors use text.
- Icons and room pictures are decorative and hidden from screen readers.

## Known gaps

- Room photos are not available yet.
- Ratings, reviews and host profiles are intentionally absent until real data exists.
- There is no loading skeleton. Loading states are plain text.
