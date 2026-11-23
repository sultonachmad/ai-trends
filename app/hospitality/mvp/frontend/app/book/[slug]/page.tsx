"use client";

/**
 * Public booking page — `/book/<page name>`. No sign-in. Bahasa Indonesia by default with
 * an English switch. A shared link can pre-fill dates, guests and the room type.
 */

import { Suspense, useCallback, useEffect, useState, type FormEvent } from "react";
import { useParams, useSearchParams } from "next/navigation";

import { AvailabilityMonth } from "@/components/booking-page/AvailabilityMonth";
import { GuestDetailsForm } from "@/components/booking-page/GuestDetailsForm";
import { RoomResults } from "@/components/booking-page/RoomResults";
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
import { addDays, errorCode, nightsBetween, parseDeepLink } from "@/lib/booking-page-format";
import { useLocale } from "@/lib/locale-store";

const inputClass =
  "w-full rounded-md border border-border bg-card px-3 py-2 text-base text-card-foreground focus:outline-none focus:ring-2 focus:ring-primary";
const labelClass = "mb-1 block text-sm font-medium";
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
    void runSearch({ arrival, departure, adults, children });
  };

  const shell = (content: React.ReactNode) => (
    <div className="mx-auto min-h-screen max-w-2xl space-y-4 bg-background p-4 text-foreground">
      <div className="flex justify-end">
        <LanguageSwitch />
      </div>
      {content}
    </div>
  );

  if (missing) return shell(<p role="alert">{t("book.notFound")}</p>);
  if (loadError) return shell(<p role="alert">{t("book.loadFailed")}</p>);
  if (!page) return shell(<p className="text-muted-foreground">{t("common.loading")}</p>);

  const validStay = Boolean(arrival && departure && departure > arrival);
  const tooLong = validStay && nightsBetween(arrival, departure) > page.max_nights;
  return shell(
    <>
      <header>
        <h1 className="text-2xl font-bold">{page.property_name}</h1>
        {page.city && <p className="text-sm text-muted-foreground">{page.city}</p>}
        <p className="text-sm text-muted-foreground">
          {t("book.times", {
            in: page.check_in_time.slice(0, 5),
            out: page.check_out_time.slice(0, 5),
          })}
        </p>
      </header>
      {chosen && searched ? (
        <GuestDetailsForm
          slug={slug}
          stay={searched}
          room={chosen.room}
          option={chosen.option}
          depositPercent={page.deposit_percent}
          holdMinutes={page.hold_minutes}
          whatsapp={page.whatsapp_phone}
          onBack={() => setChosen(null)}
          onPriceChanged={() => void runSearch(searched)}
        />
      ) : (
        <>
          <form
            onSubmit={submit}
            className="space-y-4 rounded-xl border border-border bg-card p-4 text-card-foreground shadow-sm"
          >
            <AvailabilityMonth
              slug={slug}
              today={page.today}
              lastArrival={page.last_arrival}
              arrival={arrival}
              departure={departure}
              onPick={pick}
            />
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="book-arrival" className={labelClass}>
                  {t("book.arrival")}
                </label>
                <input
                  id="book-arrival"
                  type="date"
                  required
                  min={page.today}
                  max={page.last_arrival}
                  value={arrival}
                  onChange={(event) => {
                    setArrival(event.target.value);
                    setResult(null);
                  }}
                  className={inputClass}
                />
              </div>
              <div>
                <label htmlFor="book-departure" className={labelClass}>
                  {t("book.departure")}
                </label>
                <input
                  id="book-departure"
                  type="date"
                  required
                  min={arrival ? addDays(arrival, 1) : page.today}
                  value={departure}
                  onChange={(event) => {
                    setDeparture(event.target.value);
                    setResult(null);
                  }}
                  className={inputClass}
                />
              </div>
              <div>
                <label htmlFor="book-adults" className={labelClass}>
                  {t("book.adults")}
                </label>
                <input
                  id="book-adults"
                  type="number"
                  inputMode="numeric"
                  min={1}
                  max={50}
                  required
                  value={adults}
                  onChange={(event) => setAdults(Number(event.target.value))}
                  className={inputClass}
                />
              </div>
              <div>
                <label htmlFor="book-children" className={labelClass}>
                  {t("book.children")}
                </label>
                <input
                  id="book-children"
                  type="number"
                  inputMode="numeric"
                  min={0}
                  max={50}
                  required
                  value={children}
                  onChange={(event) => setChildren(Number(event.target.value))}
                  className={inputClass}
                />
              </div>
            </div>
            {tooLong && (
              <p role="alert" className="text-sm text-destructive">
                {t("book.error.stay_too_long")}
              </p>
            )}
            <button
              type="submit"
              disabled={busy || !validStay || tooLong}
              className="min-h-11 w-full rounded-md bg-primary px-4 py-2 font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {t(busy ? "book.searching" : "book.search")}
            </button>
          </form>
          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}
          {result && searched && (
            <RoomResults
              result={result}
              arrival={searched.arrival}
              depositPercent={page.deposit_percent}
              preferredRoom={deepLink.room}
              onChoose={(room, option) => setChosen({ room, option })}
            />
          )}
        </>
      )}
    </>,
  );
}

export default function BookingPageRoute() {
  return (
    <Suspense fallback={null}>
      <BookingPage />
    </Suspense>
  );
}
