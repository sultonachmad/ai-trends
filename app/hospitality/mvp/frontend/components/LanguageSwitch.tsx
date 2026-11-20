"use client";

import { LOCALES } from "@/lib/i18n";
import { useLocale } from "@/lib/locale-store";

/** Two-button language toggle for staff screens (Bahasa Indonesia / English). */
export function LanguageSwitch() {
  const { locale, setLocale, t } = useLocale();

  return (
    <div role="group" aria-label={t("language.label")} className="inline-flex gap-1">
      {LOCALES.map((option) => (
        <button
          key={option}
          type="button"
          aria-pressed={locale === option}
          onClick={() => setLocale(option)}
          className={`rounded-md border border-border px-3 py-1 text-xs font-medium ${
            locale === option
              ? "bg-primary text-primary-foreground"
              : "bg-card text-card-foreground hover:bg-accent"
          }`}
        >
          {t(`language.${option}`)}
        </button>
      ))}
    </div>
  );
}

export default LanguageSwitch;
