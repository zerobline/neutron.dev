import { afterEach, describe, expect, it, vi } from "vitest";
import { clearSessionToken } from "@/lib/auth-session";

describe("auth-session", () => {
  afterEach(() => {
    clearSessionToken();
  });

  it("clears a legacy session token", () => {
    localStorage.setItem("neutron_session_token", "session-token");
    clearSessionToken();
    expect(localStorage.getItem("neutron_session_token")).toBeNull();
  });

  it("is safe when window is unavailable", async () => {
    const originalWindow = globalThis.window;
    vi.stubGlobal("window", undefined);
    vi.resetModules();
    const { clearSessionToken: clearToken } = await import("@/lib/auth-session");
    expect(() => clearToken()).not.toThrow();
    vi.stubGlobal("window", originalWindow);
  });
});
