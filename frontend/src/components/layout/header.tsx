"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { Cpu, Settings, Sun, Moon, User } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SettingsModal } from "@/components/settings/settings-modal";
import { useAuthStore } from "@/stores/auth-store";

export function Header() {
  const pathname = usePathname();
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const refreshMe = useAuthStore((s) => s.refreshMe);
  const logout = useAuthStore((s) => s.logout);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [themeReady, setThemeReady] = useState(false);

  useEffect(() => {
    const stored = (localStorage.getItem("neutron-theme") as "dark" | "light" | null) ?? "dark";
    // Hydrate client-only persisted theme after the server render.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setTheme(stored);
    document.documentElement.classList.toggle("light", stored === "light");
    setThemeReady(true);
  }, []);

  useEffect(() => {
    if (!themeReady) return;
    document.documentElement.classList.toggle("light", theme === "light");
    localStorage.setItem("neutron-theme", theme);
  }, [theme, themeReady]);

  useEffect(() => {
    void refreshMe();
  }, [refreshMe]);

  const toggleTheme = () => {
    setTheme((current) => (current === "dark" ? "light" : "dark"));
  };

  const handleLogout = async () => {
    await logout();
    router.push("/login");
  };

  return (
    <>
      <header className="sticky top-0 z-40 border-b border-border bg-background/80 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent shadow-lg shadow-accent/20">
              <Cpu className="h-5 w-5 text-white" />
            </div>
            <span className="text-xl font-bold text-foreground">Neutron</span>
          </Link>

          <nav className="hidden md:flex items-center gap-1">
            {[
              { href: "/templates", label: "Templates" },
              { href: "/dashboard", label: "Dashboard" },
            ].map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                className={cn(
                  "px-4 py-2 rounded-lg text-sm font-medium transition-colors",
                  pathname === href
                    ? "text-foreground bg-surface"
                    : "text-muted hover:text-foreground hover:bg-surface-hover"
                )}
              >
                {label}
              </Link>
            ))}
          </nav>

          <div className="flex items-center gap-2">
            <button onClick={toggleTheme} className="hidden sm:flex h-9 w-9 items-center justify-center rounded-lg text-muted hover:text-foreground hover:bg-surface-hover transition-colors cursor-pointer" aria-label="Toggle theme">
              {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>
            {user ? (
              <>
                <Link href="/profile" className="hidden sm:flex h-9 w-9 items-center justify-center rounded-lg text-muted hover:text-foreground hover:bg-surface-hover transition-colors" aria-label="Profile" title={user.email}>
                  <User className="h-4 w-4" />
                </Link>
                <button onClick={handleLogout} className="hidden sm:flex rounded-lg px-3 py-2 text-sm text-muted hover:text-foreground hover:bg-surface-hover transition-colors cursor-pointer">
                  Logout
                </button>
              </>
            ) : (
              <Link href="/login" className="hidden sm:flex rounded-lg px-3 py-2 text-sm text-muted hover:text-foreground hover:bg-surface-hover transition-colors">
                Login
              </Link>
            )}
            <button onClick={() => setSettingsOpen(true)} className="hidden sm:flex h-9 w-9 items-center justify-center rounded-lg text-muted hover:text-foreground hover:bg-surface-hover transition-colors cursor-pointer" aria-label="Settings">
              <Settings className="h-4 w-4" />
            </button>
            <Link href={user ? "/dashboard" : "/login"}>
              <Button size="sm">Start Building</Button>
            </Link>
          </div>
        </div>
      </header>
      <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </>
  );
}
