import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ConsolePanel, type ConsoleEntry } from "@/components/workspace/console-panel";

function makeEntry(overrides: Partial<ConsoleEntry> = {}): ConsoleEntry {
  return {
    id: "e1",
    level: "error",
    message: "Uncaught TypeError",
    timestamp: 1000,
    ...overrides,
  };
}

describe("ConsolePanel", () => {
  it("shows empty state when there are no entries", () => {
    render(<ConsolePanel entries={[]} onClear={vi.fn()} onResolve={vi.fn()} />);
    expect(screen.getByText("No console output yet.")).toBeInTheDocument();
  });

  it("renders a single error entry with message count", () => {
    const entries = [makeEntry()];
    render(<ConsolePanel entries={entries} onClear={vi.fn()} onResolve={vi.fn()} />);
    expect(screen.getByText("1 message")).toBeInTheDocument();
    expect(screen.getByText("Uncaught TypeError")).toBeInTheDocument();
  });

  it("renders plural message count for multiple entries", () => {
    const entries = [
      makeEntry({ id: "e1", level: "error", message: "Error one" }),
      makeEntry({ id: "e2", level: "warn", message: "Warning one" }),
      makeEntry({ id: "e3", level: "info", message: "Info one" }),
    ];
    render(<ConsolePanel entries={entries} onClear={vi.fn()} onResolve={vi.fn()} />);
    expect(screen.getByText("3 messages")).toBeInTheDocument();
    expect(screen.getByText("Error one")).toBeInTheDocument();
    expect(screen.getByText("Warning one")).toBeInTheDocument();
    expect(screen.getByText("Info one")).toBeInTheDocument();
  });

  it("calls onClear when Clear button is clicked", async () => {
    const user = userEvent.setup();
    const onClear = vi.fn();
    render(<ConsolePanel entries={[makeEntry()]} onClear={onClear} onResolve={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /Clear/ }));
    expect(onClear).toHaveBeenCalledOnce();
  });

  it("shows Resolve button only for error entries and calls onResolve", async () => {
    const user = userEvent.setup();
    const onResolve = vi.fn();
    const entries = [
      makeEntry({ id: "e1", level: "error", message: "Error" }),
      makeEntry({ id: "e2", level: "warn", message: "Warning" }),
    ];
    render(<ConsolePanel entries={entries} onClear={vi.fn()} onResolve={onResolve} />);
    const resolveButtons = screen.getAllByRole("button", { name: /Resolve/ });
    expect(resolveButtons).toHaveLength(1);
    await user.click(resolveButtons[0]);
    expect(onResolve).toHaveBeenCalledWith(entries[0]);
  });
});
