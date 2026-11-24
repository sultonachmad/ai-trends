import { plateVariant } from "@/lib/booking-page-format";

const VARIANT_COUNT = 3;

function Window({ variant }: { variant: number }) {
  const pane = "fill-stay-canvas stroke-stay-border-strong";
  if (variant === 0) {
    return <path d="M150 190v-70a50 50 0 0 1 100 0v70z" className={pane} strokeWidth="2" />;
  }
  if (variant === 1) {
    return (
      <>
        <rect x="104" y="70" width="88" height="120" rx="6" className={pane} strokeWidth="2" />
        <rect x="208" y="70" width="88" height="120" rx="6" className={pane} strokeWidth="2" />
      </>
    );
  }
  return (
    <>
      <circle cx="200" cy="125" r="62" className={pane} strokeWidth="2" />
      <path d="M200 63v124M138 125h124" className="stroke-stay-hairline" strokeWidth="2" />
    </>
  );
}

/** A drawn room scene, used because the booking page has no room photos yet. */
export function RoomPlate({
  id,
  order,
  className = "",
}: {
  id: string;
  order?: readonly string[];
  className?: string;
}) {
  return (
    <svg
      viewBox="0 0 400 400"
      preserveAspectRatio="xMidYMid meet"
      aria-hidden="true"
      className={`block bg-stay-surface-soft ${className}`}
    >
      {/* The floor runs past the viewBox so wide tiles show the whole scene uncropped. */}
      <rect x="-1200" y="292" width="2800" height="900" className="fill-stay-surface-strong" />
      <Window variant={plateVariant(id, VARIANT_COUNT, order)} />
      <rect x="82" y="212" width="236" height="92" rx="14" className="fill-stay-hairline" />
      <rect x="62" y="270" width="276" height="62" rx="12" className="fill-stay-canvas" />
      <rect x="62" y="298" width="276" height="34" rx="10" className="fill-stay-border-strong" />
      <rect x="96" y="244" width="92" height="38" rx="14" className="fill-stay-canvas stroke-stay-hairline" />
      <rect x="212" y="244" width="92" height="38" rx="14" className="fill-stay-canvas stroke-stay-hairline" />
      <path d="M352 332v-82" className="stroke-stay-muted" strokeWidth="3" />
      <path d="M334 250l8-34h20l8 34z" className="fill-stay-canvas stroke-stay-muted" strokeWidth="2" />
    </svg>
  );
}
