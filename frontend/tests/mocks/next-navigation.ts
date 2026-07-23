import { vi } from "vitest";

export const pushMock = vi.fn();
export const replaceMock = vi.fn();
export const backMock = vi.fn();
export const refreshMock = vi.fn();
export const prefetchMock = vi.fn();

let pathname = "/";
let params: Record<string, string> = { id: "project-1" };
let searchParams = new URLSearchParams();

export function setMockPathname(value: string) {
  pathname = value;
}

export function setMockParams(value: Record<string, string>) {
  params = value;
}

export function setMockSearchParams(value: string | Record<string, string>) {
  searchParams = typeof value === "string" ? new URLSearchParams(value) : new URLSearchParams(value);
}

export function resetNextNavigationMocks() {
  pathname = "/";
  params = { id: "project-1" };
  searchParams = new URLSearchParams();
  pushMock.mockReset();
  replaceMock.mockReset();
  backMock.mockReset();
  refreshMock.mockReset();
  prefetchMock.mockReset();
}

export function useRouter() {
  return {
    push: pushMock,
    replace: replaceMock,
    back: backMock,
    refresh: refreshMock,
    prefetch: prefetchMock,
  };
}

export function usePathname() {
  return pathname;
}

export function useParams() {
  return params;
}

export function useSearchParams() {
  return searchParams;
}
