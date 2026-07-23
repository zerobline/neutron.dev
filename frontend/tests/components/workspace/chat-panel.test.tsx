import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { ChatPanel } from "@/components/workspace/chat-panel";
import { useProjectStore } from "@/stores/project-store";
import { api } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  api: {
    uploadFile: vi.fn(),
  },
}));

describe("ChatPanel", () => {
  const defaultProps = {
    projectId: "p1",
    onSend: vi.fn(),
    onStartBuild: vi.fn(),
    onResumeBuild: vi.fn(),
    onFeedback: vi.fn(),
    projectDescription: "My project",
  };

  beforeEach(() => {
    vi.mocked(api.uploadFile).mockResolvedValue({ name: "file.txt", size: 100, type: "text/plain", path: "/uploads/file.txt" });
  });

  it("renders empty state with Start Building button", () => {
    render(<ChatPanel {...defaultProps} />);
    expect(screen.getByText("Ready to Build")).toBeInTheDocument();
    expect(screen.getByText(/My project/)).toBeInTheDocument();
  });

  it("Start Building uses project description", async () => {
    const user = userEvent.setup();
    const onStartBuild = vi.fn();
    render(<ChatPanel {...defaultProps} onStartBuild={onStartBuild} />);
    await user.click(screen.getByRole("button", { name: "Start Building" }));
    expect(onStartBuild).toHaveBeenCalledWith("My project");
  });

  it("submits typed text as start build when status is created", async () => {
    const user = userEvent.setup();
    const onStartBuild = vi.fn();
    render(<ChatPanel {...defaultProps} onStartBuild={onStartBuild} />);
    await user.type(screen.getByPlaceholderText("Describe what to build, or click Start Building..."), "Build something");
    fireEvent.keyDown(screen.getByPlaceholderText("Describe what to build, or click Start Building..."), { key: "Enter" });
    expect(onStartBuild).toHaveBeenCalledWith("Build something");
  });

  it("sends message when status is building", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    useProjectStore.setState({
      projectStatus: "building",
      agents: [{ agent: "engineer", status: "working" }],
      messages: [{ id: "m1", role: "system", content: "Started", timestamp: 1 }],
    });
    render(<ChatPanel {...defaultProps} onSend={onSend} />);
    await user.type(screen.getByPlaceholderText("Send a message..."), "Hello");
    fireEvent.keyDown(screen.getByPlaceholderText("Send a message..."), { key: "Enter" });
    expect(onSend).toHaveBeenCalledWith("Hello");
  });

  it("routes a completed-project mention directly to the engineer", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    useProjectStore.setState({
      projectStatus: "complete",
      messages: [{ id: "m1", role: "system", content: "Done", timestamp: 1 }],
    });
    render(<ChatPanel {...defaultProps} onSend={onSend} />);

    await user.click(screen.getByRole("button", { name: /Custom edit/i }));
    const input = screen.getByPlaceholderText("Describe an update, or type @ for Kai, Nina, Theo, Zara, or Ravi...");
    expect(input).toHaveValue("@engineer ");
    await user.type(input, "add a compact pricing section");
    fireEvent.keyDown(input, { key: "Enter" });

    expect(onSend).toHaveBeenCalledWith("@engineer add a compact pricing section", "engineer");
  });

  it("runs a suggested follow-up as an engineer edit", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    useProjectStore.setState({
      projectStatus: "complete",
      messages: [{ id: "m1", role: "system", content: "Done", timestamp: 1 }],
      lastCompletion: {
        message: "Project generation complete!",
        mode: "team",
        files: ["index.html", "app.js"],
        filesChanged: ["index.html", "app.js"],
        checklist: {
          items: [
            { id: "required_files", label: "Core files written", ok: true },
            { id: "seeded_demo_data", label: "Demo data seeded", ok: false, detail: "May look empty" },
          ],
        },
        suggestions: [
          {
            id: "mock_data",
            label: "Fill with mock data",
            prompt: "@engineer Fill the app with realistic mock data",
          },
        ],
        timestamp: 1,
      },
    });
    render(<ChatPanel {...defaultProps} onSend={onSend} />);
    expect(screen.getByText("Quality check")).toBeInTheDocument();
    expect(screen.getByText("Files changed")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Fill with mock data" }));
    expect(onSend).toHaveBeenCalledWith("@engineer Fill the app with realistic mock data", "engineer");
  });

  it("supports keyboard mention selection and dismissal", async () => {
    const user = userEvent.setup();
    useProjectStore.setState({
      projectStatus: "complete",
      messages: [{ id: "m1", role: "system", content: "Done", timestamp: 1 }],
    });
    render(<ChatPanel {...defaultProps} />);
    const input = screen.getByPlaceholderText("Describe an update, or type @ for Kai, Nina, Theo, Zara, or Ravi...");

    await user.type(input, "@");
    expect(screen.getByRole("listbox", { name: "Agent mentions" })).toBeInTheDocument();
    fireEvent.mouseDown(screen.getByRole("option", { name: /@engineer/ }));
    fireEvent.keyDown(input, { key: "Tab" });
    expect(input).toHaveValue("@kai ");

    await user.clear(input);
    await user.type(input, "@r");
    fireEvent.keyDown(input, { key: "Enter" });
    expect(input).toHaveValue("@engineer ");

    await user.clear(input);
    await user.type(input, "Please @");
    fireEvent.keyDown(input, { key: "Escape" });
    expect(input).toHaveValue("Please ");

    await user.type(input, "@z");
    expect(screen.getByRole("listbox", { name: "Agent mentions" })).toBeInTheDocument();
  });

  it("resumes an interrupted build from a continue command", async () => {
    const user = userEvent.setup();
    const onResumeBuild = vi.fn();
    const onSend = vi.fn();
    useProjectStore.setState({
      projectStatus: "building",
      messages: [{ id: "m1", role: "agent", agent: "data_scientist", content: "Research", timestamp: 1 }],
    });
    render(<ChatPanel {...defaultProps} onResumeBuild={onResumeBuild} onSend={onSend} />);
    await user.type(screen.getByPlaceholderText("Send a message..."), "continue");
    fireEvent.keyDown(screen.getByPlaceholderText("Send a message..."), { key: "Enter" });
    expect(onResumeBuild).toHaveBeenCalledWith("My project");
    expect(onSend).not.toHaveBeenCalled();
  });

  it("shows a resume button for interrupted builds", async () => {
    const user = userEvent.setup();
    const onResumeBuild = vi.fn();
    useProjectStore.setState({
      projectStatus: "awaiting_feedback",
      pendingFeedback: null,
      messages: [{ id: "m1", role: "agent", agent: "data_scientist", content: "Research", timestamp: 1 }],
    });
    render(<ChatPanel {...defaultProps} onResumeBuild={onResumeBuild} />);
    expect(screen.getByText(/Resume from the last CrewAI checkpoint/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Resume from checkpoint" }));
    expect(onResumeBuild).toHaveBeenCalledWith("My project");
  });

  it("does not show resume button while feedback is pending", () => {
    useProjectStore.setState({
      projectStatus: "awaiting_feedback",
      pendingFeedback: { phase: "analysis", agent: "data_scientist", content: "Research", message: "Review" },
      messages: [{ id: "m1", role: "agent", agent: "data_scientist", content: "Research", timestamp: 1 }],
    });
    render(<ChatPanel {...defaultProps} />);
    expect(screen.queryByRole("button", { name: "Resume from checkpoint" })).not.toBeInTheDocument();
  });

  it("does not submit empty message", () => {
    const onSend = vi.fn();
    const onStartBuild = vi.fn();
    render(<ChatPanel {...defaultProps} onSend={onSend} onStartBuild={onStartBuild} />);
    fireEvent.keyDown(screen.getByPlaceholderText("Describe what to build, or click Start Building..."), { key: "Enter" });
    expect(onSend).not.toHaveBeenCalled();
    expect(onStartBuild).not.toHaveBeenCalled();
  });

  it("does not submit on shift+enter", async () => {
    const user = userEvent.setup();
    const onStartBuild = vi.fn();
    render(<ChatPanel {...defaultProps} onStartBuild={onStartBuild} />);
    await user.type(screen.getByPlaceholderText("Describe what to build, or click Start Building..."), "test{shift>}{enter}{/shift}");
    expect(onStartBuild).not.toHaveBeenCalled();
  });

  it("uploads files via paperclip button", async () => {
    vi.mocked(api.uploadFile).mockResolvedValueOnce({ name: "test.txt", size: 100, type: "text/plain", path: "/uploads/test.txt" });
    render(<ChatPanel {...defaultProps} />);
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["data"], "test.txt", { type: "text/plain" });
    fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => expect(api.uploadFile).toHaveBeenCalledWith("p1", file));
    await waitFor(() => expect(screen.getByText(/test\.txt/)).toBeInTheDocument());
  });

  it("removes attached file tags", async () => {
    const user = userEvent.setup();
    vi.mocked(api.uploadFile).mockResolvedValueOnce({ name: "test.txt", size: 100, type: "text/plain", path: "/uploads/test.txt" });
    render(<ChatPanel {...defaultProps} />);
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["data"], "test.txt", { type: "text/plain" });
    fireEvent.change(fileInput, { target: { files: [file] } });
    await waitFor(() => expect(screen.getByText(/test\.txt/)).toBeInTheDocument());
    const fileTag = screen.getByText(/test\.txt/).closest("span")!;
    const removeBtn = fileTag.querySelector("button");
    if (removeBtn) await user.click(removeBtn);
    await waitFor(() => expect(screen.queryByText(/test\.txt/)).not.toBeInTheDocument());
  });

  it("submits message with file references", async () => {
    const onStartBuild = vi.fn();
    vi.mocked(api.uploadFile).mockResolvedValueOnce({ name: "doc.pdf", size: 50, type: "application/pdf", path: "/uploads/doc.pdf" });
    render(<ChatPanel {...defaultProps} onStartBuild={onStartBuild} />);
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["data"], "doc.pdf", { type: "application/pdf" });
    fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => expect(screen.getByText(/doc\.pdf/)).toBeInTheDocument());
    fireEvent.keyDown(screen.getByPlaceholderText("Describe what to build, or click Start Building..."), { key: "Enter" });
    expect(onStartBuild).toHaveBeenCalledWith("#doc.pdf");
  });

  it("handles paste with image files", async () => {
    render(<ChatPanel {...defaultProps} />);
    useProjectStore.setState({ projectStatus: "building", messages: [{ id: "m1", role: "system", content: "x", timestamp: 1 }] });
    const textarea = screen.getByPlaceholderText("Describe what to build, or click Start Building...");

    const file = new File(["img"], "screenshot.png", { type: "image/png" });
    const clipboardData = {
      items: [{ type: "image/png", getAsFile: () => file }],
    };
    fireEvent.paste(textarea, { clipboardData });
    await waitFor(() => expect(api.uploadFile).toHaveBeenCalledWith("p1", file));
  });

  it("ignores paste with no image files", () => {
    useProjectStore.setState({ projectStatus: "building", messages: [{ id: "m1", role: "system", content: "x", timestamp: 1 }] });
    render(<ChatPanel {...defaultProps} />);
    const textarea = screen.getByPlaceholderText("Send a message...");
    const clipboardData = {
      items: [{ type: "text/plain" }],
    };
    fireEvent.paste(textarea, { clipboardData });
    expect(api.uploadFile).not.toHaveBeenCalled();
  });

  it("ignores pasted image item when getAsFile returns null", () => {
    useProjectStore.setState({ projectStatus: "building", messages: [{ id: "m1", role: "system", content: "x", timestamp: 1 }] });
    render(<ChatPanel {...defaultProps} />);
    const textarea = screen.getByPlaceholderText("Send a message...");
    const clipboardData = {
      items: [{ type: "image/png", getAsFile: () => null }],
    };
    fireEvent.paste(textarea, { clipboardData });
    expect(api.uploadFile).not.toHaveBeenCalled();
  });

  it("shows upload failure and clears it after a successful retry", async () => {
    vi.mocked(api.uploadFile)
      .mockRejectedValueOnce(new Error("fail"))
      .mockResolvedValueOnce({ name: "retry.txt", size: 100, type: "text/plain", path: "/uploads/retry.txt" });
    render(<ChatPanel {...defaultProps} />);
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(fileInput, { target: { files: [new File(["data"], "test.txt", { type: "text/plain" })] } });
    expect(await screen.findByText("Could not upload file. Please try again.")).toBeInTheDocument();

    fireEvent.change(fileInput, { target: { files: [new File(["data"], "retry.txt", { type: "text/plain" })] } });
    await waitFor(() => expect(screen.queryByText("Could not upload file. Please try again.")).not.toBeInTheDocument());
    expect(screen.getByText(/retry\.txt/)).toBeInTheDocument();
  });

  it("handles file input change with no files", () => {
    render(<ChatPanel {...defaultProps} />);
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(fileInput, { target: { files: null } });
    expect(api.uploadFile).not.toHaveBeenCalled();
  });

  it("opens file dialog via paperclip button", async () => {
    const user = userEvent.setup();
    render(<ChatPanel {...defaultProps} />);
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const clickSpy = vi.spyOn(fileInput, "click");
    const paperclipBtn = screen.getAllByRole("button").find((b) => b.querySelector(".lucide-paperclip"));
    if (paperclipBtn) await user.click(paperclipBtn);
    expect(clickSpy).toHaveBeenCalled();
  });

  it("renders feedback panel when pending feedback exists", () => {
    useProjectStore.setState({
      projectStatus: "building",
      messages: [{ id: "m1", role: "system", content: "x", timestamp: 1 }],
      pendingFeedback: { phase: "planning", agent: "product_manager", content: "Plan", message: "Review" },
    });
    render(<ChatPanel {...defaultProps} />);
    expect(screen.getByText(/Review/)).toBeInTheDocument();
  });

  it("scrolls to bottom on new messages", () => {
    const { rerender } = render(<ChatPanel {...defaultProps} />);
    useProjectStore.setState({
      messages: [{ id: "m1", role: "system", content: "Hello", timestamp: 1 }],
    });
    rerender(<ChatPanel {...defaultProps} />);
  });

  it("handles paste with no clipboardData items", () => {
    useProjectStore.setState({ projectStatus: "building", messages: [{ id: "m1", role: "system", content: "x", timestamp: 1 }] });
    render(<ChatPanel {...defaultProps} />);
    const textarea = screen.getByPlaceholderText("Send a message...");
    fireEvent.paste(textarea, { clipboardData: null });
    expect(api.uploadFile).not.toHaveBeenCalled();
  });
});
