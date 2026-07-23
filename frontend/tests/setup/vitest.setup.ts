import "@testing-library/jest-dom/vitest";
import React from "react";
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";
import { resetProjectStore } from "../utils/store";
import { resetNextNavigationMocks } from "../mocks/next-navigation";
import { MockWebSocket } from "../mocks/websocket";
import { useAuthStore } from "@/stores/auth-store";

vi.mock("next/navigation", () => import("../mocks/next-navigation"));

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: React.ReactNode }) =>
    React.createElement("a", { href, ...props }, children),
}));

vi.mock("@vercel/analytics/next", () => ({
  Analytics: () => null,
}));

vi.mock("next/font/google", () => ({
  Geist: () => ({ className: "mock-geist", variable: "mock-geist-variable", style: { fontFamily: "Geist" } }),
  Geist_Mono: () => ({ className: "mock-geist-mono", variable: "mock-geist-mono-variable", style: { fontFamily: "Geist Mono" } }),
}));

interface MockHighlightProps {
  style: { color: string };
  tokens: { content: string }[][];
  getLineProps: () => Record<string, never>;
  getTokenProps: ({ token }: { token: { content: string } }) => { children: string };
}

vi.mock("prism-react-renderer", () => ({
  themes: { nightOwl: {} },
  Highlight: ({ code, children }: { code: string; children: (props: MockHighlightProps) => React.ReactNode }) =>
    children({
      style: { color: "white" },
      tokens: code.split("\n").map((line) => [{ content: line }]),
      getLineProps: () => ({}),
      getTokenProps: ({ token }: { token: { content: string } }) => ({ children: token.content }),
    }),
}));

Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

class ResizeObserverMock {
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
}

class IntersectionObserverMock {
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
  takeRecords = vi.fn(() => []);
}

vi.stubGlobal("ResizeObserver", ResizeObserverMock);
vi.stubGlobal("IntersectionObserver", IntersectionObserverMock);
vi.stubGlobal("WebSocket", MockWebSocket);

Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
  configurable: true,
  value: vi.fn(),
});

if (!globalThis.crypto) {
  Object.defineProperty(globalThis, "crypto", { value: {}, configurable: true });
}
Object.defineProperty(globalThis.crypto, "randomUUID", {
  configurable: true,
  value: vi.fn(() => "test-uuid"),
});

afterEach(() => {
  cleanup();
  resetProjectStore();
  useAuthStore.setState({ user: { id: "user-1", email: "user@example.com", display_name: null, created_at: "2026-01-01" }, loading: false, error: null });
  resetNextNavigationMocks();
  MockWebSocket.reset();
  document.body.style.overflow = "";
  document.body.style.cursor = "";
  document.body.style.userSelect = "";
  vi.clearAllMocks();
});