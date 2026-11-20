import { describe, expect, it } from "vitest";

import { formatRupiah, parseRupiah } from "@/lib/money";

describe("formatRupiah", () => {
  it.each([
    [850000, "Rp 850.000"],
    ["850000.00", "Rp 850.000"],
    ["1700000", "Rp 1.700.000"],
    [999, "Rp 999"],
    [0, "Rp 0"],
    [10000, "Rp 10.000"],
    [500000000, "Rp 500.000.000"],
  ])("formats %s as %s", (value, text) => {
    expect(formatRupiah(value)).toBe(text);
  });

  it("returns an empty string for something that is not a number", () => {
    expect(formatRupiah("abc")).toBe("");
  });
});

describe("parseRupiah", () => {
  it.each([
    ["850000", 850000],
    ["850.000", 850000],
    ["Rp 850.000", 850000],
    ["rp850000", 850000],
    ["Rp. 1.700.000", 1700000],
    [" 850 000 ", 850000],
    ["10000", 10000],
  ])("reads %s as %s", (input, amount) => {
    expect(parseRupiah(input)).toBe(amount);
  });

  it.each(["", "   ", "abc", "850000.5", "850.000,50", "850,000", "8.50.000", "-5000", "0", "1e6", "850.0000"])(
    "rejects %s",
    (input) => {
      expect(parseRupiah(input)).toBeNull();
    },
  );
});
