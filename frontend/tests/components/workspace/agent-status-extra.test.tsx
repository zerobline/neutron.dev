import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AgentStatusBar } from "@/components/workspace/agent-status";
import { useProjectStore } from "@/stores/project-store";

const getProjectSkills = vi.fn();

vi.mock("@/lib/api", () => ({
  api: {
    getProjectSkills: (...args: unknown[]) => getProjectSkills(...args),
    saveProjectSkills: vi.fn(),
    createProjectSkill: vi.fn(),
    deleteProjectSkill: vi.fn(),
  },
}));

describe("AgentStatusBar extended", () => {
  beforeEach(() => {
    getProjectSkills.mockReset();
    getProjectSkills.mockResolvedValue({ skills: [] });
  });

  it("shows only the engineer in engineer mode", () => {
    useProjectStore.setState({ buildMode: "engineer" });
    render(<AgentStatusBar />);
    expect(screen.getByText("Ravi")).toBeInTheDocument();
    expect(screen.queryByText("Kai")).not.toBeInTheDocument();
    expect(screen.queryByText("Nina")).not.toBeInTheDocument();
    expect(screen.queryByText("Theo")).not.toBeInTheDocument();
    expect(screen.queryByText("Zara")).not.toBeInTheDocument();
  });

  it("shows all agents in team mode", () => {
    useProjectStore.setState({ buildMode: "team" });
    render(<AgentStatusBar />);
    expect(screen.getByText("Kai")).toBeInTheDocument();
    expect(screen.getByText("Nina")).toBeInTheDocument();
    expect(screen.getByText("Theo")).toBeInTheDocument();
    expect(screen.getByText("Ravi")).toBeInTheDocument();
    expect(screen.getByText("Zara")).toBeInTheDocument();
  });

  it("hides phase badge when no phase is set", () => {
    useProjectStore.setState({ currentPhase: "" });
    render(<AgentStatusBar />);
    expect(screen.queryByText("Planning")).not.toBeInTheDocument();
  });

  it("shows reconnecting state when disconnected", () => {
    render(<AgentStatusBar connected={false} />);
    expect(screen.getByText("Reconnecting")).toBeInTheDocument();
  });

  it("opens skills panel when projectId is provided", async () => {
    const user = userEvent.setup();
    render(<AgentStatusBar projectId="proj-1" />);
    await user.click(screen.getByRole("button", { name: /Skills/i }));
    await waitFor(() => expect(getProjectSkills).toHaveBeenCalledWith("proj-1"));
    expect(screen.getByRole("heading", { name: "Team Skills" })).toBeInTheDocument();
  });

  it("hides skills button without projectId", () => {
    render(<AgentStatusBar />);
    expect(screen.queryByRole("button", { name: /Skills/i })).not.toBeInTheDocument();
  });
});
