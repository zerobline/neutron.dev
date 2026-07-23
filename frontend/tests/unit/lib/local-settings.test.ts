import { describe, expect, it, vi } from "vitest";
import {
  CONNECTOR_DEFINITIONS,
  DEFAULT_SETTINGS,
  addCustomMcpServer,
  countEnabledLocalSkills,
  deleteCustomMcpServer,
  deleteLocalCustomSkill,
  getBuildConnectorPayload,
  getBuildSkillPayload,
  getCustomMcpServers,
  getLocalCustomSkills,
  getLocalSettings,
  getLocalSkillAssignments,
  resetLocalSettings,
  saveCustomMcpServers,
  saveLocalSettings,
  saveLocalSkillAssignments,
  updateCustomMcpServer,
  upsertLocalCustomSkill,
  type CustomMcpServer,
} from "@/lib/local-settings";

describe("local-settings", () => {
  it("returns default settings when storage is empty", () => {
    expect(getLocalSettings()).toEqual(DEFAULT_SETTINGS);
  });

  it("saves, reads, and resets local settings", () => {
    saveLocalSettings({
      openaiApiKey: "sk-test",
      anthropicApiKey: "ant-test",
      openAiCompatibleBaseUrl: "http://localhost:11434/v1",
      theme: "light",
    });

    expect(getLocalSettings()).toMatchObject({ theme: "light" });
    expect(resetLocalSettings()).toEqual(DEFAULT_SETTINGS);
    expect(localStorage.getItem("neutron-local-settings")).toBeNull();
  });

  it("falls back safely for invalid settings storage", () => {
    localStorage.setItem("neutron-local-settings", "not-json");
    expect(getLocalSettings()).toEqual(DEFAULT_SETTINGS);
    localStorage.setItem("neutron-local-settings", JSON.stringify("bad"));
    expect(getLocalSettings()).toEqual(DEFAULT_SETTINGS);
  });

  it("defines hosted MCP connector metadata", () => {
    expect(CONNECTOR_DEFINITIONS).toHaveLength(3);
    expect(CONNECTOR_DEFINITIONS[0]).toMatchObject({
      key: "github",
      name: "GitHub",
      providerLabel: "Official GitHub MCP",
      connectionUrl: "https://github.com/settings/tokens",
    });
    expect(CONNECTOR_DEFINITIONS[1].docsUrl).toBe("https://linear.app/docs/mcp");
    expect(CONNECTOR_DEFINITIONS[2]).toMatchObject({
      key: "supabase",
      name: "Supabase",
      providerLabel: "Hosted Supabase MCP",
      docsUrl: "https://supabase.com/docs/guides/getting-started/mcp",
    });
  });

  it("returns an empty custom MCP server list by default", () => {
    expect(getCustomMcpServers()).toEqual([]);
  });

  it("adds, trims, updates, and deletes custom MCP servers", () => {
    vi.mocked(crypto.randomUUID).mockReturnValueOnce("mcp-1").mockReturnValueOnce("mcp-2");
    const added = addCustomMcpServer({
      name: " Filesystem ",
      transport: "stdio",
      commandOrUrl: " npx -y @modelcontextprotocol/server-filesystem . ",
      notes: " Local files ",
    });

    expect(added).toHaveLength(1);
    expect(added[0]).toMatchObject({
      name: "Filesystem",
      transport: "stdio",
      commandOrUrl: "npx -y @modelcontextprotocol/server-filesystem .",
      notes: "Local files",
    });
    expect(added[0].id).toBeTruthy();

    const second = addCustomMcpServer({ name: "Remote", transport: "http", commandOrUrl: "https://example.com/mcp", notes: "" });
    const updated = updateCustomMcpServer(added[0].id, {
      name: "Filesystem MCP",
      transport: "sse",
      commandOrUrl: "https://example.com/sse",
      notes: "Updated",
    });

    expect(updated.find((server) => server.id === added[0].id)).toMatchObject({
      name: "Filesystem MCP",
      transport: "sse",
      commandOrUrl: "https://example.com/sse",
      notes: "Updated",
    });
    expect(updated.find((server) => server.id === second[1].id)).toMatchObject({ name: "Remote" });

    const deleted = deleteCustomMcpServer(added[0].id);
    expect(deleted).toHaveLength(1);
    expect(deleted[0].name).toBe("Remote");
  });

  it("normalizes custom MCP server storage defensively", () => {
    localStorage.setItem("neutron-custom-mcp-servers", "not-json");
    expect(getCustomMcpServers()).toEqual([]);

    localStorage.setItem("neutron-custom-mcp-servers", JSON.stringify({ bad: true }));
    expect(getCustomMcpServers()).toEqual([]);

    const valid: CustomMcpServer = {
      id: "valid",
      name: "Valid",
      transport: "http",
      commandOrUrl: "https://example.com/mcp",
      notes: "",
      createdAt: "2026-01-01T00:00:00.000Z",
      updatedAt: "2026-01-01T00:00:00.000Z",
    };
    localStorage.setItem("neutron-custom-mcp-servers", JSON.stringify([
      valid,
      { name: "Missing id", transport: "http", commandOrUrl: "https://example.com/mcp" },
      { id: "missing-name", transport: "http", commandOrUrl: "https://example.com/mcp" },
      { id: "missing-command", name: "Bad", transport: "http" },
      { id: "bad-transport", name: "Bad", transport: "ftp", commandOrUrl: "ftp://example.com" },
      "bad",
    ]));

    expect(getCustomMcpServers()).toEqual([valid]);
  });

  it("fills missing optional custom MCP server fields", () => {
    localStorage.setItem("neutron-custom-mcp-servers", JSON.stringify([
      { id: "minimal", name: "Minimal", transport: "stdio", commandOrUrl: "node server.js", notes: 123 },
    ]));

    const [server] = getCustomMcpServers();
    expect(server).toMatchObject({ id: "minimal", name: "Minimal", notes: "" });
    expect(server.createdAt).toBeTruthy();
    expect(server.updatedAt).toBeTruthy();
  });

  it("saves normalized custom MCP servers", () => {
    saveCustomMcpServers([
      {
        id: "saved",
        name: " Saved ",
        transport: "stdio",
        commandOrUrl: " node server.js ",
        notes: " note ",
        createdAt: "2026-01-01T00:00:00.000Z",
        updatedAt: "2026-01-01T00:00:00.000Z",
      },
    ]);

    expect(getCustomMcpServers()).toEqual([
      {
        id: "saved",
        name: "Saved",
        transport: "stdio",
        commandOrUrl: "node server.js",
        notes: "note",
        createdAt: "2026-01-01T00:00:00.000Z",
        updatedAt: "2026-01-01T00:00:00.000Z",
      },
    ]);
  });

  it("builds a backend connector payload from saved custom MCP servers", () => {
    saveCustomMcpServers([
      {
        id: "saved",
        name: "Saved",
        transport: "http",
        commandOrUrl: "https://example.com/mcp",
        notes: "note",
        createdAt: "2026-01-01T00:00:00.000Z",
        updatedAt: "2026-01-01T00:00:00.000Z",
      },
    ]);

    expect(getBuildConnectorPayload()).toEqual({
      default_mcps: [
        { key: "github", enabled: true },
        { key: "linear", enabled: true },
      ],
      custom_mcp_servers: [
        {
          id: "saved",
          name: "Saved",
          transport: "http",
          command_or_url: "https://example.com/mcp",
          notes: "note",
        },
      ],
    });
  });

  it("stores skill draft assignments and counts enabled skills", () => {
    expect(getLocalSkillAssignments()).toEqual([]);
    expect(countEnabledLocalSkills()).toBe(0);

    saveLocalSkillAssignments([
      { name: " MVP_Scope_Discipline ", enabled: true, agents: ["team_leader", "team_leader", "all"] },
      { name: "browser-native-spa", enabled: false, agents: [] },
      { name: "", enabled: true, agents: ["all"] } as never,
    ]);

    expect(getLocalSkillAssignments()).toEqual([
      { name: "mvp-scope-discipline", enabled: true, agents: ["all"] },
      { name: "browser-native-spa", enabled: false, agents: ["all"] },
    ]);
    expect(countEnabledLocalSkills()).toBe(1);
  });

  it("manages local custom skills and build payload", () => {
    expect(getLocalCustomSkills()).toEqual([]);
    upsertLocalCustomSkill({
      name: " Brand_Voice ",
      description: " Friendly tone ",
      body: " Use short sentences. ",
      agents: ["product_manager"],
      enabled: true,
    });
    expect(getLocalCustomSkills()[0]).toMatchObject({
      name: "brand-voice",
      description: "Friendly tone",
      body: "Use short sentences.",
      agents: ["product_manager"],
      enabled: true,
    });

    saveLocalSkillAssignments([
      { name: "mvp-scope-discipline", enabled: true, agents: ["all"] },
      { name: "brand-voice", enabled: false, agents: ["engineer"] },
    ]);

    const payload = getBuildSkillPayload();
    expect(payload.find((s) => s.name === "mvp-scope-discipline")).toMatchObject({
      enabled: true,
      agents: ["all"],
    });
    // Assignment list wins over the custom skill's own enabled flag.
    expect(payload.find((s) => s.name === "brand-voice")).toMatchObject({
      enabled: false,
      agents: ["engineer"],
    });

    deleteLocalCustomSkill("brand-voice");
    expect(getLocalCustomSkills()).toEqual([]);
    expect(getBuildSkillPayload().some((s) => s.name === "brand-voice")).toBe(false);
  });

  it("ignores invalid skill storage", () => {
    localStorage.setItem("neutron-skill-assignments", "not-json");
    expect(getLocalSkillAssignments()).toEqual([]);
    localStorage.setItem("neutron-custom-skills", JSON.stringify([{ name: "x" }]));
    expect(getLocalCustomSkills()).toEqual([]);
  });
});
