"use client";

import { useEffect, useState, type FormEvent } from "react";

import {
  fetchBookingPageSetup,
  saveBookingPageSetup,
  type BookingPageSetup,
} from "@/lib/booking-page-api";
import { bookingPageUrl, isValidSlug } from "@/lib/booking-page-format";
import { useLocale } from "@/lib/locale-store";
import { useCan } from "@/lib/rbac-store";

const errorText = (cause: unknown) => (cause instanceof Error ? cause.message : String(cause));
const inputClass =
  "w-full rounded-md border border-border bg-card px-3 py-2 text-sm text-card-foreground focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-60";

/** The owner's setup of the public booking page. */
export function BookingPageSection() {
  const { t } = useLocale();
  const canView = useCan("booking_page:view");
  const canEdit = useCan("booking_page:edit");
  const [setup, setSetup] = useState<BookingPageSetup | null>(null);
  const [slug, setSlug] = useState("");
  const [published, setPublished] = useState(false);
  const [sold, setSold] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!canView) return;
    let cancelled = false;
    fetchBookingPageSetup()
      .then((found) => {
        if (cancelled) return;
        setSetup(found);
        setSlug(found.slug ?? "");
        setPublished(found.is_published);
        setSold(new Set(found.plans.filter((plan) => plan.sold).map((plan) => plan.id)));
      })
      .catch((cause) => {
        if (!cancelled) setError(errorText(cause));
      });
    return () => {
      cancelled = true;
    };
  }, [canView]);

  if (!canView) return null;

  const toggle = (id: string) => {
    setSaved(false);
    setSold((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      const result = await saveBookingPageSetup({
        slug: slug.trim().toLowerCase(),
        is_published: published,
        sold_plan_ids: [...sold],
      });
      setSetup(result);
      setSaved(true);
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy(false);
    }
  };

  const liveUrl =
    setup?.slug && setup.is_published && typeof window !== "undefined"
      ? bookingPageUrl(window.location.origin, setup.slug)
      : null;
  const slugOk = isValidSlug(slug.trim().toLowerCase());
  const copy = async () => {
    if (!liveUrl) return;
    try {
      await navigator.clipboard.writeText(liveUrl);
      setCopied(true);
    } catch {
      setCopied(false); // the address stays visible and selectable
    }
  };

  return (
    <section
      aria-labelledby="booking-page-heading"
      className="rounded-xl border border-border bg-card p-6 text-card-foreground shadow-sm"
    >
      <h2 id="booking-page-heading" className="text-lg font-semibold">
        {t("bookingPage.title")}
      </h2>
      <p className="mt-1 text-sm text-muted-foreground">{t("bookingPage.intro")}</p>
      {!setup ? (
        <p className="mt-3 text-sm text-muted-foreground">
          {error ?? t("common.loading")}
        </p>
      ) : (
        <form onSubmit={(event) => void submit(event)} className="mt-4 space-y-4">
          <div>
            <label htmlFor="page-slug" className="mb-1 block text-sm font-medium">
              {t("bookingPage.slug")}
            </label>
            <input
              id="page-slug"
              required
              maxLength={40}
              disabled={!canEdit}
              value={slug}
              placeholder="villa-ubud"
              onChange={(event) => {
                setSlug(event.target.value);
                setSaved(false);
              }}
              className={inputClass}
            />
            <p className="mt-1 text-xs text-muted-foreground">{t("bookingPage.slugHint")}</p>
          </div>
          <fieldset className="space-y-1">
            <legend className="text-sm font-medium">{t("bookingPage.plans")}</legend>
            {setup.plans.length === 0 && (
              <p className="text-sm text-muted-foreground">{t("bookingPage.noPlans")}</p>
            )}
            {setup.plans.map((plan) => (
              <label key={plan.id} className="flex items-center gap-2 py-1 text-sm">
                <input
                  type="checkbox"
                  disabled={!canEdit}
                  checked={sold.has(plan.id)}
                  onChange={() => toggle(plan.id)}
                />
                {plan.name}
              </label>
            ))}
          </fieldset>
          <label className="flex items-center gap-2 text-sm font-medium">
            <input
              type="checkbox"
              disabled={!canEdit}
              checked={published}
              onChange={(event) => {
                setPublished(event.target.checked);
                setSaved(false);
              }}
            />
            {t("bookingPage.publish")}
          </label>
          {liveUrl && (
            <div className="space-y-2 rounded-lg bg-muted p-3 text-sm">
              <p className="font-medium">{t("bookingPage.live")}</p>
              <a href={liveUrl} target="_blank" rel="noopener noreferrer" className="break-all text-primary underline">
                {liveUrl}
              </a>
              <div>
                <button
                  type="button"
                  onClick={() => void copy()}
                  className="rounded-md border border-border bg-card px-3 py-1 text-sm hover:bg-accent"
                >
                  {t(copied ? "calendarLinks.copied" : "calendarLinks.copy")}
                </button>
              </div>
              <p className="text-xs text-muted-foreground">{t("bookingPage.prefillHint")}</p>
            </div>
          )}
          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}
          {saved && <p role="status" className="text-sm">{t("bookingPage.saved")}</p>}
          {canEdit && (
            <button
              type="submit"
              disabled={busy || !slugOk}
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {t("bookingPage.save")}
            </button>
          )}
        </form>
      )}
    </section>
  );
}
