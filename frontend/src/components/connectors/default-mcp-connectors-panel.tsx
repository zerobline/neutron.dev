"use client";

import { useEffect, useState } from "react";
import { ExternalLink, Plug, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  api,
  type DefaultMcpKey,
  type McpConnectorSummary,
} from "@/lib/api";
import { cn } from "@/lib/utils";

interface DefaultMcpConnectorsPanelProps {
  compact?: boolean;
}

export function DefaultMcpConnectorsPanel({ compact = false }: DefaultMcpConnectorsPanelProps) {
  const [connectors, setConnectors] = useState<McpConnectorSummary[]>([]);
  const [keys, setKeys] = useState<Partial<Record<DefaultMcpKey, string>>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<DefaultMcpKey | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listMcpConnectorSettings()
      .then((result) => setConnectors(result.connectors))
      .catch(() => setError("Could not load MCP connectors. Log in and try again."))
      .finally(() => setLoading(false));
  }, []);

  const replaceConnector = (saved: McpConnectorSummary) => {
    setConnectors((current) => current.map((connector) => (
      connector.key === saved.key ? saved : connector
    )));
  };

  const saveConnector = async (connector: McpConnectorSummary) => {
    const apiKey = keys[connector.key]?.trim();
    if (!apiKey) {
      setError(`Paste a ${connector.label} token before saving.`);
      setStatus(null);
      return;
    }

    setSaving(connector.key);
    setError(null);
    setStatus(null);
    try {
      const saved = await api.updateMcpConnectorSettings({ key: connector.key, api_key: apiKey });
      replaceConnector(saved);
      setKeys((current) => ({ ...current, [connector.key]: "" }));
      setStatus(`${connector.label} credential saved. Agents will use it on the next build.`);
    } catch {
      setError(`Could not save the ${connector.label} credential.`);
    } finally {
      setSaving(null);
    }
  };

  const clearConnector = async (connector: McpConnectorSummary) => {
    setSaving(connector.key);
    setError(null);
    setStatus(null);
    try {
      const saved = await api.clearMcpConnectorKey(connector.key);
      replaceConnector(saved);
      setKeys((current) => ({ ...current, [connector.key]: "" }));
      setStatus(
        saved.has_api_key
          ? `${connector.label} key removed. A server default is still available.`
          : `${connector.label} credential removed.`
      );
    } catch {
      setError(`Could not remove the ${connector.label} credential.`);
    } finally {
      setSaving(null);
    }
  };

  return (
    <div className={cn("space-y-4", compact ? "mt-2" : "mt-0")}>
      <div>
        <div className="mb-2 flex items-center gap-2">
          <Plug className="h-5 w-5 text-accent" aria-hidden="true" />
          <h2 className="text-base font-semibold text-foreground">Default MCP connectors</h2>
        </div>
        <p className="max-w-2xl text-sm leading-relaxed text-muted">
          GitHub and Linear are included by default on every build. Save tokens here so agents get live CrewAI MCP tools. Keys are encrypted on the server and never returned to this browser.
        </p>
      </div>

      <div className="flex items-start gap-3 rounded-xl border border-accent/20 bg-accent/10 p-4">
        <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-accent" aria-hidden="true" />
        <div className="min-w-0">
          <p className="text-sm font-medium text-foreground">Write-only credentials</p>
          <p className="mt-1 text-xs leading-relaxed text-muted">
            Production users configure connectors only in this UI. Raw tokens cannot be read back through the API.
          </p>
        </div>
      </div>

      {loading ? <p className="text-sm text-muted">Loading default MCP connectors...</p> : null}
      {status ? <p className="rounded-lg border border-accent/20 bg-accent/10 px-3 py-2 text-xs text-accent">{status}</p> : null}
      {error ? <p className="rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-xs text-red-400">{error}</p> : null}

      <div className="space-y-3">
        {connectors.map((connector) => (
          <div key={connector.key} className="rounded-xl border border-border bg-surface p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-sm font-semibold text-foreground">{connector.label}</h3>
                  <span className="rounded-full bg-accent/10 px-2 py-0.5 text-[10px] font-semibold text-accent">
                    Default MCP
                  </span>
                  <span className={cn(
                    "rounded-full px-2 py-0.5 text-[10px] font-semibold",
                    connector.has_user_api_key
                      ? "bg-emerald-500/10 text-emerald-400"
                      : connector.has_api_key
                        ? "bg-amber-500/10 text-amber-400"
                        : "bg-surface-hover text-muted"
                  )}>
                    {connector.has_user_api_key
                      ? "Connected"
                      : connector.has_api_key
                        ? "Server default"
                        : "Not connected"}
                  </span>
                </div>
                <p className="mt-2 text-xs leading-relaxed text-muted">{connector.description}</p>
                <p className="mt-2 text-[11px] text-muted">Endpoint: {connector.default_url}</p>
              </div>
              <div className="flex gap-2">
                <a
                  href={connector.connection_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 rounded-lg border border-border bg-background px-2.5 py-1.5 text-xs font-medium text-foreground hover:bg-surface-hover"
                >
                  Get token <ExternalLink className="h-3 w-3" />
                </a>
                <a
                  href={connector.docs_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 rounded-lg border border-border bg-background px-2.5 py-1.5 text-xs font-medium text-foreground hover:bg-surface-hover"
                >
                  Guide <ExternalLink className="h-3 w-3" />
                </a>
              </div>
            </div>

            <div className="mt-4 flex flex-col gap-2 sm:flex-row">
              <Input
                type="password"
                autoComplete="off"
                value={keys[connector.key] ?? ""}
                onChange={(event) => setKeys((current) => ({ ...current, [connector.key]: event.target.value }))}
                placeholder={connector.key === "github" ? "ghp_... personal access token" : "lin_api_... API key"}
                className="bg-background"
              />
              <div className="flex gap-2">
                <Button
                  size="sm"
                  disabled={saving === connector.key}
                  onClick={() => { void saveConnector(connector); }}
                >
                  {saving === connector.key ? "Saving..." : "Save"}
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={saving === connector.key || !connector.has_user_api_key}
                  onClick={() => { void clearConnector(connector); }}
                >
                  Remove
                </Button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
