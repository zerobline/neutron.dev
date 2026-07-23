"use client";

import { Search, X, GitBranch, LineChart, ExternalLink, Database } from "lucide-react";
import { CustomMcpServersPanel } from "@/components/connectors/custom-mcp-servers-panel";
import { DefaultMcpConnectorsPanel } from "@/components/connectors/default-mcp-connectors-panel";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { CONNECTOR_DEFINITIONS, type ConnectorKey } from "@/lib/local-settings";
import { useMemo, useState } from "react";

const connectorIcons: Record<ConnectorKey, typeof GitBranch> = {
  github: GitBranch,
  linear: LineChart,
  supabase: Database,
};

interface ConnectorsModalProps {
  open: boolean;
  onClose: () => void;
}

export function ConnectorsModal({ open, onClose }: ConnectorsModalProps) {
  const [query, setQuery] = useState("");
  const [selectedKey, setSelectedKey] = useState<ConnectorKey>("github");
  const selected = CONNECTOR_DEFINITIONS.find((connector) => connector.key === selectedKey)!;
  const filtered = useMemo(
    () => CONNECTOR_DEFINITIONS.filter((c) => c.name.toLowerCase().includes(query.toLowerCase())),
    [query]
  );

  const chooseConnector = (key: ConnectorKey) => {
    setSelectedKey(key);
  };

  return (
    <Dialog open={open} onClose={onClose} className="max-w-5xl bg-background p-0 overflow-hidden">
      <div className="flex items-center justify-between px-6 py-5 border-b border-border">
        <div>
          <h2 className="text-lg font-semibold text-foreground">Connectors</h2>
          <p className="text-xs text-muted mt-1">GitHub and Linear are default MCPs. Save tokens here for live agent tools.</p>
        </div>
        <button onClick={onClose} className="text-muted hover:text-foreground cursor-pointer" aria-label="Close connectors">
          <X className="h-5 w-5" />
        </button>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-0">
        <div className="max-h-[70vh] overflow-y-auto p-6">
          <DefaultMcpConnectorsPanel />
          <div className="relative mb-6 mt-8">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted" />
            <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search optional connectors" className="pl-9 rounded-full bg-surface" />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pr-1">
            {filtered.map((connector) => {
              const Icon = connectorIcons[connector.key];
              const active = selected.key === connector.key;
              const isDefault = connector.key === "github" || connector.key === "linear";
              return (
                <button
                  key={connector.key}
                  type="button"
                  onClick={() => chooseConnector(connector.key)}
                  className={cn(
                    "flex items-center gap-4 rounded-xl border bg-surface p-4 text-left hover:border-accent/40 hover:bg-surface-hover transition-colors cursor-pointer",
                    active ? "border-accent/60" : "border-border"
                  )}
                >
                  <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-background border border-border text-accent">
                    <Icon className="h-5 w-5" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-semibold text-foreground">{connector.name}</h3>
                      <span className="rounded-full bg-accent/10 px-1.5 py-0.5 text-[10px] text-accent">
                        {isDefault ? "Default MCP" : "Optional"}
                      </span>
                    </div>
                    <p className="text-xs text-muted mt-1 leading-relaxed">{connector.description}</p>
                  </div>
                </button>
              );
            })}
          </div>
          <p className="mt-5 flex items-center gap-2 text-xs text-muted">
            <ExternalLink className="h-3.5 w-3.5" />
            Token pages open in a new tab. Credentials are saved only through the form above.
          </p>
          <CustomMcpServersPanel query={query} />
        </div>

        <aside className="border-t border-border bg-surface/40 p-6 lg:border-l lg:border-t-0">
          <h3 className="font-semibold text-foreground">{selected.name}</h3>
          <p className="text-xs text-muted mt-1">{selected.description}</p>
          <div className="mt-5 rounded-lg border border-border bg-background p-3">
            <p className="text-xs font-medium text-muted">Provider</p>
            <p className="mt-1 text-sm text-foreground">{selected.providerLabel}</p>
          </div>
          <div className="mt-5 flex flex-col gap-2">
            <a href={selected.connectionUrl} target="_blank" rel="noreferrer" className="inline-flex items-center justify-center rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white shadow-lg shadow-accent/25 transition-all duration-200 hover:bg-accent-hover focus:outline-none focus:ring-2 focus:ring-accent/50">
              Get {selected.name} token
            </a>
            <a href={selected.docsUrl} target="_blank" rel="noreferrer" className="inline-flex items-center justify-center rounded-lg border border-border bg-surface px-4 py-2 text-sm font-medium text-foreground transition-all duration-200 hover:bg-surface-hover focus:outline-none focus:ring-2 focus:ring-accent/50">
              View setup guide
            </a>
          </div>
        </aside>
      </div>
    </Dialog>
  );
}
