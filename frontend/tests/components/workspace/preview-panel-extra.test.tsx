import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { PreviewPanel } from "@/components/workspace/preview-panel";
import { useProjectStore } from "@/stores/project-store";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    downloadProject: vi.fn().mockResolvedValue(undefined),
    api: {
      ...actual.api,
      getProjectRuntime: vi.fn().mockResolvedValue({
        project_id: "project-1",
        status: "idle",
        port: null,
        url: null,
        message: "Preview runtime not started.",
        logs: [],
        updated_at: 1,
      }),
      startProjectRuntime: vi.fn().mockResolvedValue({
        project_id: "project-1",
        status: "installing",
        port: 3100,
        url: "http://127.0.0.1:3100",
        message: "Installing npm dependencies…",
        logs: ["$ npm install"],
        updated_at: 2,
      }),
      stopProjectRuntime: vi.fn().mockResolvedValue({
        project_id: "project-1",
        status: "stopped",
        port: null,
        url: null,
        message: "Preview stopped.",
        logs: [],
        updated_at: 3,
      }),
    },
  };
});

function seedFiles() {
  useProjectStore.setState({
    projectStack: "static",
    files: [
      { file_path: "index.html", content: "<html><head></head><body>Hello</body></html>" },
      { file_path: "styles.css", content: "body{color:red}" },
      { file_path: "app.js", content: "console.log('x')" },
    ],
  });
}

function seedNextFiles() {
  useProjectStore.setState({
    projectStack: "nextjs",
    files: [
      { file_path: "package.json", content: '{"name":"demo","scripts":{"dev":"next dev"}}' },
      { file_path: "app/page.tsx", content: "export default function Page(){return <main>Hi</main>}" },
      { file_path: "app/layout.tsx", content: "export default function Root({children}:{children:React.ReactNode}){return children}" },
    ],
  });
}

describe("PreviewPanel extended", () => {
  it("renders export button when project id is provided", async () => {
    const user = userEvent.setup();
    const { downloadProject } = await import("@/lib/api");
    seedFiles();
    render(<PreviewPanel projectId="project-1" />);
    await user.click(screen.getByRole("button", { name: "Download project ZIP" }));
    expect(downloadProject).toHaveBeenCalledWith("project-1");
  });

  it("resets export state after a failed download", async () => {
    const user = userEvent.setup();
    const { downloadProject } = await import("@/lib/api");
    vi.mocked(downloadProject).mockRejectedValueOnce(new Error("Export failed"));
    seedFiles();
    render(<PreviewPanel projectId="project-1" />);
    await user.click(screen.getByRole("button", { name: "Download project ZIP" }));
    expect(await screen.findByRole("button", { name: "Download project ZIP" })).toBeInTheDocument();
  });

  it("disables export while a download is in progress", async () => {
    const user = userEvent.setup();
    const { downloadProject } = await import("@/lib/api");
    vi.mocked(downloadProject).mockImplementation(() => new Promise(() => {}));
    seedFiles();
    render(<PreviewPanel projectId="project-1" />);
    const button = screen.getByRole("button", { name: "Download project ZIP" });
    await user.click(button);
    expect(await screen.findByText("Exporting...")).toBeInTheDocument();
    expect(button).toBeDisabled();
    expect(downloadProject).toHaveBeenCalledTimes(1);
  });

  it("hides export button when project id is absent", () => {
    seedFiles();
    render(<PreviewPanel />);
    expect(screen.queryByRole("button", { name: "Download project ZIP" })).not.toBeInTheDocument();
  });

  it("switches to the files tab and shows file list with sizes", async () => {
    const user = userEvent.setup();
    seedFiles();
    render(<PreviewPanel />);
    await user.click(screen.getByRole("button", { name: /File/ }));
    expect(screen.getByText("index.html")).toBeInTheDocument();
    expect(screen.getByText("styles.css")).toBeInTheDocument();
    expect(screen.getByText("app.js")).toBeInTheDocument();
    expect(screen.getByText("data / chats /")).toBeInTheDocument();
  });

  it("clicking a file in the files tab switches to code view", async () => {
    const user = userEvent.setup();
    seedFiles();
    render(<PreviewPanel />);
    await user.click(screen.getByRole("button", { name: /File/ }));
    await user.click(screen.getByText("app.js"));
    expect(screen.getByText("console.log('x')")).toBeInTheDocument();
  });

  it("switches to the console tab and shows empty state", async () => {
    const user = userEvent.setup();
    seedFiles();
    render(<PreviewPanel />);
    await user.click(screen.getByRole("button", { name: /Console/ }));
    expect(screen.getByText("No console output yet.")).toBeInTheDocument();
  });

  it("captures console messages from iframe postMessage", async () => {
    const user = userEvent.setup();
    seedFiles();
    render(<PreviewPanel />);

    act(() => {
      window.dispatchEvent(
        new MessageEvent("message", {
          origin: "null",
          data: { source: "neutron-preview", type: "console", level: "error", message: "ReferenceError: foo" },
        })
      );
    });

    await user.click(screen.getByRole("button", { name: /Console/ }));
    expect(screen.getByText("ReferenceError: foo")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
  });

  it("clears console entries", async () => {
    const user = userEvent.setup();
    seedFiles();
    render(<PreviewPanel />);

    act(() => {
      window.dispatchEvent(
        new MessageEvent("message", {
          origin: "null",
          data: { source: "neutron-preview", type: "console", level: "warn", message: "warning" },
        })
      );
    });

    await user.click(screen.getByRole("button", { name: /Console/ }));
    expect(screen.getByText("warning")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Clear/ }));
    expect(screen.getByText("No console output yet.")).toBeInTheDocument();
  });

  it("resolves console error by calling onSendMessage", async () => {
    const user = userEvent.setup();
    const onSendMessage = vi.fn();
    seedFiles();
    render(<PreviewPanel onSendMessage={onSendMessage} />);

    act(() => {
      window.dispatchEvent(
        new MessageEvent("message", {
          origin: "null",
          data: { source: "neutron-preview", type: "console", level: "error", message: "TypeError" },
        })
      );
    });

    await user.click(screen.getByRole("button", { name: /Console/ }));
    await user.hover(screen.getByText("TypeError"));
    await user.click(screen.getByRole("button", { name: /Resolve/ }));
    expect(onSendMessage).toHaveBeenCalledWith(
      expect.stringContaining('@engineer Fix this console error in the generated code: "TypeError"'),
    );
  });

  it("toggles select mode and handles element selection", async () => {
    const user = userEvent.setup();
    const onSendMessage = vi.fn();
    seedFiles();
    render(<PreviewPanel onSendMessage={onSendMessage} />);

    await user.click(screen.getByRole("button", { name: /Select to edit/ }));
    expect(screen.getByText("Selecting...")).toBeInTheDocument();
    expect(screen.getByText(/Click any element in the preview/)).toBeInTheDocument();

    act(() => {
      window.dispatchEvent(
        new MessageEvent("message", {
          origin: "null",
          data: {
            source: "neutron-preview",
            type: "element-selected",
            tag: "h1",
            text: "Hello World",
            selector: "h1.title",
          },
        })
      );
    });

    expect(screen.getByText("<h1>")).toBeInTheDocument();
    expect(screen.getByText("Hello World")).toBeInTheDocument();
    expect(screen.getByText("Edit with Ravi")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Make this more prominent" }));
    expect(onSendMessage).toHaveBeenCalledWith(expect.stringContaining("@engineer Modify the <h1> element"));
    expect(onSendMessage).toHaveBeenCalledWith(expect.stringContaining("Make this more prominent"));
  });

  it("applies a custom select-to-edit instruction", async () => {
    const user = userEvent.setup();
    const onSendMessage = vi.fn();
    seedFiles();
    render(<PreviewPanel onSendMessage={onSendMessage} />);

    await user.click(screen.getByRole("button", { name: /Select to edit/ }));
    act(() => {
      window.dispatchEvent(
        new MessageEvent("message", {
          origin: "null",
          data: {
            source: "neutron-preview",
            type: "element-selected",
            tag: "button",
            text: "Save",
            selector: "button.primary",
          },
        }),
      );
    });

    await user.type(
      screen.getByLabelText("Describe the change for the selected element"),
      "Change the label to Confirm",
    );
    await user.click(screen.getByRole("button", { name: /Apply edit/ }));
    expect(onSendMessage).toHaveBeenCalledWith(expect.stringContaining("Change the label to Confirm"));
    expect(onSendMessage).toHaveBeenCalledWith(expect.stringContaining("<button>"));
  });

  it("deselects select mode and clears selection", async () => {
    const user = userEvent.setup();
    seedFiles();
    render(<PreviewPanel />);

    await user.click(screen.getByRole("button", { name: /Select to edit/ }));
    expect(screen.getByText("Selecting...")).toBeInTheDocument();
    await user.click(screen.getByText("Selecting..."));
    expect(screen.getByText("Select to edit")).toBeInTheDocument();
  });

  it("opens preview in new window", async () => {
    const user = userEvent.setup();
    seedFiles();
    const mockOpen = vi.fn();
    const blobUrl = "blob:mock";
    vi.spyOn(window, "open").mockImplementation(mockOpen);
    vi.spyOn(URL, "createObjectURL").mockReturnValue(blobUrl);
    vi.spyOn(URL, "revokeObjectURL").mockReturnValue(undefined);

    render(<PreviewPanel />);
    await user.click(screen.getByRole("button", { name: /Open/ }));
    expect(mockOpen).toHaveBeenCalledWith(blobUrl, "_blank", "noopener,noreferrer");
  });

  it("handles open preview when window.open returns null", async () => {
    const user = userEvent.setup();
    seedFiles();
    vi.spyOn(window, "open").mockReturnValue(null);
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:mock");
    render(<PreviewPanel />);
    await user.click(screen.getByRole("button", { name: /Open/ }));
  });

  it("ignores messages from non-neutron sources", () => {
    seedFiles();
    render(<PreviewPanel />);
    act(() => {
      window.dispatchEvent(
        new MessageEvent("message", {
          data: { source: "other", type: "console", level: "error", message: "nope" },
        })
      );
    });
  });

  it("shows error badge count on console tab", () => {
    seedFiles();
    render(<PreviewPanel />);
    act(() => {
      window.dispatchEvent(
        new MessageEvent("message", {
          origin: "null",
          data: { source: "neutron-preview", type: "console", level: "error", message: "err1" },
        })
      );
      window.dispatchEvent(
        new MessageEvent("message", {
          origin: "null",
          data: { source: "neutron-preview", type: "console", level: "error", message: "err2" },
        })
      );
    });
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("shows complete status without working indicator", () => {
    useProjectStore.setState({ projectStatus: "complete" });
    render(<PreviewPanel />);
    expect(screen.getByText("Generating files... Preview will appear soon.")).toBeInTheDocument();
    expect(screen.queryByText("Agents are working...")).not.toBeInTheDocument();
  });

  it("shows Next.js live preview controls and starts runtime", async () => {
    const user = userEvent.setup();
    const { api } = await import("@/lib/api");
    let started = false;
    vi.mocked(api.getProjectRuntime).mockImplementation(async () =>
      started
        ? {
            project_id: "project-1",
            status: "installing" as const,
            port: 3100,
            url: "http://127.0.0.1:3100",
            message: "Installing npm dependencies…",
            logs: ["$ npm install"],
            updated_at: 2,
          }
        : {
            project_id: "project-1",
            status: "idle" as const,
            port: null,
            url: null,
            message: "Preview runtime not started.",
            logs: [],
            updated_at: 1,
          },
    );
    vi.mocked(api.startProjectRuntime).mockImplementation(async () => {
      started = true;
      return {
        project_id: "project-1",
        status: "installing",
        port: 3100,
        url: "http://127.0.0.1:3100",
        message: "Installing npm dependencies…",
        logs: ["$ npm install"],
        updated_at: 2,
      };
    });

    seedNextFiles();
    render(<PreviewPanel projectId="project-1" />);

    expect(await screen.findByText("Next.js live preview")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Select to edit/ })).not.toBeInTheDocument();
    await expect.poll(() => vi.mocked(api.getProjectRuntime).mock.calls.length).toBeGreaterThan(0);

    const pollsBeforeStart = vi.mocked(api.getProjectRuntime).mock.calls.length;
    await user.click(screen.getByRole("button", { name: /Start Next.js preview/ }));
    expect(api.startProjectRuntime).toHaveBeenCalledWith("project-1");
    expect(await screen.findByText("Installing npm dependencies…")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Installing/ })).toBeDisabled();
    // Poll loop must restart after Start (idle poll only runs once).
    await expect
      .poll(() => vi.mocked(api.getProjectRuntime).mock.calls.length)
      .toBeGreaterThan(pollsBeforeStart);
  });

  it("embeds ready Next.js runtime URL in iframe", async () => {
    const { api } = await import("@/lib/api");
    vi.mocked(api.getProjectRuntime).mockResolvedValue({
      project_id: "project-1",
      status: "ready",
      port: 3100,
      url: "http://127.0.0.1:3100",
      message: "Preview ready",
      logs: ["Ready"],
      updated_at: 5,
    });
    seedNextFiles();
    render(<PreviewPanel projectId="project-1" />);

    const frame = await screen.findByTitle("Next.js preview");
    expect(frame).toHaveAttribute("src", "http://127.0.0.1:3100");
    expect(screen.queryByRole("button", { name: /Select to edit/ })).not.toBeInTheDocument();
  });

  it("keeps polling while install status advances after start", async () => {
    const user = userEvent.setup();
    const { api } = await import("@/lib/api");
    let started = false;
    let postStartPolls = 0;
    vi.mocked(api.getProjectRuntime).mockImplementation(async () => {
      if (!started) {
        return {
          project_id: "project-1",
          status: "idle" as const,
          port: null,
          url: null,
          message: "Preview runtime not started.",
          logs: [],
          updated_at: 1,
        };
      }
      postStartPolls += 1;
      if (postStartPolls < 2) {
        return {
          project_id: "project-1",
          status: "installing" as const,
          port: 3100,
          url: "http://127.0.0.1:3100",
          message: "npm install still running… 5s elapsed",
          logs: ["$ npm install", "… still working (5s)"],
          updated_at: 2,
        };
      }
      return {
        project_id: "project-1",
        status: "ready" as const,
        port: 3100,
        url: "http://127.0.0.1:3100",
        message: "Preview ready",
        logs: ["Ready"],
        updated_at: 3,
      };
    });
    vi.mocked(api.startProjectRuntime).mockImplementation(async () => {
      started = true;
      return {
        project_id: "project-1",
        status: "installing",
        port: 3100,
        url: "http://127.0.0.1:3100",
        message: "Installing npm dependencies…",
        logs: [],
        updated_at: 2,
      };
    });

    seedNextFiles();
    render(<PreviewPanel projectId="project-1" />);
    await user.click(await screen.findByRole("button", { name: /Start Next.js preview/ }));
    expect(await screen.findByTitle("Next.js preview", {}, { timeout: 5000 })).toHaveAttribute(
      "src",
      "http://127.0.0.1:3100",
    );
  });
});
