"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Loader2, Plus, Sparkles, Trash2, X } from "lucide-react";
import { Dialog } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  api,
  type SkillAgentTarget,
  type SkillCatalogItem,
} from "@/lib/api";
import {
  deleteLocalCustomSkill,
  getLocalCustomSkills,
  getLocalSkillAssignments,
  saveLocalSkillAssignments,
  upsertLocalCustomSkill,
  type LocalCustomSkill,
} from "@/lib/local-settings";
import { cn } from "@/lib/utils";

const AGENT_OPTIONS: { id: SkillAgentTarget; label: string }[] = [
  { id: "all", label: "All agents" },
  { id: "team_leader", label: "Kai" },
  { id: "data_scientist", label: "Zara" },
  { id: "product_manager", label: "Nina" },
  { id: "architect", label: "Theo" },
  { id: "engineer", label: "Ravi" },
];

interface SkillsPanelProps {
  /** When omitted, edits are saved as a local draft applied on the next build. */
  projectId?: string;
  open: boolean;
  onClose: () => void;
}

function assignmentsFromCatalog(skills: SkillCatalogItem[]) {
  return skills.map((skill) => ({
    name: skill.name,
    enabled: skill.enabled,
    agents: (skill.agents.length ? skill.agents : ["all"]) as SkillAgentTarget[],
  }));
}

function mergeDraftCatalog(
  builtins: SkillCatalogItem[],
  customs: LocalCustomSkill[],
): SkillCatalogItem[] {
  const assignments = new Map(
    getLocalSkillAssignments().map((item) => [item.name, item] as const),
  );
  const catalog: SkillCatalogItem[] = builtins.map((skill) => {
    const assignment = assignments.get(skill.name);
    return {
      ...skill,
      source: "builtin" as const,
      enabled: assignment?.enabled ?? false,
      agents: assignment?.agents ?? (["all"] as SkillAgentTarget[]),
    };
  });
  for (const custom of customs) {
    const assignment = assignments.get(custom.name);
    catalog.push({
      name: custom.name,
      description: custom.description,
      source: "custom",
      recommended_agents: [],
      enabled: assignment?.enabled ?? custom.enabled,
      agents: assignment?.agents ?? custom.agents,
      body_preview: custom.body.slice(0, 240),
    });
  }
  return catalog;
}

export function SkillsPanel({ projectId, open, onClose }: SkillsPanelProps) {
  const draftMode = !projectId;
  const [skills, setSkills] = useState<SkillCatalogItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [createName, setCreateName] = useState("");
  const [createDescription, setCreateDescription] = useState("");
  const [createBody, setCreateBody] = useState("");
  const [createAgents, setCreateAgents] = useState<SkillAgentTarget[]>(["all"]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (projectId) {
        const result = await api.getProjectSkills(projectId);
        setSkills(result.skills);
      } else {
        const builtins = await api.listBuiltinSkills();
        setSkills(mergeDraftCatalog(builtins, getLocalCustomSkills()));
      }
    } catch {
      setError(draftMode ? "Could not load skill catalog." : "Could not load team skills.");
    } finally {
      setLoading(false);
    }
  }, [projectId, draftMode]);

  useEffect(() => {
    if (!open) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- opening starts an async request that owns this panel's loading state
    void load();
  }, [open, load]);

  const enabledCount = useMemo(
    () => skills.filter((skill) => skill.enabled).length,
    [skills],
  );

  const persist = async (next: SkillCatalogItem[]) => {
    setSaving(true);
    setError(null);
    try {
      if (projectId) {
        const result = await api.saveProjectSkills(projectId, assignmentsFromCatalog(next));
        setSkills(result.skills);
      } else {
        saveLocalSkillAssignments(assignmentsFromCatalog(next));
        setSkills(next);
      }
    } catch {
      setError("Could not save skill settings.");
      await load();
    } finally {
      setSaving(false);
    }
  };

  const toggleSkill = (name: string) => {
    const next = skills.map((skill) =>
      skill.name === name ? { ...skill, enabled: !skill.enabled } : skill,
    );
    setSkills(next);
    void persist(next);
  };

  const setSkillAgents = (name: string, agents: SkillAgentTarget[]) => {
    const next = skills.map((skill) =>
      skill.name === name
        ? { ...skill, agents: agents.length ? agents : (["all"] as SkillAgentTarget[]) }
        : skill,
    );
    setSkills(next);
    void persist(next);
  };

  const handleCreate = async () => {
    const name = createName.trim().toLowerCase().replace(/_/g, "-");
    if (!name || !createDescription.trim() || !createBody.trim()) {
      setError("Name, description, and instructions are required.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      if (projectId) {
        const result = await api.createProjectSkill(projectId, {
          name,
          description: createDescription.trim(),
          body: createBody.trim(),
          agents: createAgents,
          enabled: true,
        });
        setSkills(result.skills);
      } else {
        if (skills.some((skill) => skill.name === name && skill.source === "builtin")) {
          throw new Error(`'${name}' is a built-in skill name. Choose a different name.`);
        }
        upsertLocalCustomSkill({
          name,
          description: createDescription.trim(),
          body: createBody.trim(),
          agents: createAgents,
          enabled: true,
        });
        const builtins = await api.listBuiltinSkills();
        setSkills(mergeDraftCatalog(builtins, getLocalCustomSkills()));
      }
      setShowCreate(false);
      setCreateName("");
      setCreateDescription("");
      setCreateBody("");
      setCreateAgents(["all"]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create skill.");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (name: string) => {
    setSaving(true);
    setError(null);
    try {
      if (projectId) {
        const result = await api.deleteProjectSkill(projectId, name);
        setSkills(result.skills);
      } else {
        deleteLocalCustomSkill(name);
        const builtins = await api.listBuiltinSkills();
        setSkills(mergeDraftCatalog(builtins, getLocalCustomSkills()));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete skill.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} className="max-w-2xl bg-background p-0 overflow-hidden">
      <div className="flex items-center justify-between px-6 py-5 border-b border-border">
        <div>
          <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-accent" />
            Team Skills
          </h2>
          <p className="text-xs text-muted mt-1">
            {draftMode
              ? "Choose skills before you start. They attach when the project is created."
              : "Skills inject domain instructions into agent prompts. They are not tools."}
            {enabledCount > 0 ? ` ${enabledCount} enabled.` : ""}
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="text-muted hover:text-foreground cursor-pointer"
          aria-label="Close team skills"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      <div className="max-h-[70vh] overflow-y-auto p-6 space-y-4">
        {loading ? (
          <div className="flex items-center justify-center py-12 text-muted">
            <Loader2 className="h-5 w-5 animate-spin" />
          </div>
        ) : (
          <>
            {skills.map((skill) => (
              <div
                key={skill.name}
                className={cn(
                  "rounded-xl border p-4 transition-colors",
                  skill.enabled ? "border-accent/40 bg-accent/5" : "border-border bg-surface",
                )}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-sm font-semibold text-foreground">{skill.name}</h3>
                      <span className="rounded-full bg-background px-1.5 py-0.5 text-[10px] text-muted border border-border">
                        {skill.source === "builtin" ? "Built-in" : "Custom"}
                      </span>
                    </div>
                    <p className="text-xs text-muted mt-1 leading-relaxed">{skill.description}</p>
                    {skill.recommended_agents?.length > 0 && (
                      <p className="text-[10px] text-muted mt-1">
                        Recommended: {skill.recommended_agents.join(", ")}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    {skill.source === "custom" && (
                      <button
                        type="button"
                        onClick={() => void handleDelete(skill.name)}
                        disabled={saving}
                        className="text-muted hover:text-red-400 cursor-pointer p-1"
                        aria-label={`Delete ${skill.name}`}
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    )}
                    <button
                      type="button"
                      role="switch"
                      aria-checked={skill.enabled}
                      aria-label={`${skill.enabled ? "Disable" : "Enable"} ${skill.name}`}
                      onClick={() => toggleSkill(skill.name)}
                      disabled={saving}
                      className={cn(
                        "relative h-6 w-11 rounded-full transition-colors cursor-pointer",
                        skill.enabled ? "bg-accent" : "bg-border",
                      )}
                    >
                      <span
                        className={cn(
                          "absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white transition-transform",
                          skill.enabled && "translate-x-5",
                        )}
                      />
                    </button>
                  </div>
                </div>
                {skill.enabled && (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {AGENT_OPTIONS.map((option) => {
                      const active =
                        skill.agents.includes(option.id) ||
                        (option.id === "all" && skill.agents.includes("all"));
                      return (
                        <button
                          key={option.id}
                          type="button"
                          disabled={saving}
                          onClick={() => {
                            if (option.id === "all") {
                              setSkillAgents(skill.name, ["all"]);
                              return;
                            }
                            const withoutAll = skill.agents.filter((a) => a !== "all") as SkillAgentTarget[];
                            const has = withoutAll.includes(option.id);
                            const next = has
                              ? withoutAll.filter((a) => a !== option.id)
                              : [...withoutAll, option.id];
                            setSkillAgents(skill.name, next.length ? next : ["all"]);
                          }}
                          className={cn(
                            "rounded-full border px-2 py-0.5 text-[11px] cursor-pointer transition-colors",
                            active
                              ? "border-accent/50 bg-accent/15 text-accent"
                              : "border-border text-muted hover:text-foreground",
                          )}
                        >
                          {option.label}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            ))}

            {showCreate ? (
              <div className="rounded-xl border border-border bg-surface p-4 space-y-3">
                <h3 className="text-sm font-semibold text-foreground">New custom skill</h3>
                <Input
                  value={createName}
                  onChange={(e) => setCreateName(e.target.value)}
                  placeholder="name (e.g. brand-voice)"
                  aria-label="Skill name"
                />
                <Input
                  value={createDescription}
                  onChange={(e) => setCreateDescription(e.target.value)}
                  placeholder="Short description"
                  aria-label="Skill description"
                />
                <Textarea
                  value={createBody}
                  onChange={(e) => setCreateBody(e.target.value)}
                  placeholder="Instructions the agent should follow…"
                  rows={6}
                  aria-label="Skill instructions"
                />
                <div className="flex flex-wrap gap-1.5">
                  {AGENT_OPTIONS.map((option) => {
                    const active = createAgents.includes(option.id);
                    return (
                      <button
                        key={option.id}
                        type="button"
                        onClick={() => {
                          if (option.id === "all") {
                            setCreateAgents(["all"]);
                            return;
                          }
                          const withoutAll = createAgents.filter((a) => a !== "all");
                          const has = withoutAll.includes(option.id);
                          const next = has
                            ? withoutAll.filter((a) => a !== option.id)
                            : [...withoutAll, option.id];
                          setCreateAgents(next.length ? next : ["all"]);
                        }}
                        className={cn(
                          "rounded-full border px-2 py-0.5 text-[11px] cursor-pointer",
                          active
                            ? "border-accent/50 bg-accent/15 text-accent"
                            : "border-border text-muted",
                        )}
                      >
                        {option.label}
                      </button>
                    );
                  })}
                </div>
                <div className="flex gap-2 justify-end">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setShowCreate(false)}
                    disabled={saving}
                  >
                    Cancel
                  </Button>
                  <Button size="sm" onClick={() => void handleCreate()} disabled={saving}>
                    {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : "Create skill"}
                  </Button>
                </div>
              </div>
            ) : (
              <Button
                variant="ghost"
                className="w-full border border-dashed border-border"
                onClick={() => setShowCreate(true)}
              >
                <Plus className="h-4 w-4 mr-1.5" />
                Add custom skill
              </Button>
            )}
          </>
        )}

        {error && (
          <p className="rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-xs text-red-400">
            {error}
          </p>
        )}
      </div>
    </Dialog>
  );
}
