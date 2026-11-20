import { describe, expect, it } from "vitest";

import {
  actionsFor,
  canMatch,
  eventKey,
  nextStep,
  parsePercent,
  problemKey,
  statusBadgeClass,
  statusKey,
} from "@/lib/channel-format";
import type { ConnectionAction, ConnectionStatus } from "@/lib/channels-api";
import { LOCALES, translate } from "@/lib/i18n";

const STATUSES: ConnectionStatus[] = ["draft", "testing", "live", "paused", "error", "disconnected"];
const ACTIONS: ConnectionAction[] = ["test", "go-live", "pause", "resume", "disconnect"];
const EVENTS = [
  "started",
  "tested",
  "matching_changed",
  "products_refreshed",
  "settings_changed",
  "went_live",
  "paused",
  "resumed",
  "disconnected",
];

describe("labels", () => {
  it("has a label and badge for every status in every language", () => {
    for (const status of STATUSES) {
      expect(statusBadgeClass(status)).not.toBe("");
      for (const locale of LOCALES) {
        expect(translate(locale, statusKey(status))).not.toBe(statusKey(status));
      }
    }
  });

  it("has a sentence for every problem, known or not", () => {
    for (const problem of ["unknown_property", "channel_unavailable", "something_new"]) {
      for (const locale of LOCALES) {
        expect(translate(locale, problemKey(problem))).not.toBe(problemKey(problem));
      }
    }
    expect(problemKey("something_new")).toBe("channels.problem.other");
  });

  it("has a label for every action and history event in every language", () => {
    for (const locale of LOCALES) {
      for (const action of ACTIONS) {
        expect(translate(locale, `channels.action.${action}`)).not.toBe(`channels.action.${action}`);
      }
      for (const event of EVENTS) {
        const key = eventKey(`channel.connection.${event}`);
        expect(translate(locale, key)).not.toBe(key);
      }
    }
  });
});

describe("nextStep", () => {
  it("walks from test to match to live", () => {
    expect(nextStep({ status: "draft", mapped_pairs: 0 })).toBe("test");
    expect(nextStep({ status: "error", mapped_pairs: 0 })).toBe("test");
    expect(nextStep({ status: "testing", mapped_pairs: 0 })).toBe("match");
    expect(nextStep({ status: "testing", mapped_pairs: 2 })).toBe("live");
  });

  it("is done once the connection is in use or ended", () => {
    for (const status of ["live", "paused", "disconnected"] as const) {
      expect(nextStep({ status, mapped_pairs: 1 })).toBeNull();
    }
  });
});

describe("actionsFor", () => {
  it("offers go-live only once something is matched", () => {
    expect(actionsFor({ status: "testing", mapped_pairs: 0 })).not.toContain("go-live");
    expect(actionsFor({ status: "testing", mapped_pairs: 1 })[0]).toBe("go-live");
  });

  it("offers what each status allows", () => {
    expect(actionsFor({ status: "draft", mapped_pairs: 0 })).toEqual(["test", "disconnect"]);
    expect(actionsFor({ status: "live", mapped_pairs: 1 })).toEqual(["pause", "test", "disconnect"]);
    expect(actionsFor({ status: "paused", mapped_pairs: 1 })[0]).toBe("resume");
    expect(actionsFor({ status: "disconnected", mapped_pairs: 1 })).toEqual([]);
  });

  it("allows matching only when the channel's rooms are known", () => {
    expect(STATUSES.filter(canMatch)).toEqual(["testing", "live", "paused"]);
  });
});

describe("parsePercent", () => {
  it("reads whole and decimal percentages, with a comma or a point", () => {
    expect(parsePercent("15", 0, 50)).toBe(15);
    expect(parsePercent(" 17,5 ", 0, 50)).toBe(17.5);
    expect(parsePercent("-10", -50, 100)).toBe(-10);
    expect(parsePercent("0", 0, 50)).toBe(0);
  });

  it("refuses anything out of range or not a number", () => {
    expect(
      ["51", "-1", "1.234", "abc", "", "10%"].map((value) => parsePercent(value, 0, 50)),
    ).toEqual(Array(6).fill(null));
  });
});
