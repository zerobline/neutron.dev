import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { BuildModeDropdown } from "@/components/dashboard/build-mode-dropdown";

describe("BuildModeDropdown", () => {
  it("renders the current mode label", () => {
    render(<BuildModeDropdown value="build" onChange={vi.fn()} />);
    expect(screen.getByRole("button", { name: /Review steps/ })).toBeInTheDocument();
  });

  it("opens dropdown and shows both options", async () => {
    const user = userEvent.setup();
    render(<BuildModeDropdown value="build" onChange={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /Review steps/ }));
    expect(screen.getByText("Approve each planning phase")).toBeInTheDocument();
    expect(screen.getByText("Plans and builds to completion")).toBeInTheDocument();
    expect(screen.getByText("Recommended")).toBeInTheDocument();
  });

  it("calls onChange when a different mode is selected", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<BuildModeDropdown value="build" onChange={onChange} />);
    await user.click(screen.getByRole("button", { name: /Review steps/ }));
    await user.click(screen.getByText("Auto build"));
    expect(onChange).toHaveBeenCalledWith("goal");
  });

  it("closes dropdown after selection", async () => {
    const user = userEvent.setup();
    render(<BuildModeDropdown value="build" onChange={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /Review steps/ }));
    expect(screen.getByText("Approve each planning phase")).toBeInTheDocument();
    await user.click(screen.getByText("Auto build"));
    expect(screen.queryByText("Approve each planning phase")).not.toBeInTheDocument();
  });

  it("closes dropdown on outside click", async () => {
    const user = userEvent.setup();
    render(<BuildModeDropdown value="build" onChange={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /Review steps/ }));
    expect(screen.getByText("Approve each planning phase")).toBeInTheDocument();
    fireEvent.mouseDown(document.body);
    expect(screen.queryByText("Approve each planning phase")).not.toBeInTheDocument();
  });

  it("shows check mark next to the active mode", async () => {
    const user = userEvent.setup();
    const { rerender } = render(<BuildModeDropdown value="goal" onChange={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /Auto build/ }));
    const goalButton = screen.getByText("Plans and builds to completion").closest("button")!;
    expect(goalButton.querySelector("svg")).not.toBeNull();

    rerender(<BuildModeDropdown value="build" onChange={vi.fn()} />);
  });
});
