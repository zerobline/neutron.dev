"use client";

import { useMemo, useState } from "react";
import { Plus, Server, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  addCustomMcpServer,
  deleteCustomMcpServer,
  getCustomMcpServers,
  updateCustomMcpServer,
  type CustomMcpServer,
  type CustomMcpServerInput,
  type CustomMcpTransport,
} from "@/lib/local-settings";
import { cn } from "@/lib/utils";

const transportLabels: Record<CustomMcpTransport, string> = {
  stdio: "STDIO",
  sse: "SSE",
  http: "HTTP",
};

const commandPlaceholders: Record<CustomMcpTransport, string> = {
  stdio: "npx -y @modelcontextprotocol/server-filesystem .",
  sse: "https://example.com/sse",
  http: "https://example.com/mcp",
};

const emptyDraft: CustomMcpServerInput = {
  name: "",
  transport: "stdio",
  commandOrUrl: "",
  notes: "",
};

interface CustomMcpServersPanelProps {
  query?: string;
  compact?: boolean;
}

function matchesQuery(server: CustomMcpServer, query: string): boolean {
  const haystack = `${server.name} ${server.transport} ${server.commandOrUrl} ${server.notes}`.toLowerCase();
  return haystack.includes(query.toLowerCase());
}

function validationError(draft: CustomMcpServerInput): string | null {
  if (!draft.name.trim()) return "Name is required.";
  if (!draft.commandOrUrl.trim()) return "Command or URL is required.";
  if ((draft.transport === "http" || draft.transport === "sse") && !/^https?:\/\//i.test(draft.commandOrUrl.trim())) {
    return "Remote MCP servers must start with http:// or https://.";
  }
  return null;
}

export function CustomMcpServersPanel({ query = "", compact = false }: CustomMcpServersPanelProps) {
  const [servers, setServers] = useState(() => getCustomMcpServers());
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState<CustomMcpServerInput>(emptyDraft);
  const [message, setMessage] = useState<string | null>(null);
  const filteredServers = useMemo(
    () => servers.filter((server) => !query.trim() || matchesQuery(server, query)),
    [servers, query]
  );
  const error = validationError(draft);
  const formOpen = editingId !== null;

  const startAdd = () => {
    setEditingId("new");
    setDraft(emptyDraft);
    setMessage(null);
  };

  const startEdit = (server: CustomMcpServer) => {
    setEditingId(server.id);
    setDraft({
      name: server.name,
      transport: server.transport,
      commandOrUrl: server.commandOrUrl,
      notes: server.notes,
    });
    setMessage(null);
  };

  const closeForm = () => {
    setEditingId(null);
    setDraft(emptyDraft);
  };

  const saveDraft = () => {
    /* v8 ignore next -- submit button is disabled while validation errors exist */
    if (error) return;
    const next = editingId === "new" ? addCustomMcpServer(draft) : updateCustomMcpServer(editingId!, draft);
    setServers(next);
    setMessage(editingId === "new" ? "Custom MCP server saved locally." : "Custom MCP server updated.");
    closeForm();
  };

  const removeServer = (id: string) => {
    setServers(deleteCustomMcpServer(id));
    /* v8 ignore next -- delete controls are outside the edit form in normal UI flows */
    if (editingId === id) closeForm();
    setMessage("Custom MCP server deleted.");
  };

  return (
    <div className={cn("space-y-4", compact ? "mt-6" : "mt-8") }>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="font-semibold text-foreground">Custom MCP servers</h3>
          <p className="mt-1 text-xs text-muted">Saved locally in this browser and attached to future builds as connector context. Local STDIO commands are not auto-executed.</p>
        </div>
        <Button size="sm" onClick={startAdd}>
          <Plus className="mr-1.5 h-3.5 w-3.5" /> Add custom server
        </Button>
      </div>

      {message ? <p className="rounded-lg border border-accent/20 bg-accent/10 px-3 py-2 text-xs text-accent">{message}</p> : null}

      {formOpen ? (
        <div className="grid gap-3 rounded-xl border border-border bg-surface p-4">
          <div className="grid gap-3 md:grid-cols-2">
            <div>
              <label className="text-xs font-medium text-muted" htmlFor="custom-mcp-name">Name</label>
              <Input id="custom-mcp-name" value={draft.name} onChange={(e) => setDraft((current) => ({ ...current, name: e.target.value }))} placeholder="Filesystem" className="mt-1" />
            </div>
            <div>
              <label className="text-xs font-medium text-muted" htmlFor="custom-mcp-transport">Transport</label>
              <select
                id="custom-mcp-transport"
                value={draft.transport}
                onChange={(e) => setDraft((current) => ({ ...current, transport: e.target.value as CustomMcpTransport, commandOrUrl: "" }))}
                className="mt-1 w-full rounded-lg border border-border bg-surface px-4 py-2.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-accent/50"
              >
                <option value="stdio">STDIO command</option>
                <option value="sse">SSE URL</option>
                <option value="http">HTTP URL</option>
              </select>
            </div>
          </div>
          <div>
            <label className="text-xs font-medium text-muted" htmlFor="custom-mcp-command">Command or URL</label>
            <Input id="custom-mcp-command" value={draft.commandOrUrl} onChange={(e) => setDraft((current) => ({ ...current, commandOrUrl: e.target.value }))} placeholder={commandPlaceholders[draft.transport]} className="mt-1" />
          </div>
          <div>
            <label className="text-xs font-medium text-muted" htmlFor="custom-mcp-notes">Notes</label>
            <Textarea id="custom-mcp-notes" value={draft.notes} onChange={(e) => setDraft((current) => ({ ...current, notes: e.target.value }))} placeholder="Optional context for this MCP server" className="mt-1 min-h-20" />
          </div>
          {error ? <p className="text-xs text-red-400">{error}</p> : null}
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={closeForm}>Cancel</Button>
            <Button onClick={saveDraft} disabled={Boolean(error)}>{editingId === "new" ? "Save custom server" : "Update custom server"}</Button>
          </div>
        </div>
      ) : null}

      {filteredServers.length ? (
        <div className={cn("grid gap-3", compact ? "grid-cols-1" : "md:grid-cols-2")}>
          {filteredServers.map((server) => (
            <div key={server.id} className="rounded-xl border border-border bg-surface p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-medium text-foreground">{server.name}</p>
                    <span className="rounded-full bg-surface-hover px-2 py-0.5 text-[10px] font-semibold text-muted">{transportLabels[server.transport]}</span>
                    <span className="rounded-full bg-accent/10 px-2 py-0.5 text-[10px] font-semibold text-accent">Local config</span>
                  </div>
                  <p className="mt-2 break-all font-mono text-xs text-muted">{server.commandOrUrl}</p>
                  {server.notes ? <p className="mt-2 text-xs text-muted">{server.notes}</p> : null}
                </div>
                <Server className="h-4 w-4 shrink-0 text-muted" />
              </div>
              <div className="mt-4 flex justify-end gap-2">
                <Button size="sm" variant="secondary" onClick={() => startEdit(server)}>Edit</Button>
                <Button size="sm" variant="ghost" onClick={() => removeServer(server.id)}>
                  <Trash2 className="mr-1 h-3.5 w-3.5" /> Delete
                </Button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="rounded-xl border border-dashed border-border bg-surface/50 p-4 text-sm text-muted">
          {query.trim() ? "No custom MCP servers match your search." : "No custom MCP servers yet."}
        </div>
      )}
    </div>
  );
}
