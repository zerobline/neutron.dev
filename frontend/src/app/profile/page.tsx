"use client";

import { useState } from "react";
import { Header } from "@/components/layout/header";
import { Footer } from "@/components/layout/footer";
import { SettingsModal } from "@/components/settings/settings-modal";
import { Button } from "@/components/ui/button";
import { User, Settings, KeyRound, Search } from "lucide-react";

type SettingsSection = "general" | "connectors" | "billing" | "cloud" | "search" | "account" | "help";

function ProfileContent() {
  const [settingsSection, setSettingsSection] = useState<SettingsSection>("general");
  const [settingsOpen, setSettingsOpen] = useState(() => {
    /* v8 ignore next */
    if (typeof window === "undefined") return false;
    return new URLSearchParams(window.location.search).get("settings") === "globalControl";
  });

  const openSettings = (section: SettingsSection = "general") => {
    setSettingsSection(section);
    setSettingsOpen(true);
  };

  return (
    <main className="flex-1">
      <div className="mx-auto max-w-4xl px-6 py-12">
        <div className="rounded-3xl border border-border bg-surface p-8">
          <div className="flex items-center gap-5">
            <div className="h-16 w-16 rounded-2xl bg-accent text-white flex items-center justify-center">
              <User className="h-8 w-8" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-foreground">Profile</h1>
              <p className="text-muted">Manage your local Neutron workspace.</p>
            </div>
          </div>

          <div className="mt-8 grid gap-4 sm:grid-cols-2">
            <button onClick={() => openSettings("general")} className="rounded-2xl border border-border bg-background p-5 text-left hover:border-accent/40 transition-colors cursor-pointer">
              <Settings className="h-5 w-5 text-accent mb-3" />
              <h2 className="font-semibold text-foreground">Global Control</h2>
              <p className="text-sm text-muted mt-1">API keys, providers, default model, theme, permissions.</p>
            </button>
            <button onClick={() => openSettings("cloud")} className="rounded-2xl border border-border bg-background p-5 text-left hover:border-accent/40 transition-colors cursor-pointer">
              <KeyRound className="h-5 w-5 text-accent mb-3" />
              <h2 className="font-semibold text-foreground">Credentials</h2>
              <p className="text-sm text-muted mt-1">Set the AI provider, model, base URL, and API key for backend agent runs.</p>
            </button>
            <button onClick={() => openSettings("search")} className="rounded-2xl border border-border bg-background p-5 text-left hover:border-accent/40 transition-colors cursor-pointer">
              <Search className="h-5 w-5 text-accent mb-3" />
              <h2 className="font-semibold text-foreground">Search APIs</h2>
              <p className="text-sm text-muted mt-1">Store encrypted Brave, Serper, Tavily, and Exa credentials for research tools.</p>
            </button>
          </div>

          <Button className="mt-8" onClick={() => openSettings("general")}>
            Open Settings
          </Button>
        </div>
      </div>
      <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} initialSection={settingsSection} />
    </main>
  );
}

export default function ProfilePage() {
  return (
    <>
      <Header />
      <ProfileContent />
      <Footer />
    </>
  );
}
