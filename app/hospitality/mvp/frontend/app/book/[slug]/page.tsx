"use client";

/**
 * Public booking page — `/book/<page name>`. No sign-in. Bahasa Indonesia by default with
 * an English switch. A shared link can pre-fill dates, guests and the room type.
 */

import { Suspense, useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { useParams, useSearchParams } from "next/navigation";

import { AvailabilityMonth } from "@/components/booking-page/AvailabilityMonth";
import { GuestDetailsForm } from "@/components/booking-page/GuestDetailsForm";
import { RoomResults } from "@/components/booking-page/RoomResults";
import { staySectionTitle } from "@/components/booking-page/stay-classes";
import { StayHero } from "@/components/booking-page/StayHero";
import { StayPlanner } from "@/components/booking-page/StayPlanner";
import { ThingsToKnow } from "@/components/booking-page/ThingsToKnow";
import { LanguageSwitch } from "@/components/LanguageSwitch";
import { ApiError } from "@/lib/api-client";
import {
  fetchAvailability,
  fetchPublicPage,
  type Availability,
  type PublicPage,
  type RateOption,
  type RoomResult,
  type StayQuery,
} from "@/lib/booking-page-api";
import { errorCode, nightsBetween, parseDeepLink } from "@/lib/booking-page-format";
import { useLocale } from "@/lib/locale-store";

const CONTAINER = "mx-auto w-full max-w-[1128px] px-4 min-[744px]:px-6";
const NOT_FOUND = 404;

function BookingPage() {
  const { slug } = useParams<{ slug: string }>();
  const searchParams = useSearchParams();
  const { t } = useLocale();
  const [deepLink] = useState(() => parseDeepLink(new URLSearchParams(searchParams.toString())));
  const [page, setPage] = useState<PublicPage | null>(null);
  const [missing, setMissing] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [arrival, setArrival] = useState(deepLink.arrival ?? "");
  const [departure, setDeparture] = useState(deepLink.departure ?? "");
  const [adults, setAdults] = useState(deepLink.adults);
  const [children, setChildren] = useState(deepLink.children);
  const [result, setResult] = useState<Availability | null>(null);
  const [searched, setSearched] = useState<StayQuery | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [chosen, setChosen] = useState<{ room: RoomResult; option: RateOption } | null>(null);
  const resultsRef = useRef<HTMLDivElement>(null);
  const revealResults = useRef(false);

  const runSearch = useCallback(
    async (stay: StayQuery) => {
      setBusy(true);
      setError(null);
      setChosen(null);
      try {
        setResult(await fetchAvailability(slug, stay));
        setSearched(stay);
      } catch (cause) {
        setResult(null);
        setError(t(`book.error.${errorCode(cause)}`, { phone: "" }));
      } finally {
        setBusy(false);
      }
    },
    [slug, t],
  );

  useEffect(() => {
    let cancelled = false;
    fetchPublicPage(slug)
      .then((found) => {
        if (cancelled) return;
        setPage(found);
        if (deepLink.arrival && deepLink.departure) {
          void runSearch({
            arrival: deepLink.arrival,
            departure: deepLink.departure,
            adults: deepLink.adults,
            children: deepLink.children,
          });
        }
      })
      .catch((cause) => {
        if (cancelled) return;
        if (cause instanceof ApiError && cause.status === NOT_FOUND) setMissing(true);
        else setLoadError(true);
      });
    return () => {
      cancelled = true;
    };
    // the first search runs once, from the link the guest opened
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug]);

  const pick = (date: string) => {
    setResult(null);
    setChosen(null);
    if (!arrival || departure || date <= arrival) {
      setArrival(date);
      setDeparture("");
    } else {
      setDeparture(date);
    }
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    revealResults.current = true;
    void runSearch({ arrival, departure, adults, children });
  };

  // Results land below the fold on a phone: take the guest (and screen reader) there.
  useEffect(() => {
    if (!result || chosen || !revealResults.current) return;
    revealResults.current = false;
    resultsRef.current?.focus({ preventScroll: true });
    resultsRef.current?.scrollIntoView({ block: "start" });
  }, [result, chosen]);

  useEffect(() => {
    if (chosen) window.scrollTo({ top: 0 });
  }, [chosen]);

  const shell = (content: React.ReactNode, name?: string, footer = false) => (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-stay-hairline">
        <div className={`${CONTAINER} flex h-20 items-center justify-between gap-4`}>
          <p className="min-w-0 truncate text-type-title text-stay-primary min-[744px]:text-type-display-sm">{name}</p>
          {/* The shared switch reads theme variables: point them at this page's tokens. */}
          <div className="shrink-0 [--aside-active-bg:theme(colors.stay.surface-strong)] [--card-foreground:theme(colors.stay.ink)] [--input-border:theme(colors.stay.hairline)] [--primary-color:theme(colors.stay.ink)] [--sub-section-bg:theme(colors.stay.canvas)]">
            <LanguageSwitch />
          </div>
        </div>
      </header>
      <div className={`${CONTAINER} flex-1 pb-28 min-[744px]:pb-16`}>{content}</div>
      {footer && (
        <footer className="border-t border-stay-hairline">
          <p className={`${CONTAINER} py-6 pb-28 text-type-caption-sm text-stay-muted min-[744px]:pb-6`}>
            © {page?.today.slice(0, 4)} {name}
          </p>
        </footer>
      )}
    </div>
  );
  const notice = (text: string, role?: "alert") => (
    <p role={role} className="py-16 text-center text-type-body text-stay-muted">
      {text}
    </p>
  );

  if (missing) return shell(notice(t("book.notFound"), "alert"));
  if (loadError) return shell(notice(t("book.loadFailed"), "alert"));
  if (!page) return shell(notice(t("common.loading")));

  const validStay = Boolean(arrival && departure && departure > arrival);
  const nights = validStay ? nightsBetween(arrival, departure) : 0;
  const tooLong = nights > page.max_nights;
  if (chosen && searched) {
    return shell(
      <GuestDetailsForm
        slug={slug}
        stay={searched}
        room={chosen.room}
        option={chosen.option}
        depositPercent={page.deposit_percent}
        holdMinutes={page.hold_minutes}
        whatsapp={page.whatsapp_phone}
        roomOrder={page.rooms.map((room) => room.id)}
        onBack={() => {
          revealResults.current = true;
          setChosen(null);
        }}
        onPriceChanged={() => void runSearch(searched)}
      />,
      page.property_name,
      true,
    );
  }
  return shell(
    <>
      <div className="pt-6">
        <StayHero rooms={page.rooms} />
      </div>
      <div className="grid gap-x-12 min-[744px]:grid-cols-[minmax(0,1fr)_320px] lg:grid-cols-[minmax(0,1fr)_372px]">
        <div className="min-w-0 min-[744px]:col-start-1">
          <div className="py-6">
            <h1 className="text-type-display-xl">{page.property_name}</h1>
            {page.city && <p className="text-type-body text-stay-muted">{page.city}</p>}
          </div>
          <section className="border-t border-stay-hairline py-8">
            <h2 className={staySectionTitle}>{t("book.datesTitle")}</h2>
            <p className="mb-4 text-type-body-sm text-stay-muted">{t("book.datesHint")}</p>
            <AvailabilityMonth
              slug={slug}
              today={page.today}
              lastArrival={page.last_arrival}
              arrival={arrival}
              departure={departure}
              onPick={pick}
            />
          </section>
        </div>
        {/* Not an <aside>: the root layout reads any aside as the staff sidebar. */}
        <div className="min-[744px]:col-start-2 min-[744px]:row-span-3 min-[744px]:row-start-1 min-[744px]:pt-6">
          <div className="min-[744px]:sticky min-[744px]:top-6">
            <StayPlanner
              today={page.today}
              lastArrival={page.last_arrival}
              arrival={arrival}
              departure={departure}
              adults={adults}
              childCount={children}
              nights={nights}
              tooLong={tooLong}
              busy={busy}
              onArrival={(value) => {
                setArrival(value);
                setResult(null);
              }}
              onDeparture={(value) => {
                setDeparture(value);
                setResult(null);
              }}
              onAdults={setAdults}
              onChildren={setChildren}
              onSubmit={submit}
            />
          </div>
        </div>
        <div
          ref={resultsRef}
          tabIndex={-1}
          className="min-w-0 outline-none min-[744px]:col-start-1 [&:not(:empty)]:border-t [&:not(:empty)]:border-stay-hairline [&:not(:empty)]:py-8 max-[743.98px]:[&:not(:empty)]:mt-8"
        >
          {error && (
            <p role="alert" className="text-type-body-sm text-stay-error">
              {error}
            </p>
          )}
          {result && searched && (
            <RoomResults
              result={result}
              arrival={searched.arrival}
              depositPercent={page.deposit_percent}
              preferredRoom={deepLink.room}
              roomOrder={page.rooms.map((room) => room.id)}
              onChoose={(room, option) => setChosen({ room, option })}
            />
          )}
        </div>
        <div className="min-w-0 max-[743.98px]:mt-8 min-[744px]:col-start-1">
          <ThingsToKnow page={page} />
        </div>
      </div>
    </>,
    page.property_name,
    true,
  );
}

export default function BookingPageRoute() {
  return (
    <Suspense fallback={null}>
      <BookingPage />
    </Suspense>
  );
}
