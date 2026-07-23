import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SkillsPanel } from "@/components/workspace/skills-panel";

const getProjectSkills = vi.fn();
const saveProjectSkills = vi.fn();
const createProjectSkill = vi.fn();
const deleteProjectSkill = vi.fn();
const listBuiltinSkills = vi.fn();

vi.mock("@/lib/api", () => ({
  api: {
    getProjectSkills: (...args: unknown[]) => getProjectSkills(...args),
    saveProjectSkills: (...args: unknown[]) => saveProjectSkills(...args),
    createProjectSkill: (...args: unknown[]) => createProjectSkill(...args),
    deleteProjectSkill: (...args: unknown[]) => deleteProjectSkill(...args),
    listBuiltinSkills: (...args: unknown[]) => listBuiltinSkills(...args),
  },
}));

const catalog = {
  skills: [
    {
      name: "mvp-scope-discipline",
      description: "Keep MVP tight",
      source: "builtin" as const,
      recommended_agents: ["team_leader"],
      enabled: false,
      agents: ["all"] as const,
      body_preview: "When shaping…",
    },
    {
      name: "brand-voice",
      description: "Friendly tone",
      source: "custom" as const,
      recommended_agents: [],
      enabled: true,
      agents: ["product_manager"] as const,
      body_preview: "Use short sentences",
    },
  ],
};

describe("SkillsPanel", () => {
  beforeEach(() => {
    getProjectSkills.mockReset();
    saveProjectSkills.mockReset();
    createProjectSkill.mockReset();
    deleteProjectSkill.mockReset();
    listBuiltinSkills.mockReset();
    localStorage.clear();
    getProjectSkills.mockResolvedValue(catalog);
    listBuiltinSkills.mockResolvedValue(
      catalog.skills.filter((s) => s.source === "builtin").map((s) => ({ ...s, enabled: false })),
    );
    saveProjectSkills.mockImplementation(async (_id: string, skills: unknown) => ({
      skills: (skills as Array<{ name: string; enabled: boolean; agents: string[] }>).map((s) => {
        const existing = catalog.skills.find((c) => c.name === s.name)!;
        return { ...existing, enabled: s.enabled, agents: s.agents };
      }),
    }));
  });

  it("does not load when closed", () => {
    render(<SkillsPanel projectId="p1" open={false} onClose={vi.fn()} />);
    expect(getProjectSkills).not.toHaveBeenCalled();
  });

  it("loads builtin catalog in dashboard draft mode without a project", async () => {
    render(<SkillsPanel open onClose={vi.fn()} />);
    await waitFor(() => expect(listBuiltinSkills).toHaveBeenCalled());
    expect(getProjectSkills).not.toHaveBeenCalled();
    expect(screen.getByText("mvp-scope-discipline")).toBeInTheDocument();
    expect(
      screen.getByText(/Choose skills before you start/i),
    ).toBeInTheDocument();
  });

  it("persists draft toggles to localStorage", async () => {
    const user = userEvent.setup();
    render(<SkillsPanel open onClose={vi.fn()} />);
    await waitFor(() => expect(listBuiltinSkills).toHaveBeenCalled());
    await user.click(screen.getByRole("switch", { name: /Enable mvp-scope-discipline/i }));
    const stored = JSON.parse(localStorage.getItem("neutron-skill-assignments") || "[]");
    expect(stored.some((s: { name: string; enabled: boolean }) => s.name === "mvp-scope-discipline" && s.enabled)).toBe(true);
  });

  it("loads and lists skills when open", async () => {
    render(<SkillsPanel projectId="p1" open onClose={vi.fn()} />);
    await waitFor(() => expect(getProjectSkills).toHaveBeenCalledWith("p1"));
    expect(screen.getByRole("heading", { name: "Team Skills" })).toBeInTheDocument();
    expect(screen.getByText("mvp-scope-discipline")).toBeInTheDocument();
    expect(screen.getByText("brand-voice")).toBeInTheDocument();
    expect(screen.getByRole("switch", { name: /Disable brand-voice/i })).toHaveAttribute(
      "aria-checked",
      "true",
    );
  });

  it("toggles a skill and saves", async () => {
    const user = userEvent.setup();
    render(<SkillsPanel projectId="p1" open onClose={vi.fn()} />);
    await waitFor(() => expect(getProjectSkills).toHaveBeenCalled());
    await user.click(screen.getByRole("switch", { name: /Enable mvp-scope-discipline/i }));
    await waitFor(() => expect(saveProjectSkills).toHaveBeenCalled());
    const payload = saveProjectSkills.mock.calls[0][1];
    expect(payload.find((s: { name: string }) => s.name === "mvp-scope-discipline").enabled).toBe(true);
  });

  it("creates a custom skill", async () => {
    const user = userEvent.setup();
    createProjectSkill.mockResolvedValue({
      skills: [
        ...catalog.skills,
        {
          name: "seo-checklist",
          description: "SEO basics",
          source: "custom",
          recommended_agents: [],
          enabled: true,
          agents: ["all"],
        },
      ],
    });
    render(<SkillsPanel projectId="p1" open onClose={vi.fn()} />);
    await waitFor(() => expect(getProjectSkills).toHaveBeenCalled());
    await user.click(screen.getByRole("button", { name: /Add custom skill/i }));
    await user.type(screen.getByLabelText("Skill name"), "seo-checklist");
    await user.type(screen.getByLabelText("Skill description"), "SEO basics");
    await user.type(screen.getByLabelText("Skill instructions"), "Add meta titles.");
    await user.click(screen.getByRole("button", { name: /Create skill/i }));
    await waitFor(() =>
      expect(createProjectSkill).toHaveBeenCalledWith(
        "p1",
        expect.objectContaining({
          name: "seo-checklist",
          description: "SEO basics",
          body: "Add meta titles.",
        }),
      ),
    );
    expect(screen.getByText("seo-checklist")).toBeInTheDocument();
  });

  it("deletes a custom skill", async () => {
    const user = userEvent.setup();
    deleteProjectSkill.mockResolvedValue({
      skills: catalog.skills.filter((s) => s.name !== "brand-voice"),
    });
    render(<SkillsPanel projectId="p1" open onClose={vi.fn()} />);
    await waitFor(() => expect(getProjectSkills).toHaveBeenCalled());
    await user.click(screen.getByRole("button", { name: /Delete brand-voice/i }));
    await waitFor(() => expect(deleteProjectSkill).toHaveBeenCalledWith("p1", "brand-voice"));
    expect(screen.queryByText("brand-voice")).not.toBeInTheDocument();
  });

  it("shows load error", async () => {
    getProjectSkills.mockRejectedValueOnce(new Error("fail"));
    render(<SkillsPanel projectId="p1" open onClose={vi.fn()} />);
    await waitFor(() => expect(screen.getByText("Could not load team skills.")).toBeInTheDocument());
  });
});
