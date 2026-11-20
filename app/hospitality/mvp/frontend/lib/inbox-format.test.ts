import { describe, expect, it } from "vitest";

import {
  applyFirstPage,
  dayLabel,
  daysApart,
  formatClock,
  formatListTime,
  mergeConversations,
  mergeMessages,
  sameConversation,
  startsNewDay,
} from "@/lib/inbox-format";

const UTC = "UTC";
const JAKARTA = "Asia/Jakarta";

describe("mergeConversations", () => {
  const a = { id: "a", last_message_at: "2026-11-20T10:00:00Z", unread_count: 0 };
  const b = { id: "b", last_message_at: "2026-11-20T09:00:00Z", unread_count: 0 };

  it("replaces rows by id and keeps rows the fresh page did not include", () => {
    const fresh = [{ ...b, last_message_at: "2026-11-20T11:00:00Z", unread_count: 2 }];

    const merged = mergeConversations([a, b], fresh);

    expect(merged.map((c) => c.id)).toEqual(["b", "a"]);
    expect(merged[0].unread_count).toBe(2);
  });

  it("adds new conversations in activity order", () => {
    const c = { id: "c", last_message_at: "2026-11-20T09:30:00Z", unread_count: 1 };

    expect(mergeConversations([a, b], [c]).map((x) => x.id)).toEqual(["a", "c", "b"]);
  });

  it("does not change its inputs", () => {
    const current = [a, b];
    mergeConversations(current, [{ ...b, last_message_at: "2026-11-20T12:00:00Z" }]);

    expect(current).toEqual([a, b]);
  });
});

describe("applyFirstPage", () => {
  const row = (id: string, hour: string) => ({ id, last_message_at: `2026-11-20T${hour}:00:00Z` });

  it("uses the fresh page as the whole list when there is no further page", () => {
    expect(applyFirstPage([row("old", "01")], [row("a", "10")], false).map((r) => r.id)).toEqual([
      "a",
    ]);
  });

  it("keeps older rows loaded earlier and drops rows that left the list", () => {
    const current = [row("a", "10"), row("gone", "09"), row("b", "08"), row("older", "03")];
    const fresh = [row("new", "11"), row("a", "10"), row("b", "08")];

    expect(applyFirstPage(current, fresh, true).map((r) => r.id)).toEqual([
      "new",
      "a",
      "b",
      "older",
    ]);
  });

  it("returns an empty list when the server has nothing", () => {
    expect(applyFirstPage([row("a", "10")], [], false)).toEqual([]);
  });
});

describe("sameConversation", () => {
  const base = {
    id: "a",
    status: "open",
    unread_count: 0,
    last_message_at: "2026-11-20T10:00:00Z",
    reply_blocked_reason: null,
    guest: { name: "Budi", phone: "+6281234567890" },
  };

  it("is true for equal visible state in different objects", () => {
    expect(sameConversation(base, { ...base, guest: { ...base.guest } })).toBe(true);
  });

  it.each([
    { status: "resolved" },
    { unread_count: 2 },
    { last_message_at: "2026-11-20T10:05:00Z" },
    { reply_blocked_reason: "window_closed" },
    { guest: { name: "Sari", phone: "+6281234567890" } },
    { id: "b" },
  ])("is false when %o differs", (change) => {
    expect(sameConversation(base, { ...base, ...change })).toBe(false);
  });
});

describe("mergeMessages", () => {
  const m1 = { id: "1", created_at: "2026-11-20T10:00:00Z" };
  const m2 = { id: "2", created_at: "2026-11-20T10:01:00Z" };
  const m3 = { id: "3", created_at: "2026-11-20T10:02:00Z" };

  it("appends only messages not already shown, oldest first", () => {
    expect(mergeMessages([m1, m2], [m2, m3]).map((m) => m.id)).toEqual(["1", "2", "3"]);
  });

  it("returns the same array when nothing is new, so the screen does not re-render", () => {
    const current = [m1, m2];

    expect(mergeMessages(current, [m2])).toBe(current);
  });

  it("orders a late-arriving earlier message correctly", () => {
    expect(mergeMessages([m1, m3], [m2]).map((m) => m.id)).toEqual(["1", "2", "3"]);
  });
});

describe("time helpers", () => {
  const now = new Date("2026-11-20T03:00:00Z"); // 10:00 in Jakarta

  it("counts calendar days in the given timezone", () => {
    // 16:30Z on the 19th is already 23:30 on the 19th in Jakarta -> yesterday
    expect(daysApart(new Date("2026-11-19T16:30:00Z"), now, JAKARTA)).toBe(1);
    // 17:30Z on the 19th is 00:30 on the 20th in Jakarta -> today
    expect(daysApart(new Date("2026-11-19T17:30:00Z"), now, JAKARTA)).toBe(0);
  });

  it("shows the clock for today and the date for older items", () => {
    expect(formatListTime("2026-11-20T02:05:00Z", "id", now, UTC)).toBe("02.05");
    expect(formatListTime("2026-11-20T02:05:00Z", "en", now, UTC)).toBe("02:05");
    expect(formatListTime("2026-11-03T02:05:00Z", "en", now, UTC)).toBe("3 Nov");
    expect(formatListTime(null, "en", now, UTC)).toBe("");
  });

  it("formats the clock in the property timezone", () => {
    expect(formatClock("2026-11-20T03:00:00Z", "en", JAKARTA)).toBe("10:00");
  });

  it("labels days as today, yesterday or a date", () => {
    expect(dayLabel("2026-11-20T01:00:00Z", "en", now, UTC)).toEqual({ kind: "today" });
    expect(dayLabel("2026-11-19T01:00:00Z", "en", now, UTC)).toEqual({ kind: "yesterday" });
    expect(dayLabel("2026-11-10T01:00:00Z", "en", now, UTC)).toEqual({
      kind: "date",
      text: "10 Nov",
    });
  });

  it("detects the first message of a day", () => {
    expect(startsNewDay(null, "2026-11-20T01:00:00Z", UTC)).toBe(true);
    expect(startsNewDay("2026-11-20T00:10:00Z", "2026-11-20T23:50:00Z", UTC)).toBe(false);
    expect(startsNewDay("2026-11-19T23:50:00Z", "2026-11-20T00:10:00Z", UTC)).toBe(true);
  });
});
