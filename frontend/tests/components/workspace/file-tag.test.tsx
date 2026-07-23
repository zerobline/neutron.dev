import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { FileTag } from "@/components/workspace/file-tag";

describe("FileTag", () => {
  it("renders the file name with hash prefix", () => {
    render(<FileTag name="readme.md" />);
    expect(screen.getByText("#readme.md")).toBeInTheDocument();
  });

  it("does not render remove button when onRemove is absent", () => {
    render(<FileTag name="readme.md" />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("renders remove button and calls onRemove when clicked", async () => {
    const user = userEvent.setup();
    const onRemove = vi.fn();
    render(<FileTag name="readme.md" onRemove={onRemove} />);
    await user.click(screen.getByRole("button"));
    expect(onRemove).toHaveBeenCalledOnce();
  });
});
