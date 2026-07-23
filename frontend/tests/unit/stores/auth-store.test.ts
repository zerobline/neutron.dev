import { beforeEach, describe, expect, it, vi } from "vitest";

const apiMocks = vi.hoisted(() => ({
  me: vi.fn(),
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
}));

const sessionMocks = vi.hoisted(() => ({
  clearSessionToken: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: apiMocks,
}));

vi.mock("@/lib/auth-session", () => ({
  clearSessionToken: sessionMocks.clearSessionToken,
}));

const testUser = {
  id: "user-1",
  email: "user@example.com",
  display_name: "User",
  created_at: "2026-01-01",
};

const authResponse = testUser;

async function loadAuthStore() {
  vi.resetModules();
  const { useAuthStore } = await import("@/stores/auth-store");
  return useAuthStore;
}

describe("auth-store", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("refreshMe stores the current user", async () => {
    apiMocks.me.mockResolvedValue(testUser);
    const useAuthStore = await loadAuthStore();
    await useAuthStore.getState().refreshMe();
    expect(useAuthStore.getState()).toMatchObject({ user: testUser, loading: false, error: null });
  });

  it("refreshMe clears the user on failure", async () => {
    apiMocks.me.mockRejectedValue(new Error("unauthorized"));
    const useAuthStore = await loadAuthStore();
    await useAuthStore.getState().refreshMe();
    expect(useAuthStore.getState()).toMatchObject({ user: null, loading: false });
  });

  it("refreshMe skips fetch within TTL window", async () => {
    apiMocks.me.mockResolvedValue(testUser);
    const useAuthStore = await loadAuthStore();
    await useAuthStore.getState().refreshMe();
    expect(apiMocks.me).toHaveBeenCalledTimes(1);
    await useAuthStore.getState().refreshMe();
    expect(apiMocks.me).toHaveBeenCalledTimes(1);
  });

  it("refreshMe deduplicates concurrent calls", async () => {
    apiMocks.me.mockResolvedValue(testUser);
    const useAuthStore = await loadAuthStore();
    const p1 = useAuthStore.getState().refreshMe();
    const p2 = useAuthStore.getState().refreshMe();
    await Promise.all([p1, p2]);
    expect(apiMocks.me).toHaveBeenCalledTimes(1);
  });

  it("login stores the authenticated user and clears legacy browser tokens", async () => {
    apiMocks.login.mockResolvedValue(authResponse);
    const useAuthStore = await loadAuthStore();
    await useAuthStore.getState().login("user@example.com", "password123");
    expect(apiMocks.login).toHaveBeenCalledWith({ email: "user@example.com", password: "password123" });
    expect(sessionMocks.clearSessionToken).toHaveBeenCalled();
    expect(useAuthStore.getState()).toMatchObject({ user: testUser, loading: false, error: null });
  });

  it("login stores API errors and rethrows", async () => {
    apiMocks.login.mockRejectedValue(new Error("Invalid credentials"));
    const useAuthStore = await loadAuthStore();
    await expect(useAuthStore.getState().login("user@example.com", "bad")).rejects.toThrow("Invalid credentials");
    expect(useAuthStore.getState()).toMatchObject({ user: null, loading: false, error: "Invalid credentials" });
  });

  it("login falls back to a generic error message", async () => {
    apiMocks.login.mockRejectedValue("nope");
    const useAuthStore = await loadAuthStore();
    await expect(useAuthStore.getState().login("user@example.com", "bad")).rejects.toBe("nope");
    expect(useAuthStore.getState().error).toBe("Could not log in.");
  });

  it("register stores the created user and clears legacy browser tokens", async () => {
    apiMocks.register.mockResolvedValue(authResponse);
    const useAuthStore = await loadAuthStore();
    await useAuthStore.getState().register("user@example.com", "password123", "User");
    expect(apiMocks.register).toHaveBeenCalledWith({
      email: "user@example.com",
      password: "password123",
      display_name: "User",
    });
    expect(sessionMocks.clearSessionToken).toHaveBeenCalled();
    expect(useAuthStore.getState()).toMatchObject({ user: testUser, loading: false, error: null });
  });

  it("register stores API errors and rethrows", async () => {
    apiMocks.register.mockRejectedValue(new Error("Email taken"));
    const useAuthStore = await loadAuthStore();
    await expect(useAuthStore.getState().register("user@example.com", "password123")).rejects.toThrow("Email taken");
    expect(useAuthStore.getState()).toMatchObject({ user: null, loading: false, error: "Email taken" });
  });

  it("register falls back to a generic error message", async () => {
    apiMocks.register.mockRejectedValue("nope");
    const useAuthStore = await loadAuthStore();
    await expect(useAuthStore.getState().register("user@example.com", "password123")).rejects.toBe("nope");
    expect(useAuthStore.getState().error).toBe("Could not create account.");
  });

  it("logout clears the user and session token even when the API call fails", async () => {
    const useAuthStore = await loadAuthStore();
    useAuthStore.setState({ user: testUser });
    apiMocks.logout.mockRejectedValue(new Error("network"));
    await expect(useAuthStore.getState().logout()).rejects.toThrow("network");
    expect(apiMocks.logout).toHaveBeenCalled();
    expect(sessionMocks.clearSessionToken).toHaveBeenCalled();
    expect(useAuthStore.getState()).toMatchObject({ user: null, loading: false, error: null });
  });
});
