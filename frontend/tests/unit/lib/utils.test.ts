import { describe, expect, it } from "vitest";
import { cn, getAgentBgColor } from "@/lib/utils";

describe("utils", () => {
  it("merges conditional classes and resolves Tailwind conflicts", () => {
    expect(cn("px-2", false && "hidden", ["text-sm"], "px-4")).toBe("text-sm px-4");
  });

  it.each([
    ["team_leader", "bg-leader/10 border-leader/20"],
    ["product_manager", "bg-pm/10 border-pm/20"],
    ["architect", "bg-architect/10 border-architect/20"],
    ["engineer", "bg-engineer/10 border-engineer/20"],
    ["data_scientist", "bg-scientist/10 border-scientist/20"],
    ["unknown", "bg-surface border-border"],
  ])("returns bg colors for %s", (agent, bg) => {
    expect(getAgentBgColor(agent)).toBe(bg);
  });
});
