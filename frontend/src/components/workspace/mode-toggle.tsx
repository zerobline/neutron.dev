"use client";

import { Target, Users, User } from "lucide-react";
import { useProjectStore } from "@/stores/project-store";
import type { BuildMode } from "@/types";

const modes: { id: BuildMode; label: string; icon: typeof Users; description: string }[] = [
  {
    id: "team",
    label: "Team",
    icon: Users,
    description: "All 5 agents collaborate",
  },
  {
    id: "engineer",
    label: "Engineer",
    icon: User,
    description: "Ravi builds directly",
  },
  {
    id: "goal",
    label: "Goal",
    icon: Target,
    description: "Plan and build autonomously",
  },
];

export function ModeToggle() {
  const buildMode = useProjectStore((s) => s.buildMode);
  const setBuildMode = useProjectStore((s) => s.setBuildMode);
  const projectStatus = useProjectStore((s) => s.projectStatus);

  const locked = projectStatus !== "created";

  return (
    <div className="flex items-center gap-1 rounded-lg bg-surface p-1">
      {modes.map((m) => {
        const Icon = m.icon;
        const active = buildMode === m.id;
        return (
          <button
            key={m.id}
            onClick={() => !locked && setBuildMode(m.id)}
            disabled={locked}
            title={m.description}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors cursor-pointer ${
              active
                ? "bg-accent text-white"
                : "text-muted hover:text-foreground"
            } ${locked ? "opacity-50 cursor-not-allowed" : ""}`}
          >
            <Icon className="h-3.5 w-3.5" />
            {m.label}
          </button>
        );
      })}
    </div>
  );
}
