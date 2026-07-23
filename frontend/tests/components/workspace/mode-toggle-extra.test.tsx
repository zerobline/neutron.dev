import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ModeToggle } from "@/components/workspace/mode-toggle";
import { useProjectStore } from "@/stores/project-store";

describe("ModeToggle extended", () => {
  it("renders team, engineer, and goal modes", () => {
    render(<ModeToggle />);
    expect(screen.getByRole("button", { name: /Team/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Engineer/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Goal/ })).toBeInTheDocument();
  });

  it("switches to engineer and goal modes when clicked", async () => {
    const user = userEvent.setup();
    render(<ModeToggle />);
    await user.click(screen.getByRole("button", { name: /Engineer/ }));
    expect(useProjectStore.getState().buildMode).toBe("engineer");
    await user.click(screen.getByRole("button", { name: /Goal/ }));
    expect(useProjectStore.getState().buildMode).toBe("goal");
  });

  it("is locked when project status is not created", async () => {
    const user = userEvent.setup();
    useProjectStore.setState({ projectStatus: "building" });
    render(<ModeToggle />);
    const engineerBtn = screen.getByRole("button", { name: /Engineer/ });
    expect(engineerBtn).toBeDisabled();
    await user.click(engineerBtn);
    expect(useProjectStore.getState().buildMode).toBe("team");
  });
});
