"use client";

import { useEffect, useRef, useState } from "react";
import { X, SlidersHorizontal, Plug, CreditCard, Cloud, User, HelpCircle, Globe, Sun, Moon, Search } from "lucide-react";
import { CustomMcpServersPanel } from "@/components/connectors/custom-mcp-servers-panel";
import { DefaultMcpConnectorsPanel } from "@/components/connectors/default-mcp-connectors-panel";
import { SearchProviderSettingsPanel } from "@/components/settings/search-provider-settings-panel";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  api,
  type LlmProvider,
  type ModelOption,
  type OAuthDeviceStartResponse,
  type ProviderSettings,
  type ProviderSummary,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth-store";
import {
  CONNECTOR_DEFINITIONS,
  getLocalSettings,
  resetLocalSettings,
  saveLocalSettings,
  type AppSettings,
  type AppTheme,
} from "@/lib/local-settings";

const nav = [
  { id: "general", label: "General", icon: SlidersHorizontal },
  { id: "connectors", label: "Connectors", icon: Plug },
  { id: "billing", label: "Beta usage", icon: CreditCard },
  { id: "cloud", label: "Cloud & AI", icon: Cloud },
  { id: "search", label: "Search APIs", icon: Search },
  { id: "account", label: "Account", icon: User },
  { id: "help", label: "Help Center", icon: HelpCircle },
] as const;

const providers: { value: LlmProvider; label: string }[] = [
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic" },
  { value: "mistral", label: "Mistral" },
  { value: "kimi", label: "Kimi" },
  { value: "moonshot", label: "Moonshot" },
  { value: "openrouter", label: "OpenRouter" },
  { value: "groq", label: "Groq" },
  { value: "xai", label: "Grok / xAI (API key)" },
  { value: "xai-oauth", label: "Grok OAuth (SuperGrok)" },
  { value: "nvidia", label: "NVIDIA" },
  { value: "openai-compatible", label: "OpenAI-compatible" },
  { value: "custom", label: "Custom" },
];

const providerPresets: Record<LlmProvider, Pick<ProviderSettings, "model" | "base_url">> = {
  openai: { model: "gpt-4o", base_url: null },
  anthropic: { model: "claude-sonnet-4-20250514", base_url: null },
  mistral: { model: "mistral-large-latest", base_url: "https://api.mistral.ai/v1" },
  "openai-compatible": { model: "", base_url: "" },
  moonshot: { model: "kimi-k2", base_url: "https://api.moonshot.ai/v1" },
  kimi: { model: "kimi-for-coding", base_url: "https://api.kimi.com/coding/v1" },
  openrouter: { model: "openai/gpt-4o-mini", base_url: "https://openrouter.ai/api/v1" },
  groq: { model: "llama-3.3-70b-versatile", base_url: null },
  xai: { model: "grok-3-mini", base_url: null },
  "xai-oauth": { model: "grok-4.5", base_url: "https://api.x.ai/v1" },
  nvidia: { model: "llama-3.3-nemotron-super-49b-v1.5", base_url: null },
  custom: { model: "", base_url: null },
};

type Section = (typeof nav)[number]["id"];

interface SettingsModalProps {
  open: boolean;
  onClose: () => void;
  initialSection?: Section;
}

const defaultProviderSettings: ProviderSettings = {
  provider: "openai",
  model: "gpt-4o",
  base_url: null,
  has_api_key: false,
  effective_model: "openai/gpt-4o",
};

export function SettingsModal({ open, onClose, initialSection = "general" }: SettingsModalProps) {
  if (!open) return null;
  return <SettingsModalInner key={initialSection} onClose={onClose} initialSection={initialSection} />;
}

function SettingsModalInner({ onClose, initialSection }: { onClose: () => void; initialSection: Section }) {
  const user = useAuthStore((s) => s.user);
  const [section, setSection] = useState<Section>(initialSection);
  const [settings, setSettings] = useState<AppSettings>(() => getLocalSettings());
  const [theme, setTheme] = useState<AppTheme>(() => {
    /* v8 ignore next */
    if (typeof document === "undefined") return getLocalSettings().theme;
    return document.documentElement.classList.contains("light") ? "light" : getLocalSettings().theme;
  });
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [providerSettings, setProviderSettings] = useState<ProviderSettings>(defaultProviderSettings);
  const [providerSummaries, setProviderSummaries] = useState<ProviderSummary[]>([]);
  const [providerApiKey, setProviderApiKey] = useState("");
  const [providerLoading, setProviderLoading] = useState(false);
  const [providerSaving, setProviderSaving] = useState(false);
  const [providerStatus, setProviderStatus] = useState<string | null>(null);
  const [providerError, setProviderError] = useState<string | null>(null);
  const [syncedModels, setSyncedModels] = useState<ModelOption[]>([]);
  const [syncedModelsLoading, setSyncedModelsLoading] = useState(false);
  const [syncedModelsError, setSyncedModelsError] = useState<string | null>(null);
  const [oauthSession, setOauthSession] = useState<OAuthDeviceStartResponse | null>(null);
  const [oauthConnecting, setOauthConnecting] = useState(false);
  const oauthPollRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [agentModels, setAgentModels] = useState<
    Array<{ id: string; label: string; model: string; is_override: boolean }>
  >([]);
  const [agentModelsDefault, setAgentModelsDefault] = useState("");
  const [agentModelsSaving, setAgentModelsSaving] = useState(false);
  const [agentModelsStatus, setAgentModelsStatus] = useState<string | null>(null);

  const fetchProviderModels = (provider: LlmProvider, currentModel: string, baseUrl: string | null) => {
    if (provider === "custom") {
      setSyncedModels([]);
      setSyncedModelsError(null);
      setSyncedModelsLoading(false);
      return;
    }

    if (provider === "openai-compatible" && !baseUrl) {
      setSyncedModels([]);
      setSyncedModelsError("Add a base URL to sync models from your local endpoint.");
      setSyncedModelsLoading(false);
      return;
    }

    setSyncedModelsLoading(true);
    setSyncedModelsError(null);
    api.getProviderModels(provider)
      .then((data) => {
        setSyncedModels(data.models);
      })
      .catch(() => {
        setSyncedModels([]);
        setSyncedModelsError("Could not sync models. Enter a model ID manually.");
      })
      .finally(() => setSyncedModelsLoading(false));
  };

  const fetchProviderSettings = () => {
    setProviderLoading(true);
    setProviderError(null);
    Promise.all([api.getProviderSettings(), api.listProviderSettings(), api.getAgentModels().catch(() => null)])
      .then(([active, list, agentModelData]) => {
        setProviderSettings(active);
        setProviderSummaries(list.providers);
        fetchProviderModels(active.provider, active.model, active.base_url);
        if (agentModelData) {
          setAgentModels(agentModelData.agents);
          setAgentModelsDefault(agentModelData.default_model);
        }
      })
      .catch(() => setProviderError("Unable to load provider settings. Please try again later."))
      .finally(() => setProviderLoading(false));
  };

  const handleAgentModelsSave = () => {
    setAgentModelsSaving(true);
    setAgentModelsStatus(null);
    const payload: Record<string, string | null> = {};
    for (const agent of agentModels) {
      const trimmed = agent.model.trim();
      payload[agent.id] =
        !trimmed || trimmed === agentModelsDefault ? null : trimmed;
    }
    api
      .updateAgentModels(payload)
      .then((data) => {
        setAgentModels(data.agents);
        setAgentModelsDefault(data.default_model);
        setAgentModelsStatus("Per-agent models saved.");
      })
      .catch(() => setAgentModelsStatus("Could not save agent models."))
      .finally(() => setAgentModelsSaving(false));
  };

  /* eslint-disable react-hooks/set-state-in-effect -- data-fetching effect; setState in .then() is the intended pattern */
  useEffect(() => {
    if (section === "cloud") fetchProviderSettings();
    return () => {
      if (oauthPollRef.current) clearTimeout(oauthPollRef.current);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  /* eslint-enable react-hooks/set-state-in-effect */

  const isOAuthProvider = providerSettings.provider === "xai-oauth";

  const navigateTo = (id: Section) => {
    setSection(id);
    if (id === "cloud") fetchProviderSettings();
  };

  const setAppTheme = (next: AppTheme) => {
    setTheme(next);
    const nextSettings = { ...settings, theme: next };
    setSettings(nextSettings);
    document.documentElement.classList.toggle("light", next === "light");
    localStorage.setItem("neutron-theme", next);
    saveLocalSettings(nextSettings);
  };

  const updateProviderSetting = (key: keyof Pick<ProviderSettings, "provider" | "model" | "base_url">, value: string) => {
    setProviderStatus(null);
    setProviderError(null);
    setProviderSettings((current) => ({ ...current, [key]: key === "base_url" && !value ? null : value }));
  };

  const updateProvider = (provider: LlmProvider) => {
    setProviderStatus(null);
    setProviderError(null);
    setProviderSettings((current) => {
      const next = provider === "custom"
        ? { ...current, provider }
        : { ...current, provider, ...providerPresets[provider] };
      fetchProviderModels(next.provider, next.model, next.base_url);
      return next;
    });
  };

  const handleSave = () => {
    const next = { ...settings, theme };
    saveLocalSettings(next);
    setSettings(next);
    setStatusMessage("Settings saved locally in this browser.");
  };

  const handleReset = () => {
    const next = resetLocalSettings();
    setSettings(next);
    setTheme(next.theme);
    document.documentElement.classList.toggle("light", next.theme === "light");
    localStorage.setItem("neutron-theme", next.theme);
    setStatusMessage("Settings reset to defaults.");
  };

  const handleProviderSave = async () => {
    setProviderSaving(true);
    setProviderError(null);
    setProviderStatus(null);
    try {
      const saved = await api.updateProviderSettings({
        provider: providerSettings.provider,
        model: providerSettings.model,
        base_url: providerSettings.base_url,
        api_key: providerApiKey || undefined,
      });
      setProviderSettings(saved);
      setProviderApiKey("");
      setProviderStatus("AI provider and model saved and activated for future builds.");
      fetchProviderModels(saved.provider, saved.model, saved.base_url);
      void api.listProviderSettings().then((list) => setProviderSummaries(list.providers));
    } catch {
      setProviderError("Could not save provider settings. Check the provider, model, and base URL.");
    } finally {
      setProviderSaving(false);
    }
  };

  const handleProviderActivate = async (provider: LlmProvider, label: string) => {
    setProviderSaving(true);
    setProviderError(null);
    setProviderStatus(null);
    try {
      const active = await api.activateProvider(provider);
      setProviderSettings(active);
      setProviderStatus(`${label} activated for builds.`);
      void api.listProviderSettings().then((list) => setProviderSummaries(list.providers));
    } catch {
      setProviderError("Could not activate provider. Log in and try again.");
    } finally {
      setProviderSaving(false);
    }
  };

  const pollOAuthSession = async (sessionId: string) => {
    try {
      const result = await api.pollXaiOAuth(sessionId);
      if (result.status === "complete") {
        setOauthSession(null);
        setOauthConnecting(false);
        // Backend activates xai-oauth on token store; refresh lists so the UI
        // shows Grok OAuth as the active build provider immediately.
        try {
          const active = await api.activateProvider("xai-oauth");
          setProviderSettings(active);
          void api.listProviderSettings().then((list) => setProviderSummaries(list.providers));
          setProviderStatus("Grok OAuth connected and activated for builds. SuperGrok or X Premium+ subscription required.");
        } catch {
          fetchProviderSettings();
          setProviderStatus("Grok OAuth connected. SuperGrok or X Premium+ subscription required.");
        }
        return;
      }
      if (result.status === "expired" || result.status === "denied") {
        setOauthSession(null);
        setOauthConnecting(false);
        setProviderError(result.status === "denied" ? "Grok OAuth authorization was denied." : "Grok OAuth session expired. Try again.");
        return;
      }
      const delay = (result.interval ?? 5) * 1000;
      oauthPollRef.current = setTimeout(() => { void pollOAuthSession(sessionId); }, delay);
    } catch {
      setOauthConnecting(false);
      setProviderError("Could not complete Grok OAuth login. Try again.");
    }
  };

  const handleGrokOAuthConnect = async () => {
    setOauthConnecting(true);
    setProviderError(null);
    setProviderStatus(null);
    try {
      const session = await api.startXaiOAuth();
      setOauthSession(session);
      window.open(session.verification_uri, "_blank", "noopener,noreferrer");
      void pollOAuthSession(session.session_id);
    } catch {
      setOauthConnecting(false);
      setProviderError("Could not start Grok OAuth. Log in and try again.");
    }
  };

  const handleGrokOAuthDisconnect = async () => {
    setProviderSaving(true);
    setProviderError(null);
    setProviderStatus(null);
    try {
      const saved = await api.disconnectXaiOAuth();
      setProviderSettings(saved);
      setOauthSession(null);
      setProviderStatus("Grok OAuth disconnected.");
      void api.listProviderSettings().then((list) => setProviderSummaries(list.providers));
    } catch {
      setProviderError("Could not disconnect Grok OAuth.");
    } finally {
      setProviderSaving(false);
    }
  };

  const handleProviderKeyClear = async () => {
    setProviderSaving(true);
    setProviderError(null);
    setProviderStatus(null);
    try {
      const saved = await api.clearProviderKey(providerSettings.provider);
      setProviderSettings(saved);
      setProviderApiKey("");
      setProviderStatus("Provider API key cleared for your account.");
      void api.listProviderSettings().then((list) => setProviderSummaries(list.providers));
    } catch {
      setProviderError("Could not clear provider API key.");
    } finally {
      setProviderSaving(false);
    }
  };

  return (
    <Dialog open onClose={onClose} className="h-[92vh] w-[calc(100vw-1rem)] max-w-6xl overflow-hidden bg-background p-0 sm:h-[78vh]">
      <div className="grid h-full grid-cols-[minmax(0,1fr)] grid-rows-[auto_minmax(0,1fr)] sm:grid-cols-[240px_minmax(0,1fr)] sm:grid-rows-1">
        <aside className="border-b border-border bg-surface/40 p-3 sm:border-b-0 sm:border-r sm:p-5">
          <h2 className="mb-6 hidden font-semibold text-foreground sm:block">Settings</h2>
          <div className="flex gap-1 overflow-x-auto pb-1 sm:block sm:space-y-1 sm:overflow-visible sm:pb-0">
            {nav.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.id}
                  onClick={() => navigateTo(item.id)}
                  className={cn(
                    "flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors cursor-pointer sm:w-full sm:gap-3",
                    section === item.id ? "bg-surface text-foreground" : "text-muted hover:text-foreground hover:bg-surface-hover"
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {item.label}
                  {item.id === "billing" ? (
                    <span className="ml-auto rounded-full bg-surface-hover px-1.5 py-0.5 text-[10px] text-muted">Soon</span>
                  ) : null}
                </button>
              );
            })}
          </div>
        </aside>

        <section className="relative min-w-0 overflow-x-hidden overflow-y-auto p-4 pt-12 sm:p-8">
          <button onClick={onClose} className="absolute right-4 top-4 text-muted hover:text-foreground cursor-pointer sm:right-6 sm:top-6" aria-label="Close settings">
            <X className="h-5 w-5" />
          </button>

          {section === "general" && (
            <div className="max-w-4xl space-y-8">
              <h1 className="text-xl font-semibold text-foreground">General</h1>
              <div className="border-b border-border pb-6">
                <h2 className="font-semibold text-foreground mb-4">AI provider and model</h2>
                <p className="text-sm text-muted">Choose the provider and exact model used by builds in Cloud & AI. Credentials stay encrypted on the server and are never returned to the browser.</p>
                <Button variant="secondary" size="sm" className="mt-3" onClick={() => navigateTo("cloud")}>Configure AI model</Button>
              </div>

              <div className="border-b border-border pb-6">
                <h2 className="font-semibold text-foreground mb-4">Theme</h2>
                <div className="flex gap-2">
                  <button onClick={() => setAppTheme("dark")} className={cn("flex items-center gap-2 rounded-lg border px-3 py-2 text-sm cursor-pointer", theme === "dark" ? "border-accent bg-accent/10 text-accent" : "border-border text-muted") }>
                    <Moon className="h-4 w-4" /> Dark
                  </button>
                  <button onClick={() => setAppTheme("light")} className={cn("flex items-center gap-2 rounded-lg border px-3 py-2 text-sm cursor-pointer", theme === "light" ? "border-accent bg-accent/10 text-accent" : "border-border text-muted") }>
                    <Sun className="h-4 w-4" /> Light
                  </button>
                </div>
              </div>

              <div>
                <h2 className="font-semibold text-foreground mb-4">Permissions</h2>
                <div className="flex items-center justify-between rounded-xl bg-surface p-4">
                  <div className="flex items-center gap-3">
                    <Globe className="h-5 w-5 text-muted" />
                    <div>
                      <p className="text-sm font-medium text-foreground">Public</p>
                      <p className="text-xs text-muted">Project can be accessed via link and discover.</p>
                    </div>
                  </div>
                  <span className="text-sm text-muted">Default</span>
                </div>
              </div>

              {statusMessage ? <p className="rounded-lg border border-accent/20 bg-accent/10 px-3 py-2 text-sm text-accent">{statusMessage}</p> : null}
              <div className="flex justify-end gap-2">
                <Button variant="ghost" onClick={handleReset}>Reset</Button>
                <Button onClick={handleSave}>Save Settings</Button>
              </div>
            </div>
          )}

          {section === "connectors" && (
            <div className="max-w-4xl space-y-8">
              <div>
                <h1 className="text-xl font-semibold text-foreground mb-2">Connectors</h1>
                <p className="text-sm text-muted">
                  GitHub and Linear ship enabled by default. Save credentials here so CrewAI agents receive live MCP tools on builds.
                </p>
              </div>
              <DefaultMcpConnectorsPanel />
              <div>
                <h2 className="mb-3 text-base font-semibold text-foreground">Optional providers</h2>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  {CONNECTOR_DEFINITIONS.filter((connector) => connector.key === "supabase").map((connector) => (
                    <div key={connector.key} className="rounded-xl border border-border bg-surface p-4">
                      <div className="flex items-center justify-between gap-3">
                        <p className="font-medium text-foreground">{connector.name}</p>
                        <span className="rounded-full bg-surface-hover px-2 py-0.5 text-[10px] font-semibold text-muted">Optional</span>
                      </div>
                      <p className="mt-2 text-xs leading-relaxed text-muted">{connector.description}</p>
                      <div className="mt-4 flex gap-2">
                        <a href={connector.connectionUrl} target="_blank" rel="noreferrer" className="inline-flex items-center justify-center rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white shadow-lg shadow-accent/25 transition-all duration-200 hover:bg-accent-hover focus:outline-none focus:ring-2 focus:ring-accent/50">Connect</a>
                        <a href={connector.docsUrl} target="_blank" rel="noreferrer" className="inline-flex items-center justify-center rounded-lg border border-border bg-surface px-3 py-1.5 text-sm font-medium text-foreground transition-all duration-200 hover:bg-surface-hover focus:outline-none focus:ring-2 focus:ring-accent/50">Guide</a>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              <CustomMcpServersPanel compact />
            </div>
          )}

          {section === "cloud" && (
            <div className="max-w-3xl space-y-6">
              <div>
                <h1 className="text-xl font-semibold text-foreground mb-2">Cloud & AI</h1>
                <p className="text-sm text-muted">Set up credentials, choose the exact model used by builds, and save to activate it for your account.</p>
              </div>

              {providerLoading ? <p className="text-sm text-muted">Loading provider settings...</p> : null}

              {providerSummaries.length > 0 && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {providerSummaries.map((provider) => (
                    <button
                      key={provider.provider}
                      type="button"
                      onClick={() => {
                        setProviderSettings(provider);
                        setProviderApiKey("");
                        fetchProviderModels(provider.provider, provider.model, provider.base_url);
                      }}
                      className={cn(
                        "rounded-xl border bg-surface p-4 text-left transition-colors hover:bg-surface-hover",
                        provider.provider === providerSettings.provider ? "border-accent" : "border-border"
                      )}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <p className="font-medium text-foreground">{provider.label}</p>
                        {provider.is_active ? <span className="rounded-full bg-accent/10 px-2 py-0.5 text-[10px] font-semibold text-accent">Active</span> : null}
                      </div>
                      <p className="mt-1 text-xs text-muted font-mono truncate">{provider.effective_model}</p>
                      <p className="mt-2 text-xs text-muted">
                        {provider.auth_method === "oauth"
                          ? `OAuth: ${provider.is_connected ? "connected" : "not connected"}`
                          : `Key: ${provider.has_api_key ? "configured" : "not configured"}`}
                      </p>
                      {!provider.is_active && (
                        <span
                          onClick={(event) => {
                            event.stopPropagation();
                            void handleProviderActivate(provider.provider, provider.label);
                          }}
                          className="mt-3 inline-flex rounded-lg border border-border px-2 py-1 text-xs text-foreground hover:bg-background"
                        >
                          Activate
                        </span>
                      )}
                    </button>
                  ))}
                </div>
              )}

              <div className="grid gap-4 rounded-xl border border-border bg-surface p-5">
                <div>
                  <label className="text-sm text-muted" htmlFor="ai-provider">Provider</label>
                  <select
                    id="ai-provider"
                    value={providerSettings.provider}
                    onChange={(e) => updateProvider(e.target.value as LlmProvider)}
                    className="mt-2 w-full rounded-lg border border-border bg-background px-4 py-2.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-accent/50"
                  >
                    {providers.map((provider) => <option key={provider.value} value={provider.value}>{provider.label}</option>)}
                  </select>
                </div>

                <div>
                  <label className="text-sm text-muted" htmlFor="ai-model">Model</label>
                  {providerSettings.provider !== "custom" && syncedModels.length > 0 ? (
                    <select
                      id="ai-model-picker"
                      aria-label="Choose a synced model"
                      defaultValue=""
                      onChange={(e) => {
                        if (e.target.value) updateProviderSetting("model", e.target.value);
                      }}
                      disabled={syncedModelsLoading || providerSaving}
                      className="mt-2 w-full rounded-lg border border-border bg-background px-4 py-2.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-accent/50"
                    >
                      <option value="">Choose a synced model...</option>
                      {syncedModels.map((model) => (
                        <option key={model.value} value={model.value}>{model.label}</option>
                      ))}
                    </select>
                  ) : null}
                  <Input
                    id="ai-model"
                    value={providerSettings.model}
                    onChange={(e) => updateProviderSetting("model", e.target.value)}
                    placeholder={providerSettings.provider === "custom" ? "provider/model" : providerPresets[providerSettings.provider].model}
                    disabled={syncedModelsLoading || providerSaving}
                    className="mt-2"
                  />
                  {providerSettings.provider !== "custom" && syncedModels.length > 0 ? (
                    <p className="mt-2 text-xs text-muted">Pick a synced model above or enter any model ID manually.</p>
                  ) : null}
                  {syncedModelsLoading ? <p className="mt-2 text-xs text-muted">Syncing models for {providerSettings.provider}...</p> : null}
                  {syncedModelsError ? <p className="mt-2 text-xs text-muted">{syncedModelsError}</p> : null}
                </div>

                <div>
                  <label className="text-sm text-muted" htmlFor="ai-base-url">Base URL</label>
                  <Input id="ai-base-url" value={providerSettings.base_url ?? ""} onChange={(e) => updateProviderSetting("base_url", e.target.value)} placeholder={providerSettings.provider === "custom" ? "https://api.example.com/v1" : providerPresets[providerSettings.provider].base_url ?? "Uses provider default"} />
                </div>

                {isOAuthProvider ? (
                  <div className="rounded-lg border border-border bg-background p-4 space-y-3">
                    <div>
                      <p className="text-sm font-medium text-foreground">Grok OAuth</p>
                      <p className="text-xs text-muted mt-1">
                        Sign in with your SuperGrok or X Premium+ account. No API key required.
                      </p>
                    </div>
                    {oauthSession ? (
                      <div className="rounded-lg border border-accent/20 bg-accent/10 p-3 text-sm text-accent space-y-2">
                        <p>Open the verification page and approve access:</p>
                        <a href={oauthSession.verification_uri} target="_blank" rel="noreferrer" className="font-mono underline break-all">
                          {oauthSession.verification_uri}
                        </a>
                        <p>Code: <span className="font-mono font-semibold">{oauthSession.user_code}</span></p>
                        <p className="text-xs">Waiting for authorization...</p>
                      </div>
                    ) : null}
                    <div className="flex gap-2">
                      <Button onClick={handleGrokOAuthConnect} disabled={oauthConnecting || providerSaving}>
                        {oauthConnecting ? "Connecting..." : providerSettings.has_api_key ? "Reconnect Grok" : "Connect with Grok"}
                      </Button>
                      {providerSettings.has_api_key ? (
                        <Button variant="ghost" onClick={handleGrokOAuthDisconnect} disabled={providerSaving}>
                          Disconnect
                        </Button>
                      ) : null}
                    </div>
                    <p className="text-xs text-muted">
                      Status: {providerSettings.has_api_key ? "connected" : "not connected"}. OAuth tokens are stored encrypted on the server.
                    </p>
                  </div>
                ) : (
                  <div>
                    <label className="text-sm text-muted" htmlFor="ai-api-key">API key</label>
                    <Input id="ai-api-key" type="password" value={providerApiKey} onChange={(e) => setProviderApiKey(e.target.value)} placeholder={providerSettings.has_api_key ? "Configured — leave blank to keep existing key" : "Paste API key"} />
                    <p className="mt-2 text-xs text-muted">Key status: {providerSettings.has_api_key ? "configured" : "not configured"}. Raw keys are never returned by the API.</p>
                  </div>
                )}

                <div className="rounded-lg border border-accent/20 bg-accent/10 p-3 text-xs text-accent space-y-1">
                  <p><strong>Mistral:</strong> provider Mistral, model <span className="font-mono">mistral-large-latest</span>. API key from <span className="font-mono">console.mistral.ai</span>.</p>
                  <p><strong>Kimi:</strong> provider Kimi, model <span className="font-mono">kimi-for-coding</span>. API key from <span className="font-mono">kimi.com/code/console</span>.</p>
                  <p><strong>OpenRouter:</strong> provider OpenRouter, model e.g. <span className="font-mono">openai/gpt-4o-mini</span>. API key from <span className="font-mono">openrouter.ai/keys</span>.</p>
                  <p><strong>Grok OAuth:</strong> provider Grok OAuth, model <span className="font-mono">grok-4.5</span>. Requires SuperGrok or X Premium+ — click Connect with Grok.</p>
                  <p><strong>Grok API key:</strong> provider xAI, model <span className="font-mono">grok-3-mini</span>. API key from <span className="font-mono">console.x.ai</span>.</p>
                  <p><strong>Groq/NVIDIA:</strong> use each provider&apos;s default model or paste any LiteLLM-supported model name.</p>
                  <p><strong>Local:</strong> provider OpenAI-compatible, model <span className="font-mono">kimchi/kimi-k2.7</span>, base URL <span className="font-mono">http://localhost:20128/v1</span>.</p>
                  <p>Effective model: <span className="font-mono">{providerSettings.effective_model}</span>.</p>
                </div>

                {providerStatus ? <p className="rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-400">{providerStatus}</p> : null}
                {providerError ? <p className="rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-sm text-red-400">{providerError}</p> : null}

                <div className="flex justify-end gap-2">
                  {!isOAuthProvider ? (
                    <Button variant="ghost" onClick={handleProviderKeyClear} disabled={providerSaving || !providerSettings.has_api_key}>Clear Key</Button>
                  ) : null}
                  <Button onClick={handleProviderSave} disabled={providerSaving}>{providerSaving ? "Saving..." : "Save and use model"}</Button>
                </div>
              </div>

              <div className="grid gap-4 rounded-xl border border-border bg-surface p-5">
                <div>
                  <h2 className="text-base font-semibold text-foreground">Per-agent models</h2>
                  <p className="mt-1 text-sm text-muted">
                    Optionally give each teammate a different model on your active provider. Leave blank or match the
                    default to use <span className="font-mono">{agentModelsDefault || providerSettings.model}</span>.
                  </p>
                </div>
                <div className="space-y-3">
                  {agentModels.map((agent) => (
                    <div key={agent.id} className="grid gap-1.5 sm:grid-cols-[1fr_1fr] sm:items-center">
                      <label className="text-sm text-foreground" htmlFor={`agent-model-${agent.id}`}>
                        {agent.label}
                        {agent.is_override ? (
                          <span className="ml-2 text-[10px] font-medium uppercase text-accent">override</span>
                        ) : null}
                      </label>
                      <Input
                        id={`agent-model-${agent.id}`}
                        value={agent.model}
                        onChange={(e) =>
                          setAgentModels((prev) =>
                            prev.map((item) =>
                              item.id === agent.id ? { ...item, model: e.target.value } : item,
                            ),
                          )
                        }
                        placeholder={agentModelsDefault || providerSettings.model}
                        className="font-mono text-xs"
                      />
                    </div>
                  ))}
                  {agentModels.length === 0 ? (
                    <p className="text-sm text-muted">Load Cloud & AI settings to configure per-agent models.</p>
                  ) : null}
                </div>
                {agentModelsStatus ? (
                  <p className="rounded-lg border border-accent/20 bg-accent/10 px-3 py-2 text-sm text-accent">
                    {agentModelsStatus}
                  </p>
                ) : null}
                <div className="flex justify-end">
                  <Button
                    onClick={handleAgentModelsSave}
                    disabled={agentModelsSaving || agentModels.length === 0}
                  >
                    {agentModelsSaving ? "Saving..." : "Save agent models"}
                  </Button>
                </div>
              </div>
            </div>
          )}

          {section === "account" && (
            <div className="max-w-2xl">
              <h1 className="text-xl font-semibold text-foreground mb-4">Account</h1>
              <div className="rounded-xl bg-surface p-4 flex items-center gap-3">
                <div className="h-10 w-10 rounded-full bg-accent text-white flex items-center justify-center font-semibold">{user?.email?.charAt(0).toUpperCase() ?? "N"}</div>
                <div>
                  <p className="font-medium text-foreground">{user?.display_name ?? user?.email ?? "Not logged in"}</p>
                  <p className="text-sm text-muted">{user ? "API keys and projects are saved to this account." : "Log in to save projects and provider keys."}</p>
                </div>
              </div>
              {!user && <Button className="mt-4" onClick={() => { window.location.href = "/login"; }}>Log in</Button>}
            </div>
          )}

          {section === "search" && <SearchProviderSettingsPanel />}

          {section === "help" && (
            <div className="max-w-4xl space-y-6">
              <div>
                <h1 className="text-xl font-semibold text-foreground mb-2">Help Center</h1>
                <p className="text-sm text-muted">Quick guidance for building projects, connecting tools, and fixing common setup issues.</p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {[
                  ["Getting started", "Create a project, choose Team or Engineer mode, then start a build from the workspace chat."],
                  ["Connectors", "Use hosted GitHub, Linear, and Supabase MCP connections, or save custom MCP server configs locally for future builds."],
                  ["Cloud & AI", "Choose the backend CrewAI provider, confirm the model, and make sure the base URL matches the selected provider."],
                  ["Uploads and artifacts", "Attach files as prompt context and review generated artifacts from the workspace preview and code tabs."],
                  ["Troubleshooting", "If builds stall, check that the backend is running, the provider key is configured, and the WebSocket is connected."],
                ].map(([title, body]) => (
                  <div key={title} className="rounded-xl border border-border bg-surface p-4">
                    <h2 className="font-semibold text-foreground">{title}</h2>
                    <p className="mt-2 text-sm text-muted leading-relaxed">{body}</p>
                  </div>
                ))}
              </div>

              <div className="rounded-xl border border-accent/20 bg-accent/10 p-4">
                <h2 className="font-semibold text-foreground">A note for beta testing</h2>
                <p className="mt-2 text-sm text-muted">Generated code needs review before it is used in a real product. Keep secrets out of prompts and test the downloaded project in your own environment.</p>
              </div>
            </div>
          )}

          {section === "billing" && (
            <div>
              <h1 className="text-xl font-semibold text-foreground mb-3">Beta usage</h1>
              <p className="text-sm text-muted">Neutron does not sell credits during the public beta. Builds use the model provider you connect in Cloud & AI, so provider usage and billing stay with that account.</p>
            </div>
          )}
        </section>
      </div>
    </Dialog>
  );
}
