import { afterEach, describe, expect, it, vi } from "vitest";

type MockResponseInit = {
  ok?: boolean;
  status?: number;
  statusText?: string;
  headers?: HeadersInit;
};

function response(body: unknown, init: MockResponseInit = {}) {
  return {
    ok: init.ok ?? true,
    status: init.status ?? 200,
    statusText: init.statusText ?? "OK",
    headers: new Headers(init.headers ?? { "content-type": "application/json" }),
    text: vi.fn().mockResolvedValue(typeof body === "string" ? body : JSON.stringify(body)),
    json: vi.fn().mockResolvedValue(body),
  } as unknown as Response;
}

async function importApi(base?: string) {
  vi.resetModules();
  if (base === undefined) {
    delete process.env.NEXT_PUBLIC_API_URL;
  } else {
    process.env.NEXT_PUBLIC_API_URL = base;
  }
  return import("@/lib/api");
}

describe("api", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    delete process.env.NEXT_PUBLIC_API_URL;
  });

  it("uses the default base URL and sends createProject JSON", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response({ id: "p1" }));
    vi.stubGlobal("fetch", fetchMock);
    const { api } = await importApi();

    await expect(api.createProject({ name: "Name", description: "Desc", template: "saas" })).resolves.toEqual({ id: "p1" });
    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/api/projects", {
      method: "POST",
      body: JSON.stringify({ name: "Name", description: "Desc", template: "saas" }),
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      signal: expect.any(AbortSignal),
    });
  });

  it.each([
    ["listProjects", "/api/projects", undefined],
    ["getProject", "/api/projects/p1", "p1"],
    ["getProjectFiles", "/api/projects/p1/files", "p1"],
    ["getProjectMessages", "/api/projects/p1/messages", "p1"],
    ["getProjectRuntime", "/api/projects/p1/runtime", "p1"],
    ["listTemplates", "/api/templates", undefined],
    ["getTemplate", "/api/templates/saas", "saas"],
    ["listUploads", "/api/projects/p1/uploads", "p1"],
    ["getAvailableModels", "/api/settings/models", undefined],
    ["getProviderSettings", "/api/settings/provider", undefined],
    ["getProviderModels", "/api/settings/providers/openai/models", "openai"],
    ["listProviderSettings", "/api/settings/providers", undefined],
    ["listSearchProviderSettings", "/api/settings/search-providers", undefined],
    ["me", "/api/auth/me", undefined],
  ] as const)("calls %s", async (method, path, arg) => {
    const fetchMock = vi.fn().mockResolvedValue(response({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);
    const { api } = await importApi("https://api.test");

    switch (method) {
      case "listProjects":
      case "listTemplates":
      case "getAvailableModels":
      case "getProviderSettings":
      case "listProviderSettings":
      case "listSearchProviderSettings":
      case "me":
        await api[method]();
        break;
      case "getProviderModels":
        await api.getProviderModels("openai");
        break;
      case "getProject":
      case "getProjectFiles":
      case "getProjectMessages":
      case "getProjectRuntime":
      case "listUploads":
        await api[method](String(arg));
        break;
      case "getTemplate":
        await api.getTemplate(String(arg));
        break;
      default:
        throw new Error(`Unhandled method in test: ${method}`);
    }
    expect(fetchMock).toHaveBeenCalledWith(`https://api.test${path}`, {
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      signal: expect.any(AbortSignal),
    });
  });

  it("starts and stops project runtime", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({ status: "installing" }))
      .mockResolvedValueOnce(response({ status: "stopped" }));
    vi.stubGlobal("fetch", fetchMock);
    const { api } = await importApi("https://api.test");

    await expect(api.startProjectRuntime("p1")).resolves.toEqual({ status: "installing" });
    await expect(api.stopProjectRuntime("p1")).resolves.toEqual({ status: "stopped" });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "https://api.test/api/projects/p1/runtime/start",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "https://api.test/api/projects/p1/runtime/stop",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("calls MCP connector settings endpoints", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({ connectors: [] }))
      .mockResolvedValueOnce(response({ key: "github", has_api_key: true }))
      .mockResolvedValueOnce(response({ key: "github", has_api_key: false }));
    vi.stubGlobal("fetch", fetchMock);
    const { api } = await importApi("https://api.test");

    await expect(api.listMcpConnectorSettings()).resolves.toEqual({ connectors: [] });
    await expect(
      api.updateMcpConnectorSettings({ key: "github", api_key: "ghp_x" }),
    ).resolves.toEqual({ key: "github", has_api_key: true });
    await expect(api.clearMcpConnectorKey("github")).resolves.toEqual({
      key: "github",
      has_api_key: false,
    });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "https://api.test/api/settings/mcp-connectors",
      expect.objectContaining({ credentials: "include" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "https://api.test/api/settings/mcp-connector",
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({ key: "github", api_key: "ghp_x" }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "https://api.test/api/settings/mcp-connector/github/key",
      expect.objectContaining({ method: "DELETE" }),
    );
  });

  it("calls project skills endpoints", async () => {
    const skillsPayload = { skills: [{ name: "mvp-scope-discipline", enabled: true, agents: ["all"] }] };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response([]))
      .mockResolvedValueOnce(response({ skills: [] }))
      .mockResolvedValueOnce(response(skillsPayload))
      .mockResolvedValueOnce(response(skillsPayload))
      .mockResolvedValueOnce(response({ skills: [] }));
    vi.stubGlobal("fetch", fetchMock);
    const { api } = await importApi("https://api.test");

    await expect(api.listBuiltinSkills()).resolves.toEqual([]);
    await expect(api.getProjectSkills("p1")).resolves.toEqual({ skills: [] });
    await expect(
      api.saveProjectSkills("p1", [{ name: "mvp-scope-discipline", enabled: true, agents: ["all"] }]),
    ).resolves.toEqual(skillsPayload);
    await expect(
      api.createProjectSkill("p1", {
        name: "brand-voice",
        description: "Friendly",
        body: "Be warm.",
      }),
    ).resolves.toEqual(skillsPayload);
    await expect(api.deleteProjectSkill("p1", "brand-voice")).resolves.toEqual({ skills: [] });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "https://api.test/api/skills",
      expect.objectContaining({ credentials: "include" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "https://api.test/api/projects/p1/skills",
      expect.objectContaining({ credentials: "include" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "https://api.test/api/projects/p1/skills",
      expect.objectContaining({ method: "PUT" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      "https://api.test/api/projects/p1/skills",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      5,
      "https://api.test/api/projects/p1/skills/brand-voice",
      expect.objectContaining({ method: "DELETE" }),
    );
  });

  it("handles delete responses without JSON bodies", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response("", { status: 204, headers: {} }))
      .mockResolvedValueOnce(response("", { status: 200, headers: {} }));
    vi.stubGlobal("fetch", fetchMock);
    const { api } = await importApi();

    await expect(api.deleteProject("p1")).resolves.toBeUndefined();
    await expect(api.deleteProject("p2")).resolves.toBeUndefined();
    expect(fetchMock).toHaveBeenNthCalledWith(1, "http://localhost:8000/api/projects/p1", {
      method: "DELETE",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      signal: expect.any(AbortSignal),
    });
  });

  it("returns text for non-JSON successful responses", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response("plain", { headers: { "content-type": "text/plain" } })));
    const { api } = await importApi();

    await expect(api.listProjects()).resolves.toBe("plain");
  });

  it("rethrows non-timeout fetch failures", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network down")));
    const { api } = await importApi();

    await expect(api.listProjects()).rejects.toThrow("network down");
  });

  it("throws exact errors for non-OK responses", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({ error: true }, { ok: false, status: 500, statusText: "Server Error" })));
    const { api } = await importApi();

    await expect(api.listProjects()).rejects.toThrow("API error: 500 Server Error");
  });

  it("updates provider settings", async () => {
    const provider = { provider: "openai-compatible", model: "kimchi/kimi-k2.7", base_url: "http://localhost:20128/v1", has_api_key: false, effective_model: "openai/kimchi/kimi-k2.7" };
    const fetchMock = vi.fn().mockResolvedValue(response(provider));
    vi.stubGlobal("fetch", fetchMock);
    const { api } = await importApi("https://api.test");

    await expect(api.updateProviderSettings({ provider: "openai-compatible", model: "kimchi/kimi-k2.7", base_url: "http://localhost:20128/v1" })).resolves.toEqual(provider);
    expect(fetchMock).toHaveBeenCalledWith("https://api.test/api/settings/provider", {
      method: "PUT",
      body: JSON.stringify({ provider: "openai-compatible", model: "kimchi/kimi-k2.7", base_url: "http://localhost:20128/v1" }),
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      signal: expect.any(AbortSignal),
    });
  });

  it("uploads files with cookie credentials and throws upload-specific errors", async () => {
    const upload = { name: "a.txt", size: 1, type: "text/plain", path: "/uploads/a.txt" };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(upload))
      .mockResolvedValueOnce(response({ error: true }, { ok: false, status: 400, statusText: "Bad Request" }));
    vi.stubGlobal("fetch", fetchMock);
    const { api } = await importApi("https://api.test");
    const file = new File(["hello"], "a.txt", { type: "text/plain" });

    await expect(api.uploadFile("p1", file)).resolves.toEqual(upload);
    expect(fetchMock).toHaveBeenCalledWith("https://api.test/api/projects/p1/uploads", {
      method: "POST",
      body: expect.any(FormData),
      credentials: "include",
      signal: expect.any(AbortSignal),
    });
    await expect(api.uploadFile("p1", file)).rejects.toThrow("API error: 400 Bad Request");
  });

  it("clears session token when uploads are unauthorized", async () => {
    localStorage.setItem("neutron_session_token", "upload-token");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      response({ detail: "Authentication required." }, { ok: false, status: 401, statusText: "Unauthorized" })
    ));
    const { api } = await importApi("https://api.test");
    const file = new File(["hello"], "a.txt", { type: "text/plain" });

    await expect(api.uploadFile("p1", file)).rejects.toThrow("Authentication required.");
    expect(localStorage.getItem("neutron_session_token")).toBeNull();
  });

  it("handles unauthorized upload without a legacy stored token", async () => {
    localStorage.removeItem("neutron_session_token");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      response({ detail: "Authentication required." }, { ok: false, status: 401, statusText: "Unauthorized" })
    ));
    const { api } = await importApi("https://api.test");
    const file = new File(["hello"], "a.txt", { type: "text/plain" });

    await expect(api.uploadFile("p1", file)).rejects.toThrow("Authentication required.");
    expect(localStorage.getItem("neutron_session_token")).toBeNull();
  });

  it("clears provider API keys", async () => {
    const provider = {
      provider: "openai-compatible",
      model: "kimchi/kimi-k2.7",
      base_url: "http://localhost:20128/v1",
      has_api_key: false,
      effective_model: "openai/kimchi/kimi-k2.7",
    };
    const fetchMock = vi.fn().mockResolvedValue(response(provider));
    vi.stubGlobal("fetch", fetchMock);
    const { api } = await importApi("https://api.test");

    await expect(api.clearProviderKey("openai-compatible")).resolves.toEqual(provider);
    expect(fetchMock).toHaveBeenCalledWith("https://api.test/api/settings/provider/openai-compatible/key", {
      method: "DELETE",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      signal: expect.any(AbortSignal),
    });
  });

  it("updates and clears search provider API keys", async () => {
    const provider = {
      provider: "brave" as const,
      label: "Brave Search",
      description: "Independent web search.",
      docs_url: "https://example.com/brave",
      has_api_key: true,
    };
    const fetchMock = vi.fn().mockResolvedValue(response(provider));
    vi.stubGlobal("fetch", fetchMock);
    const { api } = await importApi("https://api.test");

    await expect(api.updateSearchProviderSettings({ provider: "brave", api_key: "secret" })).resolves.toEqual(provider);
    await expect(api.clearSearchProviderKey("brave")).resolves.toEqual(provider);
    expect(fetchMock).toHaveBeenNthCalledWith(1, "https://api.test/api/settings/search-provider", {
      method: "PUT",
      body: JSON.stringify({ provider: "brave", api_key: "secret" }),
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      signal: expect.any(AbortSignal),
    });
    expect(fetchMock).toHaveBeenNthCalledWith(2, "https://api.test/api/settings/search-provider/brave/key", {
      method: "DELETE",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      signal: expect.any(AbortSignal),
    });
  });

  it("uses cookie credentials and clears legacy tokens on unauthorized responses", async () => {
    localStorage.setItem("neutron_session_token", "stored-token");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({ ok: true }))
      .mockResolvedValueOnce(response({ detail: "Authentication required." }, { ok: false, status: 401, statusText: "Unauthorized" }));
    vi.stubGlobal("fetch", fetchMock);
    const { api } = await importApi("https://api.test");

    await api.me();
    expect(fetchMock).toHaveBeenNthCalledWith(1, "https://api.test/api/auth/me", {
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      signal: expect.any(AbortSignal),
    });

    await expect(api.me()).rejects.toThrow("Authentication required.");
    expect(localStorage.getItem("neutron_session_token")).toBeNull();
  });

  it("calls auth and provider activation endpoints", async () => {
    const user = { id: "u1", email: "user@example.com", display_name: null, created_at: "2026-01-01" };
    const provider = {
      provider: "openai",
      model: "gpt-4o",
      base_url: null,
      has_api_key: true,
      effective_model: "openai/gpt-4o",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(user))
      .mockResolvedValueOnce(response(user))
      .mockResolvedValueOnce(response({ ok: true }))
      .mockResolvedValueOnce(response(provider));
    vi.stubGlobal("fetch", fetchMock);
    const { api } = await importApi("https://api.test");

    await expect(api.register({ email: "user@example.com", password: "password123", display_name: "User" })).resolves.toEqual(user);
    await expect(api.login({ email: "user@example.com", password: "password123" })).resolves.toEqual(user);
    await expect(api.logout()).resolves.toEqual({ ok: true });
    await expect(api.activateProvider("openai")).resolves.toEqual(provider);

    expect(fetchMock).toHaveBeenNthCalledWith(1, "https://api.test/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ email: "user@example.com", password: "password123", display_name: "User" }),
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      signal: expect.any(AbortSignal),
    });
    expect(fetchMock).toHaveBeenNthCalledWith(4, "https://api.test/api/settings/provider/openai/activate", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      signal: expect.any(AbortSignal),
    });
  });

  it("calls xAI OAuth endpoints", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({ session_id: "s1", verification_uri: "https://auth.x.ai/device", user_code: "ABCD", expires_in: 600, interval: 5 }))
      .mockResolvedValueOnce(response({ status: "complete", connected: true }))
      .mockResolvedValueOnce(response({ provider: "xai-oauth", model: "grok-4.5", base_url: "https://api.x.ai/v1", has_api_key: false, effective_model: "xai/grok-4.5" }));
    vi.stubGlobal("fetch", fetchMock);
    const { api } = await importApi("https://api.test");

    await expect(api.startXaiOAuth()).resolves.toMatchObject({ session_id: "s1" });
    await expect(api.pollXaiOAuth("s1")).resolves.toEqual({ status: "complete", connected: true });
    await expect(api.disconnectXaiOAuth()).resolves.toMatchObject({ provider: "xai-oauth" });
  });

  it("builds project download URL", async () => {
    const { getProjectDownloadUrl } = await importApi("https://api.test");
    expect(getProjectDownloadUrl("p1")).toBe("https://api.test/api/projects/p1/download");
  });

  it("downloads project archives with cookie credentials", async () => {
    const blob = new Blob(["zip"], { type: "application/zip" });
    const click = vi.fn();
    const createObjectURL = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:project");
    const revokeObjectURL = vi.spyOn(URL, "revokeObjectURL").mockReturnValue(undefined);
    vi.spyOn(document, "createElement").mockReturnValue({ click, download: "", href: "" } as unknown as HTMLAnchorElement);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      blob: vi.fn().mockResolvedValue(blob),
    }));
    const { downloadProject } = await importApi("https://api.test");

    await downloadProject("p1");

    expect(fetch).toHaveBeenCalledWith("https://api.test/api/projects/p1/download", {
      credentials: "include",
      signal: expect.any(AbortSignal),
    });
    expect(click).toHaveBeenCalled();
    createObjectURL.mockRestore();
    revokeObjectURL.mockRestore();
  });

  it("downloads project archives without bearer auth when no token is stored", async () => {
    const blob = new Blob(["zip"], { type: "application/zip" });
    const click = vi.fn();
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:project");
    vi.spyOn(URL, "revokeObjectURL").mockReturnValue(undefined);
    vi.spyOn(document, "createElement").mockReturnValue({ click, download: "", href: "" } as unknown as HTMLAnchorElement);
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      blob: vi.fn().mockResolvedValue(blob),
    });
    vi.stubGlobal("fetch", fetchMock);
    const { downloadProject } = await importApi("https://api.test");

    await downloadProject("p1");

    expect(fetchMock).toHaveBeenCalledWith("https://api.test/api/projects/p1/download", {
      credentials: "include",
      signal: expect.any(AbortSignal),
    });
  });

  it("handles unauthorized download without a legacy stored token", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      response({ detail: "Authentication required." }, { ok: false, status: 401, statusText: "Unauthorized" })
    ));
    const { downloadProject } = await importApi("https://api.test");
    await expect(downloadProject("p1")).rejects.toThrow("Authentication required.");
    expect(localStorage.getItem("neutron_session_token")).toBeNull();
  });

  it("clears session token when project download is unauthorized", async () => {
    localStorage.setItem("neutron_session_token", "download-token");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      response({ detail: "Authentication required." }, { ok: false, status: 401, statusText: "Unauthorized" })
    ));
    const { downloadProject } = await importApi("https://api.test");
    await expect(downloadProject("p1")).rejects.toThrow("Authentication required.");
    expect(localStorage.getItem("neutron_session_token")).toBeNull();
  });

  it("preserves session state for non-authentication download failures", async () => {
    localStorage.setItem("neutron_session_token", "legacy-token");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      response({ detail: "Archive unavailable." }, { ok: false, status: 500, statusText: "Server Error" })
    ));
    const { downloadProject } = await importApi("https://api.test");
    await expect(downloadProject("p1")).rejects.toThrow("Archive unavailable.");
    expect(localStorage.getItem("neutron_session_token")).toBe("legacy-token");
  });

  it.each([
    ["http://localhost:8000", "ws://localhost:8000/ws/project/p1"],
    ["https://api.test", "wss://api.test/ws/project/p1"],
    ["ftp://api.test", "ftp://api.test/ws/project/p1"],
  ])("builds websocket URL from %s", async (base, url) => {
    const { getWsUrl } = await importApi(base);
    expect(getWsUrl("p1")).toBe(url);
  });

  it("never appends legacy session tokens to websocket URLs", async () => {
    localStorage.setItem("neutron_session_token", "ws-token");
    const { getWsUrl } = await importApi("https://api.test");
    expect(getWsUrl("p1")).toBe("wss://api.test/ws/project/p1");
    localStorage.removeItem("neutron_session_token");
  });

  it("loads project checkpoints", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      response({ checkpoints: [{ id: "cp-1", created_at: "2026-01-01", parent_id: "", branch: "main", location: "db#cp-1" }], latest: "db#cp-1" })
    ));
    const { api } = await importApi("https://api.test");
    await expect(api.getProjectCheckpoints("p1")).resolves.toEqual({
      checkpoints: [{ id: "cp-1", created_at: "2026-01-01", parent_id: "", branch: "main", location: "db#cp-1" }],
      latest: "db#cp-1",
    });
  });
});
