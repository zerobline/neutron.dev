import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AgentStatusBar } from "@/components/workspace/agent-status";
import { ArtifactCard } from "@/components/workspace/artifact-card";
import { ChatPanel } from "@/components/workspace/chat-panel";
import { CodeViewer, getLanguage } from "@/components/workspace/code-viewer";
import { FeedbackPanel } from "@/components/workspace/feedback-panel";
import { MessageBubble } from "@/components/workspace/message-bubble";
import { ThinkingIndicator } from "@/components/workspace/thinking-indicator";
import { PreviewPanel } from "@/components/workspace/preview-panel";
import { SplitPane } from "@/components/workspace/split-pane";
import { UsageSummary } from "@/components/workspace/usage-summary";
import { ActivityPanel } from "@/components/workspace/activity-panel";
import { LiveSession } from "@/components/workspace/live-session";
import { useProjectStore } from "@/stores/project-store";
import type { AgentName, AgentStatus } from "@/types";

function seedFiles() {
  useProjectStore.setState({
    files: [
      { file_path: "index.html", content: "<html><head></head><body>Hello</body></html>" },
      { file_path: "styles.css", content: "body{color:red}" },
      { file_path: "app.js", content: "console.log('x')" },
      { file_path: "big.json", content: "x".repeat(2048) },
    ],
  });
}

describe("workspace components", () => {
  it("renders agent statuses with phase and fallbacks", () => {
    const agents: AgentStatus[] = [{ agent: "engineer", status: "working", currentTask: "Build" }];
    useProjectStore.setState({ currentPhase: "planning", agents });
    render(<AgentStatusBar />);
    expect(screen.getByText("Planning")).toBeInTheDocument();
    expect(screen.getByText("Ravi")).toBeInTheDocument();
    expect(screen.getByText("Working")).toBeInTheDocument();
    expect(screen.getAllByText("Idle").length).toBeGreaterThan(0);
  });

  it("renders failed agent status with task context", () => {
    const agents: AgentStatus[] = [{ agent: "product_manager", status: "error", currentTask: "Failed during planning" }];
    useProjectStore.setState({ buildMode: "team", agents });
    render(<AgentStatusBar />);
    expect(screen.getByText("Nina")).toBeInTheDocument();
    expect(screen.getByText("Failed")).toBeInTheDocument();
    expect(screen.getByText("Failed during planning")).toBeInTheDocument();
  });

  it("maps code languages and renders line numbers", () => {
    expect(getLanguage("index.html")).toBe("markup");
    expect(getLanguage("style.css")).toBe("css");
    expect(getLanguage("app.js")).toBe("javascript");
    expect(getLanguage("app.jsx")).toBe("jsx");
    expect(getLanguage("app.ts")).toBe("typescript");
    expect(getLanguage("app.tsx")).toBe("tsx");
    expect(getLanguage("data.json")).toBe("json");
    expect(getLanguage("README.md")).toBe("markdown");
    expect(getLanguage("main.py")).toBe("python");
    expect(getLanguage("unknown.bin")).toBe("markup");
    expect(getLanguage("Makefile")).toBe("markup");
    render(<CodeViewer code={"one\ntwo"} language="javascript" />);
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("two")).toBeInTheDocument();
  });

  it("expands artifact cards, previews HTML, switches to code, and collapses", async () => {
    const user = userEvent.setup();
    seedFiles();
    render(<ArtifactCard filePath="index.html" />);
    await user.click(screen.getByRole("button", { name: /index.html/ }));
    const frame = screen.getByTitle("Preview index.html");
    expect(frame).toHaveAttribute("srcDoc", expect.stringContaining("<style>body{color:red}</style>"));
    expect(frame).toHaveAttribute("srcDoc", expect.stringContaining("<script>console.log('x')</script>"));
    await user.click(screen.getByRole("button", { name: "Code" }));
    expect(screen.getByText(/Hello/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Preview" }));
    expect(screen.getByTitle("Preview index.html")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Close index.html" }));
    expect(screen.getByRole("button", { name: /index.html/ })).toBeInTheDocument();
  });

  it("renders artifact fallback extension and asset injection branches", async () => {
    const user = userEvent.setup();
    useProjectStore.setState({ files: [
      { file_path: "Makefile", content: "build:" },
      { file_path: "index.html", content: "<html><head></head><body></body></html>" },
    ] });
    const { unmount } = render(<ArtifactCard filePath="Makefile" />);
    await user.click(screen.getByRole("button", { name: /Makefile/ }));
    expect(screen.getByText("build:")).toBeInTheDocument();
    unmount();

    render(<ArtifactCard filePath="index.html" />);
    await user.click(screen.getByRole("button", { name: /index.html/ }));
    expect(screen.getByTitle("Preview index.html")).toHaveAttribute("srcDoc", expect.stringContaining("</body>"));
  });

  it("inlines external assets for generated html previews", async () => {
    const user = userEvent.setup();
    useProjectStore.setState({ files: [
      { file_path: "index.html", content: '<html><head><link rel="stylesheet" href="./styles.css"></head><body><script src="./app.js"></script></body></html>' },
      { file_path: "styles.css", content: "body{color:blue}" },
      { file_path: "app.js", content: "window.APP = true" },
    ] });
    render(<ArtifactCard filePath="index.html" />);
    await user.click(screen.getByRole("button", { name: /index.html/ }));
    const frame = screen.getByTitle("Preview index.html");
    expect(frame).toHaveAttribute("srcDoc", expect.stringContaining("<style>body{color:blue}</style>"));
    expect(frame).toHaveAttribute("srcDoc", expect.stringContaining("<script>window.APP = true</script>"));
    expect(frame).not.toHaveAttribute("srcDoc", expect.stringContaining('href="./styles.css"'));
  });

  it("renders non-HTML artifact code, large sizes, missing files, and avoids duplicate injection", async () => {
    const user = userEvent.setup();
    useProjectStore.setState({ files: [
      { file_path: "index.html", content: "<html><head><style>old</style></head><body><script>old</script></body></html>" },
      { file_path: "big.json", content: "x".repeat(2048) },
      { file_path: "styles.css", content: "new" },
      { file_path: "app.js", content: "new" },
    ] });
    const { rerender, unmount } = render(<ArtifactCard filePath="missing.ts" />);
    expect(document.body).toBeInTheDocument();
    rerender(<ArtifactCard filePath="big.json" />);
    expect(screen.getByText("2.0 KB")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /big.json/ }));
    expect(screen.getByText("x".repeat(2048))).toBeInTheDocument();
    unmount();
    render(<ArtifactCard filePath="index.html" />);
    await user.click(screen.getByRole("button", { name: /index.html/ }));
    expect(screen.getByTitle("Preview index.html")).toHaveAttribute("srcDoc", expect.stringContaining("<style>new</style>"));
    expect(screen.getByTitle("Preview index.html")).toHaveAttribute("srcDoc", expect.stringContaining("<script>new</script>"));
  });

  it("handles feedback approve, revision, cancel, unknown phase and missing agent", async () => {
    const user = userEvent.setup();
    const onFeedback = vi.fn();
    const { rerender } = render(<FeedbackPanel onFeedback={onFeedback} />);
    expect(screen.queryByText(/Review/)).not.toBeInTheDocument();

    useProjectStore.setState({ pendingFeedback: { phase: "leading", agent: "team_leader", content: "Output", message: "Review it" } });
    rerender(<FeedbackPanel onFeedback={onFeedback} />);
    await user.click(screen.getByRole("button", { name: /Approve/ }));
    expect(onFeedback).toHaveBeenCalledWith("approve");

    useProjectStore.setState({ pendingFeedback: { phase: "weird", agent: "engineer", content: "Output", message: "Review it" } });
    rerender(<FeedbackPanel onFeedback={onFeedback} />);
    expect(screen.getByText("weird Review")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Request Revision/ }));
    expect(screen.getByRole("button", { name: /Send Revision/ })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: /Send Revision/ }));
    expect(onFeedback).not.toHaveBeenCalledWith("revise", "");
    await user.type(screen.getByPlaceholderText(/Describe what/), "  Fix it  ");
    await user.click(screen.getByRole("button", { name: /Send Revision/ }));
    expect(onFeedback).toHaveBeenCalledWith("revise", "Fix it");

    useProjectStore.setState({ pendingFeedback: { phase: "building", agent: "ghost" as AgentName, content: "Output", message: "Review it" } });
    rerender(<FeedbackPanel onFeedback={onFeedback} />);
    expect(screen.getByText("has finished — review before continuing")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Request Revision/ }));
    await user.type(screen.getByPlaceholderText(/Describe what/), "Nope");
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByPlaceholderText(/Describe what/)).not.toBeInTheDocument();
  });

  it("handles chat empty state, submit modes, keyboard, and feedback panel", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    const onStartBuild = vi.fn();
    const onFeedback = vi.fn();
    const onResumeBuild = vi.fn();
    const { rerender } = render(<ChatPanel projectId="project-1" onSend={onSend} onStartBuild={onStartBuild} onResumeBuild={onResumeBuild} onFeedback={onFeedback} projectDescription="Build desc" />);
    await user.click(screen.getByRole("button", { name: "Start Building" }));
    expect(onStartBuild).toHaveBeenCalledWith("Build desc");
    expect(screen.getByRole("button", { name: "Send message" })).toBeDisabled();

    await user.type(screen.getByPlaceholderText(/Describe what/), "  Make app  ");
    await user.click(screen.getByRole("button", { name: "Send message" }));
    expect(onStartBuild).toHaveBeenCalledWith("Make app");

    useProjectStore.setState({ projectStatus: "building", messages: [{ id: "m1", role: "system", content: "Hi", timestamp: 1 }] });
    rerender(<ChatPanel projectId="project-1" onSend={onSend} onStartBuild={onStartBuild} onResumeBuild={onResumeBuild} onFeedback={onFeedback} projectDescription="Build desc" />);
    await user.type(screen.getByPlaceholderText("Send a message..."), "Hello{shift>}{enter}{/shift}there");
    expect(onSend).not.toHaveBeenCalled();
    fireEvent.keyDown(screen.getByPlaceholderText("Send a message..."), { key: "Enter" });
    expect(onSend).toHaveBeenCalledWith("Hello\nthere");

    useProjectStore.setState({ pendingFeedback: { phase: "planning", agent: "product_manager", content: "Plan", message: "Review" } });
    rerender(<ChatPanel projectId="project-1" onSend={onSend} onStartBuild={onStartBuild} onResumeBuild={onResumeBuild} onFeedback={onFeedback} projectDescription="Build desc" />);
    await user.click(screen.getByRole("button", { name: /Approve/ }));
    expect(onFeedback).toHaveBeenCalledWith("approve");

    useProjectStore.setState({ projectStatus: "complete", pendingFeedback: null });
    rerender(<ChatPanel projectId="project-1" onSend={onSend} onStartBuild={onStartBuild} onResumeBuild={onResumeBuild} onFeedback={onFeedback} projectDescription="Build desc" />);
    expect(screen.getByText("Build complete")).toBeInTheDocument();
    expect(screen.getByText("Try next")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Fill with mock data/i })).toBeInTheDocument();
  });

  it("renders message bubble variants", () => {
    useProjectStore.setState({ files: [{ file_path: "created.html", content: "<html><head></head><body></body></html>" }] });
    const long = "a".repeat(1501);
    const { rerender } = render(<MessageBubble message={{ id: "s", role: "system", content: "Created file: created.html", timestamp: 1 }} />);
    expect(screen.getByRole("button", { name: /created.html/ })).toBeInTheDocument();
    rerender(<MessageBubble message={{ id: "s2", role: "system", content: "System note", timestamp: 1 }} />);
    expect(screen.getByText("System note")).toBeInTheDocument();
    rerender(<MessageBubble message={{ id: "u", role: "user", content: "User note", timestamp: 1 }} />);
    expect(screen.getByText("User note")).toBeInTheDocument();
    rerender(<MessageBubble message={{ id: "a", role: "agent", agent: "engineer", content: "**Bold**", timestamp: 1 }} />);
    expect(screen.getByText("Ravi — Software Engineer")).toBeInTheDocument();
    expect(screen.getByText("Bold")).toBeInTheDocument();
    rerender(<MessageBubble message={{ id: "a2", role: "agent", content: long, timestamp: 1 }} />);
    expect(screen.getByText(/\.\.\./)).toBeInTheDocument();
    expect(screen.getByText("Show full output")).toBeInTheDocument();
  });

  it("expands and collapses long agent messages", async () => {
    const user = userEvent.setup();
    const long = "a".repeat(1501);
    render(<MessageBubble message={{ id: "long", role: "agent", agent: "engineer", content: long, timestamp: 1 }} />);
    expect(screen.getByText("Show full output")).toBeInTheDocument();
    await user.click(screen.getByText("Show full output"));
    expect(screen.getByText("Show less")).toBeInTheDocument();
    await user.click(screen.getByText("Show less"));
    expect(screen.getByText("Show full output")).toBeInTheDocument();
  });

  it("does not render legacy raw thinking messages", () => {
    const { container, rerender } = render(<MessageBubble message={{
      id: "think1",
      role: "agent",
      agent: "engineer",
      kind: "thinking",
      content: "Analyzing the code structure\nLooking at patterns",
      timestamp: 1,
    }} />);
    expect(container).toBeEmptyDOMElement();
    rerender(<MessageBubble message={{
      id: "think2",
      role: "agent",
      agent: "engineer",
      kind: "thinking",
      content: "\n\n",
      timestamp: 1,
    }} />);
    expect(container).toBeEmptyDOMElement();
    rerender(<MessageBubble message={{
      id: "think3",
      role: "agent",
      kind: "thinking",
      content: "No agent thinking",
      timestamp: 1,
    }} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders thinking indicator when agents are thinking", async () => {
    const user = userEvent.setup();
    const thinkingMap = new Map();
    thinkingMap.set("engineer", {
      agent: "engineer",
      content: "Reviewing the implementation",
      stream: "Considering navigation handlers",
      timestamp: 1,
    });
    useProjectStore.setState({ thinkingMessages: thinkingMap });
    render(<ThinkingIndicator />);
    expect(screen.getByText("Ravi")).toBeInTheDocument();
    expect(screen.getByText("Software Engineer")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Reviewing the implementation");
    expect(screen.getByText("Reasoning")).toBeInTheDocument();
    // Stream is expanded by default for a Manus-style live transcript.
    expect(screen.getByText("Considering navigation handlers")).toBeInTheDocument();
    await user.click(screen.getByText("Reasoning"));
    // Collapsed: full stream leaves the pre; preview line-clamp still shows text.
    expect(screen.getByText("Considering navigation handlers")).toBeInTheDocument();
  });

  it("hides raw json thinking streams", () => {
    const thinkingMap = new Map();
    thinkingMap.set("product_manager", {
      agent: "product_manager",
      content: "Defining product scope",
      stream: '{"headline":"Plan","summary":"json stream"}',
      timestamp: 1,
    });
    useProjectStore.setState({ thinkingMessages: thinkingMap });
    render(<ThinkingIndicator />);
    expect(screen.getByText("Defining product scope")).toBeInTheDocument();
    expect(screen.queryByText("Reasoning")).not.toBeInTheDocument();
  });

  it("renders structured phase result cards", async () => {
    const user = userEvent.setup();
    render(
      <MessageBubble
        message={{
          id: "phase-1",
          role: "agent",
          agent: "product_manager",
          content: "A focused portfolio plan.",
          timestamp: 1,
          kind: "phase_result",
          phaseResult: {
            id: "phase-1",
            phase: "planning",
            agent: "product_manager",
            kind: "plan",
            headline: "Portfolio plan",
            summary: "A focused portfolio plan.",
            hasStructuredSpec: true,
            timestamp: 1,
            spec: {
              mvp_features: ["Hero section"],
              milestones: ["Ship landing page"],
              pages: [{ name: "Home", purpose: "Landing", key_elements: ["Hero"] }],
            },
          },
        }}
      />
    );
    expect(screen.getByText("Portfolio plan")).toBeInTheDocument();
    expect(screen.getByText("A focused portfolio plan.")).toBeInTheDocument();
    expect(screen.getByText("Plan")).toBeInTheDocument();
    expect(screen.getByText("features")).toBeInTheDocument();
    expect(screen.getByText("pages")).toBeInTheDocument();
    expect(screen.queryByText("Hero section")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Details/i }));
    expect(screen.getByText("Hero section")).toBeInTheDocument();
    expect(screen.getByText("Home")).toBeInTheDocument();
  });

  it("renders metrics for brief, analysis, architecture, and build phase cards", async () => {
    const user = userEvent.setup();
    const { PhaseResultCard } = await import("@/components/workspace/phase-result-card");
    const cases = [
      {
        kind: "brief" as const,
        agent: "team_leader" as const,
        headline: "Brief card",
        summaryExtra: "word ".repeat(80),
        spec: {
          target_users: ["Founders"],
          mvp_inclusions: ["Landing", "Auth", "Billing", "Settings", "Reports", "Exports"],
          success_criteria: ["Demo ready"],
          assumptions: ["Static only"],
        },
        metrics: ["users", "MVP items", "criteria"],
        detail: "Landing",
        expandMore: true,
      },
      {
        kind: "analysis" as const,
        agent: "data_scientist" as const,
        headline: "Analysis card",
        spec: {
          recommendations: [
            "Keep the app static and avoid server-side frameworks entirely for MVP delivery",
            "Prefer progressive enhancement and accessible controls across all pages",
            "Ship a short onboarding walkthrough before the main dashboard",
            "Document data assumptions clearly for downstream engineering work",
            "Leave room for future API integrations without rewriting the UI shell",
            "Short",
          ],
          risks: ["Scope"],
          workflows: ["Browse"],
          evidence_gaps: ["Pricing"],
        },
        metrics: ["recs", "risks"],
        detail: "Keep the app static and avoid server-side frameworks entirely for MVP delivery",
        expandMore: true,
      },
      {
        kind: "architecture" as const,
        agent: "architect" as const,
        headline: "Architecture card",
        spec: {
          components: ["Header"],
          required_files: ["index.html", "styles.css", "app.js"],
          client_side_behavior: ["Tabs"],
          color_palette: {
            primary: "#111111",
            secondary: "#222222",
            accent: "#333333",
            background: "#ffffff",
            text: "#000000",
          },
        },
        metrics: ["components", "files"],
        detail: "Header",
      },
      {
        kind: "build" as const,
        agent: "engineer" as const,
        headline: "Build card",
        spec: {
          files_written: ["index.html"],
          behaviors_implemented: ["Tabs"],
          known_gaps: [],
        },
        metrics: ["files", "behaviors"],
        detail: "index.html",
      },
      {
        kind: "markdown" as const,
        agent: "engineer" as const,
        headline: "Markdown card",
        spec: { note: "generic" },
        metrics: [] as string[],
        detail: "generic" as string | null,
      },
    ];

    for (const item of cases) {
      const { unmount } = render(
        <PhaseResultCard
          result={{
            id: item.kind,
            phase: item.kind,
            agent: item.agent,
            kind: item.kind,
            headline: item.headline,
            summary: `${item.headline} summary${"summaryExtra" in item ? item.summaryExtra : ""}`,
            hasStructuredSpec: true,
            timestamp: 1,
            spec: item.spec,
          }}
        />,
      );
      expect(screen.getByText(item.headline)).toBeInTheDocument();
      for (const metric of item.metrics) {
        expect(screen.getByText(metric)).toBeInTheDocument();
      }
      if (item.detail || item.kind === "markdown") {
        await user.click(screen.getByRole("button", { name: /Details/i }));
        if (item.detail && item.kind !== "markdown") {
          expect(screen.getByText(item.detail)).toBeInTheDocument();
        }
        if ("expandMore" in item && item.expandMore) {
          const more = screen.getByRole("button", { name: /Show \d+ more/i });
          await user.click(more);
          expect(screen.getByRole("button", { name: /Show less/i })).toBeInTheDocument();
          await user.click(screen.getByRole("button", { name: /Show less/i }));
        }
        if (item.kind === "build") {
          await user.click(screen.getByRole("button", { name: /Known gaps/i }));
          expect(screen.getByText("No known gaps reported.")).toBeInTheDocument();
        }
      }
      unmount();
    }
  });

  it("hides thinking indicator when no agents are thinking", () => {
    useProjectStore.setState({ thinkingMessages: new Map() });
    const { container } = render(<ThinkingIndicator />);
    expect(container.innerHTML).toBe("");
  });

  it("skips rendering thinking indicator for unknown agent", () => {
    const thinkingMap = new Map();
    thinkingMap.set("ghost" as AgentName, { agent: "ghost" as AgentName, content: "boo", timestamp: 1 });
    useProjectStore.setState({ thinkingMessages: thinkingMap });
    const { container } = render(<ThinkingIndicator />);
    expect(container.querySelector(".animate-slide-up")).not.toBeInTheDocument();
  });

  it("renders recent build activity, expands history, and redacts credential details", async () => {
    const user = userEvent.setup();
    useProjectStore.setState({
      activities: Array.from({ length: 9 }, (_, index) => ({
        id: `activity-${index}`,
        kind: index === 8 ? "tool" as const : "phase" as const,
        title: index === 8 ? "Search provider" : `Phase ${index + 1}`,
        summary: index === 8 ? "Checking search configuration" : undefined,
        details: index === 8 ? '{"api_key":"secret-value","query":"docs"}' : undefined,
        agent: index === 8 ? "engineer" as const : undefined,
        status: index === 8 ? "active" as const : "complete" as const,
        timestamp: index,
      })),
    });

    render(<ActivityPanel />);
    expect(screen.getByText("Build activity")).toBeInTheDocument();
    expect(screen.getByText(/Live execution updates/)).toBeInTheDocument();
    expect(screen.queryByText("Phase 1")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /1 earlier/ }));
    expect(screen.getByText("Phase 1")).toBeInTheDocument();
    await user.click(screen.getByText("View output"));
    expect(screen.getByText(/\[redacted\]/)).toBeInTheDocument();
    expect(screen.queryByText(/secret-value/)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Show recent/ }));
    expect(screen.queryByText("Phase 1")).not.toBeInTheDocument();
  });

  it("renders a unified live session shell with stream and timeline", () => {
    const thinkingMap = new Map();
    thinkingMap.set("engineer", {
      agent: "engineer",
      content: "Writing files",
      stream: "Planning index.html structure",
      timestamp: 1,
    });
    useProjectStore.setState({
      thinkingMessages: thinkingMap,
      currentPhase: "building",
      phasePercent: 80,
      projectStatus: "building",
      activities: [
        {
          id: "t1",
          kind: "tool",
          title: "Writing a project file",
          summary: "Wrote index.html",
          status: "complete",
          timestamp: 2,
          durationMs: 900,
          agent: "engineer",
        },
      ],
      agents: [
        { agent: "team_leader", status: "complete" },
        { agent: "product_manager", status: "complete" },
        { agent: "architect", status: "complete" },
        { agent: "engineer", status: "working", currentTask: "Writing files" },
        { agent: "data_scientist", status: "complete" },
      ],
    });
    render(<LiveSession />);
    expect(screen.getByLabelText("Live agent session")).toBeInTheDocument();
    expect(screen.getByText("Live session")).toBeInTheDocument();
    expect(screen.getByText(/Building/)).toBeInTheDocument();
    // Stats line sits in the Live Session shell header (not buried in the timeline).
    expect(screen.getByText(/Live execution updates · 1 tool/)).toBeInTheDocument();
    expect(screen.getByText("Planning index.html structure")).toBeInTheDocument();
    expect(screen.getByText("Writing a project file")).toBeInTheDocument();
  });

  it("hides live session when idle", () => {
    useProjectStore.setState({
      thinkingMessages: new Map(),
      activities: [],
      projectStatus: "created",
    });
    const { container } = render(<LiveSession />);
    expect(container).toBeEmptyDOMElement();
  });

  it("hides activity panel when no build events exist", () => {
    const { container } = render(<ActivityPanel />);
    expect(container).toBeEmptyDOMElement();
  });

  it("summarizes a single completed activity", () => {
    useProjectStore.setState({
      activities: [{ id: "only", kind: "phase", title: "Brief ready", status: "complete", timestamp: 1 }],
    });
    render(<ActivityPanel />);
    expect(screen.getByText("1 recorded update")).toBeInTheDocument();
  });

  it("pluralizes completed activity history", () => {
    useProjectStore.setState({
      activities: [
        { id: "one", kind: "phase", title: "Brief ready", status: "complete", timestamp: 1 },
        { id: "two", kind: "file", title: "File ready", status: "complete", timestamp: 2 },
      ],
    });
    render(<ActivityPanel />);
    expect(screen.getByText(/2 recorded updates/)).toBeInTheDocument();
    expect(screen.getByText(/1 file/)).toBeInTheDocument();
  });

  it("shows tool duration and verbose timestamps", async () => {
    const user = userEvent.setup();
    useProjectStore.setState({
      activities: [
        {
          id: "tool-1",
          kind: "tool",
          title: "Writing a project file",
          summary: "Wrote index.html",
          status: "complete",
          timestamp: Date.now() - 15_000,
          durationMs: 1250,
          agent: "engineer",
        },
      ],
    });
    render(<ActivityPanel />);
    expect(screen.getByText("1.3s")).toBeInTheDocument();
    expect(screen.getByText(/1 tool/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Verbose/i }));
    expect(screen.getByText(/15s ago|just now|s ago/)).toBeInTheDocument();
  });

  it("covers activity error states, multi-unit durations, and relative hours", async () => {
    const user = userEvent.setup();
    useProjectStore.setState({
      activities: [
        {
          id: "err",
          kind: "tool",
          title: "Writing a project file",
          summary: "Write failed",
          details: '{"path":"app.js"}',
          status: "error",
          timestamp: Date.now() - 4_000_000,
          durationMs: 65_000,
          agent: "engineer",
        },
        {
          id: "step-1",
          kind: "step",
          title: "Composing structured output",
          status: "complete",
          timestamp: Date.now() - 120_000,
        },
        {
          id: "file-1",
          kind: "file",
          title: "Created app.js",
          details: "app.js",
          status: "complete",
          timestamp: Date.now(),
        },
      ],
    });
    render(<ActivityPanel />);
    expect(screen.getByText(/1m 5s/)).toBeInTheDocument();
    expect(screen.getByText(/1 tools \(1 failed\)|1 tool/)).toBeInTheDocument();
    expect(screen.getByText(/1 step/)).toBeInTheDocument();
    expect(screen.getByText(/1 file/)).toBeInTheDocument();
    expect(screen.getByText("Failed", { selector: ".sr-only" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Verbose/i }));
    expect(screen.getByText(/h ago/)).toBeInTheDocument();
  });

  it("shows live session log mode when build is finished", () => {
    useProjectStore.setState({
      thinkingMessages: new Map(),
      projectStatus: "complete",
      currentPhase: "custom_phase",
      phasePercent: 100,
      activities: [
        {
          id: "done",
          kind: "phase",
          title: "Build complete",
          status: "complete",
          timestamp: 1,
        },
      ],
      agents: [
        { agent: "team_leader", status: "complete" },
        { agent: "product_manager", status: "complete" },
        { agent: "architect", status: "complete" },
        { agent: "engineer", status: "complete" },
        { agent: "data_scientist", status: "complete" },
      ],
    });
    render(<LiveSession />);
    expect(screen.getByText("Session log")).toBeInTheDocument();
    expect(screen.getByText("Complete")).toBeInTheDocument();
    expect(screen.queryByText("Custom_phase")).not.toBeInTheDocument();
    expect(screen.queryByText(/100%/)).not.toBeInTheDocument();
    expect(screen.getByText(/1 recorded update/)).toBeInTheDocument();
  });

  it("resolves live session agent from working status and activity history", () => {
    useProjectStore.setState({
      thinkingMessages: new Map(),
      projectStatus: "building",
      currentPhase: "building",
      phasePercent: 40,
      activities: [
        {
          id: "a1",
          kind: "tool",
          title: "Read Project File",
          status: "active",
          timestamp: Date.now() - 500,
          agent: "engineer",
        },
      ],
      agents: [
        { agent: "team_leader", status: "idle" },
        { agent: "product_manager", status: "idle" },
        { agent: "architect", status: "idle" },
        { agent: "engineer", status: "working", currentTask: "Reading files" },
        { agent: "data_scientist", status: "idle" },
      ],
    });
    const { unmount } = render(<LiveSession />);
    expect(screen.getByText("Live session")).toBeInTheDocument();
    expect(screen.getAllByText("Ravi").length).toBeGreaterThan(0);
    unmount();

    useProjectStore.setState({
      thinkingMessages: new Map(),
      projectStatus: "complete",
      // Stale phase/percent from the final building step must not show as "Building · 100%".
      currentPhase: "building",
      phasePercent: 100,
      activities: [
        {
          id: "a2",
          kind: "agent",
          title: "Focused edit",
          status: "complete",
          timestamp: 2,
          agent: "architect",
        },
      ],
      agents: [
        { agent: "team_leader", status: "idle" },
        { agent: "product_manager", status: "idle" },
        { agent: "architect", status: "idle" },
        { agent: "engineer", status: "idle" },
        { agent: "data_scientist", status: "idle" },
      ],
    });
    render(<LiveSession />);
    expect(screen.getByText("Session log")).toBeInTheDocument();
    expect(screen.getByText("Complete")).toBeInTheDocument();
    expect(screen.queryByText(/Building/)).not.toBeInTheDocument();
    expect(screen.getByText(/1 recorded update/)).toBeInTheDocument();
  });

  it("renders long reasoning streams with mask and embedded thinking", async () => {
    const user = userEvent.setup();
    const longStream = "x".repeat(320);
    const thinkingMap = new Map();
    thinkingMap.set("architect", {
      agent: "architect",
      content: "Designing layout",
      stream: longStream,
      timestamp: 1,
    });
    useProjectStore.setState({ thinkingMessages: thinkingMap });
    render(<ThinkingIndicator embedded />);
    expect(screen.getByText("Theo")).toBeInTheDocument();
    expect(document.querySelector(".stream-mask-top")).toBeTruthy();
    await user.click(screen.getByText("Reasoning"));
    expect(document.querySelector(".stream-mask-top")).toBeNull();
  });

  it("shows thinking without stream and resolves unknown live-session agents", () => {
    const thinkingMap = new Map();
    thinkingMap.set("engineer", {
      agent: "engineer",
      content: "Preparing the next step",
      timestamp: 1,
    });
    useProjectStore.setState({
      thinkingMessages: thinkingMap,
      projectStatus: "planning",
      currentPhase: "planning",
      phasePercent: 20,
      activities: [],
    });
    const { unmount } = render(<LiveSession />);
    expect(screen.getByText("Preparing the next step")).toBeInTheDocument();
    expect(screen.queryByText("Reasoning")).not.toBeInTheDocument();
    unmount();

    const ghostMap = new Map();
    ghostMap.set("ghost" as AgentName, {
      agent: "ghost" as AgentName,
      content: "unknown",
      timestamp: 1,
    });
    useProjectStore.setState({
      thinkingMessages: ghostMap,
      activities: [
        {
          id: "p1",
          kind: "phase",
          title: "Still moving",
          status: "complete",
          timestamp: 1,
        },
      ],
      projectStatus: "building",
      currentPhase: "building",
      phasePercent: 50,
      agents: [
        { agent: "team_leader", status: "idle" },
        { agent: "product_manager", status: "idle" },
        { agent: "architect", status: "idle" },
        { agent: "engineer", status: "idle" },
        { agent: "data_scientist", status: "idle" },
      ],
    });
    render(<LiveSession />);
    expect(screen.getByText("Build activity timeline")).toBeInTheDocument();
  });

  it("formats short and whole-minute tool durations", () => {
    useProjectStore.setState({
      activities: [
        {
          id: "ms",
          kind: "tool",
          title: "Quick Tool",
          status: "complete",
          timestamp: Date.now(),
          durationMs: 420,
        },
        {
          id: "min",
          kind: "tool",
          title: "Slow Tool",
          status: "complete",
          timestamp: Date.now(),
          durationMs: 120_000,
        },
        {
          id: "mid",
          kind: "tool",
          title: "Mid Tool",
          status: "complete",
          timestamp: Date.now(),
          durationMs: 15_000,
        },
        {
          id: "s1",
          kind: "step",
          title: "Step one",
          status: "active",
          timestamp: Date.now(),
        },
        {
          id: "s2",
          kind: "step",
          title: "Step two",
          status: "complete",
          timestamp: Date.now(),
        },
        {
          id: "f1",
          kind: "file",
          title: "Created a.js",
          status: "complete",
          timestamp: Date.now(),
        },
        {
          id: "f2",
          kind: "file",
          title: "Created b.js",
          status: "complete",
          timestamp: Date.now(),
        },
        {
          id: "ckpt",
          kind: "checkpoint",
          title: "Resumed from checkpoint",
          status: "complete",
          timestamp: Date.now(),
        },
      ],
    });
    render(<ActivityPanel />);
    expect(screen.getByText("420ms")).toBeInTheDocument();
    expect(screen.getByText("2m")).toBeInTheDocument();
    expect(screen.getByText("15s")).toBeInTheDocument();
    expect(screen.getByText(/3 tools/)).toBeInTheDocument();
    expect(screen.getByText(/2 steps/)).toBeInTheDocument();
    expect(screen.getByText(/2 files/)).toBeInTheDocument();
    expect(screen.getByText("Resumed from checkpoint")).toBeInTheDocument();
    expect(screen.getByText("In progress", { selector: ".sr-only" })).toBeInTheDocument();
  });

  it("ticks live tool duration while a tool is active", () => {
    vi.useFakeTimers();
    try {
      useProjectStore.setState({
        activities: [
          {
            id: "live-tool",
            kind: "tool",
            title: "Writing a project file",
            status: "active",
            timestamp: Date.now() - 2_500,
            agent: "engineer",
          },
          {
            id: "ghost-tool",
            kind: "agent",
            title: "Unknown agent work",
            status: "complete",
            timestamp: Date.now(),
            agent: "ghost" as AgentName,
          },
        ],
      });
      render(<ActivityPanel />);
      expect(screen.getByText("2.5s")).toBeInTheDocument();
      expect(screen.getByText("Unknown agent work")).toBeInTheDocument();
      act(() => {
        vi.advanceTimersByTime(1000);
      });
      // Interval tick re-renders with an updated live duration.
      expect(screen.getByText("Writing a project file")).toBeInTheDocument();
      expect(screen.getByText(/\d+(\.\d+)?s/)).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it("shows usage summary when build is complete with token data", () => {
    useProjectStore.setState({
      projectStatus: "complete",
      tokenUsage: { total_tokens: 12500, prompt_tokens: 8000, completion_tokens: 4500, successful_requests: 6 },
    });
    render(<UsageSummary />);
    expect(screen.getByText("12.5k tokens")).toBeInTheDocument();
    expect(screen.getByText("8.0k in")).toBeInTheDocument();
    expect(screen.getByText("4.5k out")).toBeInTheDocument();
    expect(screen.getByText("6 requests")).toBeInTheDocument();
  });

  it("shows live usage while a build is running", () => {
    useProjectStore.setState({ projectStatus: "building", currentPhase: "building", tokenUsage: { total_tokens: 100, prompt_tokens: 60, completion_tokens: 40, successful_requests: 1 } });
    const { container } = render(<UsageSummary />);
    expect(container).toHaveTextContent("100 tokens");
    expect(container).toHaveTextContent("Building · 82%");
  });

  it("shows completion progress without token data", () => {
    useProjectStore.setState({ projectStatus: "complete", tokenUsage: null });
    const { container } = render(<UsageSummary />);
    expect(container).toHaveTextContent("Complete");
    expect(container).not.toHaveTextContent("100%");
  });

  it("shows explicit zero usage when the provider reports it", () => {
    useProjectStore.setState({ projectStatus: "complete", tokenUsage: { total_tokens: 0, prompt_tokens: 0, completion_tokens: 0, successful_requests: 0 } });
    const { container } = render(<UsageSummary />);
    expect(container).toHaveTextContent("0 tokens");
  });

  it("formats large token counts with M suffix", () => {
    useProjectStore.setState({
      projectStatus: "complete",
      tokenUsage: { total_tokens: 1500000, prompt_tokens: 1000000, completion_tokens: 500, successful_requests: 10 },
    });
    render(<UsageSummary />);
    expect(screen.getByText("1.5M tokens")).toBeInTheDocument();
    expect(screen.getByText("1.0M in")).toBeInTheDocument();
    expect(screen.getByText("500 out")).toBeInTheDocument();
  });

  it("shows and hides output preview in feedback panel", async () => {
    const user = userEvent.setup();
    const onFeedback = vi.fn();
    useProjectStore.setState({ pendingFeedback: { phase: "planning", agent: "product_manager", content: "Full output here", message: "Review" } });
    render(<FeedbackPanel onFeedback={onFeedback} />);
    expect(screen.getByText("Show output")).toBeInTheDocument();
    expect(screen.queryByText("Full output here")).not.toBeInTheDocument();
    await user.click(screen.getByText("Show output"));
    expect(screen.getByText("Full output here")).toBeInTheDocument();
    expect(screen.getByText("Hide output")).toBeInTheDocument();
    await user.click(screen.getByText("Hide output"));
    expect(screen.queryByText("Full output here")).not.toBeInTheDocument();
  });

  it("previews structured feedback with unknown phase labels", async () => {
    const user = userEvent.setup();
    useProjectStore.setState({
      pendingFeedback: {
        phase: "custom_review",
        agent: "ghost" as AgentName,
        content: "from content field",
        message: "Review",
        headline: "Forced headline",
      },
    });
    render(<FeedbackPanel onFeedback={vi.fn()} />);
    expect(screen.getByText("custom_review Review")).toBeInTheDocument();
    expect(screen.getByText(/has finished — review before continuing/)).toBeInTheDocument();
    await user.click(screen.getByText("Show output"));
    // Headline + content (no summary) builds preview using content as summary.
    expect(screen.getByText("Forced headline")).toBeInTheDocument();
    expect(screen.getByText("from content field")).toBeInTheDocument();
  });

  it("renders phase cards without agent, summary, or details", async () => {
    const { PhaseResultCard } = await import("@/components/workspace/phase-result-card");
    render(
      <PhaseResultCard
        result={{
          id: "edge",
          phase: "building",
          agent: "ghost" as AgentName,
          kind: "not-a-kind" as never,
          headline: "",
          summary: "",
          hasStructuredSpec: false,
          timestamp: 1,
          spec: null,
        }}
      />,
    );
    expect(screen.getAllByText("Phase complete").length).toBeGreaterThan(0);
    expect(screen.getByText("Update")).toBeInTheDocument();
  });

  it("renders minimal build error cards", () => {
    render(<MessageBubble message={{
      id: "err-min",
      role: "system",
      kind: "error",
      content: "Something went wrong.",
      timestamp: 1,
    }} />);
    expect(screen.getByText("Build stopped")).toBeInTheDocument();
    expect(screen.getByText("Something went wrong.")).toBeInTheDocument();
    expect(screen.queryByText("Next:")).not.toBeInTheDocument();
  });

  it("renders structured build error cards", async () => {
    const user = userEvent.setup();
    render(<MessageBubble message={{
      id: "err",
      role: "system",
      kind: "error",
      agent: "product_manager",
      phase: "planning",
      category: "quota",
      content: "LLM provider quota reached.",
      details: "You've reached your usage limit for this billing cycle.",
      nextAction: "Switch provider/model in Settings.",
      timestamp: 1,
    }} />);
    expect(screen.getByText("Build stopped")).toBeInTheDocument();
    expect(screen.getByText("LLM provider quota reached.")).toBeInTheDocument();
    expect(screen.getByText("Nina")).toBeInTheDocument();
    expect(screen.getByText("planning")).toBeInTheDocument();
    expect(screen.getByText("quota")).toBeInTheDocument();
    expect(screen.getByText(/Next: Switch provider/)).toBeInTheDocument();
    await user.click(screen.getByText("Show technical details"));
    expect(screen.getByText(/usage limit/)).toBeInTheDocument();
  });

  it("renders preview panel empty, working, preview, no HTML, code selection, and plural badge", async () => {
    const user = userEvent.setup();
    const { rerender } = render(<PreviewPanel />);
    expect(screen.getByText("Start building to see your project here.")).toBeInTheDocument();
    useProjectStore.setState({ projectStatus: "building" });
    rerender(<PreviewPanel />);
    expect(screen.getByText("Generating files... Preview will appear soon.")).toBeInTheDocument();
    expect(screen.getByText("Agents are working...")).toBeInTheDocument();

    seedFiles();
    rerender(<PreviewPanel />);
    expect(screen.getByText("4 files")).toBeInTheDocument();
    expect(screen.getByTitle("Preview")).toHaveAttribute("srcDoc", expect.stringContaining("body{color:red}"));
    await user.click(screen.getByRole("button", { name: /Editor/ }));
    expect(screen.getByText("Select a file to view its code.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /app.js/ }));
    expect(screen.getByText("console.log('x')")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /App Viewer/ }));

    useProjectStore.setState({ files: [{ file_path: "readme.md", content: "# Hi" }] });
    rerender(<PreviewPanel />);
    expect(screen.getByText("1 file")).toBeInTheDocument();
    expect(screen.getByText("No HTML file found to preview.")).toBeInTheDocument();
  });

  it("drags split pane and cleans up body styles", () => {
    render(<SplitPane defaultSplit={30} left={<div>Left</div>} right={<div>Right</div>} />);
    const divider = screen.getByText("Left").parentElement!.nextElementSibling as HTMLElement;
    const container = divider.parentElement as HTMLElement;
    vi.spyOn(container, "getBoundingClientRect").mockReturnValue({ left: 0, width: 1000, top: 0, bottom: 0, right: 1000, height: 100, x: 0, y: 0, toJSON: () => ({}) });
    fireEvent.mouseDown(divider);
    expect(document.body.style.cursor).toBe("col-resize");
    act(() => window.dispatchEvent(new MouseEvent("mousemove", { clientX: 900 })));
    expect(screen.getByText("Left").parentElement).toHaveStyle({ width: "80%" });
    act(() => window.dispatchEvent(new MouseEvent("mousemove", { clientX: 100 })));
    expect(screen.getByText("Left").parentElement).toHaveStyle({ width: "20%" });
    act(() => window.dispatchEvent(new MouseEvent("mouseup")));
    expect(document.body.style.cursor).toBe("");
  });

  it("shows a bounded token budget while preparing", () => {
    useProjectStore.setState({
      projectStatus: "building",
      currentPhase: "",
      phasePercent: null,
      tokenBudget: 2000,
      tokenUsage: { total_tokens: 100, prompt_tokens: 60, completion_tokens: 40, successful_requests: 1 },
    });
    render(<UsageSummary />);
    expect(screen.getByText("of 2.0k · 5%")).toBeInTheDocument();
    expect(screen.getByText("Preparing")).toBeInTheDocument();
  });

  it("switches mobile workspace tabs and resizes panels with the keyboard", async () => {
    const user = userEvent.setup();
    render(<SplitPane left={<div>Activity content</div>} right={<div>Preview content</div>} />);
    const activityTab = screen.getByRole("tab", { name: "Activity" });
    const previewTab = screen.getByRole("tab", { name: "Preview" });
    expect(activityTab).toHaveAttribute("aria-selected", "true");
    await user.click(previewTab);
    expect(previewTab).toHaveAttribute("aria-selected", "true");
    await user.click(activityTab);
    expect(activityTab).toHaveAttribute("aria-selected", "true");

    const divider = screen.getByRole("separator");
    fireEvent.keyDown(divider, { key: "ArrowRight" });
    expect(divider).toHaveAttribute("aria-valuenow", "45");
    fireEvent.keyDown(divider, { key: "ArrowLeft" });
    expect(divider).toHaveAttribute("aria-valuenow", "40");
    fireEvent.keyDown(divider, { key: "Escape" });
    expect(divider).toHaveAttribute("aria-valuenow", "40");
  });
});
