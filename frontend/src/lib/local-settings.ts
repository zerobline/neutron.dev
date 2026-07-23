export type AppTheme = "dark" | "light";

export interface AppSettings {
  openaiApiKey: string;
  anthropicApiKey: string;
  openAiCompatibleBaseUrl: string;
  theme: AppTheme;
}

export type ConnectorKey = "github" | "linear" | "supabase";

export interface ConnectorDefinition {
  key: ConnectorKey;
  name: string;
  description: string;
  providerLabel: string;
  connectionUrl: string;
  docsUrl: string;
}

export type CustomMcpTransport = "stdio" | "sse" | "http";

export interface CustomMcpServer {
  id: string;
  name: string;
  transport: CustomMcpTransport;
  commandOrUrl: string;
  notes: string;
  createdAt: string;
  updatedAt: string;
}

export type CustomMcpServerInput = Pick<CustomMcpServer, "name" | "transport" | "commandOrUrl" | "notes">;

export type DefaultMcpKey = "github" | "linear";

export interface BuildConnectorPayload {
  default_mcps: Array<{
    key: DefaultMcpKey;
    enabled: boolean;
  }>;
  custom_mcp_servers: Array<{
    id: string;
    name: string;
    transport: CustomMcpTransport;
    command_or_url: string;
    notes: string;
  }>;
}

const SETTINGS_KEY = "neutron-local-settings";
const CUSTOM_MCP_SERVERS_KEY = "neutron-custom-mcp-servers";

export const DEFAULT_SETTINGS: AppSettings = {
  openaiApiKey: "",
  anthropicApiKey: "",
  openAiCompatibleBaseUrl: "",
  theme: "dark",
};

export const DEFAULT_MCP_KEYS: DefaultMcpKey[] = ["github", "linear"];

export const CONNECTOR_DEFINITIONS: ConnectorDefinition[] = [
  {
    key: "github",
    name: "GitHub",
    description: "Enabled by default. Save a personal access token so agents can use the official GitHub MCP for repos, issues, and PRs.",
    providerLabel: "Official GitHub MCP",
    connectionUrl: "https://github.com/settings/tokens",
    docsUrl: "https://docs.github.com/en/copilot/how-tos/provide-context/use-mcp/set-up-the-github-mcp-server",
  },
  {
    key: "linear",
    name: "Linear",
    description: "Enabled by default. Save an API key so agents can use the official Linear MCP for issues, projects, and teams.",
    providerLabel: "Official Linear MCP",
    connectionUrl: "https://linear.app/settings/api",
    docsUrl: "https://linear.app/docs/mcp",
  },
  {
    key: "supabase",
    name: "Supabase",
    description: "Optional custom connector for database schema, migrations, SQL context, and project metadata.",
    providerLabel: "Hosted Supabase MCP",
    connectionUrl: "https://supabase.com/dashboard/account/tokens",
    docsUrl: "https://supabase.com/docs/guides/getting-started/mcp",
  },
];

function canUseStorage(): boolean {
  /* v8 ignore next */
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

function readJson<T>(key: string, fallback: T): T {
  /* v8 ignore next */
  if (!canUseStorage()) return fallback;
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return fallback;
    const parsed = JSON.parse(raw) as unknown;
    if (Array.isArray(fallback)) return Array.isArray(parsed) ? parsed as T : fallback;
    return parsed && typeof parsed === "object" ? { ...fallback, ...parsed } as T : fallback;
  } catch {
    return fallback;
  }
}

export function getLocalSettings(): AppSettings {
  return readJson(SETTINGS_KEY, DEFAULT_SETTINGS);
}

export function saveLocalSettings(settings: AppSettings): void {
  /* v8 ignore next */
  if (!canUseStorage()) return;
  localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
}

export function resetLocalSettings(): AppSettings {
  /* v8 ignore next */
  if (canUseStorage()) localStorage.removeItem(SETTINGS_KEY);
  return DEFAULT_SETTINGS;
}

const MCP_TRANSPORTS = new Set<CustomMcpTransport>(["stdio", "sse", "http"]);
let customMcpIdCounter = 0;

function nowIso(): string {
  return new Date().toISOString();
}

function createId(): string {
  customMcpIdCounter += 1;
  /* v8 ignore if -- browser tests provide crypto.randomUUID */
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `${crypto.randomUUID()}-${customMcpIdCounter}`;
  }
  /* v8 ignore next -- non-browser fallback */
  return `mcp-${Date.now().toString(36)}-${customMcpIdCounter}`;
}

function normalizeCustomMcpServer(value: unknown): CustomMcpServer | null {
  if (!value || typeof value !== "object") return null;
  const item = value as Partial<CustomMcpServer>;
  if (typeof item.id !== "string" || !item.id.trim()) return null;
  if (typeof item.name !== "string" || !item.name.trim()) return null;
  if (typeof item.commandOrUrl !== "string" || !item.commandOrUrl.trim()) return null;
  if (!item.transport || !MCP_TRANSPORTS.has(item.transport)) return null;
  return {
    id: item.id.trim(),
    name: item.name.trim(),
    transport: item.transport,
    commandOrUrl: item.commandOrUrl.trim(),
    notes: typeof item.notes === "string" ? item.notes.trim() : "",
    createdAt: typeof item.createdAt === "string" && item.createdAt ? item.createdAt : nowIso(),
    updatedAt: typeof item.updatedAt === "string" && item.updatedAt ? item.updatedAt : nowIso(),
  };
}

function normalizeCustomMcpInput(input: CustomMcpServerInput): CustomMcpServerInput {
  return {
    name: input.name.trim(),
    transport: input.transport,
    commandOrUrl: input.commandOrUrl.trim(),
    notes: input.notes.trim(),
  };
}

export function getCustomMcpServers(): CustomMcpServer[] {
  const raw = readJson<unknown[]>(CUSTOM_MCP_SERVERS_KEY, []);
  return raw.map(normalizeCustomMcpServer).filter((server): server is CustomMcpServer => Boolean(server));
}

export function saveCustomMcpServers(servers: CustomMcpServer[]): void {
  /* v8 ignore next */
  if (!canUseStorage()) return;
  localStorage.setItem(CUSTOM_MCP_SERVERS_KEY, JSON.stringify(servers.map(normalizeCustomMcpServer).filter(Boolean)));
}

export function addCustomMcpServer(input: CustomMcpServerInput): CustomMcpServer[] {
  const clean = normalizeCustomMcpInput(input);
  const timestamp = nowIso();
  const next = [
    ...getCustomMcpServers(),
    {
      id: createId(),
      ...clean,
      createdAt: timestamp,
      updatedAt: timestamp,
    },
  ];
  saveCustomMcpServers(next);
  return next;
}

export function updateCustomMcpServer(id: string, input: CustomMcpServerInput): CustomMcpServer[] {
  const clean = normalizeCustomMcpInput(input);
  const timestamp = nowIso();
  const next = getCustomMcpServers().map((server) =>
    server.id === id ? { ...server, ...clean, updatedAt: timestamp } : server
  );
  saveCustomMcpServers(next);
  return next;
}

export function deleteCustomMcpServer(id: string): CustomMcpServer[] {
  const next = getCustomMcpServers().filter((server) => server.id !== id);
  saveCustomMcpServers(next);
  return next;
}

export function getBuildConnectorPayload(): BuildConnectorPayload {
  return {
    default_mcps: DEFAULT_MCP_KEYS.map((key) => ({ key, enabled: true })),
    custom_mcp_servers: getCustomMcpServers().map((server) => ({
      id: server.id,
      name: server.name,
      transport: server.transport,
      command_or_url: server.commandOrUrl,
      notes: server.notes,
    })),
  };
}

/** Skill drafts chosen on the dashboard before a project exists. */
export type SkillAgentTarget =
  | "all"
  | "team_leader"
  | "product_manager"
  | "architect"
  | "engineer"
  | "data_scientist";

export interface LocalSkillAssignment {
  name: string;
  enabled: boolean;
  agents: SkillAgentTarget[];
}

export interface LocalCustomSkill {
  name: string;
  description: string;
  body: string;
  agents: SkillAgentTarget[];
  enabled: boolean;
}

const SKILL_ASSIGNMENTS_KEY = "neutron-skill-assignments";
const CUSTOM_SKILLS_KEY = "neutron-custom-skills";
const SKILL_AGENT_TARGETS = new Set<SkillAgentTarget>([
  "all",
  "team_leader",
  "product_manager",
  "architect",
  "engineer",
  "data_scientist",
]);

function normalizeSkillName(value: string): string {
  return value.trim().toLowerCase().replace(/_/g, "-");
}

function normalizeAgents(value: unknown): SkillAgentTarget[] {
  if (!Array.isArray(value) || value.length === 0) return ["all"];
  const cleaned: SkillAgentTarget[] = [];
  const seen = new Set<string>();
  for (const item of value) {
    if (typeof item !== "string") continue;
    const key = item.trim().toLowerCase() as SkillAgentTarget;
    if (!SKILL_AGENT_TARGETS.has(key) || seen.has(key)) continue;
    seen.add(key);
    cleaned.push(key);
  }
  if (cleaned.includes("all")) return ["all"];
  return cleaned.length ? cleaned : ["all"];
}

function normalizeSkillAssignment(value: unknown): LocalSkillAssignment | null {
  if (!value || typeof value !== "object") return null;
  const item = value as Partial<LocalSkillAssignment>;
  if (typeof item.name !== "string" || !item.name.trim()) return null;
  return {
    name: normalizeSkillName(item.name),
    enabled: Boolean(item.enabled),
    agents: normalizeAgents(item.agents),
  };
}

function normalizeCustomSkill(value: unknown): LocalCustomSkill | null {
  if (!value || typeof value !== "object") return null;
  const item = value as Partial<LocalCustomSkill>;
  if (typeof item.name !== "string" || !item.name.trim()) return null;
  if (typeof item.description !== "string" || !item.description.trim()) return null;
  if (typeof item.body !== "string" || !item.body.trim()) return null;
  return {
    name: normalizeSkillName(item.name),
    description: item.description.trim(),
    body: item.body.trim(),
    agents: normalizeAgents(item.agents),
    enabled: item.enabled !== false,
  };
}

export function getLocalSkillAssignments(): LocalSkillAssignment[] {
  const raw = readJson<unknown[]>(SKILL_ASSIGNMENTS_KEY, []);
  const byName = new Map<string, LocalSkillAssignment>();
  for (const item of raw.map(normalizeSkillAssignment)) {
    if (!item) continue;
    byName.set(item.name, item);
  }
  return Array.from(byName.values());
}

export function saveLocalSkillAssignments(assignments: LocalSkillAssignment[]): void {
  /* v8 ignore next */
  if (!canUseStorage()) return;
  const cleaned = assignments
    .map(normalizeSkillAssignment)
    .filter((item): item is LocalSkillAssignment => Boolean(item));
  localStorage.setItem(SKILL_ASSIGNMENTS_KEY, JSON.stringify(cleaned));
}

export function getLocalCustomSkills(): LocalCustomSkill[] {
  const raw = readJson<unknown[]>(CUSTOM_SKILLS_KEY, []);
  const byName = new Map<string, LocalCustomSkill>();
  for (const item of raw.map(normalizeCustomSkill)) {
    if (!item) continue;
    byName.set(item.name, item);
  }
  return Array.from(byName.values());
}

export function saveLocalCustomSkills(skills: LocalCustomSkill[]): void {
  /* v8 ignore next */
  if (!canUseStorage()) return;
  const cleaned = skills
    .map(normalizeCustomSkill)
    .filter((item): item is LocalCustomSkill => Boolean(item));
  localStorage.setItem(CUSTOM_SKILLS_KEY, JSON.stringify(cleaned));
}

export function upsertLocalCustomSkill(skill: LocalCustomSkill): LocalCustomSkill[] {
  const clean = normalizeCustomSkill(skill);
  if (!clean) return getLocalCustomSkills();
  const others = getLocalCustomSkills().filter((item) => item.name !== clean.name);
  const next = [...others, clean];
  saveLocalCustomSkills(next);
  // Keep assignment in sync for the draft payload.
  const assignments = getLocalSkillAssignments().filter((item) => item.name !== clean.name);
  assignments.push({ name: clean.name, enabled: clean.enabled, agents: clean.agents });
  saveLocalSkillAssignments(assignments);
  return next;
}

export function deleteLocalCustomSkill(name: string): LocalCustomSkill[] {
  const key = normalizeSkillName(name);
  const next = getLocalCustomSkills().filter((item) => item.name !== key);
  saveLocalCustomSkills(next);
  saveLocalSkillAssignments(getLocalSkillAssignments().filter((item) => item.name !== key));
  return next;
}

/** Payload applied to a new project when the build starts from the dashboard. */
export function getBuildSkillPayload(): LocalSkillAssignment[] {
  const customs = getLocalCustomSkills();
  const byName = new Map<string, LocalSkillAssignment>();
  for (const custom of customs) {
    byName.set(custom.name, {
      name: custom.name,
      enabled: custom.enabled,
      agents: custom.agents,
    });
  }
  for (const assignment of getLocalSkillAssignments()) {
    byName.set(assignment.name, assignment);
  }
  return Array.from(byName.values());
}

export function countEnabledLocalSkills(): number {
  return getBuildSkillPayload().filter((item) => item.enabled).length;
}
