import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LoginForm } from "@/components/auth/login-form";
import { useAuthStore } from "@/stores/auth-store";

const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

describe("LoginForm", () => {
  beforeEach(() => {
    pushMock.mockReset();
    useAuthStore.setState({
      user: null,
      loading: false,
      error: null,
      refreshMe: async () => {},
      login: vi.fn(async () => {
        useAuthStore.setState({ user: { id: "u1", email: "user@example.com", display_name: null, created_at: "2026-01-01" }, loading: false });
      }),
      register: vi.fn(async () => {
        useAuthStore.setState({ user: { id: "u1", email: "user@example.com", display_name: "User", created_at: "2026-01-01" }, loading: false });
      }),
      logout: vi.fn(),
    });
  });

  it("renders login mode and submits credentials", async () => {
    const user = userEvent.setup();
    render(<LoginForm />);

    expect(screen.getByRole("heading", { name: "Log in to Neutron" })).toBeInTheDocument();
    await user.type(screen.getByLabelText("Email"), "user@example.com");
    await user.type(screen.getByLabelText("Password"), "password123");
    await user.click(screen.getByRole("button", { name: "Log in" }));

    expect(useAuthStore.getState().login).toHaveBeenCalledWith("user@example.com", "password123");
    expect(pushMock).toHaveBeenCalledWith("/dashboard");
  });

  it("switches to register mode and submits account details", async () => {
    const user = userEvent.setup();
    render(<LoginForm />);

    await user.click(screen.getByRole("button", { name: "Need an account? Create one" }));
    expect(screen.getByRole("heading", { name: "Create your account" })).toBeInTheDocument();
    expect(screen.getByLabelText("Display name")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Display name"), "User");
    await user.type(screen.getByLabelText("Email"), "user@example.com");
    await user.type(screen.getByLabelText("Password"), "password123");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(useAuthStore.getState().register).toHaveBeenCalledWith("user@example.com", "password123", "User");
    expect(pushMock).toHaveBeenCalledWith("/dashboard");
  });

  it("shows loading and error states", async () => {
    useAuthStore.setState({ loading: true, error: "Invalid credentials" });
    render(<LoginForm />);

    expect(screen.getByRole("button", { name: "Working..." })).toBeDisabled();
    expect(screen.getByText("Invalid credentials")).toBeInTheDocument();
  });

  it("switches back to login mode from register", async () => {
    const user = userEvent.setup();
    render(<LoginForm />);

    await user.click(screen.getByRole("button", { name: "Need an account? Create one" }));
    await user.click(screen.getByRole("button", { name: "Already have an account? Log in" }));
    expect(screen.getByRole("heading", { name: "Log in to Neutron" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Display name")).not.toBeInTheDocument();
  });
});