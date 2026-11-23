import { describe, expect, it } from "vitest";

import {
  IMPORT_ERROR_CODES,
  exportUrl,
  importErrorKey,
  linkBadgeClass,
  linkState,
  linksInConflict,
} from "@/lib/calendar-link-format";
import type { CalendarImportStatus, CalendarLink } from "@/lib/calendar-links-api";
import { LOCALES, translate } from "@/lib/i18n";

const imports: CalendarImportStatus = {
  url_hint: "airbnb.com",
  last_synced_at: "2027-01-01T00:00:00Z",
  last_error: null,
  failing_since: null,
  at_risk: false,
  busy_dates: 2,
};
const link = (over: Partial<CalendarLink> = {}): CalendarLink => ({
  id: "1",
  label: "Airbnb",
  room_type_id: "r",
  room_type_name: "Deluxe",
  imports,
  conflict_dates: [],
  ...over,
});

describe("linkState", () => {
  it("reads each state", () => {
    expect(linkState(link({ imports: null }))).toBe("export_only");
    expect(linkState(link({ imports: { ...imports, last_synced_at: null } }))).toBe("waiting");
    expect(linkState(link())).toBe("ok");
    expect(linkState(link({ imports: { ...imports, last_error: "timeout" } }))).toBe("failing");
    expect(
      linkState(link({ imports: { ...imports, last_error: "timeout", at_risk: true } })),
    ).toBe("at_risk");
  });

  it("marks trouble in the badge", () => {
    expect(linkBadgeClass("at_risk")).toContain("destructive");
    expect(linkBadgeClass("ok")).toContain("primary");
    expect(linkBadgeClass("waiting")).toContain("muted");
  });
});

describe("labels", () => {
  it("has every error and state in every language", () => {
    for (const locale of LOCALES) {
      for (const code of IMPORT_ERROR_CODES) {
        expect(translate(locale, importErrorKey(code))).not.toBe(importErrorKey(code));
      }
      for (const state of ["export_only", "waiting", "ok", "failing", "at_risk"]) {
        const key = `calendarLinks.state.${state}`;
        expect(translate(locale, key)).not.toBe(key);
      }
    }
  });

  it("treats an unknown error as unreadable", () => {
    expect(importErrorKey("something_new")).toBe("calendarLinks.error.unreadable");
  });
});

describe("helpers", () => {
  it("joins the address without a double slash", () => {
    expect(exportUrl("https://api.example.com/", "/api/ical/x.ics")).toBe(
      "https://api.example.com/api/ical/x.ics",
    );
  });

  it("finds links in conflict", () => {
    const busy = link({ id: "2", conflict_dates: ["2027-01-05"] });
    expect(linksInConflict([link(), busy])).toEqual([busy]);
  });
});
