import { describe, expect, it } from "vitest";

import { safeCallbackUrl } from "@/lib/safe-callback";

describe("safeCallbackUrl", () => {
  it("keeps paths inside the app", () => {
    expect(safeCallbackUrl("/join/abc_DEF-1", "/dashboard")).toBe("/join/abc_DEF-1");
    expect(safeCallbackUrl("/hotel/front-desk?tab=rooms", "/dashboard")).toBe("/hotel/front-desk?tab=rooms");
  });

  it("refuses other sites, scripts and tricks", () => {
    for (const bad of [
      null,
      "",
      "https://evil.example",
      "//evil.example",
      "/\\evil.example",
      "javascript:alert(1)",
      "/\tjavascript",
      "dashboard",
    ]) {
      expect(safeCallbackUrl(bad, "/dashboard")).toBe("/dashboard");
    }
  });
});
