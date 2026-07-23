import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DeleteProjectDialog } from "@/components/dashboard/delete-project-dialog";
import { NewProjectDialog } from "@/components/dashboard/new-project-dialog";
import { ProjectCard } from "@/components/dashboard/project-card";
import { projectFixture } from "../../utils/fixtures";

describe("dashboard components", () => {
  it("renders project card with status variants and date", () => {
    render(<ProjectCard project={{ ...projectFixture, status: "complete" }} />);
    expect(screen.getAllByRole("link").some((link) => link.getAttribute("href") === "/project/project-1")).toBe(true);
    expect(screen.getByText("complete")).toBeInTheDocument();
    expect(screen.getByText("Build a test app")).toBeInTheDocument();
  });

  it("calls delete handler from project card without changing the project link", async () => {
    const user = userEvent.setup();
    const onDelete = vi.fn();
    render(<ProjectCard project={projectFixture} onDelete={onDelete} />);

    expect(screen.getAllByRole("link").some((link) => link.getAttribute("href") === "/project/project-1")).toBe(true);
    await user.click(screen.getByRole("button", { name: "Delete Project One" }));
    expect(onDelete).toHaveBeenCalledWith(projectFixture);
  });

  it("falls back for unknown project status", () => {
    render(<ProjectCard project={{ ...projectFixture, status: "weird" as never }} />);
    expect(screen.getByText("weird")).toHaveClass("bg-surface");
  });

  it("validates and submits new project dialog", async () => {
    const user = userEvent.setup();
    const onCreate = vi.fn();
    const onClose = vi.fn();
    render(<NewProjectDialog open onClose={onClose} onCreate={onCreate} initialDescription=" Template prompt " />);

    expect(screen.getByLabelText("Description")).toHaveValue(" Template prompt ");
    expect(screen.getByRole("button", { name: "Create Project" })).toBeDisabled();
    await user.type(screen.getByLabelText("Project Name"), "  Name  ");
    await user.click(screen.getByRole("button", { name: "Create Project" }));
    expect(onCreate).toHaveBeenCalledWith("Name", "Template prompt");
    expect(screen.getByLabelText("Project Name")).toHaveValue("");
    expect(screen.getByLabelText("Description")).toHaveValue("");
    await user.type(screen.getByLabelText("Description"), "Manual desc");
    expect(screen.getByLabelText("Description")).toHaveValue("Manual desc");

    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onClose).toHaveBeenCalled();
  });

  it("does not submit blank dialog fields", () => {
    const onCreate = vi.fn();
    render(<NewProjectDialog open onClose={vi.fn()} onCreate={onCreate} />);
    fireEvent.click(screen.getByRole("button", { name: "Create Project" }));
    expect(onCreate).not.toHaveBeenCalled();
  });

  it("handles overlay close for delete project dialog", () => {
    const onClose = vi.fn();
    const { container, rerender } = render(
      <DeleteProjectDialog
        project={projectFixture}
        open
        deleting={false}
        error={null}
        onClose={onClose}
        onConfirm={vi.fn()}
      />
    );
    fireEvent.click(container.firstElementChild!);
    expect(onClose).toHaveBeenCalledOnce();

    rerender(
      <DeleteProjectDialog
        project={projectFixture}
        open
        deleting
        error={null}
        onClose={onClose}
        onConfirm={vi.fn()}
      />
    );
    fireEvent.click(container.firstElementChild!);
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("confirms and disables delete project dialog", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const onConfirm = vi.fn();
    const { rerender } = render(
      <DeleteProjectDialog
        project={projectFixture}
        open
        deleting={false}
        error="Could not delete project. Try again."
        onClose={onClose}
        onConfirm={onConfirm}
      />
    );

    expect(screen.getByText(/permanently delete “Project One”/)).toBeInTheDocument();
    expect(screen.getByText("Could not delete project. Try again.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Delete Project" }));
    expect(onConfirm).toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onClose).toHaveBeenCalled();

    rerender(
      <DeleteProjectDialog
        project={projectFixture}
        open
        deleting
        error={null}
        onClose={onClose}
        onConfirm={onConfirm}
      />
    );
    expect(screen.getByRole("button", { name: "Deleting..." })).toBeDisabled();
  });
});
