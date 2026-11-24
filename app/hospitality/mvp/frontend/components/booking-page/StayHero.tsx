import { RoomPlate } from "@/components/booking-page/RoomPlate";

const MAX_TILES = 3;
const FALLBACK_ROOM = { id: "property", name: "" };

function tileClass(index: number, count: number): string {
  if (index > 0) return "hidden min-[744px]:block";
  return count === MAX_TILES ? "min-[744px]:row-span-2" : "";
}

/** Room mosaic at the top of the page: one large tile with up to two beside it. */
export function StayHero({ rooms }: { rooms: { id: string; name: string }[] }) {
  const tiles = rooms.length > 0 ? rooms.slice(0, MAX_TILES) : [FALLBACK_ROOM];
  const columns = tiles.length === 1 ? "" : "min-[744px]:grid-cols-2";
  const rows = tiles.length === MAX_TILES ? "min-[744px]:grid-rows-2" : "";
  return (
    <div
      className={`grid h-64 gap-2 overflow-hidden rounded-stay-md min-[744px]:h-[400px] ${columns} ${rows}`}
    >
      {tiles.map((room, index) => (
        <div key={room.id} className={`relative min-h-0 ${tileClass(index, tiles.length)}`}>
          <RoomPlate id={room.id} order={rooms.map((item) => item.id)} className="h-full w-full" />
          {room.name && (
            <span className="absolute left-3 top-3 max-w-[calc(100%-24px)] truncate rounded-full bg-stay-canvas px-2.5 py-1 text-type-badge text-stay-ink shadow-stay">
              {room.name}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
