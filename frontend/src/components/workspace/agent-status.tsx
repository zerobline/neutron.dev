import { useState } from "react";
import { Sparkles } from "lucide-react";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { ModeToggle } from "./mode-toggle";
import { SkillsPanel } from "./skills-panel";
import { useProjectStore } from "@/stores/project-store";
import { AGENTS } from "@/types";

const statusLabel: Record<string, string> = {
  idle: "Idle",
  working: "Working",
  thinking: "Thinking",
  complete: "Complete",
  error: "Failed",
};

interface AgentStatusBarProps {
  connected?: boolean;
  projectId?: string;
}

export function AgentStatusBar({ connected = true, projectId }: AgentStatusBarProps) {
  const agents = useProjectStore((s) => s.agents);
  const currentPhase = useProjectStore((s) => s.currentPhase);
  const buildMode = useProjectStore((s) => s.buildMode);
  const [skillsOpen, setSkillsOpen] = useState(false);

  const visibleAgents = buildMode === "engineer"
    ? AGENTS.filter((a) => a.id === "engineer")
    : AGENTS;

  return (
    <div className="flex items-center gap-4 px-4 py-3 border-b border-border bg-surface/50 overflow-x-auto">
      <ModeToggle />
      {projectId ? (
        <>
          <button
            type="button"
            onClick={() => setSkillsOpen(true)}
            className="flex items-center gap-1.5 rounded-lg border border-border bg-background px-2.5 py-1.5 text-xs font-medium text-muted hover:text-foreground hover:border-accent/40 transition-colors cursor-pointer flex-shrink-0"
            title="Add domain expertise packs to the team"
          >
            <Sparkles className="h-3.5 w-3.5 text-accent" />
            Skills
          </button>
          <SkillsPanel
            projectId={projectId}
            open={skillsOpen}
            onClose={() => setSkillsOpen(false)}
          />
        </>
      ) : null}
      <Badge variant={connected ? "success" : "warning"} className="flex-shrink-0">
        {connected ? "Live" : "Reconnecting"}
      </Badge>
      {currentPhase && (
        <Badge variant="info" className="flex-shrink-0">
          {currentPhase.charAt(0).toUpperCase() + currentPhase.slice(1)}
        </Badge>
      )}
      <div className="flex items-center gap-4">
        {visibleAgents.map((info) => {
          const status = agents.find((a) => a.agent === info.id);
          const isActive = status?.status === "working" || status?.status === "thinking";
          const showTask = isActive || status?.status === "error";
          return (
            <div key={info.id} className="flex items-center gap-2 flex-shrink-0">
              <Avatar
                name={info.name}
                color={info.color}
                size="sm"
                status={status?.status}
              />
              <div className="hidden sm:block">
                <p className="text-xs font-medium text-foreground">{info.name}</p>
                <p className={status?.status === "error" ? "text-[10px] text-red-400" : "text-[10px] text-muted capitalize"}>
                  {statusLabel[status?.status ?? "idle"]}
                </p>
                {showTask && status?.currentTask && (
                  <p className="text-[10px] text-muted max-w-[120px] truncate">
                    {status.currentTask}
                  </p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
