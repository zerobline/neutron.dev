"use client";

import { useEffect, useState } from "react";
import { ExternalLink, Search, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  api,
  type SearchProviderName,
  type SearchProviderSummary,
} from "@/lib/api";

export function SearchProviderSettingsPanel() {
  const [providers, setProviders] = useState<SearchProviderSummary[]>([]);
  const [keys, setKeys] = useState<Partial<Record<SearchProviderName, string>>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<SearchProviderName | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listSearchProviderSettings()
      .then((result) => setProviders(result.providers))
      .catch(() => setError("Could not load search API settings. Log in and try again."))
      .finally(() => setLoading(false));
  }, []);

  const replaceProvider = (saved: SearchProviderSummary) => {
    setProviders((current) => current.map((provider) => (
      provider.provider === saved.provider ? saved : provider
    )));
  };

  const saveProvider = async (provider: SearchProviderSummary) => {
    const apiKey = keys[provider.provider]?.trim();
    if (!apiKey) {
      setError(`Paste a ${provider.label} API key before saving.`);
      setStatus(null);
      return;
    }

    setSaving(provider.provider);
    setError(null);
    setStatus(null);
    try {
      const saved = await api.updateSearchProviderSettings({ provider: provider.provider, api_key: apiKey });
      replaceProvider(saved);
      setKeys((current) => ({ ...current, [provider.provider]: "" }));
      setStatus(`${provider.label} API key saved securely.`);
    } catch {
      setError(`Could not save the ${provider.label} API key.`);
    } finally {
      setSaving(null);
    }
  };

  const clearProvider = async (provider: SearchProviderSummary) => {
    setSaving(provider.provider);
    setError(null);
    setStatus(null);
    try {
      const saved = await api.clearSearchProviderKey(provider.provider);
      replaceProvider(saved);
      setKeys((current) => ({ ...current, [provider.provider]: "" }));
      setStatus(
        saved.has_api_key
          ? `${provider.label} key removed. The server default is now in use.`
          : `${provider.label} API key removed.`
      );
    } catch {
      setError(`Could not remove the ${provider.label} API key.`);
    } finally {
      setSaving(null);
    }
  };

  return (
    <div className="min-w-0 max-w-3xl space-y-6">
      <div>
        <div className="mb-2 flex items-center gap-2">
          <Search className="h-5 w-5 text-accent" aria-hidden="true" />
          <h1 className="text-xl font-semibold text-foreground">Search APIs</h1>
        </div>
        <p className="max-w-2xl text-sm leading-relaxed text-muted">
          Add search credentials for research tools and future agent workflows. Keys are encrypted on the server and are never returned to this browser.
        </p>
      </div>

      <div className="flex items-start gap-3 rounded-xl border border-accent/20 bg-accent/10 p-4">
        <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-accent" aria-hidden="true" />
        <div className="min-w-0">
          <p className="text-sm font-medium text-foreground">Write-only credentials</p>
          <p className="mt-1 text-xs leading-relaxed text-muted">
            A configured status is returned after saving, but the raw key cannot be read back through the API.
          </p>
        </div>
      </div>

      {loading ? <p className="text-sm text-muted">Loading search providers...</p> : null}

      {!loading ? (
        <div className="space-y-3">
          {providers.map((provider) => {
            const isSaving = saving === provider.provider;
            return (
              <section key={provider.provider} className="min-w-0 overflow-hidden rounded-xl border border-border bg-surface p-5">
                <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h2 className="font-medium text-foreground">{provider.label}</h2>
                      <span className={provider.has_api_key
                        ? "rounded-full bg-emerald-500/10 px-2 py-0.5 text-[11px] font-medium text-emerald-400"
                        : "rounded-full bg-surface-hover px-2 py-0.5 text-[11px] font-medium text-muted"
                      }>
                        {provider.has_api_key ? "Configured" : "Not configured"}
                      </span>
                      {provider.has_api_key ? (
                        <span className="text-[11px] text-muted">
                          {provider.has_user_api_key ? "Your key" : "Server default"}
                        </span>
                      ) : null}
                    </div>
                    <p className="mt-1 max-w-xl break-words text-sm leading-relaxed text-muted">{provider.description}</p>
                    <a
                      href={provider.docs_url}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-accent hover:text-accent-hover focus:outline-none focus:ring-2 focus:ring-accent/50"
                    >
                      Get an API key <ExternalLink className="h-3 w-3" aria-hidden="true" />
                    </a>
                  </div>
                </div>

                <div className="mt-4 grid gap-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
                  <div>
                    <label className="text-sm text-muted" htmlFor={`search-key-${provider.provider}`}>
                      {provider.label} API key
                    </label>
                    <Input
                      id={`search-key-${provider.provider}`}
                      type="password"
                      autoComplete="new-password"
                      spellCheck={false}
                      value={keys[provider.provider] ?? ""}
                      onChange={(event) => {
                        setKeys((current) => ({ ...current, [provider.provider]: event.target.value }));
                        setError(null);
                        setStatus(null);
                      }}
                      placeholder={provider.has_api_key ? "Configured; enter a new key to replace it" : "Paste API key"}
                      disabled={isSaving}
                      className="mt-2 min-w-0"
                    />
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {provider.has_user_api_key ? (
                      <Button variant="ghost" onClick={() => void clearProvider(provider)} disabled={isSaving}>
                        Remove
                      </Button>
                    ) : null}
                    <Button onClick={() => void saveProvider(provider)} disabled={isSaving}>
                      {isSaving ? "Saving..." : provider.has_api_key ? "Replace key" : "Save key"}
                    </Button>
                  </div>
                </div>
              </section>
            );
          })}
        </div>
      ) : null}

      <div aria-live="polite">
        {status ? <p className="rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-400">{status}</p> : null}
        {error ? <p className="rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-sm text-red-400">{error}</p> : null}
      </div>
    </div>
  );
}
