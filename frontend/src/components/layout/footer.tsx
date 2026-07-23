import { Cpu } from "lucide-react";

export function Footer() {
  return (
    <footer className="border-t border-border bg-background py-12">
      <div className="mx-auto max-w-7xl px-6">
        <div className="flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent">
              <Cpu className="h-4 w-4 text-white" />
            </div>
            <span className="font-semibold text-foreground">Neutron</span>
          </div>
          <div className="text-center text-sm text-muted md:text-right">
            <p>Multi-agent AI development platform, built with CrewAI.</p>
            <p className="mt-1 text-xs">Neutron is independent and is not affiliated with, endorsed by, or sponsored by CrewAI.</p>
          </div>
        </div>
      </div>
    </footer>
  );
}
