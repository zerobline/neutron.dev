import type { ProjectFile } from "@/types";
import { clearSessionToken } from "./auth-session";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const REQUEST_TIMEOUT_MS = 30_000;

export interface ModelOption {
  value: string;
  label: string;
}

export interface AvailableModels {
  models: ModelOption[];
  current: string;
}

export type ProviderModelSource = "api" | "catalog" | "fallback";

export interface ProviderModelsResponse {
  provider: LlmProvider;
  models: ModelOption[];
  current: string;
  source: ProviderModelSource;
}

export type LlmProvider = "openai" | "anthropic" | "gemini" | "mistral" | "openai-compatible" | "moonshot" | "kimi" | "openrouter" | "groq" | "xai" | "xai-oauth" | "nvidia" | "custom";
export type ProviderAuthMethod = "api_key" | "oauth";
export type SearchProviderName = "brave" | "serper" | "tavily" | "exa";
export type OAuthPollStatus = "pending" | "complete" | "expired" | "denied";

export interface User {
  id: string;
  email: string;
  display_name: string | null;
  created_at: string;
}

export type AuthResponse = User;

export interface ProviderSettings {
  provider: LlmProvider;
  model: string;
  base_url: string | null;
  has_api_key: boolean;
  effective_model: string;
}

export interface ProviderSummary extends ProviderSettings {
  label: string;
  is_active: boolean;
  requires_base_url: boolean;
  requires_api_key: boolean;
  auth_method: ProviderAuthMethod;
  is_connected: boolean;
}

export interface OAuthDeviceStartResponse {
  session_id: string;
  verification_uri: string;
  user_code: string;
  expires_in: number;
  interval: number;
}

export interface OAuthDevicePollResponse {
  status: OAuthPollStatus;
  connected?: boolean;
  interval?: number;
}

export interface ProviderListResponse {
  providers: ProviderSummary[];
  active_provider: LlmProvider;
}

export interface ProviderSettingsUpdate {
  provider: ProviderSettings["provider"];
  model: string;
  api_key?: string | null;
  base_url?: string | null;
  clear_api_key?: boolean;
}

export interface SearchProviderSummary {
  provider: SearchProviderName;
  label: string;
  description: string;
  docs_url: string;
  has_api_key: boolean;
  has_user_api_key: boolean;
}

export interface SearchProviderListResponse {
  providers: SearchProviderSummary[];
}

export interface SearchProviderSettingsUpdate {
  provider: SearchProviderName;
  api_key: string;
}

export type DefaultMcpKey = "github" | "linear";

export interface McpConnectorSummary {
  key: DefaultMcpKey;
  label: string;
  description: string;
  docs_url: string;
  connection_url: string;
  default_url: string;
  has_api_key: boolean;
  has_user_api_key: boolean;
  enabled_by_default: boolean;
}

export interface McpConnectorListResponse {
  connectors: McpConnectorSummary[];
}

export interface McpConnectorSettingsUpdate {
  key: DefaultMcpKey;
  api_key: string;
}

export interface ProjectConnectorSettings {
  default_mcps?: Array<{
    key: DefaultMcpKey;
    enabled: boolean;
  }>;
  custom_mcp_servers: Array<{
    id: string;
    name: string;
    transport: "stdio" | "sse" | "http";
    command_or_url: string;
    notes: string;
  }>;
}

export type SkillAgentTarget =
  | "all"
  | "team_leader"
  | "product_manager"
  | "architect"
  | "engineer"
  | "data_scientist";

export interface SkillCatalogItem {
  name: string;
  description: string;
  source: "builtin" | "custom";
  recommended_agents: string[];
  enabled: boolean;
  agents: SkillAgentTarget[];
  body_preview?: string | null;
}

export interface ProjectSkillsResponse {
  skills: SkillCatalogItem[];
}

export interface SkillAssignment {
  name: string;
  enabled: boolean;
  agents: SkillAgentTarget[];
}

export interface SkillCreate {
  name: string;
  description: string;
  body: string;
  agents?: SkillAgentTarget[];
  enabled?: boolean;
}


async function parseErrorMessage(res: Response): Promise<string> {
  const fallback = `API error: ${res.status} ${res.statusText}`;
  const text = await res.text().catch(() => "");
  if (!text) return fallback;
  try {
    const data = JSON.parse(text) as { detail?: unknown; message?: unknown };
    if (typeof data.detail === "string") return data.detail;
    if (typeof data.message === "string") return data.message;
  } catch {
    return text;
  }
  return fallback;
}

async function withTimeout<T>(operation: (signal: AbortSignal) => Promise<T>): Promise<T> {
  const controller = new AbortController();
  const timeout = globalThis.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    return await operation(controller.signal);
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("Request timed out. Check the server connection and try again.");
    }
    throw error;
  } finally {
    globalThis.clearTimeout(timeout);
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options?.headers as Record<string, string> | undefined),
  };
  const res = await withTimeout((signal) => fetch(`${API_BASE}${path}`, {
    ...options,
    signal,
    credentials: "include",
    headers,
  }));
  if (!res.ok) {
    if (res.status === 401) {
      clearSessionToken();
    }
    throw new Error(await parseErrorMessage(res));
  }
  if (res.status === 204) {
    return undefined as T;
  }
  const text = await res.text();
  if (!text) {
    return undefined as T;
  }
  const contentType = String(res.headers.get("content-type"));
  return (contentType.includes("application/json") ? JSON.parse(text) : text) as T;
}

export const api = {
  register: (data: { email: string; password: string; display_name?: string | null }) =>
    request<AuthResponse>("/api/auth/register", { method: "POST", body: JSON.stringify(data) }),

  login: (data: { email: string; password: string }) =>
    request<AuthResponse>("/api/auth/login", { method: "POST", body: JSON.stringify(data) }),

  logout: () => request<{ ok: boolean }>("/api/auth/logout", { method: "POST" }),

  me: () => request<User>("/api/auth/me"),

  createProject: (data: {
    name: string;
    description: string;
    template?: string;
    stack?: string;
  }) => request("/api/projects", { method: "POST", body: JSON.stringify(data) }),

  listProjects: () => request("/api/projects"),

  getProject: (id: string) => request(`/api/projects/${id}`),

  deleteProject: (id: string) =>
    request(`/api/projects/${id}`, { method: "DELETE" }),

  getProjectFiles: (id: string) => request<ProjectFile[]>(`/api/projects/${id}/files`),

  getProjectRuntime: (id: string) =>
    request<{
      project_id: string;
      status: "idle" | "installing" | "starting" | "ready" | "error" | "stopped";
      port: number | null;
      url: string | null;
      message: string;
      logs: string[];
      updated_at: number;
    }>(`/api/projects/${id}/runtime`),

  startProjectRuntime: (id: string) =>
    request<{
      project_id: string;
      status: "idle" | "installing" | "starting" | "ready" | "error" | "stopped";
      port: number | null;
      url: string | null;
      message: string;
      logs: string[];
      updated_at: number;
    }>(`/api/projects/${id}/runtime/start`, { method: "POST" }),

  stopProjectRuntime: (id: string) =>
    request<{
      project_id: string;
      status: "idle" | "installing" | "starting" | "ready" | "error" | "stopped";
      port: number | null;
      url: string | null;
      message: string;
      logs: string[];
      updated_at: number;
    }>(`/api/projects/${id}/runtime/stop`, { method: "POST" }),

  getProjectMessages: (id: string) => request(`/api/projects/${id}/messages`),

  getProjectConnectors: (id: string) => request<ProjectConnectorSettings>(`/api/projects/${id}/connectors`),

  saveProjectConnectors: (id: string, data: ProjectConnectorSettings | {
    default_mcps?: Array<{ key: DefaultMcpKey; enabled: boolean }>;
    custom_mcp_servers: ProjectConnectorSettings["custom_mcp_servers"];
  }) =>
    request<ProjectConnectorSettings>(`/api/projects/${id}/connectors`, { method: "PUT", body: JSON.stringify(data) }),

  listBuiltinSkills: () => request<SkillCatalogItem[]>("/api/skills"),

  getProjectSkills: (id: string) => request<ProjectSkillsResponse>(`/api/projects/${id}/skills`),

  saveProjectSkills: (id: string, skills: SkillAssignment[]) =>
    request<ProjectSkillsResponse>(`/api/projects/${id}/skills`, {
      method: "PUT",
      body: JSON.stringify({ skills }),
    }),

  createProjectSkill: (id: string, data: SkillCreate) =>
    request<ProjectSkillsResponse>(`/api/projects/${id}/skills`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  deleteProjectSkill: (id: string, name: string) =>
    request<ProjectSkillsResponse>(`/api/projects/${id}/skills/${encodeURIComponent(name)}`, {
      method: "DELETE",
    }),

  listTemplates: () => request("/api/templates"),

  getTemplate: (id: string) => request(`/api/templates/${id}`),

  getAvailableModels: () => request<AvailableModels>("/api/settings/models"),

  getAgentModels: () =>
    request<{
      provider: string;
      default_model: string;
      agents: Array<{ id: string; label: string; model: string; is_override: boolean }>;
    }>("/api/settings/agent-models"),

  updateAgentModels: (models: Record<string, string | null>) =>
    request<{
      provider: string;
      default_model: string;
      agents: Array<{ id: string; label: string; model: string; is_override: boolean }>;
    }>("/api/settings/agent-models", {
      method: "PUT",
      body: JSON.stringify({ models }),
    }),

  listProviderSettings: () => request<ProviderListResponse>("/api/settings/providers"),

  getProviderModels: (provider: LlmProvider) =>
    request<ProviderModelsResponse>(`/api/settings/providers/${provider}/models`),

  getProviderSettings: () => request<ProviderSettings>("/api/settings/provider"),

  updateProviderSettings: (data: ProviderSettingsUpdate) =>
    request<ProviderSettings>("/api/settings/provider", { method: "PUT", body: JSON.stringify(data) }),

  activateProvider: (provider: LlmProvider) =>
    request<ProviderSettings>(`/api/settings/provider/${provider}/activate`, { method: "POST" }),

  clearProviderKey: (provider: LlmProvider) =>
    request<ProviderSettings>(`/api/settings/provider/${provider}/key`, { method: "DELETE" }),

  listSearchProviderSettings: () =>
    request<SearchProviderListResponse>("/api/settings/search-providers"),

  updateSearchProviderSettings: (data: SearchProviderSettingsUpdate) =>
    request<SearchProviderSummary>("/api/settings/search-provider", { method: "PUT", body: JSON.stringify(data) }),

  clearSearchProviderKey: (provider: SearchProviderName) =>
    request<SearchProviderSummary>(`/api/settings/search-provider/${provider}/key`, { method: "DELETE" }),

  listMcpConnectorSettings: () =>
    request<McpConnectorListResponse>("/api/settings/mcp-connectors"),

  updateMcpConnectorSettings: (data: McpConnectorSettingsUpdate) =>
    request<McpConnectorSummary>("/api/settings/mcp-connector", { method: "PUT", body: JSON.stringify(data) }),

  clearMcpConnectorKey: (key: DefaultMcpKey) =>
    request<McpConnectorSummary>(`/api/settings/mcp-connector/${key}/key`, { method: "DELETE" }),

  startXaiOAuth: () => request<OAuthDeviceStartResponse>("/api/oauth/xai/device", { method: "POST" }),

  pollXaiOAuth: (sessionId: string) =>
    request<OAuthDevicePollResponse>("/api/oauth/xai/poll", { method: "POST", body: JSON.stringify({ session_id: sessionId }) }),

  disconnectXaiOAuth: () => request<ProviderSettings>("/api/oauth/xai", { method: "DELETE" }),

  uploadFile: async (projectId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    const res = await withTimeout((signal) => fetch(`${API_BASE}/api/projects/${projectId}/uploads`, {
      method: "POST",
      body: form,
      credentials: "include",
      signal,
    }));
    if (!res.ok) {
      if (res.status === 401) {
        clearSessionToken();
      }
      throw new Error(await parseErrorMessage(res));
    }
    return res.json() as Promise<{ name: string; size: number; type: string; path: string }>;
  },

  listUploads: (projectId: string) =>
    request<{ name: string; size: number; path: string }[]>(`/api/projects/${projectId}/uploads`),

  getProjectCheckpoints: (projectId: string) =>
    request<{
      checkpoints: Array<{
        id: string;
        created_at: string;
        parent_id: string;
        branch: string;
        location: string;
      }>;
      latest: string | null;
    }>(`/api/projects/${projectId}/checkpoints`),
};

export function getProjectDownloadUrl(projectId: string): string {
  return `${API_BASE}/api/projects/${projectId}/download`;
}

export async function downloadProject(projectId: string): Promise<void> {
  const res = await withTimeout((signal) => fetch(getProjectDownloadUrl(projectId), {
    credentials: "include",
    signal,
  }));
  if (!res.ok) {
    if (res.status === 401) {
      clearSessionToken();
    }
    throw new Error(await parseErrorMessage(res));
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${projectId}.zip`;
  link.click();
  URL.revokeObjectURL(url);
}

export function getWsUrl(projectId: string): string {
  const base = API_BASE.replace(/^http/, "ws");
  return `${base}/ws/project/${projectId}`;
}
