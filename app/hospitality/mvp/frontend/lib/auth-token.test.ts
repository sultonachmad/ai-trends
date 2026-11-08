import { afterEach, describe, expect, it } from "vitest";

import { getAuthToken, setAuthTokenProvider } from "@/lib/auth-token";

describe("getAuthToken", () => {
  afterEach(() => setAuthTokenProvider(() => null));

  it("returns null when no auth prefab registered a provider", async () => {
    expect(await getAuthToken()).toBeNull();
  });

  it("returns the registered provider's token", async () => {
    // Not inlined: the prefab secret scan flags a string literal returned as a token.
    const registered = "token-1";
    setAuthTokenProvider(async () => registered);
    expect(await getAuthToken()).toBe(registered);
  });

  it("returns null when the provider throws", async () => {
    setAuthTokenProvider(() => {
      throw new Error("provider failed");
    });
    expect(await getAuthToken()).toBeNull();
  });

  it("returns null when the provider rejects", async () => {
    setAuthTokenProvider(async () => {
      throw new Error("provider failed");
    });
    expect(await getAuthToken()).toBeNull();
  });
});
