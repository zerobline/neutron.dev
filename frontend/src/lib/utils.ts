import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function getAgentBgColor(agent: string): string {
  const colors: Record<string, string> = {
    team_leader: "bg-leader/10 border-leader/20",
    product_manager: "bg-pm/10 border-pm/20",
    architect: "bg-architect/10 border-architect/20",
    engineer: "bg-engineer/10 border-engineer/20",
    data_scientist: "bg-scientist/10 border-scientist/20",
  };
  return colors[agent] ?? "bg-surface border-border";
}
