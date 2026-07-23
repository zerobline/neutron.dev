import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { Header } from "@/components/layout/header";

describe("Header extended", () => {
  it("toggles theme between dark and light", async () => {
    const user = userEvent.setup();
    render(<Header />);

    const themeBtn = screen.getByRole("button", { name: "Toggle theme" });
    await user.click(themeBtn);
    expect(document.documentElement.classList.contains("light")).toBe(true);
    expect(localStorage.getItem("neutron-theme")).toBe("light");

    await user.click(themeBtn);
    expect(document.documentElement.classList.contains("light")).toBe(false);
    expect(localStorage.getItem("neutron-theme")).toBe("dark");
  });

  it("opens and closes the settings modal", async () => {
    const user = userEvent.setup();
    render(<Header />);
    await user.click(screen.getByRole("button", { name: "Settings" }));
    expect(screen.getByRole("button", { name: "Close settings" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Close settings" }));
    expect(screen.queryByRole("button", { name: "Close settings" })).not.toBeInTheDocument();
  });

  it("renders profile link", () => {
    render(<Header />);
    expect(screen.getByRole("link", { name: "Profile" })).toHaveAttribute("href", "/profile");
  });
});
