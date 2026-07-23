import { act, fireEvent, render, renderHook, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ErrorBoundary from "@/app/error";
import ProjectErrorBoundary from "@/app/project/[id]/error";
import { PreviewPanel } from "@/components/workspace/preview-panel";
import { api } from "@/lib/api";
import { useProjectStore } from "@/stores/project-store";
import { useProjectWebSocket } from "@/hooks/use-websocket";
import { MockWebSocket } from "./mocks/websocket";

describe("API production hardening", () => {
  it("uses backend error details when requests fail", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Invalid upload" }), {
        status: 415,
        statusText: "Unsupported Media Type",
        headers: { "content-type": "application/json" },
      })
    ));

    await expect(api.listProjects()).rejects.toThrow("Invalid upload");
  });

  it("times out hanging requests", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("fetch", vi.fn((_url: string, init?: RequestInit) => new Promise((_resolve, reject) => {
      init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
    })));

    const promise = api.listProjects();
    vi.advanceTimersByTime(30_000);

    await expect(promise).rejects.toThrow("Request timed out");
    vi.useRealTimers();
  });

  it("surfaces upload errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response("Too large", { status: 413, statusText: "Payload Too Large" })
    ));

    await expect(api.uploadFile("p1", new File(["x"], "x.txt", { type: "text/plain" }))).rejects.toThrow("Too large");
  });

  it("handles message, empty, generic, and unreadable error bodies", async () => {
    vi.stubGlobal("fetch", vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ message: "Backend says no" }), {
        status: 400,
        statusText: "Bad Request",
        headers: { "content-type": "application/json" },
      }))
      .mockResolvedValueOnce(new Response("", { status: 500, statusText: "Server Error" }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ error: true }), {
        status: 502,
        statusText: "Bad Gateway",
        headers: { "content-type": "application/json" },
      }))
      .mockResolvedValueOnce({
        ok: false,
        status: 503,
        statusText: "Unavailable",
        text: vi.fn().mockRejectedValue(new Error("body failed")),
      })
    );

    await expect(api.listProjects()).rejects.toThrow("Backend says no");
    await expect(api.listProjects()).rejects.toThrow("API error: 500 Server Error");
    await expect(api.listProjects()).rejects.toThrow("API error: 502 Bad Gateway");
    await expect(api.listProjects()).rejects.toThrow("API error: 503 Unavailable");
  });

  it("gets and saves project connector settings", async () => {
    const connectorSettings = { custom_mcp_servers: [] };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(connectorSettings), {
        headers: { "content-type": "application/json" },
      }))
      .mockResolvedValueOnce(new Response(JSON.stringify(connectorSettings), {
        headers: { "content-type": "application/json" },
      }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.getProjectConnectors("p1")).resolves.toEqual(connectorSettings);
    await expect(api.saveProjectConnectors("p1", connectorSettings)).resolves.toEqual(connectorSettings);
    expect(fetchMock).toHaveBeenNthCalledWith(2, "http://localhost:8000/api/projects/p1/connectors", expect.objectContaining({
      method: "PUT",
      body: JSON.stringify(connectorSettings),
    }));
  });
});

describe("WebSocket reconnect behavior", () => {
  it("reconnects after an unexpected close", () => {
    vi.useFakeTimers();
    renderHook(() => useProjectWebSocket("project-1"));

    expect(MockWebSocket.instances).toHaveLength(1);
    act(() => {
      MockWebSocket.instances[0].close();
      vi.advanceTimersByTime(1_000);
    });

    expect(MockWebSocket.instances).toHaveLength(2);
    vi.useRealTimers();
  });

  it("reports malformed server messages", () => {
    renderHook(() => useProjectWebSocket("project-1"));
    const ws = MockWebSocket.instances[0];
    act(() => {
      ws.open();
      ws.messageRaw("not json");
    });

    expect(useProjectStore.getState().messages[0].content).toBe("Received an invalid server message.");
  });

  it("ignores lifecycle events after the hook unmounts", () => {
    const { unmount } = renderHook(() => useProjectWebSocket("project-1"));
    const ws = MockWebSocket.instances[0];

    unmount();
    act(() => {
      ws.open();
      ws.message({ type: "phase_start", phase: "leading", message: "late event" });
      ws.error();
      ws.close();
    });

    expect(useProjectStore.getState().messages).toHaveLength(0);
  });

  it("ignores events from replaced websocket connections", () => {
    const { rerender } = renderHook(({ id }) => useProjectWebSocket(id), { initialProps: { id: "project-1" } });
    const firstSocket = MockWebSocket.instances[0];

    act(() => firstSocket.open());
    rerender({ id: "project-2" });

    act(() => {
      firstSocket.message({ type: "phase_start", phase: "leading", message: "stale event" });
      firstSocket.close();
    });

    expect(useProjectStore.getState().messages).toHaveLength(0);
    expect(MockWebSocket.instances.at(-1)?.url).toBe("ws://localhost:8000/ws/project/project-2");
  });

  it("does not open a delayed reconnect after unmount", () => {
    vi.useFakeTimers();
    const { unmount } = renderHook(() => useProjectWebSocket("project-1"));

    act(() => {
      MockWebSocket.instances[0].close();
    });
    unmount();
    act(() => {
      vi.advanceTimersByTime(10_000);
    });

    expect(MockWebSocket.instances).toHaveLength(1);
    vi.useRealTimers();
  });

  it("stops reconnecting after the retry limit", () => {
    vi.useFakeTimers();
    renderHook(() => useProjectWebSocket("project-1"));

    for (let i = 0; i < 6; i += 1) {
      act(() => {
        MockWebSocket.instances.at(-1)?.close();
        vi.advanceTimersByTime(10_000);
      });
    }

    expect(useProjectStore.getState().messages.at(-1)?.content).toBe("Connection lost. Refresh the page to reconnect.");
    vi.useRealTimers();
  });
});

describe("Preview panel hardening", () => {
  it("accepts sandbox preview console messages only from null origin and caps entries", () => {
    let id = 0;
    vi.spyOn(crypto, "randomUUID").mockImplementation(() => `test-uuid-${id++}` as `${string}-${string}-${string}-${string}-${string}`);
    useProjectStore.getState().setFiles([{ file_path: "index.html", content: "<html><body></body></html>" }]);
    render(<PreviewPanel />);

    act(() => {
      window.dispatchEvent(new MessageEvent("message", {
        origin: "https://evil.example",
        data: { source: "neutron-preview", type: "console", level: "error", message: "bad" },
      }));
      window.dispatchEvent(new MessageEvent("message", {
        origin: "null",
        source: window,
        data: { source: "neutron-preview", type: "console", level: "error", message: "wrong frame" },
      }));
      window.dispatchEvent(new MessageEvent("message", {
        origin: "null",
        data: { source: "other", type: "console", level: "error", message: "ignored source" },
      }));
      window.dispatchEvent(new MessageEvent("message", {
        origin: "null",
        data: null,
      }));

      for (let i = 0; i < 101; i += 1) {
        window.dispatchEvent(new MessageEvent("message", {
          origin: "null",
          data: { source: "neutron-preview", type: "console", level: "error", message: `err-${i}` },
        }));
      }
    });

    fireEvent.click(screen.getByRole("button", { name: /console/i }));

    expect(screen.queryByText("bad")).not.toBeInTheDocument();
    expect(screen.queryByText("wrong frame")).not.toBeInTheDocument();
    expect(screen.queryByText("ignored source")).not.toBeInTheDocument();
    expect(screen.queryByText("err-0")).not.toBeInTheDocument();
    expect(screen.getByText("err-100")).toBeInTheDocument();
  });

  it("handles fallback preview message values", () => {
    useProjectStore.getState().setFiles([{ file_path: "index.html", content: "<html><body></body></html>" }]);
    render(<PreviewPanel />);

    act(() => {
      window.dispatchEvent(new MessageEvent("message", {
        origin: "null",
        data: { source: "neutron-preview", type: "console", level: "debug", message: "fallback level" },
      }));
      window.dispatchEvent(new MessageEvent("message", {
        origin: "null",
        data: { source: "neutron-preview", type: "console", level: "warn" },
      }));
      window.dispatchEvent(new MessageEvent("message", {
        origin: "null",
        data: { source: "neutron-preview", type: "element-selected" },
      }));
    });

    fireEvent.click(screen.getByRole("button", { name: /console/i }));
    expect(screen.getByText("fallback level")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /app viewer/i }));
    expect(screen.getByText("<element>")).toBeInTheDocument();
    expect(screen.getByText("Edit with Ravi")).toBeInTheDocument();
  });

  it("opens previews with a temporary blob URL", () => {
    useProjectStore.getState().setFiles([{ file_path: "index.html", content: "<html><body></body></html>" }]);
    const open = vi.spyOn(window, "open").mockReturnValue(null);
    const createObjectURL = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:test");
    const revokeObjectURL = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);

    vi.useFakeTimers();
    render(<PreviewPanel />);
    fireEvent.click(screen.getByRole("button", { name: /open/i }));
    vi.advanceTimersByTime(1_000);

    expect(createObjectURL).toHaveBeenCalled();
    expect(open).toHaveBeenCalledWith("blob:test", "_blank", "noopener,noreferrer");
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:test");
    vi.useRealTimers();
  });
});

describe("error boundaries", () => {
  it("renders the global retry UI", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    const retry = vi.fn();
    render(<ErrorBoundary error={new Error("boom")} unstable_retry={retry} />);

    fireEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(retry).toHaveBeenCalledOnce();
  });

  it("renders the global digest when present", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    const error = Object.assign(new Error("boom"), { digest: "abc123" });
    render(<ErrorBoundary error={error} unstable_retry={vi.fn()} />);

    expect(screen.getByText("Error ID: abc123")).toBeInTheDocument();
  });

  it("renders the project retry UI", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    const retry = vi.fn();
    render(<ProjectErrorBoundary error={new Error("boom")} unstable_retry={retry} />);

    fireEvent.click(screen.getByRole("button", { name: /reload workspace/i }));
    expect(retry).toHaveBeenCalledOnce();
  });

  it("renders the project digest when present", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    const error = Object.assign(new Error("boom"), { digest: "project123" });
    render(<ProjectErrorBoundary error={error} unstable_retry={vi.fn()} />);

    expect(screen.getByText("Error ID: project123")).toBeInTheDocument();
  });
});
