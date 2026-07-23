import { describe, expect, it } from "vitest";
import { AGENTS } from "@/types";

describe("AGENTS", () => {
  it("defines the five agent contracts in display order", () => {
    expect(AGENTS).toEqual([
      { id: "team_leader", name: "Kai", role: "Team Leader", avatar: "/agents/team_leader.svg", color: "var(--leader)" },
      { id: "product_manager", name: "Nina", role: "Product Manager", avatar: "/agents/pm.svg", color: "var(--pm)" },
      { id: "architect", name: "Theo", role: "System Architect", avatar: "/agents/architect.svg", color: "var(--architect)" },
      { id: "engineer", name: "Ravi", role: "Software Engineer", avatar: "/agents/engineer.svg", color: "var(--engineer)" },
      { id: "data_scientist", name: "Zara", role: "Data Scientist", avatar: "/agents/data_scientist.svg", color: "var(--scientist)" },
    ]);
    expect(new Set(AGENTS.map((agent) => agent.id)).size).toBe(5);
  });
});
