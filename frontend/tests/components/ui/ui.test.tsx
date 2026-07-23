import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";

describe("ui components", () => {
  it.each([
    ["primary", "md"],
    ["secondary", "sm"],
    ["ghost", "lg"],
    ["danger", "md"],
  ] as const)("renders button variant %s size %s", (variant, size) => {
    render(<Button variant={variant} size={size}>Click</Button>);
    expect(screen.getByRole("button", { name: "Click" })).toBeInTheDocument();
  });

  it("forwards input and textarea props", () => {
    render(<><Input aria-label="name" defaultValue="Ada" className="custom" /><Textarea aria-label="desc" rows={3} defaultValue="Bio" /></>);
    expect(screen.getByLabelText("name")).toHaveValue("Ada");
    expect(screen.getByLabelText("desc")).toHaveValue("Bio");
  });

  it("renders card sections", () => {
    render(<Card><CardHeader>Head</CardHeader><CardTitle>Title</CardTitle><CardDescription>Desc</CardDescription><CardContent>Body</CardContent></Card>);
    expect(screen.getByText("Head")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Title" })).toBeInTheDocument();
    expect(screen.getByText("Desc")).toBeInTheDocument();
    expect(screen.getByText("Body")).toBeInTheDocument();
  });

  it.each(["sm", "md", "lg"] as const)("renders avatar size %s", (size) => {
    render(<Avatar name="alex" color="red" size={size} status="idle" />);
    expect(screen.getByText("A").getAttribute("style")).toContain("color: red");
  });

  it.each(["thinking", "working", "complete"] as const)("renders avatar status %s", (status) => {
    const { container } = render(<Avatar name="Maya" color="blue" status={status} />);
    expect(container.querySelector("span")).toBeInTheDocument();
  });

  it.each(["default", "success", "warning", "error", "info"] as const)("renders badge %s", (variant) => {
    render(<Badge variant={variant}>Badge</Badge>);
    expect(screen.getByText("Badge")).toBeInTheDocument();
  });

  it("handles dialog open, overlay close, inner click, and cleanup", () => {
    const onClose = vi.fn();
    const { rerender, unmount } = render(<Dialog open={false} onClose={onClose}>Closed</Dialog>);
    expect(screen.queryByText("Closed")).not.toBeInTheDocument();

    rerender(<Dialog open onClose={onClose} className="custom"><DialogTitle>Title</DialogTitle><DialogDescription>Desc</DialogDescription><button>Inner</button></Dialog>);
    expect(document.body.style.overflow).toBe("hidden");
    fireEvent.click(screen.getByRole("button", { name: "Inner" }));
    expect(onClose).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText("Title").parentElement!.parentElement!);
    expect(onClose).toHaveBeenCalledTimes(1);

    rerender(<Dialog open={false} onClose={onClose}>Closed</Dialog>);
    expect(document.body.style.overflow).toBe("");
    unmount();
    expect(document.body.style.overflow).toBe("");
  });

  it("renders skeleton with custom class", () => {
    const { container } = render(<Skeleton className="h-4" />);
    expect(container.firstChild).toHaveClass("animate-pulse", "h-4");
  });
});
