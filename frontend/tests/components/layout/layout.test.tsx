import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Footer } from "@/components/layout/footer";
import { Header } from "@/components/layout/header";
import { useAuthStore } from "@/stores/auth-store";
import { pushMock, setMockPathname } from "../../mocks/next-navigation";

describe("layout components", () => {
  it("renders header links and active nav state", () => {
    setMockPathname("/templates");
    render(<Header />);

    expect(screen.getByRole("link", { name: /Neutron/i })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "Templates" })).toHaveAttribute("href", "/templates");
    expect(screen.getByRole("link", { name: "Templates" })).toHaveClass("bg-surface");
    expect(screen.getByRole("link", { name: "Dashboard" })).toHaveAttribute("href", "/dashboard");
    expect(screen.getByRole("button", { name: "Start Building" })).toBeInTheDocument();
  });

  it("renders inactive dashboard header state", () => {
    setMockPathname("/other");
    render(<Header />);
    expect(screen.getByRole("link", { name: "Dashboard" })).toHaveClass("text-muted");
  });

  it("logs out and redirects to login", async () => {
    const user = userEvent.setup();
    const logout = vi.fn(async () => {
      useAuthStore.setState({ user: null, loading: false, error: null });
    });
    useAuthStore.setState({
      user: { id: "user-1", email: "user@example.com", display_name: null, created_at: "2026-01-01" },
      loading: false,
      error: null,
      refreshMe: async () => {},
      login: vi.fn(),
      register: vi.fn(),
      logout,
    });
    render(<Header />);

    await user.click(screen.getByRole("button", { name: "Logout" }));
    expect(logout).toHaveBeenCalled();
    expect(pushMock).toHaveBeenCalledWith("/login");
  });

  it("renders footer branding", () => {
    render(<Footer />);
    expect(screen.getByText("Neutron")).toBeInTheDocument();
    expect(screen.getByText(/built with CrewAI/i)).toBeInTheDocument();
    expect(screen.getByText(/not affiliated with, endorsed by, or sponsored by CrewAI/)).toBeInTheDocument();
  });
});
